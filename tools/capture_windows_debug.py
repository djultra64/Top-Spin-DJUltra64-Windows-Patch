"""Read one owned process's session-local OutputDebugString diagnostics. djultra64.

Run in the same interactive Windows session as the game. Does not launch or
modify a process, send input, install hooks, or write unrelated debug messages.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import time


def matching_message(buffer, target_pid, encoding='utf-8'):
    """Synthetic-testable DBWIN decoder; unrelated messages are discarded."""
    if len(buffer)<4 or int.from_bytes(buffer[:4],'little')!=target_pid:
        return None
    return buffer[4:].split(b'\0',1)[0].decode(encoding,errors='replace')


def _status(path, payload):
    if path is None:return
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def capture(pid, executable, output, ready_file=None, seconds=30, stop_file=None):
    if os.name!='nt':raise RuntimeError('This helper runs only on Windows.')
    if pid<=0 or not 0<seconds<=300:raise ValueError('Choose an owned PID and a duration from 1 to 300 seconds.')
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    H=wintypes.HANDLE;D=wintypes.DWORD;P=ctypes.c_void_p
    signatures={
        'OpenProcess':([D,wintypes.BOOL,D],H),
        'QueryFullProcessImageNameW':([H,D,wintypes.LPWSTR,ctypes.POINTER(D)],wintypes.BOOL),
        'CreateFileMappingW':([H,P,D,D,D,wintypes.LPCWSTR],H),
        'CreateEventW':([P,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR],H),
        'MapViewOfFile':([H,D,D,D,ctypes.c_size_t],P),
        'UnmapViewOfFile':([P],wintypes.BOOL),
        'CloseHandle':([H],wintypes.BOOL),
        'SetEvent':([H],wintypes.BOOL),
        'WaitForSingleObject':([H,D],D),
        'ProcessIdToSessionId':([D,ctypes.POINTER(D)],wintypes.BOOL),
    }
    for name,(args,result) in signatures.items():
        fn=getattr(kernel,name);fn.argtypes=args;fn.restype=result
    handles=[];view=None;count=0
    def check(value):
        if not value:raise ctypes.WinError(ctypes.get_last_error())
        return value
    try:
        process=check(kernel.OpenProcess(0x101000,False,pid));handles.append(process)
        path=ctypes.create_unicode_buffer(32768);length=D(len(path))
        check(kernel.QueryFullProcessImageNameW(process,0,path,ctypes.byref(length)))
        expected=os.path.normcase(os.path.abspath(executable))
        if os.path.normcase(os.path.abspath(path.value))!=expected:
            raise ValueError('The target PID does not match the explicitly selected executable.')
        session=D();own_session=D()
        check(kernel.ProcessIdToSessionId(pid,ctypes.byref(session)))
        check(kernel.ProcessIdToSessionId(os.getpid(),ctypes.byref(own_session)))
        if session.value!=own_session.value:
            raise ValueError('The helper and target must run in the same interactive session.')
        # Refuse an existing monitor instead of sharing/stealing its buffer.
        ctypes.set_last_error(0)
        mapping=check(kernel.CreateFileMappingW(H(-1),None,4,0,4096,r'Local\DBWIN_BUFFER'))
        existed=ctypes.get_last_error()==183;handles.append(mapping)
        if existed:raise RuntimeError('A DBWIN monitor is already active in this session; capture was not started.')
        events=[]
        for name in [r'Local\DBWIN_BUFFER_READY',r'Local\DBWIN_DATA_READY']:
            ctypes.set_last_error(0)
            event=check(kernel.CreateEventW(None,False,False,name));existed=ctypes.get_last_error()==183
            handles.append(event);events.append(event)
            if existed:raise RuntimeError('A DBWIN event is already in use; capture was not started.')
        available,data_ready=events
        view=check(kernel.MapViewOfFile(mapping,4,0,0,4096))
        output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('w',encoding='utf-8') as stream:
            check(kernel.SetEvent(available))
            _status(ready_file,{'status':'ready','pid':pid,'session':session.value,'executable':path.value})
            deadline=time.monotonic()+seconds;exited=False
            while time.monotonic()<deadline:
                if stop_file is not None and Path(stop_file).exists():break
                wait=kernel.WaitForSingleObject(data_ready,100)
                if wait==0:
                    try:
                        # Read no unrelated process's message bytes at all.
                        message_pid=ctypes.c_uint32.from_address(view).value
                        if message_pid==pid:
                            raw=ctypes.string_at(view+4,4092)
                            message=matching_message(pid.to_bytes(4,'little')+raw,pid,'mbcs')
                            stream.write(json.dumps({'time':time.time(),'pid':pid,'message':message})+'\n')
                            stream.flush();count+=1
                    finally:check(kernel.SetEvent(available))
                elif wait!=258:raise ctypes.WinError(ctypes.get_last_error())
                if kernel.WaitForSingleObject(process,0)==0:
                    if exited and wait==258:break
                    exited=True
        summary={'status':'complete','pid':pid,'session':session.value,'messages':count,'target_exited':exited}
        _status(ready_file,summary);return summary
    except BaseException as exc:
        _status(ready_file,{'status':'error','pid':pid,'error':str(exc)})
        raise
    finally:
        if view:kernel.UnmapViewOfFile(view)
        for handle in reversed(handles):kernel.CloseHandle(handle)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ready-file',type=Path)
    parser.add_argument('--stop-file',type=Path)
    parser.add_argument('--seconds',type=float,default=30)
    args=parser.parse_args()
    print(json.dumps(capture(args.pid,args.exe,args.output,args.ready_file,args.seconds,args.stop_file)))
