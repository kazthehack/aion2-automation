"""Stop-on-verification fail-safe. Never reads or answers the challenge image."""
from pathlib import Path
import time

import cv2
import psutil
import win32process


class SelectedGameProcess:
    """Pin the selected window's AION2 process identity before monitoring starts."""
    def __init__(self, hwnd):
        self.hwnd = hwnd
        _, self.pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(self.pid)
        self.created_at = process.create_time()
        self.name = process.name()

    def terminate(self):
        # Never kill by a broad process-name search, PID alone, or window title.
        name = self.name.casefold()
        if not (name.startswith('aion2') and name.endswith('.exe')):
            raise RuntimeError(f'Refusing to terminate a non-AION2 process: {self.name}')
        try:
            _, current_pid = win32process.GetWindowThreadProcessId(self.hwnd)
            process = psutil.Process(self.pid)
            if current_pid != self.pid or process.create_time() != self.created_at:
                raise RuntimeError('Selected window/process identity changed; termination refused')
            process.kill()
            return True
        except psutil.NoSuchProcess:
            return False


class VerificationGuard:
    def __init__(self, pause_inputs, terminate_game):
        self.pause_inputs = pause_inputs
        self.terminate_game = terminate_game
        root = Path(__file__).parent / 'assets'
        self.title = cv2.imread(str(root / 'verification_title.png'), cv2.IMREAD_GRAYSCALE)
        self.instruction = cv2.imread(str(root / 'verification_instruction.png'), cv2.IMREAD_GRAYSCALE)
        if self.title is None or self.instruction is None:
            raise RuntimeError('Verification fail-safe reference images are missing')
        self._matches = 0
        self._paused = False
        self._tripped = False
        self._next_check = 0.0

    def visible(self, frame):
        gray = cv2.cvtColor(frame[:max(1, int(frame.shape[0] * 0.55))], cv2.COLOR_BGR2GRAY)
        for scale in (0.6, 0.7, 0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.25, 1.4, 1.5):
            title = cv2.resize(self.title, None, fx=scale, fy=scale)
            if gray.shape[0] < title.shape[0] or gray.shape[1] < title.shape[1]:
                continue
            _, score, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(gray, title, cv2.TM_CCOEFF_NORMED))
            if score < 0.90:
                continue
            instruction = cv2.resize(self.instruction, None, fx=scale, fy=scale)
            ih, iw = instruction.shape
            sx, sy = round(x - 110 * scale), round(y + 131 * scale)
            pad = max(3, round(5 * scale))
            region = gray[max(0, sy-pad):min(gray.shape[0], sy+ih+pad),
                          max(0, sx-pad):min(gray.shape[1], sx+iw+pad)]
            if region.shape[0] < ih or region.shape[1] < iw:
                continue
            _, second, _, _ = cv2.minMaxLoc(cv2.matchTemplate(region, instruction, cv2.TM_CCOEFF_NORMED))
            if second >= 0.87:
                return True
        return False

    def check(self, frame):
        if self._tripped:
            return True
        now = time.monotonic()
        if now < self._next_check:
            return self._paused
        self._next_check = now + 0.2
        if not self.visible(frame):
            self._matches = 0
            return self._paused
        self._matches += 1
        if not self._paused:
            self._paused = True
            self.pause_inputs()
        if self._matches >= 2:
            self._tripped = True
            self.terminate_game()
        return True
