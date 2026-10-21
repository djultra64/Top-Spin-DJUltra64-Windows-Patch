import unittest
from pathlib import Path
from tools.msi_reader import read_tables, file_layout, safe_name

class ExtractionTests(unittest.TestCase):
    @unittest.skipUnless(Path('TopSpin/TopSpin.msi').is_file(), 'Private MSI integration fixture is unavailable')
    def test_actual_media_has_complete_game_layout(self):
        tables = read_tables(Path('TopSpin/TopSpin.msi'))
        self.assertEqual(len(tables['File']), 1664)
        layout = file_layout(tables)
        self.assertEqual(len(layout), 1664)
        self.assertIn('TopSpin.exe', [str(f['target']) for f in layout])
        self.assertTrue(any(str(f['target']).startswith('Media/Wads/') for f in layout))
        self.assertTrue(all(f['size'] > 0 for f in layout))

    def test_names_cannot_escape_destination(self):
        for name in ['../outside', 'a/b', 'a\\b', 'C:evil', '..', '/tmp/x', '']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_name(name)
        self.assertEqual(safe_name('TOPSPI~1.WAD|TopSpin.wad'), 'TopSpin.wad')

if __name__ == '__main__':
    unittest.main()
