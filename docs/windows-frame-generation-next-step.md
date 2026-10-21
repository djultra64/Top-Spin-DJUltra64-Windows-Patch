# Remaining Windows frame-generation work

Research by **djultra64**. This assessment does not install software, change the game, or establish Windows interpolation compatibility.

The portable Windows compatibility package preserves the original 50 FPS gameplay and 30 FPS replay/cinematic timing. The Linux candidate has the tested interpolation path. **Windows frame generation remains unimplemented and is disabled in the launcher.** A compatibility/package validation does not satisfy that separate high-FPS requirement.

## Porting the existing layer

The available local source is `afmf-linux` commit `bc56e5bd0e3a6c328aedef664d0d36363fb58b36`. The algorithm and SPIR-V shaders are reusable; this is a bounded platform/ABI port rather than writing another interpolation algorithm. It is nevertheless more than a configuration toggle or replacing a DLL:

- `src/layer_internal.h:22` rejects 32-bit builds. Its comment identifies non-dispatchable-handle logging casts as a reason. Those casts need correction and the remaining pointer/handle assumptions need a real x86 audit.
- `src/layer.h`, `src/config.c`, and swapchain modules depend on pthread synchronization/thread types. The local source uses 18 distinct pthread functions and 18 `clock_gettime` call sites. The presenter uses a condition variable explicitly configured for monotonic timed waits. A Windows implementation must preserve that clock and timeout contract.
- `src/config.c` checks `/proc/self/exe` solely to recognize Gamescope. Windows can replace this process-name check or disable the Gamescope-specific path. `mkdir` is used for optional frame dumps. Neither implies rewriting the Vulkan rendering algorithm.
- The exported negotiation entry point uses ELF visibility attributes; Windows needs an exported, correctly named x86 Vulkan-layer entry point and the proper calling convention.
- `src/layer.c` names X11/Wayland surface hooks, but they mainly log surface creation. Unknown functions already forward to the next `GetInstanceProcAddr`. No direct X11/Wayland rendering dependency was found in that path. A Windows surface logging hook can be added; its absence alone does not establish incompatibility.

Upstream supplies a Linux x86-64 layer and no x86 Windows build. A native Windows x86 game needs an architecture-matched Vulkan layer; Linux's tested WoW64 host-layer arrangement does not transfer unchanged. [Upstream FAQ](https://afmf-linux.digitalexperiments.dev/faq/), [source repository](https://github.com/serialexperimentslainnnn/afmf-linux), [Vulkan loader/layer interface](https://vulkan.lunarg.com/doc/view/latest/windows/LoaderLayerInterface.html)

A feasible implementation sequence is a small Windows platform abstraction for time/threading/process paths, an x86 build with handle/export corrections, and an **own** Vulkan swapchain harness. That harness must verify companion presentation counts, alternating cadence, resize/recreation and shutdown before any game session. DXVK x86 D3D8 requires both its D3D8 and D3D9 DLLs; Windows support is unofficial. Only a subsequent game check can establish unchanged 50/30 simulation speed and acceptable UI/ball artifacts. No such Windows layer build or validation has been completed. [DXVK DLL requirements](https://github.com/doitsujin/dxvk/blob/master/README.md), [Windows support limits](https://github.com/doitsujin/dxvk/wiki/Windows)

## Alternative source integration to investigate separately

The unofficial **Magpie Experimental** source now includes an FSR3 frame-generation backend with AMD optical flow. Its external x64 window-capture architecture could process a 32-bit game's displayed image without a D3D8 in-process layer. This is an architectural inference, not verified Top Spin compatibility.

At this assessment, its README identifies 0.6.9 as the public release and 0.6.10 as a review draft; the draft introduces the FSR3 generator. Its build option defaults off and requires separately supplied SDK/runtime inputs. The documented mode is SDR at 2×. It is therefore not a ready, tested dependency for this package. Source/build, exact component licenses, capture compatibility, presentation cadence, input latency and artifacts would all need verification before integration or redistribution. Do not install an unreleased build or bundle optional proprietary runtimes on the strength of these feature descriptions. [README/release status](https://raw.githubusercontent.com/SAOG0721/Magpie/experimental/README.md), [build options](https://raw.githubusercontent.com/SAOG0721/Magpie/experimental/src/BuildOptions.props), [0.6.10 draft](https://raw.githubusercontent.com/SAOG0721/Magpie/experimental/docs/RELEASE_NOTES_v0.6.10-experimental.md), [component boundaries](https://raw.githubusercontent.com/SAOG0721/Magpie/experimental/docs/THIRD_PARTY_AND_REDISTRIBUTION.md)

Upstream Magpie itself explicitly does not implement frame generation. Android-focused Vulkan projects do not provide evidence of a native Windows x86 integration. No free, fully reviewed, ready-to-bundle Windows D3D8 interpolation replacement was established in this bounded review. That is a statement about the investigated implementations, not a claim that Windows interpolation is impossible. [Upstream Magpie FAQ](https://github.com/Blinue/Magpie/wiki/FAQ-(EN))
