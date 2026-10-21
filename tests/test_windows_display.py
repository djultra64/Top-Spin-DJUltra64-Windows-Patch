import unittest

class WindowLayoutTests(unittest.TestCase):
    def test_requested_output_is_centered_without_negative_origin(self):
        from launcher.windows_display import output_bounds
        self.assertEqual(output_bounds('1280x720',(0,0,1920,1080)),(320,180,1280,720))
        self.assertEqual(output_bounds('1920x1080',(-1920,0,0,1080)),(-1920,0,1920,1080))
        with self.assertRaisesRegex(ValueError,'display'):
            output_bounds('3840x2160',(0,0,1920,1080))
