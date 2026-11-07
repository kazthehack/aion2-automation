"""Capture the selected game window using mss and window rect from utils."""
import threading
import time
from typing import Optional
import cv2
import numpy as np
import mss
from loguru import logger
from utils import get_window_rect


class CaptureWorker(threading.Thread):
    def __init__(self, hwnd: int, target_fps: int = 30, resize_max: int = 960):
        super().__init__(daemon=True)
        self.hwnd = hwnd
        self.target_fps = target_fps
        self.resize_max = resize_max
        self.running = threading.Event()
        self.running.clear()
        self.latest_frame = None
        self._lock = threading.Lock()
        self._last_window_size = (0, 0)

    def start_capture(self):
        self.running.set()
        if not self.is_alive():
            self.start()

    def stop_capture(self):
        self.running.clear()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self.latest_frame is None else self.latest_frame.copy()

    def run(self):
        sct = mss.mss()
        logger.info("CaptureWorker started for hwnd={} target_fps={}".format(self.hwnd, self.target_fps))
        interval = 1.0 / max(1, self.target_fps)
        while True:
            if not self.running.is_set():
                time.sleep(0.05)
                continue
            rect = get_window_rect(self.hwnd)
            if not rect:
                logger.warning("Window handle not available (hwnd=%s)" % self.hwnd)
                time.sleep(0.5)
                continue
            left, top, w, h = rect
            # store original window size so callers can map coords back
            self._last_window_size = (w, h)
            monitor = {"left": left, "top": top, "width": w, "height": h}
            img = sct.grab(monitor)
            # mss returns BGRA
            frame = np.array(img)
            if frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            # optional resize to limit bytes
            if self.resize_max is not None:
                h0, w0 = frame.shape[:2]
                scale = min(1.0, self.resize_max / max(w0, h0))
                if scale < 1.0:
                    frame = cv2.resize(frame, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)
            with self._lock:
                self.latest_frame = frame
            # time.sleep(interval)

    def get_window_size(self):
        """Return the last known original window (width, height)."""
        return self._last_window_size
