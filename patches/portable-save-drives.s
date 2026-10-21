# djultra64: resolve virtual T:/U: paths under the executable's T/U folders.
# Entry replaces 5048e5..5048ea in the version-locked path resolver.
.intel_syntax noprefix
.code32
.text
.global _start
_start:
 mov al,[edx]
 cmp al,'T'
 je portable
 cmp al,'t'
 je portable
 cmp al,'U'
 je portable
 cmp al,'u'
 je portable
 cmp al,'D'
 je game
 cmp al,'d'
 je game
 mov ecx,0x504939
 jmp ecx
game:
 mov ecx,0x5048ef
 jmp ecx
portable:
 and eax,0xff
 and al,0xdf
 add edx,2
 cmp BYTE PTR [edx],92
 jne tail_ready
 inc edx
tail_ready:
 call format_ready
 .asciz "%s\\%c\\%s"
format_ready:
 pop ecx
 push edx
 push eax
 push 0x9bdef0
 push ecx
 push DWORD PTR [esp+28]
 push DWORD PTR [esp+28]
 mov eax,0x503eb0
 call eax
 add esp,24
 ret
