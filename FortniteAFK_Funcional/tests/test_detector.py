"""Testes de reconhecimento com imagens sintéticas, sem abrir o jogo."""
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from detector import best_match, detect, detect_all, load_templates, screenshot_gray


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(15)
        self.screen = self.rng.integers(0, 256, size=(160, 220), dtype=np.uint8)
        self.template = self.screen[60:100, 100:170].copy()

    def test_detects_exact_template_at_correct_center(self):
        result = detect(self.screen, self.template, 0.95)
        self.assertIsNotNone(result)
        self.assertEqual(result[:2], (135, 80))
        self.assertGreater(result[2], 0.99)

    def test_rejects_large_template(self):
        self.assertIsNone(detect(self.screen, np.zeros((250, 250), np.uint8), 0.8))

    def test_rejects_small_template(self):
        self.assertIsNone(detect(self.screen, np.zeros((6, 6), np.uint8), 0.8))

    def test_rejects_flat_reference(self):
        self.assertIsNone(best_match(self.screen, np.full((30, 50), 255, np.uint8)))

    def test_confidence_threshold(self):
        self.assertIsNone(detect(self.screen, self.template, 1.01))

    def test_detect_all(self):
        results = detect_all(self.screen, {'partida': self.template}, 0.9)
        self.assertEqual(results['partida'][:2], (135, 80))

    def test_screenshot_conversion(self):
        pil = Image.fromarray(np.zeros((30, 40, 3), dtype=np.uint8), 'RGB')
        self.assertEqual(screenshot_gray(pil).shape, (30, 40))

    def test_load_template_with_unicode_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pasta çã'
            path.mkdir()
            ok, encoded = cv2.imencode('.png', self.template)
            self.assertTrue(ok)
            (path / 'jogar.png').write_bytes(encoded.tobytes())
            loaded = load_templates(path)
            self.assertIn('jogar', loaded)
            self.assertTrue(np.array_equal(loaded['jogar'], self.template))


if __name__ == '__main__':
    unittest.main()
