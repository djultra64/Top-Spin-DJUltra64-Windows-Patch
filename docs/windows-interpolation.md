# Windows frame interpolation

Windows integration by **djultra64**, based on the pinned upstream AFMF layer and AMD FidelityFX optical flow. Introduced in v0.2.0, this optional component is included alongside the default dgVoodoo2 renderer.

## Enable or disable

1. Open **TopSpinLauncher.exe**.
2. Select **Frame interpolation**.
3. Choose **Save settings** or **Play**.

The saved choice also applies to **Play-TopSpin.exe**. Interpolation is off on a fresh installation; upgrading preserves your preferences. To return to the default renderer, clear the checkbox and save.

Enabling it switches the game's local renderer to the included DXVK 2.7.1 x32 `d3d8.dll` and `d3d9.dll`, then enables `VK_LAYER_AFMF` for the child game process. Disabling it restores the included dgVoodoo2 `d3d8.dll` and removes the managed DXVK `d3d9.dll`. No system-wide Vulkan registration or replacement of operating-system DLLs is required. Unknown custom renderer DLLs are rejected rather than overwritten.

Interpolation creates intermediate presentation frames from successive rendered images. The original **50 FPS gameplay / 30 FPS replay and cinematic** timing remains unchanged. It does not add new simulation updates, and perceived smoothness depends on render time, display refresh and driver support.

## Requirements and recovery

Use **64-bit Windows 10/11**, a Vulkan 1.3-capable GPU and a compatible current driver with the additional features required by DXVK 2.7.1. Vulkan's version number alone is insufficient: the DXVK 2.7 series requires `VK_KHR_maintenance5`, which excludes some older Windows drivers. See the [DXVK 2.7 driver requirements](https://github.com/doitsujin/dxvk/releases/tag/v2.7) and [included DXVK version](https://github.com/doitsujin/dxvk/releases/tag/v2.7.1). The game and its interpolation layer are 32-bit, so the driver must provide the corresponding 32-bit Vulkan support on the 64-bit operating system.

If the Vulkan path cannot start or is unsuitable for your GPU, clear **Frame interpolation** and save to restore dgVoodoo2. Lowering render resolution can reduce GPU load. A disabled checkbox indicates a missing or invalid interpolation component; restore the complete release runtime rather than mixing individual DLL versions.

The component lives under `runtime/windows-framegen`; `.portable/windows-framegen.json` records its file hashes. Renderer changes update the package's integrity entries. Keep the component's bundled notices and licenses with it.

## Implementation and reproducible build

The port retains upstream optical flow/interpolation shaders and adds Windows threading, synchronization and monotonic timing through `native/framegen/windows_compat.c`. QPC provides the monotonic clock. Worker threads hold a balanced `timeBeginPeriod(1)`/`timeEndPeriod(1)` request for wake-up granularity; thread-creation failures release the request as well.

The build pins upstream commit `bc56e5bd0e3a6c328aedef664d0d36363fb58b36`, archive SHA-256 `2fccc4a6238aad1cb58ea69ffb3f775ee9644a18b4c149c987fce6290b273dcd`, and Zig 0.15.2. Supply the local upstream archive, Vulkan headers (`vulkan` and `vk_video`), a compatible glslang executable and the Zig compiler. The script does not download dependencies or read game files. Run from the repository root with a fresh output directory:

```sh
python3 native/framegen/build_windows.py \
  --archive /path/to/pinned-afmf-source.tar.gz \
  --zig /path/to/zig-0.15.2/zig \
  --vulkan-headers /path/to/vulkan-headers/include \
  --glslang /path/to/glslang \
  --output build/afmf-windows-local
```

This applies the included Windows and harness patches, compiles 19 shader permutations, builds both x86/x64 Windows DLLs and synthetic programs, and writes hashes/notices to the output. The Top Spin release uses `win32/afmf32.dll`; the x64 build exercises the same adapter for the second ABI. Source and notices are included in the release payload, while binaries and dependencies enter the ZIP through the reviewed manifest described in [Building](building.md).

Synthetic checks can run under Wine on a Linux Vulkan host with Xvfb and `xvfb-run`:

```sh
python3 native/framegen/run_wine_checks.py \
  --wine /path/to/wine \
  --build build/afmf-windows-local \
  --prefix /path/to/private-wine-prefix
```

The check executes only the generated programs and writes results under the build's `wine-checks` directory; it does not launch or read Top Spin. The programs manually chain each actual Windows layer DLL above Wine Vulkan, read generated pixels and optical flow back from the GPU, and check motion-compensated edges plus identical static frames. Both 32-bit and 64-bit outputs pass those checks; repeated frames and encoded/linear-light alpha blends fail the negative controls. All 19 compiled shader binaries match the Linux reference. This establishes the synthetic interpolation path under Wine, not native Windows Vulkan-loader or in-game execution, which were not performed for this component.

The Windows integration files have their own [MIT license](../native/framegen/LICENSE). Upstream AFMF, AMD FidelityFX, Vulkan headers, compiler/runtime components and DXVK retain their original authorship and notices. See [the component's third-party notices](../native/framegen/THIRD_PARTY_NOTICES.txt) and the release's `licenses/windows-framegen` directory.
