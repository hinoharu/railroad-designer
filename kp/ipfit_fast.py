# 交点法の当てはめ（ipfit_all.py）の内側を numba で機械語にしたもの（2026-11-08、ユーザーの指示：速度 100 倍）。
# 変えるのは費用の評価（local_cost）、交点を動かす手（best_move・best_move_w・best_r）、半径の初期値（choose_radii）の中身だけ。
# 交点の列の扱い（簡略化・取り除く・まとめる・なめ直しの回数）は ipfit_all.py / ipfit_branch.py のまま。
# 違い：元の線からの距離は、2 m 刻みの点の KD 木（cKDTree）への最近点ではなく、折れ線の線分への垂直距離（真の距離）。
#   2 m 刻みの点への距離は真の距離より最大 1 m 大きい（線分の中ほどの点）ので、費用がわずかに（0.01% ほど）変わる。
# 速くする手（結果は変えない）：
#   - numba の関数は引数ごとに型を調べる（1 個 2〜3 µs）ので、表は 1 つの配列 TAB（6 × 半径の数）、定数は 1 つの配列 PAR にまとめる
#   - 折れ線の線分を 100 m の格子に登録し（線分の囲みが重なる格子すべて）、点から 3×3 の格子の線分だけで距離を測る。
#     どれも 100 m より遠ければ全線分で測り直す（真の距離を保つ）
#   - 半径の総当たり（交点 i）では、i に関係しない部分（ほかの曲線、i に接しない直線）の費用を 1 回だけ計算する
import math, os
import numpy as np
from numba import njit
import ipfit_all as F
import speed as _sp

RCAT = F.RCAT
TAB = np.ascontiguousarray(np.vstack([F.RCAT, F.pS, F.mS, F.tau, F.XL, F.LOSS]), dtype=np.float64)   # 0 半径、1 pS、2 mS、3 tau、4 緩和曲線の長さ X、5 減速の損 LOSS
PAR = np.array([F.D, F.H, F.W_D, F.LAM, float(_sp.VMAX), 1.0 if _sp.TILT else 0.0, float(_sp.MARGIN), 100.0], dtype=np.float64)   # 7：格子で測る距離の上限 m（格子の大きさ）
RSCAN = os.environ.get('RSCAN', 'coarse')   # 半径の選び方：full＝20 m 刻みの総当たり（元のまま）。coarse＝100 m 刻み → 最良の周り ±100 m を 20 m 刻み
Q = None   # 元の折れ線（局所座標、n×2）。solve が set_polyline で置く（ipfit_all.TREE に当たる）
GS = GI = GP = IA = None   # 線分の格子（CSR：格子ごとの始まり GS、線分の番号 GI、格子の原点と大きさ GP）、全線分 IA


def set_polyline(Q_):
    """元の折れ線を置き、線分を格子に登録する（solve が呼ぶ）"""
    global Q, GS, GI, GP, IA
    Q = np.ascontiguousarray(Q_, dtype=np.float64); n = len(Q) - 1; IA = np.arange(n, dtype=np.int64)
    cs = PAR[7]; x0, y0 = Q.min(0) - cs; x1, y1 = Q.max(0) + cs
    nx = int((x1 - x0) / cs) + 1; ny = int((y1 - y0) / cs) + 1
    A = Q[:-1]; B = Q[1:]
    cx0 = ((np.minimum(A[:, 0], B[:, 0]) - x0) / cs).astype(np.int64); cx1 = ((np.maximum(A[:, 0], B[:, 0]) - x0) / cs).astype(np.int64)
    cy0 = ((np.minimum(A[:, 1], B[:, 1]) - y0) / cs).astype(np.int64); cy1 = ((np.maximum(A[:, 1], B[:, 1]) - y0) / cs).astype(np.int64)
    cnt = np.zeros(nx * ny + 1, np.int64)
    for k in range(n):
        for cy in range(cy0[k], cy1[k] + 1): cnt[cy * nx + cx0[k] + 1: cy * nx + cx1[k] + 2] += 1
    GS = np.cumsum(cnt); GI = np.empty(GS[-1], np.int64); fill = GS[:-1].copy()
    for k in range(n):
        for cy in range(cy0[k], cy1[k] + 1):
            for cx in range(cx0[k], cx1[k] + 1):
                c = cy * nx + cx; GI[fill[c]] = k; fill[c] += 1
    GP = np.array([x0, y0, cs, nx, ny], dtype=np.float64)


@njit(cache=True, nogil=True)
def _smooth(R, PAR):
    """speed.smooth と同じ：最適化に使う制限速度（km/h）"""
    VMAX = PAR[4]; MARGIN = PAR[6]
    if PAR[5] == 0.0:
        return min(VMAX, math.sqrt(R * 165 / 11.8) - MARGIN)
    t = (R - 560.0) / 40.0
    if t < 0.0: t = 0.0
    elif t > 1.0: t = 1.0
    v = (1 - t) * math.sqrt(R * 215 / 11.8) + t * (math.sqrt(R * 165 / 11.8) + 30.0) - MARGIN
    return min(VMAX, v)


@njit(cache=True, nogil=True)
def _ftime(k, PAR):
    """ipfit_all.ftime と同じ：曲率 k の所を走る 1 m あたりの時間の増分（秒）"""
    ak = abs(k)
    if ak < 1e-9: ak = 1e-9
    return 3.6 / _smooth(1.0 / ak, PAR) - 3.6 / PAR[4]


@njit(cache=True, nogil=True)
def _pen(d, PAR):
    e = d - PAR[0]
    if e < 0.0: e = 0.0
    return d * d + (PAR[2] * e) * (PAR[2] * e)


@njit(cache=True, nogil=True)
def _seg_dist1(x, y, Q, a):
    ax = Q[a, 0]; ay = Q[a, 1]; bx = Q[a + 1, 0]; by = Q[a + 1, 1]
    dx = bx - ax; dy = by - ay; L2 = dx * dx + dy * dy
    if L2 > 0.0:
        u = ((x - ax) * dx + (y - ay) * dy) / L2
        if u < 0.0: u = 0.0
        elif u > 1.0: u = 1.0
        return math.hypot(x - (ax + u * dx), y - (ay + u * dy))
    return math.hypot(x - ax, y - ay)


@njit(cache=True, nogil=True)
def _dist(x, y, Q, GS, GI, GP, IA, PAR):
    """点 (x, y) から折れ線 Q までの最短距離。3×3 の格子の線分で測り、どれも PAR[7] より遠ければ全線分で測り直す"""
    nx = int(GP[3]); ny = int(GP[4]); cx = int((x - GP[0]) / GP[2]); cy = int((y - GP[1]) / GP[2]); best = 1e30
    for yy in range(cy - 1, cy + 2):
        if yy < 0 or yy >= ny: continue
        for xx in range(cx - 1, cx + 2):
            if xx < 0 or xx >= nx: continue
            c = yy * nx + xx
            for t in range(GS[c], GS[c + 1]):
                d = _seg_dist1(x, y, Q, GI[t])
                if d < best: best = d
    if best > PAR[7]:
        for t in range(IA.shape[0]):
            d = _seg_dist1(x, y, Q, IA[t])
            if d < best: best = d
    return best


@njit(cache=True, nogil=True)
def _straight_cost(sx, sy, tx, ty, Q, GS, GI, GP, IA, PAR):
    """直線 (sx,sy)→(tx,ty) のずれの費用（5 m 刻み）と、ずれの最大"""
    Ls = math.hypot(tx - sx, ty - sy); cost = 0.0; mx = 0.0
    if Ls > 0.0:
        k = int(Ls / 5)
        if k < 1: k = 1
        w = Ls / k
        for t in range(k + 1):
            u = t / k; d = _dist(sx + (tx - sx) * u, sy + (ty - sy) * u, Q, GS, GI, GP, IA, PAR)
            cost += _pen(d, PAR) * w / PAR[1]
            if d > mx: mx = d
    return cost, mx


@njit(cache=True, nogil=True)
def _curve_cost(ipx, ipy, ax, ay, T, d1, j, Q, GS, GI, GP, IA, TAB, PAR):
    """交点 (ipx, ipy)、入る向き (ax, ay)、接線長 T、曲がる角 d1、半径の番号 j の曲線（緩和曲線＋円曲線＋緩和曲線）の点を
    ipfit_all.curve_pts と同じ刻み（5 m）で作り、ずれの費用・走行時間の増分・ずれの最大を返す"""
    R = TAB[0, j]; X = TAB[4, j]; ad = abs(d1)
    c = (1.0 / R) if d1 >= 0 else (-1.0 / R); A = R * ad - X; Ltot = 2 * X + A
    k = int(Ltot / 5)
    if k < 2: k = 2
    ds = Ltot / k; th = math.atan2(ay, ax); px = ipx - ax * T; py = ipy - ay * T; k0 = 0.0
    cost = 0.0; tsum = 0.0; mx = 0.0
    d = _dist(px, py, Q, GS, GI, GP, IA, PAR); cost += _pen(d, PAR) * ds; tsum += _ftime(k0, PAR) * ds
    if d > mx: mx = d
    for t in range(1, k + 1):
        s1 = Ltot * t / k
        if s1 < X: k1 = c * s1 / X
        elif s1 < X + A: k1 = c
        else: k1 = c * (Ltot - s1) / X
        th1 = th + ds * (k1 + k0) / 2; ph = (th1 + th) / 2
        px += ds * math.cos(ph); py += ds * math.sin(ph); th = th1; k0 = k1
        d = _dist(px, py, Q, GS, GI, GP, IA, PAR); cost += _pen(d, PAR) * ds; tsum += _ftime(k1, PAR) * ds
        if d > mx: mx = d
    return cost / PAR[1], tsum, mx


@njit(cache=True, nogil=True)
def _ends(V, Rj, lo, hi, TAB, ein, eout, uinx, uiny, d1s, Ts, skip):
    """窓 lo〜hi の各交点の曲線の始まり ein・終わり eout（端の交点はその点）、入る向き、曲がる角、接線長。
    skip の交点は飛ばす（半径の総当たりで後から入れる）。曲線が入らない交点があれば False"""
    n = V.shape[0]; m = hi - lo + 1
    for q in range(m):
        i = lo + q
        if i == 0 or i == n - 1:
            ein[q, 0] = V[i, 0]; ein[q, 1] = V[i, 1]; eout[q, 0] = V[i, 0]; eout[q, 1] = V[i, 1]
            continue
        ax = V[i, 0] - V[i - 1, 0]; ay = V[i, 1] - V[i - 1, 1]; la = math.hypot(ax, ay); ax /= la; ay /= la
        bx = V[i + 1, 0] - V[i, 0]; by = V[i + 1, 1] - V[i, 1]; lb = math.hypot(bx, by); bx /= lb; by /= lb
        d1 = math.atan2(ax * by - ay * bx, ax * bx + ay * by); uinx[q] = ax; uiny[q] = ay; d1s[q] = d1
        if i == skip: continue
        ad = abs(d1); j = Rj[i - 1]
        if ad < 2 * TAB[3, j]: return False
        T = (TAB[0, j] + TAB[1, j]) * math.tan(ad / 2) + TAB[2, j]
        ein[q, 0] = V[i, 0] - ax * T; ein[q, 1] = V[i, 1] - ay * T; eout[q, 0] = V[i, 0] + bx * T; eout[q, 1] = V[i, 1] + by * T; Ts[q] = T
    return True


@njit(cache=True, nogil=True)
def _overlap(V, lo, q, ein, eout):
    """直線 q→q+1（窓の中の番号）で、前の曲線の終わりと次の曲線の始まりが逆転していれば True"""
    return (ein[q + 1, 0] - eout[q, 0]) * (V[lo + q + 1, 0] - V[lo + q, 0]) + (ein[q + 1, 1] - eout[q, 1]) * (V[lo + q + 1, 1] - V[lo + q, 1]) < -1e-6


@njit(cache=True, nogil=True)
def wcost(V, Rj, lo, hi, Q, GS, GI, GP, IA, TAB, PAR):
    """ipfit_all.local_cost と同じ量：交点 lo〜hi の窓の費用（元の線からのずれ＋走行時間）と、ずれの最大。
    V：交点（n×2）、Rj：交点 1〜n−2 の半径の番号（TAB の列）。入らなければ (inf, inf)"""
    m = hi - lo + 1
    ein = np.empty((m, 2)); eout = np.empty((m, 2)); uinx = np.empty(m); uiny = np.empty(m); d1s = np.empty(m); Ts = np.empty(m)
    if not _ends(V, Rj, lo, hi, TAB, ein, eout, uinx, uiny, d1s, Ts, -1): return math.inf, math.inf
    for q in range(m - 1):
        if _overlap(V, lo, q, ein, eout): return math.inf, math.inf
    cost = 0.0; mx = 0.0
    for q in range(m - 1):
        c1, m1 = _straight_cost(eout[q, 0], eout[q, 1], ein[q + 1, 0], ein[q + 1, 1], Q, GS, GI, GP, IA, PAR); cost += c1
        if m1 > mx: mx = m1
    for q in range(1, m - 1):
        i = lo + q; j = Rj[i - 1]
        c1, tsum, m1 = _curve_cost(V[i, 0], V[i, 1], uinx[q], uiny[q], Ts[q], d1s[q], j, Q, GS, GI, GP, IA, TAB, PAR)
        cost += c1 + PAR[3] * (tsum + TAB[5, j])
        if m1 > mx: mx = m1
    return cost, mx


@njit(cache=True, nogil=True)
def _line_table(px, py, ux, uy, L, step, Q, GS, GI, GP, IA, PAR, f, CT):
    """直線（始点 (px, py)、向き (ux, uy)、長さ L）の上の、元の線からのずれの罰則 pen を step 刻みで表にし（最後は L の点）、
    台形の累積 CT を作る。返す：刻みの数 N（f[0..N] が有効。f[N] は L の点）"""
    N = int(L / step)
    for t in range(N + 1):
        sx = t * step if t < N else L
        f[t] = _pen(_dist(px + ux * sx, py + uy * sx, Q, GS, GI, GP, IA, PAR), PAR)
    # 刻み N−1 → N の幅は L − (N−1)·step（最後の 1 つだけ短い）
    CT[0] = 0.0
    for t in range(N):
        w = step if t < N - 1 else L - t * step
        CT[t + 1] = CT[t] + (f[t] + f[t + 1]) / 2 * w
    if N == 0: CT[0] = 0.0
    return N


@njit(cache=True, nogil=True)
def _tbl_at(f, N, L, step, s):
    """表 f の s での値（線形補間）"""
    if N == 0: return f[0]
    t = int(s / step)
    if t >= N: return f[N]
    s0 = t * step; s1 = (t + 1) * step if t + 1 < N else L
    if s1 <= s0: return f[t]
    return f[t] + (f[t + 1] - f[t]) * (s - s0) / (s1 - s0)


@njit(cache=True, nogil=True)
def _tbl_int(f, CT, N, L, step, s):
    """表の 0 から s までの積分（台形）"""
    if N == 0: return f[0] * s
    t = int(s / step)
    if t >= N: return CT[N]
    s0 = t * step
    return CT[t] + (f[t] + _tbl_at(f, N, L, step, s)) / 2 * (s - s0)


@njit(cache=True, nogil=True)
def _straight_tbl(f, CT, N, L, step, a, b, PAR):
    """直線の a〜b の部分のずれの費用。_straight_cost（5 m 刻みの和 ＝ 台形の積分 ＋ 両端の半分）と同じ量を表から求める"""
    Ls = b - a
    if Ls <= 0.0: return 0.0
    k = int(Ls / 5)
    if k < 1: k = 1
    w = Ls / k
    return (_tbl_int(f, CT, N, L, step, b) - _tbl_int(f, CT, N, L, step, a) + w * (_tbl_at(f, N, L, step, a) + _tbl_at(f, N, L, step, b)) / 2) / PAR[1]


@njit(cache=True, nogil=True)
def _scan_r_k(V, Rj, i, lo, hi, Q, GS, GI, GP, IA, TAB, PAR, coarse):
    """交点 i（lo < i < hi）の半径を選び直す：20 m 刻み（TAB の偶数列）で総当たり。i に関係しない部分の費用は 1 回だけ計算し、
    i に接する 2 本の直線のずれの費用は 2.5 m 刻みの表から取る（半径で変わるのは直線の端だけ）。
    coarse なら 100 m 刻みで見てから最良の周り ±100 m を 20 m 刻みで。返す：最小の費用、その半径の番号（入る半径がなければ元のまま）"""
    m = hi - lo + 1; qi = i - lo
    ein = np.empty((m, 2)); eout = np.empty((m, 2)); uinx = np.empty(m); uiny = np.empty(m); d1s = np.empty(m); Ts = np.empty(m)
    if not _ends(V, Rj, lo, hi, TAB, ein, eout, uinx, uiny, d1s, Ts, i): return math.inf, Rj[i - 1]
    base = 0.0
    for q in range(m - 1):
        if q == qi - 1 or q == qi: continue
        if _overlap(V, lo, q, ein, eout): return math.inf, Rj[i - 1]
        c1, _ = _straight_cost(eout[q, 0], eout[q, 1], ein[q + 1, 0], ein[q + 1, 1], Q, GS, GI, GP, IA, PAR); base += c1
    for q in range(1, m - 1):
        if q == qi: continue
        k = lo + q; j = Rj[k - 1]
        c1, tsum, _ = _curve_cost(V[k, 0], V[k, 1], uinx[q], uiny[q], Ts[q], d1s[q], j, Q, GS, GI, GP, IA, TAB, PAR)
        base += c1 + PAR[3] * (tsum + TAB[5, j])
    ad = abs(d1s[qi]); ax = uinx[qi]; ay = uiny[qi]
    bx = V[i + 1, 0] - V[i, 0]; by = V[i + 1, 1] - V[i, 1]; Lp = math.hypot(bx, by); bx /= Lp; by /= Lp
    Lm = math.hypot(V[i, 0] - V[i - 1, 0], V[i, 1] - V[i - 1, 1])
    # 手前の直線（V[i−1]→V[i]）：前の曲線の終わりから。後ろの直線（V[i]→V[i+1]）：次の曲線の始まりまで
    a_m = math.hypot(eout[qi - 1, 0] - V[i - 1, 0], eout[qi - 1, 1] - V[i - 1, 1])
    b_p = Lp - math.hypot(V[i + 1, 0] - ein[qi + 1, 0], V[i + 1, 1] - ein[qi + 1, 1])
    step = 2.5
    fm = np.empty(int(Lm / step) + 2); CTm = np.empty(int(Lm / step) + 2); Nm = _line_table(V[i - 1, 0], V[i - 1, 1], ax, ay, Lm, step, Q, GS, GI, GP, IA, PAR, fm, CTm)
    fp = np.empty(int(Lp / step) + 2); CTp = np.empty(int(Lp / step) + 2); Np = _line_table(V[i, 0], V[i, 1], bx, by, Lp, step, Q, GS, GI, GP, IA, PAR, fp, CTp)
    nR = TAB.shape[1]; best = math.inf; bj = Rj[i - 1]
    step_j = 10 if coarse else 2
    for rnd in range(2 if coarse else 1):
        if rnd == 0: a = 0; b = nR - 1
        else:
            if best == math.inf: break
            a = bj - 10; b = bj + 10; step_j = 2
            if a < 0: a = 0
            if b > nR - 1: b = nR - 1
        for j in range(a, b + 1):
            if j % step_j != 0: continue
            if ad < 2 * TAB[3, j]: continue
            T = (TAB[0, j] + TAB[1, j]) * math.tan(ad / 2) + TAB[2, j]
            if Lm - T < a_m - 1e-6 or T > b_p + 1e-6: continue   # 前の曲線・次の曲線と重なる（_overlap と同じ条件）
            c1 = _straight_tbl(fm, CTm, Nm, Lm, step, a_m, Lm - T, PAR)
            c2 = _straight_tbl(fp, CTp, Np, Lp, step, T, b_p, PAR)
            c3, tsum, _ = _curve_cost(V[i, 0], V[i, 1], ax, ay, T, d1s[qi], j, Q, GS, GI, GP, IA, TAB, PAR)
            c = base + c1 + c2 + c3 + PAR[3] * (tsum + TAB[5, j])
            if c < best - 1e-6: best = c; bj = j
    return best, bj


@njit(cache=True, nogil=True)
def _radii_cost_k(V, i, Q, GS, GI, GP, IA, TAB, PAR, L0, L1, out):
    """ipfit_all.choose_radii の COST[i, :]：交点 i+1 に各半径の曲線を入れたときの費用（接線の部分の費用は引く）。入らない半径は inf"""
    ipx = V[i + 1, 0]; ipy = V[i + 1, 1]
    ax = V[i + 1, 0] - V[i, 0]; ay = V[i + 1, 1] - V[i, 1]; la = math.hypot(ax, ay); ax /= la; ay /= la
    bx = V[i + 2, 0] - V[i + 1, 0]; by = V[i + 2, 1] - V[i + 1, 1]; lb = math.hypot(bx, by); bx /= lb; by /= lb
    d1 = math.atan2(ax * by - ay * bx, ax * bx + ay * by); ad = abs(d1)
    for j in range(TAB.shape[1]):
        out[j] = math.inf
        if ad < 2 * TAB[3, j]: continue
        T = (TAB[0, j] + TAB[1, j]) * math.tan(ad / 2) + TAB[2, j]
        if T > L0 or T > L1: continue
        c1, tsum, _ = _curve_cost(ipx, ipy, ax, ay, T, d1, j, Q, GS, GI, GP, IA, TAB, PAR)
        m = int(T / 5)   # 接線の部分（入る側 ip − uin (T − tl)、出る側 ip + uout tl。tl は 0〜T を max(2, int(T/5)) 等分）の費用を引く
        if m < 2: m = 2
        w = T / m; sub = 0.0
        for t in range(m + 1):
            tl = T * t / m
            d = _dist(ipx - ax * (T - tl), ipy - ay * (T - tl), Q, GS, GI, GP, IA, PAR); sub += _pen(d, PAR) * w
            d = _dist(ipx + bx * tl, ipy + by * tl, Q, GS, GI, GP, IA, PAR); sub += _pen(d, PAR) * w
        out[j] = c1 - sub / PAR[1] + PAR[3] * (tsum + TAB[5, j])


# ---- Python 側（ipfit_all / ipfit_branch の関数と同じ名前・同じ引数） ----------------------------------------------------
def rj(Rs): return np.rint((np.asarray(Rs, dtype=np.float64) - RCAT[0]) / 10).astype(np.int64)
def _scan_r(V, Rj, i, lo, hi):
    if lo < i < hi:
        c, j = _scan_r_k(V, Rj, i, lo, hi, Q, GS, GI, GP, IA, TAB, PAR, RSCAN == 'coarse')
    else:   # 窓の端の交点（通常は起きない）：窓全体を半径ごとに計算する
        c = math.inf; j = Rj[i - 1]; R2 = Rj.copy()
        for jj in range(0, len(RCAT), 2):
            R2[i - 1] = jj; c2, _ = wcost(V, R2, lo, hi, Q, GS, GI, GP, IA, TAB, PAR)
            if c2 < c - 1e-6: c = c2; j = jj
    return c, float(RCAT[j])


def local_cost(V_, Rs, lo, hi, want_max=False):
    V = np.ascontiguousarray(V_, dtype=np.float64)
    c, mx = wcost(V, rj(Rs), lo, hi, Q, GS, GI, GP, IA, TAB, PAR)
    return (c, mx) if want_max else c


def best_move(args):
    """ipfit_all.best_move と同じ手：交点 i を二等分線の上で ±D（5 m 刻み）動かし、半径を選び直す"""
    V_, Rs, i = args
    V = np.ascontiguousarray(V_, dtype=np.float64); lo, hi = max(0, i - 2), min(len(V) - 1, i + 2); Rj = rj(Rs)
    uin = V[i] - V[i - 1]; uin = uin / np.hypot(*uin); uo = V[i + 1] - V[i]; uo = uo / np.hypot(*uo)
    bis = uin - uo; nb = np.hypot(*bis)
    c0, _ = wcost(V, Rj, lo, hi, Q, GS, GI, GP, IA, TAB, PAR); best_ = (c0, 0.0, Rs[i - 1])
    if nb < 1e-9: return i, best_
    bis = bis / nb; V2 = V.copy(); base = V[i].copy(); S0 = F.turnsum(V, lo, hi)
    for off in F.OFFS:
        V2[i] = base + bis * off
        if abs(F.turnsum(V2, lo, hi) - S0) > 1e-6: continue
        c, R = _scan_r(V2, Rj, i, lo, hi)
        if c < best_[0] - 1e-6: best_ = (c, off, R)
    return i, (best_[0], float(bis[0] * best_[1]), float(bis[1] * best_[1]), best_[2])


def best_move_w(args):
    """ipfit_branch.best_move_w と同じ：端の交点 W を J を通る直線の上で動かす（半径も選び直す）"""
    V_, Rs, i, J, e = args
    V = np.ascontiguousarray(V_, dtype=np.float64); lo, hi = max(0, i - 2), min(len(V) - 1, i + 2); Rj = rj(Rs)
    c0, _ = wcost(V, Rj, lo, hi, Q, GS, GI, GP, IA, TAB, PAR)
    best_ = (c0, 0.0, Rs[i - 1]); V2 = V.copy(); base = V[i].copy(); S0 = F.turnsum(V, lo, hi); a0 = float((base - J) @ e)
    for off in F.OFFS:
        if a0 + off <= 1.0: continue
        V2[i] = base + e * off
        if abs(F.turnsum(V2, lo, hi) - S0) > 1e-6: continue
        c, R = _scan_r(V2, Rj, i, lo, hi)
        if c < best_[0] - 1e-6: best_ = (c, off, R)
    return i, (best_[0], float(e[0] * best_[1]), float(e[1] * best_[1]), best_[2])


def best_r(V_, Rs, i, lo, hi):
    """ipfit_all.best_r と同じ：交点 i の半径を、ほかを固定して選び直す"""
    c, R = _scan_r(np.ascontiguousarray(V_, dtype=np.float64), rj(Rs), i, lo, hi)
    return R if np.isfinite(c) else Rs[i - 1]


def choose_radii(V_):
    """ipfit_all.choose_radii と同じ：各交点の半径の初期値（隣と重ならない組の中で費用の和が最小）。費用の行列を numba で作る"""
    V = np.ascontiguousarray(V_, dtype=np.float64); L, u, dl = F.geom(V); T = F.tlen(dl); n = len(dl)
    COST = np.full((n, len(RCAT)), np.inf)
    nt = int(os.environ.get('THREADS', 4))
    if nt > 1 and n >= 8:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(nt) as ex: list(ex.map(lambda i: _radii_cost_k(V, i, Q, GS, GI, GP, IA, TAB, PAR, L[i], L[i + 1], COST[i]), range(n)))
    else:
        for i in range(n): _radii_cost_k(V, i, Q, GS, GI, GP, IA, TAB, PAR, L[i], L[i + 1], COST[i])
    best = COST[0].copy(); back = np.zeros((n, len(RCAT)), int)
    for i in range(1, n):
        ok = (T[i - 1][:, None] + T[i][None, :]) <= L[i]
        tot = np.where(ok, best[:, None], np.inf); back[i] = tot.argmin(0); best = tot.min(0) + COST[i]
        if not np.isfinite(best).any(): F.stop_here(V, i, '隣の曲線と重ならずに入る半径の組がない')
    if not np.isfinite(best).any(): F.stop_here(V, n - 1, '曲線の入る半径がない')
    ch = [int(best.argmin())]
    for i in range(n - 1, 0, -1): ch.append(back[i][ch[-1]])
    return [RCAT[j] for j in ch[::-1]]


class SerialPool:
    """multiprocessing.Pool の代わり：スレッドで並列（機械語の関数は GIL を離すので、プロセスを分けずに 4 コアを使える。
    THREADS=1 で直列）"""
    def __init__(self, n=4): self.n = int(os.environ.get('THREADS', n)); self.ex = None
    def __enter__(self):
        if self.n > 1:
            from concurrent.futures import ThreadPoolExecutor; self.ex = ThreadPoolExecutor(self.n)
        return self
    def __exit__(self, *a):
        if self.ex: self.ex.shutdown()
        return False
    def map(self, f, xs): return list(self.ex.map(f, xs)) if self.ex else list(map(f, xs))


def install():
    """ipfit_all / ipfit_branch の関数を差し替える（solve・topology はそのまま、内側だけ速くなる）"""
    import ipfit_branch as B
    F.local_cost = local_cost; F.best_move = best_move; F.best_r = best_r; F.choose_radii = choose_radii
    B.best_move_w = best_move_w; B.Pool = SerialPool
