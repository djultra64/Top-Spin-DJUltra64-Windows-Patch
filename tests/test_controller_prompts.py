"""Own, synthetic physical-layout/input policy tests. djultra64."""
import unittest

class ControllerPromptTests(unittest.TestCase):
    def test_same_physical_action_has_correct_family_name(self):
        from launcher.controllers import ControllerProfile
        p=ControllerProfile()
        for family,name,glyph in [('xbox','A','xbox.a'),('ps4','Cross','playstation.cross'),
                                  ('ps5','Cross','playstation.cross'),('switch','B','switch.b')]:
            with self.subTest(family=family):
                result=p.prompt('confirm',family)
                self.assertEqual((result.name,result.glyph),(name,glyph))
        self.assertEqual(p.prompt('regenerate','switch').name,'Y')
        self.assertEqual(p.prompt('help','switch').name,'X')

    def test_remap_changes_prompt_and_original_engine_binding_together(self):
        from launcher.controllers import ControllerProfile
        p=ControllerProfile({'confirm':'east','back':'south'})
        self.assertEqual(p.prompt('confirm','switch').name,'A')
        self.assertEqual(p.prompt('back','switch').name,'B')
        self.assertEqual(p.engine_bindings()['e_Button_A'],'1')
        self.assertEqual(p.engine_bindings()['e_Button_B'],'0')
        self.assertEqual(ControllerProfile().engine_bindings()['e_Button_A'],'0')

    def test_last_active_device_ignores_idle_drift_and_stale_events(self):
        from launcher.controllers import ActiveDevice
        a=ActiveDevice()
        a.observe('pad1','switch',2,button_pressed=True)
        self.assertEqual(a.current,('pad1','switch'))
        a.observe('keyboard','keyboard',3)
        a.observe('pad2','xbox',4,axis=0.09)
        a.observe('keyboard','keyboard',1,button_pressed=True)
        self.assertEqual(a.current,('pad1','switch'))
        a.observe('keyboard','keyboard',5,button_pressed=True)
        self.assertEqual(a.current,('keyboard','keyboard'))
        a.observe('pad2','xbox',6,axis=-0.5)
        self.assertEqual(a.current,('pad2','xbox'))

    def test_manual_override_is_fallback_and_does_not_change_keyboard(self):
        from launcher.controllers import ActiveDevice
        a=ActiveDevice(manual_family='switch')
        a.observe('virtual','unknown',1,button_pressed=True)
        self.assertEqual(a.current,('virtual','switch'))
        a.observe('keyboard','keyboard',2,button_pressed=True)
        self.assertEqual(a.current,('keyboard','keyboard'))
        a.observe('physical','ps5',3,button_pressed=True)
        self.assertEqual(a.current,('physical','switch'))

    def test_unknown_devices_use_physical_names_and_invalid_profiles_fail(self):
        from launcher.controllers import ControllerProfile,detect_family
        self.assertEqual(detect_family(0x054c,0x0ce6),'ps5')
        self.assertEqual(detect_family(0x054c,0x09cc),'ps4')
        self.assertEqual(detect_family(0x057e,0x2009),'switch')
        self.assertEqual(detect_family(0x045e,0x028e),'xbox360')
        self.assertEqual(detect_family(0x28de,0x11ff),'unknown')
        self.assertEqual(ControllerProfile().prompt('confirm','unknown').name,'South button')
        for changes in [{'confirm':'A'},{'not-an-action':'south'}]:
            with self.assertRaises(ValueError):ControllerProfile(changes)

    def test_xbox_360_uses_back_start_instead_of_modern_view_menu(self):
        from launcher.controllers import ControllerProfile,detect_family
        p=ControllerProfile()
        self.assertEqual(detect_family(0x045e,0x028f),'xbox360')
        self.assertEqual(p.prompt('select','xbox360').name,'Back')
        self.assertEqual(p.prompt('pause','xbox360').name,'Start')
        self.assertEqual(p.prompt('select','xbox').name,'View')
        self.assertEqual(p.prompt('pause','xbox').name,'Menu')
