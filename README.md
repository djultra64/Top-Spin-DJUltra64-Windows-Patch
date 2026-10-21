# Top Spin - DJUltra64 Windows Patch

Modern Windows compatibility research for the original PC version of **Top Spin**, with a Linux/Proton development path. Project work by **djultra64**.

**This repository publishes source and research, not a ready-to-use public installer.** It contains no original game executable, game assets, CD key or complete portable game package. You must supply your own game files. The current transformations are locked to the private development baseline; they are not known to support every legitimate retail edition. A clean original-media executable baseline and a reproducible public patch pipeline are still required before an installer release.

## Your copy of the game

This compatibility project is intended for a **legally purchased or otherwise lawfully obtained PC copy of Top Spin**. You supply the game yourself; no game download, product key or licensing bypass is provided here. The current patch source still requires the exact supported input hashes described in [Building and research](docs/building.md); lawful ownership does not establish that a particular edition matches those inputs.

As of **October 20, 2026**, we have not found the original PC release for sale through a current official digital storefront. GOG lists it as a [Dreamlist request](https://www.gog.com/dreamlist/game/top-spin-2003), and it appears in [abandonware archives](https://www.myabandonware.com/game/top-spin-fph). This describes its availability, not permission to download or redistribute it: the “abandonware” label is not a license. Second-hand physical copies may still be available.

## Current development results

- Corrected 16:9 gameplay camera and rendering up to **3840 × 2160**. Original menus may still stretch.
- Separate internal render and output resolutions in the assembled platform candidates.
- Original timing preserved: **50 FPS gameplay / 30 FPS replays and cinematics**. Linux interpolation adds presentation frames without raising the simulation limit. Windows frame generation is not implemented.
- English configuration launcher, direct Play entry, local saves, integrity checking and an optional Steam shortcut.
- Controller actions separated from physical button labels, optional button remapping, and manual Xbox, PlayStation and Nintendo Switch prompt styles. Automatic last-device prompts remain experimental.
- A new **Quit Game** menu row and the game FPS counter disabled in the tested Linux candidate. Windows quit behavior has static checks but still needs a native gameplay check.

These describe assembled **private development candidates**, not the result of running a single build command from this repository. Controller hardware testing is limited to the available Ally controller; other families still require checks with real devices. See [runtime validation](reports/runtime-validation.md) for the evidence and outstanding checks.

## Choose your path

| Goal | Guide |
| --- | --- |
| Understand the source workflow and supported inputs | [Building and research](docs/building.md) |
| Configure or build the Windows components | [Windows instructions](docs/windows.md) |
| Configure or investigate Linux/Proton | [Linux instructions](docs/linux.md) |
| Use a fully assembled private candidate | [Launcher reference](launcher/README.md) |

Windows uses native game execution and a game-specific dgVoodoo2 configuration. The current Linux bundle requires **x86-64 Linux, glibc 2.42 or newer, Vulkan, X11/Xwayland and an existing Steam Proton 11 installation**. It does not establish support for older Linux distributions or Steam Deck's default operating system.

## Repository boundaries

Original media, extracted games, modified executables, generated game fonts, personal configuration and portable archives stay outside public Git history. The local packaging tools produce private output that must not be uploaded as a release. No new CD-key or licensing bypass is implemented.

Own work is attributed exclusively to **djultra64**. Third-party authorship and dependency copyright/license notices remain intact. Review the included component notices before redistributing dependencies; the source publication is not permission to redistribute the original game.
