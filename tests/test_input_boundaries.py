"""Input-driver boundary tests using simulated Windows APIs and driver sends."""
import ctypes
import importlib.util
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class InputBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.foreground = 1
        self.cursor = (-500, -500)
        self.modifiers = set()
        def set_cursor(position):
            self.cursor = position
        self.gui = SimpleNamespace(
            GetForegroundWindow=lambda: self.foreground,
            GetClientRect=lambda hwnd: (0, 0, 800, 600),
            ClientToScreen=lambda hwnd, point: (point[0] + 100, point[1] + 100),
            GetCursorPos=lambda: self.cursor,
            IsIconic=lambda hwnd: False, ShowWindow=Mock(),
            SetForegroundWindow=Mock(), BringWindowToTop=Mock())
        spec = importlib.util.spec_from_file_location('_input_boundary_test',
            Path(__file__).resolve().parents[1] / 'input_controller.py')
        self.ic = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'win32gui': self.gui,
                        'win32api': SimpleNamespace(SetCursorPos=set_cursor),
                        'win32con': SimpleNamespace(SW_RESTORE=9),
                        'skill_combo_config': SimpleNamespace(INPUT_DRY_RUN=False)}):
            spec.loader.exec_module(self.ic)
        user32 = SimpleNamespace(GetAsyncKeyState=lambda vk: 0x8000 if vk in self.modifiers else 0,
                                 MapVirtualKeyW=lambda vk, mode: vk)
        self.ic.ctypes = SimpleNamespace(windll=SimpleNamespace(user32=user32), byref=ctypes.byref)
        self.ic._USER32 = user32
        self.ic._load_interception = lambda: True
        self.ic._is_dry_run = lambda: False
        self.ic.time = SimpleNamespace(sleep=lambda duration: None)
        self.ic.ACTIVE_HWND = 1
        self.ic.bind_cancel_event(threading.Event())
        self.sent = []
        def send(context, device, pointer, count):
            stroke = pointer._obj
            self.sent.append((device, {name: getattr(stroke, name) for name, _ in stroke._fields_}))
            return 1
        self.ic._INTERCEPTION_DLL = SimpleNamespace(interception_send=send)
        self.ic._INTERCEPTION_CTX = 1

    def test_alt_held_cannot_turn_automation_tab_into_alt_tab(self):
        self.modifiers.add(0x12)
        with self.assertRaises(RuntimeError):
            self.ic.tap_key('tab')
        self.assertEqual(self.sent, [])

    def test_background_game_receives_no_keys_mouse_or_focus_stealing(self):
        self.foreground = 2
        for action in (lambda: self.ic.tap_key('r'),
                       lambda: self.ic.check_input_target(),
                       lambda: self.ic.hold_mouse_down('right'),
                       lambda: self.ic.move_mouse_relative(100, 0),
                       lambda: self.ic.focus_window(1)):
            with self.assertRaises(RuntimeError):
                action()
        self.assertEqual(self.sent, [])
        self.gui.SetForegroundWindow.assert_not_called()

    def test_rotation_starts_inside_client_not_on_desktop(self):
        self.assertFalse(hasattr(self.gui, 'SetCursorPos'))
        self.ic.hold_mouse_down('right')
        self.assertEqual(self.cursor, (499, 399))
        self.assertEqual(self.sent[-1][1]['state'], 0x004)
        self.assertEqual(self.sent[-1][1]['x'], 0)
        self.assertEqual(self.sent[-1][1]['y'], 0)

    def test_real_pywin32_cursor_api_exists(self):
        import win32api
        self.assertTrue(callable(win32api.SetCursorPos))

    def test_relative_move_is_clamped_and_uses_correct_driver_flags(self):
        self.cursor = (890, 690)
        self.ic.move_mouse_relative(1000, 1000)
        stroke = self.sent[-1][1]
        self.assertEqual(stroke['flags'], 0)
        self.assertEqual((stroke['x'], stroke['y']), (8, 8))

    def test_each_rotation_recenters_even_when_cursor_is_inside_at_edge(self):
        self.cursor = (898, 698)
        self.ic.hold_mouse_down('right')
        self.assertEqual(self.cursor, (499, 399))

    def test_mouse_and_key_release_still_work_after_cancellation(self):
        self.ic._execution_context.cancel_event.set()
        self.foreground = 2
        self.modifiers.add(0x12)
        self.ic.key_up('w')
        self.ic.release_mouse('right')
        self.assertEqual(self.sent[0][1]['state'], 1)
        self.assertEqual(self.sent[1][1]['state'], 0x008)

    def test_already_focused_window_is_not_restored_or_raised(self):
        self.ic.focus_window(1)
        self.gui.ShowWindow.assert_not_called()
        self.gui.SetForegroundWindow.assert_not_called()

    def test_failed_modifier_combo_always_releases_alt(self):
        send = self.ic._INTERCEPTION_DLL.interception_send
        def fail_on_second(context, device, pointer, count):
            if len(self.sent) == 1:
                self.sent.append((device, {'failed': True}))
                raise RuntimeError('simulated driver error')
            return send(context, device, pointer, count)
        self.ic._INTERCEPTION_DLL.interception_send = fail_on_second
        with self.assertRaises(RuntimeError):
            self.ic._press_key_combination_interception('alt', '2')
        self.assertEqual(self.sent[-1][1]['code'], 0x12)
        self.assertEqual(self.sent[-1][1]['state'], 1)


if __name__ == '__main__':
    unittest.main()
