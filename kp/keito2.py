# 系統（区間の並びの版。2026-11-04、ユーザーと決めた「まず線形ありき」）：区間の部分をつないだ経路を、系統の車両の条件で走らせる。
# keito.py（支線の全部 → 幹線の分岐器の位置から終点の駅まで、の形だけ）を一般にしたもの。区間を逆向きに通る部分も扱う。
# 使い方：VMAX=130 TILT=0 TRAIN=170 python3 keito2.py 系統の定義.json [gs]
#   系統の定義：{"name": 名前, "pieces": [[区間, 起点, 終点], ...], "stops": [停車駅, ...]}
#     起点・終点は、その区間の縦断のキロ程（m）か、"start"・"end"（区間の端）か、"J:区間:start|end"（その区間の分岐器の位置を、この区間の
#     キロ程に直したもの）か、"st:駅名"（この区間の駅の位置）。起点 > 終点なら、その区間を逆向きに通る
#   gs：［駅地平化］の縦断（区間ごとの DESIGN の 2 番目）で走らせる。出力は keito2_<名前>[_gs].json
import json, sys
import numpy as np
import run
# 区間ごとの縦断（高さ指定なし、駅地平化）と、制限速度の区間（曲線）。fit・route は分岐器の位置の換算に使う
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'tables'))
import net   # 入力表から（2026-11-06、⑤の段 2。それまではここに直接書いていた）
DESIGN = net.DESIGN
CURVES = {'ipg': 'curves_fipgh.json'}
# 線の順位（network.json）。同じ駅が 2 つの区間にあるとき（分岐する駅）は、順位が上の区間の駅の位置を使う（その駅は上位の線の上にある）
RANK = net.RANK
spec = json.load(open(sys.argv[1])); GS = len(sys.argv) > 2 and sys.argv[2] == 'gs'
load = lambda f: json.load(open(f))
des = {k: load(v[1 if GS else 0]) for k, v in DESIGN.items() if all(__import__('os').path.exists(x) for x in v)}

def junction_on(sec, br, w):
    """区間 br の端 w の分岐器の位置を、区間 sec（br がつながる上位の区間）の縦断のキロ程で"""
    fb = load(f'fit_{br}.json'); j = fb['junctions'][w] if 'junctions' in fb else fb['junction']
    assert j['trunk'] == f'fit_{sec}.json', (br, w, j['trunk'], sec)
    fp = load(f'fit_{sec}.json'); rp = load(f'route_f{sec}.json')
    return float(np.interp(j['s'], fp['s'], rp['s']))

def pos(sec, v):
    d = des[sec]
    if isinstance(v, (int, float)): return float(v)
    if v == 'start': return 0.0
    if v == 'end': return float(d['s'][-1])
    if v.startswith('J:'): _, br, w = v.split(':'); return junction_on(sec, br, w)
    if v.startswith('st:'): return float(dict(d['stations'])[v[3:]])
    raise ValueError(v)

S, Z, stations, cv, path = [], [], [], [], []
off = 0.0
for sec, a_, b_ in spec['pieces']:
    d = des[sec]; a, b = pos(sec, a_), pos(sec, b_); rev = a > b; lo, hi = min(a, b), max(a, b)
    s = np.array(d['s']); z = np.array(d['z'])
    grid = np.arange(lo, hi + 1e-6, 20.0)
    if grid[-1] < hi - 1e-6: grid = np.r_[grid, hi]
    zz = np.interp(grid, s, z)
    if rev: grid, zz = grid[::-1], zz[::-1]
    ss = off + np.abs(grid - a)
    if S and abs(ss[0] - S[-1]) < 1e-6: ss, zz = ss[1:], zz[1:]
    S += ss.tolist(); Z += zz.tolist()
    for n, c in d['stations']:
        if lo - 0.5 <= c <= hi + 0.5: stations.append((n, off + abs(c - a), RANK[sec]))
    for c in load(CURVES.get(sec, f'curves_f{sec}.json')):
        if c['s1'] > lo and c['s0'] < hi:
            q0, q1 = off + abs(max(c['s0'], lo) - a), off + abs(min(c['s1'], hi) - a)
            cv.append(dict(c, s0=min(q0, q1), s1=max(q0, q1)))
    path.append([sec, round(a), round(b)]); off += hi - lo
cv.sort(key=lambda c: c['s0'])
best = {}
for n, q, r in stations:
    if n not in best or r < best[n][1]: best[n] = (q, r)
stations = sorted(((n, q) for n, (q, r) in best.items()), key=lambda x: x[1])
miss = [n for n in spec['stops'] if n not in dict(stations)]
if miss: raise SystemExit(f'停車駅が経路にない：{miss}')
d = {'s': S, 'z': Z, 'stations': stations, 'stops': spec['stops']}
x, v, t, si, stops, vh = run.simulate(d, True, cv)
legs = [t[b] - t[a] for a, b in zip(si, si[1:])]
print(f'{spec["name"]}{"（駅地平化）" if GS else ""}：{off / 1000:.2f} km、走行 {sum(legs) / 60:.1f} 分（停車を除く）、最高 {v.max() * 3.6:.0f} km/h')
print('  経路：' + ' → '.join(f'{p[0]} {p[1] / 1000:.2f}→{p[2] / 1000:.2f} km' for p in path))
for (p, q), L_ in zip(zip(spec['stops'], spec['stops'][1:]), legs): print(f'    {p}→{q} {L_ / 60:.1f} 分')
json.dump({'name': spec['name'], 'path': path, 's': S, 'z': Z, 'stations': stations, 'stops': spec['stops'],
           'x': x.tolist(), 'v': (v * 3.6).tolist(), 'lim': (vh * 3.6).tolist(), 'zone': (run.simulate.vl * 3.6).tolist(), 'run_min': sum(legs) / 60},
          open(f'keito2_{spec["name"]}{"_gs" if GS else ""}.json', 'w'), ensure_ascii=False)
