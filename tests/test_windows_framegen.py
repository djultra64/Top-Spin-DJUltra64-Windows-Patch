"""Windows interpolation selection and rollback, without launching Top Spin."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from launcher.windows_framegen import FILES, MANIFEST, component, renderer_updates
from launcher.runtime import build_launch_plan
from launcher.process import save_configuration
from launcher.settings import Settings
from launcher.integrity import build_manifest, write_manifest, verify_integrity
from tests.launcher_fixtures import config_fixture


def install(root):
    files = {}
    for name in FILES:
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps({'layer': {'name': 'VK_LAYER_AFMF', 'library_path': './afmf32.dll'}}).encode()
                   if name.endswith('.json') else name.encode())
        path.write_bytes(payload)
        files[name] = hashlib.sha256(payload).hexdigest()
    (root/'.portable').mkdir(exist_ok=True)
    (root/MANIFEST).write_text(json.dumps({'version': 1, 'files': files}))
    (root/'TopSpin.exe').write_bytes(b'user game')
    (root/'Config.pml').write_bytes(config_fixture())
    (root/'d3d8.dll').write_bytes((root/FILES[-1]).read_bytes())
    (root/'dgVoodoo.conf').write_bytes(b'original wrapper config')
    (root/'.portable/windows-graphics.json').write_text(json.dumps({'version': 1, 'backend': 'dgvoodoo2'}))
    write_manifest(root, build_manifest(root, ['TopSpin.exe', 'd3d8.dll', '.portable/windows-graphics.json', *FILES]))


class WindowsFramegenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='Top Spin ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        install(self.root)

    def test_plan_is_read_only_and_preserves_user_layers_and_paths(self):
        before = self.snapshot()
        env = {'VK_LAYER_PATH': 'C:\\user layers', 'VK_INSTANCE_LAYERS': 'VK_LAYER_USER', 'DISABLE_AFMF': '1'}
        plan = build_launch_plan(self.root, Settings(frame_generation=True), platform='win32', environ=env)
        self.assertEqual(plan.argv, [str(self.root/'TopSpin.exe')])
        self.assertEqual(plan.env['VK_LAYER_PATH'], str(self.root/'runtime/windows-framegen')+';C:\\user layers')
        self.assertEqual(plan.env['VK_INSTANCE_LAYERS'], 'VK_LAYER_AFMF;VK_LAYER_USER')
        self.assertNotIn('DISABLE_AFMF', plan.env)
        self.assertEqual(plan.env['AFMF_GAMESCOPE'], '0')
        self.assertEqual(plan.env['AFMF_MIN_FPS'], '0')
        self.assertEqual(before, self.snapshot())

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*')
                if p.is_file() and p.name != 'game.lock'}

    def test_enable_disable_updates_renderer_and_integrity_together(self):
        from tools.pml import Pml
        with patch('launcher.process.sys.platform', 'win32'):
            save_configuration(self.root, Settings(frame_generation=True, internal_resolution='3840x2160'))
        self.assertEqual((self.root/'d3d8.dll').read_bytes(), (self.root/FILES[2]).read_bytes())
        self.assertTrue((self.root/'d3d9.dll').exists())
        self.assertTrue(verify_integrity(self.root).ok)
        video = Pml((self.root/'Config.pml').read_bytes())
        self.assertEqual(video.get('Video', 'Res_X'), '3840')
        with patch('launcher.process.sys.platform', 'win32'):
            save_configuration(self.root, Settings())
        self.assertEqual((self.root/'d3d8.dll').read_bytes(), (self.root/FILES[-1]).read_bytes())
        self.assertFalse((self.root/'d3d9.dll').exists())
        self.assertTrue(verify_integrity(self.root).ok)

    def test_settings_failure_rolls_back_every_byte_and_new_files(self):
        before = self.snapshot()
        with patch('launcher.process.sys.platform', 'win32'), patch('launcher.process.save_settings', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                save_configuration(self.root, Settings(frame_generation=True))
        self.assertEqual(self.snapshot(), before)

    def test_disable_failure_restores_deleted_dxvk_and_active_manifest(self):
        with patch('launcher.process.sys.platform', 'win32'):
            save_configuration(self.root, Settings(frame_generation=True))
        before = self.snapshot()
        with patch('launcher.process.sys.platform', 'win32'), patch('launcher.process.save_settings', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):save_configuration(self.root, Settings())
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(verify_integrity(self.root).ok)

    def test_prompts_renderer_and_integrity_roll_back_as_one_transaction(self):
        import sys
        import types
        font = self.root/'Media/font.rui'; font.parent.mkdir(); font.write_bytes(b'keyboard')
        (self.root/'.portable/input.json').write_text('{}')
        write_manifest(self.root, build_manifest(self.root, ['Media/font.rui', 'TopSpin.exe', 'd3d8.dll', '.portable/windows-graphics.json', *FILES]))
        stub = types.ModuleType('launcher.glyphs')
        stub.plan_prompt_style = lambda *args: {font: b'controller'}
        before = self.snapshot()
        with patch.dict(sys.modules, {'launcher.glyphs': stub}), patch('launcher.process.sys.platform', 'win32'), \
             patch('tools.controller_config.remap_existing_controls', side_effect=lambda raw, profile: raw), \
             patch('launcher.process.save_settings', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):save_configuration(self.root, Settings(frame_generation=True))
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(verify_integrity(self.root).ok)

    def test_failed_second_atomic_write_rolls_back_renderer(self):
        from launcher.settings import atomic_write
        before = self.snapshot(); calls = 0
        def fail_once(path, payload):
            nonlocal calls
            calls += 1
            if calls == 3: raise OSError('write failed')
            atomic_write(path, payload)
        with patch('launcher.process.sys.platform', 'win32'), patch('launcher.process.atomic_write', side_effect=fail_once):
            with self.assertRaises(OSError):save_configuration(self.root, Settings(frame_generation=True))
        self.assertEqual(self.snapshot(), before)

    def test_missing_and_corrupt_components_reject_before_mutation(self):
        for name in FILES:
            path = self.root/name; raw = path.read_bytes()
            for content in [None, b'corrupt']:
                if content is None:path.unlink()
                else:path.write_bytes(content)
                before = self.snapshot()
                with patch('launcher.process.sys.platform', 'win32'):
                    with self.assertRaises(ValueError):save_configuration(self.root, Settings(frame_generation=True))
                self.assertEqual(self.snapshot(), before)
            path.write_bytes(raw)

    def test_unknown_wrappers_never_overwritten(self):
        for name in ['d3d8.dll', 'd3d9.dll']:
            path = self.root/name; previous = path.read_bytes() if path.exists() else None
            path.write_bytes(b'user custom wrapper')
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, 'Unrecognized'):renderer_updates(self.root, True)
            self.assertEqual(before, self.snapshot())
            if previous is None:path.unlink()
            else:path.write_bytes(previous)
        (self.root/'d3d9.dll').write_bytes(b'user custom wrapper')
        self.assertNotIn(self.root/'d3d9.dll', renderer_updates(self.root, False))

    def test_manifest_rejects_traversal_extra_files_and_renderer_aliases(self):
        target = self.root/MANIFEST; original = target.read_bytes()
        data = json.loads(original)
        data['files']['../outside.dll'] = '0'*64
        target.write_text(json.dumps(data))
        with self.assertRaises(ValueError):component(self.root)
        target.write_bytes(original)
        source = self.root/FILES[-1]; destination = self.root/FILES[2]
        destination.write_bytes(source.read_bytes())
        data = json.loads(original); data['files'][FILES[2]] = hashlib.sha256(destination.read_bytes()).hexdigest()
        target.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'distinct'):component(self.root)

    def test_symlinks_and_layer_library_escape_rejected(self):
        path = self.root/FILES[0]; raw = path.read_bytes(); path.unlink()
        outside = self.root/'other.dll'; outside.write_bytes(raw); path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symbolic'):component(self.root)
        path.unlink(); path.write_bytes(raw)
        path = self.root/FILES[1]
        path.write_text(json.dumps({'layer': {'name': 'VK_LAYER_AFMF', 'library_path': '../other.dll'}}))
        target = self.root/MANIFEST; data = json.loads(target.read_text())
        data['files'][FILES[1]] = hashlib.sha256(path.read_bytes()).hexdigest(); target.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Vulkan'):component(self.root)

    def test_missing_optional_component_supports_default_but_not_interpolation(self):
        (self.root/MANIFEST).unlink()
        plan = build_launch_plan(self.root, Settings(), platform='win32', environ={'AFMF_ENABLE':'1'})
        self.assertEqual(plan.env['AFMF_ENABLE'], '0')
        with self.assertRaisesRegex(ValueError, 'not installed'):
            build_launch_plan(self.root, Settings(frame_generation=True), platform='win32', environ={})
