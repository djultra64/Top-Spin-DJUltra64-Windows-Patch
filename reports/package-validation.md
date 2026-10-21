# Private portable package validation — 2026-10-20

Own work: **djultra64**. These are private local game packages, not a public source-only patch release. They contain the user's game files and must not be uploaded to GitHub.

| Check | Windows | Linux / Proton |
| --- | --- | --- |
| Archive | ZIP; self-contained launcher/runtime | TAR.GZ; local launcher/runtime; external Proton 11 |
| Default render / output | 3840×2160 / 1920×1080 | 3840×2160 / 1920×1080 |
| Timing | Original synchronization retained; native menu observed at 50 FPS | Original 50 gameplay / 30 replay timing retained |
| Frame generation | Not implemented; disabled in launcher | Included and user-confirmed smoother; generated frames keep simulation timing |
| Controller prompts | Manual Xbox 360: green A / yellow Y visible natively | Manual Xbox 360 visually verified and user-confirmed |
| Portable extraction | Actual ZIP extracted into a Windows path with spaces; frozen launcher started from System32 without installed Python | Actual TAR extracted into a path with spaces; executable permissions and relocated launcher diagnostics passed |
| Integrity | 1,734 immutable files | 3,877 immutable files |
| Actual game view | Main menu, playing video, prompts and 1080p output captured | 4K/interpolation/video/controller integration previously user-tested |
| 4K guarantee | Version-locked explicit windowed presentation parameters; live 3840×2160 readback while output is 1920×1080 | Gamescope exposes a fixed 3840×2160 game display; output is 1080p |
| Compositor shutdown | Not applicable | SDL and Vulkan thread lifetime fixes compiled; own rendered Vulkan/FG/exit controls pass |

The launcher includes English graphics/controller settings, **Check game files for integrity** and **Add to Steam**. On Linux, the Proton folder picker stays hidden when Proton is found; it appears only as a manual fallback if discovery fails. Six isolated real-Tk launcher checks covered automatic, bundled and manually selected installations, missing/invalid paths, and removal before Play; no game was started. Steam integration was tested against synthetic accounts, shortcut files and an owned fake client; no real Steam library was changed by validation. The one-click flow chooses the active or most recent account, saves settings, requests normal Steam shutdown when required, creates or renames **Top Spin** while preserving an existing shortcut ID, installs the supplied icon/logo/hero/covers, and reopens Steam if it was initially running. An account chooser is reserved for ambiguous metadata; duplicate names across installations show distinct paths and selection is resolved by index. The duplicate-account fallback was verified in real Tk against two isolated installations. The configurator uses the supplied logo and window icon. Remapping separates logical actions from physical positions and applies to menus and gameplay, including Nintendo's B/A/Y/X positions.

Manual prompt styles are fixed until changed in the launcher. Automatic switching has a corrected native UTF-16 argument contract and own ABI tests, but remains labeled experimental pending a real-device visual check. Baseline font backups stay private and restore exact keyboard resources.

## Remaining validation and limits

- Full match/replay visual proportions, complete Career profile save/reload, and real Xbox One/Series, PS4/PS5 and Switch hardware checks still need the user's deferred play session. Available Ally controls were validated under Proton; Windows has not had a real controller test.
- Windows frame generation remains separate implementation work; this package does not claim uncapped native simulation or interpolated Windows gameplay. Research scope is documented in `docs/windows-frame-generation-next-step.md`.
- Linux requires glibc 2.42 or newer and compatible Vulkan drivers. The rebuilt compositor passed own rendered-client/FG/termination controls; Top Spin itself has not been restarted with that final compositor solely for another closing test.
- Original menus may remain stretched, as accepted by the user. The gameplay camera uses the corrected 16:9 aspect.
- Public installation/ISO patch workflows and a clean original executable baseline are deferred. No original game executable, assets, CD keys or private packages should be published. No new licensing or CD-key bypass was added.

Current source verification: **145 tests passed with no skips outside the 32-bit syscall filter**. This includes the native registration and confirmation ABI harness. The direct Windows EXE passed a native inert-child test (Unicode/spaced path, working directory, wait and exit status), and the Linux direct script passed with two different saved configurations using the packaged interpreter. Official sourceless Python codec modules are retained as runtime files; generated caches remain excluded. The updated archives have all immutable member hashes checked locally; the unchanged Windows game/render path retains its earlier native validation. Private artifact checksums and detailed native evidence are under ignored `reports/runtime/`; current runtime status is in `reports/runtime-validation.md`.

## Main-menu Quit revision

The added final **Quit Game** row uses the original application confirmation. The complete menu is raised 24 virtual units so the row fits, and the original debug FPS counter is disabled. The user validated the revised row, counter removal, No cancellation and Yes exit together on Linux/Proton; the diagnostic recorded `confirmed` and the process returned 0. The original Career binding is unchanged. The Windows executable matches all guarded hook inputs, but this revision has no additional Windows game runtime validation. Only the native input DLL, MainMenu archive and each destination configuration’s ShowFPS value change in the package update. Anti-aliasing remains unchanged; native 2x MSAA and Windows wrapper alternatives are documented in `docs/anti-aliasing-investigation.md` pending a focused rendering validation.
