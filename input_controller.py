"""
Interception-only input controller.

This module provides the public input API used across the codebase and
delivers inputs exclusively via the Interception kernel driver / DLL.
No fallback backends (pydirectinput, AutoHotkey, SendInput, etc.) exist in
this implementation. If the interception DLL or driver is not available,
public API calls raise a clear RuntimeError.
"""
from typing import Optional
import os
import sys
import ctypes
import threading
from ctypes import wintypes
from pathlib import Path

# Some Python runtimes / older ctypes versions do not expose ULONG_PTR in
# ctypes.wintypes. Create a safe fallback mapped to the correct-sized unsigned
# integer based on pointer width so the SendInput ctypes Structures work.
if not hasattr(wintypes, 'ULONG_PTR'):
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        wintypes.ULONG_PTR = ctypes.c_ulonglong
    else:
        wintypes.ULONG_PTR = ctypes.c_ulong
import time
import logging
import win32gui
import win32api
import win32con
from typing import Tuple

logger = logging.getLogger(__name__)

_execution_context = threading.local()


def bind_cancel_event(event, secondary_event=None):
    """Bind input cancellation to this worker's execution, including after restart."""
    _execution_context.cancel_event = event
    _execution_context.secondary_event = secondary_event


def check_cancelled():
    event = getattr(_execution_context, 'cancel_event', None)
    secondary = getattr(_execution_context, 'secondary_event', None)
    if ((event is not None and event.is_set())
            or (secondary is not None and secondary.is_set())):
        raise RuntimeError('Automation execution stopped')


def execution_wait(duration):
    if wait_for_cancellation(duration):
        check_cancelled()


def wait_for_cancellation(duration):
    """Wait interruptibly, returning before key-up cleanup when cancelled."""
    event = getattr(_execution_context, 'cancel_event', None)
    secondary = getattr(_execution_context, 'secondary_event', None)
    if event is None and secondary is None:
        time.sleep(max(0.0, duration))
        return False
    deadline = time.monotonic() + max(0.0, duration)
    while True:
        if ((event is not None and event.is_set())
                or (secondary is not None and secondary.is_set())):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        (event if event is not None else secondary).wait(min(0.02, remaining))

_HERE = Path(__file__).parent

# Runtime backend selection and dry-run are now read from the JSON-backed
# `skill_combo_config.py` so the GUI can toggle these values at runtime.
try:
    import skill_combo_config as skill_cfg  # JSON-backed config module
except Exception:
    skill_cfg = None


def _get_backend() -> str:
    # Interception-only controller: always return 'interception'
    return 'interception'


def _is_dry_run() -> bool:
    # Prefer the module-level override `INPUT_DRY_RUN` for backwards compatibility
    try:
        return bool(INPUT_DRY_RUN)
    except Exception:
        pass
    if skill_cfg is not None:
        return bool(getattr(skill_cfg, 'INPUT_DRY_RUN', False))
    return os.environ.get('INPUT_DRY_RUN', '0').lower() in ('1', 'true', 'yes')


# Backwards-compatible module attributes expected by `main.py` and other callers.
# These can be updated by the GUI at runtime but the runtime enforces
# interception-only behavior.
if skill_cfg is not None:
    INPUT_BACKEND = 'interception'
    INPUT_DRY_RUN = bool(getattr(skill_cfg, 'INPUT_DRY_RUN', False))
else:
    INPUT_BACKEND = 'interception'
    INPUT_DRY_RUN = os.environ.get('INPUT_DRY_RUN', '0').lower() in ('1', 'true', 'yes')

# IMPORTANT: we do NOT automatically fallback here. The selected backend
# is respected; if a backend isn't available it'll log (not force a DRY_RUN).

# Compatibility / state
ACTIVE_HWND: Optional[int] = None


def open_driver(path: str = None):
    # compatibility shim — always ready
    return True


def close():
    return True


def set_active_hwnd(hwnd: int):
    global ACTIVE_HWND
    ACTIVE_HWND = hwnd


def is_window_foreground(hwnd: int) -> bool:
    try:
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def focus_window(hwnd: int):
    check_cancelled()
    """Restore and set the target window to foreground (best-effort)."""
    if not hwnd or is_window_foreground(hwnd):
        return
    if getattr(_execution_context, 'cancel_event', None) is not None:
        raise RuntimeError('Game window lost focus; automation input paused')
    try:
        if not hwnd:
            return
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.02)
        # Try attaching our thread input to the target window's thread
        try:
            # Get thread ids
            current_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            target_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, 0)
            attached = False
            if current_tid and target_tid and current_tid != target_tid:
                attached = bool(ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, True))
            # Bring to foreground while threads are attached (if possible)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            time.sleep(0.06)
        finally:
            # Detach if we attached
            try:
                if 'attached' in locals() and attached:
                    ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, False)
            except Exception:
                pass
        # Small pause to allow the OS and game to accept focus
        time.sleep(0.08)
    except Exception:
        # best-effort only
        logger.debug("focus_window: unable to focus hwnd=%s" % (str(hwnd)))


def _ensure_focus():
    """Ensure the currently configured `ACTIVE_HWND` is foreground (best-effort).

    This helper is used before sending inputs so macros are more likely to
    be accepted by the game. It's intentionally best-effort and will never
    raise exceptions to callers.
    """
    try:
        if ACTIVE_HWND is None:
            return
        if not is_window_foreground(ACTIVE_HWND):
            focus_window(ACTIVE_HWND)
            # slight delay after focusing to give the OS/game time to accept it
            time.sleep(0.03)
    except Exception:
        # swallow errors; focusing is best-effort
        pass


# Local helper for key name translation
def _require_input_target():
    """Do not send game inputs into another window or turn Tab into Alt+Tab."""
    check_cancelled()
    if ACTIVE_HWND is not None and not is_window_foreground(ACTIVE_HWND):
        raise RuntimeError('Game window is not foreground; input skipped')
    for vk in (0x10, 0x11, 0x12, 0x5B, 0x5C):  # Shift, Ctrl, Alt, Windows
        if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000:
            raise RuntimeError('Modifier key held; automation input paused')


def check_input_target():
    if not _is_dry_run():
        _require_input_target()


def _client_bounds():
    if ACTIVE_HWND is None:
        return None
    left, top, right, bottom = win32gui.GetClientRect(ACTIVE_HWND)
    left, top = win32gui.ClientToScreen(ACTIVE_HWND, (left, top))
    right, bottom = win32gui.ClientToScreen(ACTIVE_HWND, (right, bottom))
    if right - left < 4 or bottom - top < 4:
        raise RuntimeError('Game client area is unavailable')
    return left + 1, top + 1, right - 2, bottom - 2


def _prepare_rotation_cursor():
    _require_input_target()
    bounds = _client_bounds()
    if bounds is not None:
        left, top, right, bottom = bounds
        x, y = win32gui.GetCursorPos()
        center = ((left + right) // 2, (top + bottom) // 2)
        if (x, y) != center:
            win32api.SetCursorPos(center)


_KEY_TRANSLATION = {
    '-': 'minus',
    '=': 'equals',
    '\t': 'tab',
    'tab': 'tab',
    'r': 'r',
    't': 't',
}


def _translate_key(key: str) -> str:
    if not isinstance(key, str):
        return str(key).lower()
    k = key.lower().strip()
    return _KEY_TRANSLATION.get(k, k)


# Minimal virtual-key map used for scancode mapping. Keep only keys the app uses.
_USER32 = ctypes.windll.user32
VK_MAP = {
    'tab': 0x09,
    'r': 0x52,
    't': 0x54,
    'f': 0x46,
    'w': 0x57,
    'a': 0x41,
    's': 0x53,
    'd': 0x44,
    '1': 0x31,'2':0x32,'3':0x33,'4':0x34,'5':0x35,'6':0x36,'7':0x37,'8':0x38,'9':0x39,'0':0x30,
    'minus': 0xBD, 'equals': 0xBB,
    'alt': 0x12, 'ctrl': 0x11
}


def _vk_to_scancode(vk: int) -> int:
    # MapVirtualKeyW with MAPVK_VK_TO_VSC (0)
    try:
        return _USER32.MapVirtualKeyW(vk, 0)
    except Exception:
        return int(vk)


def tap_key(key: str, presses: int = 1, interval: float = 0.05):
    """Press a key using the Interception backend.

    Returns True on success. In DRY_RUN mode logs the call and returns True.
    """
    check_cancelled()
    key_name = _translate_key(key)
    if _is_dry_run():
        logger.info(f"DRY_RUN: tap_key({key_name}, presses={presses}, interval={interval})")
        return True

    # Ensure the configured target window has focus before sending inputs
    try:
        _ensure_focus()
    except Exception:
        pass
    # Interception-only: ensure driver/DLL loaded then dispatch
    if not _load_interception():
        raise RuntimeError('Interception backend required but interception DLL/driver failed to load. See logs and ensure the Interception driver is installed and the DLL is present under Interception/library/x64/')
    return _tap_key_interception(key_name, presses=presses, interval=interval)


def key_down(key: str):
    """Hold a movement key until key_up; callers must release it in finally."""
    check_cancelled()
    if _is_dry_run():
        logger.info(f'DRY_RUN: key_down({key})')
        return
    _ensure_focus()
    check_cancelled()
    _send_movement_key(key, 0)


def key_up(key: str):
    """Always permit releasing a held key, including after cancellation."""
    if _is_dry_run():
        logger.info(f'DRY_RUN: key_up({key})')
        return
    _send_movement_key(key, 1)


def _send_movement_key(key: str, state: int):
    if state == 0:
        _require_input_target()
    key = _translate_key(key)
    if key not in ('w', 'a', 'd'):
        raise ValueError(f'Unsupported movement key: {key}')
    if not _load_interception():
        raise RuntimeError('Interception DLL/driver not loaded')
    stroke = _InterceptionKeyStroke(code=_vk_to_scancode(ord(key.upper())), state=state, information=0)
    result = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, 1, ctypes.byref(stroke), 1)
    if result == 0:
        raise RuntimeError(f'Interception movement key send failed: {key}')


def hold_key(key: str, duration: float):
    check_cancelled()
    key_name = _translate_key(key)
    if _is_dry_run():
        logger.info(f"DRY_RUN: hold_key({key_name}, duration={duration})")
        return True
    try:
        _ensure_focus()
    except Exception:
        pass
    if not _load_interception():
        raise RuntimeError('Interception backend required but interception DLL/driver failed to load')
    return _hold_key_interception(key_name, duration)


def move_mouse_to(x: int, y: int, duration: float = 0.0):
    check_cancelled()
    """Move mouse to (x,y) using the Interception backend.

    In DRY_RUN mode logs the call and returns True.
    """
    if _is_dry_run():
        logger.info(f"DRY_RUN: move_mouse_to({x},{y}, duration={duration})")
        return True
    try:
        _ensure_focus()
    except Exception:
        pass
    if not _load_interception():
        raise RuntimeError('Interception backend required but interception DLL/driver failed to load')
    return _move_mouse_interception(x, y, duration)


def click_at(x: int, y: int, button: str = 'left', clicks: int = 1, interval: float = 0.1):
    check_cancelled()
    if _is_dry_run():
        logger.info(f"DRY_RUN: click_at({x},{y}, button={button}, clicks={clicks}, interval={interval})")
        return True
    try:
        _ensure_focus()
    except Exception:
        pass
    if not _load_interception():
        raise RuntimeError('Interception backend required but interception DLL/driver failed to load')
    return _click_at_interception(x, y, button=button, clicks=clicks, interval=interval)


def hold_mouse_down(button: str = 'right') -> bool:
    check_cancelled()
    """Press and hold a mouse button (does NOT release).

    Use `release_mouse(button)` to release. In DRY_RUN mode this logs the call.
    """
    btn = (button or 'right').lower()
    if _is_dry_run():
        logger.info(f"DRY_RUN: hold_mouse_down({btn})")
        return True
    _prepare_rotation_cursor()
    if not _load_interception():
        raise RuntimeError('Interception backend required but interception DLL/driver failed to load')
    code = INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN if btn == 'right' else INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN
    stroke = _InterceptionMouseStroke(state=code, flags=0, rolling=0, x=0, y=0, information=0)
    res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, 11, ctypes.byref(stroke), 1)
    return res != 0


def release_mouse(button: str = 'right') -> bool:
    """Release a previously held mouse button. In DRY_RUN mode this logs the call."""
    btn = (button or 'right').lower()
    if _is_dry_run():
        logger.info(f"DRY_RUN: release_mouse({btn})")
        return True
    if not _load_interception():
        raise RuntimeError('Interception backend required but interception DLL/driver failed to load')
    code = INTERCEPTION_MOUSE_RIGHT_BUTTON_UP if btn == 'right' else INTERCEPTION_MOUSE_LEFT_BUTTON_UP
    stroke = _InterceptionMouseStroke(state=code, flags=0, rolling=0, x=0, y=0, information=0)
    res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, 11, ctypes.byref(stroke), 1)
    return res != 0


def move_mouse_by(dx: int, dy: int, duration: float = 0.2, steps: int = 8) -> bool:
    check_cancelled()
    """Move the mouse by a relative amount over a duration (interpolated steps).

    This uses the interception mouse move stroke. Uses screen absolute positions computed
    from the current cursor position. In DRY_RUN mode this logs the intended motion.
    """
    if _is_dry_run():
        logger.info(f"DRY_RUN: move_mouse_by(dx={dx}, dy={dy}, duration={duration})")
        return True
    try:
        cx, cy = win32gui.GetCursorPos()
    except Exception:
        # Fallback to (0,0)
        cx, cy = 0, 0
    tx = int(cx + dx)
    ty = int(cy + dy)
    steps = max(1, int(steps))
    sleep_per = max(0.0, duration / steps) if duration > 0 else 0.0
    for i in range(1, steps + 1):
        check_cancelled()
        ix = int(cx + (tx - cx) * (i / steps))
        iy = int(cy + (ty - cy) * (i / steps))
        _move_mouse_interception(ix, iy)
        if sleep_per:
            execution_wait(sleep_per)
    return True


def move_mouse_relative(dx: int, dy: int, *, steps: int = 1, duration: float = 0.0) -> bool:
    check_cancelled()
    """Move the mouse by relative deltas using the interception backend.

    Designed for camera pans where absolute positioning is undesirable. Splits the
    requested delta into incremental steps to create a smooth swipe. Positive `dx`
    moves right, positive `dy` moves down.
    """
    if _is_dry_run():
        logger.info(f"DRY_RUN: move_mouse_relative(dx={dx}, dy={dy}, steps={steps}, duration={duration})")
        return True
    if not _load_interception():
        raise RuntimeError('Interception backend required but interception DLL/driver failed to load')
    steps = max(1, int(steps))
    step_delay = max(0.0, duration / steps) if duration > 0 else 0.0
    rem_x = int(dx)
    rem_y = int(dy)
    for i in range(steps):
        check_cancelled()
        # distribute remainder to keep totals accurate
        chunk_x = rem_x // (steps - i) if (steps - i) else rem_x
        chunk_y = rem_y // (steps - i) if (steps - i) else rem_y
        rem_x -= chunk_x
        rem_y -= chunk_y
        _interception_send_mouse_move(chunk_x, chunk_y)
        if step_delay:
            execution_wait(step_delay)
    return True


def double_click_at(x: int, y: int):
    return click_at(x, y, button='left', clicks=2, interval=0.08)


def perform_human_attack_click(x: int, y: int):
    # Compatibility helper: historically this performed a double-click attack.
    # ActionPlanner now uses keyboard-based targeting (Tab + R/T) so callers
    # should prefer the new behavior, but keep this function for backward-compat.
    return double_click_at(x, y)


def press_key_combination(modifier: str, key: str):
    check_cancelled()
    """Hold modifier, press key, release modifier.

    Supported modifiers: 'alt', 'ctrl' (case-insensitive).
    """
    mod = modifier.lower() if modifier else ''
    key_name = _translate_key(key)
    if _is_dry_run():
        logger.info(f"DRY_RUN: press_key_combination({mod}, {key_name})")
        return True
    try:
        _ensure_focus()
    except Exception:
        pass
    if not _load_interception():
        raise RuntimeError('Interception backend required but interception DLL/driver failed to load')
    return _press_key_combination_interception(mod, key_name)


# module init
try:
    open_driver()
except Exception:
    pass

# --------------------------
# Minimal Interception-only implementation
# --------------------------

def _tap_key_interception(key_name: str, presses: int = 1, interval: float = 0.05) -> bool:
    check_cancelled()
    # Interception-only: send using the interception DLL. No fallbacks allowed.
    if not _load_interception():
        raise RuntimeError('Interception DLL/driver not loaded')
    ok = _interception_send_key(key_name, presses=presses, interval=interval)
    if not ok:
        raise RuntimeError(f'Interception failed to send key: {key_name}')
    return True


def _hold_key_interception(key_name: str, duration: float) -> bool:
    check_cancelled()
    _require_input_target()
    # Implement hold via interception: send down, sleep, send up
    if not _load_interception():
        raise RuntimeError('Interception DLL/driver not loaded')
    # Map to VK/scan code
    base = key_name.split('+')[-1]
    vk = VK_MAP.get(base) or (ord(base.upper()) if len(base) == 1 else None)
    if vk is None:
        raise RuntimeError(f'Unsupported key for interception hold: {key_name}')
    sc = _vk_to_scancode(vk)
    down = _InterceptionKeyStroke(code=sc, state=0, information=0)
    up = _InterceptionKeyStroke(code=sc, state=1, information=0)
    res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, 1, ctypes.byref(down), 1)
    if res == 0:
        raise RuntimeError('Interception send (down) failed')
    wait_for_cancellation(duration)
    res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, 1, ctypes.byref(up), 1)
    if res == 0:
        raise RuntimeError('Interception send (up) failed')
    return True


def _move_mouse_interception(x: int, y: int, duration: float = 0.0) -> bool:
    cx, cy = win32gui.GetCursorPos()
    return _interception_send_mouse_move(x - cx, y - cy)


def _click_at_interception(x: int, y: int, button: str = 'left', clicks: int = 1, interval: float = 0.1) -> bool:
    return _interception_send_mouse_click(x, y, button=button, clicks=clicks, interval=interval)


def _press_key_combination_interception(mod: str, key_name: str) -> bool:
    check_cancelled()
    _require_input_target()
    # Interception-only implementation for modifier+key combos
    if not _load_interception():
        raise RuntimeError('Interception DLL/driver not loaded')
    mod_lower = (mod or '').lower()
    if mod_lower not in ('alt', 'ctrl'):
        raise RuntimeError(f'Unsupported modifier for interception: {mod}')
    # map modifier VK
    mod_vk = 0x12 if mod_lower == 'alt' else 0x11
    # map key
    base = key_name.split('+')[-1]
    vk = VK_MAP.get(base) or (ord(base.upper()) if len(base) == 1 else None)
    if vk is None:
        raise RuntimeError(f'Unsupported key for interception combo: {key_name}')
    mod_sc = _vk_to_scancode(mod_vk)
    key_sc = _vk_to_scancode(vk)
    down_mod = _InterceptionKeyStroke(code=mod_sc, state=0, information=0)
    up_mod = _InterceptionKeyStroke(code=mod_sc, state=1, information=0)
    down_key = _InterceptionKeyStroke(code=key_sc, state=0, information=0)
    up_key = _InterceptionKeyStroke(code=key_sc, state=1, information=0)

    try:
        res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, 1, ctypes.byref(down_mod), 1)
        if res == 0:
            raise RuntimeError('Interception send failed (mod down)')
        time.sleep(0.02)
        res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, 1, ctypes.byref(down_key), 1)
        if res == 0:
            raise RuntimeError('Interception send failed (key down)')
        time.sleep(0.02)
        return True
    finally:
        # Never leave Alt/Ctrl held if a send or other operation fails halfway through.
        for stroke in (up_key, up_mod):
            try:
                _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, 1, ctypes.byref(stroke), 1)
            except Exception as exc:
                logger.error(f'Failed to release combination key: {exc}')


# --------------------------
# Minimal Interception ctypes wrapper
# --------------------------

_INTERCEPTION_DLL = None
_INTERCEPTION_CTX = None

def _load_interception():
    global _INTERCEPTION_DLL, _INTERCEPTION_CTX
    if _INTERCEPTION_DLL is not None:
        return True
    # Try common candidate locations (repo-provided x64/x86 and system/global)
    candidates = [
        Path(__file__).parent / 'Interception' / 'library' / 'x64' / 'interception.dll',
        Path(__file__).parent / 'Interception' / 'library' / 'x86' / 'interception.dll',
    ]
    # Also allow loading by name if installed system-wide
    tried = []
    for lib_path in candidates:
        tried.append(str(lib_path))
        if lib_path.exists():
            try:
                _INTERCEPTION_DLL = ctypes.WinDLL(str(lib_path))
                break
            except Exception as e:
                logger.debug(f"interception: failed to load {lib_path}: {e}")
                _INTERCEPTION_DLL = None
    if _INTERCEPTION_DLL is None:
        # try by library name (system-installed)
        try:
            _INTERCEPTION_DLL = ctypes.WinDLL('interception')
            tried.append('system:interception')
        except Exception as e:
            logger.warning(f"interception: failed to load from candidates {tried}: {e}")
            _INTERCEPTION_DLL = None
    if _INTERCEPTION_DLL is None:
        # As a last resort attempt to run the Interception installer (requires elevation)
        try:
            if _attempt_install_interception():
                # After installer runs attempt to load again from system name
                try:
                    _INTERCEPTION_DLL = ctypes.WinDLL('interception')
                    tried.append('system:interception-after-install')
                except Exception:
                    _INTERCEPTION_DLL = None
        except Exception:
            pass
    if _INTERCEPTION_DLL is None:
        return False
    try:
        # define functions with precise prototypes
        _INTERCEPTION_DLL.interception_create_context.restype = ctypes.c_void_p
        _INTERCEPTION_DLL.interception_destroy_context.argtypes = [ctypes.c_void_p]
        _INTERCEPTION_DLL.interception_send.restype = ctypes.c_int
        _INTERCEPTION_DLL.interception_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        _INTERCEPTION_DLL.interception_is_keyboard.argtypes = [ctypes.c_int]
        _INTERCEPTION_DLL.interception_is_mouse.argtypes = [ctypes.c_int]
        # create context
        ctx = _INTERCEPTION_DLL.interception_create_context()
        if not ctx:
            logger.warning("interception: interception_create_context returned NULL")
            _INTERCEPTION_DLL = None
            return False
        _INTERCEPTION_CTX = ctypes.c_void_p(ctx)
        logger.debug(f"interception: loaded DLL and created context (ctx={_INTERCEPTION_CTX})")
        return True
    except Exception as e:
        logger.warning(f"Failed to initialize interception DLL: {e}")
        _INTERCEPTION_DLL = None
        _INTERCEPTION_CTX = None
        return False


def _attempt_install_interception() -> bool:
    """Attempt to run the Interception installer found in common locations.

    This will attempt to launch the bundled `install-interception.exe` with
    elevation (ShellExecuteW verb 'runas'). After launching the installer it
    retries loading the interception DLL a few times. Returns True if the
    installer was launched (and DLL becomes loadable), False otherwise.
    """
    try:
        candidates = []
        # Installer alongside this module (source tree)
        candidates.append(Path(__file__).parent / 'Interception' / 'command line installer' / 'install-interception.exe')
        # Installer relative to the running executable (when packaged in output/)
        try:
            exe_parent = Path(sys.argv[0]).parent
            candidates.append(exe_parent / 'Interception' / 'command line installer' / 'install-interception.exe')
        except Exception:
            pass
        # Installer from current working directory
        candidates.append(Path.cwd() / 'Interception' / 'command line installer' / 'install-interception.exe')

        installer_path = None
        for c in candidates:
            if c.exists():
                installer_path = c
                break
        if installer_path is None:
            logger.debug(f"No Interception installer found in candidates: {candidates}")
            return False

        logger.info(f"Attempting to run Interception installer: {installer_path}")
        # Launch elevated installer using ShellExecuteW
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(installer_path), None, str(installer_path.parent), 1)
            if int(ret) <= 32:
                logger.warning(f"ShellExecuteW failed to launch installer, code={ret}")
                return False
        except Exception as e:
            logger.warning(f"Failed to launch installer via ShellExecuteW: {e}")
            return False

        # Wait & retry loading DLL a few times
        for attempt in range(8):
            time.sleep(2)
            # try known candidate dll locations again
            for lib_path in [
                Path(__file__).parent / 'Interception' / 'library' / 'x64' / 'interception.dll',
                Path(__file__).parent / 'Interception' / 'library' / 'x86' / 'interception.dll',
                exe_parent / 'Interception' / 'library' / 'x64' / 'interception.dll' if 'exe_parent' in locals() else None,
            ]:
                if lib_path is None:
                    continue
                if lib_path.exists():
                    try:
                        ctypes.WinDLL(str(lib_path))
                        logger.info("Interception DLL detected after installer run")
                        return True
                    except Exception:
                        continue
        logger.warning("Interception installer ran but DLL not detected after retries")
        return False
    except Exception as e:
        logger.warning(f"_attempt_install_interception failed: {e}")
        return False


class _InterceptionKeyStroke(ctypes.Structure):
    _fields_ = [('code', ctypes.c_ushort), ('state', ctypes.c_ushort), ('information', ctypes.c_uint)]


def _interception_send_key(key_name: str, presses: int = 1, interval: float = 0.05) -> bool:
    if not _load_interception():
        return False
    # use device 1 (INTERCEPTION_KEYBOARD(0) == 1)
    device = 1
    # map key_name to vk/scancode
    parts = key_name.split('+')
    base = parts[-1]
    vk = VK_MAP.get(base) or (ord(base.upper()) if len(base) == 1 else None)
    if vk is None:
        return False
    sc = _vk_to_scancode(vk)
    for i in range(presses):
        check_cancelled()
        _require_input_target()
        stroke_down = _InterceptionKeyStroke(code=sc, state=0, information=0)
        stroke_up = _InterceptionKeyStroke(code=sc, state=1, information=0)
        # send down
        res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, device, ctypes.byref(stroke_down), 1)
        if res == 0:
            return False
        time.sleep(0.02)
        res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, device, ctypes.byref(stroke_up), 1)
        if res == 0:
            return False
        if presses > 1 and i < presses - 1:
            time.sleep(max(interval, 0.01))
    return True


# Interception mouse support
INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN = 0x001
INTERCEPTION_MOUSE_LEFT_BUTTON_UP = 0x002
INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN = 0x004
INTERCEPTION_MOUSE_RIGHT_BUTTON_UP = 0x008
INTERCEPTION_MOUSE_MIDDLE_BUTTON_DOWN = 0x010
INTERCEPTION_MOUSE_MIDDLE_BUTTON_UP = 0x020
INTERCEPTION_MOUSE_MOVE_FLAG = 0x000  # INTERCEPTION_MOUSE_MOVE_RELATIVE; 0x1000 is a filter mask


class _InterceptionMouseStroke(ctypes.Structure):
    _fields_ = [
        ('state', ctypes.c_ushort),
        ('flags', ctypes.c_ushort),
        ('rolling', ctypes.c_short),
        ('x', ctypes.c_int),
        ('y', ctypes.c_int),
        ('information', ctypes.c_uint),
    ]


def _interception_send_mouse_move(x: int, y: int) -> bool:
    _require_input_target()
    bounds = _client_bounds()
    if bounds is not None:
        cx, cy = win32gui.GetCursorPos()
        left, top, right, bottom = bounds
        x = min(right, max(left, cx + x)) - cx
        y = min(bottom, max(top, cy + y)) - cy
    if not _load_interception():
        return False
    # mouse device index 0 -> device id = INTERCEPTION_MOUSE(0) == INTERCEPTION_MAX_KEYBOARD + 0 + 1
    device = 11
    stroke = _InterceptionMouseStroke(state=0, flags=INTERCEPTION_MOUSE_MOVE_FLAG, rolling=0, x=int(x), y=int(y), information=0)
    res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, device, ctypes.byref(stroke), 1)
    return res != 0


def _interception_send_mouse_click(x: int, y: int, button: str = 'left', clicks: int = 1, interval: float = 0.1) -> bool:
    _require_input_target()
    _move_mouse_interception(x, y)
    if not _load_interception():
        return False
    device = 11
    btn_down = INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN if button == 'left' else INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN
    btn_up = INTERCEPTION_MOUSE_LEFT_BUTTON_UP if button == 'left' else INTERCEPTION_MOUSE_RIGHT_BUTTON_UP
    for i in range(clicks):
        _require_input_target()
        stroke_down = _InterceptionMouseStroke(state=btn_down, flags=0, rolling=0, x=0, y=0, information=0)
        stroke_up = _InterceptionMouseStroke(state=btn_up, flags=0, rolling=0, x=0, y=0, information=0)
        res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, device, ctypes.byref(stroke_down), 1)
        if res == 0:
            return False
        time.sleep(0.02)
        res = _INTERCEPTION_DLL.interception_send(_INTERCEPTION_CTX, device, ctypes.byref(stroke_up), 1)
        if res == 0:
            return False
        if clicks > 1 and i < clicks - 1:
            time.sleep(max(interval, 0.01))
    return True


def validate_backend(backend: str) -> None:
    """Validate that the given backend is available.

    Raises RuntimeError with actionable guidance when missing.
    """
    if not backend:
        raise RuntimeError('No backend specified')
    b = str(backend).lower()
    # Only interception is supported in this build
    if b == 'interception':
        if not _load_interception():
            raise RuntimeError('Interception backend selected but the interception DLL or driver failed to load. Ensure the Interception DLL exists under Interception/library/x64 (or x86) matching your Python bitness, and install the Interception kernel driver. Run Python as Administrator when testing.')
        return
    raise RuntimeError(f'Unsupported INPUT_BACKEND: {backend} — only "interception" is supported')

