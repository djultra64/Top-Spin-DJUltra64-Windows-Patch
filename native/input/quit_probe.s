# Own ABI checker: ECX=this, one stack argument, callee consumes 4. djultra64.
.intel_syntax noprefix
.code32
.section .text
.global abi_check
abi_check:
 push ebp
 push ebx
 push esi
 push edi
 mov eax,[esp+20]
 mov ebp,esp
 mov ebx,0x12345678
 mov esi,0x23456789
 mov edi,0x3456789a
 push DWORD PTR probe_params
 mov ecx,0x56789abc
 call eax
 test eax,eax
 jnz fail
 cmp esp,ebp
 jne fail
 cmp ebx,0x12345678
 jne fail
 cmp esi,0x23456789
 jne fail
 cmp edi,0x3456789a
 jne fail
 xor eax,eax
 jmp finish
fail:
 mov eax,1
finish:
 mov esp,ebp
 pop edi
 pop esi
 pop ebx
 pop ebp
 ret
# Three-argument thiscall binder wrapper must preserve original EAX and ret12.
.global registry_abi_check
registry_abi_check:
 push ebp
 push ebx
 push esi
 push edi
 mov eax,[esp+20]
 mov ebp,esp
 mov ebx,0x12345678
 mov esi,0x23456789
 mov edi,0x3456789a
 push 0x443cb0
 push 0xa03000
 push 0x6fbbbc
 mov ecx,0xa02000
 call eax
 cmp eax,0x12340001
 jne fail
 cmp esp,ebp
 jne fail
 cmp ebx,0x12345678
 jne fail
 cmp esi,0x23456789
 jne fail
 cmp edi,0x3456789a
 jne fail
 xor eax,eax
 jmp finish
.section .note.GNU-stack,"",@progbits
