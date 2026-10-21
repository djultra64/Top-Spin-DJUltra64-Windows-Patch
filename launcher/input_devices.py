"""Read-only SDL3 gamepad samples and activity policy. Own work: djultra64.

No input injection, virtual-device creation, vibration or exclusive acquisition.
Runtime glyph rendering and game input adaptation consume this data separately.
SDL3's gamepad API uses physical positions, including on Nintendo controllers.
"""
from dataclasses import asdict,dataclass
from pathlib import Path
import argparse
import ctypes as C
import json
import math
import time
from launcher.controllers import ActiveDevice,FAMILIES,detect_family

BUTTONS=('south','east','west','north','select','guide','start','left_stick',
         'right_stick','left_shoulder','right_shoulder','dpad_up','dpad_down','dpad_left','dpad_right')

@dataclass(frozen=True)
class PadSample:
    device: str
    name: str
    family: str
    buttons: frozenset[str]
    axes: tuple[float,...]


def sample_from_sdl(instance,name,kind,vendor,product,buttons,axes):
    if len(buttons)!=len(BUTTONS) or len(axes)!=6:
        raise ValueError('Unexpected SDL gamepad state layout.')
    family=detect_family(vendor,product)
    if vendor!=0x28de and family=='unknown':
        family={2:'xbox360',3:'xbox',5:'ps4',6:'ps5',7:'switch',8:'switch',9:'switch',10:'switch'}.get(kind,'unknown')
    normalized=tuple(max(-1.0,min(1.0,value/(32768.0 if value<0 else 32767.0))) for value in axes)
    return PadSample(str(instance),name,family,
                     frozenset(key for key,pressed in zip(BUTTONS,buttons) if pressed),normalized)

class InputActivity:
    def __init__(self,manual_family='auto',deadzone=0.25):
        self._tracker=ActiveDevice(manual_family,deadzone)
        self._previous={};self._last=-math.inf

    @property
    def current(self):return self._tracker.current

    def update(self,samples,timestamp,*,keyboard_pressed=False):
        if not math.isfinite(timestamp):raise ValueError('Invalid sample time.')
        if timestamp<=self._last:return self.current
        samples=list(samples);seen=set()
        for s in samples:
            if (not s.device or s.device in seen or s.family not in FAMILIES
                    or len(s.axes)!=6 or not s.buttons.issubset(BUTTONS)
                    or any(not math.isfinite(v) or abs(v)>1 for v in s.axes)
                    or any(v<0 for v in s.axes[4:])):
                raise ValueError('Invalid gamepad sample.')
            seen.add(s.device)
        for s in samples:
            previous=self._previous.get(s.device)
            old_buttons=previous.buttons if previous else frozenset()
            old_axes=previous.axes if previous else (0,)*6
            new_button=bool(s.buttons-old_buttons)
            movement=max((abs(value) for value,old in zip(s.axes,old_axes)
                          if abs(value-old)>0.05),default=0.0)
            if not keyboard_pressed:
                self._tracker.observe(s.device,s.family,timestamp,button_pressed=new_button,axis=movement)
        if keyboard_pressed or (self.current[0]!='keyboard' and self.current[0] not in seen):
            self._tracker.observe('keyboard','keyboard',timestamp,button_pressed=True)
        self._previous={s.device:s for s in samples};self._last=timestamp
        return self.current

class SDL3Backend:
    def __init__(self,library: Path):
        # A caller supplies an explicit bundled path, never an arbitrary PATH DLL.
        self.library=Path(library).resolve();self.sdl=None;self._pads={}

    def _fn(self,name,result,args):
        fn=getattr(self.sdl,name);fn.restype=result;fn.argtypes=args;return fn

    def __enter__(self):
        self.sdl=C.CDLL(str(self.library))
        self._fn('SDL_SetHint',C.c_bool,[C.c_char_p,C.c_char_p])(
            b'SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS',b'1')
        self.error=self._fn('SDL_GetError',C.c_char_p,[])
        self.quit=self._fn('SDL_QuitSubSystem',None,[C.c_uint])
        if not self._fn('SDL_InitSubSystem',C.c_bool,[C.c_uint])(0x2000):
            raise ValueError('Unable to initialize gamepad support: '+self.error().decode('utf-8','replace'))
        try:
            self.get=self._fn('SDL_GetGamepads',C.POINTER(C.c_uint),[C.POINTER(C.c_int)])
            self.free=self._fn('SDL_free',None,[C.c_void_p])
            self.open=self._fn('SDL_OpenGamepad',C.c_void_p,[C.c_uint])
            self.close=self._fn('SDL_CloseGamepad',None,[C.c_void_p])
            self.update=self._fn('SDL_UpdateGamepads',None,[])
            self.name=self._fn('SDL_GetGamepadName',C.c_char_p,[C.c_void_p])
            self.kind=self._fn('SDL_GetGamepadType',C.c_int,[C.c_void_p])
            self.vendor=self._fn('SDL_GetGamepadVendor',C.c_ushort,[C.c_void_p])
            self.product=self._fn('SDL_GetGamepadProduct',C.c_ushort,[C.c_void_p])
            self.button=self._fn('SDL_GetGamepadButton',C.c_bool,[C.c_void_p,C.c_int])
            self.axis=self._fn('SDL_GetGamepadAxis',C.c_short,[C.c_void_p,C.c_int])
        except Exception:
            self.quit(0x2000);raise
        return self

    def poll(self):
        self.update();count=C.c_int();ids=self.get(C.byref(count))
        if not ids:raise ValueError('Unable to enumerate gamepads: '+self.error().decode('utf-8','replace'))
        try:
            if not 0<=count.value<=256:raise ValueError('Unexpected gamepad count.')
            connected={ids[i] for i in range(count.value)}
        finally:self.free(ids)
        for key in list(self._pads):
            if key not in connected:self.close(self._pads.pop(key))
        for key in sorted(connected):
            if key not in self._pads:
                pad=self.open(key)
                if pad:self._pads[key]=pad
        result=[]
        for key,pad in self._pads.items():
            result.append(sample_from_sdl(key,(self.name(pad) or b'Gamepad').decode('utf-8','replace'),
                self.kind(pad),self.vendor(pad),self.product(pad),
                [self.button(pad,i) for i in range(len(BUTTONS))],
                [self.axis(pad,i) for i in range(6)]))
        return result

    def __exit__(self,*args):
        for pad in self._pads.values():self.close(pad)
        self._pads.clear();self.quit(0x2000)


def main():
    parser=argparse.ArgumentParser(description='Read-only controller diagnostics; no game launch.')
    parser.add_argument('--library',type=Path,required=True)
    args=parser.parse_args()
    with SDL3Backend(args.library) as backend:
        backend.poll();time.sleep(0.05)
        samples=backend.poll()
        print(json.dumps([dict(asdict(s),buttons=sorted(s.buttons)) for s in samples],indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
