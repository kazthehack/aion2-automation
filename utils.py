"""Utility helpers: window enumeration, image conversions, simple logging helpers."""
from typing import List, Tuple, Optional
import io
import sys
import time
from PIL import Image
import numpy as np
import cv2
import pygetwindow as gw
import win32gui

def list_windows() -> List[Tuple[str, int]]:
    """Return a list of (title, hwnd) for top-level windows with non-empty title."""
    wins = []
    try:
        for w in gw.getWindowsWithTitle(""):
            title = w.title
            if title:
                wins.append((title, int(w._hWnd)))
    except Exception:
        # fallback using win32gui
        def _enum(h, ctx):
            title = win32gui.GetWindowText(h)
            if title and win32gui.IsWindowVisible(h):
                wins.append((title, h))
        wins = []
        win32gui.EnumWindows(_enum, None)
    # dedupe and return
    seen = set()
    out = []
    for t, h in wins:
        if h not in seen:
            out.append((t, h))
            seen.add(h)
    return out

def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """Return (left, top, width, height) for a given hwnd. Returns None if not found."""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        return left, top, right - left, bottom - top
    except Exception:
        return None

def pil_from_bgr(bgr: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR numpy image to PIL Image."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)

def jpeg_bytes_from_bgr(bgr: np.ndarray, quality: int = 80) -> bytes:
    pil = pil_from_bgr(bgr)
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

def resize_keep_aspect(image: np.ndarray, target_max: int) -> np.ndarray:
    h, w = image.shape[:2]
    scale = min(target_max / max(w, h), 1.0)
    if scale == 1.0:
        return image
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
