"""HUD vision/parser checks; no OCR process, game, or input driver is started."""
from pathlib import Path
import sys
import queue
import threading
import time
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from target_hud import TargetHUDReader, parse_distance


class TargetHUDTests(unittest.TestCase):
    def setUp(self):
        self.reader = TargetHUDReader(lambda observation: None)
        self.sample = cv2.imread(str(Path(__file__).resolve().parents[1] / 'assets' / 'target_hud_reference.png'))

    def test_reference_hud_at_multiple_scales_and_positions(self):
        for scale in (0.75, 1.0, 1.25, 1.5, 2.0):
            with self.subTest(scale=scale):
                patch = cv2.resize(self.sample, None, fx=scale, fy=scale)
                frame = np.zeros((600, 1000, 3), np.uint8)
                frame[25:25 + patch.shape[0], 120:120 + patch.shape[1]] = patch
                hp, roi = self.reader.locate(frame)
                self.assertTrue(hp)
                self.assertTrue(roi.size)

    def test_red_objects_without_hud_anchor_are_not_health_bars(self):
        frame = np.zeros((300, 800, 3), np.uint8)
        frame[20:30, 20:300] = (0, 0, 255)
        self.assertIsNone(self.reader.locate(frame))

    def test_empty_hp_fill_is_not_a_living_target(self):
        sample = self.sample.copy()
        sample[31:39, 21:148] = 0
        sample[31:39, 187:306] = 0
        hp, _ = self.reader.locate(sample)
        self.assertFalse(hp)

    def test_distance_parser(self):
        for text, expected in [('1m', 1), ("1m '", 1), ('19 m', 19), ('20m', 20), ('19.5 m', 19.5), ('19,5m', 19.5)]:
            self.assertEqual(parse_distance(text), expected)
        for text in ['', 'Guardian 45 19m', '19', '-1m', '999m']:
            self.assertIsNone(parse_distance(text))

    @patch('target_hud.cv2.imwrite', return_value=True)
    def test_stalled_ocr_times_out_and_terminates_only_its_worker(self, write_image):
        self.reader._process = Mock()
        self.reader._process.poll.return_value = None
        self.reader._ocr_responses = queue.Queue()
        self.reader._ocr_response_timeout = 0.01
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            self.reader._read_distance(np.zeros((10, 20, 3), np.uint8), Path('unused-test.png'))
        self.reader._process.terminate.assert_called_once_with()
        self.reader._process.wait.assert_called_once()

    def test_world_target_markers_are_detected_across_scales(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        for color in ('red', 'blue'):
            sample = cv2.imread(str(root / f'target_marker_{color}.png'))
            for scale in (0.75, 1.0, 1.25, 1.5, 2.0):
                with self.subTest(color=color, scale=scale):
                    patch = cv2.resize(sample, None, fx=scale, fy=scale)
                    frame = np.zeros((600, 1000, 3), np.uint8)
                    frame[300:300 + patch.shape[0], 100:100 + patch.shape[1]] = patch
                    marker = self.reader.locate_marker(frame)
                    self.assertIsNotNone(marker)
                    self.assertEqual(marker['engaged'], color == 'red')
                    self.assertGreater(marker['target_position'][1], 300)

    def test_red_engaged_marker_has_priority_over_blue_marker(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        red = cv2.imread(str(root / 'target_marker_red.png'))
        blue = cv2.imread(str(root / 'target_marker_blue.png'))
        frame = np.zeros((600, 1000, 3), np.uint8)
        frame[100:100 + blue.shape[0], 100:100 + blue.shape[1]] = blue
        frame[400:400 + red.shape[0], 600:600 + red.shape[1]] = red
        marker = self.reader.locate_marker(frame)
        self.assertTrue(marker['engaged'])
        self.assertGreater(marker['target_position'][0], 600)

    def test_empty_scene_has_no_selected_marker(self):
        self.assertIsNone(self.reader.locate_marker(np.zeros((300, 800, 3), np.uint8)))

    @patch('target_hud.tempfile.TemporaryDirectory')
    def test_hp_checks_continue_during_slow_ocr_without_model_submissions(self, temporary_directory):
        temporary_directory.return_value.__enter__.return_value = str(Path(__file__).parent)
        observations = []
        gate = threading.Event()
        ocr_started = threading.Event()
        reader = TargetHUDReader(observations.append,
                                 frame_provider=lambda: np.zeros((300, 800, 3), np.uint8))
        reader.locate = Mock(return_value=(True, np.zeros((20, 40, 3), np.uint8)))
        reader.locate_marker = Mock(return_value=None)
        def slow_ocr(roi, path):
            ocr_started.set()
            gate.wait(2)
            return 19.0
        reader._read_distance = slow_ocr
        try:
            reader.start()
            self.assertTrue(ocr_started.wait(1))
            deadline = time.monotonic() + 1
            while len(observations) < 4 and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertGreaterEqual(len(observations), 4)
            self.assertTrue(all(o['visible'] and o['hp_visible'] for o in observations))
            self.assertTrue(all(o['distance_m'] is None for o in observations))
        finally:
            gate.set()
            reader.stop()
            reader._thread.join(1)
            reader._ocr_thread.join(1)
        self.assertFalse(reader._thread.is_alive())
        self.assertFalse(reader._ocr_thread.is_alive())


if __name__ == '__main__':
    unittest.main()
