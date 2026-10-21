# Top Spin Portable

Own integration: **djultra64**. This private package contains your game files. Do not publish the complete game folder or its ZIP. A public source-only patch is a separate deliverable.

## Start

There are two entry points:

| Action | Windows | Linux |
| --- | --- | --- |
| Configure graphics and controls | **TopSpinLauncher.exe** | **TopSpinLauncher.sh** |
| Play immediately with the last saved settings | **Play-TopSpin.exe** | **Play-TopSpin.sh** |

The direct Play entry does not open the configurator. Keep both entry points in the portable folder with their runtime files. The private Python/Tk runtime is included; Python does not need to be installed. On Windows, **Play-TopSpin.cmd** remains a compatibility shortcut.

Choose settings, then **Save settings** or **Play**. Settings stay in `.portable/launcher.json`. The launcher preserves the game's Security section and original keyboard profile. Game options and saved profiles stay under the local `T` / `U` folders. Keep these folders when moving or backing up your copy.

## Graphics

- **Render resolution** selects the internal 16:9 image, up to 3840×2160.
- **Display resolution** selects the output window. On Windows, the included game-specific D3D8 wrapper and window sizing present the internal backbuffer at this size. Choose a size your display supports.
- **Full screen** uses a borderless window on Windows.
- Gameplay uses the corrected 16:9 camera. Original menus may remain stretched.
- Original timing stays enabled: **50 FPS gameplay / 30 FPS replays and cinematics**. Native uncapping that accelerated simulation is excluded.
- **Frame generation** is implemented in the Linux graphics runtime. It inserts presentation frames without changing the game's update limit. **Windows frame generation is not included.**

The Linux package requires x86-64 Linux with **glibc 2.42 or newer**, compatible Vulkan graphics drivers, and Proton 11 installed through Steam. The launcher finds Proton automatically and hides its folder selector when available. If it cannot find Proton, it shows **Browse** as a manual fallback. This build does not support older Linux runtime ABIs; they require a separate dependency build. Proton and graphics overrides apply only to the child game process.

## Controllers

The input adapter reads SDL's physical button positions and adapts them inside this game. Xbox 360, Xbox One/Series, PlayStation 4/5 and Nintendo Switch layouts have separate prompt artwork. Real-hardware validation is limited to the available Ally controller; other devices still need hardware checks.

Choose **Controller button style** to prepare fixed prompts before starting the game: **Keyboard**, Xbox, PlayStation or Nintendo Switch. Manual styles stay selected when switching input devices. **Auto detect (experimental)** attempts to follow the last active device; its visible prompts are not yet validated. Nintendo's south/east/west/north buttons are **B / A / Y / X**.

The optional button bindings apply to **both menus and gameplay**, so prompts and actions use the same physical positions. The keyboard profile and other player assignments are preserved. Sticks, D-pad and independent triggers use the original directional timing/deadzone behavior.

Prompt artwork: Nicolae (Xelu) Berbece, updated by Paul Paun, CC0. Authentic notices are retained under `runtime/input/artwork`. dgVoodoo2 is an unmodified component by Dege supplied for this specific Top Spin mod; see `runtime/windows/licenses`.

## Check game files for integrity

This action calculates SHA-256 checksums of the package's immutable game, patch and runtime files. It reports missing or modified files without starting the game. Settings and saves are excluded. The local manifest detects accidental corruption; it is not an authenticity signature or a gameplay test.

## Add to Steam

Click **Add to Steam**. The launcher saves the current settings, detects the active or most recently used Steam account, closes Steam normally if needed, and adds **Top Spin** with its icon, logo, background and both covers. If Steam was open, it reopens automatically afterward. Account selection appears only if Steam's local account information is ambiguous.

A backup is kept beside `shortcuts.vdf`; unrelated shortcuts retain their original bytes. Previous **Top Spin Portable** entries from this folder are renamed while preserving their shortcut ID. Repeating the operation does not add a duplicate. Replaced artwork is backed up; other games' artwork is preserved. If Steam does not finish closing, no shortcut is written. On Linux, leave Steam's forced compatibility tool disabled: this launcher selects Proton itself. After moving the folder, remove the old Steam shortcut and add it again from the new location. Flatpak Steam execution has not been validated.

## Diagnostics

Logs are in `.portable/logs`. Native input initialization status is in `.portable/input-status.txt`. The Windows launcher supports `--self-test <absolute result.json>` and `--verify-files <absolute result.json>` for checks without starting a game.

Do not infer speed, geometry, save compatibility or controller hardware validation from a successful launcher or integrity check. Platform testing and its remaining limits are recorded separately in the project validation report.
