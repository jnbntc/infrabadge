#!/usr/bin/env python3
"""Prepared second M2 diagnostic trial. Requires a NEW explicit authorization.

Importing, --help and --preflight never open USB. The original trial's consumed
authorization cannot invoke this load. Firmware bytes are frozen separately.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import physical_first as first
from phase_a import ROOT, save

PACK = ROOT / 'results/m2-supervised-20261017T225909Z-y0fhadop/approved-diagnostic-artifacts'
APP_SHA = '733f7b9b839bfeed966a3914a4e6015429ddbd73be7624cbf5a8d43a6686ac2f'


def verify_artifacts():
    if subprocess.check_output(['git', '-C', str(ROOT), 'remote', 'get-url', 'origin'], text=True).strip() != 'https://github.com/jnbntc/infrabadge.git':
        raise first.StopTest('wrong_repository')
    value = json.loads((PACK / 'manifest.json').read_text())
    for name, expected in value['artifacts'].items():
        data = (PACK / name).read_bytes()
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise first.StopTest('diagnostic_artifact_mismatch')
    for name, digest in value['firmware_inputs'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise first.StopTest('firmware_sources_changed_since_diagnostic_build')
    app = PACK / 'infrabadge.bin'
    if hashlib.sha256(app.read_bytes()).hexdigest() != APP_SHA:
        raise first.StopTest('wrong_diagnostic_application')
    sys.path.insert(0, str(ROOT / 'tools'))
    import verify_build
    if verify_build.inspect(PACK, 'connectivity')['artifacts'] != value['artifacts']:
        raise first.StopTest('diagnostic_build_verification')
    rollback = first.PHASE_A / 'rollback-m11'
    approved = json.loads((rollback / 'manifest.json').read_text())
    for name, expected in approved['artifacts'].items():
        data = (rollback / name).read_bytes()
        if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise first.StopTest('m11_rollback_mismatch')
    if (PACK / 'partition_table/partition-table.bin').read_bytes() != (rollback / 'partition_table/partition-table.bin').read_bytes():
        raise first.StopTest('partition_layout_changed')
    match = re.search(r'SHA-256:\s*`([0-9a-f]{64})`', first.FACTORY_RECORD.read_text())
    if not match or first.FACTORY.stat().st_size != 8388608:
        raise first.StopTest('factory_backup_unavailable')
    with first.FACTORY.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != match[1]:
            raise first.StopTest('factory_backup_mismatch')
    return app


def previous_attempt():
    for record in (ROOT / 'results').glob('m2-physical-diagnostic-*/result.json'):
        result = json.loads(record.read_text())
        if result.get('app_sha256') == APP_SHA and result.get('flash_attempted'):
            return record.parent
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--authorized-m2-diagnostic', action='store_true', help='Only after NEW authorization for app SHA733f7b9b and one USB provisioning')
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--port', help=argparse.SUPPRESS)
    parser.add_argument('--results', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Ejecutar SIN sudo')
    os.umask(0o077)
    if args.preflight:
        first.host_preflight(artifact_verifier=verify_artifacts)
        print('Preflight diagnóstico PASS; sin abrir USB ni escribir firmware.')
        return
    if not args.authorized_m2_diagnostic or not sys.stdin.isatty():
        parser.error('Se requiere NUEVA autorización y --authorized-m2-diagnostic en terminal normal')
    if args.inside:
        if not args.port or not args.results:
            parser.error('Faltan parámetros del host')
        raise SystemExit(first.physical(args, artifact_verifier=verify_artifacts, app_sha=APP_SHA, allow_setup_wake=True))
    try:
        with (Path(tempfile.gettempdir()) / ('infrabadge-physical-' + str(os.getuid()) + '.lock')).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            previous = previous_attempt()
            if previous:
                raise first.StopTest('La carga de diagnóstico ya se intentó. Resultados: ' + str(previous))
            preflight = first.host_preflight(artifact_verifier=verify_artifacts)
            port = first.detect_host()
            out = Path(tempfile.mkdtemp(prefix='m2-physical-diagnostic-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'), dir=ROOT / 'results'))
            save(out / 'host-preflight.json', preflight)
            print('Resultados: ' + str(out), flush=True)
            command = ['distrobox', 'enter', '--name', 'iot-dev', '--', '/usr/local/bin/idf-env', 'python3', str(Path(__file__).resolve()), '--inside', '--authorized-m2-diagnostic', '--port', port, '--results', str(out)]
            raise SystemExit(subprocess.run(command).returncode)
    except Exception as error:
        raise SystemExit('Diagnóstico detenido: ' + (str(error) if isinstance(error, first.StopTest) else type(error).__name__) + '. Sin otra carga ni reset automático.') from None


if __name__ == '__main__':
    main()
