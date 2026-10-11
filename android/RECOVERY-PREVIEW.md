# 1.0.12 preview: recover transient Auto failures

This APK is built for review. It has not been installed or tested on the user's phone. Keep the installed 1.0.11 app until installation is requested.

Previously any failed board read, gesture exception, unexpected post-drop board, or accessibility interruption stopped the Auto worker. The preview keeps the capture session alive and distinguishes an active worker waiting to recover from a user stop.

- Missing accessibility: wait for the service to reconnect; never enable it automatically.
- Unreadable board, empty tray, or no legal move: wait without touching the screen.
- Drag alignment/gesture failure: attempt the existing return-to-tray path when a stroke is still held; discard the whole plan, read a stable board, then plan again.
- Unexpected board after release: log the mismatch and discard the whole plan. Do not continue the unverified remaining moves.
- Repeated failures on the same state: wait 1, 2.5, 5, then 30 seconds between attempts. Successful verified moves or a changed observed state reset the delay.
- Before every drag: recheck the board/tray against the planned state and use freshly measured pickup bounds.
- Explicit Stop still stops the worker. Closing capture or Android revoking MediaProjection ends the session; Android requires the user to confirm a new sharing session. Recovery cannot restore that permission.

The button reads `Dừng Auto (đang chờ)` while recovering. Diagnostics record `retry`, `unreadable`, `no_move`, `planned`, `mismatch`, and `verified` in the local move log. Runtime failures on actual Samsung hardware remain to be validated after installation is authorized.

This is a reliability change, not a claim of predicting Shopee's future pieces or exceeding 17k points. Candidate scoring changes did not improve all synthetic distributions consistently and were not selected.
