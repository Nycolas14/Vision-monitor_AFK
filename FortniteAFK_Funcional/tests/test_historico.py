"""Testes do histórico, usando arquivo temporário."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import historico


class HistoryTests(unittest.TestCase):
    def test_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(historico, 'HISTORY', Path(directory) / 'ausente.json'):
                self.assertEqual(historico.load_history(), [])

    def test_corrupt_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'partidas.json'
            path.write_text('{incorreto', encoding='utf-8')
            with patch.object(historico, 'HISTORY', path):
                self.assertEqual(historico.load_history(), [])

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'partidas.json'
            records = [{'fim': '2026-11-09T14:30:00'}]
            with patch.object(historico, 'HISTORY', path):
                historico.save_history(records)
                self.assertEqual(historico.load_history(), records)


if __name__ == '__main__':
    unittest.main()
