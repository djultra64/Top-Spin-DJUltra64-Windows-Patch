"""Build a fail-closed public patch ZIP, never a private game package. djultra64.

A reviewed JSON binary manifest is required; this tool never discovers files in
private build trees. Each entry is {source, destination, sha256, notices:[dest]}.
The three stubs use role input/save_drives/options_delete instead of destination;
the Lua compiler uses role lua. Installer files use role installer and destination
ApplyPatch.exe, runtime-applypatch/... or runtime-installer/... and are never
installed over the game. Role installer_python identifies runtime-installer/python.exe
whose reviewed python314._pth must include ../files for the bundled own sources.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

SOURCE_FILES = tuple('launcher/' + name + '.py' for name in (
    '__init__', '__main__', 'gui', 'process', 'steam', 'runtime', 'settings',
    'integrity', 'input_devices', 'controllers', 'glyphs', 'windows_display',
    'steam_client', 'steam_artwork')) + tuple('tools/' + name for name in (
    'install_patch.py', 'patch_game.py', 'pml.py', 'controller_config.py',
    'windows_graphics.py', 'windows_runtime.py', 'linux_runtime.py',
    'glyph_install.py', 'glyph_atlas.py', 'pam_archive.py', 'menu_quit.py',
    'menu_quit.lua')) + (
    'portable/TopSpinLauncher.sh', 'portable/TopSpinLauncher.cmd',
    'portable/Play-TopSpin.sh', 'portable/Play-TopSpin.cmd',
    'NOTICE.md', 'licenses/lua-5.0.3/COPYRIGHT')
SOURCE_ONLY_FILES = (
    'tools/build_patch_release.py', 'tools/native_input.py',
    'native/input/input.c', 'native/input/policy.c', 'native/input/policy.h',
    'native/input/engine.c', 'native/input/engine.h', 'native/input/input.ld',
    'patches/portable-path.s', 'patches/portable-save-drives.s',
    'patches/portable-options-delete.s', 'patches/lua50-topspin-format.patch',
    'native/launcher/windows_entry.py', 'native/launcher/PlayTopSpin.cs',
    'native/launcher/requirements-build.txt')
BINARY_DESTINATIONS = frozenset((
    'TopSpinLauncher.exe', 'Play-TopSpin.exe', 'd3d8.dll',
    'runtime/input/SDL3.dll', 'runtime/input/djultra-input.dll'))
PRIVATE_SUFFIXES = {'.pml', '.rui', '.ruirr', '.wad', '.iso', '.msi', '.cab',
                    '.key', '.reg', '.dmp', '.log', '.sav', '.pam'}
STUB_ROLES = {'input', 'save_drives', 'options_delete'}


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


def _binary_destination(name, role):
    safe_name(name)
    if role == 'installer_python':
        allowed = name == 'runtime-installer/python.exe'
    elif role == 'installer':
        allowed = name == 'ApplyPatch.exe' or name.startswith(('runtime-applypatch/', 'runtime-installer/'))
    else:
        allowed = (name in BINARY_DESTINATIONS or name.startswith(
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
    denied = {item['sha256'] for item in original_inventory['files']}
    if not denied or not all(re.fullmatch('[0-9a-f]{64}', value) for value in denied):
        raise ValueError('A complete private original-file inventory is required')
    output = {}
    folded = set()
    manifest = {'version': 1, 'author': 'djultra64', 'files': {}, 'stubs': {}}

    def add(name, data):
        safe_name(name)
        if name.casefold() in folded:
            raise ValueError('Duplicate or Windows path collision: ' + name)
        if digest(data) in denied:
            raise ValueError('Original game content detected: ' + name)
        folded.add(name.casefold())
        output[name] = data
        return {'path': name, 'sha256': digest(data)}

    def overlay(name, data):
        safe_name(name)
        descriptor = add('files/' + name, data)
        if name.casefold() in {key.casefold() for key in manifest['files']}:
            raise ValueError('Duplicate installed destination: ' + name)
        manifest['files'][name] = descriptor

    for name in SOURCE_FILES:
        destination = name.removeprefix('portable/') if name.startswith('portable/') else name
        overlay(destination, checked_read(root, name))
    for name in SOURCE_ONLY_FILES:
        add('sources/' + name, checked_read(root, name))
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
    entries = reviewed['files']
    destinations = {entry.get('destination') for entry in entries} | {'licenses/djultra64/NOTICE.md'}
    for entry in entries:
        data = checked_read(root, entry['source'])
        if digest(data) != entry['sha256']:
            raise ValueError('Reviewed binary hash mismatch: ' + entry['source'])
        role = entry.get('role', 'overlay')
        if role in STUB_ROLES or role == 'lua':
            notices = entry.get('notices', [])
            if not notices or any(not notice.startswith('licenses/') or notice not in destinations for notice in notices):
                raise ValueError('Missing build-input license notice: ' + role)
        if role in STUB_ROLES or role == 'lua':
            if role in manifest['stubs'] or role == 'lua' and 'lua' in manifest:
                raise ValueError('Duplicate build role')
            descriptor = add('build-inputs/' + ('lua.exe' if role == 'lua' else role + '.bin'), data)
            if role == 'lua': manifest['lua'] = descriptor
            else: manifest['stubs'][role] = descriptor
        else:
            if role not in {'overlay', 'installer', 'installer_python'}:
                raise ValueError('Unknown binary role')
            name = entry['destination']
            _binary_destination(name, role)
            if not name.startswith('licenses/'):
                notices = entry.get('notices', [])
                if not notices or any(not notice.startswith('licenses/') or notice not in destinations for notice in notices):
                    raise ValueError('Missing reviewed dependency/own-work notices: ' + name)
            if role in {'installer', 'installer_python'}: add(name, data)
            else: overlay(name, data)
    missing = BINARY_DESTINATIONS - manifest['files'].keys()
    if missing or STUB_ROLES - manifest['stubs'].keys() or 'lua' not in manifest or not ({'ApplyPatch.exe', 'runtime-installer/python.exe'} & output.keys()):
        raise ValueError('Incomplete Windows patch payload; missing runtime, compiler, stubs or Windows installer: ' + ', '.join(sorted(missing)))
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


def build_release(root, destination, reviewed, original_inventory):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Choose a fresh ZIP destination')
    output = prepare_payload(root, reviewed, original_inventory)
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
