# MainMenu Quit update: private package plan

Author: djultra64. Prepared 2026-10-20; not an applied package update.

## Reviewed candidate

The private integration candidate `build/TopSpin-Quit-Candidate-2` contains:

| File | Expected SHA256 / value |
| --- | --- |
| runtime/input/djultra-input.dll | 8e7787fd710cc6265a657f54393cffc8505f53eb186cf25ee79b3ba55dce949e |
| Media/MenuPart/RuiPC/MainMenu.rui | 937ea450e51b34085e1bad57a24315c97953902897371d9100f11cea4f9bc825 |
| Config.pml: DebugSettings/ShowFPS | false |

The native bridge changes only the five-byte CALL at `0x448d50` in process memory. Its wrapper preserves the original TitleSelect registration and its return value, then registers `DjultraQuitGame` on that same MainMenu receiver. It does not change the Career binding at `0x47e40d` or shared stub `0x4022a0`. The new method accepts only the exact one-string marker `djultra64.quit-game` and uses the original game-wide confirmation. The menu calls `this.DjultraQuitGame('djultra64.quit-game')`.

Read-only checks confirmed all native byte/name guards, PE32 base and image size match both the Linux candidate executable and the existing Windows Explicit4K executable. This establishes compatible guard inputs, not runtime validation on Windows. The own x86 harness verifies original-plus-alias registration, receiver/name/function arguments, original EAX return, ret12 registration ABI, ret4 action ABI, callee-saved registers, negative marker cases and Yes/No state handling. The broader native regression suite passed eleven tests outside the sandbox; its 32-bit syscall harness is skipped under restrictive seccomp.

`input-status.txt` uses bit8 for bridge installation: complete initialization is 15. `.portable/quit-status.txt` distinguishes alias registration, rejected argument categories, confirmation request and resulting confirmation/cancellation. These diagnostics are mutable and excluded from integrity manifests.

## Narrow update after the focused game validation

1. Record whether the row fits, navigation reaches it, No returns to the menu, Yes follows normal game shutdown, and the diagnostic agrees. A failed result blocks promotion of these changes.
2. Create new private staging folders from the existing Windows and Linux package baselines. Do not update live/running copies. Do not use the older `dist/TopSpin-Portable` tree as a new baseline: it lacks the current native input DLL and integrity manifest.
3. Replace only the native DLL and MainMenu archive with the reviewed files above. Edit each destination's existing PML tree to set `DebugSettings/ShowFPS=false`; preserve all other settings and private registration data. Never copy a candidate's entire Config.pml over another package's configuration.
4. Regenerate each immutable integrity manifest using its existing membership. Only the DLL and MainMenu entries should change; Config.pml and save/diagnostic state remain excluded. Verify membership count, unchanged remaining hashes, platform runtime selection, and absence of prefixes/logs/caches/personal saves from the deliverable.
5. Create new private ZIP/TAR archives preserving the established Windows/Linux entry points and Linux executable permissions. Extract into fresh paths with spaces and verify every immutable checksum there. Update archive SHA256 sidecars only after final archive bytes are complete.
6. Update source validation reports to identify the exact Quit candidate tested. Retain the earlier Windows launcher/render evidence, and explicitly distinguish it from any new Quit behavior not tested on Windows. Refresh private package receipts/checksums without claiming a newly tested Windows gameplay path.

No frozen launcher rebuild, extra runtime dependency, new Steam action, DRM change, or game executable replacement is required for this update. No public asset package is produced: the modified MainMenu archive remains private, while the patch recipe, own native source, version guards and synthetic tests can be shared separately.
