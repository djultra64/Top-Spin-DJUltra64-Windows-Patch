"""Build our freestanding PE32 input/prompt DLL without game code. djultra64."""
import argparse
from pathlib import Path
import subprocess

SOURCE=Path(__file__).resolve().parent.parent
IMPORTS={
    'kernel32.dll':['GetModuleHandleA','GetModuleFileNameA','GetProcAddress','LoadLibraryA',
        'GetEnvironmentVariableA','GetTickCount','VirtualAlloc','VirtualProtect',
        'FlushInstructionCache','GetCurrentProcess','GetCurrentProcessId',
        'CreateFileA','WriteFile','CloseHandle'],
    'user32.dll':['GetAsyncKeyState','GetForegroundWindow','GetWindowThreadProcessId'],
}
EXPORTS=['DjultraInitialize','DjultraPoll','DjultraGetActiveFamily','DjultraGetPadCount','DjultraResolveGlyphForTest','DjultraReadController']


def _import_assembly():
    lines=['.intel_syntax noprefix','.code32','.section .idata,"aw"']
    for i,(dll,names) in enumerate(IMPORTS.items()):
        lines.append(f'.long lookup_{i}-0x10000000,0,0,dll_{i}-0x10000000,table_{i}-0x10000000')
    lines.append('.long 0,0,0,0,0')
    for i,(dll,names) in enumerate(IMPORTS.items()):
        lines.append(f'lookup_{i}:')
        lines.extend(f'.long hint_{name}-0x10000000' for name in names);lines.append('.long 0')
        lines.append(f'table_{i}:')
        for name in names:lines.extend([f'.global iat_{name}',f'iat_{name}: .long hint_{name}-0x10000000'])
        lines.append('.long 0');lines.extend([f'dll_{i}:',f'.asciz "{dll}"'])
        for name in names:lines.extend(['.align 2',f'hint_{name}: .short 0',f'.asciz "{name}"'])
    return '\n'.join(lines)+'\n'


def build_input_hook(destination: Path) -> Path:
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    objects=[]
    for name in ['input','policy','engine']:
        target=destination/(name+'.o')
        subprocess.run(['gcc','-m32','-O2','-ffreestanding','-fno-pie','-fno-builtin',
            '-fno-stack-protector','-fno-asynchronous-unwind-tables','-mstackrealign',
            '-mpreferred-stack-boundary=2','-mincoming-stack-boundary=2',
            '-Wall','-Wextra','-c',str(SOURCE/'native/input'/(name+'.c')),'-o',str(target)],check=True)
        objects.append(str(target))
    imports=destination/'imports.s';imports.write_text(_import_assembly());obj=destination/'imports.o'
    subprocess.run(['as','--32',str(imports),'-o',str(obj)],check=True);objects.append(str(obj))
    definition=destination/'input.def';definition.write_text('LIBRARY djultra-input\nEXPORTS\n '+ '\n '.join(EXPORTS)+'\n')
    dll=destination/'djultra-input.dll'
    subprocess.run(['ld','-mi386pe','--shared','--enable-reloc-section','--image-base','0x10000000',
        '--no-leading-underscore','-T',str(SOURCE/'native/input/input.ld'),'-o',str(dll),*objects,str(definition)],check=True)
    return dll

def build_path_stub(destination: Path,*,enable_input=False) -> Path:
    destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    obj=destination/'portable-path.o';binary=destination/'portable-path.bin'
    command=['as','--32']
    if enable_input:command+=['--defsym','ENABLE_INPUT_HOOK=1']
    subprocess.run(command+[str(SOURCE/'patches/portable-path.s'),'-o',str(obj)],check=True)
    subprocess.run(['objcopy','-O','binary','-j','.text',str(obj),str(binary)],check=True)
    return binary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    print(build_input_hook(parser.parse_args().destination))
