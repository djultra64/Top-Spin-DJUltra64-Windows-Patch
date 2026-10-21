# Linux runtime support

Own integration: **djultra64**.

The current private development bundle targets **x86-64 Linux with glibc 2.42 or newer**, a working Vulkan driver and X11/Xwayland. This is the tested Fedora 43/Bazzite development baseline. A version check alone is not evidence of compatibility on every distribution. Steam with Proton 11 remains an external prerequisite unless installed separately into the portable folder.

The bundled GPU dispatch and vendor driver are intentionally supplied by the operating system. Copying another machine's graphics driver into this folder is not supported.

`tools/check_linux_runtime.sh` is a dependency-free shell preflight for this development baseline. Run it before starting the bundled Python interpreter. Newly staged Gamescope wrappers also run the copied preflight before loading their private binaries.

## Reproduce the audit

`tools.linux_runtime.audit_abi(path)` reads each ELF object's imported version requirements with `readelf --version-info`; it does not execute any binary. It distinguishes imported requirements from exported version definitions. The report retains exact GLIBC tags as well as a conservative numeric minimum. `GLIBC_ABI_GNU2_TLS` can appear in selected patched glibc 2.41 releases; the conservative unpatched baseline is 2.42.

The initial complete graphics bundle contains 676 ELF files. Python/Tk contains 69 ELF files. Both independently require this newer baseline. Reducing GStreamer plugins alone therefore cannot establish support for an older distribution.

## Smaller video runtime

Stage the optional WMV profile into a **new** private output folder:

```sh
python -m tools.linux_runtime /path/to/private/game-copy --video-profile wmv
```

The WMV profile retains the coherent GStreamer core, ASF/WMV decoder, playback/type detection, and audio/video conversion plugins. It excludes unrelated camera, network and Qt UI plugins. The original `all` profile remains the default pending integration in the game. The standalone WMV reader successfully sampled all seven original video files with the smaller profile; `BlankBumper.wmv` contains only two frames, independently confirmed with FFmpeg, and both were read before end of stream. Three MainMenu frames match the previously user-validated decoder byte for byte. This verifies initial decoding, not complete playback of every file. Do not run this staging command over an active game/runtime.

A locally staged reduced copy is `build/Linux-WMV-Runtime-Staging`. Its `TopSpin.exe` is an empty staging sentinel, not a playable copy and not an original game binary. The runtime may be copied into a separate complete game candidate after validation.

## Older distributions

Valve documents Sniper as Debian 11 based; the locally installed runtime contains glibc 2.31. It has no Gamescope, Tk or GStreamer 1 runtime matching this bundle. A Sniper wrapper cannot make Fedora's glibc 2.42 imports run on glibc 2.31. A broader Linux release requires rebuilding the Python/Tk, compositor and coherent media stack against the intended baseline, followed by decoding, controller and display validation on that baseline. This is separate from the Windows package and must not be described as complete.

Primary references:

- [Valve runtime architecture and Sniper baseline](https://github.com/ValveSoftware/steam-runtime/blob/master/doc/possible-designs.md)
- [Gamescope source and build instructions](https://github.com/ValveSoftware/gamescope)
- [GNU linker GNU2 TLS dependency definition](https://sourceware.org/pipermail/binutils/2025-August/143858.html)
- [Debian glibc symbol-version mapping, including distribution backports](https://sources.debian.org/src/glibc/2.41-12%2Bdeb13u3/debian/symbols.wildcards)

No game assets or executables may be included in a public source/patch release.
