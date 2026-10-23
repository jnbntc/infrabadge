#!/usr/bin/env python3
"""PNG references from production C parser/rendering, not the earlier Python mock."""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulate_ui import png, png_pixels

ROOT = Path(__file__).resolve().parents[2]
CASES = {
    "no-samples": ("never", 0, 1800000000, 1, -2147483648, -1, 1),
    "summary": ("healthy", 0, 1800000000, 1, -2147483648, -1, 1),
    "sites-empty-work": ("healthy", 1, 1800000000, 1, -2147483648, -1, 1),
    "node": ("healthy", 2, 1800000000, 1, -2147483648, -1, 1),
    "warning": ("warning", 0, 1800000000, 1, -2147483648, -1, 1),
    "critical": ("critical", 0, 1800000000, 1, -2147483648, -1, 1),
    "alerts": ("critical", 3, 1800000000, 1, -2147483648, -1, 1),
    "missing-metrics": ("missing", 2, 1800000000, 1, -2147483648, -1, 1),
    "stale": ("stale", 2, 1800000181, 1, -2147483648, -1, 1),
    "offline": ("offline", 0, 1800000601, 1, -2147483648, -1, 1),
    "expired-cache": ("healthy", 2, 1800000180, 0, -2147483648, -1, 1),
    "clock-untrusted": ("healthy", 0, 1800000000, 0, -2147483648, -1, 0),
    "ambient": ("healthy", 4, 1800000000, 1, 2345, 5678, 1),
    "ambient-missing": ("healthy", 4, 1800000000, 1, -2147483648, -1, 1),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    exe = Path(os.environ.get("IB_M35_NATIVE", ROOT / "results/m35-native/render"))
    folder = ROOT / "docs/m35-firmware-ui"
    folder.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        for name, (scenario, view, now, live, temp, hum, clock) in CASES.items():
            output = Path(temporary) / (name + ".pbm")
            subprocess.run(
                [
                    str(exe),
                    str(ROOT / "tests/fixtures/m35-wire" / (scenario + ".json")),
                    str(view),
                    str(now),
                    str(live),
                    str(temp),
                    str(hum),
                    str(clock),
                    str(output),
                ],
                check=True,
            )
            image = png(output.read_bytes())
            target = folder / (name + ".png")
            if args.check:
                assert png_pixels(target.read_bytes()) == png_pixels(image), name
            if args.update:
                target.write_bytes(image)
    gallery = """<!doctype html><html lang="es"><meta charset="utf-8"><title>M3.5 firmware C</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;background:#eee}main{display:flex;flex-wrap:wrap;gap:20px}figure{margin:0}img{width:200px;height:200px;image-rendering:pixelated;border:1px solid}figcaption{max-width:200px}</style><h1>M3.5 · renderer C</h1><p>Fixtures sintéticos. REAL es el indicador del protocolo de producción; estas capturas NO son datos de la notebook ni evidencia óptica.</p><main>"""
    for name in CASES:
        gallery += (
            f'<figure><img src="{name}.png" alt="{name}"><figcaption>{name}</figcaption></figure>'
        )
    gallery += "</main></html>\n"
    if args.update:
        (folder / "index.html").write_text(gallery)
    if args.check:
        assert (folder / "index.html").read_text() == gallery
    print(f"PASS: {len(CASES)} production-C synthetic 200x200 PNG references")


if __name__ == "__main__":
    main()
