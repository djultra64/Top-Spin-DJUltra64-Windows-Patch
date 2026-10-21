# Top Spin - DJUltra64 Windows Patch

A compatibility patch for the original PC version of **Top Spin**, by **djultra64**. Includes an English launcher, corrected 16:9 gameplay camera, rendering up to **3840 × 2160**, local saves and controller prompts for Xbox, PlayStation and Nintendo Switch.

The patch contains project code and redistributable dependencies. **You need your own compatible installation of the game.** Original game executables, assets and keys are not included.

## Download and install on Windows

1. Download [TopSpin-DJUltra64-Windows-Patch-v0.1.0.zip](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.1.0/TopSpin-DJUltra64-Windows-Patch-v0.1.0.zip) from [the v0.1.0 release](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/tag/v0.1.0).
2. Close the game and launcher. Extract the ZIP **directly into the game folder containing `TopSpin.exe`**. `Install-Patch.cmd` and `.topspin-patch` must sit beside `TopSpin.exe`.
3. Double-click **`Install-Patch.cmd`** and wait for the success message. The installer checks the supported executable, game resources and payload before changing game files, and backs up replaced originals locally.
4. Open **`TopSpinLauncher.exe`** to configure graphics and controls, or **`Play-TopSpin.exe`** to start with saved settings.

No separate Python installation is needed. Keep the included runtime folders with the launcher. See [Windows instructions](docs/windows.md) for requirements, supported versions, backups and troubleshooting.

## Features

- Corrected **16:9 gameplay camera** and internal rendering up to **4K**, with a separate output resolution. Original menus can remain stretched.
- Original **50 FPS gameplay / 30 FPS replay and cinematic timing**, with synchronization preserved.
- English configuration launcher and direct Play shortcut.
- Xbox 360/One/Series, PlayStation 4/5 and Nintendo Switch prompt styles, manual family selection and optional action remapping. Switch's **B/A/Y/X** physical layout is handled separately from Xbox's **A/B/X/Y**.
- **Quit Game** added to the main menu; the game's FPS counter is off by default.
- Local `T`/`U` save folders, integrity checking and an optional Steam shortcut.

Installation defaults are **3840 × 2160 internal / 1920 × 1080 output**, English, Xbox 360 prompts and frame generation off. Change them in the launcher to suit your display and controller. Automatic last-device prompt switching is available as an experimental option; manual styles provide a fixed selection.

Windows interpolation is being developed separately and is **not included in this release**. The Linux development runtime has a separate frame-generation path that adds presentation frames without increasing the game's simulation rate.

## Your copy of the game

Use the patch with a **legally purchased or otherwise lawfully obtained PC copy of Top Spin** that matches the supported version. You supply the game yourself; no game download, product key or licensing bypass is provided here.

As of **October 20, 2026**, we have not found the original PC release for sale through a current official digital storefront. GOG lists it as a [Dreamlist request](https://www.gog.com/dreamlist/game/top-spin-2003), and it appears on abandonware sites. This describes availability, not permission to download or redistribute the game: the “abandonware” label is not a license. Second-hand physical copies may still be available.

## Compatibility and other platforms

The installer accepts only the executable hashes listed in [Windows instructions](docs/windows.md) and the matching game resource variants. It rejects unsupported versions instead of applying offsets blindly. These supported inputs are not a claim of compatibility with every retail edition. No new CD-key or licensing bypass is implemented.

There is **no drop-in Linux binary release** in this Windows ZIP. Linux source/runtime instructions are in [the Linux guide](docs/linux.md); its current runtime requires x86-64 Linux, glibc 2.42 or newer, Vulkan, X11/Xwayland and Steam Proton 11.

For component builds and release assembly, see [Building](docs/building.md). For launcher controls, see [the launcher reference](launcher/README.md).

Own work is attributed exclusively to **djultra64**. Third-party authorship and required license notices remain intact. No project-wide open-source license has been selected; see [NOTICE.md](NOTICE.md). Do not redistribute original game files, generated game resources, personal keys or the installer's local backups.
