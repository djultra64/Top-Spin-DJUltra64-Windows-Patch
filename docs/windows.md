# Windows installation and use

Own work: **djultra64**.

## Requirements

Use Windows 10/11 with a graphics driver supporting the included Direct3D 11 presentation path, .NET Framework 4 for the direct Play executable, and your own compatible Top Spin PC game folder. The patch includes its installer and launcher runtimes; you do not need to install Python or Lua.

Use a folder your account can write to. Close the game and launcher before installation. The patch does not include the original game or a key, and it does not add a CD-key/licensing bypass.

## Install the release ZIP

1. Download [TopSpin-DJUltra64-Windows-Patch-v0.1.0.zip](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/download/v0.1.0/TopSpin-DJUltra64-Windows-Patch-v0.1.0.zip) from [v0.1.0](https://github.com/djultra64/Top-Spin-DJUltra64-Windows-Patch/releases/tag/v0.1.0).
2. Extract its contents directly into the folder containing `TopSpin.exe`. Do not leave the patch inside an extra nested folder.
3. Double-click **`Install-Patch.cmd`**. Wait for **Patch installed successfully**.
4. Open **`TopSpinLauncher.exe`**, adjust settings if desired and select **Save settings** or **Play**.
5. For later sessions, use **`Play-TopSpin.exe`** to launch immediately with saved settings.

After extraction, the folder should look like this:

```text
Your game folder/
  TopSpin.exe
  Config.pml
  Media/
  Install-Patch.cmd
  .topspin-patch/
```

Extraction stages installer files. The installer checks the executable, original menu/font variants and payload hashes, generates the changes, and only then writes game files. It adds the compatibility/input hooks, prompt resources, Quit Game row, launcher and graphics runtime. Originals replaced by the installer are saved under `.portable/backups/topspin-patch-v1`; `.portable/patch-install.json` records the installation.

Keep the backup and receipt. They can contain original game content and personal configuration, so do not upload them. The installer preserves the configuration's Security section and existing keyboard profiles and keeps existing `T`/`U` saves. Re-running the same installer recognizes an intact installation; it refuses to overwrite a conflicting backup or a modified installation.

## Supported executable versions

The SHA-256 of `TopSpin.exe` must be one of these exact values:

| Input | SHA-256 |
| --- | --- |
| Supported source input | `0bb3090d37956daa625faf917854c84f0263f4472c9235abf1f4c0d68721fe79` |
| Supported earlier assembled input | `ae971be61f8ba0c1c7a21f8ed1a51f5725e26d10d5a3813ef2f199354b7eef97` |
| Supported Windows assembled input | `1360e0819c49ee1c8acaffc7c3b01f57f89af74409d3e2b633931afe0f8d9a9f` |

Matching resource variants are also required. Already changed menu/font archives without a matching installation receipt are not interchangeable with original resources. Support for these inputs does not establish compatibility with every retail edition or identify an untouched original-media executable.

To inspect your executable from PowerShell in the game folder:

```powershell
Get-FileHash .\TopSpin.exe -Algorithm SHA256
```

An unsupported executable is rejected before game writes. Keep your own original files; do not replace them with an unknown download to satisfy a hash check.

## Graphics and controls

Defaults are **3840 × 2160 render / 1920 × 1080 output**, full-screen presentation, English and Xbox 360 prompts. The game-specific dgVoodoo2 runtime presents the internal backbuffer at the selected output size. Choose an output size supported by your screen; lower the render size if needed. Gameplay uses the corrected 16:9 camera. Original menus can stretch.

Original timing stays at **50 FPS gameplay / 30 FPS replays and cinematics** with synchronization enabled. Windows frame generation/interpolation is not included; leave Frame generation off.

Choose **Controller button style** for Keyboard, Xbox, PlayStation or Nintendo Switch. Optional bindings map actions to physical positions in both menus and gameplay. Switch south/east/west/north positions are **B / A / Y / X**, while Xbox uses **A / B / X / Y**. **Auto detect (experimental)** follows the last active device where available; select a manual family when you want fixed prompts or detection is ambiguous.

## Settings, saves and Steam

Launcher settings are in `.portable/launcher.json`; game options/profiles are under local `T` and `U` folders. Keep them when moving or backing up your copy. Do not mix runtime files from different releases.

**Check game files for integrity** reports missing or changed immutable game/runtime files. Settings and saves are excluded. **Add to Steam** saves settings and registers a shortcut; it may close and reopen Steam normally. After moving the game folder, remove the old Steam shortcut and add it again.

## Troubleshooting

For an unsupported executable or resource error, check the hashes and use your own matching game files. Do not disable the version checks. For a payload checksum error, extract a fresh copy of the release ZIP and keep the entire `.topspin-patch` folder together.

For permission errors, use a user-writable game folder. If installation reports an interrupted operation or conflicting backup, keep `.portable/backups/topspin-patch-v1`, `.portable/patch-install.json` and any `.portable/install.lock` while investigating; deleting them removes recovery information. There is no automatic uninstall command in this release.

Logs are in `.portable/logs`; native controller initialization status is in `.portable/input-status.txt`. Developer launcher builds and diagnostic commands are described in [Building](building.md) and [the native launcher guide](../native/launcher/README.md).

When reporting a problem on GitHub, share the error text and relevant hashes, never your original game files, generated resources, configuration containing keys, or private backup.
