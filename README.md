[![make.fun · tiny-chess-01](https://make.fun/badge/tiny-chess-01.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![rank](https://make.fun/badge/tiny-chess-01/Wahyupurnomoaji21/tiny-chess-01-v10/rank.svg)](https://make.fun/bounty/tiny-chess-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)
[![reward](https://make.fun/badge/tiny-chess-01/Wahyupurnomoaji21/tiny-chess-01-v10/reward.svg)](https://make.fun/bounty/tiny-chess-01?utm_source=github&utm_medium=readme&utm_campaign=tiny-chess-01)

[Tiny Chess 01 bounty on make.fun](https://make.fun/bounty/tiny-chess-01)

# Tiny Chess Engine v10

From-scratch 0x88 engine: PVS + transposition table + null-move pruning + LMR
+ quiescence + root repetition filter; material + piece-square eval with
pawn-shield king safety. Fixed 60,000-node budget per move (deterministic,
no clock). main.py is the minified + LZMA-packed engine.

## v10 vs v2 (best official entry so far: Elo 1650, rank 1780)

v2 is the base — v5–v9 all rebuilt/redesigned v4's search and all scored
below v4 in practice. v10 changes only two targeted things on v2:

1. **Check extension** in the main search (+1 ply when the side to move is
   in check, depth < 9). The only single change with a positive recorded
   measurement (+315 Elo in v7's config experiment); v7/v8/v9 mixed it with
   a QG cap, MTD(f) and tapered eval, so v10 tests it cleanly on v2's base.
2. **Eval-conditional root repetition filter.** v6 diagnosed 4 won games
   drawn by threefold because the engine repeated into the 2nd occurrence
   while ahead; v2's filter only blocks the 3rd occurrence, and blocks it
   unconditionally (bad when behind, where a draw is good). v10: ahead
   (> +80cp) drops any repeating move; behind (< −80cp) drops nothing;
   otherwise v2's rule.

Unchanged from v2: gentle pawn-advancement table (max 40), null-move
reduction R=2/3, uncapped quiescence, 60,000-node budget.

## Practice trials (kit, 3 trials x 6 games, 60k nodes)

See `~/workspace/makefun/tiny-chess-01-dev/trials-v10-trial{0,1,2}.log`.

- Trial 0: Elo **1451** (3W/2D/1L, spare_plies 320)
- Trial 1: Elo **1364** (3W/1D/2L, spare_plies 322)
- Trial 2: Elo **2112** (6W/0D/0L, spare_plies 561) — first perfect 6-0 trial
  of any version in this family
- **Mean: 1642,3** — below the 1650 submit target, above v4 official 1545.
  Best practice mean of any version (v2 1490, v4 1521, v6 1519).

Gate: submit only if practice mean >= 1650 (target) and > v4 official 1545.
Verdict: BORDERLINE — mean 1642 misses the 1650 target by 8 points but
beats v4 official 1545; submit decision left to the main session.
