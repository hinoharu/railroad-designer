# 線形を、実際の鉄道と同じ要素の並び（円曲線［直線は曲率 0 の円曲線］と、そのあいだの緩和曲線［クロソイド］）で作る。
# 1 段目：なめらかな線形（fit_<SEED>.json）の曲率に、要素の並びを当てはめる（形は計算しない）。
# 2 段目：形を計算し、fitk.py と同じ目的（元の折れ線からのずれ＋LAM×走行時間の増分）と規則（緩和曲線の長さ、最小半径）で最適化する。
# 停車駅のあいだの区間ごとに解き、区間ごとに途中保存する（ckpt_el/）。同じコマンドで続きから再開できる。
# 使い方：python3 fitel.py SEED LAM D 名前   例：python3 fitel.py k1e5 100000 30 e1e5
import json, math, sys, os, time
import numpy as np
from scipy.optimize import least_squares
from curves import local
from run import reversals
SEED, LAM, D, NAME = (sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]) if len(sys.argv) > 4 else ('k1e5', 1e5, 30.0, 'dbg')
H = 10.0; SAMP = 10.0; KS = 1 / 5000           # 格子の間隔、標本の間隔、これより小さい曲率は直線
RMIN, RMIN_YARD, YARD = 160.0, 160.0, 110.0
R_STD, R_EXC, W_STD, W_EXC = 300.0, 200.0, 500.0, 5000.0
W_D, W_END, EPS = 10.0, 30.0, 1e-4
# 曲率の 2 乗の和の重み：大きな半径ほど少し得をする（半径 730→800 m の得が、元の線から 1.5 m 離れる損と同じくらい）
MU2 = float(os.environ.get('MU2', '2.4e5'))
r = json.load(open('route_shibetoro_heishi.json')); pts = r['points']
P0 = local(pts); K = 111320 * math.cos(math.radians(pts[len(pts) // 2][1]))
stops = [v for (n, _), v in zip(r['stations'], r['vidx']) if n in r['stops']]
names = [n for (n, _), v in zip(r['stations'], r['vidx']) if n in r['stops']]
rev = set(reversals(r))
seed = json.load(open(f'fit_{SEED}.json'))
PS = np.array([((p[0] - pts[0][0]) * K, (p[1] - pts[0][1]) * 110570) for p in seed['A']])
sS = np.array(seed['s']); kS = np.array(seed['k']); sidx = seed['stopidx']

from speed import smooth as _vsmooth
def vkmh(k):
    k = np.maximum(np.abs(k), 1e-9)
    if os.environ.get('OLDV'): return np.minimum(130.0, np.sqrt(165 / (11.8 * k)) + 30)   # 切り分け用：前の式（本則＋30）
    return _vsmooth(1 / k)
def f_time(k): return 3.6 / vkmh(k) - 3.6 / 130
def rate_max(k):
    k = np.maximum(np.abs(k), 1e-9); R = 1 / k; V = vkmh(k)
    C = np.minimum(7.552 * V * V / R, 105.0); X = np.maximum(np.maximum(0.4 * C, 0.007 * C * V), 1.0)
    return 1 / (R * X)
def densify(Q, step):
    out = [Q[0]]
    for a, b in zip(Q, Q[1:]):
        m = max(1, int(math.ceil(np.hypot(*(b - a)) / step)))
        out += [a + (b - a) * t for t in np.linspace(0, 1, m + 1)[1:]]
    return np.array(out)

# ---- 要素の並び：円曲線 j（曲率 c_j［直線は 0 で固定］、長さ A_j）と、その間の緩和曲線 j（長さ X_j。曲率は c_j から c_{j+1} へ直線的に変わる）
class Layout:
    def __init__(self, c, A, X, curved):
        self.c0 = np.array(c, float); self.curved = np.array(curved, bool); self.m = len(c)
        self.sign = np.sign(self.c0)
        self.x0 = np.concatenate([A, X, np.abs(self.c0[self.curved])])
    def unpack(self, x):
        m = self.m; A = x[:m]; X = x[m:2 * m - 1]; c = self.c0.copy(); c[self.curved] = self.sign[self.curved] * x[2 * m - 1:]
        return A, X, c
    def knots(self, x):
        A, X, c = self.unpack(x); s = [0.0]; k = [c[0]]
        for j in range(self.m):
            s.append(s[-1] + A[j]); k.append(c[j])
            if j < self.m - 1: s.append(s[-1] + X[j]); k.append(c[j + 1])
        return np.array(s), np.array(k)
    def bounds(self):
        m = self.m; lo = np.zeros(len(self.x0)); hi = np.full(len(self.x0), np.inf)
        lo[m:2 * m - 1] = 1.0
        lo[2 * m - 1:] = 1 / 5000; hi[2 * m - 1:] = 1 / RMIN
        return lo, hi

def seed_layout(s, k):
    """なめらかな線形の曲率から、要素の並びの初期値を作る（同じ向きの範囲を曲線とし、途中で曲率が半分以下に下がる長い曲線は分ける）"""
    n = len(k); arcs = []  # (始点, 終点, 曲率)
    DS = float(np.median(np.diff(s)))
    i = 0
    while i < n:
        if abs(k[i]) <= KS:
            j = i
            while j + 1 < n and abs(k[j + 1]) <= KS: j += 1
            arcs.append([s[i], s[j], 0.0]); i = j + 1; continue
        j = i; sg = np.sign(k[i])
        while j + 1 < n and np.sign(k[j + 1]) == sg and abs(k[j + 1]) > KS: j += 1
        seg = np.abs(k[i:j + 1]); ss = s[i:j + 1]
        # 複心曲線：曲率の谷（最大の半分以下）で分ける
        cuts = [0]
        if ss[-1] - ss[0] > 600:
            mx = seg.max()
            for q in range(1, len(seg) - 1):
                if seg[q] < 0.5 * mx and seg[q] <= seg[q - 1] and seg[q] <= seg[q + 1] and ss[q] - ss[cuts[-1]] > 200: cuts.append(q)
        cuts.append(len(seg) - 1)
        for a, b in zip(cuts, cuts[1:]):
            sub = seg[a:b + 1]; d = np.trapezoid(sub, ss[a:b + 1]) if b > a else 0
            cc = max(sub.max(), KS * 1.01)
            arcs.append([ss[a], ss[b], sg * cc, d])
        i = j + 1
    c = [a[2] for a in arcs]; curved = [a[2] != 0 for a in arcs]
    # 長さは元の範囲に合わせ（全体の長さを保つ）、曲率は転向角が元と等しくなるように決める。
    # 緩和曲線の長さは規則の最短（曲率で決まるので、2 回くり返す）。転向角＝c×（円曲線の長さ＋両側の緩和曲線の半分ずつ）
    for _ in range(3):
        X = [max(1.0, abs(c[j + 1] - c[j]) / rate_max(max(abs(c[j]), abs(c[j + 1])))) for j in range(len(arcs) - 1)]
        A = []
        for j, a in enumerate(arcs):
            span = a[1] - a[0] + DS  # 範囲の端から次の範囲の端まで（元の線形の点の間隔を足す）
            half = (X[j - 1] / 2 if j > 0 else 0) + (X[j] / 2 if j < len(X) else 0)
            Aj = max(0.0, span - half); A.append(Aj)
            if curved[j]:
                cc = a[3] / max(Aj + half, 1.0)
                c[j] = float(np.sign(a[2]) * min(max(cc, KS * 1.01), 1 / RMIN))
    return Layout(c, A, X, curved)

def kgrid(lay, x, N):
    ks, kk = lay.knots(x); L = ks[-1]; h = L / N
    return np.interp(np.arange(N + 1) * h, ks, kk), h, L

def forward(th0, h, k):
    th = th0 + h * np.concatenate([[0], np.cumsum((k[1:] + k[:-1]) / 2)])
    ph = (th[1:] + th[:-1]) / 2
    return np.vstack([[0, 0], np.cumsum(h * np.c_[np.cos(ph), np.sin(ph)], axis=0)]), th

W_RATE = 1e3
def solve_leg(Q, start, th0, fix_th0, ks0, kk0, Pseed, th_seed0):
    S = densify(Q, SAMP); L0 = np.hypot(*np.diff(Q, axis=0).T).sum(); N = max(8, int(round(L0 / H)))
    lay = seed_layout(ks0 - ks0[0], kk0)
    lo, hi = lay.bounds(); x = np.clip(lay.x0, lo + 1e-9, hi - 1e-12)
    # 1 段目：曲率だけを合わせる
    grid = ks0 - ks0[0]
    def r1(x):
        ks, kk = lay.knots(x); L = ks[-1]
        kt = np.interp(grid * (L / grid[-1]), ks, kk)
        return np.concatenate([(kt - kk0) * 1e3, [(L - grid[-1]) * 0.01]])
    x = least_squares(r1, x, bounds=(lo, hi), method='trf', x_scale='jac', max_nfev=200).x
    if not fix_th0:
        th0 = float(th_seed0)
    # 1 段目の 2：なめらかな線形の点（同じキロ程の割合の位置）に合わせる
    Ps = Pseed - Pseed[0]; fr = (ks0 - ks0[0]) / (ks0[-1] - ks0[0])
    def r1b(x):
        k, h, L = kgrid(lay, x, N); P, th = forward(th0, h, k)
        Pi = np.c_[np.interp(fr * N, np.arange(N + 1), P[:, 0]), np.interp(fr * N, np.arange(N + 1), P[:, 1])]
        return np.concatenate([(Pi - Ps).ravel(), (P[-1] - Ps[-1]) * 10])
    x = least_squares(r1b, x, bounds=(lo, hi), method='trf', x_scale='jac', max_nfev=300).x
    tvar = 0 if fix_th0 else 1
    def unpack(z): return (th0 if fix_th0 else z[0]), z[tvar:]
    cS = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(S, axis=0).T))]); u = cS / cS[-1]
    def geom(z):
        t0, xx = unpack(z); k, h, L = kgrid(lay, xx, N); P, th = forward(t0, h, k); return P + start, th, k, h, L
    def project(z, u):
        P = geom(z)[0]; out = np.empty(len(S))
        for i, q in enumerate(S):
            c = u[i] * N; lo_ = max(0, int(c) - 40); hi_ = min(N, int(c) + 41)
            A = P[lo_:hi_]; B = P[lo_ + 1:hi_ + 1]; d = B - A; l2 = (d * d).sum(1)
            tt = np.clip(((q - A) * d).sum(1) / np.maximum(l2, 1e-9), 0, 1); C = A + d * tt[:, None]
            j = int(np.argmin(np.hypot(*(C - q).T))); out[i] = (lo_ + j + tt[j]) / N
        return np.maximum.accumulate(out)
    sn = np.arange(N + 1) / N
    def resid(z, u):
        P, th, k, h, L = geom(z)
        ia = np.minimum((u * N).astype(int), N - 1); tt = u * N - ia
        Pu = P[ia] * (1 - tt)[:, None] + P[ia + 1] * tt[:, None]
        d = P[ia + 1] - P[ia]; d /= np.maximum(np.hypot(*d.T), 1e-9)[:, None]; nrm = np.c_[-d[:, 1], d[:, 0]]
        dv = ((Pu - S) * nrm).sum(1); e = np.maximum(0, np.abs(dv) - D)
        r_dev = np.sign(dv) * np.sqrt(dv * dv + (W_D * e) ** 2) * math.sqrt(SAMP / H)
        r_t = np.sqrt(LAM * h * f_time(k) + EPS) - math.sqrt(EPS)
        r_k = math.sqrt(MU2 * h) * k
        sL = sn * L; yard = (sL < YARD) | (sL > L - YARD)
        ak = np.abs(k); w = np.where(yard, 0, 1)
        r_r = np.concatenate([W_STD * np.maximum(0, ak - 1 / R_STD) * math.sqrt(h) * w, W_EXC * np.maximum(0, ak - 1 / R_EXC) * math.sqrt(h) * w])
        A, X, c = lay.unpack(z[tvar:])
        dc = np.abs(np.diff(c)); cm = np.maximum(np.abs(c[1:]), np.abs(c[:-1]))
        r_x = W_RATE * np.maximum(0, dc - X * rate_max(cm)) * 1e2
        r_e = W_END * (P[-1] - Q[-1])
        return np.concatenate([r_dev, r_t, r_r, r_x, r_e, r_k])
    z = np.concatenate(([] if fix_th0 else [th0], x))
    zlo = np.concatenate(([] if fix_th0 else [-np.inf], lo)); zhi = np.concatenate(([] if fix_th0 else [np.inf], hi))
    global W_RATE
    def report(tag, z, u):
        rr = resid(z, u)[:len(S)] / math.sqrt(SAMP / H); a_ = np.abs(rr)
        A_, X_, c_ = lay.unpack(z[tvar:]); dc_ = np.abs(np.diff(c_)); v_ = dc_ / np.maximum(X_, 1e-9) / rate_max(np.maximum(np.abs(c_[1:]), np.abs(c_[:-1])))
        print(f"    {tag}: ずれ 中央値 {np.median(a_):.1f} m 最大 {a_.max():.1f} m 違反 {np.sum(v_ > 1.05)} 最大 {v_.max():.2f} 倍", flush=True)
    if os.environ.get('TEST'): report('1 段目のあと', z, project(z, u))
    for it in range(8):
        W_RATE = 1e3 * 10 ** min(it, 4)
        res = least_squares(resid, np.clip(z, zlo + 1e-12, zhi - 1e-12), args=(u,), bounds=(zlo, zhi), method='trf', x_scale='jac', max_nfev=120)
        z = res.x; u = project(z, u)
        if os.environ.get('TEST'): report(f'2 段目 {it + 1} 回目（評価 {res.nfev}・状態 {res.status}）', z, u)
    P, th, k, h, L = geom(z)
    A, X, c = lay.unpack(z[tvar:])
    dc = np.abs(np.diff(c)); viol = dc / np.maximum(X, 1e-9) / rate_max(np.maximum(np.abs(c[1:]), np.abs(c[:-1])))
    ia = np.minimum((u * N).astype(int), N - 1); tt = u * N - ia
    Pu = P[ia] * (1 - tt)[:, None] + P[ia + 1] * tt[:, None]; d = P[ia + 1] - P[ia]; d /= np.maximum(np.hypot(*d.T), 1e-9)[:, None]
    dv = ((Pu - S) * np.c_[-d[:, 1], d[:, 0]]).sum(1)
    el = {'A': A.tolist(), 'X': X.tolist(), 'c': c.tolist()}
    return P, th, k, h, dv, el, viol

t0 = time.time()
legs = list(zip(range(len(stops) - 1), range(1, len(stops))))
if os.environ.get('TEST'): legs = legs[:int(os.environ['TEST'])]
allP = []; allK = []; allD = []; stopidx = [0]; th_end = None; ELS = []; VIOL = []
for a, b in legs:
    Q = P0[stops[a]:stops[b] + 1]
    start = allP[-1] if allP else Q[0]
    fix = th_end is not None and names[a] not in rev
    ck = f'ckpt_el/{NAME}_{a}.npz'
    if os.path.exists(ck):
        zf = np.load(ck, allow_pickle=True); P, th, k, dv, viol = zf['P'], zf['th'], zf['k'], zf['dv'], zf['viol']; h = float(zf['h']); el = zf['el'].item()
    else:
        ks0 = sS[sidx[a]:sidx[b] + 1]; kk0 = kS[sidx[a]:sidx[b] + 1]
        Pseed = PS[sidx[a]:sidx[b] + 1]; d0 = Pseed[1] - Pseed[0]
        P, th, k, h, dv, el, viol = solve_leg(Q, np.array(start), th_end if fix else 0.0, fix, ks0, kk0, Pseed, math.atan2(d0[1], d0[0]))
        os.makedirs('ckpt_el', exist_ok=True); np.savez(ck, P=P, th=th, k=k, dv=dv, viol=viol, h=h, el=np.array(el, dtype=object))
    gap = float(np.hypot(*(P[-1] - Q[-1]))); P[-1] = Q[-1]
    if allP: P = P[1:]; k = k[1:]
    allP += list(P); allK += list(k); allD += list(dv); stopidx.append(len(allP) - 1); th_end = th[-1]
    ELS.append(el); VIOL += list(viol)
    nc = sum(1 for c in el['c'] if c != 0)
    print(f"  {names[a]}→{names[b]}: 円曲線 {nc}・直線 {len(el['c']) - nc}・緩和曲線 {len(el['X'])}  ずれ 最大 {np.abs(dv).max():.1f} m  終点のずれ {gap:.1f} m  規則の違反 {np.sum(viol > 1.05)} 最大 {viol.max() if len(viol) else 0:.2f} 倍  最小半径 {1 / max(1e-9, np.abs(el['c']).max()):.0f} m  ({time.time() - t0:.0f} 秒)", flush=True)
X = np.array(allP); k = np.array(allK); dv = np.array(allD)
s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(X, axis=0).T))])
print(f"LAM {LAM:g} D {D:g}: 全長 {s[-1] / 1000:.2f} km  ずれ 中央値 {np.median(np.abs(dv)):.1f} m 95% {np.percentile(np.abs(dv), 95):.1f} m 最大 {np.abs(dv).max():.1f} m  左右 {np.mean(dv > 0) * 100:.0f}:{np.mean(dv < 0) * 100:.0f}")
lon = X[:, 0] / K + pts[0][0]; lat = X[:, 1] / 110570 + pts[0][1]
json.dump({'lam': LAM, 'D': D, 'A': np.c_[lon, lat].tolist(), 's': s.tolist(), 'k': k.tolist(), 'stopidx': stopidx, 'dev': dv.tolist(), 'elements': ELS}, open(f'fit_{NAME}.json', 'w'))
