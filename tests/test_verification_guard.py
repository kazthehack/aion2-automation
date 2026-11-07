"""Fail-safe checks with fixed UI text only; process termination is always mocked."""
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from verification_guard import VerificationGuard, SelectedGameProcess


class VerificationGuardTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.guard = VerificationGuard(lambda: self.events.append('pause'), lambda: self.events.append('close'))
        self.panel = np.zeros((1097, 1142, 3), np.uint8)
        root = Path(__file__).resolve().parents[1] / 'assets'
        self.panel[42:95, 400:800] = cv2.imread(str(root / 'verification_title.png'))
        self.panel[173:222, 290:891] = cv2.imread(str(root / 'verification_instruction.png'))

    def test_fixed_dialog_text_matches_across_scales(self):
        for scale in (0.75, 1, 1.25):
            with self.subTest(scale=scale):
                frame = cv2.resize(self.panel, None, fx=scale, fy=scale)
                self.assertTrue(self.guard.visible(frame))

    def test_title_alone_or_empty_frame_does_not_trigger(self):
        self.assertFalse(self.guard.visible(np.zeros_like(self.panel)))
        title_only = self.panel.copy()
        title_only[173:222, 290:891] = 0
        self.assertFalse(self.guard.visible(title_only))
        self.assertEqual(self.events, [])

    def test_input_stops_before_close_and_close_happens_only_once(self):
        self.guard.visible = Mock(return_value=True)
        self.guard.check(self.panel)
        self.assertEqual(self.events, ['pause'])
        self.guard._next_check = 0
        self.guard.check(self.panel)
        self.assertEqual(self.events, ['pause', 'close'])
        self.guard.check(self.panel)
        self.assertEqual(self.events, ['pause', 'close'])

    def test_unconfirmed_detection_leaves_inputs_stopped_without_killing(self):
        self.guard.visible = Mock(side_effect=[True, False])
        self.guard.check(self.panel)
        self.guard._next_check = 0
        self.guard.check(self.panel)
        self.assertEqual(self.events, ['pause'])


class SelectedProcessTests(unittest.TestCase):
    @patch('verification_guard.win32process.GetWindowThreadProcessId', return_value=(10, 20))
    @patch('verification_guard.psutil.Process')
    def test_only_selected_game_process_is_closed(self, process_factory, window_pid):
        process = process_factory.return_value
        process.create_time.return_value = 123
        process.name.return_value = 'AION2-Win64-Shipping.exe'
        target = SelectedGameProcess(100)
        self.assertTrue(target.terminate())
        process.kill.assert_called_once_with()
        self.assertTrue(all(call.args == (20,) for call in process_factory.call_args_list))

    @patch('verification_guard.win32process.GetWindowThreadProcessId', return_value=(10, 20))
    @patch('verification_guard.psutil.Process')
    def test_non_game_process_is_never_killed(self, factory, window_pid):
        process = factory.return_value
        process.name.return_value = 'chrome.exe'
        process.create_time.return_value = 123
        target = SelectedGameProcess(100)
        with self.assertRaises(RuntimeError):
            target.terminate()
        process.kill.assert_not_called()

    @patch('verification_guard.win32process.GetWindowThreadProcessId', return_value=(10, 20))
    @patch('verification_guard.psutil.Process')
    def test_reused_pid_or_reassigned_window_is_never_killed(self, factory, window_pid):
        process = factory.return_value
        process.name.return_value = 'AION2.exe'
        process.create_time.side_effect = [123, 456]
        target = SelectedGameProcess(100)
        with self.assertRaises(RuntimeError):
            target.terminate()
        process.kill.assert_not_called()
        window_pid.return_value = (10, 21)
        process.create_time.side_effect = None
        process.create_time.return_value = 123
        with self.assertRaises(RuntimeError):
            target.terminate()
        process.kill.assert_not_called()


if __name__ == '__main__':
    unittest.main()
