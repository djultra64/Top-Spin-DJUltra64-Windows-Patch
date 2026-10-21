import unittest
from pathlib import Path
from tools.pml import Pml

CONFIG = Path('TopSpin/program files/Atari/TopSpin/Config.pml')

class PmlTests(unittest.TestCase):
    @unittest.skipUnless(all((CONFIG.parent / name).is_file() for name in
                            ['Config.pml', 'ConfigSchema.pml', 'GamePartData.pml']),
                         'Private PML integration fixtures are unavailable')
    def test_roundtrip_preserves_original_binary(self):
        for name in ['Config.pml', 'ConfigSchema.pml', 'GamePartData.pml']:
            with self.subTest(name=name):
                raw = (Path('TopSpin/program files/Atari/TopSpin') / name).read_bytes()
                self.assertEqual(Pml(raw).encode(), raw)

    @unittest.skipUnless(CONFIG.is_file(), 'Private Config.pml integration fixture is unavailable')
    def test_resolution_change_preserves_actions(self):
        raw = Path('TopSpin/program files/Atari/TopSpin/Config.pml').read_bytes()
        p = Pml(raw)
        old_actions = p.node('Mappings')
        p.set('Video', 'Res_X', '1920')
        p.set('Video', 'Res_Y', '1080')
        again = Pml(p.encode())
        self.assertEqual(again.get('Video', 'Res_X'), '1920')
        self.assertEqual(again.get('Video', 'Res_Y'), '1080')
        self.assertEqual(again.node('Mappings'), old_actions)

if __name__ == '__main__':
    unittest.main()

class PortableTimingRegression(unittest.TestCase):
    @unittest.skipUnless(CONFIG.is_file(), 'Private Config.pml integration fixture is unavailable')
    def test_safe_preset_keeps_pal_bank_and_sync_until_decoupled(self):
        from tools import prepare_portable
        self.assertTrue(hasattr(prepare_portable, 'make_config'), 'Missing PAL-preserving configuration builder')
        original=Path('TopSpin/program files/Atari/TopSpin/Config.pml').read_bytes()
        cfg=Pml(prepare_portable.make_config(original,1920,1080))
        self.assertEqual(cfg.get('Video','RefreshRate'),'50')
        self.assertEqual(cfg.get('DebugSettings','AutoSynchronize'),'true')
        self.assertEqual(cfg.get('Video','Res_X'),'1920')
        self.assertEqual(cfg.get('Video','Res_Y'),'1080')
