"""Quick smoke test for input functions.

This tests the high-level input API (tap_key, hold_key, move_mouse_to, click_at)
to ensure the implementation executes without raising exceptions. This is a
local smoke test and not a functional verification with a running game.
"""

import time
from input_controller import tap_key, hold_key, move_mouse_to, click_at, double_click_at


def run_all():
    print("=== User-mode input smoke test ===")
    # Key taps
    print("Tap R, T, F (3 quick presses)")
    for k in ('r', 't', 'f'):
        ok = tap_key(k)
        print(f"tap_key({k}) -> {ok}")
        time.sleep(0.1)

    # Hold a key briefly
    print("Hold key 'r' for 0.25s")
    ok = hold_key('r', 0.25)
    print(f"hold_key('r', 0.25) -> {ok}")

    # Mouse move and clicks
    print("Move cursor by small delta then click")
    # Use small moves relative to current pos by grabbing current pos and adding offsets via move_mouse_to
    move_ok = move_mouse_to(200, 200, duration=0.12)
    print(f"move_mouse_to(200,200) -> {move_ok}")
    click_ok = click_at(200, 200)
    print(f"click_at(200,200) -> {click_ok}")

    print("Double click test")
    dbl = double_click_at(200, 200)
    print(f"double_click_at -> {dbl}")

    print("Done — calls executed. Inspect system to confirm expected input behavior.")


if __name__ == '__main__':
    run_all()
