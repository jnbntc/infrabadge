#!/usr/bin/env python3
"""One explicitly authorized M2 application load and first USB-provisioned query.

No erase-all, bootloader/partition write, automatic flash retry, eFuse operation,
TLS bypass or restoration. Raw serial input and provisioning TX are not logged.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import time

from phase_a import ROOT, SDK, save, source_check
from provision import read_private, wire
from sanitize_logs import ANSI, sanitize

LAB = Path('/var/home/juanb/.local/share/infrabadge-lab/phase-a-20261017T220757Z')
PHASE_A = ROOT / 'results/m2-phase-a-20261017T220757Z'
APP_SHA = '0553e5bb71ba22c45e520af3523b74aedbcb2d37b718160b66e45bacdc613878'
CA_SHA = 'adc0ebe766de4d216ce759bc261926cc896e8760a0b5ae8fbdd23b2efa019baa'
FACTORY = Path('/var/home/juanb/Backups/esp32/infrabadge/waveshare-v2-factory-8mb.bin')
FACTORY_RECORD = Path('/var/home/juanb/.codex/attachments/51fb069a-8fe3-4cbc-900a-00ddbe2f5a11/Pasted text.txt')


class StopTest(Exception):
    """Messages are fixed safe diagnostic categories, never device output."""


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def yes(prompt):
    return input(prompt + ' [s/n]: ').strip().lower() in ('s', 'si', 'sí', 'yes', 'y')


def flash_command(port, app):
    return [sys.executable, '-m', 'esptool', '--chip', 'esp32s3', '--port', port,
            '--baud', '115200', '--before', 'default_reset', '--after', 'hard_reset',
            'write_flash', '--flash_mode', 'dio', '--flash_freq', '40m',
            '--flash_size', '8MB', '0x10000', str(app)]


def verify_artifacts():
    source_check()
    if subprocess.check_output(['git', '-C', str(ROOT), 'remote', 'get-url', 'origin'], text=True).strip() != 'https://github.com/jnbntc/infrabadge.git':
        raise StopTest('wrong_repository')
    for folder, name in [('firmware-m2', 'firmware.json'), ('rollback-m11', 'rollback-verification.json')]:
        manifest = json.loads((PHASE_A / name).read_text())
        for path, expected in manifest['artifacts'].items():
            data = (PHASE_A / folder / path).read_bytes()
            if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise StopTest('artifact_mismatch')
    app = PHASE_A / 'firmware-m2/infrabadge.bin'
    if app.stat().st_size != 853296 or hashlib.sha256(app.read_bytes()).hexdigest() != APP_SHA:
        raise StopTest('not_the_authorized_application')
    config = json.loads((PHASE_A / 'build/config/sdkconfig.json').read_text())
    if config.get('IDF_TARGET') != 'esp32s3' or config.get('ESPTOOLPY_FLASHSIZE') != '8MB':
        raise StopTest('target_or_flash_config')
    for key in ('SECURE_BOOT', 'SECURE_BOOT_V2_ENABLED', 'SECURE_FLASH_ENC_ENABLED', 'NVS_ENCRYPTION', 'BOOTLOADER_APP_ANTI_ROLLBACK', 'ESP_TLS_INSECURE', 'ESP_TLS_SKIP_SERVER_CERT_VERIFY'):
        if config.get(key):
            raise StopTest('unexpected_security_config')
    if not config.get('MBEDTLS_HAVE_TIME_DATE') or not config.get('LWIP_DNS_SUPPORT_MDNS_QUERIES'):
        raise StopTest('date_or_mdns_config')
    match = re.search(r'SHA-256:\s*`([0-9a-f]{64})`', FACTORY_RECORD.read_text())
    if not match or FACTORY.stat().st_size != 8388608:
        raise StopTest('factory_backup_unavailable')
    with FACTORY.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != match[1]:
            raise StopTest('factory_backup_mismatch')
    return app


def host_preflight(artifact_verifier=verify_artifacts):
    artifact_verifier()
    value = read_private(LAB / 'device.json')
    net = json.loads((LAB / 'network.json').read_text())
    if hashlib.sha256((LAB / 'ca.pem').read_bytes()).hexdigest() != CA_SHA or value['ca_pem'] != (LAB / 'ca.pem').read_text():
        raise StopTest('lab_ca_changed')
    gateway = json.loads((LAB / 'gateway.json').read_text())
    if hashlib.sha256(value['token'].encode()).hexdigest() not in gateway['devices'][value['device_id']]['token_sha256']:
        raise StopTest('token_mismatch')
    if value['interval_seconds'] != 900 or gateway['devices'][value['device_id']]['scenario'] != 'HEALTHY' or gateway['enable_faults']:
        raise StopTest('initial_scenario_or_interval_changed')
    if subprocess.check_output(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'], text=True).strip() != 'yes':
        raise StopTest('host_utc_not_synchronized')
    uuid = subprocess.check_output(['nmcli', '--escape', 'no', '-g', 'GENERAL.CON-UUID', 'device', 'show', net['interface']], text=True).rstrip('\n')
    ssid = subprocess.check_output(['nmcli', '--escape', 'no', '-g', '802-11-wireless.ssid', 'connection', 'show', 'uuid', uuid], text=True).rstrip('\n')
    if ssid != value['ssid']:
        raise StopTest('private_wifi_does_not_match_active_connection')
    current = json.loads(subprocess.check_output(['ip', '-j', 'address', 'show', 'dev', net['interface']], text=True))
    if not any(row.get('local') == net['address'] for dev in current for row in dev.get('addr_info', [])):
        raise StopTest('lab_lan_address_changed')
    context = ssl.create_default_context(cafile=str(LAB / 'ca.pem'))
    context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
    channel = http.client.HTTPSConnection(net['hostname'], 8443, context=context, timeout=5)
    # Host diagnostic only. The ESP32 receives the hostname, with no IP override.
    channel._create_connection = lambda target, timeout, source_address=None: socket.create_connection((net['address'], target[1]), timeout, source_address)
    try:
        channel.request('GET', '/api/v1/devices/' + value['device_id'] + '/status', headers={'Authorization': 'Bearer ' + value['token']})
        response = channel.getresponse()
        body = response.read(2049)
        if response.status != 200 or len(body) > 2048 or not json.loads(body)['simulated']:
            raise StopTest('gateway_initial_response')
    finally:
        channel.close()
    wire(value, int(time.time()))  # Validate encoding without retaining or sending a payload.
    return {'artifacts_verified': True, 'factory_backup_verified_privately': True,
            'host_utc_synchronized': True, 'host_https_tls12': True,
            'external_network_test': 'omitted_by_user', 'board_io_performed': False}


def detect_host():
    found = []
    for tty in Path('/sys/class/tty').glob('ttyACM*'):
        for parent in tty.resolve().parents:
            try:
                identity = ((parent / 'idVendor').read_text().strip(), (parent / 'idProduct').read_text().strip())
            except OSError:
                continue
            if identity == ('303a', '1001'):
                found.append(Path('/dev') / tty.name)
            break
    if len(found) != 1:
        raise StopTest('connect_exactly_one_waveshare_usb_board')
    port = Path('/dev/infrabadge') if Path('/dev/infrabadge').exists() else found[0]
    if port.resolve() != found[0].resolve() or not stat.S_ISCHR(port.stat().st_mode) or not os.access(port, os.R_OK | os.W_OK):
        raise StopTest('usb_port_not_accessible_without_sudo')
    return str(port)


def prior_write():
    for path in (ROOT / 'results').glob('m2-physical-first-*/result.json'):
        value = json.loads(path.read_text())
        if value.get('app_sha256') == APP_SHA and value.get('flash_attempted'):
            return path.parent
    return None


def query_supported(result):
    events = result.get('events', [])[result.get('provision_event_index', 0):]
    cycles = [row for row in events if row['event'] == 'cycle']
    live = any(row['event'] == 'display' and row['result'] != 'error' and row['live'] and row['clock'] for row in events)
    return bool(result.get('flash_completed') and result.get('provision_attempted') and result.get('provision_ack') and cycles
                and cycles[0]['result'] == 'OK' and live and not result.get('unexpected_reset_or_panic')
                and result.get('external_http_200_observed') and result.get('operator_screen_confirmed'))


def physical(args, *, artifact_verifier=verify_artifacts, app_sha=APP_SHA, allow_setup_wake=False):
    import serial
    from serial.tools import list_ports
    out = Path(args.results)
    result = {'status': 'preflight', 'started_utc': utc(), 'app_sha256': app_sha,
              'flash_attempted': False, 'flash_completed': False, 'provision_attempted': False,
              'provision_ack': False, 'events': [], 'unexpected_reset_or_panic': False,
              'deep_sleep_validated': False, 'etag_304_validated': False,
              'unprovisioned_offline_screen_validated': False,
              'full_m2_validation': False, 'raw_serial_text_stored': False,
              'firmware_restore_performed': False, 'efuse_or_security_changes': False}
    save(out / 'result.json', result)
    channel = None
    try:
        app = artifact_verifier()
        sdk = os.environ.get('IDF_PATH')
        if not sdk or subprocess.check_output(['git', '-C', sdk, 'rev-parse', 'HEAD'], text=True).strip() != SDK:
            raise StopTest('sdk_mismatch')
        ports = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x303a, 0x1001)]
        if len(ports) != 1 or Path(ports[0].device).resolve() != Path(args.port).resolve():
            raise StopTest('ambiguous_usb_target_inside_container')
        if not yes('¿La única placa conectada es InfraBadge Waveshare V2, con USB estable, batería correctamente conectada, botones sueltos y otros monitores cerrados?'):
            raise StopTest('operator_preparation_not_confirmed')
        snapshot = out / 'authorized-m2-app.bin'
        with snapshot.open('xb') as stream:
            stream.write(app.read_bytes())
        snapshot.chmod(0o400)
        if hashlib.sha256(snapshot.read_bytes()).hexdigest() != app_sha:
            raise StopTest('snapshot_mismatch')
        trace = PHASE_A / 'gateway-events.jsonl'
        trace_offset = trace.stat().st_size if trace.exists() else 0
        result['gateway_trace_start_bytes'] = trace_offset
        result['flash_attempted'] = True
        save(out / 'result.json', result)
        print('Cargando UNA vez sólo la aplicación M2 en0x10000. No desconectar USB.', flush=True)
        with (out / 'flash-private.log').open('xb') as log:
            completed = subprocess.run(flash_command(args.port, snapshot), stdout=log, stderr=subprocess.STDOUT, timeout=150)
        if completed.returncode:
            raise StopTest('flash_failed_no_retry')
        result['flash_completed'] = True
        result['flash_completed_utc'] = utc()
        save(out / 'result.json', result)
        # Open once, after esptool released the port. No reset requests or TX except provisioning.
        deadline = time.monotonic() + 8
        while not Path(args.port).exists() and time.monotonic() < deadline:
            time.sleep(.1)
        channel = serial.Serial(port=None, baudrate=115200, timeout=.25, write_timeout=2, exclusive=True)
        channel.port = args.port
        channel.dtr = False
        channel.rts = False
        channel.open()
        print('Esperando ventana USB; se enviará una única configuración privada con UTC actual. No tocar botones.', flush=True)
        deadline = time.monotonic() + (180 if allow_setup_wake else 110)
        cycle_at = None
        setup_clock = False
        setup_reopened = False
        while time.monotonic() < deadline:
            try:
                data = channel.readline(2048)
            except (serial.SerialException, OSError):
                result['usb_disconnected'] = True
                if allow_setup_wake and result.get('setup_wake_prompted') and not result['provision_attempted'] and not setup_reopened:
                    channel.close()
                    setup_reopened = True
                    # Passive enumeration only. Never change DTR/RTS or reset.
                    candidate = None
                    observed_absent = False
                    while time.monotonic() < deadline:
                        found = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x303a, 0x1001)]
                        if len(found) > 1:
                            raise StopTest('ambiguous_usb_target_during_setup_wake')
                        if not found:
                            observed_absent = True
                        if observed_absent and found and found[0].serial_number == ports[0].serial_number:
                            candidate = found[0]
                            break
                        time.sleep(.1)
                    if candidate is None:
                        raise StopTest('setup_wake_not_observed_no_retry')
                    channel.port = candidate.device
                    channel.open()  # One reopen for the explicit manual BOOT setup wake.
                    result['setup_usb_reopened_once'] = True
                    cycle_at = None
                    continue
                break
            if not data:
                if cycle_at is not None and time.monotonic() - cycle_at > 10 and (result['provision_attempted'] or not allow_setup_wake):
                    break
                continue
            text = ANSI.sub('', data.decode('utf-8', errors='replace')).strip()
            # No original text, Wi-Fi names, headers, identifiers or TX payload reach logs/output.
            if text == 'IBPROV_READY' and not result['provision_attempted']:
                value = read_private(LAB / 'device.json')
                result['provision_attempted'] = True
                result['provision_event_index'] = len(result['events'])
                result['provision_utc'] = utc()
                save(out / 'result.json', result)
                channel.write(wire(value, int(time.time())))
                channel.flush()
                del value
                if allow_setup_wake:
                    print('Soltá BOOT ahora; dejá ambos botones sueltos durante la consulta.', flush=True)
            elif text == 'IBPROV_OK':
                result['provision_ack'] = True
                print('IBPROV_OK: configuración aceptada. Esperando resultado de red y pantalla.', flush=True)
            elif text in ('IBPROV_ERROR', 'IBPROV_TIMEOUT'):
                raise StopTest('provision_rejected_or_window_expired_no_retry')
            events = sanitize(text)['events']
            for event in events:
                if event['event'] == 'boot' and result['provision_attempted']:
                    result['unexpected_reset_or_panic'] = True
                result['events'].append(dict(event, host_received_utc=utc()))
                if event['event'] == 'cycle':
                    cycle_at = time.monotonic()
                    setup_clock = allow_setup_wake and not result['provision_attempted'] and event['result'] == 'CLOCK'
                    print('M2_CYCLE: ' + event['result'] + '; sueño solicitado=' + str(event['sleep_s']) + ' s.', flush=True)
                elif event['event'] == 'http':
                    print('M2_HTTP: ' + json.dumps(event, separators=(',', ':')), flush=True)
                elif event['event'] == 'sleep_requested' and setup_clock and not result.get('setup_wake_prompted'):
                    result['setup_wake_prompted'] = True
                    print('CLOCK inicial es esperado: NVS se conservó, pero necesita UTC fresco.', flush=True)
                    print('Esperá que USB se desconecte y otros 2 s; después pulsá BOOT durante 3 s y soltalo. No pulsar PWR ni reset.', flush=True)
            if any(marker in text for marker in ('Guru Meditation', 'panic_abort', 'Brownout detector', 'Panel state uncertain', 'Sleep returned/refused')):
                result['unexpected_reset_or_panic'] = True
            save(out / 'result.json', result)
            if result['unexpected_reset_or_panic']:
                break
        channel.close()
        channel = None
        if trace.exists():
            with trace.open('rb') as stream:
                stream.seek(trace_offset)
                rows = [json.loads(line) for line in stream.read(65536).splitlines()]
            keys = {'sequence', 'host_epoch', 'http_status', 'conditional_request', 'peer_scope'}
            result['gateway_events'] = [row for row in rows if set(row) == keys]
        result['external_http_200_observed'] = any(row['peer_scope'] == 'external_unattributed' and row['http_status'] == 200 for row in result.get('gateway_events', []))
        cycles = [row for row in result['events'][result.get('provision_event_index', 0):] if row['event'] == 'cycle']
        if result['provision_ack'] and cycles and cycles[0]['result'] == 'OK':
            result['operator_screen_confirmed'] = yes('¿Ves HEALTHY, SIM, HORA VERIFICADA y VENCE en la pantalla e-paper?')
        else:
            result['operator_offline_screen'] = yes('¿La pantalla muestra OFFLINE y la causa de consulta no válida?')
        result['operator_no_other_device_client'] = yes('¿Durante esta prueba no ejecutaste otros clientes HTTPS con el token de la placa?')
        supported = query_supported(result) and result['operator_no_other_device_client']
        result['first_query_functionally_supported'] = supported
        result['status'] = 'first_query_passed_remaining_tests_pending' if supported else 'diagnostic_collected'
        result['finished_utc'] = utc()
        save(out / 'result.json', result)
    except (Exception, KeyboardInterrupt) as error:
        result['status'] = 'partial'
        result['stop_reason'] = str(error) if isinstance(error, StopTest) else type(error).__name__
        save(out / 'result.json', result)
    finally:
        if channel is not None:
            channel.close()
        print('Estado: ' + result['status'] + '. Resultados: ' + str(out), flush=True)
        print('Sin restauración ni otro intento automático. No publicar logs privados. No se ha validado el siguiente despertar ni304.', flush=True)
    return 0 if result['status'] == 'first_query_passed_remaining_tests_pending' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true', help='Host preflight only; never opens USB')
    parser.add_argument('--authorized-m2-first', action='store_true', help='The one application load and provisioning authorized in this chat')
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--port', help=argparse.SUPPRESS)
    parser.add_argument('--results', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Ejecutar SIN sudo')
    os.umask(0o077)
    if args.preflight:
        try:
            host_preflight()
        except Exception as error:
            raise SystemExit('Preflight detenido: ' + (str(error) if isinstance(error, StopTest) else type(error).__name__)) from None
        print('Preflight PASS: firmware/rollback/backup, Wi-Fi/UTC y gateway TLS. Sin abrir USB.')
        return
    if not args.authorized_m2_first or not sys.stdin.isatty():
        parser.error('Requiere --authorized-m2-first y terminal interactiva, SIN sudo')
    if args.inside:
        if not args.port or not args.results:
            parser.error('Faltan parámetros del host')
        raise SystemExit(physical(args))
    try:
        with (Path(tempfile.gettempdir()) / ('infrabadge-physical-' + str(os.getuid()) + '.lock')).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            previous = prior_write()
            if previous:
                raise StopTest('La carga ya se intentó; no repetir. Resultados: ' + str(previous))
            report = host_preflight()
            port = detect_host()
            out = Path(tempfile.mkdtemp(prefix='m2-physical-first-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'), dir=ROOT / 'results'))
            save(out / 'host-preflight.json', report)
            print('Resultados: ' + str(out), flush=True)
            command = ['distrobox', 'enter', '--name', 'iot-dev', '--', '/usr/local/bin/idf-env', 'python3', str(Path(__file__).resolve()), '--inside', '--authorized-m2-first', '--port', port, '--results', str(out)]
            raise SystemExit(subprocess.run(command).returncode)
    except Exception as error:
        raise SystemExit('Prueba detenida: ' + (str(error) if isinstance(error, StopTest) else type(error).__name__) + '. Sin otra carga ni reset automático.') from None


if __name__ == '__main__':
    main()
