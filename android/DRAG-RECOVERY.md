# Drag recovery (1.0.15 preview)

Previously, an unchanged board and tray produced the same deterministic plan and
the same pickup point after every failed drag. Backoff changed only the delay.

Each physical action now has a key containing the observed board/tray signature,
physical tray slot, normalized shape, target row, and target column. On a stable
unchanged result, the next attempt selects a different occupied pickup cell and
approach point. After three unsuccessful strategies that action is excluded from
the first move of beam search, exact fallback search, and streak reordering.
Later moves on changed boards remain legal. If no executable action remains,
Auto waits for the board to change without replaying the excluded gesture.

A pending gesture must be reconciled against a readable stable state before
another gesture starts. Unreadable post-release frames keep the fresh-frame
requirement. A changed board/tray discards the old plan and scopes failure memory
to the newly observed state, so a consumed piece is not replayed from the old plan.
Returning a held piece to its tray also requires a frame newer than the pre-UP
image. Successful placements still require the expected board and remaining tray.

Failure memory survives Auto toggles while the app process remains alive; it is
cleared when the observed board/tray changes. It does not persist through app
process death. Logs include action identity, physical slot, shape, and strategy.

Validation: unit regressions cover bounded attempts, unchanged-state polling,
board/tray changes, independent actions, first-move exclusions in search and
streak ordering, and subsequent unrestricted search. Android build and lint pass.
Real-device drag accuracy still requires a new sharing session after APK install;
unit tests do not establish improved scores or perfect placement.
