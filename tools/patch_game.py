"""Version-locked portability patch for supplied Top Spin. Author: djultra64."""
import hashlib
import struct
import pefile

SOURCE_SHA256 = '0bb3090d37956daa625faf917854c84f0263f4472c9235abf1f4c0d68721fe79'
WINDOWED_BACKBUFFER_SOURCE_SHA256 = 'ae971be61f8ba0c1c7a21f8ed1a51f5725e26d10d5a3813ef2f199354b7eef97'
WINDOWED_BACKBUFFER_ADDRESS = 0x57a707
# Own replacement: explicit PML height/width, then the original format lookup.
# EBX already points at D3DPRESENT_PARAMETERS; EAX/ECX finish as before.
WINDOWED_BACKBUFFER_CODE = bytes.fromhex(
    'a1 74 c1 7e 00 89 43 04 a1 70 c1 7e 00 89 03 '
    '8b 44 24 14 8b 88 38 04 00 00 89 4b 08 90 90 90 90')


def patch_windowed_backbuffer(raw: bytes) -> bytes:
    """Apply to the exact assembled candidate; no display/protection bypass.

    The original windowed path supplies zero width/height, allowing a launcher
    window resize to change the render size during device initialization.
    Request the configured internal size explicitly, leaving fullscreen intact.
    """
    if hashlib.sha256(raw).hexdigest()!=WINDOWED_BACKBUFFER_SOURCE_SHA256:
        raise ValueError('Unsupported assembled TopSpin.exe for the backbuffer fix')
    pe=pefile.PE(data=raw)
    if pe.OPTIONAL_HEADER.ImageBase!=0x400000 or pe.FILE_HEADER.Machine!=0x14c:
        raise ValueError('Expected the fixed-base x86 game executable')
    offset=pe.get_offset_from_rva(WINDOWED_BACKBUFFER_ADDRESS-0x400000)
    expected=bytes.fromhex('8b442414c786b0a3020000000000c703000000008b8838040000898eb4a30200')
    if raw[offset:offset+32]!=expected:
        raise ValueError('Windowed presentation parameters differ')
    result=bytearray(raw);result[offset:offset+32]=WINDOWED_BACKBUFFER_CODE
    checksum=pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum')
    struct.pack_into('<I',result,checksum,pefile.PE(data=bytes(result)).generate_checksum())
    return bytes(result)

def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary

def patch_executable(raw: bytes, stub: bytes, aspect: float = 16 / 9,
                     fix_options_save: bool = False,
                     fix_career_storage: bool = False,
                     fix_creator_camera_input: bool = False,
                     save_paths_stub: bytes | None = None,
                     delete_options_stub: bytes | None = None) -> bytes:
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unsupported TopSpin.exe; exact research baseline SHA256 required')
    if not stub or len(stub) > 512:
        raise ValueError('Unexpected portability stub size')
    pe = pefile.PE(data=raw)
    if pe.OPTIONAL_HEADER.ImageBase != 0x400000 or not pe.FILE_HEADER.Characteristics & 1:
        raise ValueError('Expected fixed-base executable with stripped relocations')
    last = pe.sections[-1]
    va = align(last.VirtualAddress + max(last.Misc_VirtualSize, last.SizeOfRawData),
               pe.OPTIONAL_HEADER.SectionAlignment)
    save_paths_target = delete_options_target = None
    if save_paths_stub is not None or delete_options_stub is not None:
        if (not save_paths_stub or not delete_options_stub
                or len(save_paths_stub) > 512 or len(delete_options_stub) > 512):
            raise ValueError('Both portable save bridges are required, at most 512 bytes each')
        stub += bytes((-len(stub)) % 16)
        save_paths_target = 0x400000 + va + len(stub)
        stub += save_paths_stub
        stub += bytes((-len(stub)) % 16)
        delete_options_target = 0x400000 + va + len(stub)
        stub += delete_options_stub
    save_wrapper = None
    if fix_options_save or fix_career_storage:
        save_offset = pe.get_offset_from_rva(0x5b7acd - 0x400000)
        if raw[save_offset:save_offset + 6] != bytes.fromhex('ff 15 90 c1 6e 00'):
            raise ValueError('Options free-space call bytes differ')
        stub += bytes((-len(stub)) % 16)
        save_wrapper = 0x400000 + va + len(stub)
        # CALL adds a return address: the API's directory is now [esp+4].
        # Tail-call the original stdcall API, preserving its cleanup and result.
        stub += (bytes.fromhex('c7 44 24 04') + struct.pack('<I', save_wrapper + 14)
                 + bytes.fromhex('ff 25 90 c1 6e 00') + b'.\0')
    file_offset = align(len(raw), pe.OPTIONAL_HEADER.FileAlignment)
    size = align(len(stub), pe.OPTIONAL_HEADER.FileAlignment)
    table = last.get_file_offset() + 40
    if table + 40 > min(s.PointerToRawData for s in pe.sections):
        raise ValueError('No room for PE section header')
    output = bytearray(raw)
    output.extend(bytes(file_offset + size - len(output)))
    struct.pack_into('<8sIIIIIIHHI', output, table, b'.djport\0', len(stub), va,
                     size, file_offset, 0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', output, pe.FILE_HEADER.get_field_absolute_offset('NumberOfSections'),
                     pe.FILE_HEADER.NumberOfSections + 1)
    struct.pack_into('<I', output, pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'),
                     align(va + len(stub), pe.OPTIONAL_HEADER.SectionAlignment))
    struct.pack_into('<I', output, pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'),
                     pe.OPTIONAL_HEADER.SizeOfCode + size)
    output[file_offset:file_offset + len(stub)] = stub
    call_va = 0x57de33
    offset = pe.get_offset_from_rva(call_va - 0x400000)
    if raw[offset:offset + 5] != bytes.fromhex('e8 c8 f0 ff ff'):
        raise ValueError('Installation-directory call bytes differ')
    output[offset:offset + 5] = b'\xe8' + struct.pack('<i', 0x400000 + va - call_va - 5)
    if save_paths_target is not None:
        for address, expected, opcode, target in [
                (0x5048e5, '8a 02 3c 44 74 04', 0xe9, save_paths_target),
                (0x5b7aba, 'ff 15 e8 c0 6e 00', 0xe8, delete_options_target)]:
            pos = pe.get_offset_from_rva(address - 0x400000)
            if raw[pos:pos + 6] != bytes.fromhex(expected):
                raise ValueError('Portable save bridge call bytes differ')
            output[pos:pos + 6] = bytes([opcode]) + struct.pack('<i', target - address - 5) + b'\x90'
    if fix_options_save:
        output[save_offset:save_offset + 6] = (b'\xe8' + struct.pack(
            '<i', save_wrapper - 0x5b7acd - 5) + b'\x90')
    if fix_career_storage:
        career_call = 0x5a4b7e
        career_offset = pe.get_offset_from_rva(career_call - 0x400000)
        if raw[career_offset:career_offset + 6] != bytes.fromhex('ff 15 90 c1 6e 00'):
            raise ValueError('Career free-space call bytes differ')
        # The original query uses the virtual asset drive Z:, which can report
        # zero space under Proton and abort skeleton initialization. Keep the
        # real API result and the game's capacity/failure checks intact.
        output[career_offset:career_offset + 6] = (b'\xe8' + struct.pack(
            '<i', save_wrapper - career_call - 5) + b'\x90')
    if fix_creator_camera_input:
        camera_branch = pe.get_offset_from_rva(0x6ab15e - 0x400000)
        if raw[camera_branch:camera_branch + 6] != bytes.fromhex('0f 84 7e 03 00 00'):
            raise ValueError('Creator camera input branch bytes differ')
        # A missing active device must not leave the cached camera transform
        # uninitialized. The original axis/button readers already return zero
        # for a null device; keep their calculations and normal device path.
        output[camera_branch:camera_branch + 6] = b'\x90' * 6
    if not 1 <= aspect <= 4:
        raise ValueError('Invalid aspect ratio')
    camera_offset = pe.get_offset_from_rva(0x48fc93 - 0x400000)
    if raw[camera_offset:camera_offset + 4] != struct.pack('<f', 4 / 3):
        raise ValueError('Camera default bytes differ')
    struct.pack_into('<f', output, camera_offset, aspect)
    check = pefile.PE(data=bytes(output))
    struct.pack_into('<I', output, pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum'),
                     check.generate_checksum())
    return bytes(output)
