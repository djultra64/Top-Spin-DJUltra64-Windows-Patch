# Anti-aliasing investigation

Research: djultra64 — 2026-10-20. Research only; no package, game configuration, launcher, or runtime was changed and no game was launched for this investigation.

## Recommendation

There is a concrete route on both platforms: Top Spin already has a native **2x MSAA** switch. Validate this original path first. Windows additionally has documented dgVoodoo overrides for 4x/8x MSAA. Neither route is yet a verified working Top Spin AA feature in this project. Keep existing defaults until a focused renderer measurement and one game validation establish correctness.

“FSAA” means full-scene anti-aliasing, rather than fullscreen display mode. MSAA concerns polygon coverage; borderless/windowed versus exclusive fullscreen is a separate setting. [Microsoft overview](https://learn.microsoft.com/en-us/windows/win32/direct3d9/full-scene-antialiasing).

## Original game evidence

Read-only inspection of the current Linux candidate executable found the original `Video/AntiAliasing` Boolean:

- Config reader at `0x57ba81..0x57bab8` stores the Boolean at `0x984779`; default argument is true.
- Device setup at `0x57a749` tests that Boolean. The call at `0x57a776` is `IDirect3D8::CheckDeviceMultiSampleType`, vtable offset `0x2c`, with `MultiSampleType=2`.
- On success, `0x57a77d` writes `2` into `D3DPRESENT_PARAMETERS.MultiSampleType` at object offset `0x2a3bc`. On failure it clears the Boolean at `0x57a789`.
- Therefore the native Boolean requests **2x**, with a capability check and fallback. It does not select 4x or 8x. Static inspection does not establish correct rendering across every game pass.
- `build/TopSpin-Linux-Final-Candidate/Config.pml`, read through our PML parser, currently has `Video/AntiAliasing=false`.

Executable SHA256: `ae971be61f8ba0c1c7a21f8ed1a51f5725e26d10d5a3813ef2f199354b7eef97`. Addresses describe this specific local executable and are research observations, not bytes or an executable distributed in this document. Native Direct3D8 signatures were checked against the already downloaded Wine `d3d8.h` header.

## Windows: dgVoodoo 2.87.5

The original `dgVoodoo.conf` included in the [official 2.87.5 release](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.87.5) supplies the valid AA tokens: `off`, `appdriven`, `2x`, `4x`, `8x`, `16x`, subject to GPU support. The current generated configuration uses `appdriven`; it therefore permits the native game choice, rather than already forcing MSAA.

Concrete prospective settings (not applied):

```ini
[DirectX]
Antialiasing = 4x

[DirectXExt]
RTTexturesForceScaleAndMSAA = true
```

Substitute `2x`/`8x`, or `appdriven` for the original game path. The original template explains that `RTTexturesForceScaleAndMSAA` extends forced resolution/MSAA to render-target textures; keeping it true is the existing configuration. These options can affect multipass rendering, so measure actual D3D11 sample counts and inspect the player, court, videos and UI before offering them as validated presets. [Official wrapper documentation](https://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/).

This conclusion comes from the shipped configuration and SDK, not an assumed generic INI syntax. The prior project ColorSpace mistake is unrelated and must not be repeated: retain the currently corrected `argb8888_sdr`.

## Linux: Proton 11 / DXVK

The installed Proton reports `proton-11.0-2e-x86_64`; its actual 32-bit DXVK `d3d9.dll` contains version string `v2.7`. DXVK removed `d3d9.forceSwapchainMSAA` in **2.7**, explicitly recommending higher rendering resolution through Gamescope when a game lacks built-in MSAA. Do not add that removed setting. [Official 2.7 release notes](https://github.com/doitsujin/dxvk/releases/tag/v2.7).

DXVK D3D8 forwards the application’s multisample type when creating color and depth surfaces, so the game’s own 2x path is materially different from a removed forced-swapchain override. This source behavior supports trying native MSAA; it does not prove Top Spin uses every surface correctly. [Official D3D8 implementation](https://raw.githubusercontent.com/doitsujin/dxvk/v2.7.1/src/d3d8/d3d8_device.cpp).

`d3d9.forceSampleRateShading=True` is **not an MSAA enable switch**: it changes shading frequency when multisampling is already active. Leave it alone for the initial test. [Official configuration comments](https://raw.githubusercontent.com/doitsujin/dxvk/master/dxvk.conf).

Linux currently renders at 3840×2160 and downsamples to a 1920×1080 output. This already shades four times as many pixels as native 1080p, providing spatial supersampling when reduced. At a true 4K output, a 4K internal image has no extra downsampling factor. Frame interpolation adds temporal frames; it does not itself remove spatial aliasing.

## Cost and focused validation

At 4K, one RGBA8 color surface is approximately 31.6 MiB. A color surface plus a same-sized 32-bit depth surface consumes about 126.6/253.1/506.3 MiB at 2x/4x/8x, before resolved images, additional render targets, driver allocation and interpolation buffers. These are storage estimates, not measured performance multipliers. Start with 2x; 4x is an optional desktop-quality candidate, and 8x should remain advanced until measured.

A concrete next validation can reuse the existing own D3D8 renderer probe, request 2/4/8 samples, query returned surface descriptions and underlying D3D11 sample counts, and exercise color/depth creation plus actual drawing. Then validate one controlled Top Spin session including gameplay, replay, menu video and career. No such AA probe or game test was executed during this brief research; no working-MSAA claim is made.
