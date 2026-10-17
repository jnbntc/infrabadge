import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('screen', ROOT / 'tools/generate_screen.py')
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)

class AssetTests(unittest.TestCase):
    def test_required_title_exact_case_and_frame_size(self):
        glyphs, lines = screen.load_assets()
        self.assertIn('InfraBadge M0', [line['text'] for line in lines])
        self.assertEqual(len(screen.render(glyphs, lines)), 5000)

    def test_generated_files_match_inputs(self):
        for name, expected in screen.outputs().items():
            actual = (ROOT / name).read_bytes()
            if name.endswith('.png'):
                self.assertEqual(screen.png_pixels(actual), screen.png_pixels(expected), name)
            else:
                self.assertEqual(actual, expected, name)

    def test_png_compression_changes_preserve_pixels(self):
        glyphs, lines = screen.load_assets()
        frame = screen.render(glyphs, lines)
        self.assertEqual(screen.png_pixels(screen.png(frame, level=0)), frame)
        self.assertEqual(screen.png_pixels(screen.png(frame, level=9)), frame)

    def test_private_artifacts_are_ignored(self):
        import subprocess
        for name in ['waveshare-v2-factory-8mb.bin', 'results/private.log', 'build-m0/display/infrabadge.elf', '.env']:
            result = subprocess.run(['git', 'check-ignore', '--no-index', '-q', name], cwd=ROOT)
            self.assertEqual(result.returncode, 0, name)

if __name__ == '__main__':
    unittest.main()
