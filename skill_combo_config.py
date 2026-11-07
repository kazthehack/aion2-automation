"""skill_combo_config

This module exposes configuration values and helper functions for the skill
combo system. The actual editable configuration is stored in
`skill_combo_config.json` (same directory). The JSON file is read on import
and written atomically when `save_config()` or `update_config()` is called.

This wrapper keeps the same public constants and helper functions that the
rest of the codebase expects, while making the config human-editable and
stable across program updates.
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from loguru import logger


# Path to the JSON config file (adjacent to this module)
_CONFIG_PATH = Path(__file__).with_suffix('.json')


# Default configuration used to bootstrap the JSON file if it doesn't exist.
_DEFAULT_CONFIG: Dict[str, Any] = {
    "SKILL_COOLDOWNS": {
        "1": 10.0,
        "2": 12.0,
        "3": 15.0,
        "4": 8.0,
        "5": 20.0,
        "6": 18.0,
        "7": 25.0,
        "8": 30.0,
        "9": 15.0,
        "0": 10.0,
        "-": 45.0,
        "=": 60.0,
        "f1": 10.0,
        "f2": 12.0,
        "f3": 15.0,
        "f4": 8.0,
        "f5": 20.0,
        "f6": 18.0,
        "f7": 25.0,
        "f8": 30.0,
        "f9": 15.0,
    },
    "COMBO_SETS": [
        {
            "name": "Basic DPS Rotation",
            "skills": ["1", "2", "3", "4"],
            "cooldown": 60.0,
            "delay_between_skills": 0.5,
            "enabled": True,
        },
        {
            "name": "Buff Combo",
            "skills": ["f1", "f2", "f3"],
            "cooldown": 120.0,
            "delay_between_skills": 0.8,
            "enabled": True,
        },
        {
            "name": "Ultimate Combo",
            "skills": ["f4", "5", "6", "7", "f5"],
            "cooldown": 180.0,
            "delay_between_skills": 1.0,
            "enabled": True,
        },
    ],
    "DELAY_RANDOMIZATION": 0.15,
    "SKILL_COMBO_ENABLED": True,
    "PRE_MACRO_FOCUS_ENABLED": False,
    "PRE_MACRO_FOCUS_DELAY": 0.25,
    "INPUT_BACKEND": "interception",
    "INPUT_DRY_RUN": False,
    "COMBO_PRIORITY": None,
    "STEALTH_ATTACK_MODE_ENABLED": True,
    "ATTACK_MODE_WEIGHTS": {
        "standard_attack": 0.5,
        "single_skill": 0.3,
        "combo_set": 0.2,
    },
    "SINGLE_SKILL_POOL": ["1", "2", "3", "4", "5"],
    "SINGLE_SKILL_GLOBAL_COOLDOWN": 1.5,
    # When true, during combat the planner may use skills and combo sets
    # according to the attack mode weights. This allows mixing R/T with
    # configured skills and combo sets while in combat.
    "COMBAT_USE_SKILLS": True,
    "AUTO_LOOT": True,
    "SENTRY_MODE": False,
    "FARMING_MODE": False,
    "SKIP_PRESTART_CHECKLIST": False,
    # When true, the planner will perform idle roaming: move forward and look around
    # when no monsters are detected. Toggleable in the UI.
    "ENABLE_ROAM": True,
    "LANGUAGE": "en",
}


def _atomic_write(path: Path, data: str) -> None:
    """Write `data` to `path` atomically (write temp + replace).

    This ensures we replace the JSON object cleanly rather than appending.
    """
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        f.write(data)
    os.replace(str(tmp), str(path))


def _load_config() -> Dict[str, Any]:
    if not _CONFIG_PATH.exists():
        logger.info("skill_combo_config: creating default JSON config")
        _atomic_write(_CONFIG_PATH, json.dumps(_DEFAULT_CONFIG, indent=2))
    try:
        with _CONFIG_PATH.open('r', encoding='utf-8') as f:
            cfg = json.load(f)
        return cfg
    except Exception as e:
        logger.error(f"Failed to read config JSON: {e}; using defaults")
        return dict(_DEFAULT_CONFIG)


# In-memory config object
_config: Dict[str, Any] = _load_config()


# Expose common keys as module-level names for backwards compatibility.
def _refresh_module_vars() -> None:
    global SKILL_COOLDOWNS, COMBO_SETS, DELAY_RANDOMIZATION, SKILL_COMBO_ENABLED
    global PRE_MACRO_FOCUS_ENABLED, PRE_MACRO_FOCUS_DELAY, INPUT_BACKEND, INPUT_DRY_RUN
    global COMBO_PRIORITY, STEALTH_ATTACK_MODE_ENABLED, ATTACK_MODE_WEIGHTS
    global SINGLE_SKILL_POOL, SINGLE_SKILL_GLOBAL_COOLDOWN
    global COMBAT_USE_SKILLS, AUTO_LOOT, SENTRY_MODE, FARMING_MODE, ENABLE_ROAM, LANGUAGE
    global SKIP_PRESTART_CHECKLIST

    # Normalize skill keys: strip any leading 'alt+' or 'ctrl+' and normalize to lowercase
    raw_skills = _config.get('SKILL_COOLDOWNS', {}) or {}
    normalized = {}
    for k, v in raw_skills.items():
        kn = str(k).lower().strip()
        if kn.startswith('alt+'):
            kn = kn.replace('alt+', '', 1)
        if kn.startswith('ctrl+'):
            kn = kn.replace('ctrl+', '', 1)
        normalized[kn] = v
    SKILL_COOLDOWNS = normalized
    # Normalize combo skill lists as well (strip modifiers)
    raw_combos = _config.get('COMBO_SETS', []) or []
    def _normalize_skill(s: str) -> str:
        if not isinstance(s, str):
            return s
        s2 = s.lower().strip()
        if s2.startswith('alt+'):
            s2 = s2.replace('alt+', '', 1)
        if s2.startswith('ctrl+'):
            s2 = s2.replace('ctrl+', '', 1)
        return s2

    COMBO_SETS = []
    for combo in raw_combos:
        try:
            c = dict(combo)
            if 'skills' in c and isinstance(c['skills'], list):
                c['skills'] = [_normalize_skill(s) for s in c['skills']]
            COMBO_SETS.append(c)
        except Exception:
            # fallback to original
            COMBO_SETS.append(combo)
    DELAY_RANDOMIZATION = float(_config.get('DELAY_RANDOMIZATION', 0.15))
    SKILL_COMBO_ENABLED = bool(_config.get('SKILL_COMBO_ENABLED', True))
    PRE_MACRO_FOCUS_ENABLED = bool(_config.get('PRE_MACRO_FOCUS_ENABLED', False))
    PRE_MACRO_FOCUS_DELAY = float(_config.get('PRE_MACRO_FOCUS_DELAY', 0.25))
    INPUT_BACKEND = _config.get('INPUT_BACKEND', 'interception')
    INPUT_DRY_RUN = bool(_config.get('INPUT_DRY_RUN', False))
    COMBO_PRIORITY = _config.get('COMBO_PRIORITY', None)
    STEALTH_ATTACK_MODE_ENABLED = bool(_config.get('STEALTH_ATTACK_MODE_ENABLED', True))
    ATTACK_MODE_WEIGHTS = _config.get('ATTACK_MODE_WEIGHTS', {})
    SINGLE_SKILL_POOL = _config.get('SINGLE_SKILL_POOL', [])
    SINGLE_SKILL_GLOBAL_COOLDOWN = float(_config.get('SINGLE_SKILL_GLOBAL_COOLDOWN', 1.5))
    COMBAT_USE_SKILLS = bool(_config.get('COMBAT_USE_SKILLS', True))
    AUTO_LOOT = bool(_config.get('AUTO_LOOT', True))
    SENTRY_MODE = bool(_config.get('SENTRY_MODE', False))
    FARMING_MODE = bool(_config.get('FARMING_MODE', False))
    SKIP_PRESTART_CHECKLIST = bool(_config.get('SKIP_PRESTART_CHECKLIST', False))
    ENABLE_ROAM = bool(_config.get('ENABLE_ROAM', True))
    LANGUAGE = _config.get('LANGUAGE', 'en')


_refresh_module_vars()


def save_config() -> None:
    """Write the current in-memory config back to JSON atomically.

    This replaces the JSON content (not appending) so programmatic updates
    will overwrite previous state.
    """
    try:
        text = json.dumps(_config, indent=2)
        _atomic_write(_CONFIG_PATH, text)
        logger.debug("skill_combo_config: config saved")
    except Exception as e:
        logger.error(f"Failed to save config JSON: {e}")


def update_config(updates: Dict[str, Any]) -> None:
    """Merge `updates` into the in-memory config and persist JSON.

    This performs a shallow merge for top-level keys. Callers should pass
    fully-formed values for nested structures if they want to replace them.
    """
    if not isinstance(updates, dict):
        raise TypeError('updates must be a dict')
    _config.update(updates)
    _refresh_module_vars()
    save_config()


def get_skill_cooldown(skill: str) -> float:
    skill_lower = skill.lower()
    return float(SKILL_COOLDOWNS.get(skill_lower, 10.0))


def get_randomized_delay(base_delay: float) -> float:
    variation = base_delay * DELAY_RANDOMIZATION
    return base_delay + random.uniform(-variation, variation)


def get_enabled_combo_sets() -> List[Dict[str, Any]]:
    enabled = [combo for combo in COMBO_SETS if combo.get('enabled', True)]
    if COMBO_PRIORITY is not None:
        try:
            ordered: List[Dict[str, Any]] = []
            for idx in COMBO_PRIORITY:
                if 0 <= idx < len(enabled):
                    ordered.append(enabled[idx])
            for combo in enabled:
                if combo not in ordered:
                    ordered.append(combo)
            return ordered
        except Exception as e:
            logger.warning(f"Invalid COMBO_PRIORITY, using default order: {e}")
    return enabled


def validate_combo_set(combo: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(combo, dict):
        return False, "Combo must be a dictionary"
    if 'skills' not in combo:
        return False, "Combo missing 'skills' field"
    if not isinstance(combo['skills'], list) or len(combo['skills']) == 0:
        return False, "Combo 'skills' must be a non-empty list"
    for skill in combo['skills']:
        if skill.lower() not in SKILL_COOLDOWNS:
            return False, f"Unknown skill keybind: {skill}"
    if 'cooldown' in combo and combo['cooldown'] < 0:
        return False, "Combo cooldown cannot be negative"
    if 'delay_between_skills' in combo and combo['delay_between_skills'] < 0:
        return False, "Delay between skills cannot be negative"
    if 'pre_focus' in combo and not isinstance(combo['pre_focus'], bool):
        return False, "Combo 'pre_focus' must be a boolean if specified"
    if 'pre_focus_delay' in combo and combo['pre_focus_delay'] < 0:
        return False, "Combo 'pre_focus_delay' cannot be negative"
    return True, ""


def parse_skill_keybind(skill: str) -> Tuple[Optional[str], str]:
    # Normalize and strip modifiers. Modifiers are not supported for skills anymore;
    # if present they will be ignored and the base key returned.
    skill_lower = skill.lower().strip()
    if skill_lower.startswith('alt+'):
        skill_lower = skill_lower.replace('alt+', '', 1)
    if skill_lower.startswith('ctrl+'):
        skill_lower = skill_lower.replace('ctrl+', '', 1)
    return None, skill_lower


def validate_configuration() -> bool:
    logger.info("Validating skill combo configuration...")
    errors: List[str] = []
    for skill, cooldown in SKILL_COOLDOWNS.items():
        if cooldown < 0:
            errors.append(f"Skill '{skill}' has negative cooldown: {cooldown}")
    for idx, combo in enumerate(COMBO_SETS):
        is_valid, err = validate_combo_set(combo)
        if not is_valid:
            errors.append(f"Combo set {idx} ('{combo.get('name','unnamed')}'): {err}")
    if errors:
        logger.error("Skill combo configuration errors:")
        for e in errors:
            logger.error(f"  - {e}")
        return False
    logger.success(f"✓ Skill combo configuration valid ({len(COMBO_SETS)} combo sets)")
    return True

