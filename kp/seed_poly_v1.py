# 線形要素の計算（fitel.py）の出発点を、元の折れ線から直接作る（自由曲線の計算を飛ばす。2026-11-03、ユーザーの了承）。
# 折れ線の各頂点の角を円曲線で丸める。半径は、隣の 2 辺の半分ずつに接線長が収まる最大の円（R = min(辺)/2 ÷ tan(|Δ|/2)）を、
# 最小の半径 160 m 〜 直線とみなす境 5000 m に収める（fitel.py の RMIN・KS と同じ値）。折り返し駅の頂点は丸めない。
# 約 30 m ごとに点を取り、fit_<名前>.json（A：経緯度、s：キロ程、k：曲率、stopidx：停車駅の点の番号）に書く。
# 使い方：python3 seed_poly.py 名前
import json, math, sys
import numpy as np
from curves import local
from run import reversals
RMIN, RMAX, STEP = 160.0, 5000.0, 30.0
r = json.load(open('route_shibetoro_heishi.json')); pts = r['points']
K = 111320 * math.cos(math.radians(pts[len(pts) // 2][1]))
P = local(pts)
rev_v = {v for (n, _), v in zip(r['stations'], r['vidx']) if n in set(reversals(r))}
stop_v = [v for (n, _), v in zip(r['stations'], r['vidx']) if n in r['stops']]
# 重なった点を除く（元の番号を覚える）
keep = [0]
for i in range(1, len(P)):
    if np.hypot(*(P[i] - P[keep[-1]])) > 0.5: keep.append(i)
    elif i in rev_v or i in stop_v: keep[-1] = i
Q = P[keep]; orig = keep
# 頂点ごとの丸め：接線の点 a（前の辺の上）、b（次の辺の上）、半径 R、向き
out = []   # (点, 曲率) の列を作る
def arc(i):
    a, v, b = Q[i - 1], Q[i], Q[i + 1]
    d1 = v - a; d2 = b - v; l1 = np.hypot(*d1); l2 = np.hypot(*d2)
    t1, t2 = d1 / l1, d2 / l2
    dl = math.atan2(t1[0] * t2[1] - t1[1] * t2[0], t1 @ t2)
    if abs(dl) < 1e-6 or orig[i] in rev_v: return None
    R = min(l1, l2) / 2 / math.tan(abs(dl) / 2); R = min(max(R, RMIN), RMAX)
    T = R * math.tan(abs(dl) / 2)
    return v - t1 * min(T, l1), v + t2 * min(T, l2), R, dl
pts_out = [(Q[0], 0.0)]
for i in range(1, len(Q) - 1):
    A = arc(i)
    if A is None:
        pts_out.append((Q[i], 0.0)); continue
    a, b, R, dl = A
    # 円弧を 10 m ごとの点で描く（向きは前の辺の向きから dl だけ回る）
    t1 = (Q[i] - Q[i - 1]) / np.hypot(*(Q[i] - Q[i - 1])); th0 = math.atan2(t1[1], t1[0])
    L = R * abs(dl); n = max(1, int(L / 10)); c = math.copysign(1 / R, dl)
    pts_out.append((a, 0.0)); p = a.copy(); th = th0
    for j in range(n):
        h = L / n; thm = th + c * h / 2
        p = p + h * np.array([math.cos(thm), math.sin(thm)]); th += c * h
        pts_out.append((p.copy(), c))
pts_out.append((Q[-1], 0.0))
X = np.array([p for p, _ in pts_out]); C = np.array([c for _, c in pts_out])
s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(X, axis=0).T))])
# 約 30 m ごとに取り直す（曲率は区間の値をそのまま）
sg = np.arange(0, s[-1], STEP); sg = np.append(sg, s[-1])
Xg = np.c_[np.interp(sg, s, X[:, 0]), np.interp(sg, s, X[:, 1])]
idx = np.minimum(np.searchsorted(s, sg, side='right'), len(C) - 1); Cg = C[idx]
# 停車駅の点の番号（元の頂点に最も近い点）
stopidx = [int(np.argmin(np.hypot(*(Xg - P[v]).T))) for v in stop_v]
lon = Xg[:, 0] / K + pts[0][0]; lat = Xg[:, 1] / 110570 + pts[0][1]
json.dump({'A': np.c_[lon, lat].tolist(), 's': sg.tolist(), 'k': Cg.tolist(), 'stopidx': stopidx}, open(f'fit_{sys.argv[1]}.json', 'w'))
R_ = 1 / np.abs(Cg[Cg != 0])
print(f'点 {len(sg)}、全長 {sg[-1] / 1000:.2f} km、曲線の点の半径 中央値 {np.median(R_):.0f} m・160 m の点 {np.mean(R_ <= 160.5) * 100:.0f}%、停車駅 {len(stopidx)}')
