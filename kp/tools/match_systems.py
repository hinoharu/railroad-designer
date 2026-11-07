# 編成グループ（線路上にある編成だけ）の controller の停車の設定の駅と、テンプレのダイヤの列車の停車駅を照合する（2026-11-07）
import sys, os, glob, collections, re
sys.path.insert(0, os.environ.get('SAVEANALYZER', '/home/user/freetrain_exav_alpha3_hino/tools/SaveAnalyzer'))   # FreeTrain のリポジトリの tools/SaveAnalyzer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from query import Save
import nrbf
from oud_trains import trains
from oud_parse import parse, kids
_orig = nrbf.Reader.read_members
def _read_members(self, oid, meta):
    seen = {}; names = []
    for n in meta.members:
        seen[n] = seen.get(n, 0) + 1; names.append(n if seen[n] == 1 else f'{n}#{seen[n]}')
    if names != list(meta.members): meta = nrbf._ClassMeta(meta.name, names, meta.btypes, meta.infos, meta.lib)
    return _orig(self, oid, meta)
nrbf.Reader.read_members = _read_members
norm = lambda n: re.sub(r'（信）|\(信\)|信号場$|仮乗降場$|（仮）|\(仮\)', '', n).replace('安渡移矢港', '安渡移矢岬').replace('板蘂内', '渓臼').replace('白糸', '璃瑠篠')
OUD = sys.argv[2]
r = parse(OUD); ro = kids(r, 'Rosen')[0]; syu = [s.get('Syubetsumei') for s in kids(ro, 'Ressyasyubetsu')]
pat = collections.Counter()
for dirn, name, no, mei, seq in trains(OUD, set(syu)):
    path = [(st, kind) for i, st, kind, a, d in seq if kind in ('1', '2')]
    if len(path) < 2: continue
    stops = tuple(norm(st) for st, kind in path if kind == '1')
    pat[(name, path[0][0], path[-1][0], stops)] += 1
sv = Save(sys.argv[1])
ST = {sv.loc(st.get('baseLocation')): sv.name(st) for st in sv.by_cls['freetrain.world.rail.Station']}
PL = {sv.where(p): sv.station_of(p) for p in sv.by_cls.get('freetrain.world.rail.ThinPlatform', []) if sv.where(p)}
def ctl_of(item):
    while item is not None:
        c = sv.f(item, 'controller')
        if c is not None and 'Delegation' not in c.cls: return c
        item = sv.f(item, 'TrainItem+_ownerGroup') or sv.f(item, '_ownerGroup')
def ctl_stations(c):
    out = set()
    if c is None or not c.cls.endswith('TATTrainController'): return out
    for k, v in sv.pairs(c.get('stations')):
        n = ST.get(sv.loc(k)); out.add(norm(n)) if n else None
    for k, v in sv.pairs(c.get('platforms')):
        n = PL.get(sv.loc(k)); out.add(norm(n)) if n else None
    return out
rows = collections.OrderedDict()
for g in sv.by_cls['freetrain.world.rail.TrainGroup']:
    for it in sv.items(sv.f(sv.f(g, 'items'), 'CollectionBase+list')):
        if it.cls != 'freetrain.world.rail.Train' or sv.enum(it.get('__state')) == 0: continue
        ty = sv.f(it, 'type'); tid = sv.f(ty, 'id') if ty is not None else ''
        n = len(list(sv.items(sv.f(it, 'cars')))); c = ctl_of(it)
        key = (sv.f(g, 'name'), tid[-12:], n, sv.f(c, 'name') if c is not None else '（既定）')
        rows.setdefault(key, {'n': 0, 'ctl': c})['n'] += 1
for (g, tid, n, cn), r in rows.items():
    sts = ctl_stations(r['ctl'])
    print(f'■ {g}（{tid}、{n} 両、線路上 {r["n"]} 編成）controller「{cn}」停車の設定 {len(sts)} 駅')
    if not sts: continue
    sc = []
    for (name, a, b, stops), cnt in pat.items():
        s = set(stops)
        if not s: continue
        cov = len(s & sts) / len(s | sts)   # Jaccard 係数（両方の集合の重なり）
        sc.append((cov, len(s & sts), cnt, name, a, b, len(s)))
    sc.sort(key=lambda x: (-x[0], -x[1]))
    for cov, k, cnt, name, a, b, ns in sc[:4]:
        if cov < 0.3: break
        print(f'    {cov:.0%}（{k}/{ns} 駅）{name} {norm(a)}→{norm(b)} {cnt} 本')
