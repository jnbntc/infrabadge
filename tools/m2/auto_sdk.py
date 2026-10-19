#!/usr/bin/env python3
"""Explicitly authorized one app load/setup OR read-only journal export.

Called only by automation.py after manifest approval. No auto retry, erase-all,
bootloader/table/eFuse write. Raw flash logs are private; serial TX/RX not logged.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from phase_a import SDK,save
from provision import read_private
import physical_first as first
from auto_report import validate
from auto_scope import authorization


def lines(channel,deadline):
    buffer=b''
    while time.monotonic()<deadline:
        data=channel.read(512)
        if not data:continue
        buffer+=data
        if len(buffer)>16384:raise first.StopTest('serial_frame_too_large')
        while b'\n' in buffer:
            line,buffer=buffer.split(b'\n',1)
            yield line.decode('ascii',errors='replace').strip()


def wait_export_ready(channel):
    return any(line=='IBAUTO_READY' for line in lines(channel,time.monotonic()+15))


def port_wait(list_ports):
    print('Esperando la única Waveshare USB. Si está dormida, pulsá BOOT brevemente una vez; después no tocar botones.',flush=True)
    end=time.monotonic()+30
    while time.monotonic()<end:
        ports=[p for p in list_ports.comports() if (p.vid,p.pid)==(0x303a,0x1001)]
        if len(ports)>1:raise first.StopTest('ambiguous_usb_target')
        if ports:return ports[0].device
        time.sleep(.1)
    raise first.StopTest('usb_target_not_visible')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approved-manifest',type=Path,required=True);p.add_argument('--action',choices=['load-setup','setup-existing','collect'],required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if os.geteuid()==0:raise first.StopTest('no_sudo_for_usb')
    os.umask(0o077)
    manifest=json.loads(a.approved_manifest.read_text());private=a.approved_manifest.parent
    mode=manifest.get('execution_mode','load_setup')
    if manifest['authorization']!=authorization(mode):raise first.StopTest('unsupported_authorization_scope')
    if a.action!='collect' and (a.action=='setup-existing')!=(mode=='setup_existing'):raise first.StopTest('usb_action_outside_scope')
    previous=None
    if mode=='setup_existing':
        data=(private/'previous-report.json').read_bytes()
        if hashlib.sha256(data).hexdigest()!=manifest.get('previous_journal_sha256'):raise first.StopTest('previous_journal_changed')
        previous=json.loads(data);validate(previous,previous['run'])
        if previous['phase'] not in (3,4) or previous['run']==manifest['run']:raise first.StopTest('previous_journal_not_terminal')
    sdk=os.environ.get('IDF_PATH')
    if not sdk or subprocess.check_output(['git','-C',sdk,'rev-parse','HEAD'],text=True).strip()!=SDK:raise first.StopTest('sdk_mismatch')
    image=private/'firmware/infrabadge.bin';data=image.read_bytes()
    if len(data)!=manifest['application']['bytes'] or hashlib.sha256(data).hexdigest()!=manifest['application']['sha256']:raise first.StopTest('image_changed')
    from serial.tools import list_ports
    import serial
    record=a.out/(a.action+'.json')
    if record.exists():raise first.StopTest('usb_action_already_attempted_no_retry')
    state={'action':a.action,'flash_attempted':False,'flash_completed':False,'setup_attempted':False,'setup_ack':False,'serial_opened':False}
    save(record,state)
    channel=None
    with (Path(tempfile.gettempdir())/('infrabadge-physical-'+str(os.getuid())+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            port=port_wait(list_ports)
            if a.action!='collect':
                stamp=json.loads((a.out/'host-preflight.json').read_text())
                if not 0<=time.time()-stamp['utc_checked_epoch']<90:raise first.StopTest('host_utc_preflight_too_old')
            if a.action=='load-setup':
                state['flash_attempted']=True;save(record,state)
                with (a.out/'flash-private.log').open('xb') as log:
                    status=subprocess.run(first.flash_command(port,image),stdout=log,stderr=subprocess.STDOUT,timeout=150).returncode
                if status:raise first.StopTest('flash_failed_no_retry')
                state['flash_completed']=True;save(record,state)
                end=time.monotonic()+8
                while not Path(port).exists() and time.monotonic()<end:time.sleep(.1)
            channel=serial.Serial(port=None,baudrate=115200,timeout=.2,write_timeout=3,exclusive=True)
            channel.port=port;channel.dtr=False;channel.rts=False;channel.open();state['serial_opened']=True;save(record,state)
            if a.action=='setup-existing':
                # One explicitly approved reset, using the locked esptool reset
                # strategy only. Never enter its flashing/erase command path.
                from esptool.reset import HardReset
                state['usb_reset_attempted']=True;save(record,state)
                HardReset(channel,uses_usb=True)()
                state['usb_reset_completed']=True;save(record,state)
                channel.close();time.sleep(1)
                port=port_wait(list_ports)
                channel=serial.Serial(port=None,baudrate=115200,timeout=.2,write_timeout=3,exclusive=True)
                channel.port=port;channel.dtr=False;channel.rts=False;channel.open()
            if a.action=='collect':
                # Terminal notification precedes Wi-Fi shutdown/USB driver setup.
                # Wait for readiness before TX; if READY was emitted before open,
                # the finite grace also avoids racing that handover. No reset/retry.
                state['export_ready_observed']=wait_export_ready(channel)
                save(record,state)
            channel.write(b'IBAUTO_EXPORT\n');channel.flush();previous_requested=True
            done=False
            for line in lines(channel,time.monotonic()+45):
                if a.action=='collect':
                    if line=='IBAUTO_READY':channel.write(b'IBAUTO_EXPORT\n');channel.flush()
                    if line.startswith('IBAUTO_REPORT '):
                        value=json.loads(line[len('IBAUTO_REPORT '):]);summary=validate(value,manifest['run'])
                        save(a.out/'device-report.json',value);save(a.out/'device-summary.json',summary);done=True;break
                    continue
                if line=='IBAUTO_READY':
                    if previous_requested:channel.write(b'IBAUTO_EXPORT\n');channel.flush()
                if (line.startswith('IBAUTO_REPORT ') or line=='IBAUTO_ERROR bad_journal') and not state['setup_attempted']:
                    if a.action=='setup-existing' and line=='IBAUTO_ERROR bad_journal':raise first.StopTest('existing_journal_missing_no_setup')
                    if line.startswith('IBAUTO_REPORT '):
                        prior=json.loads(line[len('IBAUTO_REPORT '):]);validate(prior,prior['run']);save(a.out/'previous-diagnostic-report.json',prior)
                        if a.action=='setup-existing' and (prior['run']!=previous['run'] or prior['phase'] not in (3,4)):
                            raise first.StopTest('installed_journal_mismatch_no_setup')
                    value=read_private(private/'device.json')
                    stamp=json.loads((a.out/'host-preflight.json').read_text())
                    if not 0<=time.time()-stamp['utc_checked_epoch']<90:raise first.StopTest('host_utc_stale_before_tx')
                    body=json.dumps({'run':manifest['run'],'config':dict(value,seed_utc=int(time.time()))},separators=(',',':'),ensure_ascii=True).encode('ascii')
                    if len(body)>4096:raise first.StopTest('setup_frame_too_large')
                    state['setup_attempted']=True;save(record,state)
                    channel.write(b'IBAUTO1 '+body+b'\n');channel.flush();del body,value
                elif line=='IBAUTO_OK':state['setup_ack']=True;save(record,state);done=True;break
                elif line=='IBAUTO_ERROR setup_rejected' and state['setup_attempted']:raise first.StopTest('setup_rejected_no_retry')
            if not done:raise first.StopTest('usb_reply_not_observed_no_retry')
            if a.action!='collect':
                # Do not close a live port directly after the ACK. Wait for the
                # first actual USB disappearance, without reopening or sending TX.
                end=time.monotonic()+60
                while time.monotonic()<end:
                    found=[p for p in list_ports.comports() if (p.vid,p.pid)==(0x303a,0x1001)]
                    if not found:state['usb_disappeared_after_setup']=True;break
                    time.sleep(.2)
                if not state.get('usb_disappeared_after_setup'):raise first.StopTest('first_usb_disappearance_not_observed')
            state['status']='completed';save(record,state)
        except (Exception,KeyboardInterrupt) as error:
            state['status']='partial';state['stop_reason']=str(error) if isinstance(error,first.StopTest) else type(error).__name__;save(record,state)
        finally:
            if channel:channel.close()
    print(a.action+': '+state['status']+'; sin reintento automático.',flush=True)
    return 0 if state['status']=='completed' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except (Exception,KeyboardInterrupt) as e:raise SystemExit('USB detenido: '+(str(e) if isinstance(e,first.StopTest) else type(e).__name__)+'. Sin otro intento.') from None
