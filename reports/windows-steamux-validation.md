# Native Windows Steam UX launcher validation

Own work: djultra64. Windows 11 x64, private CPython 3.14.8,
PyInstaller 6.22.3 and Tcl/Tk 9.0.4.

Final bundle: `build/Windows-Launcher-SteamUX/launcher`.
Final launcher-only ZIP: `build/Windows-Launcher-SteamUX/windows-launcher-steamux-v2.zip`.
SHA256: `63d072463c6f8b72275a0d8be0ea06b0376822cfaadddf160d5be1f1649068f2`.
Includes the standalone configurator, direct-play EXE, private runtime and notices.

The source snapshot SHA256 is
`d366d9e87a0f2710f3fcb06b5d35fcac9a474715d3901a24994cd710e30a6e7d`,
with the final duplicate-account chooser correction overlaid as `launcher/gui.py`
SHA256 `3c326f164c73b2b34fb872b1e77f000f5a2ddb1bd0e525982d460e87d7052a22`.

Final frozen tests passed after relocation to a path containing spaces, ñ and
日本語, with Python absent from PATH and an unrelated working directory. Hidden
Tk self-test passed; the synthetic complete bundle manifest verified 31 files.
Normal frozen startup opened its own 700×700 configurator with the header logo,
then closed through WM_CLOSE to its exact owned HWND, exit 0. Evidence:
`reports/runtime/windows-steamux-v2-{relocated-self-test,integrity-test,frozen-gui}.json`
and `windows-steamux-v2-frozen-gui.png`.

An isolated native Tk integration test used two synthetic Steam accounts and an
own compiled fake steam.exe. It selected the most recent account automatically,
saved settings, gracefully invoked only the fake client's -shutdown and reopened
it, renamed the legacy shortcut to Top Spin while preserving its app ID, and
installed all four artwork slots into only the selected synthetic profile. Header
logo and icon loaded. Evidence: `reports/runtime/windows-steam-ux-validation.json`.
This test patches Steam-root discovery, registry-account lookup and running-state
checks to the own fixture. No real Steam process, registry value or userdata was
modified. No game was launched and no keyboard/controller input was injected.

The final native build includes the reviewed duplicate-label chooser correction;
its separate account-choice regression was validated by the parent on Linux Tk.
All own Windows test processes ended and temporary tasks were removed. Evidence:
`reports/runtime/windows-steamux-v2-cleanup.json`. Machine shutdown is recorded
separately in `reports/runtime/windows-steamux-machine-cycle.json`.
