# Linux / Proton installation and use

Own work: **djultra64**.

**Top Spin Setup** installs the game and patch from your own compatible Top Spin PC ISO. Choose the ISO and a new destination; setup extracts the files, applies the version-checked changes and installs the launcher/runtime automatically. It includes Python/Tk, ISO/CAB extraction tools, Gamescope, video playback and AFMF components. Original game files, keys, Steam, Proton and GPU drivers are not included.

## Requirements

Use **x86-64 Linux with glibc 2.42 or newer**, working Vulkan graphics drivers, X11/Xwayland and an existing Steam installation with **Proton 11**. The bundled libraries retain this glibc requirement; another Proton version cannot lower it. See [runtime support](linux-runtime-support.md).

Check your architecture and glibc:

```sh
uname -m
getconf GNU_LIBC_VERSION
```

The results must identify `x86_64` and glibc 2.42 or newer. A compatible GPU driver is also required. Choose a user-writable location on a filesystem that supports executable permissions, with at least 8 GiB free for extraction, temporary copies, the runtime and local backup. The completed installation uses less space.

Use your own lawfully obtained ISO of the supported PC version. The ISO must provide the supported source executable with SHA-256 `0bb3090d37956daa625faf917854c84f0263f4472c9235abf1f4c0d68721fe79` and matching game resources; it rejects unsupported media instead of patching unknown files. It does not run the ISO's autorun/MSI installer, mount the ISO, require root access or add a licensing bypass.

## Download and open setup

1. Download [TopSpin-DJUltra64-Linux-Installer-v0.3.0.tar.gz](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.3.0/TopSpin-DJUltra64-Linux-Installer-v0.3.0.tar.gz).
2. Extract it into a normal folder such as Downloads. **Keep this installer folder separate from the new game destination.**
3. Open a terminal in the extracted `TopSpin-Installer` folder and run `./Install-TopSpin.sh`.
4. In **Top Spin Setup**, select **Browse…** beside **Game ISO** and choose your ISO.
5. Select a **new Install location**, then choose **Install**.

For example:

```sh
tar -xzf /path/to/TopSpin-DJUltra64-Linux-Installer-v0.3.0.tar.gz -C "$HOME/Downloads"
cd "$HOME/Downloads/TopSpin-Installer"
./Install-TopSpin.sh
```

The default destination is `~/Games/Top Spin`. The location browser selects an existing parent and appends `Top Spin`; type a different new folder if desired. Existing destinations, including empty folders, are rejected rather than overwritten. Setup can create missing parent folders for a new destination.

The progress message and **Details** log show what setup is doing. **Cancel** requests cancellation and waits for temporary staging cleanup. Closing an active setup offers cancellation and waits for that cleanup as well. Your original ISO remains unchanged.

On success, **Open configurator** opens the installed launcher, **Open game folder** opens the destination, and **Done** closes setup. Nothing starts the game automatically. No system Python, manual CAB extraction or separate runtime staging is needed.

## Terminal installation

The same entry point works without a graphical display when both paths are supplied:

```sh
./Install-TopSpin.sh --iso '/path/to/Top Spin.iso' --destination "$HOME/Games/Top Spin"
```

It prints progress and returns a nonzero exit code on failure. The destination must be new. Source developers can use `python -m launcher.installer --iso PATH --destination PATH --payload PATH` with the corresponding staged payload.

The optional [TopSpin-DJUltra64-Linux-Runtime-Sources-v0.2.1.tar.gz](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.2.1/TopSpin-DJUltra64-Linux-Runtime-Sources-v0.2.1.tar.gz) companion provides corresponding runtime dependency source and is unnecessary for installation/play. Runtime notices remain under `runtime/linux/licenses` and `licenses/linux-runtime`; installer dependency notices and source inputs are under `licenses/linux-installer` in the installer payload.

## Configure and play

From the installed game folder, configure with:

```sh
./TopSpinLauncher.sh
```

Choose settings, then select **Save settings** or **Play**. For later sessions, launch directly with saved settings:

```sh
./Play-TopSpin.sh
```

Fresh installation defaults are **3840 × 2160 render / 1920 × 1080 output**, English, Xbox 360 prompts and frame generation off. The launcher discovers `Proton 11.0` or `Proton - Experimental` in known Steam locations. If discovery fails, **Browse** selects the folder containing the `proton` script. `TOPSPIN_PROTON_DIR` provides a manual override, and `STEAM_ROOT` identifies a nonstandard Steam installation.

Render resolution selects the internal 16:9 image up to 3840 × 2160; display resolution selects Gamescope's output size. Choose an output your screen supports and lower the render size if needed. Gameplay camera geometry is corrected for 16:9; original menus can stretch.

Original timing remains **50 FPS gameplay / 30 FPS replays and cinematics**. Enable **Frame generation** and save/play to add intermediate presentation frames through Gamescope and the bundled Linux AFMF Vulkan layer. This does not raise the simulation limit. Clear the option for the non-interpolated path. The Windows DLL port is separate; do not substitute its files for the Linux layer.

Manual **Controller button style** choices cover Keyboard, Xbox, PlayStation and Nintendo Switch. Optional action mappings apply to menus and gameplay. Switch south/east/west/north positions are **B / A / Y / X**, compared with Xbox **A / B / X / Y**. **Auto detect (experimental)** follows the last active device where available; manual selection provides a fixed family when detection is ambiguous. The main menu includes **Quit Game** and the game's FPS counter is off by default.

## Saves, backups and Steam

Preserve `.portable/launcher.json` and local `T`/`U` save folders when backing up or moving the game. Proton state is under `.portable/proton`; logs are under `.portable/logs`. Runtime overrides apply to the child game process.

The installed patch keeps replaced original game files under `.portable/backups/topspin-patch-v1` with receipt `.portable/patch-install.json`. These are private game content and configuration; do not upload them. The ISO setup creates a fresh installation rather than upgrading an existing game directory. Keep separate game copies when using both Windows and Linux.

**Check game files for integrity** checks immutable package hashes; settings and saves are excluded. **Add to Steam** saves settings and may close/reopen Steam normally while adding the shortcut. Leave Steam's forced compatibility tool disabled because the launcher selects Proton. After moving the folder, remove the old shortcut and add it again.

## Troubleshooting

An ABI error means this installer/runtime needs a supported newer host or a separate dependency build for your distribution. The setup script checks the ABI before loading bundled Python. For missing Proton, install Proton 11 through Steam or select its directory in the launcher.

If the destination already exists, select a different new folder. For unsupported media, retain your original ISO and inspect the reported version/hash error rather than disabling checks. If the payload is missing or damaged, extract the complete installer archive again.

If a script reports permission denied, check that the filesystem supports execution and preserves executable permissions. Launch the graphical installer from a terminal to see startup errors; use the terminal installation command when no graphical display is available. Restore the full coherent runtime rather than mixing individual video libraries.

When reporting an issue, share error text and relevant hashes rather than the ISO, original game files, generated resources, personal configuration or keys. Source/runtime development instructions are in [Building](building.md).
