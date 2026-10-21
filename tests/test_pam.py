import unittest
from pathlib import Path
from tools.pam_archive import PamArchive

@unittest.skipUnless(Path('dist/TopSpin-Portable/Media/Wads/GamePart.wad').is_file(),
                     'Private GamePart.wad integration fixture is unavailable')
class PamTests(unittest.TestCase):
    def test_figure_data_matches_original_archive(self):
        p=PamArchive(Path('dist/TopSpin-Portable/Media/Wads/GamePart.wad'))
        data=p.read('Media/GamePart/Men.FIG')
        self.assertEqual(len(data),18978)
        self.assertEqual(int.from_bytes(data[4:8],'little'),308)
        self.assertEqual(data,p.read('media/gamepart/men.fig'))

    def test_lookup_missing_asset_is_explicit(self):
        p=PamArchive(Path('dist/TopSpin-Portable/Media/Wads/GamePart.wad'))
        with self.assertRaises(KeyError):p.read('Media/GamePart/does-not-exist.fig')

if __name__=='__main__':unittest.main()
