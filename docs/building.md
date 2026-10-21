# Building and research

Own work: **djultra64**.

This is a source/research workflow. It can extract a compatible local source tree and prepare an early compatibility candidate. It does **not** reproduce all features of the privately assembled Windows/Linux candidates in one step, and it is not a public installer. Keep every output containing original or modified game files private.

## Requirements

Use Python 3.10 or newer and install `requirements.txt` into a virtual environment. Source GUI use additionally requires Python's Tcl/Tk module. The extraction/preparation commands below are intended for Linux or WSL with `cabextract` and GNU binutils (`as`, `objcopy`). Native input compilation also needs GCC with `-m32` support and a GNU linker supporting `i386pe`. Windows launcher freezing must run on Windows with CPython/Tk; see [Windows](windows.md).

Run commands from the repository root. For example, on a development Linux system:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m tkinter
```

The last command opens a Tk check window; close it before continuing. Install Tcl/Tk through your operating system if it is missing. Install system build tools through your distribution's package manager.

## Input compatibility

The executable patch accepts only this exact SHA-256 value:

```text
0bb3090d37956daa625faf917854c84f0263f4472c9235abf1f4c0d68721fe79
```

It identifies the supplied development input, **not a verified clean retail baseline**. The extraction tool checks MSI sizes/hashes and explicitly recognizes a small set of known source variants; accepting one of those variants is not proof that it is an untouched retail file. See `tools/build_portable.py` and `tools/patch_game.py` for the checks. Unknown executable editions and unsupported font/menu variants are rejected. Do not remove the hash guards or change offsets to force a different edition through the tools.

The existing source layout expected by `tools.prepare_portable` is:

```text
<local-media>/TopSpin.msi
<local-media>/<external cabinets named by the MSI>
<local-media>/program files/Atari/TopSpin/TopSpin.exe
<local-media>/program files/Atari/TopSpin/Config.pml
```

Other loose MSI files must also be present where the media layout expects them. A lone installed `TopSpin.exe` is insufficient. Obtain files from your own media; this repository does not provide them or a key. A clean original-media baseline still needs investigation before a generally applicable patch can be released.

## Extract and prepare an early candidate

Use a **new private destination**. Extraction rejects an existing destination. Preparation rewrites the candidate executable and configuration, so do not point it at your installed game, an existing save-bearing package, or your media.

```sh
mkdir -p reports
python -m tools.build_portable --source /path/to/local-media --destination dist/Research-Candidate
python -m tools.prepare_portable --source /path/to/local-media --destination dist/Research-Candidate --width 1920 --height 1080
python -m tools.verify_build --destination dist/Research-Candidate --inventory reports/source-inventory.json
```

Extraction writes `reports/source-inventory.json`; keep it private because it describes your local game files. Preparation applies the version-checked executable changes, corrects the camera aspect, creates local `T`/`U` save roots, preserves the original 50 FPS timing, selects English, disables the game FPS counter and stages launcher source. The original configuration's Security section is retained; generated configuration may contain your key and must stay private.

Verification checks the declared files and hashes. It does not prove rendering, controller behavior, game progress or save compatibility. The generated `portable-build.json` is a development record, not release certification.

## Additional components

The early candidate above does not include the complete native input runtime, generated prompt fonts, video/graphics dependencies, final backbuffer patch, frozen launchers or Quit Game menu changes. Those were assembled and validated separately in private candidates.

The following commands inspect/build individual project components without supplying game code:

```sh
python -m tools.native_input build/native-input
python -m tools.menu_quit --help
python -m tools.windows_runtime --help
python -m tools.windows_direct --help
python -m tools.linux_runtime --help
```

`tools.native_input` builds the project's PE32 DLL; it does not install SDL3, patch an executable to load the hook, or extend game fonts. The local font planner in `tools/glyph_install.py` only accepts the declared original font/texture hashes. There is no complete public installation command for that integration yet.

The Quit Game delta requires a compatible **Lua 5.0.3** interpreter matching the game's bytecode header and the exact original menu archive. Build the dedicated interpreter with [the source patch and recipe](lua-bytecode.md). It writes a separate private output:

```sh
python -m tools.menu_quit /path/to/original/MainMenu.rui /path/to/private-output/MainMenu.rui --lua /path/to/compatible/lua
```

Do not replace a game's menu with an unverified output. The delta preserves original menu data and animation and rejects unknown or already patched input. See [Windows](windows.md) and [Linux](linux.md) for platform runtime requirements.

## Tests and private packaging

The complete suite is available with:

```sh
python -m unittest discover -s tests
```

Tests needing private version-locked media, extracted fixtures, compiler tools or staged dependencies report a skip when those prerequisites are unavailable. A clean source checkout can run the independent tests without game files. A supplied executable fixture must still match its supported hash; incompatible fixtures fail rather than being treated as missing. Synthetic launcher/input tests do not constitute real-controller validation. Set `TOPSPIN_TEST_EXE` only to a private supported executable fixture when running those integration tests.

After a complete candidate has been assembled and validated, the package tool can make a **private local copy** using its original inventory:

```sh
python -m tools.package_portable /path/to/assembled-candidate /path/to/new-private-package --inventory reports/source-inventory.json --platform windows
```

Choose `--platform linux` for a Linux copy. Output contains game files and may contain personal configuration. Never publish it, its ZIP, the extracted source, or generated game resources to GitHub. Public source publication and a future distributable patch are separate operations.
