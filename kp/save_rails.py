# セーブから線路のマス（位置・型・向きの番号・架線 wire）と駅・ホームの位置を取り出す
# （claude-workspace freetrain/scratchpad/tracks/rails.py に架線の項目を足した。2026-11-07、国後島。2026-11-08 に kp へ写した）
# 使い方：python3 save_rails.py セーブ.ftgd3 tables/saves/rails_<島>.json。freetrain_exav_alpha3_hino の tools/SaveAnalyzer（query.py・nrbf.py）が要る
import sys, json, glob
sys.path.insert(0, '/home/user/freetrain_exav_alpha3_hino/tools/SaveAnalyzer')
from query import Save
import nrbf
from collections import Counter
sv = Save(sys.argv[1])
cells = []; keys = Counter()
for cls, objs in sv.by_cls.items():
    if not cls.startswith('freetrain.world.rail.') or not (any(k in cls for k in ('RailRoad', 'RailRoadImpl')) or cls.endswith('BlockSystemSignal')): continue
    for o in objs:
        w = sv.where(o)
        if not w or w[0] is None: continue
        pat = sv.f(sv.f(o, 'pattern'), 'id') if sv.f(o, 'pattern') is not None else None
        wire = None
        for k in o.fields:
            if k.endswith('_wire'): wire = o.fields[k]; keys[k] += 1
        cells.append([w[0], w[1], w[2], cls.rsplit('.', 1)[-1], pat, wire])
st = []
for o in sv.by_cls['freetrain.world.rail.Station']:
    st.append([sv.name(o), sv.loc(o.get('baseLocation'))])
plat = [list(sv.where(o)) for o in sv.by_cls.get('freetrain.world.rail.ThinPlatform', []) if sv.where(o)]
json.dump({'cells': cells, 'stations': st, 'platforms': plat}, open(sys.argv[2], 'w'), ensure_ascii=False)
print(len(cells), 'マス', Counter(c[3] for c in cells).most_common(), len(st), '駅', len(plat), 'ホーム')
print('架線の項目名', dict(keys), '架線あり', sum(1 for c in cells if c[5]), 'なし', sum(1 for c in cells if c[5] == 0), '不明', sum(1 for c in cells if c[5] is None))
print('駅の例', st[:5])
