# djultra64: DeleteFileA must resolve the same portable path as the game reader.
# stdcall BOOL DeleteFileA(LPCSTR path); preserve callee-saved registers.
.intel_syntax noprefix
.code32
.text
.global portable_options_delete
portable_options_delete:
 push esi
 sub esp,512
 mov esi,esp
 push 512
 push esi
 push DWORD PTR [esp+528]
 mov eax,0x5048c0
 call eax
 add esp,12
 push esi
 call DWORD PTR ds:0x6ec0e8
 add esp,512
 pop esi
 ret 4
