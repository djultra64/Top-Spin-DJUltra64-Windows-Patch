"""Install the supported user's ISO into a new private portable folder. djultra64.

No mounts, autorun, MSI execution, host extraction tools or protection bypasses.
Only the MSI-declared media is read; original files/backups stay private.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import unicodedata

from tools.build_portable import build,media_layout,publish_noreplace
from tools.msi_reader import read_tables,file_layout,safe_name
from tools.install_patch import (SOURCE_SHA256,plan_install,apply_changes,
                                 payload_bytes,safe_path)
from launcher.integrity import verify_integrity

MAX_ISO_BYTES=16*1024**3
MAX_ENTRY_BYTES=2*1024**3
MAX_ENTRIES=100000
MAX_TOTAL_BYTES=16*1024**3
MAX_MSI_BYTES=64*1024**2


@dataclass(frozen=True)
class IsoEntry:
    path: str
    size: int


def _cancel(cancel):
    if cancel is not None and cancel.is_set():raise InterruptedError('Installation cancelled.')


def _notify(progress,message):
    if progress:progress(message)


def _canonical(path,namespace):
    if not isinstance(path,str) or not path.startswith('/') or '\\' in path or '\0' in path:
        raise ValueError('Unsafe ISO path.')
    parts=path[1:].split('/')
    result=[]
    if len(parts)>64:raise ValueError('ISO path nesting limit exceeded.')
    for part in parts:
        if namespace=='iso_path' and ';' in part:
            name,version=part.rsplit(';',1)
            if not version.isascii() or not version.isdigit():raise ValueError('Invalid ISO file version.')
            part=name
        # ISO9660 represents extensionless names as NAME.; normalize that
        # namespace only, before applying the portable filename policy.
        if namespace=='iso_path' and part.endswith('.'):part=part[:-1]
        if part in ('','.','..') or safe_name(part)!=part:
            raise ValueError('Unsafe or ambiguous ISO path.')
        result.append(unicodedata.normalize('NFC',part).casefold())
    return '/'.join(result)


def _scan_iso(image,namespace,iso_size,cancel=None):
    entries={};seen=set();total=0;count=0
    for parent,dirs,files in image.walk(**{namespace:'/'}):
        _cancel(cancel)
        for name in dirs+files:
            count+=1
            if count>MAX_ENTRIES:raise ValueError('ISO contains too many entries.')
            path=parent.rstrip('/')+'/'+name
            canonical=_canonical(path,namespace)
            if canonical in seen:raise ValueError('ISO contains duplicate or case-colliding paths.')
            seen.add(canonical)
            record=image.get_record(**{namespace:path})
            if record.is_symlink():raise ValueError('Symbolic links are not supported in the ISO.')
            if name in dirs:
                if not record.is_dir():raise ValueError('Invalid ISO directory entry.')
                continue
            if not record.is_file():raise ValueError('Unsupported ISO file type.')
            size=record.get_data_length()
            if type(size) is not int or not 0<=size<=min(MAX_ENTRY_BYTES,iso_size):
                raise ValueError('ISO file exceeds the supported size bounds.')
            total+=size
            if total>MAX_TOTAL_BYTES:raise ValueError('ISO declared contents exceed supported limits.')
            entries[canonical]=IsoEntry(path,size)
    return entries


def _copy_entry(image,namespace,entry,target,cancel):
    target.parent.mkdir(parents=True,exist_ok=True)
    remaining=entry.size
    with image.open_file_from_iso(**{namespace:entry.path}) as source,target.open('xb') as output:
        while remaining:
            _cancel(cancel)
            data=source.read(min(1024**2,remaining))
            if not data or len(data)>remaining:raise ValueError('ISO file data is truncated or exceeds its declared size.')
            output.write(data);remaining-=len(data)
        if source.read(1):raise ValueError('ISO file exceeds its declared size.')
    if target.stat().st_size!=entry.size:raise ValueError('ISO extraction size mismatch.')


def _extractor(payload):
    if payload.is_symlink():raise ValueError('The payload folder must not be a symbolic link.')
    manifest=json.loads(safe_path(payload,'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version')!=1 or manifest.get('platform')!='linux':
        raise ValueError('The ISO installer requires the Linux payload.')
    name='runtime/linux/bin/cabextract'
    descriptor=manifest.get('files',{}).get(name)
    if not descriptor or descriptor.get('path')!='files/'+name or descriptor.get('executable') is not True:
        raise ValueError('The reviewed bundled cabinet extractor is missing.')
    raw=payload_bytes(payload,descriptor)
    path=safe_path(payload,descriptor['path'])
    if not raw.startswith(b'\x7fELF') or not os.access(path,os.X_OK):
        raise ValueError('The bundled cabinet extractor is not executable.')
    return path


def _source_aliases(tables,item):
    """Use only MSI-declared short/long source names, never guessed folders."""
    directories={row['id']:row for row in tables['Directory']}
    components={row['id']:row for row in tables['Component']}
    key=components[item['component']]['directory'];parts=[];seen=set()
    while key:
        if key in seen or len(seen)>=64:raise ValueError('Cyclic MSI source directory tree.')
        seen.add(key);row=directories[key]
        if not row['parent']:break  # SourceDir is the media root, not a folder.
        name=row['name'].split(':')[-1]
        if name!='.':parts.append(name)
        key=row['parent']
    paths=['']
    for field in list(reversed(parts))+[item['name']]:
        if field.count('|')>1:raise ValueError('An MSI source filename supports at most two aliases.')
        choices=[]
        for choice in field.split('|'):
            if safe_name(choice)!=choice:raise ValueError('Unsafe MSI source alias.')
            if choice not in choices:choices.append(choice)
        if len(paths)*len(choices)>256:raise ValueError('Too many MSI source filename aliases.')
        paths=[(parent+'/'+choice).lstrip('/') for parent in paths for choice in choices]
    return paths


def _publish(staged,destination):
    """Atomically publish without ever replacing an existing empty directory."""
    publish_noreplace(staged,destination)


def install_from_iso(iso:Path,destination:Path,payload:Path,*,progress=None,cancel=None)->dict:
    """Create one complete patched game, or leave no destination on failure.

    Progress receives English strings; cancellation uses threading.Event and
    raises InterruptedError. A final directory rename occurs only after every
    extraction, patch guard and immutable-file verification has succeeded.
    """
    _cancel(cancel)
    iso=Path(iso).absolute();destination=Path(destination).absolute();payload=Path(payload).absolute()
    if os.path.lexists(destination):raise FileExistsError('Choose a new game folder; the destination already exists.')
    if iso.is_symlink() or not iso.is_file():raise ValueError('Choose a regular ISO image file.')
    iso_size=iso.stat().st_size
    if not 32768<=iso_size<=MAX_ISO_BYTES:raise ValueError('ISO image size is outside the supported bounds.')
    extractor=_extractor(payload)
    try:
        import pycdlib
    except ImportError:
        raise ValueError('The bundled ISO reader is missing. Extract the complete installer package.') from None
    image=pycdlib.PyCdlib();created=[]
    try:
        _notify(progress,'Reading the ISO image...')
        _cancel(cancel)
        try:image.open(str(iso))
        except (OSError,ValueError,IndexError,EOFError,pycdlib.pycdlibexception.PyCdlibException):
            raise ValueError('The selected file is not a supported, readable ISO image.') from None
        namespace=('udf_path' if image.has_udf() else 'joliet_path' if image.has_joliet()
                   else 'rr_path' if image.has_rock_ridge() else 'iso_path')
        entries=_scan_iso(image,namespace,iso_size,cancel)
        installers=[entry for name,entry in entries.items() if PurePosixPath(name).name=='topspin.msi']
        if len(installers)!=1:raise ValueError('The ISO must contain exactly one TopSpin.msi installer.')
        installer=installers[0]
        if installer.size>MAX_MSI_BYTES:raise ValueError('The MSI database exceeds the supported size limit.')
        # Create missing parents only after ISO/payload validation. Remove only
        # directories created by this call, and only if still empty on failure.
        parent=destination.parent
        missing=[];cursor=parent
        while not cursor.exists():missing.append(cursor);cursor=cursor.parent
        if not cursor.is_dir():raise ValueError('The destination parent is not a directory.')
        for folder in reversed(missing):folder.mkdir();created.append(folder)
        parent=parent.resolve();destination=parent/destination.name
        if os.path.lexists(destination):raise FileExistsError('The destination already exists.')
        with tempfile.TemporaryDirectory(prefix='.topspin-install-',dir=parent) as folder:
            workspace=Path(folder);source=workspace/'media';source.mkdir()
            _copy_entry(image,namespace,installer,source/'TopSpin.msi',cancel)
            _notify(progress,'Checking the game installer database...')
            try:
                tables=read_tables(source/'TopSpin.msi');files=file_layout(tables);media=media_layout(tables,files)
            except (KeyError,IndexError,StopIteration,TypeError,UnicodeError,EOFError,ValueError) as exc:
                raise ValueError('The ISO contains an unsupported or invalid game installer database.') from exc
            base=PurePosixPath(installer.path).parent.as_posix().rstrip('/')
            requested={}
            for disk in media:
                if disk['cabinet']:requested[disk['cabinet']]=[disk['cabinet']]
            for item in files:
                disk=next(row for row in media if item['sequence']<=row['last'])
                if not disk['cabinet']:
                    name='program files/Atari/TopSpin/'+item['target'].as_posix()
                    requested[name]=[name]+_source_aliases(tables,item)
            selected={}
            for relative,aliases in requested.items():
                found={_canonical(base+'/'+alias,namespace) for alias in aliases}&entries.keys()
                if not found:raise FileNotFoundError('The ISO is missing required installer media: '+relative)
                if len(found)!=1:raise ValueError('The ISO contains ambiguous installer source aliases: '+relative)
                selected[relative]=entries[found.pop()]
            # Include extraction, verified game staging, private patch backups
            # and runtime copies in a conservative same-filesystem budget.
            payload_size=sum(path.stat().st_size for path in (payload/'files').rglob('*') if path.is_file())
            required=sum(e.size for e in selected.values())+3*sum(item['size'] for item in files)+payload_size+128*1024**2
            if shutil.disk_usage(parent).free<required:
                raise OSError('Not enough free space on the destination drive; approximately '
                              +str((required+1024**3-1)//1024**3)+' GiB is required.')
            _notify(progress,'Copying only the game installer media from the ISO...')
            for relative,entry in selected.items():
                _cancel(cancel);_copy_entry(image,namespace,entry,source/relative,cancel)
            image.close();image=None
            _notify(progress,'Extracting and verifying the original game files...')
            game=workspace/'game'
            inventory=build(source,game,cabextract=extractor,progress=progress,cancel=cancel)
            _cancel(cancel)
            if hashlib.sha256((game/'TopSpin.exe').read_bytes()).hexdigest()!=SOURCE_SHA256:
                raise ValueError('Unsupported TopSpin.exe. The ISO must contain the exact supported PC executable.')
            _notify(progress,'Applying the portable compatibility patch...')
            changes,metadata=plan_install(game,payload)
            if metadata.get('platform')!='linux':raise ValueError('A Linux patch payload is required.')
            _cancel(cancel)
            receipt=apply_changes(game,changes,metadata)
            _cancel(cancel)
            _notify(progress,'Verifying the completed game installation...')
            verification=verify_integrity(game)
            if not verification.ok:raise ValueError('The completed game failed its integrity check.')
            _cancel(cancel)
            result={'installed':True,'destination':str(destination),'source_files':len(inventory['files']),
                    'integrity_files':verification.checked,'platform':'linux','author':'djultra64',
                    'patch_status':receipt.get('status','installed')}
            _publish(game,destination)
            # Publication is committed. A closed UI's progress callback must
            # not report this complete, verified installation as a failure.
            try:_notify(progress,'Installation complete. Top Spin is ready to play.')
            except Exception:pass
            return result
    finally:
        if image is not None:
            try:image.close()
            except Exception:pass
        for folder in reversed(created):
            try:folder.rmdir()
            except OSError:pass
