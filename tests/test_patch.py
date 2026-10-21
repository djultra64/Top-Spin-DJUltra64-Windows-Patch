import unittest
import hashlib
import os
from pathlib import Path
from tools.patch_game import SOURCE_SHA256, patch_executable
import pefile

def private_patch_fixture(test):
    """Require a locally supplied, exact-version executable; never ship it."""
    override = os.environ.get('TOPSPIN_TEST_EXE')
    source = Path(override) if override else Path('TopSpin/program files/Atari/TopSpin/TopSpin.exe')
    stub_path = Path('build/portable-path.bin')
    if override is None and not source.is_file():
        test.skipTest('Private executable integration fixture is unavailable')
    if not stub_path.is_file():
        test.skipTest('Build the own portable-path assembly stub for integration tests')
    raw = source.read_bytes()
    test.assertEqual(hashlib.sha256(raw).hexdigest(), SOURCE_SHA256,
                     'Executable fixture does not match the supported source SHA256')
    return raw, stub_path.read_bytes()


class PatchTests(unittest.TestCase):
    def test_patch_rejects_unknown_input(self):
        with self.assertRaises(ValueError):
            patch_executable(b'unknown', b'stub')

    def test_portable_lookup_preserves_original_code_except_hook(self):
        raw, stub = private_patch_fixture(self)
        result=patch_executable(raw, stub, aspect=4/3)
        p=pefile.PE(data=result)
        self.assertEqual(p.sections[-1].Name.rstrip(b'\0'), b'.djport')
        self.assertEqual(p.sections[-1].get_data()[:len(stub)], stub)
        self.assertEqual(result[0x1000:0x17de33], raw[0x1000:0x17de33])
        self.assertEqual(result[0x17de38:0x2e0000], raw[0x17de38:0x2e0000])
        self.assertNotEqual(result[0x17de33:0x17de38], raw[0x17de33:0x17de38])

if __name__=='__main__': unittest.main()

class OptionsSavePatchTests(unittest.TestCase):
    def test_options_query_uses_real_current_directory_without_bypassing_check(self):
        import struct
        from tools.patch_game import patch_executable
        raw, stub = private_patch_fixture(self)
        old=patch_executable(raw,stub)
        result=patch_executable(raw,stub,fix_options_save=True)
        pe=pefile.PE(data=result)
        call=pe.get_offset_from_rva(0x5b7acd-0x400000)
        self.assertEqual(result[call],0xe8)
        target=0x5b7acd+5+struct.unpack_from('<i',result,call+1)[0]
        offset=pe.get_offset_from_rva(target-0x400000)
        # Same Win32 API and actual free-space result; only its directory changes.
        self.assertEqual(result[offset:offset+4],bytes.fromhex('c7 44 24 04'))
        pointer=struct.unpack_from('<I',result,offset+4)[0]
        directory=pe.get_offset_from_rva(pointer-0x400000)
        self.assertEqual(result[directory:directory+2],b'.\0')
        self.assertEqual(result[offset+8:offset+14],bytes.fromhex('ff 25 90 c1 6e 00'))
        self.assertEqual(result[call+6:call+64],old[call+6:call+64])
        # No extra changes to original executable code, including license checks.
        text=pe.sections[0]
        begin=text.PointerToRawData;end=begin+text.SizeOfRawData
        self.assertEqual(result[begin:call],old[begin:call])
        self.assertEqual(result[call+6:end],old[call+6:end])

class CareerStoragePatchTests(unittest.TestCase):
    def test_career_queries_real_directory_and_preserves_initialization_checks(self):
        import struct
        raw, stub = private_patch_fixture(self)
        before = patch_executable(raw, stub, fix_options_save=True)
        after = patch_executable(raw, stub, fix_options_save=True,
                                 fix_career_storage=True)
        pe = pefile.PE(data=after)
        site = pe.get_offset_from_rva(0x5a4b7e - 0x400000)
        self.assertEqual(after[site], 0xe8)
        wrapper = 0x5a4b7e + 5 + struct.unpack_from('<i', after, site + 1)[0]
        pos = pe.get_offset_from_rva(wrapper - 0x400000)
        self.assertEqual(after[pos:pos + 4], bytes.fromhex('c7 44 24 04'))
        pointer = struct.unpack_from('<I', after, pos + 4)[0]
        directory = pe.get_offset_from_rva(pointer - 0x400000)
        self.assertEqual(after[directory:directory + 2], b'.\0')
        self.assertEqual(after[pos + 8:pos + 14], bytes.fromhex('ff 25 90 c1 6e 00'))
        # Limit differences in existing code to this API call. Capacity checks,
        # failure handling, matrix construction, rendering and key checks remain.
        section = pe.sections[0]
        start = section.PointerToRawData
        end = start + section.SizeOfRawData
        self.assertEqual(before[start:site], after[start:site])
        self.assertEqual(before[site + 6:end], after[site + 6:end])

class CreatorCameraPatchTests(unittest.TestCase):
    def test_camera_keeps_computing_without_active_device(self):
        raw, stub = private_patch_fixture(self)
        before = patch_executable(raw, stub, fix_career_storage=True)
        after = patch_executable(raw, stub, fix_career_storage=True,
                                 fix_creator_camera_input=True)
        pe = pefile.PE(data=after)
        pos = pe.get_offset_from_rva(0x6ab15e - 0x400000)
        self.assertEqual(before[pos:pos + 6], bytes.fromhex('0f 84 7e 03 00 00'))
        self.assertEqual(after[pos:pos + 6], b'\x90' * 6)
        text = pe.sections[0]
        start = text.PointerToRawData
        end = start + text.SizeOfRawData
        self.assertEqual(before[start:pos], after[start:pos])
        self.assertEqual(before[pos + 6:end], after[pos + 6:end])

class PortableSavePathsTests(unittest.TestCase):
    def test_optional_save_path_bridges_only_replace_two_known_calls(self):
        import struct
        raw, stub = private_patch_fixture(self)
        # Synthetic sentinels let this test verify relocation without shipping
        # or relying on original game machine code.
        drive = b'\x90\x90\xc3'
        delete = b'\x90\xc2\x04\x00'
        before = patch_executable(raw, stub)
        after = patch_executable(raw, stub, save_paths_stub=drive,
                                 delete_options_stub=delete)
        pe = pefile.PE(data=after)
        changed = set()
        for va, op, bridge in [(0x5048e5, 0xe9, drive),
                               (0x5b7aba, 0xe8, delete)]:
            pos = pe.get_offset_from_rva(va - 0x400000)
            self.assertEqual(after[pos], op)
            self.assertEqual(after[pos + 5], 0x90)
            target = va + 5 + struct.unpack_from('<i', after, pos + 1)[0]
            offset = pe.get_offset_from_rva(target - 0x400000)
            self.assertEqual(after[offset:offset + len(bridge)], bridge)
            changed.update(range(pos, pos + 6))
        text = pe.sections[0]
        start = text.PointerToRawData; end = start + text.SizeOfRawData
        self.assertFalse(any(before[i] != after[i] for i in range(start, end)
                             if i not in changed))

    def test_save_mapping_requires_native_delete_mapping_together(self):
        raw, stub = private_patch_fixture(self)
        with self.assertRaises(ValueError):
            patch_executable(raw, stub, save_paths_stub=b'\xc3')
