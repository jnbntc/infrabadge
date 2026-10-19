#!/usr/bin/env python3
"""Correct a private host-side Wi-Fi configuration; never access the board."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from provision import read_private, wire


def active_ssid(interface):
    def query(*args):
        return subprocess.check_output(
            ['nmcli', '--escape', 'no', '-g', *args], text=True,
            stderr=subprocess.DEVNULL,
        ).rstrip('\n')
    uuid = query('GENERAL.CON-UUID', 'device', 'show', interface)
    if not uuid or '\n' in uuid:
        raise ValueError('No active connection')
    return query('802-11-wireless.ssid', 'connection', 'show', 'uuid', uuid)


def private_write(path, data):
    fd, name = tempfile.mkstemp(prefix='.wifi-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(json.dumps(data, indent=2) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Ejecutar SIN sudo')
    if not sys.stdin.isatty():
        parser.error('Se requiere una terminal interactiva para entrada sin eco')
    os.umask(0o077)
    try:
        private = args.private.resolve(strict=True)
        path = private / 'device.json'
        original = read_private(path)
        net = json.loads((private / 'network.json').read_text())
        ssid = active_ssid(net['interface'])
        if not 1 <= len(ssid.encode('ascii')) <= 32 or not all(32 <= ord(c) <= 126 for c in ssid):
            raise ValueError('SSID format unsupported by current firmware')
        print('Se usará la red Wi-Fi activa de esta notebook; su nombre no se registra.')
        password = getpass.getpass('Clave de esa Wi-Fi (sin eco): ')
        repeated = getpass.getpass('Repetí la clave (sin eco): ')
        if password != repeated or not 8 <= len(password) <= 63 or not all(32 <= ord(c) <= 126 for c in password):
            raise ValueError('Password confirmation or format')
        updated = dict(original, ssid=ssid, wifi_password=password)
        wire(updated, 1792270800)  # Encoding/size check only; no serial import or transmission.
        if active_ssid(net['interface']) != ssid:
            raise ValueError('Active connection changed during prompt')
        backup = private / 'device-before-wifi-correction.json'
        # Preserve the initial private configuration exactly once.
        with backup.open('x') as stream:
            stream.write(json.dumps(original, indent=2) + '\n')
        private_write(path, updated)
        check = read_private(path)
        assert check == updated
        private_write(args.result / 'wifi-preparation.json', {
            'status': 'prepared_for_current_host_wifi',
            'ssid_matches_active_connection': True,
            'password_entered_twice_without_echo': True,
            'wifi_association_tested': False,
            'only_ssid_and_password_updated': True,
            'ca_tokens_gateway_unchanged': True,
            'board_io_performed': False,
        })
        print('PASS: configuración privada preparada para la Wi-Fi activa; CA y tokens conservados.')
        print('No se probó la clave mediante asociación ni se accedió a la placa.')
        print('Resultados: ' + str(args.result))
    except (Exception, KeyboardInterrupt):
        raise SystemExit('Preparación detenida; no se abrió ni escribió la placa. No compartir claves.') from None


if __name__ == '__main__':
    main()
