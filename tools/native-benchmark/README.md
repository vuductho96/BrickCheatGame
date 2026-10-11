# Paired native solver benchmark

Run from the repository root using JDK 17:

```powershell
./tools/native-benchmark/run.ps1 -JavaHome $env:JAVA_HOME -Seeds 12 -Start 1000 -Trays 90 -BudgetMs 100 -Output native-benchmark.csv
```

Each seed produces one complete tray stream before either solver plays. Both variants see the same stream, have the same search budget, and may use only previously observed trays as history. Their execution order alternates. Every returned move is replayed and checked for collisions and reused slots.

`Legacy*` files snapshot this project's native 1.0.11 solver, not a third-party implementation. The comparison uses 80-wide search; the app uses 160-wide search and a 1500 ms budget. Three synthetic distributions cover common shapes, a transition to harder shapes, and unfamiliar shapes from the start. They do not reproduce Shopee's generator, scoring, difficulty thresholds or Android gesture behavior.

Report moves and cleared lines separately by profile. Cap hits are censored results, not eventual survival. Wall-clock budgets and JVM warm-up introduce noise; tune with one seed set and validate on independent seeds before accepting a strategy. These numbers cannot establish a phone score improvement.

Exploration of reserving large spaces, risk-weighted rollouts, historical shape coverage and future-clear rewards produced inconsistent results across profiles. Those heuristic changes were rejected. The preview retains the existing scoring policy and only caches shape anchors and computes empty rectangle counts with bit operations, with exhaustive reference checks on random boards.

Research references (ideas only; no external code or weights incorporated):

- https://github.com/sher-shen/block-blast-luck-vs-skill — fitted value iteration and value-guided rollouts under that project's game distribution.
- https://github.com/Hanbiike/block-blast-monte-carlo-ai — sampling future pieces for block puzzle search.
