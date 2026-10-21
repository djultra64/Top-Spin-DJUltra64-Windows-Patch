"""Synthetic gamepad samples: no devices or game assets needed. djultra64."""
import unittest

class InputDeviceTests(unittest.TestCase):
    def sample(self,device='one',*,buttons=(),axes=(0,0,0,0,0,0),family='xbox'):
        from launcher.input_devices import PadSample
        return PadSample(device,'Synthetic pad',family,frozenset(buttons),tuple(axes))

    def test_held_button_does_not_steal_prompts_back_from_keyboard(self):
        from launcher.input_devices import InputActivity
        a=InputActivity()
        held=self.sample(buttons=['south'])
        self.assertEqual(a.update([held],1),('one','xbox'))
        self.assertEqual(a.update([held],2,keyboard_pressed=True),('keyboard','keyboard'))
        self.assertEqual(a.update([held],3),('keyboard','keyboard'))
        a.update([self.sample()],4)
        self.assertEqual(a.update([held],5),('one','xbox'))

    def test_stick_hold_drift_and_recenter_do_not_override_keyboard(self):
        from launcher.input_devices import InputActivity
        a=InputActivity();held=self.sample(axes=(0.7,0,0,0,0,0))
        self.assertEqual(a.update([held],1),('one','xbox'))
        a.update([held],2,keyboard_pressed=True)
        self.assertEqual(a.update([held],3),('keyboard','keyboard'))
        self.assertEqual(a.update([self.sample(axes=(0.71,0,0,0,0,0))],4),('keyboard','keyboard'))
        self.assertEqual(a.update([self.sample()],5),('keyboard','keyboard'))
        self.assertEqual(a.update([self.sample(axes=(-0.8,0,0,0,0,0))],6),('one','xbox'))

    def test_hotplug_disconnect_and_manual_family(self):
        from launcher.input_devices import InputActivity
        a=InputActivity(manual_family='switch')
        one=self.sample(buttons=['north'],family='unknown')
        self.assertEqual(a.update([one],1),('one','switch'))
        self.assertEqual(a.update([],2),('keyboard','keyboard'))
        two=self.sample('two',buttons=['east'],family='ps5')
        self.assertEqual(a.update([two],3),('two','switch'))

    def test_sdl_positions_keep_nintendo_face_locations_and_trigger_ranges(self):
        from launcher.input_devices import sample_from_sdl
        s=sample_from_sdl(7,'Switch',7,0x057e,0x2009,[True,False,True]+[False]*12,[-32768,32767,0,0,0,32767])
        self.assertEqual(s.family,'switch')
        self.assertEqual(s.buttons,frozenset(['south','west']))
        self.assertEqual(s.axes,(-1.0,1.0,0.0,0.0,0.0,1.0))
        v=sample_from_sdl(8,'Steam virtual',2,0x28de,0x11ff,[False]*15,[0]*6)
        self.assertEqual(v.family,'unknown')

    def test_corrupt_and_stale_samples_are_rejected_without_changing_state(self):
        from launcher.input_devices import InputActivity
        a=InputActivity();one=self.sample(buttons=['south'])
        a.update([one],5)
        self.assertEqual(a.update([],4),('one','xbox'))
        for sample in [self.sample(axes=(float('nan'),0,0,0,0,0)),self.sample(buttons=['A']),self.sample(axes=(0,)*5)]:
            with self.assertRaises(ValueError):a.update([sample],6)
        self.assertEqual(a.current,('one','xbox'))
