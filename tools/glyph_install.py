"""Plan version-checked local font changes; no original assets shipped. djultra64."""
import hashlib
import io
import struct
import zlib
from pathlib import Path
import zipfile
from tools.glyph_atlas import extend_font

FONT_SHA256='e61548774bb56131f582af60b0f17d94e50045575a2b27f9ba84a4dbe115723b'
TEXTURE_SHA256='3c07937f6ec0de6089bb051c8936ea4b2762d2cf849d545c1d6c82a28f793c47'
FONT='Fonts/Help_NovaBlackSSK.abc'
TEXTURE='Fonts/Help_NovaBlackSSK.dds'

# Exact source font/texture pairs from the supplied private inventory.
FONT_VARIANTS={'Help_NovaBlackSSK': {('e61548774bb56131f582af60b0f17d94e50045575a2b27f9ba84a4dbe115723b',
                        '3c07937f6ec0de6089bb051c8936ea4b2762d2cf849d545c1d6c82a28f793c47')},
 'NovaBlackSSK_14': {('2ef317435d868cc6ab0a1ed8ab91e98fea508b2b43ebbf8c4097e8923cad7b1d',
                      '6c3891339d582299c293aecf4783da5b67a34723d59e4f78a406e10a3c243e67')},
 'NovaBlackSSK_12': {('989c33ee90a248ad62d0bf892b34945fd699b7154eaf291029e1b9b6f74f6d87',
                      '3bcc73e156742604319000daed62ffc51bfb5ae2df786050fcad4d0dfea98836'),
                     ('989c33ee90a248ad62d0bf892b34945fd699b7154eaf291029e1b9b6f74f6d87',
                      'd430e1bcfa43566207c4537c9fe29e68acc843c3c4ca8cdb383f0a21381467e8')},
 '04b_11_12': {('c41546263d8d332b8d9ece3e1b372448a99f57c59d12d2f7fe5c467961f01b8e',
                'a0ceb855720aa5c84aed1a245fd50e477209db00eba337c2ceab11dafed5b3d2'),
               ('c41546263d8d332b8d9ece3e1b372448a99f57c59d12d2f7fe5c467961f01b8e',
                'c44ad63d1b8a4f93c3c809e220558d082668b95ca7ce2ee11a896c543aefd710')},
 'NovaBlackSSK_24_Buttons': {('d78ed15dfca36846dc7f6675c5e722f5ce60d08e9a3ec2b74c71d40cc71f6962',
                              '63b5ed3ee166ed824d2952b2d4a7c043ca0ebcae31d1859aa467188cb70a7e2d')}}


def _replace(raw,name,payload):
    # Append one new local entry and repoint its central record. Preserve all
    # unrelated bytes/CRC metadata, including defects in the supplied archives.
    # The original local font record becomes unreferenced ZIP data.
    end=raw.rfind(b'PK\x05\x06',max(0,len(raw)-65557))
    if end<0 or len(raw)<end+22:raise ValueError('Missing ZIP directory.')
    _,disk,cd_disk,on_disk,total,size,start,comment=struct.unpack_from('<4s4H2IH',raw,end)
    if disk or cd_disk or on_disk!=total or start+size!=end or end+22+comment!=len(raw):
        raise ValueError('Unsupported UI ZIP directory layout.')
    directory=bytearray(raw[start:end]);at=0;target=None
    for _ in range(total):
        if directory[at:at+4]!=b'PK\x01\x02' or at+46>len(directory):raise ValueError('Invalid ZIP record.')
        n,e,c=struct.unpack_from('<HHH',directory,at+28)
        length=46+n+e+c
        if at+length>len(directory):raise ValueError('Truncated ZIP record.')
        entry=bytes(directory[at+46:at+46+n])
        if entry==name.encode('ascii'):
            if target is not None:raise ValueError('Duplicate font entry.')
            target=at
        at+=length
    if at!=len(directory) or target is None:raise ValueError('Missing or incompatible font entry.')
    flags,method=struct.unpack_from('<HH',directory,target+8)
    if flags&9 or method!=0:raise ValueError('Expected a stored, unencrypted UI font entry.')
    old=struct.unpack_from('<I',directory,target+42)[0]
    if raw[old:old+4]!=b'PK\x03\x04' or old+30>start:raise ValueError('Invalid local font entry.')
    n,e=struct.unpack_from('<HH',raw,old+26)
    if old+30+n+e>start or raw[old+30:old+30+n]!=name.encode('ascii'):
        raise ValueError('Invalid local font name.')
    local=bytearray(raw[old:old+30+n+e]);crc=zlib.crc32(payload)
    struct.pack_into('<III',local,14,crc,len(payload),len(payload));local.extend(payload)
    struct.pack_into('<III',directory,target+16,crc,len(payload),len(payload))
    struct.pack_into('<I',directory,target+42,start)
    footer=bytearray(raw[end:]);struct.pack_into('<I',footer,16,start+len(local))
    return raw[:start]+bytes(local)+bytes(directory)+bytes(footer)


def plan_font_archives(game: Path):
    game=game.resolve();changes={};generated={}
    # Generate every result in memory before the caller writes any files.
    for path in sorted((game/'Media').rglob('*.rui')):
        if not path.resolve().is_relative_to(game):raise ValueError('UI path escapes the game folder.')
        raw=path.read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            selected=[name for name in FONT_VARIANTS if 'Fonts/'+name+'.abc' in archive.namelist()]
            if not selected:continue
            fonts={}
            for name in selected:
                entry='Fonts/'+name+'.abc'
                if archive.namelist().count(entry)!=1:raise ValueError('Duplicate UI font entry.')
                if archive.getinfo(entry).file_size>1024*1024:raise ValueError('Unexpected UI font size.')
                fonts[name]=archive.read(entry)
        resources=path.with_suffix('.ruirr')
        if not resources.resolve().is_relative_to(game):raise ValueError('UI texture path escapes the game folder.')
        texture_raw=resources.read_bytes();textures={}
        with zipfile.ZipFile(io.BytesIO(texture_raw)) as archive:
            for name in selected:
                entry='Fonts/'+name+'.dds'
                if archive.namelist().count(entry)!=1:raise ValueError('Missing or duplicate UI font texture.')
                if archive.getinfo(entry).file_size>8*1024*1024:raise ValueError('Unexpected font texture size.')
                textures[name]=archive.read(entry)
        for name in selected:
            abc,dds=fonts[name],textures[name]
            pair=(hashlib.sha256(abc).hexdigest(),hashlib.sha256(dds).hexdigest())
            if pair not in FONT_VARIANTS[name]:
                raise ValueError('Unsupported UI font resources: '+str(path.relative_to(game))+' / '+name)
            if pair not in generated:generated[pair]=extend_font(abc,dds)
            newabc,newdds=generated[pair]
            raw=_replace(raw,'Fonts/'+name+'.abc',newabc)
            texture_raw=_replace(texture_raw,'Fonts/'+name+'.dds',newdds)
        changes[path]=raw
        changes[resources]=texture_raw
    if not changes:raise ValueError('No supported UI font resources were found.')
    return changes
