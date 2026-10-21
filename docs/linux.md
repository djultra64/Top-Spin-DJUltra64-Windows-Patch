# Linux and Proton instructions

Own work: **djultra64**.

Linux is a development path alongside the Windows patch. This repository does not provide a complete portable game or a universally reproducible Linux runtime build. Read [Building and research](building.md) before extracting your own media. The validated private candidate contains additional components beyond the initial preparation command.

## Current runtime requirements

The current assembled bundle targets **x86-64 Linux with glibc 2.42 or newer**, working Vulkan drivers and X11/Xwayland. Its development baseline is Fedora 43/Bazzite. A version check is not proof of support for every distribution. An existing Steam installation with **Proton 11** is required; Steam and Proton are not included.

This bundle is not established as compatible with older distributions or Steam Deck's default OS. Bundling Fedora-built libraries inside an older Steam Linux Runtime does not lower their glibc requirements. A broader release requires rebuilding and testing the complete Python/Tk, compositor and media stack. See [Linux runtime support](linux-runtime-support.md).

Check the host before loading the bundled interpreter:

```sh
getconf GNU_LIBC_VERSION
sh tools/check_linux_runtime.sh
```

Run the second command from the repository root. A fully assembled candidate carries the equivalent guard at `runtime/linux/check-abi.sh`. Compatible system Vulkan drivers remain required even if the guard succeeds.

## Use an assembled private candidate

Extract or copy the entire private folder into a user-writable location. Keep its runtime subfolders together. From that folder:

```sh
./TopSpinLauncher.sh
```

Choose render/output resolution, full screen and controller style, then select **Save settings** or **Play**. The launcher discovers `Proton 11.0` and falls back to `Proton - Experimental` in known Steam locations. Proton Experimental can change independently; its discovery is not validation of every future version. If discovery fails, **Browse** lets you choose the folder containing the `proton` script. `TOPSPIN_PROTON_DIR` is also available as a manual override, and `STEAM_ROOT` can identify a nonstandard Steam installation.

After saving settings, start directly with:

```sh
./Play-TopSpin.sh
```

The assembled candidate includes its Python/Tk runtime; a separate system Python is unnecessary. For source development with a valid candidate, use the virtual environment described in [Building](building.md):

```sh
python -m launcher --game-dir /path/to/private-candidate --diagnose
python -m launcher --game-dir /path/to/private-candidate
python -m launcher --game-dir /path/to/private-candidate --play
```

`--diagnose` does not start the game. The Linux launch planner requires the staged video runtime even with frame generation off; bare Proton plus the early extracted candidate is insufficient. In particular, a missing/incoherent WMV stack can produce color bars instead of menu video.

## Graphics and input

Render resolution selects the internal 16:9 image, up to 3840 × 2160; display resolution selects the output size. Gamescope supplies separate internal/output presentation in the assembled candidate. Gameplay camera geometry is corrected; original menus may stretch.

Original timing remains **50 FPS gameplay / 30 FPS replays and cinematics**. The tested Linux frame-generation path adds presentation frames through Gamescope and the AFMF Vulkan layer without changing that simulation limit. It requires the complete graphics runtime and suitable GPU/driver support; it is not native game uncapping.

Use a manual **Controller button style** when detection is ambiguous. Xbox, PlayStation and Nintendo Switch have separate layouts and glyphs. Switch south/east/west/north positions are **B / A / Y / X**; Xbox uses **A / B / X / Y**. Optional action bindings apply to menus and gameplay. **Auto detect (experimental)** attempts last-device switching; its visible prompts still need real-device validation. Manual Xbox 360 menu prompts were visually checked; hardware testing is limited to the available Ally controller.

The Quit Game menu row and disabled game FPS counter have been tested in the Linux candidate. The full state of gameplay/save/platform checks is recorded in [runtime validation](../reports/runtime-validation.md).

## Runtime staging for developers

`tools.linux_runtime` is a host-specific staging helper, not a portable dependency downloader. It expects an RPM-based development host with `/usr/lib64`, Gamescope, Xwayland, GStreamer core/WMV plugins, XKB data, `ldd`, `readelf`, and `rpm`. It also requires a separately built 64-bit AFMF layer and its original notices, plus the Proton-compatible older bzip2 SONAME input used by the video stack. Those build inputs are not supplied by the public repository.

With those dependencies deliberately prepared, stage only into a **new private candidate**, never over an active game/runtime:

```sh
python -m tools.linux_runtime /path/to/new-private-candidate --afmf /path/to/built/afmf-layer --video-profile all
```

The helper currently also looks for `build/deps/video64/libbz2.so.1.0` and AFMF notices under `build/third-party/afmf-linux/unpacked/afmf-linux-1.3.1`. Prepare coherent dependencies and retain their upstream licenses; missing inputs should stop staging. The optional `--video-profile wmv` reduction has standalone decoding checks but is not the default fully integrated profile. Staging graphics does not create the separate Python/Tk bundle or install the input hook/prompt fonts.

## Saves, Steam and troubleshooting

Keep `.portable/launcher.json` and the local `T`/`U` save folders when moving or backing up the candidate. Proton state is under `.portable/proton`; logs are under `.portable/logs`. The launcher scopes runtime environment overrides to its child game rather than changing system-wide libraries.

**Check game files for integrity** checks package hashes without running the game. **Add to Steam** saves settings and may close/reopen Steam normally while writing the shortcut. Leave Steam's forced compatibility tool disabled for that shortcut: the launcher already selects Proton. After moving the folder, remove the old shortcut and add it again. Flatpak Steam execution has not been validated.

If startup fails, check the ABI guard, Vulkan driver, discovered Proton location and missing-file diagnostics before changing anything. An intact hash manifest is not evidence of correct game timing, complete video playback or save compatibility. Keep original media, generated fonts, keys and full private packages out of public Git history and releases.
