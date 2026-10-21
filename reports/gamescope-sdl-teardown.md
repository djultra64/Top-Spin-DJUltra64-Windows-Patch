# Gamescope SDL shutdown correction

Integration and validation: djultra64. Gamescope and its dependencies retain
their authentic authors and license notices.

## Delivered runtime

The corrected, separately staged runtime is:
`build/Gamescope-SDL-Fixed-Staging/runtime/linux`.

It was built from exact Gamescope commit
`c31743d9da2f788faad3b9e202a10bf6f49c75d9`, matching the packaged source version,
using the **already installed** Freedesktop SDK 25.08. No SDK or host packages
were installed. Missing development headers were extracted from matching
Fedora RPMs into the workspace and linked against the existing runtime library
closure. Source and dependency pins, SDK revision, header RPM hashes, build
options and patch hash are retained in:
`runtime/linux/licenses/gamescope-source-build/source-build.json`.

The initial host-only toolchain check missed this installed SDK; this report
supersedes that earlier assessment. The executable has no build-only RPATH.
The runtime keeps its existing glibc 2.42 requirement. This is not a claim of
compatibility with older Linux distributions.

The final source patch is `patches/gamescope-sdl-clean-shutdown.patch`. It changes
four source files. Authentic Gamescope, wlroots, libliftoff, libdisplay-info,
GLM, stb, ReShade, SPIR-V-Headers, vkroots and sol2 notices are retained alongside
its source-build metadata. The existing dependency notices remain intact.

No active game folder or mapped runtime was overwritten. The launcher backend
remains **SDL with X11**, preserving the previously validated visible window.
No game was launched during this investigation and no OS controls were injected.

## Evidence and resulting changes

The original compositor reproduced `SIGABRT` (`-6`) with `/usr/bin/true`, with FG
both off and on. GDB identified:

```text
std::terminate()
gamescope::CSDLBackend::~CSDLBackend()
gamescope::IBackend::Set(...)
steamcompmgr_exit()
```

Its SDL backend owned a joinable thread without stopping or joining it. The
correction supplies a stop flag, a private wake event, bounded event waiting and
a join before backend state is destroyed. The startup wait for Wayland readiness
also observes the stop flag, so a destructor cannot wait indefinitely merely
because readiness was never reached. The SDL thread now starts after all state
it uses has been initialized.

Rendering-client tests then exposed a second pre-existing shutdown defect:

```text
CVBlankTimer::CalcNextWakeupTime()
CVBlankTimer::ArmNextVBlank()
present_wait_thread_func()
```

The detached Vulkan presentation waiter could access the backend after it had
been cleared. It is now an owned `std::jthread`, with a stop callback that wakes
its atomic wait. Shutdown requests stop and joins it **before** clearing the
backend. An outstanding Vulkan presentation wait is bounded at the existing
one-second timeout. No exit code or exception is suppressed.

The runtime wrapper also checks that the bundled Xwayland is a regular,
executable file before starting Gamescope. This avoids entering an unrelated
upstream startup wait if that package component is missing. The same guard is
implemented in `tools/linux_runtime.py`; its regression covers missing,
non-executable and directory paths plus successful delegation.

## Completed controls

All tests use disposable programs, not Top Spin:

| Control | Result |
| --- | --- |
| `/usr/bin/true`, FG off | compositor exit 0 |
| `/usr/bin/true`, FG on | compositor exit 0 |
| Vulkan cube, 90 real presents, FG off | compositor exit 0 |
| Vulkan cube, 90 real presents, FG on | compositor exit 0 |
| Invalid X11 display | exit 1 in 0.03 seconds |
| Missing bundled Xwayland through supported wrapper | exit 1 in 0.004 seconds |
| Vulkan 1.1 cube after RPATH removal | 90 presents, optical-flow interpolation initialized, exit 0 |

The Vulkan 1.1 control uses a test-only loader shim in the disposable cube's own
process. Its AFMF log confirms `interpolation ready: 1280x720`, 90 application
presents and 28 generated frames. The shim is not included in the game runtime.
The earlier stock cube advertises Vulkan 1.0, so those controls exercised repeated
companion frames rather than optical-flow shader initialization.

Artifacts are retained under `reports/runtime/`, including:

- `gamescope-teardown-gdb.txt`: original abort.
- `gamescope-fixed-cube-segv-gdb.txt`: presentation-waiter lifetime defect.
- `gamescope-fixed-results.json`: final normal/display-failure controls.
- `gamescope-fixed-poststrip-flow-cube.log`: optical flow and 90 presents.
- `gamescope-wrapper-preflight.json`: missing-Xwayland guard.
- `gamescope-fixed-dependency-audit.json`: executable hash, ABI and resolved DSOs.
- `gamescope-sdk-build.log`: isolated build evidence.

Primary source:
https://github.com/ValveSoftware/gamescope/tree/c31743d9da2f788faad3b9e202a10bf6f49c75d9

## Practical limits

Top Spin has not been run with this rebuilt compositor. Its previously validated
4K/video/controller/FG behavior still requires separate real-game confirmation
before describing this exact runtime as user-validated.

Gamescope returns 0 even for `/usr/bin/false`; its process status therefore does
not establish the primary child's exit status. The real game's earlier log only
reported that the primary child shut down. Neither that line nor this compositor
fix establishes whether the real game itself exited successfully.

Directly bypassing the supported wrapper and forcing a nonexistent Xwayland
path still enters an upstream wlroots startup wait (the control was stopped
after 15 seconds). The new package wrapper rejects its missing Xwayland before
that path. No broad wlroots startup rewrite was attempted.

The native Wayland backend exited cleanly in separate disposable controls but
was not selected: an earlier user test did not show the game window with that
backend. No backend default or frozen Windows launcher was changed.
