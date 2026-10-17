#!/usr/bin/env python3
"""Explicit USB provisioning. Importing/--help never opens a device or resets it."""
import argparse
import json
import os
from pathlib import Path
import stat
import time

FIELDS = {'schema_version','device_id','ssid','wifi_password','gateway_url','token','ca_pem',
          'interval_seconds','wifi_timeout_ms','http_timeout_ms'}

def read_private(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode)&0o077:
        raise ValueError('El archivo debe ser privado (0600), regular y sin enlace simbólico')
    if path.stat().st_size>4096:raise ValueError('Configuración demasiado grande')
    value=json.loads(path.read_text())
    if not isinstance(value,dict) or set(value)!=FIELDS:raise ValueError('Campos de configuración incorrectos')
    return value

def wire(value,epoch):
    if type(epoch) is not int or not 1577836800<=epoch<=4102444800:raise ValueError('UTC fuera de rango')
    payload=dict(value,seed_utc=epoch)
    # Firmware accepts printable ASCII with standard escaped PEM newlines, no unicode escapes.
    body=json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode('ascii')
    if len(body)>4096 or b'\n' in body or b'\\u' in body:raise ValueError('Configuración inválida o demasiado grande')
    return b'IBPROV1 '+body+b'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--port',required=True)
    parser.add_argument('--confirm-trusted-host-time',action='store_true',required=True)
    args=parser.parse_args()
    try:
        value=read_private(args.config)
        import serial  # Provided by the pinned SDK environment, not another runtime dependency.
        channel=serial.Serial()
        channel.port=args.port;channel.baudrate=115200;channel.timeout=.25;channel.write_timeout=2
        channel.dtr=False;channel.rts=False;channel.open()  # No reset/bootloader commands.
        with channel:
            deadline=time.monotonic()+40
            print('Esperando IBPROV_READY; no se envían resets. Seguí el procedimiento físico documentado.')
            ready=False
            while time.monotonic()<deadline:
                line=channel.readline(256)
                if b'IBPROV_READY' in line:
                    channel.write(wire(value,int(time.time())));channel.flush();ready=True;break
            if not ready:raise RuntimeError('No apareció la ventana de provisión')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                line=channel.readline(256)
                if b'IBPROV_OK' in line:
                    print('Configuración aceptada; UTC provisto desde este host. No es validación física de M2.');return
                if b'IBPROV_ERROR' in line:raise RuntimeError('El dispositivo rechazó la configuración')
            raise RuntimeError('Sin confirmación; no reintentar automáticamente')
    except Exception:
        # Serial/config exceptions can contain private values: never print their repr or traceback.
        raise SystemExit('Provisión no completada. Revisá archivo privado, puerto y ventana USB; no hubo reset solicitado.') from None
if __name__=='__main__':main()
