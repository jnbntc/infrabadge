#!/usr/bin/env python3
"""Eight host-only design pages; original M1 glyphs/PNG codec, no dependencies."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import simulate_ui as codec  # noqa: E402
from model import VIEWS, page  # noqa: E402

FONT = json.loads((ROOT / "assets/ui-font5x7.json").read_text())


def render(data, view):
    frame = bytearray(b"\xff" * 5000)

    def rectangle(x, y, width, height, white=False):
        if not (0 <= x <= x + width <= 200 and 0 <= y <= y + height <= 200):
            raise ValueError("rectangle outside panel")
        for py in range(y, y + height):
            for px in range(x, x + width):
                offset, mask = py * 25 + px // 8, 0x80 >> (px % 8)
                frame[offset] = frame[offset] | mask if white else frame[offset] & (255 ^ mask)

    def text(x, y, value, scale=1, white=False):
        if (
            any(c not in FONT for c in value)
            or x + (len(value) * 6 - 1) * scale > 200
            or y + 7 * scale > 200
        ):
            raise ValueError("unsupported or clipped text: " + value)
        for char in value:
            for row, bits in enumerate(FONT[char]):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        rectangle(x + col * scale, y + row * scale, scale, scale, white)
            x += 6 * scale

    title, state, lines = page(data, view)
    rectangle(0, 0, 200, 23)
    text(8, 4, "INFRABADGE", 2, True)
    text(166, 9, "M3.5", white=True)
    text(8, 31, title)
    text(174, 31, "SIM")
    text(8, 48, state, 2)
    rectangle(8, 67, 184, 1)
    for index, line in enumerate(lines):
        text(8, 78 + 12 * index, line)
    rectangle(0, 169, 200, 13)
    text(8, 172, "HORA SIMULADA" if data["clock_trusted"] else "RELOJ NO SINCRONIZADO", white=True)
    text(8, 189, "BOOT SIG / LARGO INICIO")
    return bytes(frame)


def pbm(frame):
    return codec.HEADER + bytes(b ^ 255 for b in frame)


def gallery(names):
    pictures = "".join(
        f'<figure><img src="{n}.png" width="200" height="200" alt="{n}"><figcaption>{n}</figcaption></figure>'
        for n in names
    )
    return (
        """<!doctype html><html lang="es"><meta charset="utf-8"><title>InfraBadge M3.5 | propuesta</title>
<style>body{font:16px system-ui;background:#eee;color:#111;max-width:980px;margin:32px auto;padding:16px}img{image-rendering:pixelated;background:white;border:1px solid #555}#pages{display:flex;flex-wrap:wrap;gap:20px}figure{margin:0}button{padding:12px;font:inherit}#focus{width:400px;height:400px;max-width:100%;object-fit:contain}</style>
<h1>InfraBadge M3.5</h1><p>PROPUESTA SIMULADA. Prototipo Python con la fuente M1; no es el renderer C ni firmware instalado. Ninguna captura prueba hardware.</p>
<button id="next">BOOT corto: siguiente</button><button id="home">BOOT largo: resumen</button><p>PWR conserva su función eléctrica; no se simula ni se utiliza como navegación.</p><p id="label"></p><img id="focus" alt="Vista simulada">
<div id="pages">"""
        + pictures
        + """</div><script>
const names=['global','home','work','mobile','node','alerts','stale','ambient'];let view=0;
function show(){document.getElementById('focus').src=names[view]+'.png';document.getElementById('label').textContent=names[view]+' / SIM';}
document.getElementById('next').onclick=()=>{view=(view+1)%8;show()};document.getElementById('home').onclick=()=>{view=0;show()};show();</script></html>"""
    )


def run(check):
    fixtures = ROOT / "tests/m35/fixtures"
    output = ROOT / "docs/m35-ui"
    expected = {}
    names = sorted(p.stem for p in fixtures.glob("*.json"))
    for name in names:
        data = json.loads((fixtures / (name + ".json")).read_text())
        view = (
            name
            if name in VIEWS
            else {
                "critical": "global",
                "healthy": "global",
                "gateway-offline": "global",
                "clock-unknown": "global",
                "ambient-missing": "ambient",
            }[name]
        )
        frame = render(data, view)
        expected[name + ".png"] = codec.png(pbm(frame))
    expected["index.html"] = gallery(names).encode()
    manifest = {
        n: hashlib.sha256(codec.png_pixels(v)).hexdigest()
        for n, v in expected.items()
        if n.endswith(".png")
    }
    expected["pixels.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    if check:
        for name, content in expected.items():
            actual = (output / name).read_bytes()
            if (
                (codec.png_pixels(actual) != codec.png_pixels(content))
                if name.endswith(".png")
                else actual != content
            ):
                raise ValueError("stale reference " + name)
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name, content in expected.items():
            (output / name).write_bytes(content)
    return len(names)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--update", action="store_true")
    args = parser.parse_args()
    print(f"M3.5: {run(args.check)} SYNTHETIC Python previews, no device/network access")
