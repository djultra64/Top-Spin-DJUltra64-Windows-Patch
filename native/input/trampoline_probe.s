# Own minimal thiscall routine, not a copy of game logic. djultra64.
.intel_syntax noprefix
.code32
.section .fontstub,"ax"
.space 0xd50
.global own_font_lookup
own_font_lookup:
 push ebp
 mov bp,WORD PTR [esp+8]
 movzx eax,bp
 pop ebp
 ret 4
