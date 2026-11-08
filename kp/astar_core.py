# 面的な探索（devline3.py）の A* の中身。numba で機械語に変換して動かす（2026-11-08、ユーザーの了承：純 Python の A* は難しい駅間で 10〜30 秒）。
# 状態の番号 p ＝ ((j × nx ＋ i) × nz ＋ (m − M0)) × 16 ＋ h（devline3.py と同じ）。配列だけで書く（辞書・オブジェクトは使わない）。
# 優先度つき待ち行列は、配列の上の二分ヒープ（キー float64、値 int64）。同じ状態を何度も入れ、取り出したときに確定済みなら読み飛ばす。
import numpy as np
from numba import njit


@njit(cache=True)
def _push(keys, vals, n, k, v):
    i = n; keys[i] = k; vals[i] = v; n += 1
    while i > 0:
        p = (i - 1) >> 1
        if keys[p] <= keys[i]: break
        keys[p], keys[i] = keys[i], keys[p]; vals[p], vals[i] = vals[i], vals[p]; i = p
    return n


@njit(cache=True)
def _pop(keys, vals, n):
    k = keys[0]; v = vals[0]; n -= 1
    keys[0] = keys[n]; vals[0] = vals[n]; i = 0
    while True:
        l = 2 * i + 1; r = l + 1; s = i
        if l < n and keys[l] < keys[s]: s = l
        if r < n and keys[r] < keys[s]: s = r
        if s == i: break
        keys[s], keys[i] = keys[i], keys[s]; vals[s], vals[i] = vals[i], vals[s]; i = s
    return k, v, n


@njit(cache=True)
def astar(G, sea, m_lo, m_hi, dline, dgoal, CM, M0, nz, DZ, GMAX, C_TRACK, LAMBDA, BOUND, TURN, D16, LEN, KK,
          start, sbi, sbj, zB, END_TOL, hb, hbtol, g, pred, closed, heap_cap):
    """A*。g・pred・closed は呼ぶ側が用意した配列（長さ N）。返り値：(費用, 終点の状態（なければ −1）, 展開した状態の数)"""
    ny, nx = G.shape; NH = 16
    keys = np.empty(heap_cap, np.float64); vals = np.empty(heap_cap, np.int64); n = 0
    si = (start // NH) // nz; mA = (start // NH) % nz + M0
    g[start] = 0.0; pred[start] = -1
    h0 = C_TRACK * max(dgoal[si // nx, si % nx], abs(zB - mA * DZ) / GMAX)
    n = _push(keys, vals, n, h0, start); n_exp = 0
    while n > 0:
        f, p, n = _pop(keys, vals, n)
        if closed[p]: continue
        closed[p] = 1; n_exp += 1
        h = p % NH; q = p // NH; m = q % nz + M0; c = q // nz; i = c % nx; j = c // nx; gp = g[p]
        if i == sbi and j == sbj and abs(m * DZ - zB) <= END_TOL:
            if hb < 0 or min((h - hb) % 16, (hb - h) % 16) <= hbtol: return gp, p, n_exp   # 終点の向き（hb < 0 なら自由）
            continue
        for dh in range(-TURN, TURN + 1):
            h2 = (h + dh) % 16; i2 = i + D16[h2, 0]; j2 = j + D16[h2, 1]
            if i2 < 0 or i2 >= nx or j2 < 0 or j2 >= ny or sea[j2, i2]: continue
            L = LEN[h2]; k = KK[h2]; g2 = G[j2, i2]; lo2 = m_lo[j2, i2]; hi2 = m_hi[j2, i2]
            base = L * (C_TRACK + LAMBDA * dline[j2, i2]); dg2 = dgoal[j2, i2]
            for dm in range(-k, k + 1):
                m2 = m + dm
                if m2 < lo2 or m2 > hi2: continue
                hd = g2 - m2 * DZ; idx = int(round((hd + 400.0) * 2.0))
                if idx < 0: idx = 0
                elif idx > 1600: idx = 1600
                c2 = gp + base + L * CM[idx]
                hgoal = C_TRACK * max(dg2, abs(zB - m2 * DZ) / GMAX)
                if c2 + hgoal > BOUND: continue
                p2 = ((j2 * nx + i2) * nz + (m2 - M0)) * NH + h2
                if closed[p2]: continue
                if c2 < g[p2]:
                    g[p2] = c2; pred[p2] = p
                    if n >= heap_cap: return -1.0, -2, n_exp   # 待ち行列があふれた（heap_cap を増やす）
                    n = _push(keys, vals, n, c2 + hgoal, p2)
    return -1.0, -1, n_exp
