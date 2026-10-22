"""Build a fail-closed public patch archive, never a private game package. djultra64.

A reviewed JSON binary manifest is required; this tool never discovers files in
private build trees. Each entry is {source, destination, sha256, notices:[dest]}.
The three stubs use role input/save_drives/options_delete instead of destination;
the Lua compiler uses role lua. Installer files use role installer and destination
ApplyPatch.exe, runtime-applypatch/... or runtime-installer/... and are never
installed over the game. Role installer_python identifies runtime-installer/python.exe
whose reviewed python314._pth must include ../files for the bundled own sources.
A reviewed platform=linux selects a .tar.gz archive, its bundled Linux interpreter
and executable descriptors; missing platform preserves the legacy Windows ZIP.
Linux install_mode=iso places an ISO setup entrypoint in TopSpin-Installer/,
without adding fields to the patch payload manifest.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import tarfile
import zipfile

SOURCE_FILES = tuple('launcher/' + name + '.py' for name in (
    '__init__', '__main__', 'gui', 'process', 'steam', 'runtime', 'settings',
    'integrity', 'input_devices', 'controllers', 'glyphs', 'windows_display',
    'steam_client', 'steam_artwork', 'windows_framegen')) + tuple('tools/' + name for name in (
    'install_patch.py', 'patch_game.py', 'pml.py', 'controller_config.py',
    'windows_graphics.py', 'windows_runtime.py', 'linux_runtime.py',
    'glyph_install.py', 'glyph_atlas.py', 'pam_archive.py', 'menu_quit.py',
    'menu_quit.lua')) + (
    'portable/TopSpinLauncher.sh', 'portable/TopSpinLauncher.cmd',
    'portable/Play-TopSpin.sh', 'portable/Play-TopSpin.cmd',
    'NOTICE.md', 'licenses/lua-5.0.3/COPYRIGHT')
LINUX_ISO_SOURCE_FILES = ('launcher/installer.py', 'tools/iso_install.py',
    'tools/msi_reader.py', 'tools/build_portable.py')
LINUX_SOURCE_ONLY_FILES = ('patches/gamescope-sdl-clean-shutdown.patch',
    'tools/check_linux_runtime.sh', 'tools/sanitize_linux_gamescope.py')
SOURCE_ONLY_FILES = (
    'tools/build_patch_release.py', 'tools/native_input.py',
    'native/input/input.c', 'native/input/policy.c', 'native/input/policy.h',
    'native/input/engine.c', 'native/input/engine.h', 'native/input/input.ld',
    'patches/portable-path.s', 'patches/portable-save-drives.s',
    'patches/portable-options-delete.s', 'patches/lua50-topspin-format.patch',
    'native/launcher/windows_entry.py', 'native/launcher/PlayTopSpin.cs',
    'native/launcher/requirements-build.txt') + tuple('native/framegen/' + name for name in (
    'LICENSE', 'THIRD_PARTY_NOTICES.txt', 'README.md', 'afmf32.def', 'afmf64.def',
    'build_windows.py', 'check_interpolation.py', 'run_wine_checks.py',
    'windows_compat.c', 'windows_compat.h', 'windows_compat_test.c',
    'windows_golden_check.c', 'windows_harness_bridge.c',
    'windows_harness_bridge.h', 'windows_harness_functions.inc')) + (
    'patches/afmf-windows.patch', 'patches/afmf-windows-harness.patch')
LINUX_REQUIRED_DESTINATIONS = frozenset((
    'runtime/input/SDL3.dll', 'runtime/input/djultra-input.dll',
    'runtime/python/bin/python3', 'runtime/linux/check-abi.sh', '.portable/runtime.json'))
BINARY_DESTINATIONS = frozenset((
    'TopSpinLauncher.exe', 'Play-TopSpin.exe', 'd3d8.dll',
    'runtime/input/SDL3.dll', 'runtime/input/djultra-input.dll'))
PRIVATE_SUFFIXES = {'.pml', '.rui', '.ruirr', '.wad', '.iso', '.msi', '.cab',
                    '.key', '.reg', '.dmp', '.log', '.sav', '.pam'}
STUB_ROLES = {'input', 'save_drives', 'options_delete'}
FRAMEGEN_DESTINATIONS = frozenset((
    'runtime/windows-framegen/afmf32.dll',
    'runtime/windows-framegen/VkLayer_AFMF.json',
    'runtime/windows-framegen/dxvk32/d3d8.dll',
    'runtime/windows-framegen/dxvk32/d3d9.dll',
    'runtime/windows-framegen/dgvoodoo/d3d8.dll',
    '.portable/windows-framegen.json'))
# Exact authentic license text distributed by upstream DXVK v2.7.1.
FRAMEGEN_DXVK_LICENSE = 'licenses/windows-framegen/DXVK-LICENSE.txt'
FRAMEGEN_DXVK_LICENSE_SHA256 = 'a5cb1a6ded7d2d7e92d550ba28edd21be2d1d4044662b399887351023e30ce64'
FRAMEGEN_NOTICES = {
    'licenses/windows-framegen/LICENSE': 'native/framegen/LICENSE',
    'licenses/windows-framegen/THIRD_PARTY_NOTICES.txt': 'native/framegen/THIRD_PARTY_NOTICES.txt',
}


def safe_name(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Unsafe relative path')
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or any(
            part in {'', '.', '..'} or part.endswith((' ', '.')) for part in path.parts):
        raise ValueError('Unsafe relative path: ' + name)
    if (path.suffix.lower() in PRIVATE_SUFFIXES or
        path.name.lower() in {'topspin.exe', 'config.pml'} or
        any(part.lower() in {'artwork', 'steamgriddb', 't', 'u', 'z', '.git', '.agents', '.codex', 'media'} for part in path.parts)):
        raise ValueError('Private game data or personal state: ' + name)
    reserved = {'con', 'prn', 'aux', 'nul'} | {f'{base}{i}' for base in ('com', 'lpt') for i in range(1, 10)}
    if any(part.split('.')[0].lower() in reserved for part in path.parts):
        raise ValueError('Windows device path rejected')
    return name


def checked_read(root, name):
    safe_name(name)
    root = Path(root).resolve()
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Symbolic source rejected: ' + name)
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('Missing or escaping source: ' + name)
    return path.read_bytes()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _binary_destination(name, role, platform='windows'):
    safe_name(name)
    if platform == 'linux':
        allowed = (role == 'overlay' and (
            name.startswith(('licenses/', 'runtime/linux/afmf/', 'runtime/linux/bin/',
                'runtime/linux/gstreamer-1.0/', 'runtime/linux/lib64/', 'runtime/linux/share/',
                'runtime/linux/licenses/', 'runtime/python/bin/', 'runtime/python/lib/',
                'runtime/python/lib64/', 'runtime/python/share/', 'runtime/python/licenses/')) or
            name in LINUX_REQUIRED_DESTINATIONS or name in {
                'runtime/linux/provenance.json', 'runtime/python/provenance.json', 'runtime/python/runtime-build.json',
                'runtime/python/LICENSE', 'runtime/python/LICENSE.txt', 'runtime/input/LICENSE.txt', 'dxvk.conf'}))
        if PurePosixPath(name).suffix.lower() in {'.exe', '.dll'} and name not in {
                'runtime/input/SDL3.dll', 'runtime/input/djultra-input.dll'}:
            allowed = False
        if not allowed:
            raise ValueError('Linux runtime destination is not allowlisted: ' + name)
        return
    if role == 'installer_python':
        allowed = name == 'runtime-installer/python.exe'
    elif role == 'installer':
        allowed = name == 'ApplyPatch.exe' or name.startswith(('runtime-applypatch/', 'runtime-installer/'))
    else:
        allowed = (name in BINARY_DESTINATIONS or name in FRAMEGEN_DESTINATIONS or name.startswith(
            ('runtime-windows-launcher/', 'licenses/')))
    if not allowed:
        raise ValueError('Binary destination is not allowlisted: ' + name)


def prepare_payload(root, reviewed, original_inventory):
    """Validate every byte in memory before creating any output file.

    Reviewed hashes are an explicit provenance decision, not evidence of a
    redistribution license. Notice destinations must accompany runtime files.
    The private original inventory supplies a second defense against renaming
    an original game file to an otherwise allowed runtime filename.
    """
    root = Path(root)
    platform = reviewed.get('platform', 'windows')
    if platform not in {'windows', 'linux'}:
        raise ValueError('Unsupported patch release platform')
    install_mode = reviewed.get('install_mode', 'patch')
    if install_mode not in {'patch', 'iso'} or install_mode == 'iso' and platform != 'linux':
        raise ValueError('ISO installation mode requires a Linux release')
    denied = {item['sha256'] for item in original_inventory['files']}
    if not denied or not all(re.fullmatch('[0-9a-f]{64}', value) for value in denied):
        raise ValueError('A complete private original-file inventory is required')
    output = {}
    folded = set()
    installed_folded = set()
    manifest = {'version': 1, 'author': 'djultra64', 'files': {}, 'stubs': {}}
    if platform == 'linux': manifest['platform'] = platform

    def add(name, data):
        safe_name(name)
        if name.casefold() in folded:
            raise ValueError('Duplicate or Windows path collision: ' + name)
        if digest(data) in denied:
            raise ValueError('Original game content detected: ' + name)
        folded.add(name.casefold())
        output[name] = data
        return {'path': name, 'sha256': digest(data)}

    def overlay(name, data, executable=False):
        safe_name(name)
        descriptor = add('files/' + name, data)
        if executable:
            if platform != 'linux' or not (data.startswith(b'\x7fELF') or data.startswith(b'#!')):
                raise ValueError('Only Linux ELF files or scripts may be executable: ' + name)
            descriptor['executable'] = True
        if name.casefold() in installed_folded:
            raise ValueError('Duplicate installed destination: ' + name)
        installed_folded.add(name.casefold())
        manifest['files'][name] = descriptor

    for name in SOURCE_FILES:
        if platform == 'linux' and name.endswith('.cmd'): continue
        destination = name.removeprefix('portable/') if name.startswith('portable/') else name
        overlay(destination, checked_read(root, name), platform == 'linux' and name.endswith('.sh'))
    for name in SOURCE_ONLY_FILES:
        add('sources/' + name, checked_read(root, name))
    if platform == 'linux':
        for name in LINUX_SOURCE_ONLY_FILES:
            add('sources/' + name, checked_read(root, name))
        overlay('Linux-Readme.md', checked_read(root, 'docs/linux.md'))
        if install_mode == 'iso':
            for name in LINUX_ISO_SOURCE_FILES:
                overlay(name, checked_read(root, name))
    # Only this reviewed CC0 subset; never copy artwork or arbitrary asset trees.
    provenance = json.loads(checked_read(root, 'assets/input/xelu/provenance.json'))
    if provenance['license'] != 'CC0-1.0':
        raise ValueError('Unreviewed controller artwork license')
    for name in ('mapping.json', 'provenance.json', 'Readme.original.txt'):
        overlay('assets/input/xelu/' + name, checked_read(root, 'assets/input/xelu/' + name))
    for item in provenance['files']:
        name = item['file']
        if '/' in name or not name.endswith('.png'):
            raise ValueError('Unexpected controller artwork entry')
        data = checked_read(root, 'assets/input/xelu/' + name)
        if digest(data) != item['sha256']:
            raise ValueError('Controller artwork hash mismatch: ' + name)
        overlay('assets/input/xelu/' + name, data)

    # Own copyright notice is explicit; no project-wide MIT license is implied.
    overlay('licenses/djultra64/NOTICE.md', checked_read(root, 'NOTICE.md'))
    def notice_name(name):
        return isinstance(name, str) and (name.startswith('licenses/') or platform == 'linux' and
            name.startswith(('runtime/linux/licenses/', 'runtime/python/licenses/')))

    entries = reviewed['files']
    destinations = {entry.get('destination') for entry in entries} | {'licenses/djultra64/NOTICE.md'}
    for entry in entries:
        data = checked_read(root, entry['source'])
        if digest(data) != entry['sha256']:
            raise ValueError('Reviewed binary hash mismatch: ' + entry['source'])
        role = entry.get('role', 'overlay')
        if platform == 'linux' and role == 'lua' and not data.startswith((b'\x7fELF', b'#!')):
            raise ValueError('Linux Lua compiler must be an ELF executable or script')
        if role in STUB_ROLES or role == 'lua':
            notices = entry.get('notices', [])
            if not notices or any(not notice_name(notice) or notice not in destinations for notice in notices):
                raise ValueError('Missing build-input license notice: ' + role)
        if role in STUB_ROLES or role == 'lua':
            if role in manifest['stubs'] or role == 'lua' and 'lua' in manifest:
                raise ValueError('Duplicate build role')
            descriptor = add('build-inputs/' + (('lua' if platform == 'linux' else 'lua.exe') if role == 'lua' else role + '.bin'), data)
            if role == 'lua': manifest['lua'] = descriptor
            else: manifest['stubs'][role] = descriptor
        else:
            if role not in {'overlay', 'installer', 'installer_python'}:
                raise ValueError('Unknown binary role')
            name = entry['destination']
            _binary_destination(name, role, platform)
            if not notice_name(name):
                notices = entry.get('notices', [])
                if not notices or any(not notice_name(notice) or notice not in destinations for notice in notices):
                    raise ValueError('Missing reviewed dependency/own-work notices: ' + name)
            if role in {'installer', 'installer_python'}: add(name, data)
            else:
                executable = entry.get('executable', bool((root / entry['source']).stat().st_mode & 0o111) and
                    (data.startswith(b'\x7fELF') or data.startswith(b'#!'))) if platform == 'linux' else False
                if 'executable' in entry and (platform != 'linux' or type(entry['executable']) is not bool):
                    raise ValueError('Executable flags require boolean Linux descriptors')
                overlay(name, data, executable)
    required = LINUX_REQUIRED_DESTINATIONS if platform == 'linux' else BINARY_DESTINATIONS
    if install_mode == 'iso': required = required | {'runtime/linux/bin/cabextract'}
    missing = required - manifest['files'].keys()
    if missing or STUB_ROLES - manifest['stubs'].keys() or 'lua' not in manifest or platform == 'windows' and not ({'ApplyPatch.exe', 'runtime-installer/python.exe'} & output.keys()):
        raise ValueError('Incomplete ' + platform + ' patch payload; missing runtime, compiler, stubs or installer: ' + ', '.join(sorted(missing)))
    if platform == 'linux':
        bootstrap_files = ['runtime/python/bin/python3', 'runtime/linux/check-abi.sh']
        if install_mode == 'iso': bootstrap_files.append('runtime/linux/bin/cabextract')
        for name in bootstrap_files:
            if not manifest['files'][name].get('executable'):
                raise ValueError('Linux bootstrap file must be executable: ' + name)
        from tools.install_patch import validate_linux_runtime
        overlay_bytes = {name: output[item['path']] for name, item in manifest['files'].items()}
        executable_names = [name for name, item in manifest['files'].items() if item.get('executable')]
        with tempfile.TemporaryDirectory(prefix='topspin-linux-validation-') as folder:
            validate_linux_runtime(Path(folder), overlay_bytes, executable_names)
    framegen = FRAMEGEN_DESTINATIONS & manifest['files'].keys()
    if framegen:
        if framegen != FRAMEGEN_DESTINATIONS:
            raise ValueError('Incomplete Windows frame interpolation component')
        for destination, source in FRAMEGEN_NOTICES.items():
            descriptor = manifest['files'].get(destination)
            if descriptor is None or output[descriptor['path']] != checked_read(root, source):
                raise ValueError('Missing or altered Windows frame interpolation notice: ' + destination)
        dxvk_notice = manifest['files'].get(FRAMEGEN_DXVK_LICENSE)
        if dxvk_notice is None or digest(output[dxvk_notice['path']]) != FRAMEGEN_DXVK_LICENSE_SHA256:
            raise ValueError('Missing or altered upstream DXVK v2.7.1 license')
        for name in ('d3d8.dll', 'd3d9.dll'):
            entry = next(entry for entry in entries
                if entry.get('destination') == 'runtime/windows-framegen/dxvk32/' + name)
            if FRAMEGEN_DXVK_LICENSE not in entry.get('notices', []):
                raise ValueError('DXVK DLL must reference its upstream license notice')
        afmf_entry = next(entry for entry in entries
            if entry.get('destination') == 'runtime/windows-framegen/afmf32.dll')
        if not FRAMEGEN_NOTICES.keys() <= set(afmf_entry.get('notices', [])):
            raise ValueError('AFMF DLL must reference its own and upstream license notices')
        # Use the same strict component schema and hash checks as the launcher.
        # Only these reviewed files enter this disposable validation directory.
        from launcher.windows_framegen import component
        with tempfile.TemporaryDirectory(prefix='topspin-framegen-validation-') as folder:
            for name in sorted(framegen):
                path = Path(folder) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(output[manifest['files'][name]['path']])
            component(folder)
    if 'runtime-installer/python.exe' in output:
        required = {'runtime-installer/python314.zip', 'runtime-installer/python314.dll',
                    'runtime-installer/python314._pth'}
        if not required <= output.keys():
            raise ValueError('Incomplete embedded CPython 3.14 installer runtime')
        paths = {line.strip() for line in output['runtime-installer/python314._pth'].decode('utf-8').splitlines()
                 if line.strip() and not line.lstrip().startswith('#')}
        if '../files' not in paths or not paths <= {'../files', '.', 'python314.zip', 'Lib/site-packages', 'import site'}:
            raise ValueError('Embedded Python paths must include ../files and only bundled libraries')
    add('manifest.json', (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    return output



def _build_linux_release(destination, output, install_mode='patch'):
    if not destination.name.endswith('.tar.gz'):
        raise ValueError('Linux patch releases use a .tar.gz destination')
    manifest = json.loads(output['manifest.json'])
    executable = {descriptor['path'] for descriptor in manifest['files'].values()
                  if descriptor.get('executable')}
    executable.add(manifest['lua']['path'])
    command = b'''#!/bin/sh
# Public patch installer, own integration: djultra64.
set -eu
root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
files="$root/.topspin-patch/files"
python_root="$files/runtime/python"
printf '%s\n' 'Preparing the Top Spin patch. This may take a moment.'
# Run the ABI check with the system shell before loading bundled ELF files.
sh "$files/runtime/linux/check-abi.sh" || exit $?
if [ ! -x "$python_root/bin/python3" ]; then
    printf '%s\n' 'The packaged Python interpreter is missing or not executable.' >&2
    exit 1
fi
export PYTHONHOME="$python_root"
export PYTHONPATH="$files"
export PYTHONNOUSERSITE=1
export LD_LIBRARY_PATH="$python_root/lib64"
cd -- "$root"
check_only=0
for argument in "$@"; do
    if [ "$argument" = --check ]; then check_only=1; fi
done
if "$python_root/bin/python3" -s -m tools.install_patch --game-dir "$root" --payload "$root/.topspin-patch" "$@" > "$root/.topspin-patch/install.log" 2>&1; then
    if [ "$check_only" = 1 ]; then
        printf '%s\n' 'Patch validated successfully. No game files were changed.'
    else
        printf '%s\n' 'Patch installed successfully. Open TopSpinLauncher.sh to configure or Play-TopSpin.sh to play.'
    fi
else
    status=$?
    cat "$root/.topspin-patch/install.log" >&2
    printf '%s\n' 'Patch installation failed.' >&2
    exit "$status"
fi
'''
    prefix = 'TopSpin-Installer/' if install_mode == 'iso' else ''
    entrypoint = 'Install-TopSpin.sh' if install_mode == 'iso' else 'Install-Patch.sh'
    if install_mode == 'iso':
        command = b'''#!/bin/sh
# ISO setup bootstrap, own integration: djultra64.
set -eu
root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
files="$root/.topspin-patch/files"
python_root="$files/runtime/python"
# Use the system shell to reject unsupported ABI before loading bundled ELF.
sh "$files/runtime/linux/check-abi.sh" || exit $?
if [ ! -x "$python_root/bin/python3" ]; then
    printf '%s\n' 'The packaged Python interpreter is missing or not executable.' >&2
    exit 1
fi
export PYTHONHOME="$python_root"
export PYTHONPATH="$files"
export PYTHONNOUSERSITE=1
export LD_LIBRARY_PATH="$python_root/lib64"
export TK_LIBRARY="$python_root/share/tk9.0"
export TCL_LIBRARY="$python_root/share/tcl9.0"
cd -- "$root"
if [ "$#" -gt 0 ]; then
    printf '%s\n' 'Preparing Top Spin installation.'
fi
exec "$python_root/bin/python3" -s -m launcher.installer --payload "$root/.topspin-patch" "$@"
'''
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile() as staged:
        with tarfile.open(fileobj=staged, mode='w:gz') as archive:
            for name, data, mode in [(entrypoint, command, 0o755)] + [
                    ('.topspin-patch/' + name, data, 0o755 if name in executable else 0o644)
                    for name, data in sorted(output.items())]:
                info = tarfile.TarInfo(prefix + name)
                info.size = len(data)
                info.mode = mode
                info.uid = info.gid = 0
                info.uname = info.gname = 'djultra64'
                archive.addfile(info, io.BytesIO(data))
        staged.seek(0)
        with destination.open('xb') as target:
            while chunk := staged.read(1024 * 1024): target.write(chunk)
    return {'author': 'djultra64', 'platform': 'linux', 'files': len(output) + 1,
            'payload_bytes': sum(map(len, output.values())), 'tar_gz_bytes': destination.stat().st_size}

def build_release(root, destination, reviewed, original_inventory):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Choose a fresh archive destination')
    output = prepare_payload(root, reviewed, original_inventory)
    if reviewed.get('platform', 'windows') == 'linux':
        return _build_linux_release(destination, output, reviewed.get('install_mode', 'patch'))
    # Extraction changes only the patch staging directory and the new entrypoint.
    if 'runtime-installer/python.exe' in output:
        interpreter = '"%~dp0.topspin-patch\\runtime-installer\\python.exe" -I -m tools.install_patch'
    else:
        interpreter = '"%~dp0.topspin-patch\\ApplyPatch.exe"'
    command = ('@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
        'echo Preparing the Top Spin patch. This may take a moment.\r\n' + interpreter +
        ' --game-dir "%~dp0." --payload "%~dp0.topspin-patch" > "%~dp0.topspin-patch\\install.log" 2>&1\r\n'
        'if errorlevel 1 (\r\n  type "%~dp0.topspin-patch\\install.log"\r\n'
        '  echo Patch installation failed.\r\n  pause\r\n  exit /b 1\r\n)\r\n'
        'echo Patch installed successfully. Open TopSpinLauncher.exe to configure or Play-TopSpin.exe to play.\r\npause\r\n').encode('ascii')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive final creation means an existing archive is never overwritten.
    with tempfile.TemporaryFile() as staged:
        with zipfile.ZipFile(staged, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('Install-Patch.cmd', command)
            for name, data in sorted(output.items()):
                archive.writestr('.topspin-patch/' + name, data)
        staged.seek(0)
        with destination.open('xb') as target:
            while chunk := staged.read(1024 * 1024): target.write(chunk)
    return {'author': 'djultra64', 'files': len(output) + 1,
            'payload_bytes': sum(map(len, output.values())), 'zip_bytes': destination.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--reviewed-binaries', type=Path, required=True)
    parser.add_argument('--original-inventory', type=Path, default=Path('reports/source-inventory.json'))
    args = parser.parse_args()
    print(json.dumps(build_release(args.root, args.destination,
        json.loads(args.reviewed_binaries.read_text()), json.loads(args.original_inventory.read_text())), indent=2))


if __name__ == '__main__':
    main()
