"""Explicit windowed render dimensions; own ABI fixture, no game execution."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import pefile
from tools.patch_game import (WINDOWED_BACKBUFFER_CODE, WINDOWED_BACKBUFFER_ADDRESS,
                              patch_windowed_backbuffer)


class WindowedBackbufferTests(unittest.TestCase):
    def test_unknown_executable_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            patch_windowed_backbuffer(b'unknown')

    def test_version_locked_change_preserves_all_other_game_bytes(self):
        source=Path('build/TopSpin-Controller-Candidate/TopSpin.exe')
        if not source.exists():self.skipTest('Private assembled integration fixture is unavailable')
        raw=source.read_bytes();changed=patch_windowed_backbuffer(raw)
        pe=pefile.PE(data=raw);offset=pe.get_offset_from_rva(WINDOWED_BACKBUFFER_ADDRESS-0x400000)
        self.assertEqual(changed[offset:offset+32],WINDOWED_BACKBUFFER_CODE)
        checksum=pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum')
        restored=bytearray(changed)
        restored[checksum:checksum+4]=raw[checksum:checksum+4]
        restored[offset:offset+32]=raw[offset:offset+32]
        self.assertEqual(bytes(restored),raw)
        self.assertTrue(pefile.PE(data=changed).verify_checksum())

    @unittest.skipUnless(sys.platform=='linux' and shutil.which('as') and shutil.which('ld'),
                         'Own ABI harness requires Linux x86 compatibility and GNU binutils')
    def test_actual_32bit_code_uses_internal_resolution_and_preserves_format_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);payload=root/'payload.bin';payload.write_bytes(WINDOWED_BACKBUFFER_CODE)
            source=root/'harness.s'
            source.write_text(r'''.intel_syntax noprefix
.section .pml,"aw"
width: .long 0
height: .long 0
.section .data
cases: .long 1280,720,1920,1080,3840,2160
.section .bss
app: .space 0x2a500
adapter: .space 0x500
.section .text
payload:
.incbin "PAYLOAD"
ret
.global _start
_start:
mov edi,offset cases
mov ebp,3
mov dword ptr [adapter+0x438],22
mov dword ptr [app+0x2a3b8],1
mov dword ptr [app+0x2a3c8],1
again:
mov eax,[edi]
mov [width],eax
mov eax,[edi+4]
mov [height],eax
mov esi,offset app
lea ebx,[esi+0x2a3ac]
sub esp,32
mov dword ptr [esp+0x10],offset adapter
mov edx,0x12345678
call payload
add esp,32
cmp eax,offset adapter
jne failed
cmp ecx,22
jne failed
cmp edx,0x12345678
jne failed
mov eax,[width]
cmp [ebx],eax
jne failed
mov eax,[height]
cmp [ebx+4],eax
jne failed
cmp dword ptr [ebx+8],22
jne failed
cmp dword ptr [ebx+12],1
jne failed
cmp dword ptr [ebx+28],1
jne failed
add edi,8
dec ebp
jnz again
xor ebx,ebx
jmp done
failed:
mov ebx,1
done:
mov eax,1
int 0x80
'''.replace('PAYLOAD',str(payload)))
            subprocess.run(['as','--32',str(source),'-o',str(root/'harness.o')],check=True,capture_output=True)
            subprocess.run(['ld','-melf_i386','-e','_start','-Ttext','0x8048000',
                            '--section-start=.pml=0x7ec170',str(root/'harness.o'),'-o',str(root/'harness')],
                           check=True,capture_output=True)
            result=subprocess.run([str(root/'harness')],capture_output=True)
            if result.returncode==-31:self.skipTest('Sandbox blocks x86 syscalls; execute this own ABI harness outside the sandbox')
            self.assertEqual(result.returncode,0,'The actual instructions must keep configured dimensions even with a smaller output window.')
