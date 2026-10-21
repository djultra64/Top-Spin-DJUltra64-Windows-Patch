"""Physical controller layout and menu-action policy. Own work: djultra64.

This module does not poll devices or draw inside the game. A runtime adapter must
supply meaningful device activity and consume the same profile for input/prompts.
VID/PID detection describes the exposed device, not a controller hidden by Steam
Input. Such virtual devices need metadata from the adapter or a manual override.
"""
from dataclasses import dataclass
import math

FAMILIES=('xbox360','xbox','ps4','ps5','switch','unknown')
# These menu actions follow the original engine's independent logical bindings.
ACTIONS={
    'confirm':('e_Button_A','south'), 'back':('e_Button_B','east'),
    'regenerate':('e_Button_C','west'), 'help':('e_Button_D','north'),
    'next_view':('e_Button_E','left_shoulder'),
    'previous_view':('e_Button_F','right_shoulder'),
    'select':('e_Button_Back','select'), 'pause':('e_Button_Start','start'),
}
DI_TOKENS={'south':'0','east':'1','west':'2','north':'3',
           'left_shoulder':'4','right_shoulder':'5','select':'6','start':'7'}
NAMES={
    'xbox360':('A','B','X','Y','LB','RB','Back','Start'),
    'xbox':('A','B','X','Y','LB','RB','View','Menu'),
    'ps4':('Cross','Circle','Square','Triangle','L1','R1','Share','Options'),
    'ps5':('Cross','Circle','Square','Triangle','L1','R1','Create','Options'),
    'switch':('B','A','Y','X','L','R','Minus','Plus'),
    'unknown':('South button','East button','West button','North button',
               'Left shoulder','Right shoulder','Select','Start'),
}
GLYPHS={
    'xbox360':('a','b','x','y','lb','rb','back','start'),
    'xbox':('a','b','x','y','lb','rb','view','menu'),
    'ps4':('cross','circle','square','triangle','l1','r1','share','options'),
    'ps5':('cross','circle','square','triangle','l1','r1','create','options'),
    'switch':('b','a','y','x','l','r','minus','plus'),
    'unknown':tuple(DI_TOKENS),
}

@dataclass(frozen=True)
class Prompt:
    name: str
    glyph: str
    position: str

class ControllerProfile:
    def __init__(self,remap=None):
        self._positions={action:position for action,(_,position) in ACTIONS.items()}
        for action,position in (remap or {}).items():
            if action not in ACTIONS or position not in DI_TOKENS:
                raise ValueError('Choose a known action and physical button position.')
            self._positions[action]=position

    def prompt(self,action,family):
        if family not in FAMILIES:raise ValueError('Unknown controller family.')
        if action not in self._positions:raise ValueError('Unknown controller action.')
        position=self._positions[action];index=tuple(DI_TOKENS).index(position)
        namespace='playstation' if family in ('ps4','ps5') else family
        return Prompt(NAMES[family][index],namespace+'.'+GLYPHS[family][index],position)

    def engine_bindings(self):
        return {ACTIONS[action][0]:DI_TOKENS[position]
                for action,position in self._positions.items()}


def detect_family(vendor,product):
    # Match exposed, identified products. Avoid treating every Sony/Nintendo USB
    # product as a controller or guessing a hidden pad behind a virtual device.
    if vendor==0x045e and product in (0x028e,0x028f):return 'xbox360'
    if vendor==0x045e and product in (0x02d1,0x02dd,0x02e0,0x02ea,0x02fd,0x0b12,0x0b13):return 'xbox'
    if vendor==0x054c:
        if product in (0x05c4,0x09cc,0x0ba0):return 'ps4'
        if product in (0x0ce6,0x0df2):return 'ps5'
    if vendor==0x057e and product in (0x2006,0x2007,0x2009,0x200e):return 'switch'
    return 'unknown'

class ActiveDevice:
    def __init__(self,manual_family='auto',deadzone=0.2):
        if manual_family not in ('auto',)+FAMILIES:
            raise ValueError('Choose Auto or a supported controller family.')
        if not math.isfinite(deadzone) or not 0<deadzone<1:
            raise ValueError('Invalid activity deadzone.')
        self.manual_family=manual_family;self.deadzone=deadzone
        self._current=('keyboard','keyboard');self._last=-math.inf

    @property
    def current(self):
        device,family=self._current
        if family!='keyboard' and self.manual_family!='auto':family=self.manual_family
        return device,family

    def observe(self,device,family,timestamp,*,button_pressed=False,axis=0.0):
        if family not in ('keyboard',)+FAMILIES:raise ValueError('Unknown controller family.')
        if not math.isfinite(timestamp) or not math.isfinite(axis):
            raise ValueError('Invalid input activity sample.')
        # Polling an idle device must not steal the prompts. Adapters must pass
        # button edges or deliberate stick activity, not held-button poll data.
        if timestamp<=self._last or not (button_pressed or abs(axis)>self.deadzone):return
        self._current=(device,family);self._last=timestamp


def profile_from_positions(positions):
    if not isinstance(positions,str) or len(positions)!=8 or any(c not in '01234567' for c in positions):
        raise ValueError('Menu controls must use eight physical button positions.')
    physical=tuple(DI_TOKENS)
    return ControllerProfile({action:physical[int(value)] for action,value in zip(ACTIONS,positions)})
