"""Read-only checks of immutable portable files. Author: djultra64.

The manifest is a local corruption check, not an authenticity signature. User
configuration and saved games are deliberately outside its scope.
"""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import tempfile

MANIFEST = '.portable/integrity.json'


def relative_path(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value:
        raise ValueError('Unsafe integrity file path')
    path=PurePosixPath(value)
    if path.is_absolute() or any(part in ('','.', '..') for part in value.split('/')):
        raise ValueError('Unsafe integrity file path')
    return path


def is_mutable(name):
    path=relative_path(name)
    if path.as_posix() in {'.portable/input.json','.portable/runtime.json','.portable/windows-graphics.json',
                          '.portable/windows-framegen.json'}:return False
    return (path.parts[0].lower() in {'t','u','z','.portable'} or
            path.name.lower() in {'config.pml','dgvoodoo.conf'})


def checked_path(root,name):
    path=relative_path(name); current=Path(root)
    for part in path.parts:
        current=current/part
        if current.is_symlink():
            raise ValueError(f'Symbolic links are not allowed in integrity files: {name}')
    return current


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(root,paths):
    root=Path(root).resolve();files=[];seen=set()
    for name in sorted(paths):
        relative_path(name)
        if name.casefold() in seen:raise ValueError(f'Duplicate integrity path: {name}')
        seen.add(name.casefold())
        if is_mutable(name):continue
        path=checked_path(root,name)
        if not path.is_file():raise FileNotFoundError(f'Missing package file: {name}')
        files.append({'path':name,'size':path.stat().st_size,'sha256':sha256(path)})
    if not files:raise ValueError('Integrity manifest has no immutable files')
    return {'version':1,'files':files}


def write_manifest(root,manifest):
    target=checked_path(Path(root).resolve(),MANIFEST)
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.integrity-',dir=target.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(manifest,stream,indent=2);stream.write('\n')
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return target


def manifest_with_updates(root,changes):
    """Update expected bytes for version-checked, launcher-generated resources.

    Call only after the prompt generator has validated the installed resources
    and generated replacements. Unrelated package hashes retain their values.
    """
    root=Path(root).resolve()
    data=json.loads(checked_path(root,MANIFEST).read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('files'),list):
        raise ValueError('Invalid integrity manifest')
    updates={}
    for path,payload in changes.items():
        name=Path(path).relative_to(root).as_posix();relative_path(name)
        if is_mutable(name):continue
        checked_path(root,name)
        updates[name]=(len(payload),hashlib.sha256(payload).hexdigest())
    seen=set()
    for entry in data['files']:
        if not isinstance(entry,dict):raise ValueError('Invalid integrity manifest entry')
        name=entry.get('path');relative_path(name)
        if name.casefold() in seen:raise ValueError('Duplicate integrity path')
        seen.add(name.casefold())
        if name in updates:
            entry['size'],entry['sha256']=updates.pop(name)
    if updates:raise ValueError('Generated prompt resource is missing from the integrity manifest')
    return data


@dataclass(frozen=True)
class IntegrityResult:
    checked: int
    missing: tuple
    modified: tuple

    @property
    def ok(self):return not (self.missing or self.modified)

    @property
    def summary(self):
        if self.ok:return f'Integrity check passed: {self.checked} files verified.'
        return (f'Integrity check failed: {len(self.missing)} missing, '
                f'{len(self.modified)} modified ({self.checked} files checked).')


def verify_integrity(root):
    root=Path(root).resolve()
    target=checked_path(root,MANIFEST)
    if not target.is_file():
        raise ValueError('Integrity manifest is missing. Rebuild the portable package to enable file verification.')
    try:data=json.loads(target.read_text(encoding='utf-8'))
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError('Could not read integrity manifest') from exc
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('files'),list) or not data['files']:
        raise ValueError('Unsupported or empty integrity manifest')
    seen=set();validated=[]
    for item in data['files']:
        if not isinstance(item,dict):raise ValueError('Invalid integrity manifest entry')
        name=item.get('path');relative_path(name)
        value=item.get('sha256');size=item.get('size')
        if (name.casefold() in seen or is_mutable(name) or type(size) is not int or size<0 or
                not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value)):
            raise ValueError(f'Invalid integrity manifest entry: {name}')
        seen.add(name.casefold());validated.append((name,checked_path(root,name),size,value))
    missing=[];modified=[]
    for name,path,size,value in validated:
        if not path.is_file():missing.append(name)
        elif path.stat().st_size!=size or sha256(path)!=value:modified.append(name)
    return IntegrityResult(len(validated),tuple(missing),tuple(modified))
