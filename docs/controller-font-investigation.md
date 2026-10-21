# Controller prompt font investigation

Own investigation: **djultra64**. Addresses below describe the version-locked private executable; no original executable bytes or font assets are included here.

## Confirmed cause

The first integration extended `Help_NovaBlackSSK`, but the root menu's English `Help_Continue` / `help_continue` string entries select **`NovaBlackSSK_14`**. Merely finding an extended Help font loaded in memory did not establish that the visible prompt used it. The live process had both an extended 256×1024 font and an unextended 256×512 font. Parent-side mutation of the unused Help font's UV record left the bottom prompt unchanged and was restored.

The English prompt inventory requires five fonts: `Help_NovaBlackSSK`, `NovaBlackSSK_14`, `NovaBlackSSK_12`, `04b_11_12` and `NovaBlackSSK_24_Buttons`. The extension covers 18 instances and seven version-locked font/texture pairs, including DXT3, DXT5 and BGRA32. The native hook recognizes the appended private-use range rather than a single atlas size. Japanese fonts are outside this English prompt implementation.

## Confirmed remaining ABI mismatch

Extending all fonts still left keyboard prompts visible. The caller at **0x5f2da6** writes the UTF-16 character into **SI**, preserving the upper half of ESI, then pushes the full register at **0x5f2dd4**. The original lookup reads only the low 16 bits. Our hook compared the entire 32-bit argument, so pointer-derived upper bits prevented a match.

The hook now normalizes its argument to 16 bits before mapping. An actual thiscall harness reproduced the failure with dirty upper bits against the previous DLL, then passed 168 cases with the fix. The static-mode harness also passed 168 cases. These are ABI tests, not a claim of visually validated dynamic device switching.

## Manual selection

The launcher prepares fixed prompts before starting the game by copying the chosen family's appended glyph records into the original keyboard-code slots. Each change is generated from hash-verified private baseline backups, preserving codepoint ranges and the existing texture. Keyboard restores the exact baseline archives. Optional button remaps select physical positions consistently with the game bindings, including Nintendo's swapped face-button names.

Configuration, prompt resources and their local integrity hashes are written as one recoverable transaction while holding the game-folder lock. Private backups contain original-derived game resources and must not be published. The public implementation contains hashes and transformation logic only.

A real Linux menu capture, `reports/runtime/controller-manual-xbox-menu.png`, shows the green A icon beside Continue and yellow Y beside Help with the Xbox 360 style. Other controller families and dynamic switching still need real-device visual checks.

## Why no speculative cache invalidation was added

The font metrics wrapper at **0x612dd0** calls the lookup at **0x612d50**, then stores the actual 28-byte glyph-record pointer at the output metrics structure's **+8**. It does not itself bake UV coordinates into a mesh.

The text layout/draw routine at **0x5f2c00** reads its font from `this + 0x50`. Its first-200-character metrics cache is a **stack-local temporary** rebuilt by that invocation, with calls through font virtual slot +0x14 at **0x5f2dd7** and **0x5f2dfe**. The draw pass reuses those temporary records and falls back to another lookup at **0x5f2fde** for longer text. At **0x5f32d3**, it passes the metrics/glyph pointer to the text renderer through virtual slot +0x18 of `this + 0x1c`.

These observations do not establish that every screen rebuilds its text every frame, but they disprove treating this specific 200-entry array as a persistent cross-frame cache. The font-selection mismatch and independently reproduced argument-width mismatch explain the failures without adding a cache-invalidating hook.

## Original prompt codepoints independently checked

The original private atlas shows:

| Codepoint | Keyboard prompt | Logical menu action |
| --- | --- | --- |
| U+2123 | Return | Confirm |
| U+2124 | Backspace | Back |
| U+2125 | F8 | Regenerate / contextual secondary action |
| U+2126 | F1 | Help |
| U+2127 | F6 | Next view |
| U+2128 | F5 | Previous view |
| U+212B | F7 | Select |
| U+212C | Tab | Pause / contextual menu action |

This validates the existing eight-code mapping as an atlas mapping. It does not independently prove that every screen assigns the same logical action to those keys; contextual prompts still require matching the actual configured action.

The private visual contact sheet is `build/original-keyglyph-map.png`; it contains original pixels and must remain excluded from public source/packages.

## Validation needed after extending all selected fonts

- Parse and validate each source atlas's actual dimensions/compression rather than assuming Help's DXT5 layout.
- Preserve original compressed image blocks and original glyph sizes/coverage.
- Recognize extended atlas variants by their appended private-use range and supported dimensions; leave unrelated fonts unchanged.
- Exercise every family/physical position against synthetic font objects for each supported variant in the own native harness.
- Confirm a visible prompt changes when the active device changes and restores the keyboard prompt on keyboard activity, using a single concrete gameplay session when ready.
