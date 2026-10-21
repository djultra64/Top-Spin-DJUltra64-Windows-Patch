"""Local static controller prompt styles. Own work: djultra64.

Only hashes and our replacement logic ship in source. Baseline archive backups
contain the user's own assets and stay inside their private portable folder.
No Pillow, external interpreter or original game asset is imported here.
"""
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile
import zlib
from launcher.settings import atomic_write

FAMILIES=('xbox360','xbox','ps4','ps5','switch','unknown')
CODES=(0x2123,0x2124,0x2125,0x2126,0x2127,0x2128,0x212b,0x212c)
FONT_NAMES=('Help_NovaBlackSSK','NovaBlackSSK_14','NovaBlackSSK_12','04b_11_12','NovaBlackSSK_24_Buttons')
# Offline verified v2 outputs from the version-checked original inventory.
BASELINE_SHA256={'Media/CareerPart/RuiPC/Base.rui': '1038481c8ebf7e6f92dace02c342c2f83e15aa5904cf39f79c3e24f479915c69',
 'Media/MenuPart/RuiPC/Base.rui': '0ca90d61969e962986f802585cf00d4cfe0d82cf744ee4184a9936cda3501a29',
 'Media/MenuPart/RuiPC/SportMenu.rui': '51eca9747fd3c79dbe495aa23bf5d5fb0748285583ee1a22b72cf7e8e6198aff',
 'Media/PlayerCreatorMenuPart/RuiPC/Base.rui': 'f4f925f76fd4d65a3d7dbe0c270b3d0a9bf8386cd135f17a2305f84afc5db347',
 'Media/RuiPC/Base.rui': '45a7a990f4152f6bcd777ea138daf922239b9e42c1a482dcac776b382ba969b7'}

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


def _validate_style(family,positions):
    if family not in ('auto','keyboard')+FAMILIES:
        raise ValueError('Unsupported prompt family.')
    if not isinstance(positions,str) or len(positions)!=8 or any(c not in '01234567' for c in positions):
        raise ValueError('Prompt positions must contain eight physical button positions.')


def _local(root,relative):
    result=(root/relative).resolve()
    if not result.is_relative_to(root):raise ValueError('Prompt path escapes the portable folder.')
    return result


def _style_font(data,family,positions):
    if len(data)<28:raise ValueError('Truncated prompt font.')
    version,line,width,height,ascent,range_count=struct.unpack_from('<6I',data)
    if version!=6 or not 0<range_count<512 or 28+range_count*4>len(data):
        raise ValueError('Unsupported prompt font layout.')
    ranges=[struct.unpack_from('<HH',data,24+i*4) for i in range(range_count)]
    if ranges[-1]!=(0xe000,0xe02f):raise ValueError('Missing controller prompt font range.')
    if any(lo>hi or (i and lo<=ranges[i-1][1]) for i,(lo,hi) in enumerate(ranges)):
        raise ValueError('Invalid prompt font ranges.')
    codes=[c for lo,hi in ranges for c in range(lo,hi+1)]
    count=struct.unpack_from('<I',data,24+range_count*4)[0];start=28+range_count*4
    if count!=len(codes) or len(data)!=start+count*28:raise ValueError('Invalid prompt glyph table.')
    out=bytearray(data);family_index=FAMILIES.index(family)
    for action,original in enumerate(CODES):
        if original not in codes:continue
        target=codes.index(original);replacement=codes.index(0xe000+family_index*8+int(positions[action]))
        out[start+target*28:start+(target+1)*28]=data[start+replacement*28:start+(replacement+1)*28]
    return bytes(out)


def _style_archive(raw,family,positions):
    if family in ('auto','keyboard'):return raw
    payloads={}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in FONT_NAMES:
            entry='Fonts/'+name+'.abc'
            if entry not in archive.namelist():continue
            if archive.namelist().count(entry)!=1:raise ValueError('Duplicate prompt font.')
            if archive.getinfo(entry).file_size>1024*1024:raise ValueError('Unexpected prompt font size.')
            payloads[entry]=_style_font(archive.read(entry),family,positions)
    if not payloads:raise ValueError('No controller prompt fonts were found.')
    for name,payload in payloads.items():raw=_replace(raw,name,payload)
    return raw


def plan_prompt_style(game,family,positions='01234567'):
    """Return all required writes after validating every baseline/current file."""
    _validate_style(family,positions);root=Path(game).resolve();changes={}
    state_path=_local(root,'.portable/glyphs/style.json')
    if state_path.exists():
        try:state=json.loads(state_path.read_text())
        except (OSError,json.JSONDecodeError) as exc:raise ValueError('Invalid prompt style state.') from exc
        if not isinstance(state,dict) or set(state)!= {'version','family','positions'} or state['version']!=1:
            raise ValueError('Unsupported prompt style state.')
        _validate_style(state['family'],state['positions'])
    else:state=None
    for relative,digest in BASELINE_SHA256.items():
        path=_local(root,relative);backup=_local(root,'.portable/glyphs/baseline/'+relative)
        if not path.is_file():raise ValueError('A prompt archive is missing: '+relative)
        current=path.read_bytes()
        if state is None:
            baseline=current
            if hashlib.sha256(baseline).hexdigest()!=digest:
                raise ValueError('Unsupported prompt baseline: '+relative)
            if backup.exists() and hashlib.sha256(backup.read_bytes()).hexdigest()!=digest:
                raise ValueError('A prompt baseline backup was modified: '+relative)
            if not backup.exists():changes[backup]=baseline
        else:
            if not backup.is_file():raise ValueError('A prompt baseline backup is missing: '+relative)
            baseline=backup.read_bytes()
            if hashlib.sha256(baseline).hexdigest()!=digest:
                raise ValueError('A prompt baseline backup was modified: '+relative)
            expected=_style_archive(baseline,state['family'],state['positions'])
            if current!=expected:raise ValueError('A prompt archive was modified outside the launcher: '+relative)
        styled=_style_archive(baseline,family,positions)
        if current!=styled:changes[path]=styled
    state=(json.dumps({'version':1,'family':family,'positions':positions},indent=2)+'\n').encode()
    if not state_path.exists() or state_path.read_bytes()!=state:changes[state_path]=state
    return changes


def apply_prompt_style(game,family,positions='01234567'):
    """Apply a validated plan with rollback; return modified Media payloads."""
    root=Path(game).resolve();changes=plan_prompt_style(root,family,positions)
    previous={p:p.read_bytes() if p.exists() else None for p in changes};written=[]
    try:
        for path,data in changes.items():
            atomic_write(path,data);written.append(path)
    except BaseException:
        for path in reversed(written):
            if previous[path] is None:path.unlink(missing_ok=True)
            else:atomic_write(path,previous[path])
        raise
    media=root/'Media'
    return {p:data for p,data in changes.items() if p.is_relative_to(media)}
