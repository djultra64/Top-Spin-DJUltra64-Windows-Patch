# Top Spin launcher

Own integration: **djultra64**. Install the patch into your own compatible game using the [Windows](../docs/windows.md) or [Linux / Proton](../docs/linux.md) installation guide. The patch includes launcher runtimes; original game files and keys are not included.

## Start

| Action | Windows | Linux / Proton |
| --- | --- | --- |
| Configure graphics and controls | `TopSpinLauncher.exe` | `TopSpinLauncher.sh` |
| Play with saved settings | `Play-TopSpin.exe` | `Play-TopSpin.sh` |

The direct Play entry opens the game with saved settings. Keep the entry points and their runtime folders together. On Windows, `Play-TopSpin.cmd` is an alternative direct shortcut. Both platform releases include their own Python/Tk runtime. Use the Windows ZIP or Linux tar.gz for your operating system; their installer runtimes are separate.

Choose settings, then **Save settings** or **Play**. Launcher settings stay in `.portable/launcher.json`. The launcher preserves the game's Security section and original keyboard profile. Game options and profiles stay under local `T`/`U` folders; keep them when moving or backing up the game.

## Graphics

- **Render resolution** selects the internal 16:9 image, up to 3840 × 2160.
- **Display resolution** selects the output size. Windows uses the game-specific D3D8 wrapper; a complete Linux runtime uses Gamescope. Choose an output supported by your display.
- **Full screen** uses borderless presentation on Windows.
- Gameplay uses the corrected 16:9 camera. Original menus can remain stretched.
- Timing stays at **50 FPS gameplay / 30 FPS replays and cinematics** with synchronization enabled.
- **Frame interpolation** on Windows uses the included DXVK/AFMF component and is off by default. Enable it, then select **Save settings** or **Play**. Disable it and save to restore dgVoodoo2. It requires a compatible Vulkan driver; see [Windows interpolation](../docs/windows-interpolation.md). Linux retains its separate **Frame generation** option.

Fresh installation defaults on both platforms are 3840 × 2160 render / 1920 × 1080 output, English, Xbox 360 prompts and interpolation off. The game FPS counter is disabled, and **Quit Game** is available in the main menu.

The Linux runtime needs x86-64 Linux with glibc 2.42 or newer, Vulkan, X11/Xwayland and an existing Steam Proton 11 installation. The launcher finds Proton in known Steam locations; **Browse** appears when a manual selection is needed.

## Controllers

Choose **Controller button style** for Keyboard, Xbox, PlayStation or Nintendo Switch prompts. Manual styles stay selected when changing input devices. **Auto detect (experimental)** attempts to follow the last active device; manual selection provides a fixed family when detection is ambiguous.

Actions map to physical positions. Xbox south/east/west/north buttons are **A / B / X / Y**; Nintendo Switch uses **B / A / Y / X**. Optional button mappings apply to both menus and gameplay so actions and their prompts follow the same positions. The keyboard profile and other player assignments are preserved. Sticks, D-pad and independent triggers retain the original directional timing/deadzone behavior.

Controller prompt artwork is by Nicolae (Xelu) Berbece, updated by Paul Paun, under CC0. dgVoodoo2 is an unmodified component by Dege supplied for this specific Top Spin mod. Included dependency notices preserve their authentic attribution.

## Integrity and Steam

**Check game files for integrity** compares SHA-256 checksums of immutable game, patch and runtime files and reports missing/modified files. Settings and saves are excluded. The local manifest is a corruption check, not an authenticity signature.

**Add to Steam** saves settings, detects the local account and adds a shortcut. It closes Steam normally if necessary and reopens it afterward. Account selection appears when local account information is ambiguous. Existing shortcuts and artwork are preserved or backed up as appropriate; repeating the action does not create a duplicate entry for the same game folder.

On Linux, leave Steam's forced compatibility tool disabled because the launcher selects Proton. After moving the game folder, remove the old shortcut and add it again. Steam artwork is used only when it is available locally; the public patch does not include original game artwork.

## Diagnostics and backups

Logs are in `.portable/logs`; native controller initialization status is in `.portable/input-status.txt`. Windows diagnostic modes `--self-test <absolute result.json>` and `--verify-files <absolute result.json>` run without starting the game; see [the native launcher guide](../native/launcher/README.md).

Installer originals are under `.portable/backups/topspin-patch-v1`, and the receipt is `.portable/patch-install.json`. Upgrades keep replaced project/runtime files and the previous receipt under `.portable/backups/topspin-patch-updates/<payload-sha256>` while preserving preferences, controls and saves. Keep these files for recovery. Backups, generated game resources, personal keys and complete game folders belong only in your private installation, not public uploads.
