# 交点法の試作（2026-11-03、ユーザーの提案）：直線を先に決め、その間を規格の曲線でつなぐ。
#  1. 元の折れ線を、ずれの上限 D（30 m）の幅で簡略化する（ダグラス・ポイカー法）。辺を直線、頂点を交点とする
#  2. 同じ向きの交点が近すぎて、最小半径の曲線でも 2 つが入らない所は、外側の 2 本の直線の交点に 1 つにまとめる
#  3. 交点ごとに、規格の半径（160〜5000 m、10 m 刻み）の単曲線（緩和曲線＋円曲線＋緩和曲線。緩和曲線の長さは規則
#     X = max(0.4C, 0.007CV) で半径から決まる）を全部試し、費用＝ずれ（元の折れ線からの距離の 2 乗の積分 ÷ 30 m）
#     ＋ LAM × 走行時間の増分（秒）を求める
#  4. 隣り合う曲線が重ならない（接線長の和 ≤ 直線の長さ）組み合わせのうち、費用の合計が最小のものを動的計画法で選ぶ
# 使い方：python3 ipfit.py 区間の始点の駅名   → ip_<駅名>.json（10 m ごとの点と曲率）
import json, math, sys, time
import numpy as np
from scipy.spatial import cKDTree
from curves import local
from speed import smooth
D, LAM, H, W_D = 30.0, 1e5, 30.0, 10.0
RCAT = np.arange(160.0, 5000.1, 10.0)
t0 = time.time()
r = json.load(open('route_shibetoro_heishi.json')); pts = r['points']; P = local(pts)
K = 111320 * math.cos(math.radians(pts[len(pts) // 2][1]))
stops = [v for (n, _), v in zip(r['stations'], r['vidx']) if n in r['stops']]
names = [n for (n, _), v in zip(r['stations'], r['vidx']) if n in r['stops']]
a = names.index(sys.argv[1]); Q0 = P[stops[a]:stops[a + 1] + 1]
Q = [Q0[0]]
for q in Q0[1:]:
    if np.hypot(*(q - Q[-1])) > 0.5: Q.append(q)
Q = np.array(Q)
# 元の折れ線を 2 m ごとの点にして、距離を速く求める
dense = [Q[0]]
for p_, q_ in zip(Q, Q[1:]):
    n = max(1, int(np.hypot(*(q_ - p_)) / 2)); dense += [p_ + (q_ - p_) * t for t in np.linspace(0, 1, n + 1)[1:]]
tree = cKDTree(np.array(dense))
def dist(X): return tree.query(X)[0]
# 1. 簡略化
def dp(i, j, out):
    A_, B_ = Q[i], Q[j]; d = B_ - A_; L = np.hypot(*d) or 1
    e = np.abs(d[0] * (Q[i + 1:j, 1] - A_[1]) - d[1] * (Q[i + 1:j, 0] - A_[0])) / L if j > i + 1 else np.array([])
    if len(e) and e.max() > D:
        k = i + 1 + int(e.argmax()); dp(i, k, out); out.append(k); dp(k, j, out)
sel = [0]; dp(0, len(Q) - 1, sel); sel.append(len(Q) - 1); V_ = Q[sel]
# 規格の曲線の表（半径ごと）
Vk = smooth(RCAT); C = np.minimum(7.552 * Vk * Vk / RCAT, 105.0); XL = np.maximum(np.maximum(0.4 * C, 0.007 * C * Vk), 1.0)
tau = XL / (2 * RCAT); pS = XL ** 2 / (24 * RCAT); mS = XL / 2 - XL ** 3 / (240 * RCAT ** 2)
def ftime(k):   # 1 m あたりの走行時間の増分（秒）
    k = np.maximum(np.abs(k), 1e-9); return 3.6 / smooth(1 / k) - 3.6 / 130
def geom(V_):
    d = np.diff(V_, axis=0); L = np.hypot(*d.T); u = d / L[:, None]
    dl = np.arctan2(u[:-1, 0] * u[1:, 1] - u[:-1, 1] * u[1:, 0], (u[:-1] * u[1:]).sum(1))
    return L, u, dl
def tlen(dl):   # 交点ごとの、半径ごとの接線長（入らない半径は inf）
    ad = np.abs(dl)[:, None]; T = (RCAT + pS) * np.tan(ad / 2) + mS
    return np.where(ad >= 2 * tau, T, np.inf)
# 2. 同じ向きの交点が近すぎる所をまとめる。反向の交点が近すぎる所（描いた揺れが規則の許す曲線よりきつい所）は、
#    交角の小さい方の交点を取り除き、前後の直線を延ばしてつなぐ
n_merge = n_drop = 0
while True:
    L, u, dl = geom(V_); T = tlen(dl); Tmin = T.min(1)
    bad = [i for i in range(len(dl) - 1) if np.sign(dl[i]) == np.sign(dl[i + 1]) and Tmin[i] + Tmin[i + 1] > L[i + 1]]
    rev = [i for i in range(len(dl) - 1) if np.sign(dl[i]) != np.sign(dl[i + 1]) and Tmin[i] + Tmin[i + 1] > L[i + 1]]
    # 端の直線（駅から最初の交点まで）に入らない曲線も
    ends = [i for i in (0, len(dl) - 1) if Tmin[i] > L[i if i == 0 else i + 1]]
    if not bad and not rev and not ends: break
    if not bad:
        if rev:
            i = min(rev, key=lambda i: L[i + 1]); drop = i if abs(dl[i]) < abs(dl[i + 1]) else i + 1
        else:
            drop = ends[0]
        V_ = np.delete(V_, drop + 1, axis=0); n_drop += 1; continue
    n_merge += 1
    i = min(bad, key=lambda i: L[i + 1])   # 最も短い直線から
    # 頂点 i+1 と i+2（V_ の番号）を、辺 i と辺 i+2 の延長の交点 1 つに
    p1, d1 = V_[i], u[i]; p2, d2 = V_[i + 3], -u[i + 2]
    M = np.array([d1, -d2]).T; t = np.linalg.solve(M, p2 - p1); X_ = p1 + d1 * t[0]
    V_ = np.vstack([V_[:i + 1], [X_], V_[i + 3:]])
L, u, dl = geom(V_); T = tlen(dl); n = len(dl)
# 3. 交点ごと・半径ごとの費用
def curve_pts(ip, uin, dl1, R, X):
    """交点 ip、入る向き uin、交角 dl1（符号つき）、半径 R、緩和曲線長 X の単曲線を、TS から ST まで 5 m ごとの点に"""
    ad = abs(dl1); c = math.copysign(1 / R, dl1); A = R * ad - X
    T_ = (R + X * X / (24 * R)) * math.tan(ad / 2) + X / 2 - X ** 3 / (240 * R * R)
    Ltot = 2 * X + A; m = max(2, int(Ltot / 5)); s = np.linspace(0, Ltot, m + 1)
    k = np.where(s < X, c * s / X, np.where(s < X + A, c, c * (Ltot - s) / X))
    th0 = math.atan2(uin[1], uin[0]); h = np.diff(s)
    th = th0 + np.concatenate([[0], np.cumsum(h * (k[1:] + k[:-1]) / 2)])
    ph = (th[1:] + th[:-1]) / 2
    X0 = ip - uin * T_
    Pc = X0 + np.vstack([[0, 0], np.cumsum(h[:, None] * np.c_[np.cos(ph), np.sin(ph)], axis=0)])
    return Pc, k, s, T_
def pen(d): e = np.maximum(0, d - D); return d * d + (W_D * e) ** 2
COST = np.full((n, len(RCAT)), np.inf)
for i in range(n):
    ip = V_[i + 1]; uin = u[i]; uout = u[i + 1]
    for j, R in enumerate(RCAT):
        if not np.isfinite(T[i, j]) or T[i, j] > L[i] or T[i, j] > L[i + 1]: continue
        Pc, k, s, T_ = curve_pts(ip, uin, dl[i], R, XL[j])
        h = np.gradient(s)
        dv = (pen(dist(Pc)) * h).sum() / H
        # 曲線に置き換えた直線の部分（TS→交点→ST）のずれを引く
        tl = np.linspace(0, T_, max(2, int(T_ / 5)) + 1)
        tp = np.vstack([ip - uin[None] * (T_ - tl)[:, None], ip + uout[None] * tl[:, None]])
        dv0 = (pen(dist(tp)) * (T_ / max(1, len(tl) - 1))).sum() / H
        COST[i, j] = dv - dv0 + LAM * (ftime(k) * h).sum()
# 4. 動的計画法（隣り合う 2 つの曲線の接線長の和 ≤ 間の直線の長さ）
best = COST[0].copy(); back = np.zeros((n, len(RCAT)), int)
for i in range(1, n):
    ok = (T[i - 1][:, None] + T[i][None, :]) <= L[i]
    tot = np.where(ok, best[:, None], np.inf)
    back[i] = tot.argmin(0); best = tot.min(0) + COST[i]
if not np.isfinite(best.min()): sys.exit('曲線の入らない所がある（反向曲線の間の直線が短すぎる）')
ch = [int(best.argmin())]
for i in range(n - 1, 0, -1): ch.append(back[i][ch[-1]])
ch = ch[::-1]
# 5. 交点を動かす（2026-11-03、ユーザーと合意）：直線を平行に動かすのではなく、交点を角の二等分線の方向に動かす
#    （両側の直線は隣の交点を軸に回る）。交点ごとに、動かす量（−D〜+D、5 m 刻み）とその交点の半径を全部試し、
#    両隣の曲線の半径はそのままで、TS（隣の隣の曲線の終わり）から TS までの費用（ずれ＋走行時間）が最も下がるものを選ぶ。
#    これを全部の交点について SWEEPS 回くり返し、最後に半径を動的計画法で選び直す
SWEEPS = int(__import__('os').environ.get('SWEEPS', '3')); OFFS = np.arange(-D, D + 0.1, 5.0)
def ipdata(V_, i, R):
    """交点 i（1..n）の、入る向き・交角・半径 R での接線長"""
    uin = V_[i] - V_[i - 1]; uin /= np.hypot(*uin); uo = V_[i + 1] - V_[i]; uo /= np.hypot(*uo)
    d1 = math.atan2(uin[0] * uo[1] - uin[1] * uo[0], uin @ uo); j = int(round((R - RCAT[0]) / 10))
    ad = abs(d1); T_ = (R + pS[j]) * math.tan(ad / 2) + mS[j] if ad >= 2 * tau[j] else math.inf
    return uin, uo, d1, T_, j
def local_cost(V_, Rs, lo, hi):
    """交点 lo の曲線の終わり（ST）から交点 hi の曲線の始まり（TS）までの費用。lo・hi は 0 か n+1 なら駅"""
    segs = []; ends = []
    for i in range(lo, hi + 1):
        if i == 0 or i == len(V_) - 1: ends.append((V_[i], V_[i])); continue
        uin, uo, d1, T_, j = ipdata(V_, i, Rs[i - 1])
        if not np.isfinite(T_): return math.inf
        ends.append((V_[i] - uin * T_, V_[i] + uo * T_))
        if lo < i < hi: segs.append((i, uin, d1, j))
    # 直線の長さ（ST(i) から TS(i+1)）が負なら入らない
    for i in range(hi - lo):
        st = ends[i][1]; ts = ends[i + 1][0]; e = V_[lo + i + 1] - V_[lo + i]
        if (ts - st) @ e < -1e-6: return math.inf
    cost = 0.0
    for i in range(hi - lo):   # 直線
        st = ends[i][1]; ts = ends[i + 1][0]; Ls = np.hypot(*(ts - st))
        if Ls > 0:
            m = max(1, int(Ls / 5)); X = st + (ts - st) * np.linspace(0, 1, m + 1)[:, None]
            cost += (pen(dist(X)) * (Ls / m)).sum() / H
    for i, uin, d1, j in segs:   # 曲線
        Pc, k, s_, T_ = curve_pts(V_[i], uin, d1, RCAT[j], XL[j]); h = np.gradient(s_)
        cost += (pen(dist(Pc)) * h).sum() / H + LAM * (ftime(k) * h).sum()
    return cost
Rs = [RCAT[j] for j in ch]
RC20 = RCAT[::2]
def total(V_, Rs): return local_cost(V_, Rs, 0, len(V_) - 1)
c0 = total(V_, Rs)
for sw in range(SWEEPS):
    moved = 0
    for i in range(1, len(V_) - 1):
        lo, hi = max(0, i - 2), min(len(V_) - 1, i + 2)
        uin = V_[i] - V_[i - 1]; uin /= np.hypot(*uin); uo = V_[i + 1] - V_[i]; uo /= np.hypot(*uo)
        bis = uin - uo; nb = np.hypot(*bis)
        if nb < 1e-9: continue
        bis /= nb   # 外側（曲線の中心と反対の向き）
        best_ = (local_cost(V_, Rs, lo, hi), 0.0, Rs[i - 1])
        base = V_[i].copy()
        for off in OFFS:
            V_[i] = base + bis * off
            for R in RC20:
                Rs2 = list(Rs); Rs2[i - 1] = R
                c = local_cost(V_, Rs2, lo, hi)
                if c < best_[0] - 1e-6: best_ = (c, off, R)
        V_[i] = base + bis * best_[1]; Rs[i - 1] = best_[2]
        if best_[1] != 0: moved += 1
    c1 = total(V_, Rs)
    print(f"  交点を動かす {sw + 1} 回目：動かした交点 {moved}・費用 {c0:.4g} → {c1:.4g}（{time.time() - t0:.0f} 秒）", flush=True); c0 = c1
# 半径を 10 m 刻みで選び直す（動的計画法）
L, u, dl = geom(V_); T = tlen(dl); n = len(dl)
COST = np.full((n, len(RCAT)), np.inf)
for i in range(n):
    ip = V_[i + 1]; uin = u[i]; uout = u[i + 1]
    for j, R in enumerate(RCAT):
        if not np.isfinite(T[i, j]) or T[i, j] > L[i] or T[i, j] > L[i + 1]: continue
        Pc, k, s, T_ = curve_pts(ip, uin, dl[i], R, XL[j]); h = np.gradient(s)
        dv = (pen(dist(Pc)) * h).sum() / H
        tl = np.linspace(0, T_, max(2, int(T_ / 5)) + 1)
        tp = np.vstack([ip - uin[None] * (T_ - tl)[:, None], ip + uout[None] * tl[:, None]])
        dv0 = (pen(dist(tp)) * (T_ / max(1, len(tl) - 1))).sum() / H
        COST[i, j] = dv - dv0 + LAM * (ftime(k) * h).sum()
best = COST[0].copy(); back = np.zeros((n, len(RCAT)), int)
for i in range(1, n):
    ok = (T[i - 1][:, None] + T[i][None, :]) <= L[i]
    tot = np.where(ok, best[:, None], np.inf); back[i] = tot.argmin(0); best = tot.min(0) + COST[i]
ch = [int(best.argmin())]
for i in range(n - 1, 0, -1): ch.append(back[i][ch[-1]])
ch = ch[::-1]
# 線形を組み立てる（10 m ごとの点と曲率）
out = [(V_[0], 0.0)]
for i, j in enumerate(ch):
    Pc, k, s, T_ = curve_pts(V_[i + 1], u[i], dl[i], RCAT[j], XL[j])
    out += [(p_, kk) for p_, kk in zip(Pc, k)]
out.append((V_[-1], 0.0))
X = np.array([p_ for p_, _ in out]); kk = np.array([q for _, q in out])
s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(X, axis=0).T))])
sg = np.arange(0, s[-1], 10.0); Xg = np.c_[np.interp(sg, s, X[:, 0]), np.interp(sg, s, X[:, 1])]
kg = kk[np.minimum(np.searchsorted(s, sg, side='right'), len(kk) - 1)]
dvA = dist(Xg); tA = (ftime(kg) * 10).sum()
# 元の折れ線の点（2 m ごと）から線形までの距離
dvB = cKDTree(Xg).query(np.array(dense))[0]
Rs = RCAT[ch]
print(f"まとめた交点 {n_merge}・取り除いた交点 {n_drop}")
print(f"{names[a]}→{names[a + 1]}：直線 {n + 1} 本・曲線 {n}（半径の中央値 {np.median(Rs):.0f} m、最小 {Rs.min():.0f} m）  "
      f"ずれ（線形→元の線）中央値 {np.median(dvA):.1f} m・95% {np.percentile(dvA, 95):.1f} m・最大 {dvA.max():.1f} m  "
      f"（元の線→線形）最大 {dvB.max():.1f} m  曲線による時間の増分 {tA / 60:.2f} 分  計算 {time.time() - t0:.0f} 秒")
lon = Xg[:, 0] / K + pts[0][0]; lat = Xg[:, 1] / 110570 + pts[0][1]
json.dump({'A': np.c_[lon, lat].tolist(), 's': sg.tolist(), 'k': kg.tolist(), 'R': Rs.tolist(), 'ip': (np.c_[V_[:, 0] / K + pts[0][0], V_[:, 1] / 110570 + pts[0][1]]).tolist()}, open(f'ip_{names[a]}{__import__("os").environ.get("TAG", "")}.json', 'w'), ensure_ascii=False)
