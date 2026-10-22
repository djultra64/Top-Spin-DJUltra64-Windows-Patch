# Build the patch and components

Own work: **djultra64**.

For normal installation, use the [Windows](windows.md) or [Linux / Proton](linux.md) release instructions. This page covers source development and assembly of the public platform archives. A public patch archive contains project source and redistributable runtime components; complete extracted/portable game packages remain private.

## Development requirements

Use Python 3.10 or newer with the packages in `requirements.txt`. Source GUI use needs Tcl/Tk. Linux/WSL extraction and assembly need `cabextract` and GNU binutils (`as`, `objcopy`); native input compilation also needs GCC with `-m32` support and a linker supporting `i386pe`. Freeze the Windows launcher on Windows with official CPython/Tk. The release installer bundles its own CPython 3.14 runtime, Pillow and compatible Lua compiler. A Windows runtime executed under Wine can also run the launcher build tool; keep the Windows Python executable and build dependencies inside that Wine environment rather than using Linux PyInstaller to produce a Windows executable.

Run source commands from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

The compatible executable hashes are listed in [Windows instructions](windows.md). Font and menu transformations also check exact input hashes. Do not remove those guards to force an unknown edition through the tools. Input provenance and a clean original-media baseline are separate from matching a known development hash.

## Public Windows release assembly

`tools.build_patch_release` builds the ZIP from an explicit reviewed binary manifest and a private original-file inventory. It does not scan private build folders for arbitrary files. The manifest identifies each component's source, allowlisted destination, SHA-256 and required notice files; portability stubs and the compatible Lua compiler have explicit build roles.

```sh
python -m tools.build_patch_release --help
python -m tools.build_patch_release dist/TopSpin-DJUltra64-Windows-Patch-v0.2.1.zip --reviewed-binaries /path/to/reviewed-binaries.json --original-inventory /path/to/private-source-inventory.json
```

Choose a fresh output path. The builder checks hashes, path safety, allowed destinations, required component roles, upstream notices and known original-game hashes. It rejects original game content and private game-data file types. Preserve the original-file inventory privately; do not publish it with the release.

The archive's root contains `Install-Patch.cmd` and `.topspin-patch`. The payload includes launcher/input/graphics runtimes, project source, notices, patch stubs and compatible Lua/Python tooling. It contains no prepatched `TopSpin.exe`, game menu archives, generated game fonts or key. The installer generates those changes locally from the user's compatible files.

`tools.install_patch` validates and plans the full change set before game writes. It preserves replaced originals under `.portable/backups/topspin-patch-v1`, creates an installation receipt and rolls back replaced files if an ordinary installation error occurs. A matching receipt allows recognition of an intact installation. It refuses an unknown executable, unsupported resources, corrupted payload or conflicting backup. Upgrades preserve settings and game resources, stage changed runtime files, and retain the previous receipt with replaced files under `.portable/backups/topspin-patch-updates/<payload-sha256>`. The builder requires the interpolation component to be complete when any part of it is supplied.

For a developer validation without changing game files, use a complete staged payload:

```sh
python -m tools.install_patch --game-dir /path/to/compatible-private-game --payload /path/to/staged/.topspin-patch --check
```

The Lua compiler in the Windows release is a Windows executable; this command needs an environment that can execute that compiler. The Windows command entry point supplies the bundled interpreter automatically. `--check` still performs resource compilation in temporary storage.

## Public Linux / Proton release assembly

The ISO-based setup archive uses a reviewed manifest with `"platform": "linux"` and `"install_mode": "iso"`. Supply the reviewed Python/Tk, Gamescope, matching `gamescopereaper`, host-dialog wrapper, Xwayland, video, AFMF, Lua and controller runtimes, plus pinned PyCdlib 1.22.0 and the executable `runtime/linux/bin/cabextract`. Steam, Proton and GPU drivers remain external.

```sh
python -m tools.build_patch_release dist/TopSpin-DJUltra64-Linux-Installer-v0.3.2.tar.gz --reviewed-binaries /path/to/reviewed-linux-iso-binaries.json --original-inventory /path/to/private-source-inventory.json
```

Choose a fresh archive destination. The archive contains `TopSpin-Installer/Install-TopSpin.sh` and its `.topspin-patch` payload. The shell runs its ABI preflight before loading the bundled Python/Tk. Without arguments, `launcher.installer` opens setup; `--iso PATH --destination PATH` runs the same operation without a graphical display.

`tools.iso_install` reads the image without mounts or executing its autorun/MSI. It locates the game database, copies only its declared cabinets and loose files, reconstructs the private game with `tools.build_portable`, then applies the existing Linux patch and verifies the result. Cabinet filenames, identifiers and lengths are checked before decompression. Extraction and temporary copies use the destination filesystem. The completed folder is published with atomic no-replace semantics; existing destinations and unrelated files are preserved.

The runtime source companion below supplies the corresponding third-party graphics/media sources. The project-owned Gamescope and host-dialog wrappers remain in the payload source. The setup archive additionally contains PyCdlib source and the exact cabextract source RPM under `licenses/linux-installer/sources`, with upstream notices and SHA-256 provenance. No original executable, MSI, cabinet, game resource, key, ISO or private backup may enter the public archive.

For the previous patch-in-place format, omit `install_mode` from the reviewed Linux manifest. The builder then emits the legacy root `Install-Patch.sh` and `.topspin-patch` layout. Windows output remains separate and unchanged.

To reproduce the Linux graphics runtime inputs, `tools.linux_runtime` expects an RPM-based host with `/usr/lib64`, Gamescope, Xwayland, GStreamer core/WMV plugins, XKB data, `ldd`, `readelf` and `rpm`, plus a separately built 64-bit Linux AFMF layer and its notices. Pass the `gamescopereaper` produced by the same compositor build, then stage into a new private candidate:

For a custom compositor, build both `src/gamescope` and `src/gamescopereaper` from the same pinned Gamescope checkout and configured SDK build. This release uses commit `c31743d9da2f788faad3b9e202a10bf6f49c75d9` and the user-installed `org.freedesktop.Sdk/x86_64/25.08` SDK, version 25.08.17; the exact SDK commit and build options are recorded in the runtime provenance. For an already configured `sdk-build` directory:

```sh
flatpak --user run --command=sh --filesystem=/path/to/gamescope-source org.freedesktop.Sdk/x86_64/25.08 -c 'ninja -C /path/to/gamescope-source/sdk-build src/gamescope src/gamescopereaper'
```

Use the stripped, build-RPATH-free installed binaries from that build. The staging helper initially reads the compositor from `/usr/bin/gamescope`; when supplying a custom build, replace the staged `gamescope.bin` with its reviewed, sanitized compositor binary in the same release inventory. `--reaper` selects only its matching helper, not the compositor itself. Never let the wrapper resolve a different system `gamescopereaper` through the host PATH.

```sh
python -m tools.linux_runtime /path/to/new-private-candidate --afmf /path/to/built/afmf-layer --video-profile all --reaper /path/to/matching/gamescopereaper
```

The helper also needs `build/deps/video64/libbz2.so.1.0` and AFMF notices under `build/third-party/afmf-linux/unpacked/afmf-linux-1.3.1`. The release uses the coherent `all` video profile, not the reduced `wmv` development option. This staging command does not build the separate Python/Tk bundle or install executable hooks and generated game fonts; the reviewed release inventory must include the complete dependency set. See [runtime support](linux-runtime-support.md) for the glibc 2.42 ABI floor.

The release also publishes [TopSpin-DJUltra64-Linux-Runtime-Sources-v0.2.1.tar.gz](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.2.1/TopSpin-DJUltra64-Linux-Runtime-Sources-v0.2.1.tar.gz) with corresponding Linux runtime dependency source. It is separate from the binary patch and unnecessary for normal installation. Preserve complete component notices under `runtime/linux/licenses` and `licenses/linux-runtime`.

The v0.3.2 launch planner scopes `DISABLE_GAMESCOPE_WSI=1` to its nested Gamescope and Proton child, selecting ordinary X11/Xwayland presentation to avoid inherited FROG surface-hook conflicts. It does not change the host compositor/global environment or disable the independent AFMF layer.

The Linux v0.3.1 launcher includes only the SteamGridDB URL/hash/dimension manifest, not the artwork images. Its explicit **Add to Steam** action downloads missing/corrupt images, validates them before cache writes, and preserves valid local artwork. Keep this runtime download separate from public archive assembly. Windows v0.2.1 frozen launcher binaries are unchanged by these source/Linux updates.

## Build Windows launcher components

On Windows, with official CPython including Tcl/Tk:

```powershell
python -m venv build\windows-launcher-venv
.\build\windows-launcher-venv\Scripts\python.exe -m pip install -r native\launcher\requirements-build.txt
.\build\windows-launcher-venv\Scripts\python.exe -m tools.windows_runtime --work build\windows-launcher-build
python -m tools.windows_direct --destination build\Windows-Direct-Entry
```

Keep the resulting `TopSpinLauncher.exe` with its `runtime-windows-launcher` directory. The direct Play entry requires .NET Framework 4. See [the native launcher guide](../native/launcher/README.md) for staging and diagnostic commands.

The game-specific graphics helper, `tools.windows_graphics.stage_dgvoodoo`, accepts the exact official dgVoodoo2 2.87.5 archive and original redistribution documentation. It copies the unmodified x86 D3D8 component with Dege's notices. The optional interpolation path instead uses the pinned DXVK 2.7.1 x32 D3D8/D3D9 components and the project's Windows AFMF port. See [Windows interpolation](windows-interpolation.md) for the full cross-build command, pinned inputs, synthetic checks and license details.

## Other source components

Build the project's freestanding PE32 input DLL with:

```sh
python -m tools.native_input build/native-input
```

This builds only the owned DLL. The release assembly separately includes SDL3, the executable loading stub, controller assets and font-generation source. Generated game font/archive outputs belong only in the user's game folder.

The Quit Game delta needs Lua 5.0.3 with the game's bytecode format. The format patch is in `patches/lua50-topspin-format.patch`. To generate a separate local menu output:

```sh
python -m tools.menu_quit /path/to/original/MainMenu.rui /path/to/private-output/MainMenu.rui --lua /path/to/compatible/lua
```

The delta checks the original archive/chunks and preserves original menu animation. The installer combines it with font changes automatically.

## Private extraction and research workflow

The extraction tools expect a local media layout containing `TopSpin.msi`, its external cabinets and loose files, including `program files/Atari/TopSpin/TopSpin.exe` and `Config.pml`. A lone installed executable is insufficient. Use your own media and a fresh output:

```sh
mkdir -p reports
python -m tools.build_portable --source /path/to/local-media --destination dist/Research-Candidate
python -m tools.prepare_portable --source /path/to/local-media --destination dist/Research-Candidate --width 1920 --height 1080
python -m tools.verify_build --destination dist/Research-Candidate --inventory reports/source-inventory.json
```

This older research path extracts a full private game, applies the basic compatibility settings and stages launcher source. It does not perform the complete public platform install pipeline. Preparation rewrites its destination's executable/configuration; use a new candidate rather than your installed game or save-bearing package.

`tools.package_portable` copies a complete assembled candidate into a private package. That output contains game files and may contain personal configuration; it is not the public release ZIP and must not be uploaded.

The Linux release uses a separate coherent dependency stack, with glibc 2.42 as its runtime floor. The downloadable archive already contains it; end users do not need to run the staging tools.

## Tests

```sh
python -m unittest discover -s tests
```

Some integration tests require private version-locked media, compiler tools or staged dependencies. Keep those fixtures local. Do not infer availability of those fixtures from the public source checkout.

The reviewed Gamescope build removes its build-only RPATH using the Meson install helper. Before public staging, run `python -m tools.sanitize_linux_gamescope /path/to/staged/gamescope.bin` to normalize the two remaining embedded build-path constants without changing ELF offsets. The wrapper sets the installed script directory explicitly. The sanitizer rejects an active RPATH and records before/after hashes for provenance.
