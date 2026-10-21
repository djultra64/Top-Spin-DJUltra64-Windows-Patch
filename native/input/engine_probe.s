# Own stub only: reserve exact ABI entry, never original game code. djultra64.
.intel_syntax noprefix
.code32
.section .enginestub,"ax"
.space 0x1e0
.global own_engine_reader
own_engine_reader:
 # Choose the alternate x86 MOV encoding expected by the guarded entry.
 .byte 0x55,0x8b,0xec,0x83,0xe4,0xf8
 mov eax,DWORD PTR [ebp+12]
 mov DWORD PTR [eax],0x12345678
 mov eax,37
 mov esp,ebp
 pop ebp
 ret
