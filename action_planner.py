"""Action planner that maps detections to in-game actions.

Behavior implemented per user spec:
 - Confirmed target HUD/arrow markers take priority over monster detections.
 - Without a selected target, scan, try Tab once, and rotate if selection fails.
 - Move only toward a selected target's marker, then send the R/T/1/2 combat sequence.
 - A dedicated combat worker sends R/T while detection monitors target presence.
 - Confirmed target disappearance stops combat. Auto loot skips the F-key branch.

This module uses `input_controller` to send OS-level inputs.

(Stealth mode removed) Uses deterministic timings and immediate actions.
"""
import time
import threading
from typing import List, Dict, Tuple, Optional
from loguru import logger
import input_controller as ic
import skill_combo_config
import random


def _center_of(d: Dict) -> Tuple[int, int]:
    x = float(d.get("x", 0))
    y = float(d.get("y", 0))
    w = float(d.get("width", 0))
    h = float(d.get("height", 0))
    return int(x + w / 2.0), int(y + h / 2.0)


def _iou(a: Dict, b: Dict) -> float:
    ax1 = a.get("x", 0)
    ay1 = a.get("y", 0)
    ax2 = ax1 + a.get("width", 0)
    ay2 = ay1 + a.get("height", 0)
    bx1 = b.get("x", 0)
    by1 = b.get("y", 0)
    bx2 = bx1 + b.get("width", 0)
    by2 = by1 + b.get("height", 0)
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class ActionPlanner:
    def __init__(self, hwnd: int, enabled: bool = True, conf_thresh: float = 0.25):
        self.hwnd = hwnd
        self.enabled = enabled
        self.conf_thresh = conf_thresh
        self._window_size = (0, 0)
        self._player_exclusion_fraction = 0.20  # central 20% of width and height
        self._lock = threading.Lock()
        self._last_action = 0.0
        # Use non-stealth deterministic timing
        self._cooldown = 0.2
        # previous target lock removed; use self._current_target state instead
        
        # Warmup/idle tracking removed (no stealth behavior)
        self._action_count = 0
        
        # Skill Combo Manager - handles skill macros with cooldown tracking
        try:
            from skill_combo_manager import SkillComboManager
            self.skill_combo_manager = SkillComboManager(hwnd)
            logger.info("✓ Skill Combo Manager integrated into Action Planner")
        except Exception as e:
            logger.warning(f"Skill Combo Manager not available: {e}")
            self.skill_combo_manager = None
        # New state machine: scanning -> combat -> cooldown
        self._mode = 'scanning'  # scanning | approaching | combat | cooldown
        self._approach_thread = None
        self._approach_stop = threading.Event()
        self._approach_expired = threading.Event()
        self._approach_timeout = 3.0  # never walk indefinitely waiting for a box-size estimate
        self._steering_enter_fraction = 0.12
        self._steering_exit_fraction = 0.07
        self._approach_missing_since = None
        self._approach_missing_frames = 0
        self._approach_target_loss_grace = 1.0
        self._target_tab_interval = 1.0
        self._last_target_tab = float('-inf')
        self._search_thread = None
        self._sentry_rotation_thread = None
        self._sentry_rotation_stop = threading.Event()
        self._sentry_rotation_pause = 0.5
        self._search_stop = threading.Event()
        self._target_confirm_wait = 0.8
        self._post_tab_attack_wait = 1.5
        self._last_search_completed = float('-inf')
        self._search_retry_delay = 1.0
        self._failed_selection_attempts = 0
        self._max_selection_attempts = 2
        self._last_target_position = None
        self._last_target_position_at = 0.0
        self._selected_target = threading.Event()
        self._hud_initialized = threading.Event()
        self._selection_missing_since = None
        self._selection_missing_frames = 0
        self._selection_loss_grace = 1.0
        self._target_hud = dict(visible=False, hp_visible=False, distance_m=None, observed_at=0.0)
        self._detected_target_health = False
        self._stop_distance_m = 19.0
        self._resume_distance_m = 20.0
        self._hud_max_age = 1.5
        self._roam_turn_duration = 0.2
        self._roam_turn_segments = 12
        self._roam_turn_step = (10, 16)
        self._current_target: Optional[Dict] = None
        self._combat_thread = None
        self._combat_stop = threading.Event()
        self._combat_started = 0.0
        self._target_missing_since = None
        self._target_missing_frames = 0
        self._combat_signal_seen = False
        self.health_detection_supported = False
        self._health_acquire_grace = 1.0
        self._target_loss_grace = 0.15
        self._cooldown_until = 0.0
        self._last_attack = 0.0
        self._attack_repeat_gap = 0.20  # let the previous sequence register before repeating
        self._attack_key_gap = 0.15  # give R time to register before T
        self._last_cooldown_action = 0.0
        self._cooldown_f_interval = (0.6, 1.8)  # random press F intervals during cooldown
        # roaming (idle movement) state
        self._roaming = False
        self._roam_cancel_event = threading.Event()
        self.mode_cancel_event = threading.Event()
        self._last_farming_press = None
        self.set_sentry_mode(getattr(skill_combo_config, 'SENTRY_MODE', False))
        self._roam_thread = None
        self._last_roam_time = 0.0
        self._roam_cooldown = (3.0, 8.0)  # seconds between roam attempts
        # consecutive no-detections counter (trigger roam after N empties)
        self._no_mobs_count = 0
        self._no_mobs_threshold = 5
        # store last detections so roaming thread can re-check for monsters
        self._last_detections: List[Dict] = []

    def _send_basic_attack(self, require_visible_monster=False):
        """Send the shared R, T, 1, 2 sequence on every attack cycle."""
        if not self.enabled or getattr(skill_combo_config, 'FARMING_MODE', False):
            return
        if not ic.is_window_foreground(self.hwnd):
            ic.focus_window(self.hwnd)
        keys = ('r', 't', '1', '2')
        for index, key in enumerate(keys):
            ic.check_cancelled()
            if require_visible_monster and not self._visible_monsters():
                return
            if not self.enabled or getattr(skill_combo_config, 'FARMING_MODE', False):
                return
            if index:
                ic.execution_wait(self._attack_key_gap)
            if require_visible_monster and not self._visible_monsters():
                return
            ic.tap_key(key)
        self._last_attack = time.time()

    def _start_combat_worker(self):
        """Never overlap workers, including when a stopped target is reacquired."""
        if self._combat_thread is not None and self._combat_thread.is_alive():
            return False
        if (not self.enabled
                or (not self._has_selected_target() and not getattr(skill_combo_config, 'SENTRY_MODE', False))
                or getattr(skill_combo_config, 'FARMING_MODE', False)):
            return False
        self._stop_approach_worker()
        stop_event = threading.Event()
        self._combat_stop = stop_event
        self._roam_cancel_event.set()
        self._combat_started = time.monotonic()
        self._target_missing_since = None
        self._target_missing_frames = 0
        self._combat_signal_seen = False
        self._mode = 'combat'
        self._combat_thread = threading.Thread(
            target=self._combat_loop, args=(stop_event,), daemon=True, name='combat-input')
        self._combat_thread.start()
        return True

    def _stop_combat_worker(self, wait=False):
        self._combat_stop.set()
        worker = self._combat_thread
        if wait and worker is not None and worker is not threading.current_thread():
            worker.join(timeout=0.3)

    def _select_nearby_target(self, selected_event=None):
        if (not self.enabled or getattr(skill_combo_config, 'FARMING_MODE', False)
                or getattr(skill_combo_config, 'SENTRY_MODE', False)
                or not self._hud_initialized.is_set()):
            return
        if self._has_selected_target():
            if selected_event is not None:
                selected_event.set()
            return  # Keep the existing target instead of cycling away with Tab.
        now = time.monotonic()
        if now - self._last_target_tab < self._target_tab_interval:
            if selected_event is not None:
                selected_event.set()
            return
        ic.check_cancelled()
        ic.focus_window(self.hwnd)
        if self._has_selected_target():
            if selected_event is not None:
                selected_event.set()
            return
        ic.tap_key('tab')
        self._last_target_tab = now
        if selected_event is not None:
            selected_event.set()
        ic.execution_wait(self._attack_key_gap)
        return True

    def _combat_loop(self, stop_event):
        # Only this worker sends combat inputs; combos cannot interleave with R/T.
        ic.bind_cancel_event(getattr(self, 'cancel_event', None), stop_event)
        try:
            # Wait for any interrupted roaming input to finish releasing its keys.
            while (self._roaming or
                   (self._search_thread is not None and self._search_thread.is_alive()) or
                   (self._approach_thread is not None and self._approach_thread.is_alive())):
                ic.execution_wait(0.02)
            ic.check_cancelled()
            if not self.enabled or getattr(skill_combo_config, 'FARMING_MODE', False):
                return
            self._send_basic_attack()
            while not stop_event.is_set():
                ic.check_cancelled()
                if not self.enabled or getattr(skill_combo_config, 'FARMING_MODE', False):
                    break
                self._send_basic_attack()
                manager = self.skill_combo_manager
                if (manager is not None
                        and getattr(skill_combo_config, 'SKILL_COMBO_ENABLED', True)
                        and getattr(skill_combo_config, 'COMBAT_USE_SKILLS', True)):
                    ic.check_cancelled()
                    if manager.has_ready_combo() or manager.has_available_single_skill():
                        ic.execution_wait(self._attack_repeat_gap)
                        manager.try_stealth_attack(True)
                ic.execution_wait(self._attack_repeat_gap)
        except Exception as exc:
            if not stop_event.is_set() and not getattr(self, 'cancel_event', stop_event).is_set():
                logger.error(f'ActionPlanner: combat worker stopped: {exc}')

    def _combat_target_present(self, detections, mobs):
        if self._selected_target.is_set() and not self._target_hud['visible']:
            return True  # A brief HUD miss must not end combat and reacquire another unit.
        if self._target_hud['visible']:
            # Missing/stale OCR must not make movement resume on a selected target.
            return self._target_hud['hp_visible']
        health = any(str(d.get('class', '')).lower() == 'mob_combat_health'
                     and float(d.get('confidence') or 0) >= self.conf_thresh
                     for d in detections)
        if health:
            self.health_detection_supported = True
        # Any active health bar counts: the game can switch targets automatically.
        return health if self.health_detection_supported else bool(mobs)

    def _finish_combat(self):
        self._stop_combat_worker(wait=True)
        self._current_target = None
        self._approach_expired.clear()
        if getattr(skill_combo_config, 'AUTO_LOOT', True):
            self._mode = 'scanning'
        else:
            self._mode = 'cooldown'
            self._cooldown_until = time.time() + 0.5
            self._last_cooldown_action = 0.0
        logger.info('ActionPlanner: target lost; combat worker stopped')

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if not self.enabled:
            self._sentry_rotation_stop.set()
            self._stop_combat_worker()
            self._stop_search_worker()
            self._stop_approach_worker()
            self._roam_cancel_event.set()
            self._mode = 'scanning'
            self._current_target = None

    def set_sentry_mode(self, enabled: bool):
        if not enabled:
            self._stop_combat_worker()
            self._sentry_rotation_stop.set()
        if enabled or getattr(skill_combo_config, 'FARMING_MODE', False):
            self._roam_cancel_event.set()
            self._stop_search_worker()
            self._stop_approach_worker()
        else:
            self._roam_cancel_event.clear()

    def set_farming_mode(self, enabled: bool):
        self._sentry_rotation_stop.set()
        self._stop_combat_worker()
        self._stop_search_worker()
        self._stop_approach_worker()
        # Interrupt any in-flight combat sequence; the next tick binds a fresh event.
        self.mode_cancel_event.set()
        self.mode_cancel_event = threading.Event()
        self._last_farming_press = None
        self._mode = 'scanning'
        self._current_target = None
        self.set_sentry_mode(getattr(skill_combo_config, 'SENTRY_MODE', False))

    def farming_tick(self):
        if not self.enabled or not getattr(skill_combo_config, 'FARMING_MODE', False):
            return
        if self._combat_thread is not None and self._combat_thread.is_alive():
            return  # Allow the interrupted combat worker to release its last key first.
        if (self._roaming or
                (self._sentry_rotation_thread is not None and self._sentry_rotation_thread.is_alive()) or
                (self._search_thread is not None and self._search_thread.is_alive()) or
                (self._approach_thread is not None and self._approach_thread.is_alive())):
            return  # Movement must finish releasing W/right mouse before farming starts.
        now = time.monotonic()
        if self._last_farming_press is None or now - self._last_farming_press >= 1.0:
            ic.focus_window(self.hwnd)
            ic.tap_key('f')
            self._last_farming_press = now

    def sentry_tick(self):
        if (not self.enabled or not getattr(skill_combo_config, 'SENTRY_MODE', False)
                or getattr(skill_combo_config, 'FARMING_MODE', False)):
            return
        self._stop_search_worker()
        self._stop_approach_worker()
        self._start_combat_worker()
        if self._has_selected_target():
            self._sentry_rotation_stop.set()
            return
        if self._sentry_rotation_thread is None or not self._sentry_rotation_thread.is_alive():
            stop_event = threading.Event()
            self._sentry_rotation_stop = stop_event
            self._sentry_rotation_thread = threading.Thread(target=self._sentry_rotation_loop,
                args=(stop_event,), daemon=True, name='sentry-camera')
            self._sentry_rotation_thread.start()

    def _sentry_rotation_loop(self, stop_event):
        ic.bind_cancel_event(getattr(self, 'cancel_event', None), stop_event)
        mouse_held = False
        try:
            while (self._roaming or
                   (self._search_thread is not None and self._search_thread.is_alive()) or
                   (self._approach_thread is not None and self._approach_thread.is_alive())):
                ic.execution_wait(0.02)
            while (self.enabled and getattr(skill_combo_config, 'SENTRY_MODE', False)
                   and not getattr(skill_combo_config, 'FARMING_MODE', False)
                   and not self._has_selected_target()):
                ic.check_cancelled()
                ic.focus_window(self.hwnd)
                ic.hold_mouse_down('right')
                mouse_held = True
                duration = self._roam_turn_duration / max(1, self._roam_turn_segments)
                for _ in range(self._roam_turn_segments):
                    ic.check_cancelled()
                    if (not self.enabled or not getattr(skill_combo_config, 'SENTRY_MODE', False)
                            or getattr(skill_combo_config, 'FARMING_MODE', False)
                            or self._has_selected_target()):
                        return
                    ic.move_mouse_relative(random.randint(*self._roam_turn_step), 0,
                                           steps=1, duration=duration * 0.7)
                    ic.execution_wait(duration * 0.3)
                ic.release_mouse('right')
                mouse_held = False
                ic.execution_wait(self._sentry_rotation_pause)
        except Exception as exc:
            if not stop_event.is_set() and not getattr(self, 'cancel_event', stop_event).is_set():
                logger.debug(f'ActionPlanner: sentry rotation stopped: {exc}')
        finally:
            if mouse_held:
                try:
                    ic.release_mouse('right')
                except Exception as exc:
                    logger.error(f'ActionPlanner: failed to release sentry mouse: {exc}')

    def is_enabled(self) -> bool:
        return bool(self.enabled)

    def _target_in_attack_range(self, target):
        if getattr(skill_combo_config, 'SENTRY_MODE', False):
            return True
        if self._has_selected_target():
            distance = self._hud_distance()
            if distance is None:
                # A world-space target marker supplies direction even before distance OCR.
                return self._target_marker_position() is None
            limit = self._stop_distance_m if self._mode == 'approaching' else self._resume_distance_m
            return distance <= limit
        return False

    def _hud_distance(self):
        observation = self._target_hud
        stamp = observation.get('distance_observed_at', observation['observed_at'])
        if stamp is None or time.monotonic() - stamp > self._hud_max_age:
            return None
        return observation['distance_m']

    def update_target_hud(self, observation):
        """Called by the HUD reader, including while model inference is busy."""
        if observation['observed_at'] < self._target_hud['observed_at']:
            return
        self._target_hud = observation
        self._record_target_presence(observation['visible'] or self._detected_target_health,
                                     observation['observed_at'])
        self._hud_initialized.set()
        if observation['visible']:
            self._roam_cancel_event.set()
            distance = self._hud_distance()
            if observation.get('target_position') is not None:
                self._last_target_position = observation['target_position']
                self._last_target_position_at = observation['observed_at']
            if ((distance is None and observation.get('target_position') is None)
                    or (distance is not None and distance <= self._stop_distance_m)):
                self._stop_approach_worker()

    def _has_selected_target(self):
        return (self._selected_target.is_set() or self._target_hud['visible']
                or self._detected_target_health)

    def _target_marker_position(self):
        position = self._target_hud.get('target_position')
        if (position is None and self._has_selected_target()
                and time.monotonic() - self._last_target_position_at < self._selection_loss_grace):
            position = self._last_target_position
        return position

    def _record_target_presence(self, present, observed_at):
        if present:
            self._failed_selection_attempts = 0
            self._selected_target.set()
            self._sentry_rotation_stop.set()
            self._stop_search_worker()
            self._selection_missing_since = None
            self._selection_missing_frames = 0
        elif self._selected_target.is_set():
            if self._selection_missing_since is None:
                self._selection_missing_since = observed_at
            self._selection_missing_frames += 1
            if (self._selection_missing_frames >= 3
                    and observed_at - self._selection_missing_since >= self._selection_loss_grace):
                self._selected_target.clear()
                self._last_target_position = None
                self._stop_approach_worker()
                if not getattr(skill_combo_config, 'SENTRY_MODE', False):
                    self._stop_combat_worker()

    def _start_approach_worker(self):
        if (not self.enabled or not self._has_selected_target()
                or getattr(skill_combo_config, 'SENTRY_MODE', False)
                or getattr(skill_combo_config, 'FARMING_MODE', False)):
            return
        if (self._has_selected_target()
                and self._target_in_attack_range(self._current_target or {})):
            return
        if self._approach_thread is not None and self._approach_thread.is_alive():
            return
        self._roam_cancel_event.set()
        stop_event = threading.Event()
        self._approach_stop = stop_event
        expired_event = threading.Event()
        self._approach_expired = expired_event
        self._mode = 'approaching'
        self._approach_missing_since = None
        self._approach_missing_frames = 0
        self._approach_thread = threading.Thread(
            target=self._approach_loop, args=(stop_event, expired_event), daemon=True, name='approach-input')
        self._approach_thread.start()

    def _stop_approach_worker(self):
        self._approach_stop.set()

    def _steering_key(self, previous=None):
        target = self._current_target
        width = self._window_size[0]
        if width <= 0 or (not self._has_selected_target() and (not target or not target.get('width'))):
            return None
        if self._has_selected_target():
            position = self._target_marker_position()
            if position is None:
                return None
            cx = position[0]
        else:
            cx, _ = _center_of(target)
        offset = cx / width - 0.5
        if previous == 'a' and offset < -self._steering_exit_fraction:
            return 'a'
        if previous == 'd' and offset > self._steering_exit_fraction:
            return 'd'
        if offset < -self._steering_enter_fraction:
            return 'a'
        if offset > self._steering_enter_fraction:
            return 'd'
        return None

    def _hold_approach_movement(self):
        """Keep W held while steering from the latest target position."""
        held = set()
        direction = None
        deadline = time.monotonic() + self._approach_timeout
        try:
            ic.check_cancelled()
            ic.key_down('w')
            held.add('w')
            while time.monotonic() < deadline:
                ic.check_cancelled()
                ic.check_input_target()
                if (not self.enabled or getattr(skill_combo_config, 'SENTRY_MODE', False)
                        or getattr(skill_combo_config, 'FARMING_MODE', False)):
                    return False
                next_direction = self._steering_key(direction)
                if next_direction != direction:
                    if direction is not None:
                        ic.key_up(direction)
                        held.discard(direction)
                    direction = next_direction
                    if direction is not None:
                        ic.key_down(direction)
                        held.add(direction)
                ic.execution_wait(min(0.03, max(0, deadline - time.monotonic())))
            return True
        finally:
            # Release lateral keys first; releases remain allowed after cancellation.
            for key in ('a', 'd', 'w'):
                if key in held:
                    try:
                        ic.key_up(key)
                    except Exception as exc:
                        logger.error(f'ActionPlanner: failed to release {key}: {exc}')

    def _approach_loop(self, stop_event, expired_event):
        ic.bind_cancel_event(getattr(self, 'cancel_event', None), stop_event)
        try:
            while (self._roaming or
                   (self._search_thread is not None and self._search_thread.is_alive()) or
                   (self._sentry_rotation_thread is not None and self._sentry_rotation_thread.is_alive()) or
                   (self._combat_thread is not None and self._combat_thread.is_alive())):
                ic.execution_wait(0.02)
            ic.check_cancelled()
            if not self.enabled or getattr(skill_combo_config, 'SENTRY_MODE', False):
                return
            ic.focus_window(self.hwnd)
            if getattr(skill_combo_config, 'FARMING_MODE', False):
                return
            if not self._hold_approach_movement():
                return
            ic.check_cancelled()
            expired_event.set()
        except Exception as exc:
            if not stop_event.is_set() and not getattr(self, 'cancel_event', stop_event).is_set():
                logger.error(f'ActionPlanner: approach worker stopped: {exc}')

    def _find_target_mob(self, detections: List[Dict]) -> Optional[Dict]:
        # priority: mob_oncursor, mob_near, mob_away
        priority = ["mob_oncursor", "mob_near", "mob_away"]
        
        # Get player position (center of screen)
        from utils import get_window_rect
        window_rect = get_window_rect(self.hwnd)
        if window_rect:
            _, _, screen_w, screen_h = window_rect
            player_x = screen_w / 2.0
            player_y = screen_h / 2.0
        else:
            player_x = player_y = 0
        
        # Collect all valid mob targets with their distances to player
        candidates = []
        
        for p in priority:
            for d in detections:
                name = str(d.get("class", "")).lower()
                if name == p and float(d.get("confidence") or 0) >= self.conf_thresh:
                    # check for overlapping mob_target marker
                    has_target_marker = False
                    for m in detections:
                        if str(m.get("class", "")).lower() == "mob_target":
                            if _iou(d, m) > 0.05:
                                has_target_marker = True
                                break
                    
                    # Calculate distance to player (center of screen)
                    mob_cx, mob_cy = _center_of(d)
                    distance = ((mob_cx - player_x) ** 2 + (mob_cy - player_y) ** 2) ** 0.5
                    
                    # Store candidate with priority weight and distance
                    priority_weight = priority.index(p)  # 0=oncursor, 1=near, 2=away
                    candidates.append((d, priority_weight, distance, has_target_marker))
        
        if not candidates:
            return None
        
        # Sort by: priority first (oncursor > near > away), then by distance (nearest first)
        # Prefer mobs with target markers
        candidates.sort(key=lambda x: (x[1], not x[3], x[2]))  # priority, not has_marker, distance
        
        return candidates[0][0]  # Return the closest mob with highest priority

    def _find_map_dots(self, detections: List[Dict]) -> List[Dict]:
        candidates = []
        for d in detections:
            name = str(d.get("class", "")).lower()
            if any(k in name for k in ("map", "dot", "red", "enemy", "map_dot", "map_enemy")):
                candidates.append(d)
        return candidates

    def filter_detections(self, detections: List[Dict], width: int, height: int) -> List[Dict]:
        """Ignore monster boxes centered on the player; preserve other classes."""
        self._window_size = (width, height)
        return [d for d in detections if not self._is_center_monster(d)]

    def _is_center_monster(self, detection: Dict) -> bool:
        if str(detection.get('class', '')).lower() != 'monster':
            return False
        width, height = self._window_size
        if width <= 0 or height <= 0:
            return False
        cx, cy = _center_of(detection)
        half_fraction = self._player_exclusion_fraction / 2.0
        return (abs(cx - width / 2.0) <= width * half_fraction
                and abs(cy - height / 2.0) <= height * half_fraction)

    def _find_all_monsters(self, detections: List[Dict]) -> List[Dict]:
        """Return all detections that match the 'monster' class using the new model.

        The updated model only outputs detections with class 'monster' for enemies.
        """
        out = []
        for d in detections:
            name = str(d.get('class', '')).lower()
            # New model uses exact class 'monster'
            if name == 'monster' and not self._is_center_monster(d):
                try:
                    if float(d.get('confidence', 0.0)) >= self.conf_thresh:
                        out.append(d)
                except Exception:
                    out.append(d)
        return out

    def _find_north_map_dots(self, dots: List[Dict], window_w: int, window_h: int) -> List[Dict]:
        """
        Find map dots that are in the 'north' direction relative to player.
        Assumes minimap is typically in top-right corner and player is at center.
        Dots above the player's position on minimap = north direction.
        """
        if not dots:
            return []
        
        # Find the minimap region (usually top-right quadrant)
        # Assume dots with x > window_w/2 and y < window_h/2 are on minimap
        map_dots = []
        for d in dots:
            dx = float(d.get("x", 0))
            dy = float(d.get("y", 0))
            # Minimap is typically in top-right
            if dx > window_w * 0.5 and dy < window_h * 0.5:
                map_dots.append(d)
        
        if not map_dots:
            return dots  # Fallback: return all dots
        
        # Find the center of minimap dots (approximate player position on minimap)
        avg_x = sum(float(d.get("x", 0)) for d in map_dots) / len(map_dots)
        avg_y = sum(float(d.get("y", 0)) for d in map_dots) / len(map_dots)
        
        # Dots with y < avg_y are "north" of player
        north_dots = [d for d in map_dots if float(d.get("y", 0)) < avg_y]
        
        return north_dots if north_dots else map_dots
    
    # Movement macros removed — this planner focuses on scanning -> combat -> cooldown.

    def plan_and_execute(self, detections: List[Dict], window_rect: Tuple[int, int, int, int]):
        """detections are in target (window) pixel coords; window_rect is (left, top, w, h)
        """
        if not self.enabled:
            return

        if getattr(skill_combo_config, 'FARMING_MODE', False):
            self.farming_tick()
            return

        if getattr(skill_combo_config, 'SENTRY_MODE', False):
            self.sentry_tick()
            return
        
        now = time.time()
        
        # Idle simulation removed (deterministic, continuous execution)
        
        # Detection monitors target presence; combat input runs independently.
        
        # Warmup removed — no extra delays
        
        self._last_action = now
        self._action_count += 1

        detections = self.filter_detections(detections, window_rect[2], window_rect[3])
        self._detected_target_health = any(
            str(d.get('class', '')).lower() == 'mob_combat_health'
            and float(d.get('confidence') or 0) >= self.conf_thresh for d in detections)
        if self._detected_target_health:
            self._record_target_presence(True, time.monotonic())
        elif self.health_detection_supported and not self._target_hud['visible']:
            self._record_target_presence(False, time.monotonic())
        target_visible = self._has_selected_target()
        if target_visible:
            self._roam_cancel_event.set()
            if self._target_in_attack_range(self._current_target or {}):
                self._stop_approach_worker()

        # update last detections (for roam thread to consult)
        try:
            with self._lock:
                self._last_detections = list(detections)
        except Exception:
            self._last_detections = list(detections)

        left, top, w, h = window_rect

        # Auto loot bypasses the entire F-key cooldown, including when toggled mid-cooldown.
        if self._mode == 'cooldown' and getattr(skill_combo_config, 'AUTO_LOOT', True):
            self._mode = 'scanning'
            self._current_target = None

        # Global cooldown behavior: if in cooldown mode, randomly press F during the cooldown window
        if self._mode == 'cooldown':
            if time.time() < self._cooldown_until:
                # schedule random F presses during cooldown
                if time.time() - self._last_cooldown_action >= random.uniform(*self._cooldown_f_interval):
                    try:
                        ic.focus_window(self.hwnd)
                        ic.tap_key('f')
                        self._last_cooldown_action = time.time()
                        logger.info("ActionPlanner(COOLDOWN): pressed 'F' during cooldown")
                    except Exception as e:
                        logger.error(f"ActionPlanner(COOLDOWN): failed to press F: {e}")
                return
            else:
                # cooldown finished — go back to scanning
                self._mode = 'scanning'
                self._current_target = None
                logger.info("ActionPlanner: cooldown finished, back to scanning")

        # 1) New MONSTER targeting + combat state-machine
        mobs = self._find_all_monsters(detections)

        if not target_visible:
            self._stop_approach_worker()
            self._stop_combat_worker()
            if self._mode == 'combat':
                self._finish_combat()
                if self._mode == 'cooldown':
                    return
            self._mode = 'scanning'
            self._current_target = None
            self._start_search_worker(bool(mobs))
            return
        self._stop_search_worker()

        if self._mode == 'approaching':
            if (((target_visible or getattr(skill_combo_config, 'SENTRY_MODE', False))
                    and self._target_in_attack_range(self._current_target))
                    or self._approach_expired.is_set()
                    or self._approach_thread is None or not self._approach_thread.is_alive()):
                self._stop_approach_worker()
                if self._approach_expired.is_set():
                    logger.info('ActionPlanner: approach limit reached; released W and trying combat')
                self._start_combat_worker()
            return

        if self._mode == 'scanning' and (mobs or target_visible):
            self._current_target = self._current_target or {}
            if self._target_in_attack_range(self._current_target):
                self._start_combat_worker()
            else:
                self._start_approach_worker()
            return

        if self._mode == 'combat':
            distance = self._hud_distance() if self._target_hud['visible'] else None
            if (distance is not None and distance > self._resume_distance_m
                    and not getattr(skill_combo_config, 'SENTRY_MODE', False)
                    and not self._approach_expired.is_set()):
                self._stop_combat_worker()
                self._start_approach_worker()
                return
            # Detection observes; the worker keeps attacking without awaiting this tick.
            if self._combat_thread is None or not self._combat_thread.is_alive():
                self._finish_combat()
                return
            now_mono = time.monotonic()
            if self._combat_target_present(detections, mobs):
                self._combat_signal_seen = True
                self._target_missing_since = None
                self._target_missing_frames = 0
            elif (self._combat_signal_seen
                    or now_mono - self._combat_started >= self._health_acquire_grace):
                if self._target_missing_since is None:
                    self._target_missing_since = now_mono
                self._target_missing_frames += 1
                if (self._target_missing_frames >= 2
                        and now_mono - self._target_missing_since >= self._target_loss_grace):
                    self._finish_combat()
            return

    def _stop_search_worker(self):
        self._search_stop.set()
        self._roam_cancel_event.set()

    def _start_search_worker(self, monsters_visible):
        if (not self.enabled or self._has_selected_target()
                or not self._hud_initialized.is_set()
                or getattr(skill_combo_config, 'FARMING_MODE', False)
                or getattr(skill_combo_config, 'SENTRY_MODE', False)):
            return
        if self._search_thread is not None and self._search_thread.is_alive():
            return
        if time.monotonic() - self._last_search_completed < self._search_retry_delay:
            return
        stop_event = threading.Event()
        self._search_stop = stop_event
        self._roam_cancel_event.clear()
        self._search_thread = threading.Thread(target=self._search_loop,
            args=(stop_event, monsters_visible), daemon=True, name='target-search')
        self._search_thread.start()

    def _search_loop(self, stop_event, monsters_visible):
        ic.bind_cancel_event(getattr(self, 'cancel_event', None), stop_event)
        try:
            while ((self._combat_thread is not None and self._combat_thread.is_alive())
                   or (self._sentry_rotation_thread is not None and self._sentry_rotation_thread.is_alive())
                   or (self._approach_thread is not None and self._approach_thread.is_alive())):
                ic.execution_wait(0.02)
            ic.check_cancelled()
            if self._has_selected_target():
                return
            # Try selection even when model detections are missing: the game may find a target.
            tab_sent = self._select_nearby_target()
            if not tab_sent:
                return
            # Tab can select units that YOLO misses. Attack once immediately, then
            # allow HUD confirmation; do not Tab repeatedly while waiting for a box.
            self._send_basic_attack()
            ic.execution_wait(self._post_tab_attack_wait)
            if self._has_selected_target():
                return
            self._failed_selection_attempts += 1
            if (self._visible_monsters()
                    and self._failed_selection_attempts < self._max_selection_attempts):
                logger.info('ActionPlanner: monsters still visible; retrying selection without rotating')
                return
            self._failed_selection_attempts = 0
            self._perform_roam()
        except Exception as exc:
            if not stop_event.is_set() and not getattr(self, 'cancel_event', stop_event).is_set():
                logger.error(f'ActionPlanner: target search stopped: {exc}')
        finally:
            self._last_search_completed = time.monotonic()

    def _visible_monsters(self):
        with self._lock:
            latest = list(self._last_detections)
        return self._find_all_monsters(latest)

    def _perform_roam(self):
        """Search by rotating only. Never walk or rotate with an existing target."""
        ic.bind_cancel_event(getattr(self, 'cancel_event', None), self._roam_cancel_event)
        self._roaming = True
        mouse_held = False
        try:
            ic.check_cancelled()
            if (self._has_selected_target() or not self.enabled
                    or getattr(skill_combo_config, 'SENTRY_MODE', False)
                    or getattr(skill_combo_config, 'FARMING_MODE', False)):
                return
            ic.focus_window(self.hwnd)
            ic.hold_mouse_down('right')
            mouse_held = True
            duration = self._roam_turn_duration / max(1, self._roam_turn_segments)
            for _ in range(self._roam_turn_segments):
                ic.check_cancelled()
                if self._has_selected_target():
                    break
                ic.move_mouse_relative(random.randint(*self._roam_turn_step), 0,
                                       steps=1, duration=duration * 0.7)
                ic.execution_wait(duration * 0.3)
        except Exception as exc:
            if not self._roam_cancel_event.is_set():
                logger.debug(f'ActionPlanner: search rotation stopped: {exc}')
        finally:
            if mouse_held:
                try:
                    ic.release_mouse('right')
                except Exception as exc:
                    logger.error(f'ActionPlanner: failed to release search mouse: {exc}')
            self._roaming = False
