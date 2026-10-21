"""Own synthetic DBWIN buffers. djultra64."""
import unittest
from tools.capture_windows_debug import matching_message

class WindowsDebugCaptureTests(unittest.TestCase):
    def test_exact_process_only_and_null_terminated_message(self):
        data=(42).to_bytes(4,'little')+b'CreateDevice 3840x2160\0unused private bytes'
        self.assertEqual(matching_message(data,42),'CreateDevice 3840x2160')
        self.assertIsNone(matching_message(data,41))
        self.assertIsNone(matching_message(b'bad',42))

    def test_unrelated_bytes_are_never_decoded(self):
        data=(43).to_bytes(4,'little')+b'\xff\xfe other process'
        # Even an invalid decoder name must not be touched for another PID.
        self.assertIsNone(matching_message(data,42,encoding='not-a-real-codec'))
