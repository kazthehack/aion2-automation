"""Detection controller: ties capture, workflow client, and overlay together."""
import threading
import time
from typing import Callable
from loguru import logger
from capture import CaptureWorker
from model_client import LocalModelClient
from action_planner import ActionPlanner
import input_controller as ic
import skill_combo_config
from target_hud import TargetHUDReader
from verification_guard import VerificationGuard, SelectedGameProcess
from utils import get_window_rect
# utils helpers (no jpeg encode needed for local model)


class DetectionController:
    def __init__(self, hwnd: int, overlay_update: Callable, log_fn: Callable, fps: int = None, on_failsafe=None):
        """overlay_update(detections, (w,h)) will be called on each new result or tick.
        log_fn(text) will be called to output logs to UI.
        """
        self.hwnd = hwnd
        self.overlay_update = overlay_update
        self.log = log_fn
        self._on_failsafe = on_failsafe
        self._selected_game = None
        try:
            self._selected_game = SelectedGameProcess(hwnd)
        except Exception as exc:
            self.log(f'Process identity unavailable; verification fail-safe will stop inputs only: {exc}')
        # Default FPS (no stealth behavior). Higher default for more real-time overlay updates.
        self.fps = fps if fps is not None else 30

        # keep capture at original size (no forced resize) to preserve mapping accuracy;
        # we'll make a resized copy for the model if needed inside the model client.
        self.capture = CaptureWorker(hwnd=hwnd, target_fps=max(5, self.fps * 2), resize_max=None)
        # local model uses models/aion.pt in repo
        self.client = LocalModelClient(weights_path="models/aion.pt")
        # action planner will perform input actions (Tab-target + R/T attacks / movement)
        # Enabled by default per user request; main window will also apply its stored preference.
        self.action_planner = ActionPlanner(hwnd=hwnd, enabled=True)
        names = getattr(self.client.model, 'names', {})
        labels = names.values() if isinstance(names, dict) else names
        self.action_planner.health_detection_supported = any(
            str(label).lower() == 'mob_combat_health' for label in (labels or []))
        self._cancel_execution = threading.Event()
        self.action_planner.cancel_event = self._cancel_execution
        self._last_hud_status = None
        self.hud_reader = TargetHUDReader(
            self._on_target_hud, frame_provider=self.capture.get_latest_frame,
            verification_guard=VerificationGuard(self._pause_for_verification, self._close_verified_game))

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._running = threading.Event()

        # last known detections and frame size
        self._detections = []
        self._frame_size = (0, 0)
        
        # Startup delay flag - prevents actions immediately after start
        self._startup_complete = False

    def _pause_for_verification(self):
        self._cancel_execution.set()
        self._running.clear()
        self.action_planner.set_enabled(False)
        self.log('Daeva Verification detected: all automated input stopped. Confirming before closing AION2.')

    def _close_verified_game(self):
        # Release held inputs before closing the window; never send dialog clicks/keys.
        self._pause_for_verification()
        try:
            for name in ('_search_thread', '_approach_thread', '_combat_thread', '_sentry_rotation_thread'):
                worker = getattr(self.action_planner, name, None)
                if worker is not None and worker is not threading.current_thread():
                    worker.join(timeout=0.4)
            if self._selected_game is None:
                self.log('Automation remains stopped; AION2 process identity was unavailable, so no process was killed.')
            else:
                self._selected_game.terminate()
                self.log('Verification fail-safe: selected AION2 process closed. Automation remains stopped.')
        except Exception as exc:
            self.log(f'Automation stopped; could not close selected AION2 safely: {exc}')
        finally:
            self.stop()
            if self._on_failsafe is not None:
                self._on_failsafe()

    def _on_target_hud(self, observation):
        self.action_planner.update_target_hud(observation)
        if not observation['visible']:
            if self.action_planner._has_selected_target():
                return  # Do not report a lost target for a brief missed frame.
            status = 'none'
            message = 'Target HUD: no selected target confirmed; monster boxes alone do not confirm selection.'
        else:
            source = 'arrow marker' if observation.get('target_position') is not None else 'HP bar'
            distance = self.action_planner._hud_distance()
            if distance is None:
                status = (source, 'unknown')
                message = f'Target confirmed by {source}, without needing a monster box; distance not read yet.'
            else:
                status = (source, round(distance, 1))
                message = f'Target confirmed by {source}: {distance:g} m; monster bounding box not required.'
        if status != self._last_hud_status:
            self._last_hud_status = status
            self.log(message)

    def start(self):
        # Start without extra startup delay (stealth removed)
        self.log("Starting capture and detection")
        self.capture.start_capture()
        self.hud_reader.start()
        self._running.set()
        if not self._worker.is_alive():
            self._worker.start()
        
        # No startup delay — automation active immediately
        self._startup_complete = True
        self.log("✓ Automation active")

    def stop(self):
        self._cancel_execution.set()
        self.action_planner.set_enabled(False)
        self.log("Stopping detection")
        self._running.clear()
        self.capture.stop_capture()
        self.hud_reader.stop()

    def _run(self):
        ic.bind_cancel_event(self._cancel_execution)
        interval = 1.0 / max(1, self.fps)
        while self._running.is_set():
            ic.bind_cancel_event(self._cancel_execution, self.action_planner.mode_cancel_event)
            # Farming runs independently of frames/model inference for steady F presses.
            if getattr(skill_combo_config, 'FARMING_MODE', False):
                if self._startup_complete:
                    try:
                        self.action_planner.farming_tick()
                    except Exception as e:
                        self.log(f'Farming mode error: {e}')
                self._cancel_execution.wait(0.02)
                continue
            if getattr(skill_combo_config, 'SENTRY_MODE', False):
                if self._startup_complete:
                    self.action_planner.sentry_tick()
                self._cancel_execution.wait(0.02)
                continue
            frame = self.capture.get_latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            h, w = frame.shape[:2]
            self._frame_size = (w, h)
            try:
                # We run the local model on a resized copy for speed, then map detections
                # back to the original window coordinates.
                orig_w, orig_h = self.capture.get_window_size() or (w, h)
                frame_for_model = frame.copy()
                # Always push latest known detections to overlay immediately so the overlay
                # stays responsive even if inference takes longer than a single loop.
                try:
                    self.overlay_update(self._detections, (orig_w, orig_h))
                except Exception:
                    pass
                # Let the model client decide resizing via its imgsz; but we will pass the frame_for_model as-is.
                t0 = time.time()
                preds = self.client.predict(frame_for_model)
                t1 = time.time()
                inference_ms = (t1 - t0) * 1000.0

                sent_h, sent_w = frame_for_model.shape[:2]
                sx = orig_w / sent_w if sent_w and orig_w else 1.0
                sy = orig_h / sent_h if sent_h and orig_h else 1.0

                conv = []
                for p in preds:
                    try:
                        x = float(p.get("x", 0)) * sx
                        y = float(p.get("y", 0)) * sy
                        pw = float(p.get("width", 0)) * sx
                        ph = float(p.get("height", 0)) * sy
                        conv.append({"x": x, "y": y, "width": pw, "height": ph, "class": p.get("class"), "confidence": p.get("confidence")})
                    except Exception:
                        continue

                # Update latest detection list (in pixel coords for the original window)
                conv = self.action_planner.filter_detections(conv, orig_w, orig_h)
                self._detections = conv
                # record whether this frame had detections for the action planner to consult
                try:
                    self.action_planner._last_frame_had_detections = bool(len(conv))
                    self.action_planner._last_inference_ms = inference_ms
                except Exception:
                    pass
                # push to overlay (pass overlay target size as orig window size)
                # Push the new detections immediately to overlay
                try:
                    self.overlay_update(self._detections, (orig_w, orig_h))
                except Exception:
                    pass
                # execute action planner (navigate / attack) -- pass full window rect
                # BUT ONLY if startup delay is complete (CryEngine anti-cheat evasion)
                if self._startup_complete:
                    try:
                        rect = get_window_rect(self.hwnd)
                        if rect:
                            left, top, rw, rh = rect
                            self.action_planner.plan_and_execute(self._detections, (left, top, rw, rh))
                        else:
                            # fallback: use origin at (0,0) + orig sizes
                            self.action_planner.plan_and_execute(self._detections, (0, 0, orig_w, orig_h))
                    except Exception as e:
                        # action planner errors should not stop the detection loop
                        self.log(f"Action planner error: {e}")
            except Exception as e:
                self.log(f"Inference error: {e}")
            time.sleep(interval)
