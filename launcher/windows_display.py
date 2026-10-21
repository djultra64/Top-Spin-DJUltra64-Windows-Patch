"""Size only this launch's native game window; never generate input. djultra64."""
import json
from pathlib import Path
import threading

def output_bounds(resolution,monitor):
    width,height=map(int,resolution.split('x'))
    left,top,right,bottom=monitor
    if width>right-left or height>bottom-top:
        raise ValueError('The output resolution exceeds this display. Choose its native resolution or smaller.')
    return left+(right-left-width)//2,top+(bottom-top-height)//2,width,height

def resize_game_window(pid,resolution,fullscreen,*,title='Top Spin'):
    import ctypes
    from ctypes import wintypes as w
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    class Monitor(ctypes.Structure):
        _fields_=[('size',w.DWORD),('monitor',w.RECT),('work',w.RECT),('flags',w.DWORD)]
    user.EnumWindows.argtypes=[callback_type,w.LPARAM];user.EnumWindows.restype=w.BOOL
    user.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    user.IsWindowVisible.argtypes=[w.HWND];user.IsWindowVisible.restype=w.BOOL
    user.GetWindowTextW.argtypes=[w.HWND,w.LPWSTR,ctypes.c_int]
    user.GetClientRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
    user.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];user.GetWindowLongW.restype=w.LONG
    user.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,w.LONG];user.SetWindowLongW.restype=w.LONG
    user.MonitorFromWindow.argtypes=[w.HWND,w.DWORD];user.MonitorFromWindow.restype=w.HANDLE
    user.GetMonitorInfoW.argtypes=[w.HANDLE,ctypes.POINTER(Monitor)]
    user.AdjustWindowRectEx.argtypes=[ctypes.POINTER(w.RECT),w.DWORD,w.BOOL,w.DWORD]
    user.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
    handles=[]
    @callback_type
    def collect(handle,unused):
        owner=w.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(owner))
        if owner.value==pid and user.IsWindowVisible(handle):
            text=ctypes.create_unicode_buffer(256);user.GetWindowTextW(handle,text,256)
            if text.value==title:handles.append(handle)
        return True
    previous=None
    if hasattr(user,'SetThreadDpiAwarenessContext'):
        user.SetThreadDpiAwarenessContext.argtypes=[w.HANDLE]
        user.SetThreadDpiAwarenessContext.restype=w.HANDLE
        previous=user.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    try:
        user.EnumWindows(collect,0)
        if not handles:return None
        handle=handles[0];monitor=Monitor();monitor.size=ctypes.sizeof(Monitor)
        if not user.GetMonitorInfoW(user.MonitorFromWindow(handle,2),ctypes.byref(monitor)):
            raise ctypes.WinError(ctypes.get_last_error())
        rect=monitor.monitor;x,y,width,height=output_bounds(resolution,(rect.left,rect.top,rect.right,rect.bottom))
        style=user.GetWindowLongW(handle,-16)&0xffffffff
        frame=0x00cf0000
        desired=((style&~frame)|0x80000000) if fullscreen else ((style&~0x80000000)|frame)
        client=w.RECT();user.GetClientRect(handle,ctypes.byref(client))
        if client.right-client.left!=width or client.bottom-client.top!=height or style!=desired:
            user.SetWindowLongW(handle,-16,ctypes.c_int32(desired).value)
            frame_rect=w.RECT(0,0,width,height)
            user.AdjustWindowRectEx(ctypes.byref(frame_rect),desired,False,user.GetWindowLongW(handle,-20)&0xffffffff)
            if not user.SetWindowPos(handle,None,x+frame_rect.left,y+frame_rect.top,
                                     frame_rect.right-frame_rect.left,frame_rect.bottom-frame_rect.top,0x34):
                raise ctypes.WinError(ctypes.get_last_error())
        user.GetClientRect(handle,ctypes.byref(client))
        return {'pid':pid,'window':int(handle),'requested_client':[width,height],
                'actual_client':[client.right-client.left,client.bottom-client.top],
                'borderless':fullscreen,'input_events_sent':0}
    finally:
        if previous:user.SetThreadDpiAwarenessContext(previous)

def watch_game_window(pid,settings,log_path,stop):
    """Correct startup-size changes while the game initializes its video device."""
    previous=None
    for _ in range(240):
        if stop.wait(0.25):return
        try:
            result=resize_game_window(pid,settings.output_resolution,settings.fullscreen)
            if result is not None and result!=previous:
                Path(log_path).write_text(json.dumps(result,indent=2)+'\n');previous=result
        except (OSError,ValueError) as exc:
            Path(log_path).write_text(json.dumps({'error':str(exc),'input_events_sent':0})+'\n');return

def start_window_watcher(pid,settings,log_path):
    stop=threading.Event()
    worker=threading.Thread(target=watch_game_window,args=(pid,settings,log_path,stop),daemon=True)
    worker.start()
    return stop,worker
