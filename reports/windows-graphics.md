# Native Windows graphics validation

Own integration: **djultra64**. The unmodified game-specific compatibility
component is **dgVoodoo2 2.87.5 x86 D3D8.dll**, by Dege.

The official redistribution documentation permits individual unmodified
components with a specific game/mod. Original terms and component provenance
are retained under `runtime/windows/licenses/dgVoodoo2` in the private package.

- [Official release](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.5)
- Original ZIP SHA256: `5ffde6927f7355ca3fdd5d785b581256a8e6539fa13e395a891ade6ba1040850`
- Production D3D8.dll SHA256: `d03e2562178db1fcf3493fc0a0b23a465e35c55d73adb3ec095be866cd662704`
- [Original terms](https://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/)

## Configuration failure found on Windows

The first native game start showed the generic message “Your hardware doesn't
match Top Spin requirements.” A read-only stack capture recovered the actual
HRESULT: **0x82000003**, no compatible Direct3D adapters/modes. No CPU, RAM,
operating-system, CD or key check was bypassed.

Original device enumeration rejects every mode smaller than the configured
render dimensions, even when creating a windowed device. The wrapper therefore
needs both internal and output dimensions in `ExtraEnumeratedResolutions`.

An isolated native enumeration probe then established why the initial local
configuration was not taking effect. The official debug wrapper read the correct
local file but rejected `ColorSpace = argb8888_srgb`, abandoned that configuration
and fell back to passthrough. The actual binary accepts `argb8888_sdr`; changing
to that value made the sentinel configuration enumerate its four intended modes,
including 3840×2160 in both tested formats. The implementation and regression
checks now use the runtime-accepted value.

The old negative override experiments used the invalid configuration and cannot
alone support conclusions about valid wrapper settings. A new control with the
accepted configuration nevertheless produced **1920×1080 D3D11 textures** when
requesting a 1920×1080 logical backbuffer/window, despite `Resolution = 3840x2160`.
Do not rely on that option alone as proof of 4K rendering. Evidence:
`reports/runtime/windows-native-forced4k-1080-logical.txt`.

## Actual game and extracted production package

Tests ran in the existing interactive Windows session on Windows 11 Pro x64
10.0.26200, NVIDIA RTX 2060, physical 1920×1080 display. SSH session zero was used
for orchestration, not as a substitute for interactive display validation.

A bounded, exact-PID DBWIN reader observed the actual game with the official
debug wrapper. The game created a **3840×2160 implicit swapchain** in windowed
mode; its own output window subsequently remained **1920×1080**, with no reset in
the captured transition. The initial presentation parameters used zero width and
height, which inherit client dimensions. The final Windows executable replaces
only the 32-byte windowed presentation-parameter construction block at 0x57a707
and updates the PE checksum. It supplies width and height from the validated game
resolution globals, preserves format/register/flag behavior, and leaves the
fullscreen branch intact. A version guard rejects other input executables.
An executed x86 instruction harness confirms 720p, 1080p and 4K dimensions and
preserved surrounding state.

The final production run through the frozen launcher confirmed the fix directly:
a read-only inspector verified the original application vtable, initialized
Direct3D device and the exact live presentation-parameter structure passed to
CreateDevice. It reported **3840×2160**, format 22, one backbuffer, windowed mode,
and the exact owned game HWND. At the same time that window's actual client was
**1920×1080**. Samples at 5, 15, 30 and 40 seconds agreed. No startup-timing or
wrapper-override assumption is needed.

The production wrapper was restored after that game exited. Its full immutable
manifest passed again. The complete private ZIP was then transferred, SHA256
verified and extracted into a fresh folder containing spaces. The standalone
`TopSpinLauncher.exe --play` started the game from an unrelated working directory
with Python removed from PATH. Automatic output sizing reported 1920×1080 at
five seconds and stayed at that size.

Two visible compositor captures show the main menu, different playing-video
frames, green Xbox 360 A for Continue and yellow Y for Help. The production game
counter reads **50 FPS**. A window-DC capture had shown a white rectangle; the
visible compositor captures establish that this was a capture limitation.

- `reports/runtime/windows-native-game-graphics-summary.json`
- `reports/runtime/windows-explicit4k-startup.json`
- `reports/runtime/windows-production-display.json`
- `reports/runtime/windows-explicit4k-screen-30.png`
- `reports/runtime/windows-explicit4k-screen-40.png`

The production game closed through WM_CLOSE without injected keyboard/controller
input. All **1,722 immutable files** passed the frozen integrity check afterwards.
No match, replay, Career progression or physical controller interaction was
performed on Windows during these automated startup tests. Frame generation is
not included in the Windows build; original simulation timing is preserved.

## Diagnostic isolation and cleanup

MinHook 1.3.4, by Tsuda Kageyu and contributors, is used only inside the own
isolated graphics probe, with its original BSD notices retained in the diagnostic
dependency source. It is not part of the production game runtime. The DBWIN
reader records only the explicitly verified owned process and closes its events,
mapping and process handle. Debug frame rates are not performance measurements.

All project-owned Windows game/probe processes and temporary scheduled tasks
were stopped after the production checks. Power remains under the parent task's
maquinita reservation and was not changed by this agent.
