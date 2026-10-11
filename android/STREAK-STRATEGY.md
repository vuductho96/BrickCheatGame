# Streak strategy: improve clear timing while preserving the planned board

Confirmed rule: the first row/column clear starts a streak. Three consecutive placements without a clear end it. A clear resets the miss counter, including a clear on the third placement. A tray refill does not reset the counter.

The controller counts clears only after the released placement is verified against the observed board and remaining tray. Failed pickup/alignment is not a placement. The observed counters and board/tray signature persist across Auto stops and delayed refills. Unexplained board changes reset the estimate because manual moves and a new game cannot be reconstructed reliably from one frame. Starting mid-game tracks the observed portion of the run, not an asserted game multiplier.

The original solver first selects a baseline plan using its current-tray search, board geometry and sampled future-piece risk. The streak pass then checks at most six permutations of the baseline's three placements. It accepts a reordered path only if every placement is legal, all the same pieces are used, the resulting board is exactly the baseline board, and the number of cleared rows/columns is no smaller. Expected intermediate boards are recomputed, so release verification follows the actual selected order. Partial baseline plans are left unchanged.

Accepted orders reward clears and simultaneous clears inside the active streak, penalize its third missed placement, and prefer fewer pending misses when otherwise equivalent. The relative weights are search priorities, not Shopee's unknown point formula. Future pieces are sampled risk scenarios; they are not predictions of the actual next tray.

This preserves baseline placement feasibility and end-of-tray geometry, while improving opportunities to earn streak bonus through clear timing. It does not make the baseline invincible, guarantee a score, or guarantee a fixed next-tray distribution if Shopee adapts generation to score.

Earlier reward-first searches produced longer runs but worse survival on independent synthetic streams. They were rejected. The final implementation changes placement order within a baseline plan, rather than selecting a riskier end board for streak reward.

Run the benchmark with `-Mode order`. One baseline plan is computed per tray and replayed for both policies. The benchmark asserts equal end boards, equal placement counts and no loss of cleared lines at every tray, removing the confounding effect of two separately timed searches. Compare streak breaks and maximum streak lines. These are simulated observations, not measured Shopee points.

Validation: 24 synthetic games, seeds 4000–4007 per profile, capped at 90 trays, beam width 80 and a 150 ms baseline search budget. All board/placement/clear invariants passed. Total streak breaks fell from 106 to 55. Average maximum streak lines rose from 23.6 to 32.2 for common shapes, 21.0 to 27.0 for the transition profile, and 17.4 to 19.5 for unfamiliar shapes. Survival length and total cleared lines were identical per game. Raw results are in `tools/native-benchmark/order-holdout.csv`. The phone uses a wider 160-state beam and a 1500 ms budget; its point improvement remains unmeasured.
