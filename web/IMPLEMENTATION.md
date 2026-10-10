# HTML companion design

Reference: reference-concept.png, generated full primary screen, native 1586×992.
Source game: captures/trial-current.png (actual S23+ 1080×2340).

Tokens: pale #f5f8fb chrome; text #172d3f; orange #fa5317 actions; dark teal #063d49 canvas; green #02d39b board frame; Segoe UI.
Composition: open header, 1.9:1 desktop game/sidebar columns, square 8×8 board, three fixed tray slots, next-move heading and three ranked rows, live phone preview, bottom status strip.
Interactions: pointer drag with grabbed-cell anchor; highlight valid/invalid drop; only valid user drops submit input; refresh before input; screenshots after input; phone board authoritative; stale results do not submit input.

Intentional adaptations: code-native CSS block bevels represent the real phone's colors and geometry rather than static sprites (input mapping needs each cell); full uncropped phone screenshot is shown; dynamic actual hints replace concept example values; footer includes actionable capture/mismatch states; smaller laptop and mobile stack responsively.

Backend: Python HTTP bridge bound to 127.0.0.1:8765; ADB screenshot + user-triggered swipe/tap; local session token and same-origin check on input endpoints. Fixed S23+ calibration expects 1080×2340; screenshot checks block game-over/covered/animation states.
No network-hosted frontend assets or AI API calls at runtime.

## Fidelity/interaction ledger, final pass

Both concept and latest Edge screenshot inspected with view_image at native 1586×992; mobile checked at 390×844.

1. Copy: header Xếp Gạch, Chụp lại, Gợi ý nước đi, Màn hình điện thoại and footer preserved. Actual plan locations intentionally replace example coordinates. Added phone-click help and search time because these are functional controls.
2. Layout: main board left, suggestions/phone right, three fixed tray slots, footer all fit native viewport after reducing canvas height and phone panel height. Mobile uses a single column with no horizontal overflow.
3. Color: pale #f5f8fb chrome, orange actions/selected option, dark teal canvas and bright green board frame match the concept.
4. Typography: Segoe UI hierarchy reviewed in header, hint, plan rows, image caption and controls; header and hint sizes increased in the final pass.
5. Assets/geometry: exact current occupied cells and each piece shape from the S23+ reference. Beveled blocks intentionally use code-native CSS to preserve per-cell colors/input hit testing. Full actual phone image replaces the concept's cropped phone.
6. Interaction: invalid pointer drop generates no POST; valid pointer drop submits correct piece/row/column/grab anchor, removes the used slot after verified response; no app console/page errors. Input response was mocked in browser QA; live gesture validation is still pending phone reconnection.
7. Backend: 31 pytest checks passed including real screenshot recognition, blocked old/invalid states, mapped input coordinates and post-move verification.
Browser plugin unavailable; Playwright with installed Edge used. QA screenshots stored outside source tree in Codex visualizations.


LIVE update: main panel is the actual phone video on canvas, with persistent WebSocket touch control. Desktop/mobile verified; real placement confirmed (score 220 to 240). Measured visual response 239ms in one trial. Smaller encoded stream preserves geometry and avoids decode backlog; simulator is a read-only hint preview.


Auto Local: explicit start/stop button, three actual beam/time budgets, local-only OpenCV and bitboard solver. Active control stops on manual pointer-down or Escape. User requested no further phone trials; final checks are offline tests and passive browser UI only.


Alignment/sync repair: snapped gray drop footprint is the position authority; lifted sprite position is no longer enough. Stable observations publish independently of Auto with frame/time identity. In-flight plans are hidden, mode budgets shared, and recoverable placement errors replan. QA: 52 tests, including supplied screenshot and fake phone; passive browser observation age 0.16s and zero input requests.

2026-10-10 superseding execution visibility and alignment: moving state still suppresses fresh `plans`, but exposes a separate immutable `execution` bound to the observed state ID. UI displays the locked target and sequential moves during Auto, and compares expected/actual occupancy after release via `last_check`. Real-phone testing was explicitly authorized again by the user. One recorded single-cell failure had the correct gray footprint but a displaced lifted sprite and landed one row up/one column right. Release now requires BOTH sprite alignment and footprint confirmation on fresh frames, with no learned sprite offset exemption. A clipped Z at the left edge is moved inward for observation before correction. Offline fake previews now include visible lifted sprites and the fake video advances during stationary holds. Local diagnostics are gated to actual ADB bridges so fake tests do not overwrite phone evidence.
