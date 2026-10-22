# Top Spin - DJUltra64 Windows Patch

A compatibility patch for the original PC version of **Top Spin**, by **djultra64**. Includes an English launcher, corrected 16:9 gameplay camera, rendering up to **3840 × 2160**, local saves and controller prompts for Xbox, PlayStation and Nintendo Switch.

The patch contains project code and redistributable dependencies. **You need your own compatible PC copy: installed game files on Windows, or a game ISO on Linux.** Original game executables, assets and keys are not included.

## Download and install on Windows

1. Download [TopSpin-DJUltra64-Windows-Patch-v0.2.1.zip](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.2.1/TopSpin-DJUltra64-Windows-Patch-v0.2.1.zip) from [the v0.2.1 release](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/tag/v0.2.1).
2. Close the game and launcher. Extract the ZIP **directly into the game folder containing `TopSpin.exe`**. `Install-Patch.cmd` and `.topspin-patch` must sit beside `TopSpin.exe`.
3. Double-click **`Install-Patch.cmd`** and wait for the success message. The installer checks the supported executable, game resources and payload before changing game files, and backs up replaced originals locally.
4. Open **`TopSpinLauncher.exe`** to configure graphics and controls, or **`Play-TopSpin.exe`** to start with saved settings.

Upgrading from Windows v0.1.0 or v0.2.0 uses the same steps and preserves existing settings, controls and saves. No separate Python installation is needed. Keep the included runtime folders with the launcher. See [Windows instructions](docs/windows.md) for requirements, supported versions, backups and troubleshooting.

## Download and install on Linux / Proton

Requires **x86-64 Linux, glibc 2.42 or newer, Vulkan, X11/Xwayland and Steam Proton 11**. The installer includes Python/Tk, ISO/CAB extraction tools, Gamescope, video libraries and the Linux interpolation layer. Steam, Proton and GPU drivers remain external.

1. Download [TopSpin-DJUltra64-Linux-Installer-v0.3.0.tar.gz](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.3.0/TopSpin-DJUltra64-Linux-Installer-v0.3.0.tar.gz) and extract it into a normal folder, such as Downloads.
2. Open a terminal in the extracted **TopSpin-Installer** folder and run **`./Install-TopSpin.sh`**.
3. In **Top Spin Setup**, choose your own compatible game ISO and a **new installation folder**, then select **Install**. The default destination is `~/Games/Top Spin`; existing folders are never overwritten.
4. When setup finishes, select **Open configurator**, or open **`TopSpinLauncher.sh`** in the installed game folder. Use **`Play-TopSpin.sh`** for later sessions with saved settings.

Setup extracts and patches the game automatically. It leaves the ISO unchanged, requires no administrator access or system Python, and does not start the game automatically. [Linux instructions](docs/linux.md) include the graphical and terminal workflows. The optional [Linux runtime source companion](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.2.1/TopSpin-DJUltra64-Linux-Runtime-Sources-v0.2.1.tar.gz) is unnecessary for installation or play.

## Features

- Corrected **16:9 gameplay camera** and internal rendering up to **4K**, with a separate output resolution. Original menus can remain stretched.
- Original **50 FPS gameplay / 30 FPS replay and cinematic timing**, with synchronization preserved.
- Optional **frame interpolation**: a reversible DXVK/AFMF renderer switch on Windows, and Gamescope/AFMF presentation on Linux. Original simulation timing is preserved.
- English configuration launcher and direct Play shortcut.
- Xbox 360/One/Series, PlayStation 4/5 and Nintendo Switch prompt styles, manual family selection and optional action remapping. Switch's **B/A/Y/X** physical layout is handled separately from Xbox's **A/B/X/Y**.
- **Quit Game** added to the main menu; the game's FPS counter is off by default.
- Local `T`/`U` save folders, integrity checking and an optional Steam shortcut.

Installation defaults are **3840 × 2160 internal / 1920 × 1080 output**, English, Xbox 360 prompts and frame generation off. Change them in the launcher to suit your display and controller. Automatic last-device prompt switching is available as an experimental option; manual styles provide a fixed selection.

To enable Windows interpolation, open **TopSpinLauncher.exe**, select **Frame interpolation** and choose **Save settings** or **Play**. It uses the included DXVK/AFMF component and requires a compatible Vulkan driver. Turn it off to restore the default dgVoodoo2 renderer. See [Windows interpolation](docs/windows-interpolation.md) for requirements and component details. On Linux, enable **Frame generation** in the launcher and save or play to use the included Linux presentation path.

## Your copy of the game

Use the patch with a **legally purchased or otherwise lawfully obtained PC copy of Top Spin** that matches the supported version. You supply the game yourself; no game download, product key or licensing bypass is provided here.

As of **October 20, 2026**, we have not found the original PC release for sale through a current official digital storefront. GOG lists it as a [Dreamlist request](https://www.gog.com/dreamlist/game/top-spin-2003), and it appears on abandonware sites. This describes availability, not permission to download or redistribute the game: the “abandonware” label is not a license. Second-hand physical copies may still be available.

## Compatibility and other platforms

The installers validate known executables and matching game resources as described in the [Windows instructions](docs/windows.md) and [Linux ISO instructions](docs/linux.md). It rejects unsupported versions instead of applying offsets blindly. These supported inputs are not a claim of compatibility with every retail edition. No new CD-key or licensing bypass is implemented.

Windows uses the v0.2.1 patch ZIP; Linux uses the v0.3.0 ISO installer tar.gz. The Linux runtime requires glibc 2.42 or newer; it does not provide compatibility with older Linux ABIs. See [Linux requirements](docs/linux.md) and [the runtime support notes](docs/linux-runtime-support.md).

For component builds and release assembly, see [Building](docs/building.md). For launcher controls, see [the launcher reference](launcher/README.md).

Own work is attributed exclusively to **djultra64**. Third-party authorship and required license notices remain intact. The Windows interpolation integration has its own [MIT license](native/framegen/LICENSE); other project code retains the terms stated in [NOTICE.md](NOTICE.md). Do not redistribute original game files, generated game resources, personal keys or the installer's local backups.
