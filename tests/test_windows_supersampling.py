"""Windows wrapper uses separate render and requested window resolutions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from launcher.runtime import build_launch_plan
from launcher.process import save_configuration
from launcher.settings import Settings
from tools.pml import Pml
from tests.launcher_fixtures import config_fixture

class WindowsSupersamplingTests(unittest.TestCase):
    def fixture(self,root):
        (root/'.portable').mkdir()
        (root/'.portable/windows-graphics.json').write_text(json.dumps({'version':1,'backend':'dgvoodoo2'}))
        (root/'d3d8.dll').write_bytes(b'test wrapper')
        (root/'dgVoodoo.conf').write_text('previous graphics')
        (root/'Config.pml').write_bytes(config_fixture())
        (root/'TopSpin.exe').touch()
    def test_native_plan_accepts_supersampling_only_with_complete_local_wrapper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            settings=Settings(internal_resolution='3840x2160',output_resolution='1920x1080')
            plan=build_launch_plan(root,settings,platform='win32',environ={})
            self.assertEqual(plan.argv,[str(root/'TopSpin.exe')])
            (root/'d3d8.dll').unlink()
            with self.assertRaisesRegex(ValueError,'Windows graphics runtime'):
                build_launch_plan(root,settings,platform='win32',environ={})
    def test_save_requests_real_internal_backbuffer_and_preserves_pal_timing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            with patch('launcher.process.sys.platform','win32'):
                save_configuration(root,Settings(internal_resolution='3840x2160',output_resolution='1920x1080'))
            config=Pml((root/'Config.pml').read_bytes())
            self.assertEqual(config.get('Video','Res_X'),'3840')
            self.assertEqual(config.get('Video','FullScreen'),'false')
            self.assertEqual(config.get('Video','RefreshRate'),'50')
            self.assertIn('Resolution = 3840x2160',(root/'dgVoodoo.conf').read_text())
    def test_settings_failure_restores_game_and_graphics_config(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);raw=(root/'Config.pml').read_bytes()
            with patch('launcher.process.sys.platform','win32'),patch('launcher.process.save_settings',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):save_configuration(root,Settings(internal_resolution='3840x2160'))
            self.assertEqual((root/'Config.pml').read_bytes(),raw)
            self.assertEqual((root/'dgVoodoo.conf').read_text(),'previous graphics')
