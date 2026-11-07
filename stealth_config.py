"""
STEALTH CONFIGURATION FOR CRYENGINE ANTI-CHEAT EVASION

CryEngine has AGGRESSIVE anti-cheat that detects:
- Too-fast action timing (instant responses)
- Perfect mouse movements (straight lines)
- Consistent timing patterns
- High detection polling rates

This config makes the bot look like a slow, cautious human player.
"""
import random

# ============================================================================
# CRITICAL: ULTRA-SLOW TIMING TO AVOID CRYENGINE DETECTION
# ============================================================================

# Detection loop FPS (how often we check for mobs/objects)
# MUST BE LOW - CryEngine detects high polling rates
DETECTION_FPS = 10

# Startup delay before ANY automation begins (seconds)
# Gives CryEngine time to see "player is idle after loading"
STARTUP_DELAY_MIN = 0.0
STARTUP_DELAY_MAX = 15.0

# Warmup period - first N actions have EXTRA delays
# This simulates a human "getting oriented" after starting
WARMUP_ACTIONS = 10
WARMUP_EXTRA_DELAY_MIN = 2.0  # Extra seconds per action
WARMUP_EXTRA_DELAY_MAX = 5.0

# ============================================================================
# ACTION TIMING - HUMAN-LIKE DELAYS
# ============================================================================

# Base cooldown between ANY actions (seconds)
# CryEngine WILL detect if actions are too frequent
ACTION_COOLDOWN_MIN = 0.8
ACTION_COOLDOWN_MAX = 2.0

# Additional delay after clicking a mob (seconds)
POST_CLICK_DELAY_MIN = 0.5
POST_CLICK_DELAY_MAX = 1.2

# Delay after pressing movement keys (seconds)
POST_MOVEMENT_DELAY_MIN = 0.3
POST_MOVEMENT_DELAY_MAX = 0.8

# Foreground-only input safety (never send input unless game is focused)
FOREGROUND_ONLY = True

# Key tap down-time and inter-press interval randomization (seconds)
KEY_TAP_DOWN_MIN = 0.02
KEY_TAP_DOWN_MAX = 0.07
KEY_TAP_INTERVAL_MIN = 0.06
KEY_TAP_INTERVAL_MAX = 0.18

# ============================================================================
# MOUSE MOVEMENT - SMOOTH & HUMAN-LIKE
# ============================================================================

# Mouse movement duration (seconds)
MOUSE_MOVE_DURATION_MIN = 0.2
MOUSE_MOVE_DURATION_MAX = 0.5

# Mouse jitter/randomization (pixels)
# Adds random offset to click positions
MOUSE_JITTER_X = 15
MOUSE_JITTER_Y = 15

# Target click position on mob (percentage down from top of the box)
# Clicking in the LOWER PART of the detection box (not center, not below)
MOB_CLICK_Y_MIN = 0.70  # 70% down from top of box (lower part)
MOB_CLICK_Y_MAX = 0.90  # 90% down from top of box (near bottom edge)

# Mouse micro-jitter before click (pixels)
MICRO_JITTER_BEFORE_CLICK = 3  # move within ±3px then settle

# Targeting/attack interval and button hold press times (seconds)
DOUBLE_CLICK_INTERVAL_MIN = 0.06
DOUBLE_CLICK_INTERVAL_MAX = 0.22
MOUSE_BUTTON_DOWN_MIN = 0.018
MOUSE_BUTTON_DOWN_MAX = 0.055
PRE_CLICK_PAUSE_MIN = 0.020
PRE_CLICK_PAUSE_MAX = 0.080

# When avoiding detection, we can do key-based targeting then attack (Tab + R/T)
# Primary attack key used for click-then-key strategy
PRIMARY_ATTACK_KEY = '1'

# Delay between click and attack key press (seconds)
CLICK_KEY_DELAY_MIN = 0.1
CLICK_KEY_DELAY_MAX = 0.3

# Strategy weights for attack click when "standard" attacking a mob
# Must be >= 0; will be normalized at runtime.
STRATEGY_WEIGHT_TWO_SINGLE = 0.0
STRATEGY_WEIGHT_CLICK_THEN_KEY = 0.85
STRATEGY_WEIGHT_KEY_THEN_CLICK = 0.05
STRATEGY_WEIGHT_RIGHT_CLICK = 0.1

# Hard block sequential attack patterns (avoid mechanical repeated inputs)
AVOID_SEQUENTIAL_CLICKS = True

# ============================================================================
# IDLE SIMULATION - CRITICAL FOR STEALTH
# ============================================================================

# Periodic "thinking" pauses where bot does nothing
# This simulates human decision-making
IDLE_CHECK_INTERVAL = 30.0
IDLE_PROBABILITY = 0.35
IDLE_DURATION_MIN = 4.0
IDLE_DURATION_MAX = 12.0

# ============================================================================
# MOVEMENT KEY HOLD DURATION
# ============================================================================

# How long to hold W/A/S/D keys (seconds)
KEY_HOLD_DURATION_MIN = 0.4
KEY_HOLD_DURATION_MAX = 1.2

# Randomization for key hold (percentage)
# Adds ±X% variation to hold duration
KEY_HOLD_VARIATION = 0.25  # ±25%

# Turn duration for 70-degree turns (approximate)
# Depends on game sensitivity, but ~1-2s is typical for 70 degrees
TURN_70_DEGREES_MIN = 1.0  # seconds
TURN_70_DEGREES_MAX = 1.8  # seconds

# ============================================================================
# MOUSE DRAGGING - SMOOTH MOVEMENT (NO TELEPORT)
# ============================================================================

# Always use smooth mouse dragging (Bezier curves)
MOUSE_DRAG_ENABLED = True
MOUSE_DRAG_CURVE = 0.15  # Bezier curve intensity (0-1, higher = more curved)
MOUSE_DRAG_MIN_DURATION = 0.15  # Minimum drag time (seconds)
MOUSE_DRAG_MAX_DURATION = 0.40  # Maximum drag time (seconds)

# ============================================================================
# MOVEMENT MACRO - RANDOMIZED PATTERNS
# ============================================================================

# Movement pattern types
MOVEMENT_PATTERNS = [
    "forward",           # Just move forward
    "forward_zigzag",    # Forward with slight left/right
    "circle_left",       # Circle strafe left
    "circle_right",      # Circle strafe right
    "backup_turn",       # Backup and turn
    "strafe_left",       # Strafe left
    "strafe_right",      # Strafe right
]

# Movement pattern duration (seconds)
MOVEMENT_PATTERN_MIN = 1.5
MOVEMENT_PATTERN_MAX = 4.0

# Chance to change movement pattern (0-1)
MOVEMENT_PATTERN_CHANGE_CHANCE = 0.25  # 25% chance per action

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_action_delay():
    """Get random delay between actions (seconds)."""
    return random.uniform(ACTION_COOLDOWN_MIN, ACTION_COOLDOWN_MAX)

def get_post_click_delay():
    """Get random delay after clicking (seconds)."""
    return random.uniform(POST_CLICK_DELAY_MIN, POST_CLICK_DELAY_MAX)

def get_post_movement_delay():
    """Get random delay after movement (seconds)."""
    return random.uniform(POST_MOVEMENT_DELAY_MIN, POST_MOVEMENT_DELAY_MAX)

def get_mouse_move_duration():
    """Get random mouse movement duration (seconds)."""
    return random.uniform(MOUSE_MOVE_DURATION_MIN, MOUSE_MOVE_DURATION_MAX)

def get_mouse_jitter():
    """Get random mouse position jitter (dx, dy in pixels)."""
    dx = random.randint(-MOUSE_JITTER_X, MOUSE_JITTER_X)
    dy = random.randint(-MOUSE_JITTER_Y, MOUSE_JITTER_Y)
    return dx, dy

def get_micro_jitter():
    """Get tiny mouse jitter for pre-click micro-movement (dx, dy in px)."""
    j = MICRO_JITTER_BEFORE_CLICK
    return random.randint(-j, j), random.randint(-j, j)

def get_mob_click_offset(mob_height):
    """Get Y offset for clicking on mob (pixels from top of mob box)."""
    ratio = random.uniform(MOB_CLICK_Y_MIN, MOB_CLICK_Y_MAX)
    return int(mob_height * ratio)

def should_idle():
    """Check if bot should enter idle state (returns bool)."""
    return random.random() < IDLE_PROBABILITY

def get_idle_duration():
    """Get random idle duration (seconds)."""
    return random.uniform(IDLE_DURATION_MIN, IDLE_DURATION_MAX)

def get_key_hold_duration():
    """Get random key hold duration with variation (seconds)."""
    base = random.uniform(KEY_HOLD_DURATION_MIN, KEY_HOLD_DURATION_MAX)
    variation = base * KEY_HOLD_VARIATION * random.uniform(-1, 1)
    return max(0.1, base + variation)

def get_key_tap_down_time():
    """Randomized down-time for a tap key (seconds)."""
    return random.uniform(KEY_TAP_DOWN_MIN, KEY_TAP_DOWN_MAX)

def get_key_tap_interval():
    """Randomized interval between repeated taps (seconds)."""
    return random.uniform(KEY_TAP_INTERVAL_MIN, KEY_TAP_INTERVAL_MAX)

def get_startup_delay():
    """Get random startup delay (seconds)."""
    return random.uniform(STARTUP_DELAY_MIN, STARTUP_DELAY_MAX)

def get_warmup_delay():
    """Get extra delay for warmup actions (seconds)."""
    return random.uniform(WARMUP_EXTRA_DELAY_MIN, WARMUP_EXTRA_DELAY_MAX)

def get_turn_70_degrees_duration():
    """Get duration to turn approximately 70 degrees (seconds)."""
    return random.uniform(TURN_70_DEGREES_MIN, TURN_70_DEGREES_MAX)

def get_mouse_drag_duration():
    """Get random mouse drag duration (seconds)."""
    return random.uniform(MOUSE_DRAG_MIN_DURATION, MOUSE_DRAG_MAX_DURATION)

def get_movement_pattern():
    """Get random movement pattern."""
    return random.choice(MOVEMENT_PATTERNS)

def get_movement_pattern_duration():
    """Get duration for movement pattern (seconds)."""
    return random.uniform(MOVEMENT_PATTERN_MIN, MOVEMENT_PATTERN_MAX)

def should_change_movement_pattern():
    """Check if movement pattern should change."""
    return random.random() < MOVEMENT_PATTERN_CHANGE_CHANCE

def get_double_click_interval():
    """Interval between first and second click (seconds)."""
    return random.uniform(DOUBLE_CLICK_INTERVAL_MIN, DOUBLE_CLICK_INTERVAL_MAX)

def get_mouse_button_down_time():
    """How long to keep mouse button held down (seconds)."""
    return random.uniform(MOUSE_BUTTON_DOWN_MIN, MOUSE_BUTTON_DOWN_MAX)

def get_pre_click_pause():
    """Short pause before a click to mimic human hesitation (seconds)."""
    return random.uniform(PRE_CLICK_PAUSE_MIN, PRE_CLICK_PAUSE_MAX)

def get_click_then_key_delay():
    """Delay between click and primary attack key press (seconds)."""
    return random.uniform(CLICK_KEY_DELAY_MIN, CLICK_KEY_DELAY_MAX)

def choose_attack_click_strategy():
    """Choose which strategy to use for a standard 'attack' click.

    Returns one of: 'two_single', 'click_then_key', 'key_then_click', 'right_click'
    """
    w_two = max(0.0, STRATEGY_WEIGHT_TWO_SINGLE)
    w_ck = max(0.0, STRATEGY_WEIGHT_CLICK_THEN_KEY)
    w_ktc = max(0.0, STRATEGY_WEIGHT_KEY_THEN_CLICK)
    w_right = max(0.0, STRATEGY_WEIGHT_RIGHT_CLICK)
    total = w_two + w_ck + w_ktc + w_right
    # fallback to sensible defaults if all zero
    if total <= 0:
        w_two, w_ck, w_ktc, w_right = 0.0, 0.8, 0.1, 0.1
        total = 1.0
    r = random.random() * total
    if r < w_two:
        return 'two_single'
    r -= w_two
    if r < w_ck:
        return 'click_then_key'
    r -= w_ck
    if r < w_ktc:
        return 'key_then_click'
    return 'right_click'
