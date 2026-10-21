"""Compile only our own portable C policy; no game binary/assets. djultra64."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from launcher.controllers import ControllerProfile,FAMILIES,ACTIONS,DI_TOKENS

@unittest.skipUnless(shutil.which('gcc'),'Native policy checks require GCC')
class NativeInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();library=Path(cls.temp.name)/'policy.so'
        subprocess.run(['gcc','-shared','-fPIC','-O2','native/input/policy.c','-o',str(library)],check=True,capture_output=True)
        cls.lib=ctypes.CDLL(str(library))
        cls.resolve=cls.lib.dj_glyph_code;cls.resolve.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.POINTER(ctypes.c_ubyte)]
        cls.resolve.restype=ctypes.c_uint
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_every_family_and_remap_uses_the_same_physical_position_as_input(self):
        codes=[0x2123,0x2124,0x2125,0x2126,0x2127,0x2128,0x212b,0x212c]
        for rotation in range(8):
            actions=list(ACTIONS);physical=list(DI_TOKENS)
            profile=ControllerProfile({a:physical[(i+rotation)%8] for i,a in enumerate(actions)})
            mapping=(ctypes.c_ubyte*8)(*[int(profile.engine_bindings()[ACTIONS[a][0]]) for a in actions])
            for f,family in enumerate(FAMILIES,1):
                for i,(action,code) in enumerate(zip(actions,codes)):
                    position=physical.index(profile.prompt(action,family).position)
                    self.assertEqual(self.resolve(code,f,mapping),0xe000+(f-1)*8+position)
                    self.assertEqual(self.resolve(code,0,mapping),code)
            self.assertEqual(self.resolve(ord('A'),1,mapping),ord('A'))

    def test_invalid_family_or_position_leaves_original_glyph_unchanged(self):
        invalid=(ctypes.c_ubyte*8)(*[255]*8)
        self.assertEqual(self.resolve(0x2123,1,invalid),0x2123)
        self.assertEqual(self.resolve(0x2123,99,None),0x2123)
