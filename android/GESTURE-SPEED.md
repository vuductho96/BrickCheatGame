# Gesture speed (1.0.17 preview)

The app defaults to 2x gesture timing. The speed button toggles between 1x and 2x
and persists the choice. A change applies to the next drag, not an active stroke.

At 2x, pickup, move, release and post-move settling durations are halved. Capture
frequency stays unchanged. Each alignment iteration still waits for a newer
captured image; release still requires two matching target footprints. Post-release
board verification keeps the original stability delay and checks the expected
board and remaining tray. Pre-drag stability polling is faster.

An unsuccessful drag retries at normal speed with a different pickup/approach.
Returning a held piece to the tray also uses normal speed. Failed-action exclusions
and adaptive 1.5/3/5-second planning budgets remain unchanged.

The 2x label describes gesture timing, not measured total moves per minute. Screen
recognition, animations, Android scheduling and crowded-board search still take
time. No new real-device throughput or placement-accuracy claim is made before
testing this installed version with a user-confirmed sharing session.

Installed directly from Gradle's build output; no separate APK is exported.
