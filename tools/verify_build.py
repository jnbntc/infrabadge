#!/usr/bin/env python3
"""Validate compiled artifacts/configuration; never accesses a device."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def verify_m2_logging(config, image):
    # A runtime tag cannot restore ESP_LOGI calls removed by the compiler.
    assert config.get('LOG_DEFAULT_LEVEL') == 2, 'M2 SDK default logging must stay WARN'
    assert config.get('LOG_MAXIMUM_LEVEL') == 3, 'M2 INFO events must be compiled; DEBUG must stay excluded'
    assert config.get('LOG_DYNAMIC_LEVEL_CONTROL'), 'M2 needs per-tag runtime log control'
    for marker in (b'M2_BOOT:', b'M2_DISPLAY:', b'M2_CYCLE:', b'M2_HTTP:'):
        assert marker in image, f'Missing compiled M2 event: {marker.decode()}'


def elf_symbols(data):
    assert data[:6] == b'\x7fELF\x01\x01', 'Expected 32-bit little-endian ELF'
    offset = struct.unpack_from('<I', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 46)
    sections = [struct.unpack_from('<IIIIIIIIII', data, offset + i * size) for i in range(count)]
    names = set()
    for section in sections:
        if section[1] != 2:  # SHT_SYMTAB
            continue
        strings = sections[section[6]]
        table = data[strings[4]:strings[4]+strings[5]]
        assert section[9] >= 16, 'Invalid ELF symbol entry size'
        for pos in range(section[4], section[4]+section[5], section[9]):
            name, _, _, _, _, index = struct.unpack_from('<IIIBBH', data, pos)
            if index:  # defined symbols, not undefined references
                names.add(table[name:table.index(b'\0', name)].decode('ascii', errors='replace'))
    return names


def elf_retained_record(data):
    offset=struct.unpack_from('<I',data,32)[0]
    size,count,strings_index=struct.unpack_from('<HHH',data,46)
    sections=[struct.unpack_from('<IIIIIIIIII',data,offset+i*size) for i in range(count)]
    names_section=sections[strings_index]
    section_names=data[names_section[4]:names_section[4]+names_section[5]]
    for section in sections:
        if section[1]!=2:
            continue
        strings=sections[section[6]]
        names=data[strings[4]:strings[4]+strings[5]]
        for pos in range(section[4],section[4]+section[5],section[9]):
            name,_,record_size,_,_,index=struct.unpack_from('<IIIBBH',data,pos)
            symbol=names[name:names.index(b'\0',name)].decode('ascii',errors='replace')
            if symbol=='timer_diag_retained' and 0<index<len(sections):
                retained=sections[index]
                label=section_names[retained[0]:section_names.index(b'\0',retained[0])].decode()
                assert 'rtc_noinit' in label and retained[1]==8 and record_size==28, 'RTC record placement/size mismatch'
                return label
    raise AssertionError('RTC noinit record not found')


def elf_multisite_record(data):
    offset = struct.unpack_from('<I', data, 32)[0]
    size, count, names_index = struct.unpack_from('<HHH', data, 46)
    sections = [struct.unpack_from('<IIIIIIIIII', data, offset+i*size) for i in range(count)]
    table = sections[names_index]
    section_names = data[table[4]:table[4]+table[5]]
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        names = data[strings[4]:strings[4]+strings[5]]
        for pos in range(section[4], section[4]+section[5], section[9]):
            name, _, record_size, _, _, index = struct.unpack_from('<IIIBBH', data, pos)
            if names[name:names.index(b'\0',name)] == b'retained' and 0<index<len(sections):
                retained = sections[index]
                label = section_names[retained[0]:section_names.index(b'\0',retained[0])].decode()
                assert 'rtc_noinit' in label and retained[1] == 8 and 5000<record_size<=7680, 'M3.5 RTC placement/size'
                return record_size
    raise AssertionError('M3.5 retained RTC record not found')


def inspect(build, profile):
    config = json.loads((build / 'config/sdkconfig.json').read_text())
    network_profile = profile in ('connectivity','automation','multisite','roaming')
    assert config['IDF_TARGET'] == 'esp32s3', 'Unexpected target'
    assert config['ESPTOOLPY_FLASHSIZE'] == '8MB', 'Flash size must be 8MB'
    assert config.get('ESP_CONSOLE_USB_SERIAL_JTAG'), 'USB Serial/JTAG console required'
    assert not config.get('SPIRAM'), 'M0 does not use PSRAM'
    for key in ['SECURE_BOOT', 'SECURE_BOOT_V2_ENABLED', 'SECURE_FLASH_ENC_ENABLED', 'BT_ENABLED', 'ESP_TLS_INSECURE', 'ESP_TLS_SKIP_SERVER_CERT_VERIFY', 'NVS_ENCRYPTION', 'BOOTLOADER_APP_ANTI_ROLLBACK']:
        assert not config.get(key), f'Forbidden feature: {key}'
    assert bool(config.get('ESP_WIFI_ENABLED')) == network_profile, 'Wi-Fi allowed only in network profiles'
    if network_profile:
        assert config.get('MBEDTLS_HAVE_TIME_DATE'), 'TLS certificate date validation required'
    modes = [name for name in ['display', 'sensors', 'sleep'] if config.get(f'IB_M0_{name.upper()}')]
    assert modes == ([] if profile in ('ui','timer','connectivity','automation','multisite','roaming') else [profile]), f'Wrong M0 profile: {modes}'
    assert bool(config.get('IB_M1_UI')) == (profile == 'ui'), 'Wrong M1 selection'
    assert bool(config.get('IB_M11_TIMER_DIAG')) == (profile == 'timer'), 'Wrong M1.1 selection'
    assert bool(config.get('IB_M2_CONNECTIVITY')) == network_profile, 'Wrong M2 selection'
    assert bool(config.get('IB_M2_AUTO_DIAG')) == (profile == 'automation'), 'Wrong autonomous diagnostic selection'
    assert bool(config.get('IB_M35_UI')) == (profile in ('multisite','roaming')), 'Wrong M3.5 selection'
    assert bool(config.get('IB_M36_ROAMING')) == (profile == 'roaming'), 'M3.6 profile isolation'
    description = json.loads((build / 'project_description.json').read_text())
    assert description['git_revision'] in ['v5.5.5', '5.5.5'], 'Unexpected IDF version'
    artifacts = {}
    for name in ['infrabadge.elf', 'infrabadge.bin', 'bootloader/bootloader.bin', 'partition_table/partition-table.bin']:
        data = (build / name).read_bytes()
        assert data, f'Empty artifact: {name}'
        artifacts[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        if name.endswith('.elf'):
            assert data[:4] == b'\x7fELF' and struct.unpack_from('<H', data, 18)[0] == 94, 'Expected Xtensa ELF'
            linked_ui = {'ib_ui_render', 'ib_ui_mock', 'ib_display_present', 'ib_power_sleep'} & elf_symbols(data)
            expected_ui = {'ib_ui_render','ib_ui_mock','ib_display_present','ib_power_sleep'} if profile=='ui' else (
                {'ib_display_present','ib_power_sleep'} if profile in ('multisite','roaming') else
                {'ib_ui_render','ib_display_present'} if profile=='automation' else
                {'ib_ui_render','ib_display_present','ib_power_sleep'} if network_profile else set())
            assert linked_ui == expected_ui, f'Unexpected UI linkage: {linked_ui}'
            diag={'ib_td_boot','ib_td_arm_sleep','ib_td_render'} & elf_symbols(data)
            assert (len(diag)==3 if profile=='timer' else not diag), f'Unexpected timer linkage: {diag}'
            if profile=='timer':
                elf_retained_record(data)
            network={'ib_cycle_run','ib_snapshot_decode','ib_wifi_start','ib_https_fetch'} & elf_symbols(data)
            assert (network == {'ib_wifi_start'} if profile in ('multisite','roaming') else len(network)==4 if network_profile else not network), f'Unexpected network linkage: {network}'
            m35={'ib35_decode','ib35_render','ib35_resume','ib_https_fetch_presentation'} & elf_symbols(data)
            assert (len(m35)==4 if profile in ('multisite','roaming') else not m35), 'M3.5 linkage isolation'
            if profile in ('multisite','roaming'):
                assert elf_multisite_record(data)==6184, 'Unexpected RTC layout change requires review'
            roaming={'ib36_query','ib36_plan','ib36_usb','ib36_load'} & elf_symbols(data)
            assert (len(roaming)==4 if profile=='roaming' else not roaming), 'M3.6 linkage isolation'
            auto={'ib_ma_resume','ib_ma_append','ib_ma_export'} & elf_symbols(data)
            assert (len(auto)==3 if profile=='automation' else not auto), 'Autonomous journal isolation failed'
        elif name == 'infrabadge.bin' and profile == 'automation':
            assert b'IBAUTO_REPORT ' in data and b'IBAUTO_READY' in data, 'Missing diagnostic USB report'
        elif name == 'infrabadge.bin' and profile == 'connectivity':
            verify_m2_logging(config, data)
        elif name == 'infrabadge.bin' and profile in ('multisite','roaming'):
            assert config.get('LOG_DEFAULT_LEVEL')==2 and config.get('LOG_MAXIMUM_LEVEL')==3
            for marker in (b'M35_BOOT:',b'M35_QUERY:',b'M35_DISPLAY:',b'M36_SLEEP:' if profile=='roaming' else b'M35_SLEEP:'):
                assert marker in data, 'M3.5 sanitized logging was compiled out'
    flash = json.loads((build / 'flasher_args.json').read_text())
    assert set(flash['flash_files']) == {'0x0', '0x8000', '0x10000'}, 'Unexpected flash offsets'
    # Exclude radio stacks from the minimal dependency closure as well as runtime use.
    forbidden = ({'bt','mqtt','openthread'} | (set() if network_profile else {'esp_wifi'})) & set(description['build_components'])
    assert not forbidden, f'Unexpected linked component closure: {forbidden}'
    return {'profile': profile, 'status': 'passed', 'target': 'esp32s3', 'esp_idf': 'v5.5.5',
            'flash_size': '8MB', 'artifacts': artifacts, 'hardware_validation': 'not_performed',
            'flash_performed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--profile', choices=['display', 'sensors', 'sleep', 'ui', 'timer', 'connectivity', 'automation', 'multisite', 'roaming'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.build, args.profile)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS: {args.profile}, ESP32-S3 Xtensa, 8MB flash, USB logging, irreversible security disabled, Wi-Fi only in network profiles; no hardware I/O')


if __name__ == '__main__':
    main()
