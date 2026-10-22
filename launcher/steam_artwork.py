"""Install user-provided Steam artwork on explicit Add to Steam. djultra64.

Runtime uses only the Python standard library. The caller owns Steam's closed /
shortcut workflow; this module never starts or stops Steam and never edits VDF.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import struct
import urllib.parse
import urllib.request
import uuid
import zlib
from launcher.settings import atomic_write

ROLES=('landscape','portrait','hero','logo')
IMAGE_EXTENSIONS={'.png','.jpg','.jpeg','.webp','.tga','.gif','.webm'}

# Fixed user-selected resources; no copyrighted artwork bytes are bundled.
ARTWORK_SOURCES={'icon': {'url': 'https://cdn2.steamgriddb.com/icon/d3257767e94c24d25f618f96a324c780.png',
          'sha256': '8037c8831ecc373b41150b1674b3c789cebaa46026e0ed2f33d6f425fc96ee33',
          'width': 1024,
          'height': 1024},
 'logo': {'url': 'https://cdn2.steamgriddb.com/logo/e58226fbcc883887b380d916b41c4b0e.png',
          'sha256': 'b4f83df94ad453fe07b6bf0be9c8d3f8d796775c0b61b7a1f01d98ae13f6f262',
          'width': 390,
          'height': 87},
 'hero': {'url': 'https://cdn2.steamgriddb.com/hero/fbe0452c6aaf5ae4f65cc802298f9693.png',
          'sha256': '609a4a62adc97a12133eb05e096106b2a6f14f26d2d47ae43f8054e2f1dff313',
          'width': 1920,
          'height': 620},
 'portrait': {'url': 'https://cdn2.steamgriddb.com/grid/5b2abbcf7c45a21a72be22e15ef5f939.png',
              'sha256': '7f7dcdee8e81026f16f17fecea0e37f9f8d11fe2861000732715eb6389b5d9d6',
              'width': 600,
              'height': 900},
 'landscape': {'url': 'https://cdn2.steamgriddb.com/grid/f5e4f9a607bd4a71fa49cb956af7ed78.png',
               'sha256': '32ceeb3ef8fd2444666c79861bd14ef6bf7651e58e563ea071eb3d03f49ff424',
               'width': 920,
               'height': 430}}
MAX_ARTWORK_BYTES=20*1024*1024


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


def _safe_artwork_url(url):
    parts=urllib.parse.urlsplit(url)
    if (parts.scheme!='https' or parts.hostname!='cdn2.steamgriddb.com' or
            parts.port not in (None,443) or parts.username is not None or
            parts.password is not None or parts.fragment):
        raise ValueError('Steam artwork downloads require the fixed HTTPS artwork host.')
    return url


class ArtworkRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,response,code,message,headers,newurl):
        _safe_artwork_url(newurl)
        return super().redirect_request(request,response,code,message,headers,newurl)


def fetch_artwork_image(url):
    """Download only from the selected CDN, with a timeout and byte limit."""
    _safe_artwork_url(url)
    request=urllib.request.Request(url,headers={'User-Agent':'TopSpinArtwork/djultra64'})
    opener=urllib.request.build_opener(ArtworkRedirectHandler())
    with opener.open(request,timeout=20) as response:
        _safe_artwork_url(response.geturl())
        length=response.headers.get('Content-Length')
        if length is not None and (not length.isdecimal() or int(length)>MAX_ARTWORK_BYTES):
            raise ValueError('Steam artwork response exceeds the supported size.')
        data=response.read(MAX_ARTWORK_BYTES+1)
    if len(data)>MAX_ARTWORK_BYTES:
        raise ValueError('Steam artwork response exceeds the supported size.')
    return data


def ensure_artwork(game_root,*,fetch=None,progress=None):
    """Fetch missing/broken images on explicit Add; retain valid custom PNGs.

    Validate every pending download before cache writes. A failed write restores
    previous cache bytes. This function never accesses a Steam profile/process.
    """
    root=Path(game_root).resolve();directory=root/'artwork/steam'
    if (root/'artwork').is_symlink() or directory.is_symlink():
        raise ValueError('Steam artwork must stay inside the game folder.')
    if directory.exists() and not directory.is_dir():
        raise ValueError('Steam artwork cache must be a regular folder.')
    fetch=fetch or fetch_artwork_image
    paths={role:directory/(role+'.png') for role in ARTWORK_SOURCES}
    pending={};originals={}
    for role,path in paths.items():
        if path.is_symlink() or path.exists() and not path.is_file():
            raise ValueError('Invalid Steam artwork cache path: '+path.name)
        original=path.read_bytes() if path.exists() else None
        if original is not None:
            try:
                _png_size(original)
            except ValueError:
                pass
            else:
                continue
        item=ARTWORK_SOURCES[role]
        _safe_artwork_url(item['url'])
        if progress:progress('Downloading Steam artwork: '+role+'…')
        raw=fetch(item['url'])
        if not isinstance(raw,bytes) or len(raw)>MAX_ARTWORK_BYTES:
            raise ValueError('Unsupported Steam artwork response size: '+role)
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:
            raise ValueError('Steam artwork checksum differs from the selected image: '+role)
        if _png_size(raw)!=(item['width'],item['height']):
            raise ValueError('Steam artwork dimensions differ from the selected image: '+role)
        pending[path]=raw;originals[path]=original
    written=[]
    try:
        for path,raw in pending.items():
            if (root/'artwork').is_symlink() or directory.is_symlink() or path.is_symlink():
                raise ValueError('Steam artwork cache path changed while downloading.')
            atomic_write(path,raw);written.append(path)
    except (OSError,ValueError):
        for path in reversed(written):
            if originals[path] is None:path.unlink(missing_ok=True)
            else:atomic_write(path,originals[path])
        raise
    validate_artwork(root)
    if progress:progress('Steam artwork is ready.')
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
