OUTPUT_FORMAT(pei-i386)
OUTPUT_ARCH(i386)
ENTRY(DllMain)
SECTIONS {
 . = 0x10001000;
 .text : { *(.text*) }
 . = ALIGN(4096);
 .rdata : { *(.rdata*) *(.rodata*) }
 . = ALIGN(4096);
 .data : { *(.data*) }
 . = ALIGN(4096);
 .bss : { *(.bss*) *(COMMON) }
 . = ALIGN(4096);
 .idata : { *(.idata*) }
 . = ALIGN(4096);
 .edata : { *(.edata*) }
 . = ALIGN(4096);
 .reloc : { *(.reloc*) }
 /DISCARD/ : { *(.note*) *(.comment*) *(.eh_frame*) }
}
