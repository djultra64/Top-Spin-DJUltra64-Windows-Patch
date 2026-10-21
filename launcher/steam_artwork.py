"""Install user-provided Steam artwork on explicit Add to Steam. djultra64.

Runtime uses only the Python standard library. The caller owns Steam's closed /
shortcut workflow; this module never starts or stops Steam and never edits VDF.
"""
from dataclasses import dataclass
from pathlib import Path
import struct
import uuid
import zlib
from launcher.settings import atomic_write

ROLES=('landscape','portrait','hero','logo')
IMAGE_EXTENSIONS={'.png','.jpg','.jpeg','.webp','.tga','.gif','.webm'}


def _png_size(data):
    if not isinstance(data,bytes) or len(data)<45 or data[:8]!=b'\x89PNG\r\n\x1a\n':
        raise ValueError('A Steam artwork file is not a valid PNG image.')
    position=8;size=None;ended=False
    while position<len(data):
        if position+12>len(data):raise ValueError('A Steam artwork PNG is incomplete.')
        length=struct.unpack_from('>I',data,position)[0];kind=data[position+4:position+8]
        end=position+12+length
        if end>len(data):raise ValueError('A Steam artwork PNG is incomplete.')
        chunk=data[position+8:end-4]
        if zlib.crc32(kind+chunk)&0xffffffff!=struct.unpack_from('>I',data,end-4)[0]:
            raise ValueError('A Steam artwork PNG is damaged.')
        if position==8:
            if kind!=b'IHDR' or length!=13:raise ValueError('Invalid Steam artwork PNG header.')
            size=struct.unpack_from('>II',chunk)
            if any(value<1 or value>8192 for value in size):raise ValueError('Unsupported Steam artwork image size.')
        if kind==b'IEND':
            if length or end!=len(data):raise ValueError('Invalid Steam artwork PNG ending.')
            ended=True;break
        position=end
    if not ended or size is None:raise ValueError('A Steam artwork PNG is incomplete.')
    return size


def validate_artwork(game_root):
    """Validate the four grid PNGs before any Steam changes; return role->Path.

    Icons remain in the game folder and are selected by the shortcut creator.
    The optional PNG icon is validated when present. Missing artwork raises a
    readable ValueError; callers can skip this feature in source-only builds.
    """
    root=Path(game_root).resolve();directory=root/'artwork/steam'
    if (root/'artwork').is_symlink() or directory.is_symlink():
        raise ValueError('Steam artwork must be stored inside the portable game folder.')
    paths={}
    for role in ROLES:
        path=directory/(role+'.png')
        if path.is_symlink() or not path.is_file():raise ValueError('Steam artwork is missing: '+role+'.png')
        try:_png_size(path.read_bytes())
        except OSError as exc:raise ValueError('Could not read Steam artwork: '+role+'.png') from exc
        paths[role]=path
    icon=directory/'icon.png'
    if icon.exists():
        if icon.is_symlink() or not icon.is_file():raise ValueError('Invalid Steam artwork icon path.')
        _png_size(icon.read_bytes())
    return paths


@dataclass(frozen=True)
class ArtworkInstallResult:
    installed: tuple
    unchanged: tuple
    backups: tuple
    removed: tuple


def install_artwork(game_root,shortcuts_path,appid):
    """Install four images beside the selected profile's shortcuts.vdf.

    Per-file backups precede writes. Existing image variants for exactly this
    appid and slot are backed up and removed, so a previous JPEG cannot take
    priority over the supplied PNG. Every other artwork slot is preserved.
    """
    if type(appid) is not int or not 0<appid<=0xffffffff:raise ValueError('Invalid Steam shortcut app ID.')
    sources=validate_artwork(game_root)
    payloads={role:path.read_bytes() for role,path in sources.items()}
    shortcut=Path(shortcuts_path)
    if shortcut.name.casefold()!='shortcuts.vdf' or shortcut.parent.name.casefold()!='config':
        raise ValueError('Choose the Steam profile config/shortcuts.vdf path.')
    directory=shortcut.parent.resolve()
    if not directory.is_dir():raise ValueError('The selected Steam profile config folder does not exist.')
    grid=directory/'grid'
    if grid.is_symlink() or grid.exists() and not grid.is_dir():raise ValueError('Steam artwork grid must be a regular folder.')
    stems={'landscape':str(appid),'portrait':str(appid)+'p','hero':str(appid)+'_hero','logo':str(appid)+'_logo'}
    targets={role:grid/(stem+'.png') for role,stem in stems.items()}
    by_stem={value.casefold():role for role,value in stems.items()}
    old={}
    if grid.exists():
        for path in grid.iterdir():
            if path.stem.casefold() in by_stem and path.suffix.casefold() in IMAGE_EXTENSIONS:
                if path.is_symlink() or not path.is_file():raise ValueError('A Steam artwork target is not a regular file: '+path.name)
                old[path]=path.read_bytes()
    changed=[role for role,target in targets.items() if old.get(target)!=payloads[role]]
    stale=[path for path in old if path!=targets[by_stem[path.stem.casefold()]]]
    affected=[path for path in old if path in stale or by_stem[path.stem.casefold()] in changed]
    if not changed and not stale:return ArtworkInstallResult((),tuple(targets.values()),(),())
    backup_root=grid/'.topspin-artwork-backups'
    if affected and (backup_root.is_symlink() or backup_root.exists() and not backup_root.is_dir()):
        raise ValueError('Steam artwork backup location must be a regular folder.')
    grid.mkdir(exist_ok=True);backups=[];written=[];removed=[]
    if affected:
        backup_dir=backup_root/uuid.uuid4().hex
        backup_dir.mkdir(parents=True,mode=0o700)
        for path in affected:
            backup=backup_dir/path.name;atomic_write(backup,old[path]);backups.append(backup)
    try:
        for role in changed:
            target=targets[role];atomic_write(target,payloads[role]);written.append(target)
        for path in stale:path.unlink();removed.append(path)
    except OSError:
        # Roll back only our four slots; backups remain available to the user.
        for path in written:
            if path not in old:path.unlink(missing_ok=True)
        for path in set(written+removed):
            if path in old:atomic_write(path,old[path])
        raise
    return ArtworkInstallResult(tuple(written),tuple(targets[role] for role in ROLES if role not in changed),tuple(backups),tuple(removed))
