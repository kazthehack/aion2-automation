"""Read the selected-target HUD using a visual anchor and local Windows OCR.

Runs independently of model inference. The bundled detector has no HP-bar class.
"""
import json
import queue
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time

import cv2
import numpy as np
from loguru import logger


def parse_distance(text):
    text = text.strip().strip("'\"\u2018\u2019\u201c\u201d|").strip()
    match = re.fullmatch(r'\s*(\d{1,3}(?:[.,]\d+)?)\s*m\s*', text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(',', '.'))
    return value if 0 <= value <= 200 else None


class TargetHUDReader:
    def __init__(self, on_observation, frame_provider=None, verification_guard=None):
        self.on_observation = on_observation
        self.frame_provider = frame_provider
        self.verification_guard = verification_guard
        self._ocr_pending = threading.Event()
        self._ocr_request = None
        self._ocr_result = None
        self._ocr_thread = None
        self._generation = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._pending = threading.Event()
        self._frame = None
        self._process = None
        self._ocr_responses = None
        self._ocr_response_timeout = 3.0
        self._thread = None
        self._warned = False
        self._last_visible = False
        self._missing_frames = 0
        self._marker_position = None
        reference = cv2.imread(str(Path(__file__).parent / 'assets' / 'target_hud_reference.png'))
        if reference is None:
            raise RuntimeError('Target HUD reference image is missing')
        self._anchor = cv2.cvtColor(reference[33:62, 155:183], cv2.COLOR_BGR2GRAY)
        root = Path(__file__).parent / 'assets'
        red = cv2.imread(str(root / 'target_marker_red.png'))
        blue = cv2.imread(str(root / 'target_marker_blue.png'))
        self._markers = [
            (True, red[9:37, 15:36], red[9:37, 157:179]),
            (False, blue[1:32, 3:25], blue[1:32, 128:151]),
        ]

    def start(self):
        self._ocr_thread = threading.Thread(target=self._ocr_loop, daemon=True, name='target-distance')
        self._ocr_thread.start()
        self._thread = threading.Thread(target=self._run, daemon=True, name='target-hud')
        self._thread.start()

    def submit(self, frame):
        # Search the upper HUD area, not red objects elsewhere in the game world.
        with self._lock:
            self._frame = (frame.copy(), time.monotonic())
        self._pending.set()

    def stop(self):
        self._stop.set()
        self._pending.set()
        self._ocr_pending.set()
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

    def locate(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        best = None
        for scale in (0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
            anchor = cv2.resize(self._anchor, None, fx=scale, fy=scale)
            if anchor.shape[0] > gray.shape[0] or anchor.shape[1] > gray.shape[1]:
                continue
            score_map = cv2.matchTemplate(gray, anchor, cv2.TM_CCOEFF_NORMED)
            _, score, _, position = cv2.minMaxLoc(score_map)
            if best is None or score > best[0]:
                best = (score, position, scale)
        if best is None or best[0] < 0.82:
            return None
        _, (ax, ay), scale = best
        x, y = ax - 155 * scale, ay - 33 * scale

        def crop(x1, y1, x2, y2):
            left, top = max(0, round(x + x1 * scale)), max(0, round(y + y1 * scale))
            right, bottom = min(frame.shape[1], round(x + x2 * scale)), min(frame.shape[0], round(y + y2 * scale))
            return frame[top:bottom, left:right]

        # Exclude the red center ornament and right marker when checking HP fill.
        hp_pixels = 0
        for bar in (crop(21, 31, 148, 39), crop(187, 31, 306, 39)):
            if bar.size:
                hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)
                hue, sat, value = cv2.split(hsv)
                hp_pixels += np.count_nonzero(((hue < 12) | (hue > 160)) & (sat > 100) & (value > 110))
        return bool(hp_pixels >= max(4, 8 * scale * scale)), crop(258, 4, 301, 27)

    def _read_distance(self, roi, path):
        if self._stop.is_set():
            return None
        if not roi.size:
            return None
        if self._process is None or self._process.poll() is not None:
            self._process = subprocess.Popen(
                ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                 '-File', str(Path(__file__).with_name('target_hud_ocr.ps1'))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            responses = queue.Queue()
            self._ocr_responses = responses
            def collect_responses(stream):
                try:
                    for response in stream:
                        responses.put(response)
                except (OSError, ValueError):
                    pass
                finally:
                    responses.put(None)
            threading.Thread(target=collect_responses, args=(self._process.stdout,),
                             daemon=True, name='distance-ocr-responses').start()
        if self._stop.is_set():
            self.stop()
            return None
        image = cv2.resize(roi, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        cv2.imwrite(str(path), image)
        self._process.stdin.write(str(path) + '\n')
        self._process.stdin.flush()
        try:
            line = self._ocr_responses.get(timeout=self._ocr_response_timeout)
        except queue.Empty:
            self._process.terminate()
            self._process.wait(timeout=1)
            raise RuntimeError('Distance OCR timed out; its worker will restart') from None
        if not line:
            raise RuntimeError('Windows OCR worker exited without a result')
        result = json.loads(line)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return parse_distance(result.get('text', ''))

    def locate_marker(self, frame):
        """Find paired target arrows, prioritizing the red engaged-target marker."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for engaged, left_image, right_image in self._markers:
            best = None
            for scale in (0.75, 1.0, 1.25, 1.5, 2.0):
                left = cv2.cvtColor(cv2.resize(left_image, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY)
                right = cv2.cvtColor(cv2.resize(right_image, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY)
                lh, lw = left.shape
                rh, rw = right.shape
                if gray.shape[0] < max(lh, rh) or gray.shape[1] < lw + rw:
                    continue
                scores = cv2.matchTemplate(gray, left, cv2.TM_CCOEFF_NORMED)
                for _ in range(3):
                    _, left_score, _, (x, y) = cv2.minMaxLoc(scores)
                    if left_score < 0.77:
                        break
                    x1, x2 = x + lw + round(25 * scale), min(gray.shape[1], x + round(450 * scale))
                    y1, y2 = max(0, y - round(5 * scale)), min(gray.shape[0], y + max(lh, rh) + round(5 * scale))
                    search = gray[y1:y2, x1:x2]
                    if search.shape[0] >= rh and search.shape[1] >= rw:
                        matches = cv2.matchTemplate(search, right, cv2.TM_CCOEFF_NORMED)
                        _, right_score, _, (rx, ry) = cv2.minMaxLoc(matches)
                        rx, ry = rx + x1, ry + y1
                        text = frame[max(0, y):min(frame.shape[0], y + lh), x + lw:rx]
                        if text.size:
                            hsv = cv2.cvtColor(text, cv2.COLOR_BGR2HSV)
                            gold = np.count_nonzero((hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 40)
                                                   & (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 100))
                            glow = cv2.cvtColor(frame[y:y + lh, x:x + lw], cv2.COLOR_BGR2HSV)
                            colored = (glow[:, :, 1] > 65) & (glow[:, :, 2] > 100)
                            red = np.count_nonzero(colored & ((glow[:, :, 0] < 12) | (glow[:, :, 0] > 165)))
                            blue = np.count_nonzero(colored & (glow[:, :, 0] >= 80) & (glow[:, :, 0] <= 130))
                            color_matches = red > blue + 3 if engaged else blue > red + 3
                            score = min(left_score, right_score)
                            if color_matches and right_score >= 0.77 and gold >= max(6, 8 * scale * scale):
                                position = ((x + lw + rx) / 2, y + lh / 2)
                                rank = score
                                if self._marker_position is not None:
                                    dx, dy = position[0] - self._marker_position[0], position[1] - self._marker_position[1]
                                    rank -= 0.15 * min(1.0, (dx * dx + dy * dy) ** 0.5 / frame.shape[1])
                                if best is None or rank > best['rank']:
                                    best = dict(score=score, rank=rank, engaged=engaged, target_position=position)
                    scores[max(0, y - lh):min(scores.shape[0], y + lh),
                           max(0, x - lw):min(scores.shape[1], x + lw)] = -1
            if best is not None:
                self._marker_position = best['target_position']
                return best
        return None

    def _publish(self, visible, hp, distance, observed_at, marker=None, distance_observed_at=None):
        if not self._stop.is_set():
            self.on_observation(dict(visible=visible, hp_visible=hp,
                                     distance_m=distance, observed_at=observed_at,
                                     distance_observed_at=distance_observed_at,
                                     target_position=marker['target_position'] if marker else None,
                                     engaged=marker['engaged'] if marker else False))

    def _ocr_loop(self):
        with tempfile.TemporaryDirectory(prefix='aion-target-hud-') as directory:
            path = Path(directory) / 'distance.png'
            while not self._stop.is_set():
                if not self._ocr_pending.wait(0.2):
                    continue
                with self._lock:
                    request = self._ocr_request
                    self._ocr_pending.clear()
                if request is None or self._stop.is_set():
                    continue
                generation, roi, observed_at = request
                distance = None
                try:
                    distance = self._read_distance(roi, path)
                except Exception as exc:
                    if not self._warned and not self._stop.is_set():
                        logger.warning(f'Target distance OCR unavailable; movement stays stopped with a visible HUD: {exc}')
                        self._warned = True
                with self._lock:
                    self._ocr_result = (generation, distance, observed_at)

    def _run(self):
        next_ocr_at = 0.0
        try:
            while not self._stop.is_set():
                if self.frame_provider is not None:
                    captured = self.frame_provider()
                    if captured is None:
                        self._stop.wait(0.05)
                        continue
                    frame = captured
                    observed_at = time.monotonic()
                else:
                    if not self._pending.wait(0.2):
                        continue
                    with self._lock:
                        frame_data = self._frame
                        self._pending.clear()
                    if frame_data is None:
                        continue
                    frame, observed_at = frame_data
                if self.verification_guard is not None and self.verification_guard.check(frame):
                    self._stop.wait(0.05)
                    continue
                result = self.locate(frame[:max(1, int(frame.shape[0] * 0.4))])
                marker = self.locate_marker(frame)
                if result is None and marker is None:
                    self._missing_frames += 1
                    if not self._last_visible or self._missing_frames >= 2:
                        if self._last_visible:
                            self._generation += 1
                        self._last_visible = False
                        self._marker_position = None
                        self._publish(False, False, None, observed_at)
                else:
                    self._missing_frames = 0
                    hp, roi = result if result is not None else (True, None)
                    if marker is not None:
                        hp = True
                    if not self._last_visible:
                        self._generation += 1
                        next_ocr_at = 0.0
                    self._last_visible = True
                    with self._lock:
                        cached = self._ocr_result
                    distance = None
                    distance_observed_at = None
                    if (cached is not None and cached[0] == self._generation
                            and observed_at - cached[2] <= 1.5):
                        distance = cached[1]
                        distance_observed_at = cached[2] if distance is not None else None
                    # HP presence is published on every visual check, never blocked by OCR.
                    self._publish(True, hp, distance, observed_at, marker, distance_observed_at)
                    if roi is not None and time.monotonic() >= next_ocr_at:
                        with self._lock:
                            self._ocr_request = (self._generation, roi.copy(), observed_at)
                        self._ocr_pending.set()
                        next_ocr_at = time.monotonic() + 0.25
                self._stop.wait(0.05)
        except Exception as exc:
            logger.error(f'Target HUD reader stopped: {exc}')
        finally:
            self.stop()
