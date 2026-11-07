# FreeTrain のマップ（rails.json）から、隣り合う駅の間が複線か単線かを読み取る（2026-11-04、ユーザーの了承）
#  1. 線路のマス（高さは無視して平面で）を 8 方向につながる網とみなし、隣り合う 2 駅の間を最短の道でたどる
#  2. 駅の構内（ホームの線路のマスから 3 マス以内）は数えない
#  3. 道のマスごとに、前後 3 マスから進む向きを求め、直角な方向（前後 1 マス以内の幅、左右 3 マス以内）にある線路のマスの
#     直角方向の位置を並べ、0.6 マスより離れた所で分けて、平行な線路の本数を数える
# 使い方：python3 tracks.py rails.json 線の駅の並び.json 出力.json
import json, sys, re, math
from collections import deque
R = json.load(open(sys.argv[1])); LINES = json.load(open(sys.argv[2]))
occ = {}
for x, y, z, c, p, w in R['cells']: occ.setdefault((x, y), c)
wire = {}
for x, y, z, c, p, w in R['cells']: wire[(x, y)] = max(wire.get((x, y), 0), w or 0)   # 架線（RailRoad._wire > 0）。2026-11-07、国後島
plat = {(x, y) for x, y, z, c, p, w in R['cells'] if c == 'ThinPlatform+RailRoadImpl'}
yard = set()
for (x, y) in plat:
    for dx in range(-3, 4):
        for dy in range(-3, 4): yard.add((x + dx, y + dy))
norm = lambda n: re.sub(r'（信）|\(信\)|信号場$|仮乗降場$|（仮）|\(仮\)', '', n)
ST = {norm(n): (l[0], l[1]) for n, l in R['stations'] if l}
NB = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
# 線路の切れ目：行き止まりのマス（隣に線路が 1 マスだけ）から 3〜4 マス先に線路があれば、つながっているとみなす
# （坂の線路などの位置の抜けで、行き止まりの 342 か所のうち 316 か所が 3 マス、26 か所が 4 マス。2026-11-04 に数えた）
JUMP = {}
for c in occ:
    if sum((c[0] + dx, c[1] + dy) in occ for dx, dy in NB) != 1: continue
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            q = (c[0] + dx, c[1] + dy)
            if q in occ and max(abs(dx), abs(dy)) > 2 and dx * dx + dy * dy <= 20:
                JUMP.setdefault(c, []).append(q); JUMP.setdefault(q, []).append(c)
def nearest_cell(p):
    best = None
    for r in range(0, 12):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                q = (p[0] + dx, p[1] + dy)
                if q in occ:
                    d = dx * dx + dy * dy
                    if best is None or d < best[0]: best = (d, q)
        if best: return best[1]
    return None
def path(a, b, limit=4000):
    s, t = nearest_cell(a), nearest_cell(b)
    if not s or not t: return None
    prev = {s: None}; dq = deque([s])
    while dq:
        u = dq.popleft()
        if u == t: break
        if abs(u[0] - s[0]) + abs(u[1] - s[1]) > limit: continue
        for v in [(u[0] + dx, u[1] + dy) for dx, dy in NB] + JUMP.get(u, []):
            if v in occ and v not in prev: prev[v] = u; dq.append(v)
    if t not in prev: return None
    out = [t]
    while out[-1] != s: out.append(prev[out[-1]])
    return out[::-1]
def ntracks(P, i):
    a, b = P[max(0, i - 3)], P[min(len(P) - 1, i + 3)]
    dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1; ux, uy = dx / L, dy / L; px, py = -uy, ux
    x0, y0 = P[i]; offs = []
    for ddx in range(-4, 5):
        for ddy in range(-4, 5):
            q = (x0 + ddx, y0 + ddy)
            if q not in occ: continue
            al = ddx * ux + ddy * uy; pe = ddx * px + ddy * py
            if abs(al) <= 1.0 and abs(pe) <= 3.2: offs.append(pe)
    offs.sort(); n = 1 if offs else 0
    for u, v in zip(offs, offs[1:]):
        if v - u > 0.6: n += 1
    return n
out = []
for line, names in LINES.items():
    for a, b in zip(names, names[1:]):
        A, B = ST.get(norm(a)), ST.get(norm(b))
        if not A or not B: out.append({'line': line, 'from': a, 'to': b, 'note': 'マップに駅がない'}); continue
        P = path(A, B)
        if not P: out.append({'line': line, 'from': a, 'to': b, 'note': '線路でつながらない'}); continue
        ns = [None if P[i] in yard else ntracks(P, i) for i in range(len(P))]
        body = [n for n in ns if n is not None]
        runs = []; r = 0
        for n in ns:
            if n is not None and n >= 2: r += 1
            else:
                if r: runs.append(r)
                r = 0
        if r: runs.append(r)
        out.append({'line': line, 'from': a, 'to': b, 'cells': len(P), 'outside': len(body),
                    'double': sum(1 for n in body if n == 2), 'more': sum(1 for n in body if n >= 3), 'single': sum(1 for n in body if n == 1),
                    'longest_double_run': max(runs) if runs else 0,
                    'wired': sum(1 for i in range(len(P)) if P[i] not in yard and wire.get(P[i], 0) > 0), 'wired_all': sum(1 for q in P if wire.get(q, 0) > 0)})
json.dump(out, open(sys.argv[3], 'w'), ensure_ascii=False, indent=0)
for o in out:
    if 'note' in o: print(f"{o['line']} {o['from']}→{o['to']}：{o['note']}"); continue
    f = (o['double'] + o['more']) / o['outside'] if o['outside'] else 0
    print(f"{o['line']} {o['from']}→{o['to']}：道 {o['cells']} マス（構内の外 {o['outside']}）単線 {o['single']}・複線 {o['double']}・3 本以上 {o['more']}（複線以上の割合 {f:.0%}、最長の連続 {o['longest_double_run']} マス）架線 {o['wired'] / o['outside'] if o['outside'] else 0:.0%}")
