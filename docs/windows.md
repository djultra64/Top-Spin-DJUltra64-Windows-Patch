# Windows instructions

Own work: **djultra64**.

The public repository contains development source, not a Windows installer or a downloadable complete game. The steps below distinguish source component builds from use of an already assembled private candidate. Start with [Building and research](building.md) for input restrictions and extraction. WSL may be used for extraction/assembly tools; the frozen launcher and game must be checked in native Windows.

## Use an assembled private candidate

Keep the complete folder together in a user-writable location. Do not mix files from different candidates. No system Python is needed when the frozen launcher runtime is included.

| Action | Entry point |
| --- | --- |
| Configure graphics and controls | `TopSpinLauncher.exe` |
| Start with saved settings | `Play-TopSpin.exe` |
| Compatibility direct entry | `Play-TopSpin.cmd` |

Open the configurator, choose settings, then select **Save settings** or **Play**. Render resolution is the internal 16:9 image, up to 3840 × 2160; display resolution is the output size and must suit your screen. The game-specific dgVoodoo2 runtime is required for distinct internal/output sizes. Full screen uses borderless presentation. The corrected gameplay camera is 16:9; original menus may remain stretched.

Keep **Frame generation** disabled. Windows frame generation is not implemented. Original gameplay stays at 50 FPS and replay/cinematic timing at 30 FPS; raising the game's update rate can accelerate simulation.

Select a manual **Controller button style** if automatic prompts do not match your controller. Xbox, PlayStation and Nintendo Switch layouts are distinct. Switch south/east/west/north buttons are **B / A / Y / X**, compared with Xbox **A / B / X / Y**. Optional mappings apply by action to menus and gameplay. **Auto detect (experimental)** attempts last-device prompt switching but still needs real-device visual validation. Hardware checks currently cover only the available Ally controller.

The new Quit Game row has been tested in Linux. Windows shutdown guards have static checks, but a native in-game Quit test remains outstanding. Save compatibility and gameplay checks also remain separate from launcher/integrity checks.

## Build and run launcher source

Install official CPython 3.10 or newer for Windows, including Tcl/Tk. From PowerShell in the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tkinter
.\.venv\Scripts\python.exe -m launcher --game-dir 'C:\path\to\private-candidate' --diagnose
.\.venv\Scripts\python.exe -m launcher --game-dir 'C:\path\to\private-candidate'
```

Close the Tk check window before continuing. `--diagnose` inspects the launch plan without starting the game. A basic extracted candidate can open the configurator, but controller families/remapping need the separately assembled native input/font runtime. Different render/output sizes need the separately staged Windows graphics runtime. Source launcher startup alone does not establish that the full game integration is ready.

For direct launch after saving valid settings:

```powershell
.\.venv\Scripts\python.exe -m launcher --game-dir 'C:\path\to\private-candidate' --play
```

## Build the frozen entry points

Run this on Windows with official CPython/Tk and a fresh work directory:

```powershell
python -m venv build\windows-launcher-venv
.\build\windows-launcher-venv\Scripts\python.exe -m pip install -r native\launcher\requirements-build.txt
.\build\windows-launcher-venv\Scripts\python.exe -m tools.windows_runtime --work build\windows-launcher-build
python -m tools.windows_direct --destination build\Windows-Direct-Entry
```

The configurator output is under `build\windows-launcher-build\dist\TopSpinLauncher`. Keep `TopSpinLauncher.exe` with `runtime-windows-launcher`. The direct entry needs Windows .NET Framework 4. See [the native launcher build guide](../native/launcher/README.md) for staging and self-tests. Building these components does not create a playable game package.

The Windows graphics helper is `tools.windows_graphics.stage_dgvoodoo`; it requires the exact official dgVoodoo2 2.87.5 archive and original redistribution documentation. It copies the unmodified x86 D3D8 component and preserves Dege's notices. There is no general-purpose installer CLI for the complete graphics/executable integration. Do not substitute arbitrary wrapper versions or describe the helper as a validated patch for all retail editions.

## Settings, saves and diagnostics

Launcher settings are in `.portable/launcher.json`; game options/profiles are under local `T` and `U` folders. Preserve them when backing up or moving a candidate. Logs are in `.portable/logs`, and native input initialization status is in `.portable/input-status.txt`.

Use **Check game files for integrity** for missing/changed package files. A frozen launcher also supports `--self-test` and `--verify-files`; see [the native launcher guide](../native/launcher/README.md). Neither mode starts the game or proves gameplay compatibility.

**Add to Steam** saves current settings and registers a shortcut; it may close and reopen Steam normally. After moving the folder, remove the old shortcut and add it again. Keep all source media, generated game resources, keys and complete private packages out of public uploads.
