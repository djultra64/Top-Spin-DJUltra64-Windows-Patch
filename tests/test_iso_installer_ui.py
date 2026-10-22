"""Headless ISO setup workflow and CLI tests. Own work: djultra64."""
import contextlib
import importlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


class InstallerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('launcher.installer')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.iso = self.root/'my game.iso'
        self.iso.write_bytes(b'fixture')
        self.target = self.root/'Top Spin'
        self.payload = self.root/'.topspin-patch'

    def finish(self, controller):
        deadline = time.monotonic()+3
        events = []
        while controller.running and time.monotonic()<deadline:
            events.extend(controller.drain())
            if controller.running:
                time.sleep(.005)
        self.assertFalse(controller.running, 'Installer worker did not finish')
        return events

    def test_success_is_queued_without_opening_any_program(self):
        worker_threads = []
        def install(iso, destination, payload, *, progress, cancel):
            worker_threads.append(threading.get_ident())
            progress('Extracting game files…')
            return {'installed': True}
        controller = self.module.InstallController(self.payload, install=install)
        with patch.object(subprocess, 'Popen') as opened:
            controller.start(str(self.iso), str(self.target))
            events = self.finish(controller)
            opened.assert_not_called()
        self.assertNotEqual(worker_threads, [threading.get_ident()])
        self.assertTrue(controller.succeeded)
        self.assertEqual(controller.destination, self.target)
        self.assertIn(('progress', 'Extracting game files…'), events)
        self.assertEqual(events[-1], ('success', {'installed': True}))

    def test_rejects_existing_destination_before_starting_worker(self):
        self.target.mkdir()
        called = []
        controller = self.module.InstallController(self.payload, install=lambda *a, **k: called.append(a))
        with self.assertRaisesRegex(ValueError, 'already exists'):
            controller.start(str(self.iso), str(self.target))
        self.assertFalse(controller.running)
        self.assertEqual(called, [])

    def test_empty_paths_are_not_interpreted_as_current_directory(self):
        controller = self.module.InstallController(self.payload, install=lambda *a, **k: None)
        for iso, target in [('', str(self.target)), (str(self.iso), '  ')]:
            with self.subTest(iso=iso, target=target):
                with self.assertRaises(ValueError):
                    controller.start(iso, target)
        self.assertFalse(controller.running)

    def test_cancel_waits_for_worker_cleanup_before_state_finishes(self):
        started, cleanup = threading.Event(), threading.Event()
        def install(iso, destination, payload, *, progress, cancel):
            started.set()
            if not cancel.wait(2):
                raise RuntimeError('Cancel event was not signalled')
            cleanup.set()
            raise InterruptedError('Installation cancelled.')
        controller = self.module.InstallController(self.payload, install=install)
        controller.start(str(self.iso), str(self.target))
        self.assertTrue(started.wait(2))
        with self.assertRaisesRegex(ValueError, 'already running'):
            controller.start(str(self.iso), str(self.root/'other'))
        controller.request_cancel()
        self.assertTrue(controller.running)
        events = self.finish(controller)
        self.assertTrue(cleanup.is_set())
        self.assertFalse(controller.succeeded)
        self.assertEqual(events[-1][0], 'cancelled')

    def test_worker_error_is_reported_and_a_fresh_attempt_can_start(self):
        def install(*args, **kwargs):
            raise ValueError('Unsupported game version')
        controller = self.module.InstallController(self.payload, install=install)
        controller.start(str(self.iso), str(self.target))
        events = self.finish(controller)
        self.assertEqual(events[-1], ('error', 'Unsupported game version'))
        self.assertFalse(controller.succeeded)
        controller.start(str(self.iso), str(self.target))
        self.finish(controller)

    def test_cli_calls_core_without_importing_tk(self):
        calls = []
        def install(iso, destination, payload, *, progress, cancel):
            calls.append((iso, destination, payload))
            progress('Checking ISO…')
            return {'installed': True}
        with patch.object(self.module, '_install_from_iso', install), patch.object(self.module, 'show_setup') as gui:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = self.module.main(['--iso', str(self.iso), '--destination', str(self.target), '--payload', str(self.payload)])
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(self.iso, self.target, self.payload)])
        self.assertIn('Checking ISO', output.getvalue())
        gui.assert_not_called()

    def test_cli_errors_are_nonzero_without_traceback_or_gui(self):
        def install(*args, **kwargs):
            raise ValueError('Unsupported ISO')
        with patch.object(self.module, '_install_from_iso', install), patch.object(self.module, 'show_setup') as gui:
            with contextlib.redirect_stderr(io.StringIO()) as error:
                code = self.module.main(['--iso', str(self.iso), '--destination', str(self.target)])
        self.assertEqual(code, 1)
        self.assertIn('Unsupported ISO', error.getvalue())
        self.assertNotIn('Traceback', error.getvalue())
        gui.assert_not_called()

    def test_cli_extractor_failure_has_a_friendly_nonzero_result(self):
        def install(*args, **kwargs):
            raise subprocess.CalledProcessError(2, ['cabextract'])
        with patch.object(self.module, '_install_from_iso', install):
            with contextlib.redirect_stderr(io.StringIO()) as error:
                code = self.module.main(['--iso', str(self.iso), '--destination', str(self.target)])
        self.assertEqual(code, 1)
        self.assertIn('Installation failed:', error.getvalue())
        self.assertNotIn('Traceback', error.getvalue())

    def test_browsed_parent_creates_a_fresh_named_target(self):
        self.assertEqual(self.module.destination_in_parent(self.root), self.root/'Top Spin')
        self.assertEqual(self.module.default_destination(), Path.home()/'Games'/'Top Spin')


class InstallerGeometryTests(unittest.TestCase):
    def test_actions_remain_inside_default_and_minimum_window(self):
        try:
            import tkinter as tk
            window = tk.Tk()
        except (ImportError, RuntimeError) as exc:
            self.skipTest('A Tk runtime and display are required: '+str(exc))
        except Exception as exc:
            if type(exc).__name__ == 'TclError':
                self.skipTest('A graphical display is required: '+str(exc))
            raise
        from launcher.installer import show_setup
        checked = []
        def inspect_geometry():
            try:
                for width, height in [(740, 620), (660, 540)]:
                    window.geometry(str(width)+'x'+str(height))
                    window.update_idletasks()
                    window.update()
                    pending, buttons = [window], {}
                    while pending:
                        widget = pending.pop()
                        pending.extend(widget.winfo_children())
                        if widget.winfo_class() == 'TButton':
                            buttons[widget.cget('text')] = widget
                    for label in ['Install', 'Done', 'Open configurator', 'Open game folder']:
                        button = buttons[label]
                        with self.subTest(size=(width, height), button=label):
                            self.assertTrue(button.winfo_ismapped(), label+' is hidden')
                            x = button.winfo_rootx()-window.winfo_rootx()
                            y = button.winfo_rooty()-window.winfo_rooty()
                            self.assertGreaterEqual(x, 0)
                            self.assertGreaterEqual(y, 0)
                            self.assertLessEqual(x+button.winfo_width(), window.winfo_width())
                            self.assertLessEqual(y+button.winfo_height(), window.winfo_height())
                    checked.append((width, height))
            finally:
                window.destroy()
        window.mainloop = inspect_geometry
        with patch.object(tk, 'Tk', return_value=window):
            show_setup(Path('/tmp/unused-topspin-geometry-payload'))
        self.assertEqual(checked, [(740, 620), (660, 540)])


if __name__ == '__main__':
    unittest.main()
