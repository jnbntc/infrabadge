#!/usr/bin/env python3
"""Validate compiled artifacts/configuration; never accesses a device."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


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


def inspect(build, profile):
    config = json.loads((build / 'config/sdkconfig.json').read_text())
    assert config['IDF_TARGET'] == 'esp32s3', 'Unexpected target'
    assert config['ESPTOOLPY_FLASHSIZE'] == '8MB', 'Flash size must be 8MB'
    assert config.get('ESP_CONSOLE_USB_SERIAL_JTAG'), 'USB Serial/JTAG console required'
    assert not config.get('SPIRAM'), 'M0 does not use PSRAM'
    for key in ['SECURE_BOOT', 'SECURE_BOOT_V2_ENABLED', 'SECURE_FLASH_ENC_ENABLED', 'BT_ENABLED', 'ESP_WIFI_ENABLED']:
        assert not config.get(key), f'Forbidden feature: {key}'
    modes = [name for name in ['display', 'sensors', 'sleep'] if config.get(f'IB_M0_{name.upper()}')]
    assert modes == ([] if profile in ('ui','timer') else [profile]), f'Wrong M0 profile: {modes}'
    assert bool(config.get('IB_M1_UI')) == (profile == 'ui'), 'Wrong M1 selection'
    assert bool(config.get('IB_M11_TIMER_DIAG')) == (profile == 'timer'), 'Wrong M1.1 selection'
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
            assert (len(linked_ui) == 4 if profile == 'ui' else not linked_ui), f'Unexpected UI linkage: {linked_ui}'
            diag={'ib_td_boot','ib_td_arm_sleep','ib_td_render'} & elf_symbols(data)
            assert (len(diag)==3 if profile=='timer' else not diag), f'Unexpected timer linkage: {diag}'
            if profile=='timer':
                elf_retained_record(data)
    flash = json.loads((build / 'flasher_args.json').read_text())
    assert set(flash['flash_files']) == {'0x0', '0x8000', '0x10000'}, 'Unexpected flash offsets'
    # Exclude radio stacks from the minimal dependency closure as well as runtime use.
    forbidden = {'esp_wifi', 'bt', 'mqtt', 'openthread'} & set(description['build_components'])
    assert not forbidden, f'Unexpected linked component closure: {forbidden}'
    return {'profile': profile, 'status': 'passed', 'target': 'esp32s3', 'esp_idf': 'v5.5.5',
            'flash_size': '8MB', 'artifacts': artifacts, 'hardware_validation': 'not_performed',
            'flash_performed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--profile', choices=['display', 'sensors', 'sleep', 'ui', 'timer'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.build, args.profile)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS: {args.profile}, ESP32-S3 Xtensa, 8MB flash, USB logging, security/radios disabled; no hardware I/O')


if __name__ == '__main__':
    main()
