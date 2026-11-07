"""Combat lifecycle tests with simulated input; never load the input driver."""
import importlib.util
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class SimulatedInput:
    def __init__(self):
        self.context = threading.local()
        self.keys = []
        self.movement = []
        self.rotations = []
        self.mouse = []

    def bind_cancel_event(self, event, secondary_event=None):
        self.context.events = (event, secondary_event)

    def check_cancelled(self):
        if any(event is not None and event.is_set()
               for event in getattr(self.context, 'events', ())):
            raise RuntimeError('cancelled')

    def check_input_target(self):
        self.check_cancelled()

    def execution_wait(self, duration):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            self.check_cancelled()
            time.sleep(0.001)
        self.check_cancelled()

    def is_window_foreground(self, hwnd):
        return True

    def focus_window(self, hwnd):
        self.check_cancelled()

    def tap_key(self, key):
        self.check_cancelled()
        self.keys.append((key, threading.get_ident()))
        time.sleep(0.001)

    def hold_key(self, key, duration):
        self.check_cancelled()
        self.movement.append(('down', key))
        try:
            self.execution_wait(duration)
        except RuntimeError:
            pass
        finally:
            self.movement.append(('up', key))

    def key_down(self, key):
        self.check_cancelled()
        self.movement.append(('down', key))

    def key_up(self, key):
        self.movement.append(('up', key))


class CombatWorkerTests(unittest.TestCase):
    monster = {'class': 'monster', 'confidence': 0.9,
               'x': 100, 'y': 100, 'width': 20, 'height': 30}
    rect = (0, 0, 800, 600)

    def setUp(self):
        self.ic = SimulatedInput()
        self.ic.hold_mouse_down = lambda button: self.ic.mouse.append(('down', button))
        self.ic.release_mouse = lambda button: self.ic.mouse.append(('up', button))
        self.ic.move_mouse_relative = lambda dx, dy, **kwargs: self.ic.rotations.append((dx, dy))
        self.cfg = SimpleNamespace(FARMING_MODE=False, SENTRY_MODE=False,
                                   AUTO_LOOT=True, ENABLE_ROAM=True,
                                   SKILL_COMBO_ENABLED=False, COMBAT_USE_SKILLS=True)
        self.manager = Mock()
        modules = {'input_controller': self.ic, 'skill_combo_config': self.cfg,
                   'loguru': SimpleNamespace(logger=Mock()),
                   'skill_combo_manager': SimpleNamespace(SkillComboManager=lambda hwnd: self.manager)}
        spec = importlib.util.spec_from_file_location(
            '_combat_planner_test', Path(__file__).resolve().parents[1] / 'action_planner.py')
        module = importlib.util.module_from_spec(spec)
        module_patch = patch.dict(sys.modules, modules)
        module_patch.start()
        self.addCleanup(module_patch.stop)
        spec.loader.exec_module(module)
        self.planner = module.ActionPlanner(1)
        self.planner.cancel_event = threading.Event()
        self.planner._attack_key_gap = 0.001
        self.planner._attack_repeat_gap = 0.001
        self.planner._target_confirm_wait = 0.03
        self.planner._post_tab_attack_wait = 0.04
        self.planner._search_retry_delay = 0
        self.planner._roam_turn_duration = 0.024
        self.planner._target_loss_grace = 0
        self.planner._window_size = (800, 600)
        self.planner._hud_initialized.set()  # Simulate a completed initial HUD scan.

    def tearDown(self):
        self.planner.cancel_event.set()
        self.planner.set_enabled(False)
        for name in ('_search_thread', '_combat_thread', '_approach_thread', '_sentry_rotation_thread'):
            worker = getattr(self.planner, name)
            if worker is not None:
                worker.join(0.5)
                self.assertFalse(worker.is_alive(), name)

    def wait_for(self, condition):
        deadline = time.monotonic() + 1
        while not condition() and time.monotonic() < deadline:
            time.sleep(0.002)
        self.assertTrue(condition())

    def scan(self, detections=()):
        self.planner.plan_and_execute(list(detections), self.rect)

    def hud(self, distance=19, position=None):
        self.planner.update_target_hud(dict(visible=True, hp_visible=True,
            distance_m=distance, target_position=position, engaged=position is not None,
            observed_at=time.monotonic()))

    def lose_target(self):
        self.planner._selection_loss_grace = 0
        for _ in range(3):
            self.planner.update_target_hud(dict(visible=False, hp_visible=False,
                distance_m=None, target_position=None, observed_at=time.monotonic()))

    def test_selected_target_repeats_rt1_without_tab_or_search(self):
        self.hud()
        self.scan([self.monster])
        self.wait_for(lambda: len(self.ic.keys) >= 12)
        self.assertEqual([k for k, _ in self.ic.keys[:12]], ['r', 't', '1', '2'] * 3)
        self.assertEqual(self.ic.movement, [])
        self.assertEqual(self.ic.rotations, [])
        self.assertFalse(self.planner._start_combat_worker())

    def test_high_confidence_monster_tries_tab_and_full_rotation_without_turning(self):
        self.scan([dict(self.monster, confidence=0.8)])
        worker = self.planner._search_thread
        self.wait_for(lambda: not worker.is_alive())
        self.assertEqual([k for k, _ in self.ic.keys], ['tab', 'r', 't', '1', '2'])
        self.assertEqual(self.ic.movement, [])
        self.assertEqual(self.ic.rotations, [])
        self.assertEqual(self.ic.mouse, [])
        self.assertIsNone(self.planner._combat_thread)
        self.assertIsNone(self.planner._approach_thread)

    def test_one_tab_attack_attempt_precedes_rotation_even_without_yolo(self):
        self.scan()
        self.wait_for(lambda: not self.planner._search_thread.is_alive())
        self.assertEqual([k for k, _ in self.ic.keys], ['tab', 'r', 't', '1', '2'])
        self.assertEqual(self.ic.movement, [])
        self.assertEqual(len(self.ic.rotations), 12)
        self.assertTrue(all(10 <= abs(dx) <= 16 for dx, _ in self.ic.rotations))

    def test_tab_confirmation_follows_marker_without_rotation(self):
        self.planner._target_confirm_wait = 0.5
        self.scan([self.monster])
        self.wait_for(lambda: bool(self.ic.keys))
        self.hud(25, (100, 200))
        self.scan()
        self.wait_for(lambda: ('down', 'a') in self.ic.movement)
        self.assertEqual([k for k, _ in self.ic.keys].count('tab'), 1)
        self.assertEqual(self.ic.rotations, [])
        self.assertEqual(self.planner._mode, 'approaching')

    def test_tab_selected_target_moves_even_when_yolo_returns_no_boxes(self):
        self.planner._target_confirm_wait = 0.5
        self.scan([])
        self.wait_for(lambda: 'tab' in [key for key, _ in self.ic.keys])
        self.hud(25, (650, 200))
        self.scan([])
        self.wait_for(lambda: ('down', 'd') in self.ic.movement)
        self.assertIn(('down', 'w'), self.ic.movement)
        self.assertEqual([key for key, _ in self.ic.keys].count('tab'), 1)
        self.assertEqual(self.ic.rotations, [])
        self.assertEqual(self.planner._mode, 'approaching')

    def test_attack_probe_can_acquire_target_before_rotation(self):
        self.planner._target_confirm_wait = 0.15
        self.scan([self.monster])
        self.wait_for(lambda: [key for key, _ in self.ic.keys] == ['tab', 'r', 't', '1', '2'])
        self.hud(19)
        self.scan()
        self.wait_for(lambda: len(self.ic.keys) >= 5)
        self.assertEqual(self.ic.rotations, [])
        self.assertEqual(self.ic.movement, [])
        self.assertEqual([key for key, _ in self.ic.keys].count('tab'), 1)

    def test_monster_detected_during_selection_wait_prevents_rotation(self):
        self.planner._target_confirm_wait = 0.08
        self.scan()
        self.wait_for(lambda: bool(self.ic.keys))
        self.scan([dict(self.monster, confidence=0.8)])
        self.wait_for(lambda: not self.planner._search_thread.is_alive())
        self.assertEqual(self.ic.rotations, [])
        self.assertEqual([key for key, _ in self.ic.keys], ['tab', 'r', 't', '1', '2'])

    def test_arrow_direction_overrides_other_monster_boxes(self):
        self.hud(25, (100, 200))
        self.scan([dict(self.monster, x=650, height=120)])
        self.wait_for(lambda: ('down', 'a') in self.ic.movement)
        self.assertNotIn(('down', 'd'), self.ic.movement)
        self.hud(25, (650, 200))
        self.wait_for(lambda: ('down', 'd') in self.ic.movement)
        self.assertLess(self.ic.movement.index(('up', 'a')), self.ic.movement.index(('down', 'd')))
        self.hud(25, (400, 200))
        self.wait_for(lambda: ('up', 'd') in self.ic.movement)
        self.assertNotIn(('up', 'w'), self.ic.movement)
        self.hud(19, (400, 200))
        self.scan()
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        for key in ('w', 'a', 'd'):
            self.assertEqual(self.ic.movement.count(('down', key)), self.ic.movement.count(('up', key)))
        self.assertNotIn('tab', [k for k, _ in self.ic.keys])

    def test_marker_without_distance_can_approach_but_is_bounded(self):
        self.planner._approach_timeout = 0.04
        self.hud(None, (100, 200))
        self.scan()
        self.wait_for(lambda: not self.planner._approach_thread.is_alive())
        self.assertTrue(self.planner._approach_expired.is_set())
        self.assertEqual(self.ic.movement[-1], ('up', 'w'))
        self.scan()
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        self.assertEqual(self.planner._mode, 'combat')
        self.assertNotIn('tab', [k for k, _ in self.ic.keys])

    def test_hp_only_unknown_distance_attacks_without_blind_movement(self):
        self.hud(None)
        self.scan()
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        self.assertEqual(self.ic.movement, [])
        self.assertNotIn('tab', [k for k, _ in self.ic.keys])

    def test_19_20_metre_hysteresis(self):
        self.hud(25, (100, 200))
        self.scan()
        self.wait_for(lambda: ('down', 'w') in self.ic.movement)
        self.hud(19.5, (100, 200))
        self.scan()
        self.assertEqual(self.planner._mode, 'approaching')
        self.hud(19)
        self.scan()
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        self.hud(20)
        self.scan()
        self.assertEqual(self.planner._mode, 'combat')
        self.hud(21, (100, 200))
        self.scan()
        self.wait_for(lambda: self.ic.movement.count(('down', 'w')) == 2)

    def test_selection_lock_survives_brief_hud_loss(self):
        self.hud()
        self.scan()
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        self.planner.update_target_hud(dict(visible=False, hp_visible=False,
            distance_m=None, observed_at=time.monotonic()))
        self.scan([self.monster])
        self.assertTrue(self.planner._has_selected_target())
        self.assertEqual(self.planner._mode, 'combat')
        self.assertNotIn('tab', [k for k, _ in self.ic.keys])
        self.assertEqual(self.ic.rotations, [])

    def test_confirmed_target_loss_stops_attack_and_returns_to_search(self):
        self.hud()
        self.scan()
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        worker = self.planner._combat_thread
        self.lose_target()
        self.scan()
        self.wait_for(lambda: not worker.is_alive())
        self.wait_for(lambda: bool(self.ic.rotations))
        self.assertEqual(self.planner._mode, 'scanning')

    def test_farming_interrupts_movement_and_only_sends_f(self):
        self.hud(25, (100, 200))
        self.scan()
        self.wait_for(lambda: ('down', 'a') in self.ic.movement)
        self.cfg.FARMING_MODE = True
        self.planner.set_farming_mode(True)
        self.wait_for(lambda: not self.planner._approach_thread.is_alive())
        self.planner.farming_tick()
        self.assertEqual([k for k, _ in self.ic.keys], ['f'])
        self.assertEqual(self.ic.movement[-1], ('up', 'w'))

    def test_sentry_rotates_without_searching_or_walking(self):
        self.cfg.SENTRY_MODE = True
        self.planner.set_sentry_mode(True)
        self.scan([self.monster])
        self.assertIsNone(self.planner._search_thread)
        self.wait_for(lambda: bool(self.ic.rotations))
        self.hud(25, (100, 200))
        self.scan()
        self.wait_for(lambda: not self.planner._sentry_rotation_thread.is_alive())
        turns = len(self.ic.rotations)
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        self.assertEqual(self.ic.movement, [])
        self.planner.sentry_tick()
        self.assertEqual(len(self.ic.rotations), turns)
        self.assertNotIn('tab', [k for k, _ in self.ic.keys])

    def test_sentry_with_existing_target_never_starts_rotation(self):
        self.cfg.SENTRY_MODE = True
        self.hud(19)
        self.planner.sentry_tick()
        self.wait_for(lambda: len(self.ic.keys) >= 4)
        self.assertIsNone(self.planner._sentry_rotation_thread)
        self.assertEqual(self.ic.rotations, [])

    def test_new_visual_frame_cannot_refresh_stale_distance_or_start_search(self):
        self.planner.update_target_hud(dict(visible=True, hp_visible=True, distance_m=22,
            observed_at=time.monotonic(), distance_observed_at=time.monotonic() - 20))
        self.assertIsNone(self.planner._hud_distance())
        self.scan([])
        self.wait_for(lambda: len(self.ic.keys) >= 4)
        self.assertIsNone(self.planner._search_thread)
        self.assertEqual(self.ic.rotations, [])

    def test_sentry_resumes_rotation_after_confirmed_target_loss(self):
        self.cfg.SENTRY_MODE = True
        self.hud(19)
        self.planner.sentry_tick()
        combat = self.planner._combat_thread
        self.wait_for(lambda: len(self.ic.keys) >= 4)
        self.lose_target()
        self.planner.sentry_tick()
        self.wait_for(lambda: bool(self.ic.rotations))
        self.assertIs(self.planner._combat_thread, combat)
        self.assertEqual(self.ic.movement, [])

    def test_sentry_attacks_without_monsters_target_hud_or_completed_hud_scan(self):
        self.cfg.SENTRY_MODE = True
        self.planner._hud_initialized.clear()
        self.planner.set_sentry_mode(True)
        self.planner.sentry_tick()
        worker = self.planner._combat_thread
        self.wait_for(lambda: len(self.ic.keys) >= 8)
        self.planner.sentry_tick()
        self.assertIs(self.planner._combat_thread, worker)
        self.assertEqual([key for key, _ in self.ic.keys[:8]], ['r', 't', '1', '2'] * 2)
        self.assertEqual(self.ic.movement, [])
        self.wait_for(lambda: bool(self.ic.rotations))
        self.assertIsNone(self.planner._search_thread)

    def test_farming_still_overrides_sentry_and_stop_cancels_it(self):
        self.cfg.SENTRY_MODE = True
        self.planner.sentry_tick()
        self.wait_for(lambda: len(self.ic.keys) >= 4)
        self.cfg.FARMING_MODE = True
        self.planner.set_farming_mode(True)
        self.wait_for(lambda: not self.planner._combat_thread.is_alive())
        self.wait_for(lambda: not self.planner._sentry_rotation_thread.is_alive())
        count = len(self.ic.keys)
        self.planner.sentry_tick()
        self.planner.farming_tick()
        self.assertEqual([key for key, _ in self.ic.keys[count:]], ['f'])

    def test_disabling_sentry_stops_camera_and_releases_mouse(self):
        self.cfg.SENTRY_MODE = True
        self.planner._roam_turn_duration = 2
        self.planner.sentry_tick()
        self.wait_for(lambda: bool(self.ic.rotations))
        self.cfg.SENTRY_MODE = False
        self.planner.set_sentry_mode(False)
        self.wait_for(lambda: not self.planner._sentry_rotation_thread.is_alive())
        self.assertEqual(self.ic.mouse[-1], ('up', 'right'))
        self.assertEqual(self.ic.movement, [])

    def test_stop_releases_movement_keys(self):
        self.hud(25, (100, 200))
        self.scan()
        self.wait_for(lambda: ('down', 'a') in self.ic.movement)
        self.planner.cancel_event.set()
        self.wait_for(lambda: not self.planner._approach_thread.is_alive())
        self.assertEqual(self.ic.movement[-2:], [('up', 'a'), ('up', 'w')])

    def test_stop_interrupts_search_rotation_and_releases_mouse(self):
        self.planner._roam_turn_duration = 2
        self.scan()
        self.wait_for(lambda: bool(self.ic.rotations))
        self.planner.set_enabled(False)
        self.wait_for(lambda: not self.planner._search_thread.is_alive())
        self.assertEqual(self.ic.mouse[-1], ('up', 'right'))

    def test_selected_marker_interrupts_search_rotation(self):
        self.planner._roam_turn_duration = 2
        self.scan()
        self.wait_for(lambda: bool(self.ic.rotations))
        tab_count = [k for k, _ in self.ic.keys].count('tab')
        self.hud(25, (100, 200))
        self.scan()
        self.wait_for(lambda: ('down', 'a') in self.ic.movement)
        self.assertFalse(self.planner._search_thread.is_alive())
        self.assertEqual(self.ic.mouse[-1], ('up', 'right'))
        self.assertEqual([k for k, _ in self.ic.keys].count('tab'), tab_count)

    def test_target_acquired_during_focus_prevents_pending_tab(self):
        self.ic.focus_window = Mock(side_effect=lambda hwnd: self.hud())
        self.planner._select_nearby_target()
        self.assertEqual(self.ic.keys, [])
        self.assertTrue(self.planner._has_selected_target())

    def test_combo_runs_off_detection_thread_and_can_be_cancelled(self):
        started = threading.Event()
        def combo(has_health):
            started.set()
            self.ic.execution_wait(0.5)
        self.cfg.SKILL_COMBO_ENABLED = True
        self.manager.has_ready_combo.return_value = True
        self.manager.try_stealth_attack.side_effect = combo
        self.hud()
        self.scan()
        self.assertTrue(started.wait(1))
        self.planner.set_enabled(False)
        self.wait_for(lambda: not self.planner._combat_thread.is_alive())

    def test_model_health_confirms_target_without_tab(self):
        self.scan([dict(class_='unused', **{'class':'mob_combat_health', 'confidence':0.9})])
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        self.assertNotIn('tab', [k for k, _ in self.ic.keys])

    def test_center_filter_still_ignores_player_character(self):
        center = dict(self.monster, x=390, y=285)
        self.assertEqual(self.planner.filter_detections([center], 800, 600), [])
        self.scan([center])
        self.wait_for(lambda: not self.planner._search_thread.is_alive())
        self.assertEqual([k for k, _ in self.ic.keys].count('tab'), 1)
        self.assertEqual(self.ic.movement, [])

    def test_no_duplicate_search_workers_or_extra_tab_while_waiting(self):
        self.planner._post_tab_attack_wait = 0.5
        self.scan([self.monster])
        worker = self.planner._search_thread
        self.wait_for(lambda: bool(self.ic.keys))
        for _ in range(5):
            self.scan([self.monster])
        self.assertIs(self.planner._search_thread, worker)
        self.assertEqual([k for k, _ in self.ic.keys].count('tab'), 1)

    def test_startup_waits_for_hud_check_before_any_tab(self):
        self.planner._hud_initialized.clear()
        self.scan([self.monster])
        self.assertIsNone(self.planner._search_thread)
        self.assertEqual(self.ic.keys, [])
        self.hud(19, (100, 200))
        self.scan([self.monster])
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        self.assertNotIn('tab', [key for key, _ in self.ic.keys])

    def test_brief_marker_loss_keeps_direction_and_suppresses_search(self):
        self.hud(25, (100, 200))
        self.scan()
        self.wait_for(lambda: ('down', 'a') in self.ic.movement)
        worker = self.planner._approach_thread
        self.planner.update_target_hud(dict(visible=False, hp_visible=False,
            distance_m=None, observed_at=time.monotonic()))
        self.scan([dict(self.monster, x=650)])
        self.assertTrue(worker.is_alive())
        self.assertNotIn(('up', 'w'), self.ic.movement)
        self.assertIsNone(self.planner._search_thread)
        self.assertNotIn('tab', [key for key, _ in self.ic.keys])

    def test_manual_looting_still_follows_target_loss(self):
        self.cfg.AUTO_LOOT = False
        self.hud()
        self.scan()
        self.wait_for(lambda: len(self.ic.keys) >= 3)
        self.lose_target()
        self.scan()
        self.assertEqual(self.planner._mode, 'cooldown')
        self.scan()
        self.assertEqual(self.ic.keys[-1][0], 'f')

    def test_unconfirmed_boxes_cannot_suppress_rotation_forever(self):
        self.planner._target_tab_interval = 0
        self.scan([dict(self.monster, confidence=0.8)])
        first = self.planner._search_thread
        self.wait_for(lambda: not first.is_alive())
        self.assertEqual(self.ic.rotations, [])
        self.scan([dict(self.monster, confidence=0.8)])
        self.wait_for(lambda: not self.planner._search_thread.is_alive())
        self.assertTrue(self.ic.rotations)
        self.assertEqual([key for key, _ in self.ic.keys].count('tab'), 2)

    def test_yolo_box_loss_does_not_cancel_a_tab_selected_attack_attempt(self):
        original_tap = self.ic.tap_key
        def disappear_on_r(key):
            original_tap(key)
            if key == 'r':
                with self.planner._lock:
                    self.planner._last_detections = []
        self.ic.tap_key = disappear_on_r
        self.scan([self.monster])
        self.wait_for(lambda: not self.planner._search_thread.is_alive())
        self.assertEqual([key for key, _ in self.ic.keys], ['tab', 'r', 't', '1', '2'])
        self.assertTrue(self.ic.rotations)


if __name__ == '__main__':
    unittest.main()
