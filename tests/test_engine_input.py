"""Exercise our SDL-to-engine state adapter without a game or input events."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

@unittest.skipUnless(shutil.which('gcc'),'GCC required')
class EngineInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();binary=Path(cls.temp.name)/'engine.so'
        subprocess.run(['gcc','-shared','-fPIC','native/input/engine.c','-o',str(binary)],check=True,capture_output=True)
        cls.library=ctypes.CDLL(str(binary));cls.write=cls.library.dj_engine_state
        cls.write.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_short),ctypes.c_int]
        cls.write.restype=ctypes.c_int
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def state(self,buttons=0,axes=None,connected=1):
        buffer=(ctypes.c_ubyte*1164)(*[0x5a]*1164)
        sample=(ctypes.c_short*6)(*(axes or [0]*6))
        self.assertEqual(self.write(buffer,len(buffer),buttons,sample,connected),1)
        return buffer
    def test_physical_face_shoulders_and_center_buttons_have_canonical_slots(self):
        for physical,engine in enumerate([0,1,2,3,6,10,7,8,9,4,5,11,12,13,14]):
            state=self.state(1<<physical)
            self.assertEqual(list(state[6:22]),[int(i==engine) for i in range(16)])
            self.assertEqual(bytes(state[:4]),b'ZZZZ')
            self.assertEqual(bytes(state[360:]),b'Z'*(1164-360))
    def test_sticks_and_independent_triggers_match_original_direction_slots(self):
        state=self.state(axes=[-32768,32767,-16384,16384,32767,16384])
        axis=(ctypes.c_float*80).from_buffer(state,40)
        self.assertAlmostEqual(axis[0],1.0);self.assertEqual(axis[40],0)
        self.assertAlmostEqual(axis[41],1.0);self.assertEqual(axis[1],0)
        self.assertEqual(axis[3],1.0)
        self.assertEqual(axis[44],1.0)
        self.assertAlmostEqual(axis[42],1.0)
        self.assertEqual(axis[2],1.0)
    def test_original_deadzone_is_preserved_for_sticks_and_triggers(self):
        state=self.state(axes=[-10922,10922,0,0,10000,0])
        self.assertEqual(bytes(state[40:360]),bytes(320))
    def test_dpad_drives_navigation_and_opposing_directions_cancel(self):
        for button,slot in [(11,1),(12,41),(13,0),(14,40)]:
            state=self.state(1<<button)
            axes=(ctypes.c_float*80).from_buffer(state,40)
            self.assertEqual(axes[slot],1.0)
        state=self.state((1<<11)|(1<<12)|(1<<13)|(1<<14))
        self.assertEqual(bytes(state[40:360]),bytes(320))
    def test_disconnect_clears_pressed_state_without_touching_other_fields(self):
        state=self.state((1<<15)-1,[32767]*6,connected=0)
        self.assertEqual(bytes(state[6:22]),bytes(16))
        self.assertEqual(bytes(state[40:360]),bytes(320))
        self.assertEqual(ctypes.c_uint.from_buffer(state,32).value,0)
        self.assertEqual(ctypes.c_uint.from_buffer(state,36).value,1)
    def test_invalid_buffer_is_rejected_without_writing(self):
        state=(ctypes.c_ubyte*360)(*[0x5a]*360);axes=(ctypes.c_short*6)()
        self.assertEqual(self.write(state,359,0,axes,1),0)
        self.assertEqual(bytes(state),b'Z'*360)
        self.assertEqual(self.write(None,360,0,axes,1),0)
