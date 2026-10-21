# Windows frame generation platform port

Integration by **djultra64**. This is a redistributable native Windows port of the pinned `afmf-linux` platform layer and its existing optical-flow interpolation algorithm. Third-party author names and notices remain intact. It does not require Lossless Scaling or a proprietary frame-generation runtime.

The game-facing runtime is x86 `afmf32.dll` with a portable Vulkan layer manifest, used through the x86 DXVK D3D8 and D3D9 renderer. The x64 DLL is also built and tested for harness use. The manifest names `VK_LAYER_AFMF` and references `./afmf32.dll`; the launcher supplies its absolute directory through child-process environment variables. The dgVoodoo D3D11 renderer is a separate compatibility fallback and cannot load a Vulkan layer itself.

## Build

`build_windows.py` verifies upstream commit `bc56e5bd0e3a6c328aedef664d0d36363fb58b36` using archive SHA256 `2fccc4a6238aad1cb58ea69ffb3f775ee9644a18b4c149c987fce6290b273dcd`, then applies the runtime and harness patches under `patches/`. It regenerates the same 19 shader permutations as upstream and builds native Windows DLLs and synthetic tests with warnings treated as errors.

The tested toolchain is official Zig 0.15.2, glslang, and Vulkan 1.4.341 headers on Linux. No host packages are installed by the recipe. Provide different input locations through `--archive`, `--zig`, `--vulkan-headers` and `--glslang`; choose a fresh output directory:

```sh
python3 native/framegen/build_windows.py --output build/afmf-windows-new
```

The output records hashes of the source archive, integration sources, patches, shader header, compiler, DLLs and harnesses. Source paths are mapped out of release diagnostics; runtime DLLs carry their shaders internally and need no compiler or shader files on the user's PC. Dependencies at runtime are the Windows UCRT, Kernel32, Winmm and the user's Vulkan driver.

## Windows synchronization and cadence

`windows_compat.c` implements the subset of pthreads used by the pinned source through Windows synchronization and thread APIs. QPC supplies monotonic timestamps. Timed condition waits compare absolute QPC deadlines and round remaining waits up to milliseconds.

QPC accuracy does not improve scheduler wake granularity. The first live shim-created thread therefore requests `timeBeginPeriod(1)` and the last returning thread balances it with `timeEndPeriod(1)`. Overlapping presenter, worker and pipeline threads share one module-owned request. Thread-creation failure unwinds its ownership; request failure prevents thread creation and follows upstream's logged fallback. Normal layer destruction joins its threads before unload. No Winmm calls occur in DllMain and no atexit callback can double-release the request.

On Windows 10 version 2004 and later, timer-resolution requests apply to the calling process. Windows 11 can withdraw the improved resolution when the window-owning process is occluded or minimized, so the request itself is not proof of display cadence. See Microsoft's [timeBeginPeriod](https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod) and [timeEndPeriod](https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timeendperiod) contracts. No game simulation timing code is changed by this adapter.

## Verification

Both x86 and x64 Windows DLLs were exercised above Wine's Vulkan thunk in a dedicated synthetic Win32 harness on llvmpipe under private Xvfb. Each moving-square run produced 119 generated companions for 120 source presents. GPU readbacks passed the upstream midpoint and optical-flow checks plus translated-edge energy checks. Previous/current frame repetition and both encoded-space and linear-light alpha blends fail the negative controls.

Identical-static fixtures produce the same RGB pixels as their source with zero optical flow. Their 119 identical generated companions are valid static-scene output. Every freshly compiled SPIR-V module is byte-for-byte identical to the existing Linux build. The timer contract tests cover overlapping ownership, final release, repeated lifecycle, failed thread creation and monotonic 10/16.667/20 ms deadlines on both ABIs.

Run the synthetic checks using a dedicated Wine prefix:

```sh
python3 native/framegen/run_wine_checks.py \
  --wine /absolute/path/to/wine64 \
  --build build/afmf-windows-new \
  --prefix /absolute/path/to/dedicated-prefix
```

`--fixtures motion` or `--fixtures static` selects a subset. `windows-compat-test.exe` checks the timer/thread contract independently. The manual loader bridge belongs only to the test executable: Wine's normal Vulkan loader does not discover this native Windows DLL as an explicit layer. These results establish Windows DLL execution and interpolation through that bridge; native Windows loader discovery, real-adapter cadence and Top Spin session behavior were not measured in this environment. They do not establish native 50→100 or 30→60 displayed FPS.

The integration files use the adjacent MIT `LICENSE`. `THIRD_PARTY_NOTICES.txt` contains the upstream AFMF, AMD FidelityFX, Vulkan headers, Zig and mingw-w64 notices. Original game files are supplied privately by each user and are excluded from these sources and synthetic tests.
