# Isolated Windows graphics diagnostics

These are our own programs by djultra64. They require no game files and never
send keyboard, mouse or gamepad events. They create one temporary window and
exit after drawing their own colored triangle.

`python -m tools.windows_graphics_probe` builds the freestanding PE32
`build/native-graphics-probe/NativeGraphicsProbe.exe` with GNU binutils/GCC.
Run it in an **interactive Windows console session**, in a private working folder
containing the official x86 dgVoodoo2 `d3d8.dll`, its config, and official
MinHook 1.3.4 `MinHook.x86.dll`. Dependencies are not copied into source control.
The MinHook BSD license must accompany any redistribution of this diagnostic.

The probe observes only its own process: it detours D3D11 device creation, then
logs actual texture sizes created by that returned device. Its normal test
requests a 3840×2160 D3D8 backbuffer while creating a 1920×1080 borderless window.
The result is written beside its executable as `native-resolution-probe.txt`.
It exits only its own diagnostic process, reclaiming its private GPU resources.

`ResolutionProbe.cs` is the earlier managed instrumented variant, including
actual D3D11 bound-target dimensions, DXGI swapchain sizes and optional official
debug-wrapper messages. `ConfigProbe.cs` uses the official dgVoodoo API to read
parsed config values; it expects its official API DLL and SDK-generated default
config structure. These are investigation tools, not launcher components.

The native 4K-backbuffer / 1080p-window control passed on the project's Windows
machine (RTX 2060). This establishes that presentation route, not Top Spin's
in-game rendering or gameplay timing. Those require their separate validation.
