# Copyright and third-party notices

Original project work and documentation: Copyright 2026 **djultra64**.

No project-wide license for the original work has been selected for this source publication. Do not infer that dependency licenses apply to the entire project. Third-party files retain their own licenses and copyright notices.

## Controller prompts

The selected PNGs in `assets/input/xelu/` come from **Xelu's Free Controller Prompts**, created by **Nicolae (Xelu) Berbece** and updated by **Paul Paun (2021)**. They are offered under **CC0-1.0**. These controller prompts are not Top Spin game assets. The original readme, source link, file hashes and physical-position mapping are included in that folder.

Source: https://thoseawesomeguys.com/prompts/

## Gamescope source patch

`patches/gamescope-sdl-clean-shutdown.patch` modifies Gamescope. Its context and upstream material remain subject to the upstream notices in [LICENSES/Gamescope.txt](LICENSES/Gamescope.txt). Original project integration and local corrections are attributed to djultra64. No Gamescope executable or third-party runtime bundle is included in this repository.

Upstream: https://github.com/ValveSoftware/gamescope

## Windows interpolation integration

The original files in `native/framegen/` are the djultra64 Windows platform integration and verification tools, offered under their [component MIT license](native/framegen/LICENSE). The upstream AFMF algorithm and AMD FidelityFX shader notices remain authentic in [the component notices](native/framegen/THIRD_PARTY_NOTICES.txt). This component license does not apply to the complete project or to original game files.

DXVK retains its authentic zlib/libpng license and authors. The Windows release keeps its exact DXVK version and notices alongside the optional Vulkan interpolation runtime. The game and its synchronization logic are not included in that component.

## Lua source patch

`patches/lua50-topspin-format.patch` contains the local compatibility changes to upstream Lua 5.0.3. Original changes are attributed to djultra64; upstream authors and the MIT permission notice remain in [licenses/lua-5.0.3/COPYRIGHT](licenses/lua-5.0.3/COPYRIGHT). No compiled game script or Lua executable is included. See [the build recipe](docs/lua-bytecode.md).

## External build and runtime dependencies

Python, Tk, Pillow, pefile, olefile, SDL, Lua, Proton, DXVK, dgVoodoo2 and other optional dependencies retain their upstream licenses. Build instructions and runtime staging tools do not grant permission to redistribute their outputs without their required notices. Dependency binaries and runtime bundles are not included here.

## Game ownership and private outputs

Top Spin and its original executable, assets, scripts, fonts, videos and other game data belong to their respective owners. None of those files, product keys, personal saves or private portable packages is included. Generated or modified game resources remain private. SteamGridDB game artwork used in private testing is also excluded; this repository does not claim a redistribution license for it.

The compatibility source contains narrow instruction signatures, offsets and hashes needed to validate supported inputs. It contains no complete game executable or original asset archive. No new CD-check or product-key bypass is implemented, and original licensing requirements remain applicable.
