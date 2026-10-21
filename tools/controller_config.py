"""Prepare a native DirectInput pad profile for manual validation. Own work: djultra64.

Numeric button tokens and axis tokens follow the original launcher's output format.
This configures input only: dynamic glyphs and device-family detection are separate,
still-pending work. Xbox-compatible button/trigger ordering must be tested on hardware.
"""
import argparse
import copy
from pathlib import Path
from tools.pml import Pml
from launcher.controllers import ControllerProfile

PROFILE='djultra64_gamepad_test'
BUTTONS={
 'e_Button_A':'0', 'e_Button_B':'1', 'e_Button_C':'2', 'e_Button_D':'3',
 'e_Button_E':'4', 'e_Button_F':'5', 'e_Button_Back':'6', 'e_Button_Start':'7',
 'e_Button_LeftTrigger_1':'AXE_POS_LZ', 'e_Button_RightTrigger_1':'AXE_NEG_LZ',
 'e_Axe1_Left':'AXE_NEG_LX', 'e_Axe1_Right':'AXE_POS_LX',
 'e_Axe1_Up':'AXE_NEG_LY', 'e_Axe1_Down':'AXE_POS_LY',
}

def value(node,name):
 return dict(node.properties)[Pml.key(name)]

def put(node,name,new):
 key=Pml.key(name)
 for i,(k,old) in enumerate(node.properties):
  if k==key:
   node.properties[i]=(k,str(new));return
 raise ValueError('Missing controller property '+name)

def configure_pad(raw: bytes, device_index: int, *, menu_profile: ControllerProfile | None=None) -> bytes:
 if not 1<=device_index<=4:
  raise ValueError('Choose an enumerated pad index from 1 to 4; 0 is keyboard')
 config=Pml(raw);pads=config.node('Mappings/Assign').children
 if len(pads)!=5:raise ValueError('Unsupported virtual-controller layout')
 if any(value(pad,'Controller')==str(device_index) for pad in pads[1:]):
  raise ValueError('This controller is already assigned to another player')
 # The engine supports four players plus a keyboard controller. Keep the existing
 # keyboard mapping available in a spare slot; never displace another player.
 keyboard=next((n for n in pads[1:] if value(n,'Controller')=='0'),None)
 if keyboard is None:
  keyboard=next((n for n in reversed(pads[1:]) if value(n,'Controller')=='-1'),None)
 if keyboard is None:raise ValueError('No free slot for the keyboard fallback')
 if value(pads[0],'Controller')=='0':
  keyboard.properties=copy.deepcopy(pads[0].properties)
 for section in ['Menu','InGame']:
  group=config.node('Mappings/'+section)
  if not group.children:raise ValueError('Missing keyboard profile')
  index=next((i for i,n in enumerate(group.children) if value(n,'Name')==PROFILE),None)
  if index is None:
   node=copy.deepcopy(group.children[0]);index=len(group.children)
   node.properties=[(k,PROFILE if k==Pml.key('Name') else '-1') for k,v in node.properties]
   group.children.append(node)
  node=group.children[index]
  bindings=BUTTONS.copy()
  if section=='Menu':bindings.update((menu_profile or ControllerProfile()).engine_bindings())
  for key,new in bindings.items():put(node,key,new)
  put(pads[0],section,index)
 put(pads[0],'Controller',device_index)
 return config.encode()

def _active_owned_menu(config):
 try:
  pads=config.node('Mappings/Assign').children
  profiles=config.node('Mappings/Menu').children
  index=int(value(pads[0],'Menu'))
  if index<0 or index>=len(profiles) or value(profiles[index],'Name')!=PROFILE:
   raise ValueError('Choose the active portable menu profile before remapping menu actions.')
  return profiles[index]
 except (StopIteration,KeyError,IndexError) as exc:
  raise ValueError('The active portable menu profile was not found.') from exc

def read_existing_menu_positions(raw: bytes) -> str:
 config=Pml(raw);profile=_active_owned_menu(config)
 from launcher.controllers import ACTIONS
 result=''.join(value(profile,engine) for engine,_ in ACTIONS.values())
 if len(result)!=8 or any(c not in '01234567' for c in result):
  raise ValueError('The active portable menu profile uses unsupported button positions.')
 return result

def remap_existing_menu(raw: bytes,profile: ControllerProfile) -> bytes:
 config=Pml(raw);target=_active_owned_menu(config)
 for action,new in profile.engine_bindings().items():put(target,action,new)
 return config.encode()

def remap_existing_controls(raw: bytes,profile: ControllerProfile) -> bytes:
 """Keep shared logical-button prompts and both owned input contexts together."""
 config=Pml(raw);menu=_active_owned_menu(config)
 try:
  pads=config.node('Mappings/Assign').children
  profiles=config.node('Mappings/InGame').children
  index=int(value(pads[0],'InGame'))
  if index<0 or index>=len(profiles) or value(profiles[index],'Name')!=PROFILE:
   raise ValueError('Choose the active portable gameplay profile before remapping controls.')
  gameplay=profiles[index]
 except (StopIteration,KeyError,IndexError) as exc:
  raise ValueError('The active portable gameplay profile was not found.') from exc
 for target in [menu,gameplay]:
  for action,new in profile.engine_bindings().items():put(target,action,new)
 return config.encode()

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--config',type=Path,required=True)
 parser.add_argument('--device-index',type=int,required=True)
 args=parser.parse_args();raw=args.config.read_bytes();result=configure_pad(raw,args.device_index)
 if result==raw:
  print('Profile already configured; no changes')
 else:
  backup=args.config.with_name(args.config.stem+'.before-gamepad.pml')
  with backup.open('xb') as f:f.write(raw)
  args.config.write_bytes(result)
  print('Prepared input test profile; backup:',backup)
