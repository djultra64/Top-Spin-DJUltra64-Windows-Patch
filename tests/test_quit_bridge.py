"""Exercise guarded registration and actual x86 thiscall without a game. djultra64."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

@unittest.skipUnless(shutil.which('gcc') and shutil.which('ld'),'Native build tools required')
class QuitBridgeTests(unittest.TestCase):
    def test_guarded_callback_opens_confirmation_and_preserves_x86_abi(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            subprocess.run(['gcc','-m32','-O2','-ffreestanding','-fno-pie','-fno-builtin',
                '-fno-stack-protector','-fno-asynchronous-unwind-tables',
                '-ffunction-sections','-fdata-sections','-mpreferred-stack-boundary=2',
                '-mincoming-stack-boundary=2','-c','native/input/quit_probe.c','-o',str(root/'probe.o')],check=True,capture_output=True)
            subprocess.run(['as','--32','native/input/quit_probe.s','-o',str(root/'abi.o')],check=True,capture_output=True)
            binary=root/'quit-probe'
            subprocess.run(['ld','-melf_i386','--gc-sections','-e','_start','-o',str(binary),str(root/'probe.o'),str(root/'abi.o')],check=True,capture_output=True)
            result=subprocess.run([str(binary)],timeout=5,capture_output=True)
            if result.returncode==-31:
                self.skipTest('Sandbox denies 32-bit syscalls; run this isolated harness outside seccomp')
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
