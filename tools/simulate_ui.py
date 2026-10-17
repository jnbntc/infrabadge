#!/usr/bin/env python3
"""Compile the actual C UI and export 12 PBM/PNG references plus offline gallery."""
import argparse
import binascii
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import zlib
ROOT = Path(__file__).resolve().parents[1]
NAMES = [f'{screen}-{state}' for state in ('HEALTHY', 'WARNING', 'CRITICAL', 'OFFLINE')
         for screen in ('summary', 'alerts', 'diagnostics')]
HEADER = b'P4\n200 200\n'
def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', binascii.crc32(kind + data) & 0xffffffff)
def png(pbm):
    if not pbm.startswith(HEADER) or len(pbm) != len(HEADER) + 5000:
        raise ValueError('Invalid PBM')
    packed = pbm[len(HEADER):]
    # PNG monochrome grayscale: 1=white, same as the panel (PBM is inverted).
    scan = b''.join(b'\0' + bytes(v ^ 255 for v in packed[y*25:(y+1)*25]) for y in range(200))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 200, 200, 1, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scan, 9)) + chunk(b'IEND', b''))
def png_pixels(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('PNG signature')
    offset, compressed, header, ended = 8, b'', None, False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError('Truncated chunk')
        size = struct.unpack_from('>I', data, offset)[0]
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+size]
        if offset + 12 + size > len(data):
            raise ValueError('Truncated payload')
        crc = struct.unpack_from('>I', data, offset+8+size)[0]
        if crc != binascii.crc32(kind + payload) & 0xffffffff:
            raise ValueError('PNG CRC')
        if kind == b'IHDR':
            header = payload
        elif kind == b'IDAT':
            compressed += payload
        elif kind == b'IEND':
            ended = True
        offset += size + 12
    if not ended or header != struct.pack('>IIBBBBB', 200, 200, 1, 0, 0, 0, 0):
        raise ValueError('PNG metadata')
    scan = zlib.decompress(compressed)
    if len(scan) != 5200 or any(scan[y*26] != 0 for y in range(200)):
        raise ValueError('Unexpected PNG scanlines')
    return scan

def gallery():
    return '''<!doctype html><html lang="es"><meta charset="utf-8"><title>InfraBadge M1 — simulador</title>
<style>body{font:16px system-ui;background:#eee;color:#111;max-width:960px;margin:32px auto;padding:0 20px}button,select{font:inherit;padding:10px;margin:4px}img{image-rendering:pixelated;width:400px;height:400px;border:1px solid #333;background:white;max-width:100%;object-fit:contain}#all{display:flex;flex-wrap:wrap;gap:24px}#all img{width:200px;height:200px}figure{margin:0}p{line-height:1.6}</style>
<h1>InfraBadge M1</h1><p>Datos simulados · imágenes producidas por el renderizador C del firmware.<br>Reloj no sincronizado. Esto no es evidencia de hardware.</p>
<button id="boot">BOOT · siguiente vista</button><button id="pwr">PWR · siguiente escenario</button>
<p id="label" aria-live="polite"></p><img id="screen" alt="Pantalla simulada">
<p>En la placa: mantener PWR al menos 1,2 s y soltar solicita deep sleep. El simulador sólo muestra imágenes; no emula alimentación, rebotes, SPI ni tiempos del panel.</p><h2>Referencias 1:1</h2><div id="all"></div>
<script>const views=['summary','alerts','diagnostics'],states=['HEALTHY','WARNING','CRITICAL','OFFLINE'];let view=0,state=0;
function show(){screenImage.src=views[view]+'-'+states[state]+'.png';document.getElementById('label').textContent=views[view]+' / '+states[state];}const screenImage=document.getElementById('screen');
document.getElementById('boot').onclick=()=>{view=(view+1)%3;show()};document.getElementById('pwr').onclick=()=>{state=(state+1)%4;show()};
for(const status of states)for(const v of views){const figure=document.createElement('figure'),image=document.createElement('img'),caption=document.createElement('figcaption');image.src=v+'-'+status+'.png';image.alt=v+' '+status;caption.textContent=v+' / '+status;figure.append(image,caption);document.getElementById('all').append(figure)}show();</script></html>'''

def run(output, check=False, update=False):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='infrabadge-ui-') as work:
        work = Path(work)
        exe = work / 'simulate'
        subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + ['-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
            '-I'+str(ROOT/'components/ui/include'), '-I'+str(ROOT/'components/ui/generated'),
            str(ROOT/'components/ui/model.c'), str(ROOT/'components/ui/render.c'), str(ROOT/'tools/ui_sim.c'),
            '-o', str(exe)], check=True)
        subprocess.run([str(exe), str(work)], check=True)
        for name in NAMES:
            data = (work / (name+'.pbm')).read_bytes()
            image = png(data)
            fixture = ROOT/'tests/fixtures/ui'/(name+'.pbm')
            reference = ROOT/'docs/ui'/(name+'.png')
            if check:
                if fixture.read_bytes() != data or png_pixels(reference.read_bytes()) != png_pixels(image):
                    raise SystemExit('Visual reference differs: '+name+' (review before --update)')
            if update:
                fixture.parent.mkdir(parents=True, exist_ok=True)
                reference.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_bytes(data)
                reference.write_bytes(image)
            (output/(name+'.pbm')).write_bytes(data)
            (output/(name+'.png')).write_bytes(image)
        (output/'index.html').write_text(gallery())
        if update:
            (ROOT/'docs/ui/index.html').write_text(gallery())
        elif check and (ROOT/'docs/ui/index.html').read_text() != gallery():
            raise SystemExit('Stale UI gallery')
    print('UI: 12 C-rendered screens; '+('references verified' if check else str(output)))
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'results/m1-preview')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true')
    group.add_argument('--update', action='store_true', help='Intentionally replace reviewed visual references')
    args = parser.parse_args()
    run(args.output, args.check, args.update)
if __name__ == '__main__':
    main()
