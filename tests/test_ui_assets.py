import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('simulate_ui',ROOT/'tools/simulate_ui.py')
simulator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulator)
class UiAssets(unittest.TestCase):
    def test_twelve_reference_pairs(self):
        self.assertEqual(len(list((ROOT/'docs/ui').glob('*.png'))),12)
        self.assertEqual(len(list((ROOT/'tests/fixtures/ui').glob('*.pbm'))),12)
        scans=[]
        for name in simulator.NAMES:
            pbm=(ROOT/'tests/fixtures/ui'/(name+'.pbm')).read_bytes()
            png=(ROOT/'docs/ui'/(name+'.png')).read_bytes()
            scan=simulator.png_pixels(png)
            self.assertEqual(scan,simulator.png_pixels(simulator.png(pbm)))
            scans.append(scan)
        self.assertEqual(len(set(scans)),12)
    def test_corrupt_png_rejected(self):
        data=bytearray(simulator.png(simulator.HEADER+b'\x00'*5000))
        data[50]^=1
        with self.assertRaises(ValueError): simulator.png_pixels(bytes(data))
    def test_truncation_rejected(self):
        data=simulator.png(simulator.HEADER+b'\x00'*5000)
        for size in (0,8,20,len(data)-1):
            with self.assertRaises(ValueError): simulator.png_pixels(data[:size])
    def test_original_font_covers_ui(self):
        import json
        font=json.loads((ROOT/'assets/ui-font5x7.json').read_text())
        self.assertTrue(set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .:/%?!-') <= set(font))
if __name__=='__main__': unittest.main()
