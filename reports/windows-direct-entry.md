# Windows direct-play entry point

Own work: djultra64.

Artifact: `build/Windows-Direct-Entry/Play-TopSpin.exe`.
SHA256: `5f88d7e516abd7215548190cc74e6726bc44322ab5a2031fa85b828ee0d02000`.

The small GUI-subsystem executable invokes adjacent `TopSpinLauncher.exe` with
exactly `--play`, sets the portable folder as the child's working directory,
waits for it and returns its exit code. Missing-launcher/start failures show an
English error. It does not open the configurator or store separate settings.
The existing `TopSpinLauncher.exe` remains the configurator and runtime owner.

Built with Windows' .NET Framework v4 C# compiler. The resulting EXE requires the
Windows .NET Framework 4 runtime, included on Windows 10/11, and no Python.
`tools/windows_direct.py` reproduces the build from the own C# source.

Native Windows validation used only an own fake `TopSpinLauncher.exe`. The
wrapper was run from `C:\Windows\System32`, while its portable directory
contained spaces, ñ and 日本語. The child recorded the exact portable working
directory and `--play`; after a 750 ms delay it returned 37. The wrapper waited
1,103 ms and returned 37. Its PE subsystem is Windows GUI (2). No game was
launched and no keyboard/controller input was injected. Evidence:
`reports/runtime/windows-direct-validation.json`. All own test processes ended;
no scheduled tasks were created.
