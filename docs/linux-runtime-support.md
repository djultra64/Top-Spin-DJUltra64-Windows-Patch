# Linux runtime support

Own integration: **djultra64**.

The Linux/Proton patch bundles its Python/Tk launcher, Gamescope, Xwayland support files, a coherent GStreamer video stack and the Linux AFMF Vulkan layer. It targets **x86-64 Linux with glibc 2.42 or newer**, Vulkan and X11/Xwayland. Steam with Proton 11 remains external. Download/install instructions are in [the Linux guide](linux.md); users of the archive do not need to stage these dependencies themselves.

The development baseline is Fedora 43/Bazzite. The ABI requirement applies to bundled libraries as well as the interpreter. Distribution names alone do not establish compatibility, and GPU dispatch/vendor drivers are supplied by the operating system. Do not copy another machine's graphics driver into the game folder.

## Preflight and ABI audit

The installer runs a dependency-free shell ABI preflight before loading its private interpreter. The installed copy is `runtime/linux/check-abi.sh`; Gamescope wrappers also check the ABI before starting private binaries. From a source checkout, the equivalent command is:

```sh
sh tools/check_linux_runtime.sh
```

`tools.linux_runtime.audit_abi(path)` reads imported ELF version requirements with `readelf --version-info` without executing the objects. It distinguishes imported requirements from exported definitions, retaining the exact GLIBC tags and a conservative numeric minimum. `GLIBC_ABI_GNU2_TLS` can appear in selected patched glibc 2.41 distributions; the conservative unpatched baseline is 2.42.

Both the graphics/media runtime and bundled Python/Tk independently need this ABI floor. Removing video plugins does not establish support for an older distribution.

## Gamescope helpers and host libraries

Linux v0.3.1 supplies the Gamescope process helper from the matching compositor build. Its launcher and dialog wrappers keep the bundled compositor/video libraries scoped to the processes that need them. A host dialog restores the original host loader environment before starting, so the system GTK/GStreamer stack does not load the game's incompatible private libraries. The bundled wrapper does not replace system libraries.

Keep `runtime/linux/bin/gamescope`, `gamescope.bin`, `gamescopereaper`, `zenity` and Xwayland support files together. The preflight reports a missing or non-executable helper before starting the compositor. The host dialog executable itself comes from the operating system.

## Coherent video runtime

The release uses the complete video runtime alongside Proton 11. Its GStreamer core, plugins and dependent libraries must stay together. A missing or mismatched WMV stack can produce color bars instead of menu video even when the executable starts. Restore the complete Linux payload rather than replacing individual libraries from another installation.

Developers can stage the runtime using `tools.linux_runtime`; see [Building](building.md). The helper has `all` and `wmv` video profiles. The release uses `all`. The smaller `wmv` profile is a separate development option that retains ASF/WMV decoding, playback/type detection and audio/video conversion while excluding unrelated camera/network/Qt plugins. Its reduced contents do not alter the release's host ABI requirement.

## Older distributions

An older Steam Linux Runtime cannot make glibc 2.42 imports work on an older host merely by wrapping the same binaries. Broader compatibility requires rebuilding the interpreter/Tk, compositor and coherent media dependencies against the intended baseline. Proton selection does not substitute for that rebuild. Use the current release only on a host meeting its requirements.

Primary references:

- [Valve runtime architecture and Sniper baseline](https://github.com/ValveSoftware/steam-runtime/blob/master/doc/possible-designs.md)
- [Gamescope source and build instructions](https://github.com/ValveSoftware/gamescope)
- [GNU linker GNU2 TLS dependency definition](https://sourceware.org/pipermail/binutils/2025-August/143858.html)
- [Debian glibc symbol-version mapping, including distribution backports](https://sources.debian.org/src/glibc/2.41-12%2Bdeb13u3/debian/symbols.wildcards)

The public archive includes redistributable runtime components and complete notices under `runtime/linux/licenses` and `licenses/linux-runtime`, never original game assets/executables, generated game font archives, keys or private backups. The optional [Linux runtime source companion](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.2.1/TopSpin-DJUltra64-Linux-Runtime-Sources-v0.2.1.tar.gz) supplies corresponding dependency source and is not needed to install or play.
