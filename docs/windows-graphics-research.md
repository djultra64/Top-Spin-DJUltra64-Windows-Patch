# Windows graphics and frame-generation assessment

Own research/integration: **djultra64**. Research status: not a Windows gameplay validation.

The supported safe timing target remains the original **50 updates/second during gameplay and 30 during replays/cinematics**. Raising presentation frequency must preserve those updates. Previous native-unlock experiments visibly accelerated the game and are not a deliverable.

## Existing AFMF layer

The private Linux build pins `serialexperimentslainnnn/afmf-linux` at `bc56e5bd0e3a6c328aedef664d0d36363fb58b36`. Its release is Linux x86-64; upstream says a separate 32-bit build is not supplied. [Upstream FAQ](https://afmf-linux.digitalexperiments.dev/faq/)

The pinned source establishes concrete port work:

- `src/layer_internal.h:22` explicitly rejects `sizeof(void*) != 8`. The adjacent comment identifies handle logging as one reason. Removing the assertion alone is not an ABI audit.
- `src/layer.h` stores pthread mutex/thread state; swapchain threads use condition variables, monotonic timed waits and `clock_gettime`. A Windows build needs a verified compatible threading/time implementation, or explicit Win32 replacements.
- `src/config.c` reads `/proc/self/exe`; dump support uses POSIX `mkdir`. Windows exports currently use ELF visibility attributes, so a DLL build needs correct exported loader negotiation symbols and x86 calling conventions.
- Surface hooks name Wayland/X11/headless/display. Unknown functions already forward through `GetInstanceProcAddr`, so lack of a Win32 surface logging hook by itself does **not** prove a surface cannot work.
- SPIR-V compute shaders and most Vulkan swapchain code are reusable. The Linux shared object itself cannot load into Windows.

A Windows **32-bit** DLL is needed inside this 32-bit game when using native Windows DXVK. Linux's working WoW64 path instead reaches a 64-bit host Vulkan layer. This architectural distinction is why copying the tested `.so`, or building only a Windows x64 DLL, is insufficient. The Vulkan loader requires appropriate layer discovery, manifest/library paths and loader entry points. [LunarG loader interface](https://vulkan.lunarg.com/doc/view/latest/windows/LoaderLayerInterface.html)

A MinGW/winpthreads port is technically plausible, but its smallest honest milestone is an **own standalone Vulkan x86 swapchain harness**: create/present/resize/destroy, generate/count companion presents, verify monotonic cadence and teardown. Only then should it touch Top Spin. Compilation alone does not verify interpolation or speed. No full port was started during this assessment.

## Smallest optional Windows interpolation path

On supported AMD hardware with the user's existing Adrenalin driver, AFMF 2.1 supports Vulkan and D3D11/12. The required driver is 25.3.1 or newer; hardware/fullscreen requirements vary. This is an optional driver feature, not software bundled by this project. [AMD requirements](https://www.amd.com/en/products/software/adrenalin/afmf.html)

DXVK provides the D3D8-to-Vulkan path using **both x32 `d3d8.dll` and `d3d9.dll`**. Its authors explicitly describe Windows as unofficial/unsupported, so Top Spin must be tested rather than assuming the Linux result transfers. [Required DXVK DLLs](https://github.com/doitsujin/dxvk/blob/master/README.md), [Windows limitations](https://github.com/doitsujin/dxvk/wiki/Windows)

A practical optional chain is therefore **Top Spin → x32 DXVK → Vulkan → user-installed AMD AFMF**. It avoids redistributing driver/proprietary interpolation components, but does not provide interpolation on arbitrary GPUs. AMD requires VSync disabled. Preserve the game's original update limiter; if disabling synchronization changes game speed, reject this mode. The current Linux configuration preserves the game timing setting while overriding presentation interval at the translation layer, which is a candidate approach to validate on Windows, not proof.

The Windows launcher must not offer an apparently functional built-in interpolation toggle when it only launches this external driver feature. Until native validation, label it unavailable or document the external option as untested.

## 4K rendering on a lower-resolution Windows display

First test a **windowed** D3D device with a 3840×2160 backbuffer and a smaller client window. DXVK's D3D8 path delegates to D3D9; Microsoft documents Present scaling the backbuffer into the destination client rectangle. This suggests an own small display probe before adding another renderer. It remains an inference until tested against Top Spin's device creation/reset behavior. [Microsoft Present behavior](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-present)

As an optional user-supplied alternative, dgVoodoo supports forcing DirectX render resolutions and translating D3D8 to D3D11/12. This could also expose the game to an external driver interpolation feature. It does not replace the game's 16:9 camera correction and needs its own timing/video/controller checks. Keep its binary out of an open-source-only dependency package unless its distribution terms are separately satisfied. [Author's resolution/output documentation](https://dgvoodoo2.dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/)

## Rejected shortcuts

- Upstream Magpie explicitly has no frame-generation plans; its scaling FPS counter is not proof of game/interpolated FPS. [Magpie FAQ](https://github.com/Blinue/Magpie/wiki/FAQ-(EN))
- FSR3 is not a drop-in D3D8 frame-generation DLL. Its documented integration uses modern swapchains and additional frame resources. [AMD FSR3 integration](https://gpuopen.com/manuals/fidelityfx_sdk/techniques/super-resolution-interpolation/)
- Paid Lossless Scaling and proprietary shader redistribution are not dependencies of this package.

A Windows package validated at native 50/30 FPS can still be a useful portable compatibility package. It must explicitly state that broadly available Windows interpolation remains unimplemented rather than describe that original high-FPS requirement as satisfied.
