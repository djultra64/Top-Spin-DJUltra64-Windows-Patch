import shutil
import tempfile
from pathlib import Path
import unittest
import pefile

@unittest.skipUnless(all(shutil.which(x) for x in ['gcc','ld','as']),'Native build tools required')
class NativeInputBuildTests(unittest.TestCase):
    def test_native_hook_is_own_relocatable_pe32_with_only_system_imports(self):
        from tools.native_input import build_input_hook
        with tempfile.TemporaryDirectory() as d:
            dll=build_input_hook(Path(d));pe=pefile.PE(str(dll))
            self.assertEqual(pe.FILE_HEADER.Machine,0x14c)
            self.assertTrue(pe.FILE_HEADER.Characteristics&0x2000)
            self.assertTrue(pe.DIRECTORY_ENTRY_BASERELOC)
            names={x.name for x in pe.DIRECTORY_ENTRY_EXPORT.symbols}
            self.assertTrue({b'DjultraInitialize',b'DjultraPoll',b'DjultraGetActiveFamily',b'DjultraResolveGlyphForTest'}<=names)
            self.assertIn(b'DjultraReadController',names)
            for entry in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                self.assertGreater(entry.address,0)
                self.assertLess(entry.address,pe.OPTIONAL_HEADER.SizeOfImage)
            self.assertEqual({x.dll.lower() for x in pe.DIRECTORY_ENTRY_IMPORT},{b'kernel32.dll',b'user32.dll'})

    def test_portable_path_bootstrap_is_opt_in_and_uses_local_runtime(self):
        from tools.native_input import build_path_stub
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            legacy=build_path_stub(root/'legacy',enable_input=False).read_bytes()
            native=build_path_stub(root/'native',enable_input=True).read_bytes()
            self.assertNotIn(b'djultra-input.dll',legacy)
            self.assertIn(b'\\runtime\\input\\djultra-input.dll\0',native)
            self.assertIn(b'DjultraInitialize\0',native)
            self.assertLessEqual(len(native),512)
