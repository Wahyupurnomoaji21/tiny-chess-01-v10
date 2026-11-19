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

Gate: submit only if practice mean >= 1650 (target) and > v4 official 1545.
