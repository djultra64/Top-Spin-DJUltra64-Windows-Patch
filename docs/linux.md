# Linux / Proton installation and use

Own work: **djultra64**.

The Linux/Proton archive installs the patch into your own compatible Top Spin PC game folder. It includes project code and redistributable Python/Tk, Gamescope, video and AFMF components. **Original game files, assets, keys, Steam, Proton and GPU drivers are not included.** You do not need to install system Python or assemble the runtime yourself.

## Requirements

Use **x86-64 Linux with glibc 2.42 or newer**, working Vulkan graphics drivers, X11/Xwayland and an existing Steam installation with **Proton 11**. The bundled libraries retain this glibc requirement; an older distribution cannot run them merely by choosing another Proton version. See [runtime support](linux-runtime-support.md).

Check your architecture and glibc before downloading:

```sh
uname -m
getconf GNU_LIBC_VERSION
```

The results must identify `x86_64` and glibc 2.42 or newer. A compatible GPU driver is also required. Keep the game in a folder your account can write to, on a filesystem that supports executable permissions. Close the game and launcher before installing.

The installer accepts the supported source executable (`0bb3090d37956daa625faf917854c84f0263f4472c9235abf1f4c0d68721fe79`) or the earlier Linux assembled executable (`ae971be61f8ba0c1c7a21f8ed1a51f5725e26d10d5a3813ef2f199354b7eef97`), with matching menu/font resource variants. The Windows assembled executable and graphics runtime belong in a separate Windows installation. Unknown versions are rejected before game writes. Use your own lawfully obtained game; this patch does not add a key or licensing bypass.

## Download and install

1. Download [TopSpin-DJUltra64-Linux-Proton-Patch-v0.2.1.tar.gz](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.2.1/TopSpin-DJUltra64-Linux-Proton-Patch-v0.2.1.tar.gz) from [the v0.2.1 release](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/tag/v0.2.1).
2. Extract it directly into the folder containing `TopSpin.exe`, keeping its file permissions.
3. Open a terminal in that game folder and run `sh ./Install-Patch.sh`.
4. After installation succeeds, run `./TopSpinLauncher.sh` to configure, or `./Play-TopSpin.sh` to start with saved settings.

For example, replace the paths below with your download and game locations:

```sh
tar -xzf /path/to/TopSpin-DJUltra64-Linux-Proton-Patch-v0.2.1.tar.gz -C '/path/to/Top Spin'
cd '/path/to/Top Spin'
sh ./Install-Patch.sh
./TopSpinLauncher.sh
```

The optional [TopSpin-DJUltra64-Linux-Runtime-Sources-v0.2.1.tar.gz](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.2.1/TopSpin-DJUltra64-Linux-Runtime-Sources-v0.2.1.tar.gz) companion provides corresponding runtime dependency source. It is not needed to install or play. Dependency notices are included under `runtime/linux/licenses` and `licenses/linux-runtime`.

The archive root contains `Install-Patch.sh` and `.topspin-patch`; both belong beside `TopSpin.exe`, `Config.pml` and `Media`. Extraction only stages patch files. The installer validates the executable, game resources and payload, generates changes locally and keeps replaced originals under `.portable/backups/topspin-patch-v1`. The receipt is `.portable/patch-install.json`.

Keep the original backup and receipt. Reinstalling an intact payload is recognized; later Linux payload upgrades retain replaced components and the previous receipt under `.portable/backups/topspin-patch-updates/<payload-sha256>`. Settings, controls, game resources and saves are preserved during supported upgrades. Cross-platform upgrades are rejected: keep separate Windows and Linux game copies when using both.

## Configure and play

Choose settings, then select **Save settings** or **Play**. For later sessions:

```sh
./Play-TopSpin.sh
```

Fresh installation defaults are **3840 × 2160 render / 1920 × 1080 output**, English, Xbox 360 prompts and frame generation off. The launcher discovers `Proton 11.0` or `Proton - Experimental` in known Steam locations. If discovery fails, **Browse** selects the folder containing the `proton` script. `TOPSPIN_PROTON_DIR` provides a manual override, and `STEAM_ROOT` identifies a nonstandard Steam installation.

Render resolution selects the internal 16:9 image up to 3840 × 2160; display resolution selects Gamescope's output size. Choose an output your screen supports and lower the render size if needed. Gameplay camera geometry is corrected for 16:9; original menus can stretch.

Original timing remains **50 FPS gameplay / 30 FPS replays and cinematics**. Enable **Frame generation** and save/play to add intermediate presentation frames through Gamescope and the bundled Linux AFMF Vulkan layer. This does not raise the game simulation limit. Clear the option to use the non-interpolated presentation path. The Windows DLL port is separate; do not substitute its files for the Linux layer.

Manual **Controller button style** choices cover Keyboard, Xbox, PlayStation and Nintendo Switch. Optional action mappings apply to menus and gameplay. Switch south/east/west/north positions are **B / A / Y / X**, compared with Xbox **A / B / X / Y**. **Auto detect (experimental)** follows the last active device where available; manual selection provides a fixed family when detection is ambiguous. The main menu includes **Quit Game** and the game's FPS counter is off by default.

## Saves, integrity and Steam

Preserve `.portable/launcher.json` and local `T`/`U` save folders when backing up or moving the game. Proton state is under `.portable/proton`; logs are under `.portable/logs`. Runtime environment overrides apply to the child game process.

**Check game files for integrity** checks immutable package hashes; settings and saves are excluded. **Add to Steam** saves settings and may close/reopen Steam normally while adding the shortcut. Leave Steam's forced compatibility tool disabled because the launcher selects Proton. After moving the folder, remove the old shortcut and add it again.

## Troubleshooting

An ABI error means this bundle needs a newer supported host or a separate dependency build for your distribution. A different Proton version cannot lower the bundled libraries' glibc requirement. The install script runs the ABI preflight before loading its private Python runtime.

For missing Proton, install Proton 11 through Steam or select its directory in the launcher. For missing/corrupted payload files, extract the complete Linux archive again. If a script reports permission denied, check that the game filesystem supports execution and retains executable permissions; invoke the installed launcher with `bash ./TopSpinLauncher.sh` if necessary. Missing video/runtime files require restoring the full coherent runtime, including its video plugins, rather than mixing individual libraries.

Keep any private backup, receipt and `.portable/install.lock` after an interrupted installation; they contain recovery information. There is no automatic uninstall command. When reporting an issue, share error text and relevant hashes rather than original files, generated resources, personal configuration or keys.

Developers can find runtime staging and archive assembly instructions in [Building](building.md). Those steps are not required to use the downloadable patch.
