from tests.launcher_fixtures import config_fixture
"""Launcher regressions that never start TopSpin or edit a Steam library."""
import json
import tempfile
import unittest
from pathlib import Path
from launcher.settings import Settings, apply_graphics, save_settings, load_settings
from launcher.runtime import build_launch_plan
from tools.pml import Pml

class SettingsTests(unittest.TestCase):
    def test_invalid_game_config_has_a_user_readable_error(self):
        with self.assertRaisesRegex(ValueError,'Config.pml'):
            apply_graphics(b'short',Settings())

    def test_unknown_or_unsafe_choices_are_rejected(self):
        for data in [{'internal_resolution':'99999x99999'}, {'frame_generation':'yes'},
                     {'fullscreen':1}, {'output_resolution':'1920x1200'}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                Settings.from_dict(data)

    def test_graphics_preserve_input_security_and_original_simulation(self):
        raw=config_fixture()
        before=Pml(raw)
        after=Pml(apply_graphics(raw,Settings(internal_resolution='2560x1440')))
        self.assertEqual(before.node('Mappings'),after.node('Mappings'))
        self.assertEqual(before.node('Security'),after.node('Security'))
        self.assertEqual(dict(after.node('Video').properties)[Pml.key('Res_X')],'2560')
        self.assertEqual(dict(after.node('Video').properties)[Pml.key('RefreshRate')],'50')
        self.assertEqual(dict(after.node('DebugSettings').properties)[Pml.key('AutoSynchronize')],'true')

    def test_first_open_reads_existing_graphics_instead_of_resetting_them(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=config_fixture()
            (root/'Config.pml').write_bytes(apply_graphics(raw,Settings(internal_resolution='3840x2160')))
            self.assertEqual(load_settings(root).internal_resolution,'3840x2160')
            self.assertFalse((root/'.portable/launcher.json').exists())

    def test_local_settings_roundtrip_does_not_change_game_config(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cfg=root/'Config.pml';cfg.write_bytes(b'untouched')
            setting=Settings(internal_resolution='3840x2160',frame_generation=True)
            save_settings(root,setting)
            self.assertEqual(load_settings(root),setting)
            self.assertEqual(cfg.read_bytes(),b'untouched')

class LaunchPlanTests(unittest.TestCase):
    def test_gamescope_uses_standard_game_wsi_without_disabling_compositor_or_interpolation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'.portable').mkdir()
            for name in ['TopSpin.exe','runtime/proton/proton','runtime/gamescope','runtime/video/libgst.so']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch()
            layer=root/'runtime/afmf';layer.mkdir()
            (layer/'libafmf-linux.so').touch()
            (layer/'afmf-linux.json').write_text(json.dumps({'layer':{'name':'VK_LAYER_AFMF','library_path':'libafmf-linux.so'}}))
            (root/'.portable/runtime.json').write_text(json.dumps({'proton':'runtime/proton/proton',
                'gamescope':'runtime/gamescope','afmf_layer':'runtime/afmf',
                'video_libraries':['runtime/video/libgst.so'],'video_plugins':'runtime/video'}))
            steam=root/'Steam';steam.mkdir()
            for enabled in [False,True]:
                with self.subTest(frame_generation=enabled):
                    plan=build_launch_plan(root,Settings(frame_generation=enabled),platform='linux',
                        environ={'STEAM_ROOT':str(steam),'ENABLE_GAMESCOPE_WSI':'1','DISABLE_GAMESCOPE_WSI':'0'})
                    self.assertEqual(plan.argv[0],str(root/'runtime/gamescope'))
                    self.assertIn('DISABLE_GAMESCOPE_WSI=1',plan.argv)
                    self.assertEqual(plan.env['DISABLE_GAMESCOPE_WSI'],'1')
                    self.assertIn('AFMF_ENABLE='+str(int(enabled)),plan.argv)
                    if enabled:self.assertIn('VK_ADD_IMPLICIT_LAYER_PATH='+str(layer),plan.argv)

    def test_host_helper_loader_snapshot_excludes_portable_libraries_and_preserves_host_values(self):
        from launcher.runtime import capture_host_loader_environment
        # LD_PRELOAD splits on whitespace as well as colons; the portable
        # game itself uses basenames for that reason, while host paths survive.
        root=Path('/own-game')
        env={'LD_LIBRARY_PATH':str(root/'runtime/python/lib64')+':'+str(root/'runtime/linux/lib64')+':/host/steam libs',
             'LD_PRELOAD':str(root/'runtime/linux/lib64/private.so')+':libgst-own.so:/host/overlay.so'}
        capture_host_loader_environment(env,root,[root/'runtime/linux/lib64/libgst-own.so'])
        self.assertEqual(env['TOPSPIN_HOST_LD_LIBRARY_PATH'],'/host/steam libs')
        self.assertEqual(env['TOPSPIN_HOST_LD_PRELOAD'],'/host/overlay.so')
        self.assertEqual(env['TOPSPIN_HOST_LD_PRELOAD_SET'],'1')
        self.assertEqual(env['LD_LIBRARY_PATH'],'/host/steam libs')
        self.assertEqual(env['LD_PRELOAD'],'/host/overlay.so')

    def test_native_windows_plan_has_no_shell_and_uses_game_directory(self):
        with tempfile.TemporaryDirectory(prefix='Top Spin ') as d:
            root=Path(d);(root/'TopSpin.exe').touch()
            plan=build_launch_plan(root,Settings(),platform='win32',environ={})
            self.assertEqual(plan.argv,[str(root/'TopSpin.exe')])
            self.assertEqual(plan.cwd,root)
            self.assertNotIn('WINEPREFIX',plan.env)

    def test_linux_requires_graphics_runtime_for_frame_generation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'TopSpin.exe').touch()
            with self.assertRaisesRegex(ValueError,'runtime'):
                build_launch_plan(root,Settings(frame_generation=True),platform='linux',environ={})

    def test_portable_manifest_cannot_escape_folder(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'TopSpin.exe').touch();(root/'.portable').mkdir()
            (root/'.portable/runtime.json').write_text(json.dumps({'proton':'../../elsewhere'}))
            with self.assertRaisesRegex(ValueError,'inside'):
                build_launch_plan(root,Settings(),platform='linux',environ={})

    def test_moved_linux_bundle_uses_local_prefix_and_child_graphics_environment(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            parent=Path(d);root=parent/'original'
            (root/'.portable').mkdir(parents=True)
            for name in ['TopSpin.exe','runtime/proton/proton','runtime/gamescope','runtime/video/libgst.so']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.touch()
            for name in ['runtime/afmf','runtime/video/plugins','runtime/video/lib']:(root/name).mkdir(parents=True,exist_ok=True)
            (root/'runtime/afmf/libafmf-linux.so').touch()
            (root/'runtime/afmf/afmf-linux.json').write_text(json.dumps({'layer':{'name':'VK_LAYER_AFMF','library_path':'libafmf-linux.so'}}))
            data={'proton':'runtime/proton/proton','gamescope':'runtime/gamescope',
                  'afmf_layer':'runtime/afmf','video_libraries':['runtime/video/libgst.so'],
                  'video_plugins':'runtime/video/plugins','library_path':'runtime/video/lib'}
            (root/'.portable/runtime.json').write_text(json.dumps(data))
            moved=parent/'Moved Top Spin';shutil.move(root,moved)
            steam=parent/'Steam';steam.mkdir()
            settings=Settings(internal_resolution='3840x2160',output_resolution='1920x1080',frame_generation=True)
            plan=build_launch_plan(moved,settings,platform='linux',environ={'STEAM_ROOT':str(steam),'PYTHONHOME':str(moved/'runtime/python'),
                    'PYTHONPATH':'launcher-private','TK_LIBRARY':'private-tk','TCL_LIBRARY':'private-tcl',
                    'LD_LIBRARY_PATH':str(moved/'runtime/python/lib64')+':/host/libs'})
            self.assertEqual(plan.env['STEAM_COMPAT_DATA_PATH'],str(moved/'.portable/proton'))
            self.assertNotIn('LD_PRELOAD',plan.env)
            self.assertNotIn('PYTHONHOME',plan.env)
            self.assertNotIn('PYTHONPATH',plan.env)
            self.assertEqual(plan.env['TOPSPIN_HOST_LD_LIBRARY_PATH'],'/host/libs')
            self.assertEqual(plan.env['TOPSPIN_HOST_LD_LIBRARY_PATH_SET'],'1')
            self.assertEqual(plan.env['TOPSPIN_HOST_LD_PRELOAD_SET'],'0')
            self.assertTrue(any(arg.endswith('runtime/video/lib:/host/libs') for arg in plan.argv))
            self.assertIn('LD_PRELOAD=libgst.so',plan.argv)
            self.assertIn('AFMF_ENABLE=1',plan.argv)
            self.assertIn('GST_REGISTRY_1_0='+str(moved/'.portable/gstreamer-registry.bin'),plan.argv)
            self.assertEqual(plan.argv[-1],str(moved/'TopSpin.exe'))
            self.assertFalse(any(str(root) in arg for arg in plan.argv))

    @unittest.skipUnless(__import__('sys').platform=='linux' and Path('/usr/lib64/libz.so.1').exists(),
                         'Linux loader regression uses the system zlib')
    def test_loader_actually_preloads_library_from_folder_with_spaces(self):
        import os,shutil,subprocess
        with tempfile.TemporaryDirectory(prefix='Top Spin loader ') as d:
            root=Path(d);(root/'.portable').mkdir();(root/'runtime/video').mkdir(parents=True)
            (root/'TopSpin.exe').touch();(root/'runtime/proton').mkdir()
            (root/'runtime/proton/proton').touch()
            shutil.copy2('/usr/lib64/libz.so.1',root/'runtime/video/libz.so.1')
            (root/'.portable/runtime.json').write_text(json.dumps({
                'proton':'runtime/proton/proton','video_libraries':['runtime/video/libz.so.1'],
                'video_plugins':'runtime/video'}))
            steam=root/'Steam';steam.mkdir()
            plan=build_launch_plan(root,Settings(),platform='linux',environ={'STEAM_ROOT':str(steam)})
            env=dict(os.environ,LD_PRELOAD=plan.env['LD_PRELOAD'],
                     LD_LIBRARY_PATH=plan.env['LD_LIBRARY_PATH'],LD_DEBUG='libs')
            result=subprocess.run(['/usr/bin/true'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0)
            self.assertNotIn('ERROR:',result.stderr)
            self.assertTrue(any('calling init:' in line and str(root/'runtime/video/libz.so.1') in line
                                for line in result.stderr.splitlines()),result.stderr)


    def test_proton11_is_not_reported_ready_without_video_playback_fix(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'TopSpin.exe').touch();(root/'.portable').mkdir()
            proton=root/'proton';proton.touch();steam=root/'Steam';steam.mkdir()
            (root/'.portable/runtime.json').write_text(json.dumps({'proton':'proton'}))
            with self.assertRaisesRegex(ValueError,'Video playback runtime'):
                build_launch_plan(root,Settings(),platform='linux',environ={'STEAM_ROOT':str(steam)})

class ControllerSettingsTests(unittest.TestCase):
    def test_keyboard_style_is_explicit_and_static_mode_is_scoped_to_child(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'TopSpin.exe').touch();(root/'.portable').mkdir()
            folder=root/'runtime/input';folder.mkdir(parents=True)
            for name in ['djultra-input.dll','SDL3.dll']:(folder/name).touch()
            (root/'.portable/input.json').write_text(json.dumps({'version':1,'glyph_count':48}))
            for family in ['keyboard','switch','auto']:
                settings=Settings(controller_family=family)
                source={};plan=build_launch_plan(root,settings,platform='win32',environ=source)
                self.assertEqual(plan.env['TOPSPIN_STATIC_PROMPTS'],'0' if family=='auto' else '1')
                self.assertEqual(source,{})

    def test_controller_choices_roundtrip_and_reject_invalid_physical_positions(self):
        setting=Settings(controller_family='switch',menu_positions='10234567')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);save_settings(root,setting)
            self.assertEqual(load_settings(root),setting)
        for bad in [dict(controller_family='random'),dict(menu_positions='ABXY'),dict(menu_positions='01234568')]:
            with self.assertRaises(ValueError):Settings(**bad)

    def test_native_input_preferences_require_bundle_and_are_scoped_to_child(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'TopSpin.exe').touch();(root/'.portable').mkdir()
            settings=Settings(controller_family='ps5',menu_positions='10234567')
            with self.assertRaisesRegex(ValueError,'controller runtime'):
                build_launch_plan(root,settings,platform='win32',environ={})
            folder=root/'runtime/input';folder.mkdir(parents=True)
            for name in ['djultra-input.dll','SDL3.dll']:(folder/name).touch()
            (root/'.portable/input.json').write_text(json.dumps({'version':1,'glyph_count':48}))
            source={'UNCHANGED':'yes'};plan=build_launch_plan(root,settings,platform='win32',environ=source)
            self.assertEqual(source,{'UNCHANGED':'yes'})
            self.assertEqual(plan.env['TOPSPIN_CONTROLLER_FAMILY'],'ps5')
            self.assertEqual(plan.env['TOPSPIN_MENU_POSITIONS'],'10234567')
