# Build the patch and components

Own work: **djultra64**.

For normal Windows installation, use [the release instructions](windows.md). This page covers source development and assembly of the public patch ZIP. A public patch archive contains project source and redistributable runtime components; complete extracted/portable game packages remain private.

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
python -m tools.build_patch_release dist/TopSpin-DJUltra64-Windows-Patch-v0.2.0.zip --reviewed-binaries /path/to/reviewed-binaries.json --original-inventory /path/to/private-source-inventory.json
```

Choose a fresh output path. The builder checks hashes, path safety, allowed destinations, required component roles, upstream notices and known original-game hashes. It rejects original game content and private game-data file types. Preserve the original-file inventory privately; do not publish it with the release.

The archive's root contains `Install-Patch.cmd` and `.topspin-patch`. The payload includes launcher/input/graphics runtimes, project source, notices, patch stubs and compatible Lua/Python tooling. It contains no prepatched `TopSpin.exe`, game menu archives, generated game fonts or key. The installer generates those changes locally from the user's compatible files.

`tools.install_patch` validates and plans the full change set before game writes. It preserves replaced originals under `.portable/backups/topspin-patch-v1`, creates an installation receipt and rolls back replaced files if an ordinary installation error occurs. A matching receipt allows recognition of an intact installation. It refuses an unknown executable, unsupported resources, corrupted payload or conflicting backup. Upgrades preserve settings and game resources, stage changed runtime files, and retain the previous receipt with replaced files under `.portable/backups/topspin-patch-updates/<payload-sha256>`. The builder requires the interpolation component to be complete when any part of it is supplied.

For a developer validation without changing game files, use a complete staged payload:

```sh
python -m tools.install_patch --game-dir /path/to/compatible-private-game --payload /path/to/staged/.topspin-patch --check
```

The Lua compiler in the Windows release is a Windows executable; this command needs an environment that can execute that compiler. The Windows command entry point supplies the bundled interpreter automatically. `--check` still performs resource compilation in temporary storage.

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

This older research path extracts a full private game, applies the basic compatibility settings and stages launcher source. It does not perform the complete public Windows install pipeline. Preparation rewrites its destination's executable/configuration; use a new candidate rather than your installed game or save-bearing package.

`tools.package_portable` copies a complete assembled candidate into a private package. That output contains game files and may contain personal configuration; it is not the public release ZIP and must not be uploaded.

Linux runtime assembly is described in [the Linux guide](linux.md). It uses a separate coherent dependency stack, with glibc 2.42 as the current runtime floor.

## Tests

```sh
python -m unittest discover -s tests
```

Some integration tests require private version-locked media, compiler tools or staged dependencies. Keep those fixtures local. Do not infer availability of those fixtures from the public source checkout.
