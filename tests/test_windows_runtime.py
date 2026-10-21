"""Windows frozen packaging checks, without starting the game."""
import tempfile
import unittest
from pathlib import Path
from tools.windows_runtime import pyinstaller_command, validate_bundle, stage_bundle


class WindowsRuntimeTests(unittest.TestCase):
    def test_build_contains_only_own_entry_and_is_an_isolated_onedir_bundle(self):
        command = pyinstaller_command(Path('python.exe'), Path('/source'), Path('/build'))
        self.assertIn('--onedir', command)
        self.assertIn('--windowed', command)
        self.assertEqual(command[command.index('--contents-directory') + 1], 'runtime-windows-launcher')
        self.assertEqual(command[-1], str(Path('/source')/'native/launcher/windows_entry.py'))
        self.assertNotIn('--add-data', command)
        self.assertNotIn('TopSpin.exe', ' '.join(command))

    def test_staging_preserves_game_and_rejects_incomplete_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root/'built'; bundle.mkdir()
            game = root/'game'; game.mkdir()
            (game/'TopSpin.exe').write_bytes(b'user game')
            (bundle/'TopSpinLauncher.exe').write_bytes(b'MZown launcher')
            (bundle/'Play-TopSpin.exe').write_bytes(b'MZown direct entry')
            with self.assertRaisesRegex(ValueError, 'runtime'):
                stage_bundle(bundle, game)
            self.assertFalse((game/'TopSpinLauncher.exe').exists())
            runtime = bundle/'runtime-windows-launcher'; runtime.mkdir(parents=True)
            (runtime/'python313.dll').write_bytes(b'MZpython')
            (runtime/'_tkinter.pyd').write_bytes(b'MZtk')
            (runtime/'_tcl_data').mkdir(); (runtime/'_tk_data').mkdir()
            (runtime/'_tcl_data/init.tcl').write_text('test')
            (runtime/'_tk_data/tk.tcl').write_text('test')
            validate_bundle(bundle)
            stage_bundle(bundle, game)
            self.assertEqual((game/'TopSpin.exe').read_bytes(), b'user game')
            self.assertEqual((game/'Play-TopSpin.exe').read_bytes(), b'MZown direct entry')
            self.assertTrue((game/'runtime-windows-launcher/_tkinter.pyd').is_file())
            with self.assertRaisesRegex(FileExistsError, 'already'):
                stage_bundle(bundle, game)

class FrozenChildDllTests(unittest.TestCase):
    def test_dll_search_is_restored_even_when_child_creation_fails(self):
        from launcher.process import _clean_dll_directory
        class Kernel:
            def __init__(self): self.directory = 'C:\\private runtime'; self.changes = []
            def GetDllDirectoryW(self, size, buffer):
                if buffer is not None: buffer.value = self.directory
                return len(self.directory)
            def SetDllDirectoryW(self, value):
                self.changes.append(value); self.directory = value or ''; return 1
        kernel = Kernel()
        with self.assertRaisesRegex(OSError, 'child failed'):
            with _clean_dll_directory(kernel):
                self.assertEqual(kernel.directory, '')
                raise OSError('child failed')
        self.assertEqual(kernel.changes, [None, 'C:\\private runtime'])

class TclNineTests(unittest.TestCase):
    def test_embedded_tcl_nine_libraries_do_not_require_loose_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'TopSpinLauncher.exe').write_bytes(b'MZ')
            runtime = root/'runtime-windows-launcher'; runtime.mkdir()
            for name in ['python314.dll', '_tkinter.pyd', 'tcl90.dll', 'tcl9tk90.dll']:
                (runtime/name).write_bytes(b'MZ')
            validate_bundle(root)

class FrozenIntegrityTests(unittest.TestCase):
    def test_file_mode_reports_real_corruption_and_does_not_change_settings(self):
        from native.launcher.windows_entry import verify_files
        from launcher.integrity import build_manifest, write_manifest
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); game = root/'game'; game.mkdir()
            (game/'TopSpin.exe').write_bytes(b'user-owned test executable')
            (game/'Config.pml').write_bytes(b'keep settings')
            write_manifest(game,build_manifest(game,['TopSpin.exe','Config.pml']))
            result = root/'result.json'
            self.assertEqual(verify_files(result,root=game),0)
            self.assertEqual(json.loads(result.read_text())['count'],1)
            (game/'TopSpin.exe').write_bytes(b'modified')
            self.assertEqual(verify_files(result,root=game),1)
            report=json.loads(result.read_text())
            self.assertFalse(report['ok'])
            self.assertEqual(report['modified'],['TopSpin.exe'])
            self.assertEqual((game/'Config.pml').read_bytes(),b'keep settings')
