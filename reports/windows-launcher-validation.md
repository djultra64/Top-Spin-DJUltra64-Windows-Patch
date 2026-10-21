# Final Windows portable package validation — 2026-10-20

Own integration: **djultra64**. Original third-party notices remain intact.

## Final private artifact

`build/TopSpin-Windows-Portable-20261020-Explicit4K-PRIVATE.zip`

- SHA256: `a9848f6be8a63d535094e73790b8126f6502239ee0d76bf3f906040c9450d773`
- Size: 1,334,598,940 bytes; 1,735 files plus empty T/U directories.
- 1,722 immutable game/launcher/runtime files covered by the local integrity
  manifest. User configuration, prompt-style baseline backups and saved games
  are intentionally separate from immutable checks.
- Defaults: 3840×2160 render, 1920×1080 borderless output, original timing,
  Windows frame generation disabled, Xbox 360 prompt style.
- Game executable SHA256:
  `1360e0819c49ee1c8acaffc7c3b01f57f89af74409d3e2b633931afe0f8d9a9f`
- Own input DLL SHA256:
  `a23ad609d74c374bf76f62cc41c4b37b83f7d9fa85521146cf36d90bade6f9e5`

This ZIP contains the user's original game files and may retain the user's key
in Config.pml. It is a private local test/play package, not a GitHub release.
Public source patches and original-media protection compatibility are separate
from this private artifact. No new CD/key bypass was introduced.

## Native launcher build

The standalone launcher was compiled on Windows 11 Pro x64 10.0.26200 using the
official signed CPython 3.14.8 distribution and pinned PyInstaller 6.22.3. Its
CPython and Tcl/Tk 9.0.4 libraries are private to `runtime-windows-launcher`; the
user needs no Python installation. Required CPython, PyInstaller, Tcl and Tk
notices are included. The exact build dependencies are recorded in
`native/launcher/requirements-build.txt`.

Final standalone launcher bundle:
`build/Windows-Launcher-Delivery/launcher`. Its launcher-only ZIP SHA256 is
`6efd2983041db5ecf1b9ef1b6d36f3dc51ae69b88d3acac1a75fe5317bd5cbaf`.

Native source regressions passed. Frozen hidden-Tk self-tests passed in the build
folder and after moving the complete bundle to a path containing spaces, with an
unrelated working directory and Python removed from PATH. The self-test imports
the manual glyph module and validates keyboard plus all six controller styles.
The frozen `--verify-files` mode passed its complete 30-file launcher manifest.
The scoped DLL search-path guard keeps the launcher's private Python/Tk search
directory out of the native game's inherited DLL configuration.

## Actual Windows game validation

The full private package was extracted on the skill-defined trusted Windows
machine into a fresh folder containing spaces. The standalone frozen launcher
started the production game from `C:\Windows\System32` with Python removed from
PATH. No game keyboard/controller input was injected.

The final executable supplies explicit internal backbuffer dimensions, removing
a window-size startup race. Read-only native samples verified the original game
application vtable, initialized device and exact live D3D8 presentation structure:
3840×2160, one backbuffer, format 22, windowed mode and the correct owned HWND.
That window's actual client remained 1920×1080 under the automatic output helper.

Visible compositor captures at 30 and 40 seconds show the main menu with
**50 FPS**, different playing-video frames, green Xbox 360 A for Continue and
yellow Y for Help. Window-DC captures initially showed a white rectangle; these
were capture artifacts and were replaced by crops of the visible own window.

The game closed gracefully through WM_CLOSE. The full frozen file-integrity
check passed before and after native runs. The official diagnostic wrapper was
used only in an earlier bounded investigation and restored before production
validation. The final private ZIP contains the unmodified production wrapper.

Evidence under `reports/runtime`:

- `windows-explicit4k-build.json`
- `windows-explicit4k-startup.json`
- `windows-explicit4k-screen-30.png` and `windows-explicit4k-screen-40.png`
- `windows-explicit4k-integrity-before.json` and `windows-explicit4k-integrity-after.json`
- `windows-final-zip-extraction.json` and `windows-final-zip-integrity.json`
- `windows-final-owned-cleanup.json`

The exact final ZIP was transferred with SHA256 verification and extracted
again into `Windows Final Extracted`. Its frozen integrity check passed all
1,722 immutable files. No additional game launch was needed. Final cleanup
confirmed zero project-owned Windows processes and zero temporary tasks.

No match, replay, Career progression/save or physical controller operation was
performed on Windows during these automated startup tests. Linux controller
validation and the remaining user play checks are recorded separately. Windows
frame generation is not included; the original simulation rate is preserved.

Machine power and the reservation remain under the parent agent's control; this
agent does not change power state.
