"""Synthetic installer safety checks; no original game content. djultra64."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import install_patch as installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'TopSpin.exe').write_bytes(b'unknown game')
        (self.root/'Config.pml').write_bytes(b'user configuration')

    def test_unknown_executable_is_rejected_without_writes(self):
        before = set(self.root.rglob('*'))
        with self.assertRaisesRegex(ValueError, 'Unsupported TopSpin.exe'):
            installer.plan_install(self.root, self.root/'missing-payload')
        self.assertEqual(before, set(self.root.rglob('*')))
        self.assertEqual((self.root/'TopSpin.exe').read_bytes(), b'unknown game')

    def test_transaction_keeps_private_originals_and_receipt(self):
        (self.root/'T').mkdir()
        (self.root/'T/save').write_bytes(b'my save')
        result = installer.apply_changes(self.root, {'TopSpin.exe': b'own test replacement',
                                                     'runtime/test.dll': b'own runtime'})
        backup = self.root/installer.BACKUP/'TopSpin.exe'
        self.assertEqual(backup.read_bytes(), b'unknown game')
        self.assertEqual((self.root/'T/save').read_bytes(), b'my save')
        self.assertEqual(result['files']['TopSpin.exe']['sha256'], hashlib.sha256(b'own test replacement').hexdigest())
        self.assertEqual(json.loads((self.root/installer.RECEIPT).read_text()), result)
        if __import__('os').name != 'nt':
            self.assertEqual(backup.stat().st_mode & 0o077, 0)

    def test_failed_transaction_restores_all_files_and_removes_new_files(self):
        original = installer.os.replace
        def fail_receipt(source, destination):
            if Path(destination) == self.root/installer.RECEIPT:
                raise OSError('simulated full disk')
            return original(source, destination)
        with patch.object(installer.os, 'replace', side_effect=fail_receipt):
            with self.assertRaisesRegex(OSError, 'full disk'):
                installer.apply_changes(self.root, {'TopSpin.exe': b'changed', 'runtime/new.dll': b'new'})
        self.assertEqual((self.root/'TopSpin.exe').read_bytes(), b'unknown game')
        self.assertFalse((self.root/'runtime/new.dll').exists())
        self.assertFalse((self.root/installer.BACKUP).exists())
        self.assertFalse((self.root/installer.RECEIPT).exists())

    def test_backup_collision_rejects_without_overwrite(self):
        backup = self.root/installer.BACKUP
        backup.mkdir(parents=True)
        (backup/'sentinel').write_bytes(b'private')
        with self.assertRaisesRegex(ValueError, 'backup'):
            installer.apply_changes(self.root, {'TopSpin.exe': b'changed'})
        self.assertEqual((backup/'sentinel').read_bytes(), b'private')
        self.assertEqual((self.root/'TopSpin.exe').read_bytes(), b'unknown game')

    def test_symlink_and_escape_destinations_rejected_before_writes(self):
        outside = self.root/'outside'
        outside.mkdir()
        (self.root/'runtime').symlink_to(outside, target_is_directory=True)
        for name in ['runtime/test.dll', '../escape', 'T/profile', 'SecurityConfig.pml', 'C:/bad', '.portable/backups/evil']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                installer.apply_changes(self.root, {name: b'changed'})
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual((self.root/'TopSpin.exe').read_bytes(), b'unknown game')

    def test_reapplication_checks_receipt_and_detects_changed_install(self):
        installer.apply_changes(self.root, {'TopSpin.exe': b'changed'})
        self.assertEqual(installer.installed_receipt(self.root)['status'], 'installed')
        (self.root/'TopSpin.exe').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'changed'):
            installer.installed_receipt(self.root)

    def test_normal_settings_edits_are_preserved_on_receipt_validation(self):
        installer.apply_changes(self.root, {'TopSpin.exe': b'changed',
                                           'Config.pml': b'initial config',
                                           '.portable/launcher.json': b'initial settings'})
        (self.root/'Config.pml').write_bytes(b'user controls and graphics')
        (self.root/'.portable/launcher.json').write_bytes(b'user settings')
        self.assertEqual(installer.installed_receipt(self.root)['status'], 'installed')
        self.assertEqual((self.root/'Config.pml').read_bytes(), b'user controls and graphics')

    def test_windows_configuration_supports_default_4k_1080_launch_plan(self):
        from launcher.settings import Settings
        from launcher.runtime import build_launch_plan
        settings = Settings(internal_resolution='3840x2160', output_resolution='1920x1080',
                            controller_family='xbox360')
        changes = installer.plan_windows_configuration(settings)
        changes.update({'runtime/input/djultra-input.dll': b'own test DLL',
                        'runtime/input/SDL3.dll': b'test redistributable fixture',
                        '.portable/input.json': installer.json_bytes({'version': 1, 'glyph_count': 48}),
                        'd3d8.dll': b'test wrapper fixture'})
        installer.apply_changes(self.root, changes)
        plan = build_launch_plan(self.root, settings, platform='win32', environ={})
        self.assertEqual(plan.argv, [str(self.root/'TopSpin.exe')])
        self.assertEqual(plan.env['TOPSPIN_CONTROLLER_FAMILY'], 'xbox360')
        self.assertEqual(plan.env['TOPSPIN_STATIC_PROMPTS'], '1')
        self.assertIn(b'Resolution = 3840x2160', (self.root/'dgVoodoo.conf').read_bytes())
        self.assertIn(b'DesktopResolution = 1920x1080', (self.root/'dgVoodoo.conf').read_bytes())

    def test_initial_manual_prompt_style_keeps_private_keyboard_baseline(self):
        from tests.test_glyph_styles import PromptStyleTests
        from launcher.glyphs import _style_archive
        path, raw, known = PromptStyleTests().fixture(self.root)
        relative = path.relative_to(self.root).as_posix()
        changes = {relative: raw}
        with patch('launcher.glyphs.BASELINE_SHA256', known):
            installer.prepare_prompt_styles(changes, 'xbox360')
        self.assertEqual(changes['.portable/glyphs/baseline/'+relative], raw)
        self.assertEqual(changes[relative], _style_archive(raw, 'xbox360', '01234567'))
        self.assertEqual(json.loads(changes['.portable/glyphs/style.json'])['family'], 'xbox360')

    def test_reapplication_accepts_launcher_selected_prompt_family(self):
        from tests.test_glyph_styles import PromptStyleTests
        from launcher.glyphs import apply_prompt_style
        path, raw, known = PromptStyleTests().fixture(self.root)
        relative = path.relative_to(self.root).as_posix()
        changes = {'TopSpin.exe': b'changed', relative: raw}
        with patch('launcher.glyphs.BASELINE_SHA256', known):
            installer.prepare_prompt_styles(changes, 'xbox360')
            installer.apply_changes(self.root, changes)
            apply_prompt_style(self.root, 'ps5')
            self.assertEqual(installer.installed_receipt(self.root)['status'], 'installed')
            path.write_bytes(b'corrupt font')
            with self.assertRaises(ValueError):
                installer.installed_receipt(self.root)

    def test_integrity_includes_unmodified_game_files_but_excludes_private_sources(self):
        (self.root/'original-library.dll').write_bytes(b'user original')
        (self.root/'.topspin-patch').mkdir()
        (self.root/'.topspin-patch/private-source').write_bytes(b'installer')
        (self.root/'T').mkdir()
        (self.root/'T/profile').write_bytes(b'save')
        result = installer.build_install_integrity(self.root, {'runtime/new.dll': b'own'})
        names = {entry['path'] for entry in result['files']}
        self.assertEqual(names, {'TopSpin.exe', 'original-library.dll', 'runtime/new.dll'})

    def upgrade_fixture(self):
        initial = {'TopSpin.exe': b'supported old patched exe',
                   'launcher/gui.py': b'old own launcher',
                   'd3d8.dll': b'known graphics wrapper',
                   'Media/test-font.rui': b'private generated resource',
                   '.portable/windows-graphics.json': installer.json_bytes({'version': 1, 'backend': 'dgvoodoo2'}),
                   '.portable/launcher.json': b'user custom settings'}
        installer.apply_changes(self.root, initial)
        (self.root/'Config.pml').write_bytes(b'user security and custom controls')
        (self.root/'T/profile').write_bytes(b'precious save')
        payload = self.root/'.topspin-patch'
        payload.mkdir()
        def item(name, raw):
            path = payload/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}
        manifest = {'version': 1, 'author': 'djultra64', 'files': {}, 'stubs': {},
                    'lua': item('lua.exe', b'own synthetic interpreter fixture')}
        for name, raw in {'launcher/gui.py': b'new own launcher',

                          'd3d8.dll': b'known graphics wrapper',
                          'runtime/input/djultra-input.dll': b'own input',
                          'runtime/input/SDL3.dll': b'synthetic SDL redistributable'}.items():
            manifest['files'][name] = item('files/'+name, raw)
        from launcher.windows_framegen import FILES
        components = {'runtime/windows-framegen/afmf32.dll': b'own frame generation',
                      'runtime/windows-framegen/VkLayer_AFMF.json': installer.json_bytes(
                          {'layer': {'name': 'VK_LAYER_AFMF', 'library_path': 'afmf32.dll'}}),
                      'runtime/windows-framegen/dxvk32/d3d8.dll': b'synthetic DXVK8',
                      'runtime/windows-framegen/dxvk32/d3d9.dll': b'synthetic DXVK9',
                      'runtime/windows-framegen/dgvoodoo/d3d8.dll': b'known graphics wrapper'}
        declaration = {'version': 1, 'files': {name: hashlib.sha256(components[name]).hexdigest() for name in FILES}}
        components['.portable/windows-framegen.json'] = installer.json_bytes(declaration)
        for name, raw in components.items():
            manifest['files'][name] = item('files/'+name, raw)
        for key in ('input', 'save_drives', 'options_delete'):
            manifest['stubs'][key] = item(key+'.bin', b'own synthetic stub')
        (payload/'manifest.json').write_text(json.dumps(manifest))
        return payload

    def test_v1_upgrade_updates_only_own_files_and_can_reapply_without_resetting_user_state(self):
        payload = self.upgrade_fixture()
        preserved = {name: (self.root/name).read_bytes() for name in
                     ['TopSpin.exe', 'Config.pml', '.portable/launcher.json',
                      'T/profile', 'Media/test-font.rui', 'd3d8.dll']}
        original_backup = (self.root/installer.BACKUP/'TopSpin.exe').read_bytes()
        with patch.object(installer, 'WINDOWS_SHA256', hashlib.sha256(preserved['TopSpin.exe']).hexdigest()), \
             patch('tools.windows_graphics.DLL_SHA256', hashlib.sha256(preserved['d3d8.dll']).hexdigest()):
            changes, metadata = installer.plan_install(self.root, payload)
            self.assertEqual(metadata['operation'], 'upgrade')
            from launcher.windows_framegen import FILES
            self.assertEqual(set(changes), set(FILES) | {'launcher/gui.py',
                                           '.portable/windows-framegen.json',
                                           'runtime/input/djultra-input.dll', 'runtime/input/SDL3.dll',
                                           '.portable/integrity.json'})
            receipt = installer.apply_changes(self.root, changes, metadata)
            self.assertEqual(installer.plan_install(self.root, payload)[0], {})
        for name, raw in preserved.items():
            self.assertEqual((self.root/name).read_bytes(), raw, name)
        self.assertEqual((self.root/installer.BACKUP/'TopSpin.exe').read_bytes(), original_backup)
        update = receipt['updates'][-1]
        self.assertTrue((self.root/update['backup']/installer.RECEIPT).is_file())
        self.assertEqual((self.root/'launcher/gui.py').read_bytes(), b'new own launcher')
        self.assertEqual(receipt['backup'], installer.BACKUP)

    def test_same_payload_accepts_known_renderer_switch_and_preserves_checkbox(self):
        from launcher.windows_framegen import component
        payload = self.upgrade_fixture()
        exe_hash = hashlib.sha256((self.root/'TopSpin.exe').read_bytes()).hexdigest()
        wrapper_hash = hashlib.sha256((self.root/'d3d8.dll').read_bytes()).hexdigest()
        with patch.object(installer, 'WINDOWS_SHA256', exe_hash), \
             patch('tools.windows_graphics.DLL_SHA256', wrapper_hash):
            changes, metadata = installer.plan_install(self.root, payload)
            installer.apply_changes(self.root, changes, metadata)
            runtime = component(self.root)
            (self.root/'d3d8.dll').write_bytes(runtime['dxvk32/d3d8.dll'])
            (self.root/'d3d9.dll').write_bytes(runtime['dxvk32/d3d9.dll'])
            graphics = {'version': 1, 'backend': 'dgvoodoo2', 'renderer': 'dxvk-afmf'}
            (self.root/'.portable/windows-graphics.json').write_bytes(installer.json_bytes(graphics))
            preferences = b'user settings with interpolation enabled'
            (self.root/'.portable/launcher.json').write_bytes(preferences)
            self.assertEqual(installer.plan_install(self.root, payload)[0], {})
            self.assertEqual((self.root/'.portable/launcher.json').read_bytes(), preferences)
            (self.root/'d3d9.dll').write_bytes(b'unknown third-party wrapper')
            with self.assertRaisesRegex(ValueError, 'renderer'):
                installer.plan_install(self.root, payload)

    def test_upgrade_preserves_enabled_renderer_when_its_component_version_changes(self):
        from launcher.windows_framegen import component
        payload = self.upgrade_fixture()
        exe_hash = hashlib.sha256((self.root/'TopSpin.exe').read_bytes()).hexdigest()
        wrapper_hash = hashlib.sha256((self.root/'d3d8.dll').read_bytes()).hexdigest()
        with patch.object(installer, 'WINDOWS_SHA256', exe_hash), \
             patch('tools.windows_graphics.DLL_SHA256', wrapper_hash):
            changes, metadata = installer.plan_install(self.root, payload)
            installer.apply_changes(self.root, changes, metadata)
            runtime = component(self.root)
            (self.root/'d3d8.dll').write_bytes(runtime['dxvk32/d3d8.dll'])
            (self.root/'d3d9.dll').write_bytes(runtime['dxvk32/d3d9.dll'])
            (self.root/'.portable/windows-graphics.json').write_bytes(installer.json_bytes(
                {'version': 1, 'backend': 'dgvoodoo2', 'renderer': 'dxvk-afmf'}))
            name = 'runtime/windows-framegen/dxvk32/d3d8.dll'
            outer = json.loads((payload/'manifest.json').read_text())
            (payload/outer['files'][name]['path']).write_bytes(b'new known DXVK8 version')
            outer['files'][name]['sha256'] = hashlib.sha256(b'new known DXVK8 version').hexdigest()
            declaration = payload/outer['files']['.portable/windows-framegen.json']['path']
            inner = json.loads(declaration.read_text())
            inner['files'][name] = outer['files'][name]['sha256']
            declaration.write_bytes(installer.json_bytes(inner))
            outer['files']['.portable/windows-framegen.json']['sha256'] = hashlib.sha256(declaration.read_bytes()).hexdigest()
            (payload/'manifest.json').write_text(json.dumps(outer))
            changes, metadata = installer.plan_install(self.root, payload)
            self.assertEqual(changes['d3d8.dll'], b'new known DXVK8 version')
            self.assertNotIn('Config.pml', changes)
            self.assertNotIn('.portable/launcher.json', changes)
            installer.apply_changes(self.root, changes, metadata)
            self.assertEqual(installer.plan_install(self.root, payload)[0], {})

    def test_upgrade_keeps_immutable_metadata_and_can_save_interpolation_on_and_off(self):
        from tools.pml import Pml, Node
        from tools.controller_config import PROFILE, BUTTONS
        from launcher.settings import Settings
        from launcher.process import save_configuration
        from launcher.integrity import verify_integrity
        from launcher.windows_framegen import component
        from tests.launcher_fixtures import config_fixture
        from tests.test_glyph_styles import PromptStyleTests
        payload = self.upgrade_fixture()
        # A real synthetic PML tree exercises the actual controller remapper.
        tree = Pml(config_fixture())
        mapping = tree.node('Mappings')
        def node(name, properties=(), children=()):
            return Node(Pml.key(name), list(children), [(Pml.key(k), str(v)) for k, v in properties])
        profile = [('Name', PROFILE), *BUTTONS.items()]
        mapping.children = [node('Menu', children=[node('PadProfile', profile)]),
                            node('InGame', children=[node('PadProfile', profile)]),
                            node('Assign', children=[node('Pad', [('Controller', 1), ('Menu', 0), ('InGame', 0)])])]
        (self.root/'Config.pml').write_bytes(tree.encode())
        for name, raw in {'.portable/input.json': installer.json_bytes({'version': 1, 'glyph_count': 48}),
                          '.portable/runtime.json': b'{}',
                          'dgVoodoo.conf': b'old known renderer config'}.items():
            (self.root/name).write_bytes(raw)
        font, raw, known = PromptStyleTests().fixture(self.root)
        glyphs = {font.relative_to(self.root).as_posix(): raw}
        with patch('launcher.glyphs.BASELINE_SHA256', known):
            installer.prepare_prompt_styles(glyphs, 'xbox360')
        for name, raw in glyphs.items():
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        exe_hash = hashlib.sha256((self.root/'TopSpin.exe').read_bytes()).hexdigest()
        wrapper_hash = hashlib.sha256((self.root/'d3d8.dll').read_bytes()).hexdigest()
        with patch.object(installer, 'WINDOWS_SHA256', exe_hash), \
             patch('tools.windows_graphics.DLL_SHA256', wrapper_hash), \
             patch('launcher.glyphs.BASELINE_SHA256', known):
            changes, metadata = installer.plan_install(self.root, payload)
            installer.apply_changes(self.root, changes, metadata)
            names = {entry['path'] for entry in json.loads((self.root/'.portable/integrity.json').read_text())['files']}
            self.assertTrue({'.portable/input.json', '.portable/runtime.json',
                             '.portable/windows-graphics.json'} <= names)
            runtime = component(self.root)
            with patch('launcher.process.sys.platform', 'win32'):
                save_configuration(self.root, Settings(frame_generation=True, controller_family='xbox360',
                                                       internal_resolution='3840x2160'))
            self.assertEqual((self.root/'d3d8.dll').read_bytes(), runtime['dxvk32/d3d8.dll'])
            self.assertTrue(verify_integrity(self.root).ok)
            with patch('launcher.process.sys.platform', 'win32'):
                save_configuration(self.root, Settings(frame_generation=False, controller_family='xbox360',
                                                       internal_resolution='3840x2160'))
            self.assertEqual((self.root/'d3d8.dll').read_bytes(), runtime['dgvoodoo/d3d8.dll'])
            self.assertFalse((self.root/'d3d9.dll').exists())
            self.assertTrue(verify_integrity(self.root).ok)
            self.assertEqual(installer.plan_install(self.root, payload)[0], {})

    def test_upgrade_failure_rolls_back_old_receipt_integrity_and_runtime_exactly(self):
        payload = self.upgrade_fixture()
        old_integrity = b'original user integrity bytes'
        (self.root/'.portable/integrity.json').write_bytes(old_integrity)
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        with patch.object(installer, 'WINDOWS_SHA256', hashlib.sha256(before['TopSpin.exe']).hexdigest()), \
             patch('tools.windows_graphics.DLL_SHA256', hashlib.sha256(before['d3d8.dll']).hexdigest()):
            changes, metadata = installer.plan_install(self.root, payload)
            original_replace = installer.os.replace
            failed = False
            def fail_once(source, destination):
                nonlocal failed
                if Path(destination) == self.root/installer.RECEIPT and not failed:
                    failed = True
                    raise OSError('simulated upgrade disk failure')
                return original_replace(source, destination)
            with patch.object(installer.os, 'replace', side_effect=fail_once):
                with self.assertRaisesRegex(OSError, 'upgrade disk failure'):
                    installer.apply_changes(self.root, changes, metadata)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after, before)

    def test_upgrade_rejects_corrupt_payload_before_writes(self):
        payload = self.upgrade_fixture()
        (payload/'files/launcher/gui.py').write_bytes(b'corrupt download')
        before = (self.root/installer.RECEIPT).read_bytes()
        with patch.object(installer, 'WINDOWS_SHA256', hashlib.sha256((self.root/'TopSpin.exe').read_bytes()).hexdigest()):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                installer.plan_install(self.root, payload)
        self.assertEqual((self.root/installer.RECEIPT).read_bytes(), before)
        self.assertEqual((self.root/'launcher/gui.py').read_bytes(), b'old own launcher')

    def test_manifest_payload_hash_and_path_validation(self):
        payload = self.root/'payload'
        payload.mkdir()
        (payload/'own.bin').write_bytes(b'own')
        descriptor = {'path': 'own.bin', 'sha256': hashlib.sha256(b'own').hexdigest()}
        self.assertEqual(installer.payload_bytes(payload, descriptor), b'own')
        for bad in [dict(descriptor, sha256='0'*64), dict(descriptor, path='../Config.pml')]:
            with self.assertRaises(ValueError):
                installer.payload_bytes(payload, bad)


if __name__ == '__main__':
    unittest.main()
