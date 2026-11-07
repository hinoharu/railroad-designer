# 編成グループごとに、線路上にある編成の数（Train.__state）と、ダイヤの controller が停車の設定を持つ駅を出す（2026-11-07、国後島）
import sys, os, glob, collections, re
sys.path.insert(0, os.environ.get('SAVEANALYZER', '/home/user/freetrain_exav_alpha3_hino/tools/SaveAnalyzer'))   # FreeTrain のリポジトリの tools/SaveAnalyzer
from query import Save
import nrbf
_orig = nrbf.Reader.read_members
def _read_members(self, oid, meta):
    seen = {}; names = []
    for n in meta.members:
        seen[n] = seen.get(n, 0) + 1; names.append(n if seen[n] == 1 else f'{n}#{seen[n]}')
    if names != list(meta.members): meta = nrbf._ClassMeta(meta.name, names, meta.btypes, meta.infos, meta.lib)
    return _orig(self, oid, meta)
nrbf.Reader.read_members = _read_members
sv = Save(sys.argv[1])
ST = {}   # 位置 → 駅名（駅の baseLocation と、ホームの位置→駅）
for st in sv.by_cls['freetrain.world.rail.Station']: ST[sv.loc(st.get('baseLocation'))] = sv.name(st)
PL = {}
for p in sv.by_cls.get('freetrain.world.rail.ThinPlatform', []):
    w = sv.where(p)
    if w: PL[w] = sv.station_of(p)
def ctl_of(item):
    while item is not None:
        c = sv.f(item, 'controller')
        if c is not None and 'Delegation' not in c.cls: return c
        item = sv.f(item, 'TrainItem+_ownerGroup') or sv.f(item, '_ownerGroup')
    return None
def ctl_stations(c):
    out = set()
    if c is None or not c.cls.endswith('TATTrainController'): return out
    for k, v in sv.pairs(c.get('stations')): out.add(ST.get(sv.loc(k), f'?{sv.loc(k)}'))
    for k, v in sv.pairs(c.get('platforms')): out.add(PL.get(sv.loc(k), f'?p{sv.loc(k)}'))
    return out
rows = collections.OrderedDict()
for g in sv.by_cls['freetrain.world.rail.TrainGroup']:
    for it in sv.items(sv.f(sv.f(g, 'items'), 'CollectionBase+list')):
        if it.cls != 'freetrain.world.rail.Train': continue
        ty = sv.f(it, 'type'); tid = sv.f(ty, 'id') if ty is not None else ''
        cars = sv.f(it, 'cars'); n = len(list(sv.items(cars))) if cars is not None else None
        state = sv.enum(it.get('__state'))
        c = ctl_of(it)
        key = (sv.f(g, 'name'), tid[-12:], n, sv.f(c, 'name') if c is not None else '（既定）')
        r = rows.setdefault(key, {'n': 0, 'states': collections.Counter(), 'ctl': c})
        r['n'] += 1; r['states'][state] += 1
for (g, tid, n, cn), r in rows.items():
    sts = ctl_stations(r['ctl'])
    print(f'{g}｜{tid}｜{n} 両｜編成 {r["n"]}（状態 {dict(r["states"])}）｜controller「{cn}」停車の設定 {len(sts)} 駅：{"・".join(sorted(sts))[:200]}')
