# fitel.py の関数だけを読み込み、1 区間目の初期値を調べる
import sys, math, numpy as np
src = open('fitel.py').read(); src = src[:src.index('t0 = time.time()')]
sys.argv = ['x']; F = {}; exec(compile(src, 'fitel.py', 'exec'), F)
a, b = 0, 1; Q = F['P0'][F['stops'][a]:F['stops'][b] + 1]
sS, kS, sidx, PS = F['sS'], F['kS'], F['sidx'], F['PS']
ks0 = sS[sidx[a]:sidx[b] + 1]; kk0 = kS[sidx[a]:sidx[b] + 1]; Ps = PS[sidx[a]:sidx[b] + 1]
lay = F['seed_layout'](ks0 - ks0[0], kk0); lo, hi = lay.bounds(); x = np.clip(lay.x0, lo + 1e-9, hi - 1e-12)
N = int(round((ks0[-1] - ks0[0]) / F['H'])); d0 = Ps[1] - Ps[0]; th0 = math.atan2(d0[1], d0[0])
fr = (ks0 - ks0[0]) / (ks0[-1] - ks0[0])
def poserr(x):
    k, h, L = F['kgrid'](lay, x, N); P, th = F['forward'](th0, h, k)
    Pi = np.c_[np.interp(fr * N, np.arange(N + 1), P[:, 0]), np.interp(fr * N, np.arange(N + 1), P[:, 1])]
    return np.hypot(*(Pi - (Ps - Ps[0])).T), L
e, L = poserr(x); A, X, c = lay.unpack(x)
print('初期値：円曲線と直線', lay.m, ' 長さ %.0f / %.0f m' % (L, ks0[-1] - ks0[0]), ' 位置の差 中央値 %.0f 最大 %.0f m' % (np.median(e), e.max()))
ks, kk = lay.knots(x); kt = np.interp(ks0 - ks0[0], ks, kk)
print('曲率の差 中央値 %.1e 最大 %.1e' % (np.median(abs(kt - kk0)), abs(kt - kk0).max()))
# どこで向きがずれるか：向き（転向角の積分）の差を 2 km ごとに
th_s = np.concatenate([[0], np.cumsum((kk0[1:] + kk0[:-1]) / 2 * np.diff(ks0))])
th_e = np.concatenate([[0], np.cumsum((kt[1:] + kt[:-1]) / 2 * np.diff(ks0))])
for q in range(0, len(ks0), len(ks0) // 10): print('  %.1f km 向きの差 %.1f°' % ((ks0[q] - ks0[0]) / 1000, math.degrees(th_e[q] - th_s[q])))
