"""Build our isolated x86 native Windows resolution probe. djultra64.

Run only inside a project-private folder containing the official D3D8 wrapper
and MinHook.x86.dll. No original game files are required.
"""
from pathlib import Path
import subprocess
SOURCE=Path(__file__).resolve().parent.parent
root=SOURCE/'build/native-graphics-probe';root.mkdir(parents=True,exist_ok=True)
imports=['GetModuleHandleA','GetModuleFileNameA','LoadLibraryA','GetProcAddress','CreateFileA','WriteFile','CloseHandle','ExitProcess','Sleep']
lines=['.intel_syntax noprefix','.code32','.section .idata,"aw"','.long lookup-0x400000,0,0,dll-0x400000,table-0x400000','.long 0,0,0,0,0','lookup:']
lines += [f'.long hint_{n}-0x400000' for n in imports]+['.long 0','table:']
for n in imports:lines += [f'.global iat_{n}',f'iat_{n}: .long hint_{n}-0x400000']
lines += ['.long 0','dll: .asciz "kernel32.dll"']
for n in imports:lines += ['.align 2',f'hint_{n}: .short 0',f'.asciz "{n}"']
(root/'imports.s').write_text('\n'.join(lines)+'\n')
(root/'probe.ld').write_text((SOURCE/'native/input/input.ld').read_text().replace('ENTRY(DllMain)','ENTRY(_start)').replace('0x10001000','0x401000'))
subprocess.run(['gcc','-m32','-O2','-ffreestanding','-fno-pie','-fno-builtin','-fno-stack-protector','-fno-asynchronous-unwind-tables','-mstackrealign','-mpreferred-stack-boundary=2','-mincoming-stack-boundary=2','-Wall','-Wextra','-c',str(SOURCE/'native/graphics/ResolutionProbe.c'),'-o',str(root/'probe.o')],check=True)
subprocess.run(['as','--32',str(root/'imports.s'),'-o',str(root/'imports.o')],check=True)
subprocess.run(['ld','-mi386pe','--image-base','0x400000','--no-leading-underscore','-T',str(root/'probe.ld'),'-o',str(root/'NativeGraphicsProbe.exe'),str(root/'probe.o'),str(root/'imports.o')],check=True)
