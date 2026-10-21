"""Exercise the packaging sanitizer against runnable owned ELF fixtures. djultra64."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.sanitize_linux_gamescope import sanitize


@unittest.skipUnless(shutil.which('cc') and shutil.which('readelf'), 'ELF compiler tools unavailable')
class GamescopeSanitizationTests(unittest.TestCase):
    def compile(self, root, *flags):
        source = root/'fixture.c'
        source.write_text('#include <stdio.h>\nint main(void) {\n'
            'puts("/build user/project/build/third-party/gamescope/devel/usr/lib64");\n'
            'puts("/build user/project/build/Gamescope-SDK-Staging/share/gamescope/scripts");\n'
            'puts("unrelated content"); return 0; }\n')
        target = root/'fixture'
        subprocess.run(['cc', str(source), '-o', str(target), *flags], check=True,
                       capture_output=True)
        return target

    def test_binary_runs_with_public_defaults_and_same_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = self.compile(Path(folder))
            before = binary.read_bytes()
            result = sanitize(binary)
            self.assertTrue(result['same_size'])
            self.assertEqual(len(before), binary.stat().st_size)
            self.assertNotIn(b'/build user/', binary.read_bytes())
            output = subprocess.check_output([str(binary)], text=True)
            self.assertEqual(output, '/usr/lib64\n/usr/share/gamescope/scripts\nunrelated content\n')
            again = sanitize(binary)
            self.assertEqual(again['before_sha256'], again['after_sha256'])

    def test_active_rpath_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = self.compile(Path(folder), '-Wl,-rpath,/private-build-libraries')
            before = binary.read_bytes()
            with self.assertRaisesRegex(ValueError, 'RPATH'):
                sanitize(binary)
            self.assertEqual(binary.read_bytes(), before)
