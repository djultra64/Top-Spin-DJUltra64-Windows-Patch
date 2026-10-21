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
