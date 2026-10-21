"""Windows-only graphics wrapper configuration; never launches a game."""
import unittest
from tools.windows_graphics import make_config


class GraphicsConfigTests(unittest.TestCase):
    def test_internal_resolution_is_enumerated_above_physical_display_size(self):
        text=make_config('3840x2160','1920x1080',fullscreen=False)
        line=next(line for line in text.splitlines() if line.startswith('ExtraEnumeratedResolutions = '))
        self.assertIn('3840x2160',line)
        self.assertIn('1920x1080',line)

    def test_supersampling_config_keeps_simulation_and_refresh_application_controlled(self):
        text=make_config('3840x2160','1920x1080',fullscreen=True)
        self.assertIn('OutputAPI = d3d11_fl11_0',text)
        # The shipped wrapper rejects the older template's "srgb" spelling and
        # silently enters passthrough, discarding the entire local config.
        self.assertIn('ColorSpace = argb8888_sdr\n',text)
        self.assertNotIn('ColorSpace = argb8888_srgb',text)
        self.assertIn('Resolution = 3840x2160',text)
        self.assertIn('DesktopResolution = 1920x1080',text)
        self.assertIn('FullscreenAttributes = fake',text)
        self.assertIn('ScalingMode = stretched_ar',text)
        self.assertIn('ForceVerticalSync = false',text)
        self.assertIn('FPSLimit = 0',text)
        self.assertNotIn('@50',text)
        self.assertNotIn('@60',text)
        self.assertNotIn('AutoSynchronize',text)

    def test_window_mode_and_invalid_resolution(self):
        text=make_config('1920x1080','1920x1080',fullscreen=False)
        self.assertIn('FullScreenMode = false',text)
        for bad in ['4096x2160','3840x0','0x0','1920x1080\nEnable=true','90000x50625']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):make_config(bad,'1920x1080')
