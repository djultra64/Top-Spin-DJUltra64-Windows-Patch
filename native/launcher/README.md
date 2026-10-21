# Frozen Windows launcher

Own integration: **djultra64**. The build contains project launcher code, CPython,
Tcl/Tk and their required dependencies. It does not include a game executable,
game data, CD keys, or protection changes.

Build on Windows with an official CPython installation that includes Tcl/Tk:

```powershell
python -m venv build\windows-launcher-venv
build\windows-launcher-venv\Scripts\python.exe -m pip install -r native\launcher\requirements-build.txt
build\windows-launcher-venv\Scripts\python.exe -m tools.windows_runtime --work build\windows-launcher-build
```

Use a fresh build directory. The result is
`build\windows-launcher-build\dist\TopSpinLauncher`. The executable is
`TopSpinLauncher.exe`; its private dependencies are in
`runtime-windows-launcher`. Keep both together. The target PC needs no Python
installation. `--stage <fresh portable game folder>` copies only launcher files
and notices, preserves the game, and refuses to overwrite an earlier runtime.

Before starting a game, verify the built executable on Windows:

```powershell
$p = Start-Process -FilePath '.\TopSpinLauncher.exe' -ArgumentList '--self-test','C:\absolute\launcher-result.json' -Wait -PassThru
$p.ExitCode
Get-Content 'C:\absolute\launcher-result.json'
```

The self-test creates a hidden Tk window, checks bundled imports, exercises the
DLL search-path guard and writes a JSON result. It never starts Top Spin or
changes game settings. Repeat it after moving the complete folder to a location
containing spaces, using a different working directory. A successful self-test
reports `ready: true` and `frozen: true`.

A native game launch uses a scoped `SetDllDirectoryW(NULL)` guard so that the game
does not inherit the private Python/Tk DLL search directory. The launcher restores
its own directory immediately after child creation.

Build and runtime references:

- [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html)
- [Frozen runtime paths](https://pyinstaller.org/en/stable/runtime-information.html)
- [External process DLL search isolation](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application)

After the complete private game package and its integrity manifest are staged,
verify it through the frozen launcher itself (no Python installation required):

```powershell
$p = Start-Process -FilePath '.\TopSpinLauncher.exe' -ArgumentList '--verify-files','C:\absolute\integrity-result.json' -Wait -PassThru
$p.ExitCode
Get-Content 'C:\absolute\integrity-result.json'
```

This mode checks the folder containing the executable. It writes `ok`, `summary`,
`count`, `missing` and `modified`, and returns zero only when all listed files
match. It does not start the game or change configuration or saved games.

### Direct play executable

`Play-TopSpin.exe` starts the adjacent `TopSpinLauncher.exe --play` with the
portable folder as its working directory. It waits and propagates the child exit
code, so Steam can track the game lifetime. It has no console and uses Unicode
paths. The existing configurator executable remains separate.

Build on Windows with the existing .NET Framework 4 compiler (included on
Windows 10/11; no additional Python requirement for the resulting executable):

```powershell
python -m tools.windows_direct --destination build/Windows-Direct-Entry
```

The direct entry point requires the Windows .NET Framework 4 runtime. Its own
source is `native/launcher/PlayTopSpin.cs`; it contains no game data. Native
validation with a fake child, Unicode/space-containing paths, an unrelated
working directory, a delayed child and exit code 37 is recorded in
`reports/runtime/windows-direct-validation.json`. No game is started by that
validation.
