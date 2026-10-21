# djultra64 — replace the installation-directory lookup only.
# Signature matches the cdecl reader at the sole call site in 0x57de33.
# Arguments: key, value, output, capacity, root. Preserve callee-saved registers.
.intel_syntax noprefix
.code32
.text
.global portable_path
portable_path:
    push esi
    push edi
    mov esi, [esp+20]
    push DWORD PTR [esp+24]
    push esi
    push 0
    call DWORD PTR ds:0x6ec0d0 # Existing GetModuleFileNameA import
    test eax, eax
    jz failed
    cmp eax, [esp+24]
    jae failed
    lea edi, [esi+eax]
scan:
    cmp edi, esi
    jbe failed
    dec edi
    cmp BYTE PTR [edi], 92
    jne scan
    cmp edi, esi
    je failed
    # Keep the slash when the executable is directly in a drive root.
    lea eax, [esi+2]
    cmp edi, eax
    jne trim
    inc edi
trim:
    mov BYTE PTR [edi], 0
    mov eax, 1
.ifdef ENABLE_INPUT_HOOK
    # Preserve the directory lookup result, registers and flags around our
    # optional helper. Build its absolute path from the executable directory.
    pushfd
    pushad
    sub esp, 544
    mov edx, esi
    mov edi, esp
    mov ecx, 480
input_copy_root:
    mov al, [edx]
    inc edx
    mov [edi], al
    inc edi
    test al, al
    jz input_append_suffix
    loop input_copy_root
    jmp input_done
input_append_suffix:
    dec edi
    call input_suffix_pointer
    .asciz "\\runtime\\input\\djultra-input.dll"
input_suffix_pointer:
    pop edx
input_copy_suffix:
    mov al, [edx]
    inc edx
    mov [edi], al
    inc edi
    test al, al
    jne input_copy_suffix
    push esp
    call DWORD PTR ds:0x6ec1dc # Existing LoadLibraryA import
    test eax, eax
    jz input_done
    mov ebx, eax
    call input_export_pointer
    .asciz "DjultraInitialize"
input_export_pointer:
    pop edx
    push edx
    push ebx
    call DWORD PTR ds:0x6ec1e0 # Existing GetProcAddress import
    test eax, eax
    jz input_done
    call eax
input_done:
    add esp, 544
    popad
    popfd
.endif
    pop edi
    pop esi
    ret
failed:
    xor eax, eax
    pop edi
    pop esi
    ret
