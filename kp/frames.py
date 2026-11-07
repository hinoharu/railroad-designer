# snaps_<名前>.json（ipfit_dbg.py の段ごと・手ごとの記録）から、老門の付近のコマ送りの図のデータを作る
import json, math, sys, os
import numpy as np
os.environ['REVERSE'] = '1'; sys.argv = ['ipfit_all.py', 'x']
src = open('ipfit_all.py').read().split('# 折り返し駅で分ける')[0]; exec(src)
S = json.load(open(sys.argv_[1] if False else 'snaps_dbgs.json'))
r = json.load(open('route_shibetoro_heishi.json')); pts = r['points']; Pl = local(pts)
v = [vv for (n, _), vv in zip(r['stations'], r['vidx']) if n == '老門'][0]; c0 = Pl[v]
toll = lambda X: [[x / K + pts[0][0], y / 110570 + pts[0][1]] for x, y in X]
WIN = 2500.0
def curves_of(V, R):
    out = []; info = []
    if R is None: return out, info
    V = np.array(V)
    for i in range(1, len(V) - 1):
        if np.hypot(*(V[i] - c0)) > 6 * WIN and np.hypot(*(V[i - 1] - c0)) > 6 * WIN: continue
        uin = V[i] - V[i - 1]; uin = uin / np.hypot(*uin); uo = V[i + 1] - V[i]; uo = uo / np.hypot(*uo)
        d1 = math.atan2(uin[0] * uo[1] - uin[1] * uo[0], uin @ uo); j = int(round((R[i - 1] - RCAT[0]) / 10))
        if abs(d1) < 2 * tau[j]: continue
        Pc, k, s, T_ = curve_pts(V[i], uin, d1, R[i - 1], XL[j]); out.append(toll(Pc)); info.append((i, math.degrees(d1), R[i - 1], T_))
    return out, info
frames = []; prevV = None
for sn in S['snaps']:
    V = np.array(sn['V']); near = [i for i in range(len(V)) if np.hypot(*(V[i] - c0)) < WIN]
    if not near: continue
    lo, hi = max(0, min(near) - 1), min(len(V) - 1, max(near) + 1)
    changed = set()
    if prevV is not None:
        for i in range(lo, hi + 1):
            if np.min(np.hypot(*(prevV - V[i]).T)) > 1.0: changed.add(i)
    is_move = sn['tag'].startswith(('取り除く', 'まとめる'))
    if is_move and not changed: prevV = V; continue
    cur, info = curves_of(sn['V'], sn['R'])
    ips = [[*toll([V[i]])[0], i, i in changed] for i in range(lo, hi + 1)]
    allp = np.array(toll(V[lo:hi + 1]) + [p for c in cur for p in c[::5]])
    lon0, lat0 = allp.min(0); lon1, lat1 = allp.max(0)
    span = max(lon1 - lon0, (lat1 - lat0) * 1.42) * 0.55 + 0.003; cx, cy = (lon0 + lon1) / 2, (lat0 + lat1) / 2
    big = [x for x in info if lo <= x[0] <= hi]
    txt = '　'.join(f"交点 {i}：{'左' if d > 0 else '右'} {abs(d):.0f}°・R {R:.0f}・接線長 {T:.0f} m" for i, d, R, T in big if abs(d) > 40)
    frames.append({'title': sn['tag'], 'text': txt or '（老門の付近の交点と直線）', 'bbox': [cx - span, cy - span / 1.42, cx + span, cy + span / 1.42],
                   'tang': toll(V[lo:hi + 1]), 'ips': ips, 'curves': cur})
    prevV = V
json.dump({'orig': r['points'], 'frames': frames}, open('../trace/frames.json', 'w'), ensure_ascii=False)
print(len(frames), [f['title'] for f in frames])
