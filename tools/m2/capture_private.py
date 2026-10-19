#!/usr/bin/env python3
"""Future phase B RX-only capture; NEVER run during phase A."""
import argparse
import os
from pathlib import Path
import time
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=120);p.add_argument('--authorized-read-m2',action='store_true',required=True)
    a=p.parse_args()
    target=a.output.expanduser().resolve()
    if target.is_relative_to(ROOT) or not 1<=a.seconds<=3600:p.error('Log fuera del repositorio y duración1..3600 s')
    import serial  # SDK dependency. Importing/help never opens a device.
    channel=serial.Serial(port=None,baudrate=115200,timeout=.25)
    channel.port=a.port;channel.dtr=False;channel.rts=False
    # Creation is exclusive and private; never truncate a log or backup.
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    total=0;disconnected=False
    try:
        with os.fdopen(fd,'wb') as output:
            channel.open()  # OS/USB effects still require physical observation.
            deadline=time.monotonic()+a.seconds
            while time.monotonic()<deadline and total<10*1024*1024:
                try:data=channel.read(1024)
                except serial.SerialException:disconnected=True;break
                output.write(data);output.flush();total+=len(data)
    except KeyboardInterrupt:pass
    finally:channel.close()
    print('Captura RX privada terminada: bytes='+str(total)+' desconexion='+str(disconnected)+'. Sin secuencias de reset, TX ni reapertura automática; no prueba sueño.')
if __name__=='__main__':main()
