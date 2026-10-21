"""Validated, reversible Windows interpolation runtime selection. djultra64."""
import hashlib
import json
from pathlib import Path
from launcher.integrity import checked_path

MANIFEST = '.portable/windows-framegen.json'
BASE = 'runtime/windows-framegen/'
FILES = tuple(BASE + name for name in (
    'afmf32.dll', 'VkLayer_AFMF.json', 'dxvk32/d3d8.dll',
    'dxvk32/d3d9.dll', 'dgvoodoo/d3d8.dll'))


def component(root):
    """Read and hash every component, without modifying the portable folder."""
    root = Path(root).resolve()
    target = checked_path(root, MANIFEST)
    if not target.exists():
        raise ValueError('Windows frame interpolation component is not installed.')
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or set(data) != {'version', 'files'} or data['version'] != 1:
            raise ValueError('Unsupported Windows frame interpolation manifest.')
        files = data['files']
        if not isinstance(files, dict) or set(files) != set(FILES):
            raise ValueError('Invalid Windows frame interpolation file list.')
        payloads = {}
        for name in FILES:
            digest = files[name]
            if (not isinstance(digest, str) or len(digest) != 64 or
                    any(c not in '0123456789abcdef' for c in digest)):
                raise ValueError('Invalid Windows frame interpolation hash: ' + name)
            payload = checked_path(root, name).read_bytes()
            if hashlib.sha256(payload).hexdigest() != digest:
                raise ValueError('Windows frame interpolation component is corrupt: ' + name)
            payloads[name.removeprefix(BASE)] = payload
        layer = json.loads(payloads['VkLayer_AFMF.json'])['layer']
        if layer['name'] != 'VK_LAYER_AFMF' or layer['library_path'] not in ('afmf32.dll', './afmf32.dll'):
            raise ValueError('Invalid Windows frame interpolation Vulkan layer.')
        # A hash list with aliases cannot safely distinguish the two renderers.
        wrappers = [payloads[name] for name in ('dxvk32/d3d8.dll', 'dxvk32/d3d9.dll', 'dgvoodoo/d3d8.dll')]
        if len(set(wrappers)) != 3:
            raise ValueError('Windows renderer files must be distinct.')
        return payloads
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Windows frame interpolation component is missing or invalid.') from exc


def available(root):
    try:
        component(root)
        return True
    except ValueError:
        return False


def renderer_updates(root, enabled):
    """Return complete writes/deletions; unknown user wrappers are never replaced."""
    root = Path(root).resolve()
    if not checked_path(root, MANIFEST).exists() and not enabled:
        return {}
    payloads = component(root)
    d8 = checked_path(root, 'd3d8.dll')
    d9 = checked_path(root, 'd3d9.dll')
    if not d8.is_file() or d8.read_bytes() not in (payloads['dgvoodoo/d3d8.dll'], payloads['dxvk32/d3d8.dll']):
        raise ValueError('Unrecognized d3d8.dll; restore the packaged Windows renderer before switching.')
    d9_bytes = d9.read_bytes() if d9.exists() else None
    if enabled and d9_bytes not in (None, payloads['dxvk32/d3d9.dll']):
        raise ValueError('Unrecognized d3d9.dll; move the custom wrapper before enabling interpolation.')
    result = {d8: payloads['dxvk32/d3d8.dll'] if enabled else payloads['dgvoodoo/d3d8.dll']}
    if enabled:
        result[d9] = payloads['dxvk32/d3d9.dll']
    elif d9_bytes == payloads['dxvk32/d3d9.dll']:
        result[d9] = None
    return {path: data for path, data in result.items()
            if (path.read_bytes() if path.exists() else None) != data}


def configure_environment(root, env, enabled):
    # Validate the pending switch during launch planning, before any writes.
    renderer_updates(root, enabled)
    if not enabled:
        env['AFMF_ENABLE'] = '0'
        return
    folder = str(Path(root).resolve() / BASE)
    # The Windows Vulkan loader uses semicolons for paths and layer names.
    for key, first in [('VK_LAYER_PATH', folder), ('VK_INSTANCE_LAYERS', 'VK_LAYER_AFMF')]:
        entries = [first] + [part for part in env.get(key, '').split(';') if part]
        env[key] = ';'.join(dict.fromkeys(entries))
    env.pop('DISABLE_AFMF', None)
    env.update(AFMF_ENABLE='1', AFMF_GAMESCOPE='0', AFMF_MIN_FPS='0')


def integrity_with_renderer_updates(root, changes, data=None):
    """Merge verified wrapper additions/deletions into the package integrity list."""
    from launcher.integrity import MANIFEST as INTEGRITY
    if data is None:
        data = json.loads(checked_path(root, INTEGRITY).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('files'), list):
        raise ValueError('Invalid integrity manifest')
    names = {'d3d8.dll', 'd3d9.dll'}
    updates = {path.relative_to(root).as_posix(): payload for path, payload in changes.items()}
    if set(updates) - names:
        raise ValueError('Invalid Windows renderer integrity update')
    data['files'] = [entry for entry in data['files'] if entry.get('path') not in updates]
    for name, payload in updates.items():
        if payload is not None:
            data['files'].append({'path': name, 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
    data['files'].sort(key=lambda entry: entry['path'])
    return data
