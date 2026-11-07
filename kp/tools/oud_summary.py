# ダイヤの列車を、種別ごとに「起点→終点（停車駅の並び）」でまとめる（2026-11-07、国後島）
import sys, re
from collections import Counter, defaultdict
from oud_parse import parse, kids
from oud_trains import trains
r = parse(sys.argv[1]); ro = kids(r, 'Rosen')[0]; syu = [s.get('Syubetsumei') for s in kids(ro, 'Ressyasyubetsu')]
pat = defaultdict(Counter)
for dirn, name, no, mei, seq in trains(sys.argv[1], set(syu)):
    # seq: (駅番号, 駅名, 扱い, 着, 発)。扱い（Ekikakushu の先頭）：1 停車、2 通過、3 経由なし（通過の記号なし）
    pts = [(i, st, kind) for i, st, kind, a, d in seq]
    path = [(i, st, kind) for i, st, kind in pts if kind in ('1', '2')]
    if len(path) < 2: continue
    stops = [st for i, st, kind in path if kind == '1']
    key = (name, path[0][1], path[-1][1], tuple(stops))
    pat[name][key] += 1
for name in syu:
    if not pat[name]: continue
    print(f'## {name}（{sum(pat[name].values())} 本）')
    for (n, a, b, stops), c in sorted(pat[name].items(), key=lambda kv: -kv[1]):
        print(f'  {c:3d} 本  {a}→{b}  停車 {len(stops)}：{"・".join(stops)}')
