# Tiny chess engine v10: v2's proven search + two targeted fixes.
# 0x88 board, incremental eval, PVS + TT + null-move + LMR + quiescence,
# fixed node budget per move (deterministic, no clock, no randomness).
# v10 vs v2 (the best official entry, Elo 1650): (1) check extension in the
# main search (+1 ply when in check, depth < 9) -- the only single change
# with a positive recorded measurement (+315 Elo in v7's config experiment;
# v7/v8/v9 mixed it with a QG cap, MTD(f) and tapered eval, so v10 tests it
# cleanly on v2's base). (2) Eval-conditional root repetition filter:
# when ahead (> +80cp) drop any move repeating a position (v6 diagnosed 4
# won games drawn by threefold via 2nd occurrence); when behind (< -80cp)
# drop nothing (a repetition draw is good); otherwise v2's rule (drop the
# 3rd occurrence). Pawn table, null-move R, uncapped quiescence and the
# 60,000-node budget are v2's, unchanged.
import json, os, random, sys, urllib.request

VAL = [0, 100, 320, 330, 500, 900, 0]
ADV = [0, 0, 4, 8, 14, 24, 40, 0]
CEN = [0, 0, 0, 10, 15, 10, 5, 0]
KMG = [20, 25, 10, 0, 0, 10, 25, 20]
MATE = 100000
D = [16, -16, 1, -1, 15, 17, -15, -17]      # king dirs; [:4] rook, [4:] bishop
RD = D[:4]
BD = D[4:]
ND = [31, 33, 14, 18, -31, -33, -14, -18]   # knight dirs
_R = random.Random(20261112).getrandbits
Z = [[_R(64) for _ in range(128)] for _ in range(15)]
Q = [_R(64) for _ in range(25)]  # [0]=side, [1..8]=ep file, [9..24]=castling

B = [0] * 128        # board, 1..6 white, 9..14 black (type = p & 7)
side = 0
castle = 15
ep = -1
S = 0                # white-perspective material+PST, non-king pieces
nm = 0               # non-pawn material total, for king phase
H = 0
ksq = [4, 116]
undo = []
N = 0
BGT = int(os.environ.get('TINYCHESS_NODES', '60000'))
TT = {}
KL = [[0, 0] for _ in range(128)]
HS = [0] * (2 * 128 * 128)


def pst(p, sq):
    t = p & 7
    r = sq >> 4
    f = sq & 7
    rr, sgn = (r, 1) if p < 8 else (7 - r, -1)
    c = min(f, 7 - f) + min(rr, 7 - rr)
    v = VAL[t] + (ADV[rr] + (CEN[rr] if f in (3, 4) else 0) if t == 1 else 6 * c - 20 if t == 2 else 4 * c - 8 if t == 3 else (15 if rr == 6 else 0) + (5 if rr == 0 and f in (3, 4) else 0) if t == 4 else 2 * c - 6)
    return sgn * v


def evaluate():
    s = S
    ph = min(nm, 7800)
    for w in (0, 1):
        sq = ksq[w]
        r = sq >> 4
        f = sq & 7
        rr = r if w == 0 else 7 - r
        c = min(f, 7 - f) + min(rr, 7 - rr)
        st = 16 - 32 * w
        pw = 1 + 8 * w
        sh = 0
        for df in (-1, 0, 1):
            t = sq + st + df
            if (f or df > -1) and not t & 0x88 and B[t] != pw:
                sh += 1
        mg = (KMG[f] if rr == 0 else max(-50, -15 * rr)) - 15 * sh
        k = (mg * ph + (8 * c - 24) * (7800 - ph)) // 7800
        s += k if w == 0 else -k
    return s if side == 0 else -s


def setup():
    # start position only; S/nm/H are constants for it (checked vs full build)
    global B, side, castle, ep, S, nm, H, ksq
    B = [0] * 128
    undo.clear()
    for i in range(8):
        c = int('42356324'[i])
        B[i] = c
        B[112 + i] = c + 8
        B[16 + i] = 1
        B[96 + i] = 9
    S = 0
    nm = 6400
    H = 0x5f99378aa28692a7
    ksq = [4, 116]
    side = 0
    castle = 15
    ep = -1


def attacked(sq, by_white):
    for d in ((-15, -17) if by_white else (15, 17)):
        s = sq + d
        if not s & 0x88 and B[s] == (1 if by_white else 9):
            return True
    for d in ND:
        s = sq + d
        if not s & 0x88 and B[s] == (2 if by_white else 10):
            return True
    for d in D:
        s = sq + d
        if not s & 0x88 and B[s] == (6 if by_white else 14):
            return True
    RQ = (4, 5) if by_white else (12, 13)
    BQ = (3, 5) if by_white else (11, 13)
    for i, d in enumerate(D):
        s = sq + d
        while not s & 0x88:
            p = B[s]
            if p:
                if (i < 4 and p in RQ) or (i >= 4 and p in BQ):
                    return True
                break
            s += d
    return False


def gen(caps_only=False):
    mv = []
    us = side

    def promo(f, t, sc):
        for pr in (5, 4, 3, 2):
            mv.append(f | (t << 7) | (pr << 14) | ((sc + VAL[pr]) << 17))

    for sq in range(128):
        if sq & 0x88:
            continue
        p = B[sq]
        if not p or (p < 8) != (us == 0):
            continue
        t = p & 7
        if t == 1:
            step = 16 if us == 0 else -16
            start = 1 if us == 0 else 6
            last = 6 if us == 0 else 1
            r = sq >> 4
            one = sq + step
            if not B[one]:
                if r == last:
                    promo(sq, one, 900)
                elif not caps_only:
                    mv.append(sq | (one << 7))
                    if r == start and not B[sq + 2 * step]:
                        mv.append(sq | ((sq + 2 * step) << 7))
            for d in (step - 1, step + 1):
                to = sq + d
                if to & 0x88:
                    continue
                q = B[to]
                if q and (q < 8) != (us == 0):
                    if r == last:
                        promo(sq, to, 100000 + 10 * VAL[q & 7] - 1)
                    else:
                        mv.append(sq | (to << 7) | ((100000 + 10 * VAL[q & 7] - 1) << 17))
                elif to == ep:
                    mv.append(sq | (to << 7) | (100030 << 17))
        elif t in (2, 6):
            for d in (ND if t == 2 else D):
                to = sq + d
                if to & 0x88:
                    continue
                q = B[to]
                if not q:
                    if not caps_only:
                        mv.append(sq | (to << 7))
                elif (q < 8) != (us == 0):
                    mv.append(sq | (to << 7) | ((100000 + 10 * VAL[q & 7] - t) << 17))
        else:
            for d in (RD if t == 4 else BD if t == 3 else D):
                to = sq + d
                while not to & 0x88:
                    q = B[to]
                    if not q:
                        if not caps_only:
                            mv.append(sq | (to << 7))
                    else:
                        if (q < 8) != (us == 0):
                            mv.append(sq | (to << 7) | ((100000 + 10 * VAL[q & 7] - t) << 17))
                        break
                    to += d
    if not caps_only:
        k = ksq[us]
        home = 4 if us == 0 else 116
        rk = 4 if us == 0 else 12
        if k == home:
            for bit, sgn in ((1, 1), (2, -1)):
                if us:
                    bit *= 4
                if castle & bit and B[home + (3 if sgn == 1 else -4)] == rk and not B[home + sgn] and not B[home + 2 * sgn] and (sgn == 1 or not B[home - 3]):
                    if not attacked(home, us == 1) and not attacked(home + sgn, us == 1) and not attacked(home + 2 * sgn, us == 1):
                        mv.append(home | ((home + 2 * sgn) << 7))
    return mv


def make(mv):
    global side, castle, ep, S, nm, H
    f = mv & 127
    t = (mv >> 7) & 127
    pr = (mv >> 14) & 7
    p = B[f]
    cap = B[t]
    epcap = -1
    if not cap and (p & 7) == 1 and t == ep:
        epcap = t - 16 if side == 0 else t + 16
        cap = B[epcap]
    undo.append((mv, cap, castle, ep, S, nm, H))
    H ^= Q[0]
    if ep >= 0:
        H ^= Q[1 + (ep & 7)]
    H ^= Q[9 + castle]
    if cap:
        S -= pst(cap, epcap if epcap >= 0 else t)
        H ^= Z[cap][epcap if epcap >= 0 else t]
        if epcap >= 0:
            B[epcap] = 0
        ct = cap & 7
        if ct == 3:
            S += -30 if cap < 8 else 30
        if ct != 1:
            nm -= VAL[ct]
    # rook leaving / captured on its home square loses castling rights
    for s, bit in ((0, 2), (7, 1), (112, 8), (119, 4)):
        if f == s or t == s:
            castle &= ~bit
    if (p & 7) != 6:
        S -= pst(p, f)
    H ^= Z[p][f]
    B[f] = 0
    np = p
    if pr:
        np = pr if p < 8 else pr + 8
        nm += VAL[pr] - 100
    B[t] = np
    if (p & 7) != 6:
        S += pst(np, t)
    H ^= Z[np][t]
    if (p & 7) == 6:
        ksq[side] = t
        castle &= ~(3 if side == 0 else 12)
        if abs(t - f) == 2:
            rf, rt = (f + 3, f + 1) if t > f else (f - 4, f - 1)
            rk = 4 + 8 * side
            B[rf] = 0
            B[rt] = rk
            S -= pst(rk, rf)
            S += pst(rk, rt)
            H ^= Z[rk][rf] ^ Z[rk][rt]
    if (p & 7) == 1 and abs(t - f) == 32:
        ep = (f + t) // 2
    else:
        ep = -1
    if ep >= 0:
        H ^= Q[1 + (ep & 7)]
    H ^= Q[9 + castle]
    side ^= 1


def unmake():
    global side, castle, ep, S, nm, H
    mv, cap, oc, oep, oS, onm, oH = undo.pop()
    f = mv & 127
    t = (mv >> 7) & 127
    pr = (mv >> 14) & 7
    side ^= 1
    p = B[t]
    if pr:
        p = 1 if side == 0 else 9
    if (p & 7) == 6:
        ksq[side] = f
        if abs(t - f) == 2:
            rt, rf = (f + 1, f + 3) if t > f else (f - 1, f - 4)
            B[rt] = 0
            B[rf] = 4 + 8 * side
    B[f] = p
    B[t] = 0
    if cap:
        if (p & 7) == 1 and t == oep and not B[t]:
            B[t - 16 if side == 0 else t + 16] = cap
        else:
            B[t] = cap
    castle, ep, S, nm, H = oc, oep, oS, onm, oH


def legal(mv):
    make(mv & 131071)
    ok = not attacked(ksq[side ^ 1], side == 0)
    if not ok:
        unmake()
    return ok


def srch(d, a, b, ply):
    global N, side, ep, H
    N += 1
    if N >= BGT:
        return 0
    chk = attacked(ksq[side], side == 1)
    if d > 0 and chk and d < 9:
        d += 1 # v10: check extension
    a0 = a
    ttm = 0
    q = d <= 0
    if q:
        best = -MATE - 1
        if not chk:
            st = evaluate()
            if st >= b:
                return st
            best = st
            if st > a:
                a = st
    else:
        ent = TT.get(H)
        if ent:
            ed, flag, esc, emv = ent
            ttm = emv
            if ed >= d:
                s = esc
                if s > MATE - 200:
                    s -= ply
                elif s < -MATE + 200:
                    s += ply
                if flag == 1 or (flag == 2 and s >= b) or (flag == 3 and s <= a):
                    return s
        if d >= 4 and not chk and b < MATE - 200 and nm > 900 and evaluate() >= b:
            undo.append((0, 0, castle, ep, S, nm, H))
            H ^= Q[0]
            if ep >= 0:
                H ^= Q[1 + (ep & 7)]
            ep = -1
            side ^= 1
            r = 2 if d < 6 else 3
            sc = -srch(d - 1 - r, -b, -b + 1, ply + 1)
            _, _, oc, oep, _, _, oH = undo.pop()
            side ^= 1
            ep = oep
            H = oH
            if N >= BGT:
                return 0
            if sc >= b:
                return b
        best = -MATE - 1
    moves = gen(caps_only=(q and not chk))
    scored = []
    for pm in moves:
        mv = pm & 131071
        sc = pm >> 17
        if mv == ttm:
            sc = 1 << 20
        elif sc == 0:
            if mv == KL[ply][0]:
                sc = 50000
            elif mv == KL[ply][1]:
                sc = 40000
            else:
                sc = min(HS[side * 16384 + (mv & 127) * 128 + ((mv >> 7) & 127)], 40000)
        scored.append(mv | (sc << 17))
    scored.sort(reverse=True)
    bestmv = 0
    legal_n = 0
    for pm in scored:
        mv = pm & 131071
        if q and not chk:
            t = (mv >> 7) & 127
            qq = B[t]
            if not qq and (mv >> 14) & 7 == 0 and t != ep:
                continue
            if qq and best + VAL[qq & 7] + 200 < a:
                continue
        if not legal(mv):
            continue
        legal_n += 1
        capq = (mv >> 14) & 7 or (undo[-1][1] != 0)
        if q:
            sc = -srch(0, -b, -a, ply + 1)
        elif legal_n == 1:
            sc = -srch(d - 1, -b, -a, ply + 1)
        else:
            if d >= 3 and legal_n >= 4 and not capq and not chk:
                sc = -srch(d - 2, -a - 1, -a, ply + 1)
                if sc > a:
                    sc = -srch(d - 1, -b, -a, ply + 1)
            else:
                sc = -srch(d - 1, -a - 1, -a, ply + 1)
                if a < sc < b:
                    sc = -srch(d - 1, -b, -a, ply + 1)
        unmake()
        if N >= BGT:
            return 0
        if sc > best:
            best = sc
            bestmv = mv
        if sc >= b:
            if not q and not capq:
                if KL[ply][0] != mv:
                    KL[ply][1] = KL[ply][0]
                    KL[ply][0] = mv
                HS[side * 16384 + (mv & 127) * 128 + ((mv >> 7) & 127)] += d * d
            break
        if sc > a:
            a = sc
    if legal_n == 0:
        return -MATE + ply if chk else (0 if not q else best)
    if N >= BGT:
        return 0
    if q:
        return best
    s = best
    if s > MATE - 200:
        s += ply
    elif s < -MATE + 200:
        s -= ply
    if best >= b:
        flag = 2
    elif best <= a0:
        flag = 3
    else:
        flag = 1
    if len(TT) > 300000:
        TT.clear()
    TT[H] = (d, flag, s, bestmv)
    return best


def search_root(max_depth=30):
    global N
    N = 0
    moves = gen()
    moves.sort(reverse=True)
    legal_moves = []
    for pm in moves:
        mv = pm & 131071
        if legal(mv):
            legal_moves.append(mv)
            unmake()
    if len(legal_moves) == 1:
        return legal_moves[0]
    # v10: repetition filter depends on the static eval (side to move).
    # Ahead: never repeat (2nd occurrence already lets the opponent claim).
    # Behind: never filter (a repetition draw is good). Else: v2's rule.
    ev0 = evaluate()
    lim = 1 if ev0 > 80 else 99 if ev0 < -80 else 2
    r = []
    for mv in legal_moves:
        make(mv)
        if [u[6] for u in undo].count(H) < lim:
            r.append(mv)
        unmake()
    if r:
        legal_moves = r
    order = legal_moves[:]
    best = order[0]
    for d in range(1, max_depth + 1):
        a = -MATE - 1
        scored = []
        aborted = False
        for mv in order:
            make(mv)
            sc = -srch(d - 1, -MATE - 1, -a, 1)
            unmake()
            if N >= BGT:
                aborted = True
                break
            scored.append((sc, mv))
            if sc > a:
                a = sc
        if aborted:
            break
        scored.sort(key=lambda z: -z[0])
        order = [mv for _, mv in scored]
        best = order[0]
        if scored[0][0] >= MATE - 200:
            break
    return best


def post(env, path, body):
    req = urllib.request.Request(env + path, data=json.dumps(body).encode(),
                                 headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req) as res:
        return json.load(res)


def sq(s):
    return 'abcdefgh'[s & 7] + str((s >> 4) + 1)


def main():
    env = os.environ.get('MAKEFUN_ENV_URL')
    if not env:
        sys.exit('MAKEFUN_ENV_URL is not set')
    while True:
        g = post(env, '/game', {})
        if g.get('status') == 'done':
            break
        while g.get('status') == 'your_move':
            setup()
            for u in g['moves']:
                f = 'abcdefgh'.index(u[0]) + (int(u[1]) - 1) * 16
                t = 'abcdefgh'.index(u[2]) + (int(u[3]) - 1) * 16
                pr = 'nbrq'.index(u[4]) + 2 if len(u) == 5 else 0
                make(f | (t << 7) | (pr << 14))
            mv = search_root()
            pr = (mv >> 14) & 7
            g = post(env, '/move', {'game': g['game'], 'move': sq(mv & 127) + sq((mv >> 7) & 127) + ('nbrq'[pr - 2] if pr else '')})


if __name__ == '__main__':
    main()
