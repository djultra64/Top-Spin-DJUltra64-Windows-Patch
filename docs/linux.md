# Linux and Proton

Own work: **djultra64**.

The v0.2.0 Windows ZIP includes a Windows interpolation component and uses a Windows installer/runtime. It is **not a native Linux drop-in patch**. Linux currently uses the source tools and a separately assembled runtime; no Linux binary release is supplied here. See [Building](building.md) for input compatibility and the source workflow.

## Runtime requirements

The current Linux runtime targets **x86-64 Linux with glibc 2.42 or newer**, Vulkan and X11/Xwayland. Steam with **Proton 11** is required separately. The runtime's ABI floor applies to its bundled libraries and Python/Tk; placing them inside an older Steam Linux Runtime does not lower it. See [Linux runtime support](linux-runtime-support.md) for the dependency design.

Check the host from the repository root:

```sh
getconf GNU_LIBC_VERSION
sh tools/check_linux_runtime.sh
```

A complete Linux candidate carries the equivalent guard at `runtime/linux/check-abi.sh`. Supply compatible Vulkan drivers from your operating system.

## Launch a complete Linux candidate

Keep the entire assembled folder together in a user-writable location. Configure with:

```sh
./TopSpinLauncher.sh
```

Choose graphics and controller settings, then select **Save settings** or **Play**. For later sessions, start directly with saved settings:

```sh
./Play-TopSpin.sh
```

The launcher discovers `Proton 11.0` or `Proton - Experimental` in known Steam locations. If needed, **Browse** selects the folder containing the `proton` script. `TOPSPIN_PROTON_DIR` provides a manual override and `STEAM_ROOT` identifies a nonstandard Steam installation.

A complete candidate includes its Python/Tk runtime. For source development, install the dependencies in [Building](building.md) and use:

```sh
python -m launcher --game-dir /path/to/private-candidate --diagnose
python -m launcher --game-dir /path/to/private-candidate
python -m launcher --game-dir /path/to/private-candidate --play
```

`--diagnose` checks the launch plan without starting the game. Linux requires the staged video runtime even with frame generation off; bare Proton plus an extracted game folder does not provide the complete integration.

## Graphics and input

Render resolution selects the internal 16:9 image up to 3840 × 2160; display resolution selects the output size. Gamescope supplies separate internal/output presentation. The gameplay camera is corrected for 16:9, while original menus can stretch.

Original timing remains **50 FPS gameplay / 30 FPS replays and cinematics**. The Linux frame-generation path uses Gamescope and the Linux AFMF Vulkan layer to add presentation frames without raising the simulation limit. The Windows port in v0.2.0 is a separate component; do not substitute its DLLs for the Linux layer. It requires the complete graphics runtime and suitable GPU/driver support.

Manual **Controller button style** choices cover Xbox, PlayStation and Nintendo Switch. Optional action mappings apply to menus and gameplay. Switch south/east/west/north positions are **B / A / Y / X**, compared with Xbox **A / B / X / Y**. **Auto detect (experimental)** follows the last active device where available; manual selection provides a fixed family when detection is ambiguous.

## Stage the Linux runtime from source

`tools.linux_runtime` is a host-specific staging helper. It expects an RPM-based host with `/usr/lib64`, Gamescope, Xwayland, GStreamer core/WMV plugins, XKB data, `ldd`, `readelf` and `rpm`. It also needs a separately built 64-bit AFMF layer, its upstream notices and the Proton-compatible older bzip2 SONAME used by the video stack.

After preparing those dependencies, stage into a **new candidate**, never over an active game/runtime:

```sh
python -m tools.linux_runtime /path/to/new-private-candidate --afmf /path/to/built/afmf-layer --video-profile all
```

The helper also expects `build/deps/video64/libbz2.so.1.0` and AFMF notices under `build/third-party/afmf-linux/unpacked/afmf-linux-1.3.1`. `--video-profile wmv` selects a smaller WMV-focused plugin set. This operation does not build the separate Python/Tk bundle or install input hooks and generated prompt fonts.

## Saves and Steam

Preserve `.portable/launcher.json` and local `T`/`U` save folders when backing up or moving the game. Proton state is under `.portable/proton`; logs are under `.portable/logs`. Runtime environment overrides apply to the child game process.

**Check game files for integrity** checks package hashes. **Add to Steam** saves settings and may close/reopen Steam normally while adding the shortcut. Leave Steam's forced compatibility tool disabled: the launcher selects Proton itself. After moving the folder, remove the old shortcut and add it again.

Keep your original media, generated fonts, keys, backups and complete game packages out of public uploads. The public patch is separate from your private game installation.
