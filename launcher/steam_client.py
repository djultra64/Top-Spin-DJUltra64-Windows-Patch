"""Read account metadata and gracefully manage the user's Steam client. djultra64.

No account credentials are returned, no VDF includes are followed, and no Steam
file is written here. The caller must finish shutdown before editing shortcuts.
"""
from dataclasses import dataclass
from pathlib import Path
import csv
import io
import os
import shutil
import subprocess
import sys
import time
from launcher.process import clean_windows_dll_search

PROC_ROOT=Path('/proc')


def _account_id(value):
    return (isinstance(value,str) and bool(value) and all(c in '0123456789' for c in value)
            and len(value)<=10 and 0<int(value)<=0xffffffff and str(int(value))==value)


@dataclass(frozen=True)
class SteamAccount:
    steam_root: Path
    account_id: str
    display_name: str
    most_recent: bool=False
    timestamp: int=0

    def __post_init__(self):
        if not _account_id(self.account_id):raise ValueError('Invalid Steam account ID.')
        object.__setattr__(self,'steam_root',Path(self.steam_root).resolve())

    @property
    def shortcuts_path(self):
        return self.steam_root/'userdata'/self.account_id/'config/shortcuts.vdf'


def _tokens(text):
    at=0;length=len(text)
    while at<length:
        if text[at].isspace():at+=1;continue
        if text.startswith('//',at):
            end=text.find('\n',at+2);at=length if end<0 else end+1;continue
        if text.startswith('/*',at):
            end=text.find('*/',at+2)
            if end<0:raise ValueError('Unterminated comment.')
            at=end+2;continue
        char=text[at]
        if char in '{}':yield ('brace',char);at+=1;continue
        if char=='"':
            at+=1;parts=[]
            while at<length:
                char=text[at];at+=1
                if char=='"':break
                if char=='\\':
                    if at>=length:raise ValueError('Unterminated escape.')
                    following=text[at];at+=1
                    parts.append({'n':'\n','t':'\t','r':'\r','"':'"','\\':'\\'}.get(following,'\\'+following))
                else:parts.append(char)
            else:raise ValueError('Unterminated string.')
            yield ('string',''.join(parts))
        else:
            start=at
            while at<length and not text[at].isspace() and text[at] not in '{}"':
                if text.startswith('//',at) or text.startswith('/*',at):break
                at+=1
            if at==start:raise ValueError('Invalid token.')
            yield ('string',text[start:at])


def _parse_loginusers(text):
    # Preserve quoted braces as text, including PersonaNames such as '{'.
    tokens=list(_tokens(text));position=0
    def block(depth=0,nested=False):
        nonlocal position
        if depth>32:raise ValueError('Excessive nesting.')
        result={}
        while position<len(tokens):
            kind,key=tokens[position];position+=1
            if kind=='brace' and key=='}':
                if nested:return result
                raise ValueError('Unexpected closing brace.')
            if kind=='brace' or key.casefold() in ('#include','#base') or position>=len(tokens):
                raise ValueError('Unsupported metadata structure.')
            key=key.casefold()
            if key in result:raise ValueError('Duplicate metadata key.')
            kind,value=tokens[position];position+=1
            if kind=='brace' and value=='{':value=block(depth+1,True)
            elif kind=='brace':raise ValueError('Missing metadata value.')
            result[key]=value
        if nested:raise ValueError('Missing closing brace.')
        return result
    parsed=block()
    if set(parsed)!= {'users'} or not isinstance(parsed['users'],dict):
        raise ValueError('Missing users root.')
    return parsed['users']


def _number(value):
    if not isinstance(value,str) or not value.isascii() or not value.isdecimal() or len(value)>20:return 0
    return int(value)


def discover_accounts(roots):
    accounts=[];seen=set()
    for value in roots:
        root=Path(value).resolve()
        if root in seen:continue
        seen.add(root);userdata=root/'userdata'
        if not userdata.is_dir():continue
        metadata={};login=root/'config/loginusers.vdf'
        if login.exists():
            try:
                if login.stat().st_size>2*1024*1024:raise ValueError('Oversized metadata.')
                users=_parse_loginusers(login.read_text(encoding='utf-8-sig'))
            except (UnicodeError,ValueError) as exc:
                raise ValueError('Could not read Steam loginusers.vdf account metadata.') from None
            for steam_id,fields in users.items():
                numeric=_number(steam_id)
                if not 0xffffffff<numeric<=0xffffffffffffffff or not isinstance(fields,dict):continue
                account=str(numeric&0xffffffff)
                if account in metadata:raise ValueError('Ambiguous Steam loginusers.vdf account IDs.')
                metadata[account]=fields
        for folder in sorted(userdata.iterdir(),key=lambda p:p.name):
            if folder.is_symlink() or not folder.is_dir() or not _account_id(folder.name):continue
            fields=metadata.get(folder.name,{})
            display=fields.get('personaname','')
            display=''.join(c for c in display if c.isprintable()).strip() if isinstance(display,str) else ''
            accounts.append(SteamAccount(root,folder.name,display or 'Steam account '+folder.name,
                                         fields.get('mostrecent')=='1',_number(fields.get('timestamp'))))
    return accounts


def _windows_active_account():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam\ActiveProcess') as key:
            number=winreg.QueryValueEx(key,'ActiveUser')[0]
        if type(number) is not int or not 0<number<=0xffffffff:return None
        root=None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
                root=Path(winreg.QueryValueEx(key,'SteamPath')[0]).resolve()
        except (OSError,TypeError):pass
        return str(number),root
    except (ImportError,OSError):return None


def _unique_timestamp(accounts):
    if not accounts:return None
    maximum=max(account.timestamp for account in accounts)
    matches=[account for account in accounts if account.timestamp==maximum]
    return matches[0] if maximum>0 and len(matches)==1 else None


def _linux_active_root(roots):
    # Match only executable paths under a known installation. A sandbox's /app
    # path cannot safely identify a host installation and is left unresolved.
    roots=set(roots);found=set()
    try:processes=list(PROC_ROOT.iterdir())
    except OSError:return None
    for process in processes:
        if not process.name.isdigit():continue
        try:
            if process.stat().st_uid!=os.getuid():continue
            if (process/'comm').read_text().strip()!='steam':continue
            if any(line.startswith('State:') and line.split()[1]=='Z'
                   for line in (process/'status').read_text().splitlines()):continue
            executable=Path(os.readlink(process/'exe'))
            matches=[root for root in roots if executable.is_relative_to(root)]
            if matches:found.add(max(matches,key=lambda path:len(path.parts)))
        except OSError:continue
    return next(iter(found)) if len(found)==1 else None


def select_account(accounts,platform=None):
    accounts=list(dict.fromkeys(accounts));platform=platform or sys.platform
    if platform=='win32':
        active=_windows_active_account()
        if active:
            account,root=active
            candidates=[a for a in accounts if a.account_id==account and (root is None or a.steam_root==root)]
            if len(candidates)==1:return candidates[0]
    if platform=='linux' and len({account.steam_root for account in accounts})>1:
        active_root=_linux_active_root(account.steam_root for account in accounts)
        if active_root is not None:
            accounts=[account for account in accounts if account.steam_root==active_root]
    recent=[account for account in accounts if account.most_recent]
    if len(recent)==1:return recent[0]
    if recent:return _unique_timestamp(recent)
    selected=_unique_timestamp(accounts)
    if selected:return selected
    return accounts[0] if len(accounts)==1 else None


def _windows_session_id():
    import ctypes
    value=ctypes.c_uint32();kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.ProcessIdToSessionId.argtypes=[ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)]
    kernel.ProcessIdToSessionId.restype=ctypes.c_int
    if not kernel.ProcessIdToSessionId(os.getpid(),ctypes.byref(value)):
        raise OSError('Could not identify the current Windows session.')
    return value.value


def steam_is_running(platform=None):
    platform=platform or sys.platform
    if platform=='win32':
        session=_windows_session_id()
        result=subprocess.run(['tasklist','/FI','IMAGENAME eq steam.exe','/FI','SESSION eq '+str(session),'/FO','CSV','/NH'],
                              capture_output=True,text=True,check=True,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return any(row and row[0].casefold()=='steam.exe' for row in csv.reader(io.StringIO(result.stdout)))
    if platform!='linux':raise ValueError('Steam client control supports Windows and Linux.')
    uid=os.getuid()
    for process in PROC_ROOT.iterdir():
        if not process.name.isdigit():continue
        try:
            if process.stat().st_uid!=uid:continue
            if (process/'comm').read_text().strip()!='steam':continue
            status=(process/'status').read_text()
            if any(line.startswith('State:') and line.split()[1]=='Z' for line in status.splitlines()):continue
            return True
        except (OSError,ProcessLookupError):continue
    return False


def _client_environment():
    env=dict(os.environ);private=[]
    if env.get('PYTHONHOME'):private.append(Path(env['PYTHONHOME']).resolve())
    if getattr(sys,'_MEIPASS',None):private.append(Path(sys._MEIPASS).resolve())
    for key in ['PYTHONHOME','PYTHONPATH','TK_LIBRARY','TCL_LIBRARY','LD_PRELOAD']:env.pop(key,None)
    original=env.pop('LD_LIBRARY_PATH_ORIG',None)
    libraries=original if original is not None else env.get('LD_LIBRARY_PATH','')
    kept=[]
    for entry in libraries.split(':'):
        if not entry:continue
        path=Path(entry).resolve()
        if any(path.is_relative_to(root) for root in private):continue
        kept.append(entry)
    if kept:env['LD_LIBRARY_PATH']=':'.join(kept)
    else:env.pop('LD_LIBRARY_PATH',None)
    return env


def _steam_command(root,platform):
    root=Path(root).resolve()
    if platform=='win32':
        executable=root/'steam.exe'
        if not executable.is_file():raise FileNotFoundError('Steam.exe was not found in the selected installation.')
        return [str(executable)]
    if platform!='linux':raise ValueError('Steam client control supports Windows and Linux.')
    if 'com.valvesoftware.Steam' in root.parts and '.var' in root.parts:
        flatpak=shutil.which('flatpak')
        if not flatpak:raise FileNotFoundError('The Flatpak command was not found.')
        return [flatpak,'run','com.valvesoftware.Steam']
    script=root/'steam.sh'
    if script.is_file() and os.access(script,os.X_OK):return [str(script)]
    steam=shutil.which('steam')
    if not steam:raise FileNotFoundError('The Steam command was not found.')
    return [steam]


def _start_client(root,platform,shutdown=False):
    command=_steam_command(root,platform)
    if shutdown:command.append('-shutdown')
    with clean_windows_dll_search():
        return subprocess.Popen(command,cwd=Path(root),env=_client_environment(),
                                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def close_steam(steam_root,*,platform=None,timeout=45):
    platform=platform or sys.platform
    if not isinstance(timeout,(int,float)) or not 0<timeout<=45:
        raise ValueError('Steam shutdown timeout must be between 0 and 45 seconds.')
    if not steam_is_running(platform):return False
    process=_start_client(steam_root,platform,shutdown=True)
    deadline=time.monotonic()+timeout
    while steam_is_running(platform):
        if time.monotonic()>=deadline:
            process.poll()
            raise TimeoutError('Steam did not close in time. No shortcut files were changed.')
        time.sleep(0.2)
    process.poll()
    return True


def reopen_steam(steam_root,platform=None):
    _start_client(steam_root,platform or sys.platform)
