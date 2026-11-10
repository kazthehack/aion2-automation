# Development handoff for the next Codex agent

## Confirm the workspace first

The intended repository is:

`C:\Users\User\Desktop\aion2-automation`

Remote: `https://github.com/kazthehack/aion2-automation.git`

Branch last observed: `main`, tracking `origin/main`, with a clean working tree.

The previous chat remained attached to the old folder even after the project folder was changed:

`C:\Users\User\Downloads\AION2_AutoSim-main\AION2_AutoSim-main`

Before editing, check the actual working directory, Git root, status, and remote. Do not assume changing a project setting updated an existing chat. Do not continue editing the Downloads copy or overwrite the Desktop repository with it. Read the current repository and any applicable AGENTS.md; this handoff describes prior intent, not proof of current implementation.

## How to collaborate with this user

- The user develops through short, practical iterations and live observations. Requests often contain typos; interpret their intended behavior using the conversation and code.
- A request to add or fix something means implement it, not merely propose it. Avoid repeated confirmation questions when the scope is clear.
- Keep updates and final responses concise. Explain the resulting behavior first, then relevant testing and limitations.
- Ask only when an ambiguity materially changes behavior. For example, the final Sentry Mode requirement superseded earlier interpretations: rotate only when there is no target, while attacking in place.
- The user becomes frustrated by repeated speculative fixes that circle back to earlier bugs. Trace the actual state transition or input path before changing another threshold.
- Treat new observations as refinements to the existing system. Preserve the other modes, stop controls, and input protection.
- Do not silently change several unrelated behaviors to fix one complaint. Distinguish camera speed, sweep amount, scan frequency, and pauses between sweeps.
- For a missing recognition, distinguish model output, filtering, HUD recognition, OCR parsing, cached values, and displayed logs. These are different failure points.
- Never describe mocked tests as live game verification. State what was actually tested. The user normally needs to restart the application after source changes.

## Product behavior to preserve

### Inputs and combat

- The shared attack sequence is `R -> T -> 1 -> 2`, with approximately 150 ms between keys and a 200 ms pause between repeated sequences. Check current code for the exact values.
- Basic attacks run in a dedicated worker so model inference does not determine their cadence. Skill combos execute in the same combat worker to avoid interleaving combat inputs.
- Do not accidentally replace actual key presses with assignments such as `atk = 'r'`. This previously caused R/T/1 to be overwritten without being sent.
- Alt+Shift+C is a global stop shortcut. Stop must cancel ongoing sequences and release held keys and mouse buttons, not just prevent the next planner call.
- Cancellation must also work during delays, movement, and camera turns. Key-up and mouse-up remain permitted after cancellation or focus loss.

### Target selection and movement

- A model box labelled `monster` is a candidate, not proof that the game selected a target.
- The bundled model was inspected and had only the `monster` class. It does not itself provide HP-bar detection.
- Selected targets are recognized separately from the target HUD/HP bar and paired world-space arrow markers. Red `< >` markers indicate engaged targets; references also exist for the blue marker.
- A confirmed selected target suppresses Tab and search rotation. Brief missed observations retain the target lock; the prior loss rule required at least three missing observations spanning one second.
- A selected target does not require a YOLO bounding box. Its arrow position supplies steering direction. Never steer toward an unrelated large monster box while another target is selected.
- With no confirmed target, the latest requested behavior is one Tab followed by one bounded `R/T/1/2` attempt immediately, then time for HUD confirmation. Previously, waiting for a YOLO box after Tab caused repeated target switching before attacks began.
- Do not create an unlimited empty-screen attack loop. Unconfirmed attempts must return to rotation/rechecking. Previously, visible but unconfirmed boxes could suppress rotation indefinitely; attempts were bounded to two before rotating.
- Search rotation does not walk forward. Approach movement is reserved for a confirmed target.
- Approach holds W continuously and steers with A/D based on the selected arrow's horizontal position. Use a center tolerance/hysteresis so small position changes do not chatter between keys.
- The requested distance band is 19–20 metres: stop approaching at 19 m and resume beyond 20 m. Keep this hysteresis.
- Approach has a three-second limit because the older box-height threshold caused indefinite W holds. Verify the current fallback after that limit rather than extending the hold arbitrarily.
- An HP bar with unreadable distance and no direction should not authorize blind walking. A visible world marker may provide a bounded direction-based approach while distance is unavailable.

### Dashboard modes

- Auto loot: checked by default. Checked means the game handles loot, so skip the entire F-key loot branch and its cooldown. Unchecked restores the short manual-loot branch.
- Farming Mode: only F approximately once per second. No combat, movement, targeting, or rotation. Takes priority over Sentry Mode.
- Sentry Mode (updated after live reports of game auto-approach): acquire using Tab, never an attack. No W/A/D. Require fresh distance OCR of 15 m or less before combat; recheck before each basic attack key and before a combo. Ignore OCR captured before the acquisition Tab and readings older than 0.5 seconds. Clear targets beyond 15 m with Escape; unreadable/stale distance times out after one second and also clears. Suppress attacks while the rejected HUD lingers, then pause acquisition/attacks for 1.5 seconds after it disappears while search rotation continues. Stop rotation for a selected, non-rejected target. This supersedes the earlier continuous empty-screen attacking/no-Tab requirement. Live verification of the revised selection path is still needed.
- Live logs belong on the dashboard after Simulate mode and before Start/Stop buttons. The separate Logs tab was removed.
- Main window opens normally, not maximized. The initial checklist has a persisted "Don't show this again" choice saved only on acceptance.
- Startup selects the AION2 window when available. Refresh preserves an existing valid user selection.

## Recognition and OCR

- Monster confidence threshold was 0.25. A monster box whose center lies in the central 20% of window width and height is deliberately excluded to reduce player-character false positives. This also hides real monsters in that region; do not mistake it for a model failure.
- Model inference used image size 640. Small/distant enemies and unfamiliar appearances can still be missed.
- `target_hud.py` recognizes HUD/marker references from `assets`. References were derived from user screenshots, so different layouts/scales still need real-image verification.
- HP/marker checks run independently of YOLO inference. Distance OCR runs separately so a slow OCR request does not block target recognition.
- Distance uses a local Windows OCR PowerShell worker (`target_hud_ocr.ps1`); no external OCR service is required.
- Keep the OCR reading's original timestamp separate from the latest visual observation. Republish of a new visual frame must not refresh an old distance.
- An OCR request timeout was added so a stalled worker can terminate and restart instead of blocking forever.
- The dashboard previously logged only transitions between "near" and "far", making 22 m appear stuck while other far values were read. Log actual distance changes and report unavailable readings clearly.

## Input boundaries and verification fail-safe

- Automation must not type into desktop applications or steal focus repeatedly. Block new input while the selected game is not foreground or modifier keys are held; this prevents automated Tab becoming Alt+Tab.
- Camera sweeps recenter the cursor inside the game client before right-button down and keep relative movement inside the client area. Correct Interception relative-move flags are `0`, not the mouse-filter mask `0x1000`.
- `SetCursorPos` belongs to `win32api`, not `win32gui`. A mock once invented the missing API and hid a production error. Verify real API availability before mocking it.
- The user requested a Daeva Verification fail-safe to prevent further desktop input. It matches only the dialog's fixed title/instruction text, never the challenge characters.
- First strong match stops all automated input. A second match confirms shutdown. It closes only the selected AION2 window's process, verified by executable name, HWND-to-PID mapping, and process creation time. If identity cannot be verified, stay stopped and kill nothing.
- Do not solve, submit, refresh, or interact with the verification challenge, and do not resume automatically after the fail-safe.

## Implementation and verification habits

- Main files: `action_planner.py` (workers/state decisions), `detection.py` (capture/model coordination and dashboard feedback), `target_hud.py` (visual/OCR workers), `input_controller.py` (Windows/Interception boundaries), `main.py` (Qt UI), `skill_combo_config.py` and JSON (persisted settings), `verification_guard.py` (stop/close fail-safe).
- Use persisted JSON configuration through its update API. Avoid independently changing module globals and JSON into contradictory states.
- Give each worker its own cancellation event. Prevent duplicate workers, serialize handoff of held input, and release keys/buttons in `finally` blocks.
- Test the actual regression: no-box selected targets, target flicker, no-target search, immediate post-Tab attacks, Sentry/Farming priority, cancellation, foreground/modifier guards, and mouse release.
- All automated tests must simulate game input and process termination. Never kill the live game, move the desktop cursor, or send real game inputs merely to run a test suite.
- Native API availability and screenshot recognition can be tested separately without actuating input. Headless Qt checks were used for widget order and feedback.
- Test command: `python -m unittest discover -s tests -p "test_*.py"`.
- The working Python executable previously found was `C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe`; the bare `python` launcher was inaccessible. Verify the current environment.
- Some source files have a UTF-8 BOM; use `utf-8-sig` when manually reading them for syntax checks.
- The last reported suite before this handoff passed 60 tests in the old Downloads copy. Do not claim that result for the Desktop repository without running its current tests.
- Git initialization, an existing remote, or an intent to push is not permission to publish every later change. Inspect the working tree and follow the user's current request before committing/pushing.
