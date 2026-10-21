"""Apply a source-only, version-locked patch to the user's private game. djultra64.

The public archive extracts under .topspin-patch first. Nothing in the game is
changed until executable, resources and every payload hash have been checked.
Original executable/config/resources remain PRIVATE under .portable/backups.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import zipfile

from tools.patch_game import (SOURCE_SHA256, WINDOWED_BACKBUFFER_SOURCE_SHA256,
                              patch_executable, patch_windowed_backbuffer)

WINDOWS_SHA256 = '1360e0819c49ee1c8acaffc7c3b01f57f89af74409d3e2b633931afe0f8d9a9f'
BACKUP = '.portable/backups/topspin-patch-v1'
RECEIPT = '.portable/patch-install.json'
MENU = 'Media/MenuPart/RuiPC/MainMenu.rui'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(root: Path, name: str) -> Path:
    """Reject links, Windows drive syntax, traversal and ambiguous separators."""
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\0' in name:
        raise ValueError('Unsafe patch path.')
    relative = PurePosixPath(name)
    reserved = {'con', 'prn', 'aux', 'nul'} | {f'{prefix}{i}' for prefix in ('com', 'lpt') for i in range(1, 10)}
    if any(p.endswith((' ', '.')) or p.split('.')[0].lower() in reserved for p in relative.parts):
        raise ValueError('Ambiguous Windows patch path: '+name)
    if relative.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('Unsafe patch path: '+name)
    candidate = root
    for part in relative.parts:
        candidate = candidate/part
        if candidate.is_symlink():
            raise ValueError('Symbolic links are not supported: '+name)
        if candidate.exists() and candidate != root/relative and not candidate.is_dir():
            raise ValueError('A patch parent is not a directory: '+name)
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError('Patch path escapes the game folder.')
    return candidate


def payload_bytes(payload: Path, descriptor: dict) -> bytes:
    if not isinstance(descriptor, dict) or set(descriptor) != {'path', 'sha256'}:
        raise ValueError('Invalid payload file descriptor.')
    raw = safe_path(payload, descriptor['path']).read_bytes()
    if digest(raw) != descriptor['sha256']:
        raise ValueError('Payload checksum mismatch: '+descriptor['path'])
    if not raw:
        raise ValueError('Empty payload files are not supported.')
    return raw


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True)+'\n').encode('utf-8')


def _protected(name):
    lower = name.lower()
    first = lower.split('/')[0]
    return (first in ('t', 'u', '.topspin-patch') or
            lower.startswith('.portable/backups/') or
            lower in ('securityconfig.pml', RECEIPT.lower()) or
            first in ('.git', '.agents', '.codex'))


def _overlay_allowed(name):
    lower = name.lower()
    first = lower.split('/')[0]
    if _protected(name) or first == 'media' or lower in ('topspin.exe', 'config.pml'):
        return False
    if lower.endswith('.exe'):
        return lower in ('play-topspin.exe', 'launcher-topspin.exe', 'topspinlauncher.exe') or first == 'runtime'
    if lower.endswith(('.pml', '.rui', '.ruirr', '.wad', '.pam')):
        return False
    return True


def installed_receipt(game: Path):
    path = safe_path(game, RECEIPT)
    if not path.exists():
        return None
    receipt = json.loads(path.read_text(encoding='utf-8'))
    if receipt.get('version') != 1 or receipt.get('author') != 'djultra64' or not isinstance(receipt.get('files'), dict):
        raise ValueError('Unsupported installation receipt.')
    from launcher.integrity import is_mutable
    has_framegen = safe_path(game, '.portable/windows-framegen.json').exists()
    if has_framegen:
        validate_renderer_state(game)
    for name, record in receipt['files'].items():
        if (is_mutable(name) and name != '.portable/windows-framegen.json') or (
                has_framegen and name == '.portable/windows-graphics.json'):
            continue
        current = safe_path(game, name)
        if not current.is_file() or digest(current.read_bytes()) != record['sha256']:
            if name in ('d3d8.dll', 'd3d9.dll') and has_framegen:
                continue
            from launcher.glyphs import BASELINE_SHA256, plan_prompt_style
            if name in BASELINE_SHA256 and current.is_file():
                state = json.loads(safe_path(game, '.portable/glyphs/style.json').read_text())
                # Validate the actual selected family against the private baseline
                # rather than treating a normal launcher change as corruption.
                plan_prompt_style(game, state['family'], state['positions'])
                continue
            raise ValueError('The installed patch has changed: '+name+'. Restore your private backup before reinstalling.')
    return receipt


def plan_windows_configuration(settings):
    from tools.windows_graphics import make_config
    return {'dgVoodoo.conf': make_config(settings.internal_resolution,
                                       settings.output_resolution,
                                       fullscreen=False).encode('ascii'),
            '.portable/windows-graphics.json': json_bytes({'version': 1, 'backend': 'dgvoodoo2'})}


def prepare_prompt_styles(changes, family):
    """Keep generated keyboard archives private before selecting initial icons."""
    from launcher.glyphs import BASELINE_SHA256, _style_archive
    for name, expected in BASELINE_SHA256.items():
        baseline = changes.get(name)
        if baseline is None or digest(baseline) != expected:
            raise ValueError('Generated prompt baseline differs from the supported release: '+name)
        changes['.portable/glyphs/baseline/'+name] = baseline
        changes[name] = _style_archive(baseline, family, '01234567')
    changes['.portable/glyphs/style.json'] = (json.dumps(
        {'version': 1, 'family': family, 'positions': '01234567'}, indent=2)+'\n').encode()


def build_install_integrity(game, changes):
    """Cover original game/runtime files as well as locally generated outputs."""
    from launcher.integrity import is_mutable
    names = set(changes)
    # These descriptors live beside private backups and settings, so their
    # immutable membership must survive upgrades without crawling .portable.
    for name in ('.portable/input.json', '.portable/runtime.json',
                 '.portable/windows-graphics.json', '.portable/windows-framegen.json'):
        path = safe_path(game, name)
        if path.is_file():
            names.add(name)
    excluded = {'.topspin-patch', '.git', '.agents', '.codex', 't', 'u', 'z'}
    for directory, folders, files in os.walk(game, followlinks=False):
        parent = Path(directory)
        relative = parent.relative_to(game)
        folders[:] = [folder for folder in folders
                      if (relative.parts or folder.lower() not in excluded)
                      and not (parent/folder).is_symlink()
                      and (relative.parts or folder != '.portable')]
        for filename in files:
            name = (relative/filename).as_posix()
            if is_mutable(name):
                continue
            safe_path(game, name)
            names.add(name)
    result = []
    for name in sorted(names):
        if is_mutable(name):
            continue
        path = safe_path(game, name)
        if name in changes:
            size, checksum = len(changes[name]), digest(changes[name])
        else:
            checksum = hashlib.sha256()
            with path.open('rb') as stream:
                while block := stream.read(1024*1024):
                    checksum.update(block)
            size, checksum = path.stat().st_size, checksum.hexdigest()
        result.append({'path': name, 'size': size, 'sha256': checksum})
    return {'version': 1, 'files': result}


def validated_payload(game, payload):
    payload = Path(payload).absolute()
    if payload.is_symlink():
        raise ValueError('The payload folder must not be a symbolic link.')
    manifest_raw = safe_path(payload, 'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    if (set(manifest) not in ({'version', 'files', 'stubs', 'lua'},
                               {'version', 'author', 'files', 'stubs', 'lua'})
            or manifest['version'] != 1 or manifest.get('author', 'djultra64') != 'djultra64'):
        raise ValueError('Unsupported patch payload manifest.')
    changes = {}
    for name, descriptor in manifest['files'].items():
        safe_path(game, name)
        if not _overlay_allowed(name):
            raise ValueError('Payload would overwrite protected game content: '+name)
        changes[name] = payload_bytes(payload, descriptor)
    for required in ('runtime/input/djultra-input.dll', 'runtime/input/SDL3.dll', 'd3d8.dll'):
        if required not in changes:
            raise ValueError('Required controller runtime missing from payload: '+required)
    stubs = manifest['stubs']
    if set(stubs) != {'input', 'save_drives', 'options_delete'}:
        raise ValueError('The three prepared portability stubs are required.')
    prepared = {key: payload_bytes(payload, descriptor) for key, descriptor in stubs.items()}
    payload_bytes(payload, manifest['lua'])
    validate_framegen_payload(changes)
    return changes, prepared, manifest['lua'], digest(manifest_raw)


def validate_framegen_payload(overlay):
    from launcher.windows_framegen import FILES, MANIFEST, component
    selected = set(FILES) | {MANIFEST}
    if not (selected & overlay.keys()):
        return
    if not selected <= overlay.keys():
        raise ValueError('The complete Windows interpolation component is required.')
    # Only redistributable runtime bytes enter this scratch tree, never assets.
    with tempfile.TemporaryDirectory(prefix='topspin-runtime-preflight-') as folder:
        root = Path(folder)
        for name in selected:
            path = safe_path(root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(overlay[name])
        return component(root)


def validate_renderer_state(game):
    """Recognize only the packaged default or a fully validated local switch."""
    from tools.windows_graphics import DLL_SHA256
    d8 = safe_path(game, 'd3d8.dll')
    framegen_manifest = safe_path(game, '.portable/windows-framegen.json')
    if not framegen_manifest.exists():
        if safe_path(game, 'd3d9.dll').exists():
            raise ValueError('An unrecognized d3d9.dll is installed; preserve the custom wrapper before upgrading.')
        if d8.exists() and digest(d8.read_bytes()) != DLL_SHA256:
            raise ValueError('Unrecognized d3d8.dll; preserve the custom renderer and restore the packaged wrapper before upgrading.')
        return 'dgvoodoo2'
    from launcher.windows_framegen import component
    components = component(game)
    graphics = json.loads(safe_path(game, '.portable/windows-graphics.json').read_text())
    if (not isinstance(graphics, dict) or set(graphics) not in
            ({'version', 'backend'}, {'version', 'backend', 'renderer'}) or
            graphics.get('version') != 1 or graphics.get('backend') != 'dgvoodoo2'):
        raise ValueError('Unsupported Windows renderer state.')
    selected = graphics.get('renderer', 'dgvoodoo2')
    if selected not in ('dgvoodoo2', 'dxvk-afmf'):
        raise ValueError('Unsupported Windows renderer selection.')
    expected = components['dxvk32/d3d8.dll' if selected == 'dxvk-afmf' else 'dgvoodoo/d3d8.dll']
    if not d8.is_file() or d8.read_bytes() != expected:
        raise ValueError('The selected Windows renderer differs from its validated component.')
    d9 = safe_path(game, 'd3d9.dll')
    if selected == 'dxvk-afmf':
        if not d9.is_file() or d9.read_bytes() != components['dxvk32/d3d9.dll']:
            raise ValueError('The selected Windows Direct3D 9 renderer is missing or changed.')
    elif d9.exists():
        raise ValueError('An unexpected d3d9.dll is installed; preserve it before upgrading.')
    return selected


def plan_upgrade(game, payload, receipt):
    overlay, _stubs, _lua, manifest_hash = validated_payload(game, payload)
    selected_renderer = validate_renderer_state(game)
    if receipt.get('payload_manifest_sha256') == manifest_hash:
        return {}, receipt
    preserve = {'dgVoodoo.conf', 'd3d8.dll', '.portable/launcher.json',
                '.portable/input.json', '.portable/windows-graphics.json'}
    changes = {}
    for name, raw in overlay.items():
        if name in preserve or name.startswith('.portable/glyphs/'):
            continue
        path = safe_path(game, name)
        if not path.is_file() or path.read_bytes() != raw:
            changes[name] = raw
    new_component = validate_framegen_payload(overlay)
    if new_component is not None:
        selected_d8 = new_component['dxvk32/d3d8.dll' if selected_renderer == 'dxvk-afmf' else 'dgvoodoo/d3d8.dll']
        if safe_path(game, 'd3d8.dll').read_bytes() != selected_d8:
            changes['d3d8.dll'] = selected_d8
        if selected_renderer == 'dxvk-afmf' and safe_path(game, 'd3d9.dll').read_bytes() != new_component['dxvk32/d3d9.dll']:
            changes['d3d9.dll'] = new_component['dxvk32/d3d9.dll']
    # Local game resources remain untouched. Integrity includes unchanged game
    # bytes, authorized renderer/font state and the complete new runtime.
    changes['.portable/integrity.json'] = json_bytes(build_install_integrity(game, changes))
    metadata = dict(receipt)
    metadata.update(operation='upgrade', status='validated',
                    payload_manifest_sha256=manifest_hash,
                    _previous_receipt_sha256=digest(safe_path(game, RECEIPT).read_bytes()))
    return changes, metadata


def plan_install(game: Path, payload: Path):
    """Validate and construct all output bytes in memory, without game writes."""
    game = Path(game).absolute()
    if game.is_symlink() or not game.is_dir():
        raise ValueError('Choose an existing, non-symlink game folder.')
    raw = safe_path(game, 'TopSpin.exe').read_bytes()
    source_hash = digest(raw)
    if source_hash not in (SOURCE_SHA256, WINDOWED_BACKBUFFER_SOURCE_SHA256, WINDOWS_SHA256):
        raise ValueError('Unsupported TopSpin.exe. This patch requires the exact supported game version.')
    receipt = installed_receipt(game)
    if receipt:
        return plan_upgrade(game, payload, receipt)
    validate_renderer_state(game)
    if safe_path(game, BACKUP).exists():
        raise ValueError('A private backup already exists without a valid receipt. Recover it before installing.')
    # Reject linked media before planners can read anything outside this tree.
    media = safe_path(game, 'Media')
    for entry in media.rglob('*'):
        if entry.is_symlink():
            raise ValueError('Symbolic links are not supported in game media.')
    changes, prepared, lua_descriptor, manifest_hash = validated_payload(game, payload)
    if source_hash == SOURCE_SHA256:
        raw = patch_executable(raw, prepared['input'], 16/9,
                               fix_options_save=True, fix_career_storage=True,
                               fix_creator_camera_input=True,
                               save_paths_stub=prepared['save_drives'],
                               delete_options_stub=prepared['options_delete'])
        if digest(raw) != WINDOWED_BACKBUFFER_SOURCE_SHA256:
            raise ValueError('Prepared input stub does not produce the supported executable.')
    if digest(raw) == WINDOWED_BACKBUFFER_SOURCE_SHA256:
        raw = patch_windowed_backbuffer(raw)
    if digest(raw) != WINDOWS_SHA256:
        raise ValueError('The final executable checksum differs from the supported release.')
    changes['TopSpin.exe'] = raw
    from launcher.settings import Settings, apply_graphics
    from tools.pml import Pml
    from tools.controller_config import configure_pad
    config_raw = safe_path(game, 'Config.pml').read_bytes()
    settings = Settings(internal_resolution='3840x2160', output_resolution='1920x1080',
                        controller_family='xbox360')
    config = apply_graphics(config_raw, settings)
    tree = Pml(config)
    tree.set('DebugSettings', 'ShowFPS', 'false')
    tree.set('General', 'Language', 'Eng')
    tree.set('General', 'LaunchPart', 'e_TopSpin_MenuPart')
    tree.set('Video', 'FullScreen', 'false')
    # configure_pad preserves Security, all original mapping profiles and spare
    # controller assignments; installs an owned profile plus keyboard fallback.
    changes['Config.pml'] = configure_pad(tree.encode(), 1)
    changes['.portable/launcher.json'] = json_bytes(asdict(settings))
    changes['.portable/input.json'] = json_bytes({'version': 1, 'glyph_count': 48})
    changes.update(plan_windows_configuration(settings))
    from tools.glyph_install import plan_font_archives, _replace
    from tools.menu_quit import patch_main_menu, MEMBER_SHA256
    menu_changed = patch_main_menu(safe_path(game, MENU).read_bytes(),
                                   safe_path(Path(payload).absolute(), lua_descriptor['path']))
    fonts = plan_font_archives(game)
    for path, data in fonts.items():
        changes[path.relative_to(game).as_posix()] = data
    # Merge independent changes if MainMenu contains one of the patched fonts.
    if MENU in changes:
        with zipfile.ZipFile(io.BytesIO(menu_changed)) as archive:
            for member in MEMBER_SHA256:
                changes[MENU] = _replace(changes[MENU], member, archive.read(member))
    else:
        changes[MENU] = menu_changed
    prepare_prompt_styles(changes, settings.controller_family)
    changes['.portable/integrity.json'] = json_bytes(build_install_integrity(game, changes))
    for name in changes:
        safe_path(game, name)
    for folder in ('T', 'U'):
        path = safe_path(game, folder)
        if path.exists() and not path.is_dir():
            raise ValueError('The local save path is not a directory: '+folder)
    return changes, {'version': 1, 'author': 'djultra64', 'source_sha256': source_hash,
                     'status': 'validated', 'payload_manifest_sha256': manifest_hash}


def _write_exclusive(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        if os.name != 'nt':
            os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _replace_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.topspin-install-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def apply_changes(game: Path, changes: dict[str, bytes], metadata: dict | None = None):
    """Rollback every replaced file on error; private originals are exclusive."""
    game = Path(game).absolute()
    if game.is_symlink():
        raise ValueError('Symbolic link game folders are not supported.')
    paths = {}
    canonical = set()
    for name in changes:
        if name.lower() in canonical:
            raise ValueError('Duplicate case-insensitive patch destination: '+name)
        canonical.add(name.lower())
        paths[name] = safe_path(game, name)
        if _protected(name):
            raise ValueError('Protected installation path: '+name)
    metadata = dict(metadata or {})
    upgrading = metadata.get('operation') == 'upgrade'
    backup_name = BACKUP
    if upgrading:
        manifest_hash = metadata.get('payload_manifest_sha256', '')
        if len(manifest_hash) != 64 or any(c not in '0123456789abcdef' for c in manifest_hash):
            raise ValueError('Invalid upgrade manifest hash.')
        backup_name = '.portable/backups/topspin-patch-updates/'+manifest_hash
    backup = safe_path(game, backup_name)
    if backup.exists():
        raise ValueError('The private backup already exists; it will never be overwritten.')
    for folder in ('T', 'U'):
        save_folder = safe_path(game, folder)
        if save_folder.exists() and not save_folder.is_dir():
            raise ValueError('The local save path is not a directory: '+folder)
    receipt_path = safe_path(game, RECEIPT)
    previous_receipt = receipt_path.read_bytes() if receipt_path.exists() else None
    if upgrading:
        installed_receipt(game)
        validate_renderer_state(game)
        if previous_receipt is None or digest(previous_receipt) != metadata.get('_previous_receipt_sha256'):
            raise ValueError('The previous installation receipt changed during upgrade planning.')
    elif previous_receipt is not None:
        raise ValueError('The installation receipt already exists.')
    # A process lock also leaves a clear refusal after a power interruption.
    lock = safe_path(game, '.portable/install.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('An installation is active or interrupted; inspect the private backup and install.lock before retrying.') from exc
    os.close(lock_fd)
    previous = {}
    written = []
    created_dirs = []
    backup_created = False
    receipt = dict(metadata)
    receipt.pop('_previous_receipt_sha256', None)
    receipt.update(version=1, author='djultra64', status='installed',
                   backup=metadata.get('backup', BACKUP), files=dict(metadata.get('files', {})))
    if upgrading:
        receipt['updates'] = list(metadata.get('updates', [])) + [
            {'backup': backup_name, 'payload_manifest_sha256': metadata['payload_manifest_sha256'],
             'previous_receipt_sha256': digest(previous_receipt)}]
    try:
        backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        backup_created = True
        if previous_receipt is not None:
            _write_exclusive(backup/RECEIPT, previous_receipt)
        for name, path in paths.items():
            # Repeat link validation immediately before reading and writing.
            safe_path(game, name)
            previous[name] = path.read_bytes() if path.exists() else None
            if previous[name] is not None:
                _write_exclusive(backup/name, previous[name])
            receipt['files'][name] = {'sha256': digest(changes[name]),
                                      'original_sha256': digest(previous[name]) if previous[name] is not None else None}
        _write_exclusive(backup/'backup-manifest.json', json_bytes(receipt))
        for folder in ('T', 'U'):
            save_folder = safe_path(game, folder)
            if not save_folder.exists():
                save_folder.mkdir()
                created_dirs.append(save_folder)
        for name, path in paths.items():
            safe_path(game, name)
            parent = path.parent
            while not parent.exists():
                created_dirs.append(parent)
                parent = parent.parent
            _replace_bytes(path, changes[name])
            written.append(name)
        _replace_bytes(receipt_path, json_bytes(receipt))
    except BaseException:
        try:
            for name in reversed(written):
                if previous[name] is None:
                    paths[name].unlink(missing_ok=True)
                else:
                    _replace_bytes(paths[name], previous[name])
            if previous_receipt is None:
                receipt_path.unlink(missing_ok=True)
            else:
                _replace_bytes(receipt_path, previous_receipt)
            if backup_created:
                shutil.rmtree(backup)
            for directory in created_dirs:
                if directory.exists() and not any(directory.iterdir()):
                    directory.rmdir()
        except BaseException as recovery_error:
            raise RuntimeError('Rollback was interrupted. Keep the private backup and install.lock for recovery.') from recovery_error
        else:
            lock.unlink(missing_ok=True)
        raise
    lock.unlink(missing_ok=True)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install the djultra64 Top Spin patch into your own existing game.')
    parser.add_argument('--game-dir', type=Path, default=Path.cwd())
    parser.add_argument('--payload', type=Path)
    parser.add_argument('--check', action='store_true', help='Validate everything without changing the game.')
    args = parser.parse_args(argv)
    try:
        game = args.game_dir.absolute()
        changes, metadata = plan_install(game, args.payload or game/'.topspin-patch')
        if changes and not args.check:
            metadata = apply_changes(game, changes, metadata)
        metadata['planned_files'] = len(changes)
        print(json.dumps(metadata, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile) as exc:
        print('Patch installation failed: '+str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
