"""Explicit non-Steam shortcut creation, preserving other records. djultra64.

Binary KV1 reference: https://github.com/ValvePython/vdf (format only).
No Steam data is read or written on ordinary Play.
"""
from pathlib import Path
import os
import struct
import subprocess
import sys
import uuid
import zlib
from launcher.settings import atomic_write

EMPTY=b'\x00shortcuts\x00\x08\x08'

def _cstring(data,pos):
    end=data.find(b'\0',pos)
    if end<0:raise ValueError('Invalid Steam shortcuts: unterminated string.')
    return data[pos:end],end+1


def _entries(data,pos,depth=0):
    if depth>64:raise ValueError('Invalid Steam shortcuts: excessive nesting.')
    entries=[]
    while pos<len(data):
        start=pos;kind=data[pos];pos+=1
        if kind==8:return entries,pos
        key,pos=_cstring(data,pos)
        if kind==0:value,pos=_entries(data,pos,depth+1)
        elif kind==1:value,pos=_cstring(data,pos)
        elif kind==5:
            begin=pos
            while pos+1<len(data) and data[pos:pos+2]!=b'\0\0':pos+=2
            if pos+1>=len(data):raise ValueError('Invalid Steam wide string.')
            pos+=2;value=data[begin:pos]
        elif kind in {2,3,4,6,7,10}:
            size=8 if kind in {7,10} else 4
            value=data[pos:pos+size];pos+=size
            if pos>len(data):raise ValueError('Invalid Steam numeric value.')
        else:raise ValueError('Unsupported Steam shortcuts field type: '+str(kind))
        entries.append((kind,key,value,data[start:pos]))
    raise ValueError('Invalid Steam shortcuts: missing closing marker.')


def _string(key,value):
    if '\0' in key or '\0' in value:raise ValueError('Invalid shortcut text.')
    return b'\x01'+key.encode()+b'\0'+value.encode('utf-8')+b'\0'


def shortcut_spec(root: Path,platform=None):
    platform=platform or sys.platform
    filename='TopSpinLauncher.exe' if platform=='win32' else 'TopSpinLauncher.sh'
    # Steam stores the surrounding quotes as part of the executable string.
    spec={'AppName':'Top Spin','Exe':'"'+str(root/filename)+'"',
          'StartDir':'"'+str(root)+'"','LaunchOptions':'--play'}
    icon=root/'artwork/steam'/('icon.ico' if platform=='win32' else 'icon.png')
    if icon.is_file():spec['icon']=str(icon)
    return spec


def add_shortcut_bytes(data: bytes,spec: dict) -> tuple[bytes,int]:
    entries,end=_entries(data,0)
    if end!=len(data) or len(entries)!=1 or entries[0][:2]!=(0,b'shortcuts'):
        raise ValueError('Invalid Steam shortcuts root.')
    children=entries[0][2];indices=[];used_appids=set()
    for index,(kind,key,fields,raw) in enumerate(children):
        if kind!=0 or not key.isdigit():raise ValueError('Invalid Steam shortcut index.')
        indices.append(int(key))
        strings={k.decode('utf-8','replace').lower():v.decode('utf-8','replace')
                 for t,k,v,r in fields if t==1}
        ids=[struct.unpack('<I',v)[0] for t,k,v,r in fields if t==2 and k.lower()==b'appid']
        used_appids.update(ids)
        legacy=spec['AppName']=='Top Spin' and strings.get('appname')=='Top Spin Portable'
        if strings.get('exe')==spec['Exe'] and (strings.get('appname')==spec['AppName'] or legacy):
            if strings.get('startdir')!=spec['StartDir'] or strings.get('launchoptions')!=spec['LaunchOptions']:
                raise ValueError('An existing shortcut has different options. Remove it in Steam before adding it again.')
            appid=ids[0] if ids else zlib.crc32((spec['Exe']+strings['appname']).encode())|0x80000000
            update_icon=bool(spec.get('icon')) and strings.get('icon')!=spec['icon']
            if legacy or update_icon:
                replacements={b'appname':spec['AppName']}
                if update_icon:replacements[b'icon']=spec['icon']
                body=b''.join(_string(k.decode('utf-8'),replacements[k.lower()])
                              if t==1 and k.lower() in replacements else r for t,k,v,r in fields)
                if update_icon and 'icon' not in strings:body+=_string('icon',spec['icon'])
                renamed=b'\x00'+key+b'\x00'+body+b'\x08'
                records=[r for t,k,v,r in children];records[index]=renamed
                return b'\x00shortcuts\x00'+b''.join(records)+b'\x08\x08',appid
            return data,appid
    appid=zlib.crc32((spec['Exe']+spec['AppName']).encode())|0x80000000
    if appid in used_appids:raise ValueError('A Steam shortcut ID collision was detected. Existing shortcuts were left unchanged.')
    body=b'\x02appid\0'+struct.pack('<I',appid)
    body+=b''.join(_string(k,spec[k]) for k in ['AppName','Exe','StartDir'])
    body+=_string('icon',spec.get('icon',''))+_string('ShortcutPath','')+_string('LaunchOptions',spec['LaunchOptions'])
    for key,value in [('IsHidden',0),('AllowDesktopConfig',1),('AllowOverlay',1),
                      ('OpenVR',0),('Devkit',0),('DevkitOverrideAppID',0),('LastPlayTime',0)]:
        body+=b'\x02'+key.encode()+b'\0'+struct.pack('<I',value)
    body+=_string('DevkitGameID','')+_string('FlatpakAppID','')+b'\x00tags\0\x08\x08'
    new=b'\x00'+str(max(indices,default=-1)+1).encode()+b'\0'+body
    # Existing child records retain every original byte, including unknown fields.
    return b'\x00shortcuts\0'+b''.join(r for t,k,v,r in children)+new+b'\x08\x08',appid


def steam_is_running(platform=None):
    platform=platform or sys.platform
    if platform=='win32':
        result=subprocess.run(['tasklist','/FI','IMAGENAME eq steam.exe','/FO','CSV','/NH'],
                              capture_output=True,text=True,check=True,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return '"steam.exe"' in result.stdout.lower()
    # /proc avoids shell commands and only checks process names, not arguments
    # containing a Steam path (the portable launcher can have one itself).
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():continue
        try:
            if (item/'comm').read_text().strip()=='steam':return True
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
    return False


def write_shortcut(path: Path,spec: dict,*,steam_running: bool) -> int:
    if steam_running:raise ValueError('Close Steam completely, then click Add to Steam again.')
    original=path.read_bytes() if path.exists() else EMPTY
    result,appid=add_shortcut_bytes(original,spec)
    if result==original:return appid
    path.parent.mkdir(parents=True,exist_ok=True)
    # An exclusive local lock also prevents two instances of this launcher from
    # racing. Steam must be closed separately because it does not use this lock.
    lock=path.with_name(path.name+'.topspin.lock')
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise ValueError('Another shortcut update is in progress.') from None
    try:
        os.close(fd)
        if (path.read_bytes() if path.exists() else EMPTY)!=original:
            raise ValueError('Steam shortcuts changed during this operation. Please try again.')
        if path.exists():
            backup=path.with_name(path.name+'.'+uuid.uuid4().hex+'.bak')
            with backup.open('xb') as stream:stream.write(original)
        atomic_write(path,result)
    finally:lock.unlink()
    return appid
