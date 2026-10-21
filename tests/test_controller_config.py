import copy
from pathlib import Path
import unittest
from tools.pml import Pml

SOURCE=Path('TopSpin/program files/Atari/TopSpin/Config.pml')
@unittest.skipUnless(SOURCE.is_file(), 'Private Config.pml integration fixture is unavailable')
class ControllerConfigTests(unittest.TestCase):
 def test_native_pad_profile_preserves_other_settings_and_keyboard(self):
  from tools.controller_config import configure_pad
  raw=SOURCE.read_bytes();before=Pml(raw);after=Pml(configure_pad(raw,1))
  for n in before.root.children:
   if n.key!=Pml.key('Mappings'):
    self.assertEqual(n,next(c for c in after.root.children if c.key==n.key))
  for path in ['Mappings/Menu','Mappings/InGame']:
   self.assertEqual(before.node(path).children[0],after.node(path).children[0])
   self.assertEqual(len(after.node(path).children),2)
  self.assertEqual(after.get('Mappings/Assign/Pad','Controller'),'1')
  pads=after.node('Mappings/Assign').children
  self.assertEqual([v for k,v in pads[4].properties if k==Pml.key('Controller')],['0'])
  self.assertEqual(sum(dict(n.properties)[Pml.key('Controller')]=='1' for n in pads),1)
 def test_reapplying_own_profile_does_not_duplicate_it(self):
  from tools.controller_config import configure_pad
  once=configure_pad(SOURCE.read_bytes(),1)
  self.assertEqual(configure_pad(once,1),once)
 def test_no_available_keyboard_slot_is_rejected(self):
  from tools.controller_config import configure_pad
  p=Pml(SOURCE.read_bytes())
  for pad in p.node('Mappings/Assign').children[1:]:
   pad.properties=[(k,'2' if k==Pml.key('Controller') else v) for k,v in pad.properties]
  with self.assertRaisesRegex(ValueError,'keyboard'):
   configure_pad(p.encode(),1)
 def test_unknown_or_keyboard_device_cannot_be_used_as_pad(self):
  from tools.controller_config import configure_pad
  for device in [-1,0,5]:
   with self.subTest(device=device),self.assertRaises(ValueError):configure_pad(SOURCE.read_bytes(),device)

 def test_device_already_assigned_to_another_player_is_rejected(self):
  from tools.controller_config import configure_pad,put
  config=Pml(SOURCE.read_bytes())
  put(config.node('Mappings/Assign').children[1],'Controller',1)
  raw=config.encode()
  with self.assertRaisesRegex(ValueError,'already assigned'):
   configure_pad(raw,1)
  self.assertEqual(config.encode(),raw)

 def test_menu_remap_matches_prompt_without_changing_gameplay_or_keyboard(self):
  from tools.controller_config import configure_pad
  from launcher.controllers import ControllerProfile
  profile=ControllerProfile({'confirm':'east','back':'south'})
  raw=SOURCE.read_bytes();before=Pml(raw)
  after=Pml(configure_pad(raw,1,menu_profile=profile))
  menu=after.node('Mappings/Menu').children[-1]
  game=after.node('Mappings/InGame').children[-1]
  self.assertEqual(dict(menu.properties)[Pml.key('e_Button_A')],'1')
  self.assertEqual(dict(game.properties)[Pml.key('e_Button_A')],'0')
  self.assertEqual(profile.prompt('confirm','switch').name,'A')
  self.assertEqual(before.node('Mappings/Menu').children[0],after.node('Mappings/Menu').children[0])

 def test_launcher_remap_updates_only_active_owned_menu_profile(self):
  from tools.controller_config import configure_pad,remap_existing_menu
  from launcher.controllers import ControllerProfile
  raw=configure_pad(SOURCE.read_bytes(),1);before=Pml(raw)
  changed=remap_existing_menu(raw,ControllerProfile({'confirm':'east','back':'south'}));after=Pml(changed)
  self.assertEqual(before.node('Mappings/InGame'),after.node('Mappings/InGame'))
  self.assertEqual(before.node('Mappings/Assign'),after.node('Mappings/Assign'))
  self.assertEqual(before.node('Mappings/Menu').children[0],after.node('Mappings/Menu').children[0])
  self.assertEqual(dict(after.node('Mappings/Menu').children[1].properties)[Pml.key('e_Button_A')],'1')
  with self.assertRaisesRegex(ValueError,'active portable menu profile'):remap_existing_menu(SOURCE.read_bytes(),ControllerProfile())

 def test_shared_launcher_bindings_match_prompts_in_menu_and_gameplay(self):
  from tools.controller_config import configure_pad,remap_existing_controls
  from launcher.controllers import ControllerProfile
  raw=configure_pad(SOURCE.read_bytes(),1);before=Pml(raw)
  result=Pml(remap_existing_controls(raw,ControllerProfile({'confirm':'east','back':'south'})))
  for section in ['Menu','InGame']:
   profiles=result.node('Mappings/'+section).children
   self.assertEqual(profiles[0],before.node('Mappings/'+section).children[0])
   self.assertEqual(dict(profiles[1].properties)[Pml.key('e_Button_A')],'1')
   self.assertEqual(dict(profiles[1].properties)[Pml.key('e_Button_B')],'0')
  self.assertEqual(before.node('Mappings/Assign'),result.node('Mappings/Assign'))
