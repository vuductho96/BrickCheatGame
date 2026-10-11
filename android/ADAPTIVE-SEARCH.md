# Adaptive search (1.0.16 preview)

The phone allocates computation from the observed board and actual tray rather
than using a fixed 160-state / 1.5-second search everywhere.

| Pressure | Current-tray beam | Time budget | Final boards | Future scenarios | Future beam | Fallback node cap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Normal | 160 | 1.5 s | 16 | 16 | 6 | 50,000 |
| Careful | 320 | 3 s | 24 | 24 | 10 | 100,000 |
| Critical | 640 | 5 s | 32 | 32 | 16 | 200,000 |

Critical applies with 20 or fewer free cells, or when any current piece has at
most two legal anchors (including zero: another piece may clear space first).
Careful applies with 32 or fewer free cells, at most six anchors for any piece,
or 40 or fewer free cells with no empty 3-by-3 rectangle. Otherwise use Normal.
These are bounded search settings, not guaranteed waiting times or predictions.

Depth remains the actual current tray plus two sampled hypothetical future trays.
Increasing breadth tests more placements, piece orders, end boards and risk
scenarios. It does not pretend to know future generated pieces. Existing scoring
rewards actual cleared lines and free space, penalizes isolated holes, and tests
future placement survival. Streak ordering still requires the same final board
and no loss of cleared lines; no new aggressive bonus weights were introduced.
Simultaneous row/column removal uses the union of occupied cells, so intersections
are not counted twice as freed space.

Immediately before each gesture the controller rechecks board/tray stability.
Changed state invalidates the plan even if computation took five seconds. The
1.0.15 failed-action memory remains active in wider search and streak reordering.
Logs record search level, configured budget/beam and completed scenario count.

Validation includes adaptive trigger fixtures, a legal three-piece replay using
critical search with a forbidden first action, row/column union removal, and the
existing planner, streak, lifecycle and failed-drag regression suite. Real Shopee
score gains and S23+ planning latency have not yet been measured for this build.

This version is installed directly from the internal Gradle build output; no
separate downloadable APK is exported. Enable Bric accessibility, share one
application (Shopee) or the entire screen, then use Auto. Updating the app closes
the previous capture session; Android asks for sharing consent again.
