from tests.launcher_fixtures import config_fixture
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from launcher.process import GameLock, save_configuration, run_game
from launcher.settings import Settings

class ProcessTests(unittest.TestCase):
    def test_spawn_failure_keeps_graphics_and_saved_preferences_consistent(self):
        from launcher.runtime import LaunchPlan
        from launcher.settings import load_settings
        from tools.pml import Pml
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'Config.pml').write_bytes(config_fixture())
            selected=Settings(internal_resolution='3840x2160')
            with patch('launcher.process.build_launch_plan',return_value=LaunchPlan(['missing'],root,{})), \
                 patch('launcher.process.subprocess.Popen',side_effect=OSError('not found')):
                with self.assertRaises(OSError):run_game(root,selected)
            self.assertEqual(load_settings(root),selected)
            self.assertEqual(Pml((root/'Config.pml').read_bytes()).get('Video','Res_X'),'3840')

    def test_generated_prompts_and_integrity_roll_back_with_settings_failure(self):
        import json,sys,types
        from launcher.integrity import build_manifest,write_manifest,verify_integrity
        from tools.controller_config import remap_existing_controls
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'.portable').mkdir();(root/'Media').mkdir()
            (root/'.portable/input.json').write_text('{}')
            font=root/'Media/font.rui';font.write_bytes(b'keyboard')
            (root/'Config.pml').write_bytes(config_fixture())
            write_manifest(root,build_manifest(root,['Media/font.rui']))
            original=(root/'.portable/integrity.json').read_bytes()
            stub=types.ModuleType('launcher.glyphs')
            from unittest.mock import Mock
            stub.plan_prompt_style=Mock(return_value={font:b'controller',root/'.portable/glyphs/state.json':b'new state'})
            with patch.dict(sys.modules,{'launcher.glyphs':stub}), \
                 patch('tools.controller_config.remap_existing_controls',side_effect=lambda raw,profile:raw), \
                 patch('launcher.process.save_settings',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):save_configuration(root,Settings(controller_family='switch'))
            stub.plan_prompt_style.assert_called_once_with(root,'switch','01234567')
            self.assertEqual(font.read_bytes(),b'keyboard')
            self.assertEqual((root/'.portable/integrity.json').read_bytes(),original)
            self.assertFalse((root/'.portable/glyphs/state.json').exists())
            self.assertTrue(verify_integrity(root).ok)

    def test_lock_rejects_second_launcher_and_can_be_reacquired(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with GameLock(root):
                with self.assertRaisesRegex(ValueError,'already running'):
                    with GameLock(root):pass
            with GameLock(root):pass

    def test_configuration_failure_restores_original_config(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=config_fixture()
            (root/'Config.pml').write_bytes(raw)
            with patch('launcher.process.save_settings',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):save_configuration(root,Settings())
            self.assertEqual((root/'Config.pml').read_bytes(),raw)

    def test_missing_runtime_does_not_change_config_or_start_process(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'TopSpin.exe').touch();(root/'Config.pml').write_bytes(b'unchanged')
            with patch('launcher.process.subprocess.Popen') as start:
                with self.assertRaises(ValueError):run_game(root,Settings(frame_generation=True))
                start.assert_not_called()
            self.assertEqual((root/'Config.pml').read_bytes(),b'unchanged')

    def test_fresh_portable_prefix_directory_exists_before_proton_starts(self):
        from launcher.runtime import LaunchPlan
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'Config.pml').write_bytes(config_fixture())
            prefix=root/'.portable/proton'
            plan=LaunchPlan(['fake-proton'],root,{'STEAM_COMPAT_DATA_PATH':str(prefix)})
            def start(*args,**kwargs):
                self.assertTrue(prefix.is_dir())
                process=__import__('unittest.mock',fromlist=['Mock']).Mock()
                process.wait.return_value=0
                return process
            with patch('launcher.process.build_launch_plan',return_value=plan), \
                 patch('launcher.process.subprocess.Popen',side_effect=start):
                self.assertEqual(run_game(root,Settings()),0)

    def test_preload_remains_absolute_when_proton_reorders_library_search_path(self):
        import os,shutil,subprocess,sys
        if sys.platform!='linux' or not Path('/usr/lib64/libz.so.1').exists():self.skipTest('Linux loader test')
        from launcher.runtime import LaunchPlan
        from launcher.process import prepared_launch
        with tempfile.TemporaryDirectory(prefix='Top Spin ') as d:
            root=Path(d);lib=root/'runtime/libz.so.1';lib.parent.mkdir()
            shutil.copy2('/usr/lib64/libz.so.1',lib)
            plan=LaunchPlan(['/usr/bin/true'],root,{'LD_PRELOAD':'libz.so.1'},preload_libraries=[lib])
            with prepared_launch(plan) as actual:
                preload=actual.env['LD_PRELOAD']
                self.assertNotIn(' ',preload)
                self.assertTrue(Path(preload).is_absolute())
                self.assertEqual(Path(preload).read_bytes(),lib.read_bytes())
                env=dict(os.environ,LD_PRELOAD=preload,LD_LIBRARY_PATH='/nowhere',LD_DEBUG='libs')
                result=subprocess.run(actual.argv,env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0)
                self.assertNotIn('ERROR:',result.stderr)
                self.assertTrue(any('calling init:' in line and preload in line for line in result.stderr.splitlines()))
            self.assertFalse(Path(preload).exists())
