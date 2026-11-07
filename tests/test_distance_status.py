"""Exercise dashboard distance feedback without starting a GUI or input driver."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class DistanceStatusTests(unittest.TestCase):
    def test_far_distance_changes_are_logged_and_missing_reading_clears_status(self):
        source = Path(__file__).resolve().parents[1] / 'detection.py'
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == '_on_target_hud')
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
        state = {}
        planner = SimpleNamespace(update_target_hud=lambda observation: state.update(observation),
            _has_selected_target=lambda: state.get('visible', False),
            _hud_distance=lambda: state.get('distance_m'))
        listener = SimpleNamespace(action_planner=planner, _last_hud_status=None, log=Mock())
        observe = namespace['_on_target_hud']
        for distance in (22, 21, 21, None):
            observe(listener, dict(visible=True, hp_visible=True, distance_m=distance))
        self.assertEqual(listener.log.call_count, 3)
        messages = [call.args[0] for call in listener.log.call_args_list]
        self.assertIn('22 m', messages[0])
        self.assertIn('21 m', messages[1])
        self.assertIn('distance not read', messages[2])


if __name__ == '__main__':
    unittest.main()
