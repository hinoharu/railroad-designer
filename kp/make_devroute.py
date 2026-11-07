# 駅間ごとの探索の結果（dev3_A_B.json）をつないで、背蘂線の経路（駅の位置だけから引いた線）を作る（POC、2026-11-05）。
# 出力の形は path.py の経路と同じ（points・stations・stops・vidx）。作図の線（route_sesibe.json）との比べも出す
import json, sys, math
import numpy as np
from geo import metres, project
src, out = sys.argv[1:3]
r = json.load(open(src)); names = [n for n, _ in r['stations']]
pts, stations, vidx, rows = [], [], [], []
ch = 0.0
for a, b in zip(names, names[1:]):
    d = json.load(open(f'dev3_{a}_{b}.json')); p = d['points']
    if not pts: pts = [p[0]]; stations.append((a, 0.0)); vidx.append(0)
    for q in p[1:]: ch += metres(pts[-1], q); pts.append(q)
    stations.append((b, ch)); vidx.append(len(pts) - 1)
    # 作図の線との比べ：探した線の各点から作図の駅間の線までの距離
    ia, ib = r['vidx'][names.index(a)], r['vidx'][names.index(b)]; D = r['points'][ia:ib + 1]
    dev = [min(project(tuple(q), tuple(u), tuple(v))[1] for u, v in zip(D, D[1:])) for q in p]
    Ld = sum(metres(u, v) for u, v in zip(D, D[1:]))
    rows.append((a, b, Ld, d['length'], max(dev), float(np.median(dev))))
json.dump({'points': pts, 'stations': stations, 'stops': names, 'vidx': vidx,
           'note': '駅の位置だけを拘束条件に、地形から引いた線（devline2.py、25‰、重連の想定）。作図の線は route_sesibe.json'}, open(out, 'w'), ensure_ascii=False)
print('駅間｜作図の長さ｜新しい長さ｜差｜作図の線からの離れ 最大・中央値')
for a, b, Ld, L, mx, md in rows: print(f'{a}→{b}｜{Ld / 1000:.2f} km｜{L / 1000:.2f} km｜{(L - Ld) / 1000:+.2f} km｜{mx:.0f} m・{md:.0f} m')
print(f'全体：作図 {sum(x[2] for x in rows) / 1000:.2f} km → {ch / 1000:.2f} km')
