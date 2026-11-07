# 編成グループごとに、車両のプラグイン（名前・速度）、両数、ダイヤの controller を読む（speed2.py を広げた。2026-11-07、国後島）
import sys, os, collections, re, subprocess, glob, os
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
NAMES = {0: '最高速', 1: '超高速', 2: '高速', 3: '中速', 4: '低速', 5: '超低速'}
SP = {'slow': 4, 'medium': 3, 'fast': 2, 'superb': 1}
cache = {}
def plugin_info(tid):
    if tid in cache: return cache[tid]
    r = (None, None, None)
    for f in subprocess.run(['grep', '-rlF', '--include=plugin.xml', tid.strip('{}'), os.environ.get('FT_PLUGINS', '/home/user/freetrain_exav_alpha3_hino/plugins')], capture_output=True, text=True).stdout.split():
        x = open(f, 'rb').read().decode('cp932', 'replace')
        m = re.search(r'<contribution[^>]*type="train"[^>]*id="\{?%s\}?"(.*?)</contribution>' % re.escape(tid.strip('{}')), x, re.S)
        if m:
            body = m.group(1)
            name = re.search(r'<name>\s*(.*?)\s*</name>', body, re.S); sp = re.search(r'<speed>\s*(\w+)\s*</speed>', body, re.S)
            ds = re.search(r'<description>\s*(.*?)\s*</description>', body, re.S)
            if not (name and name.group(1).strip()) and ds: name = re.match(r'(.*)', re.sub(r'\s+', ' ', ds.group(1))[:28])
            v = sp.group(1).lower() if sp else None
            r = (name.group(1).strip() if name else None, SP.get(v, int(v) if v and v.isdigit() else None), os.path.basename(os.path.dirname(f))); break
    cache[tid] = r; return r
sv = Save(sys.argv[1])
def ctl(item):
    while item is not None:
        c = sv.f(item, 'controller')
        if c is not None and 'Delegation' not in c.cls:
            if 'ReferenceImpl' in c.cls: return ('（既定）', -1)
            m = sv.f(c, 'maxspeed'); return (sv.f(c, 'name'), m if isinstance(m, int) else -1)
        item = sv.f(item, 'TrainItem+_ownerGroup') or sv.f(item, '_ownerGroup')
    return ('（既定）', -1)
c = collections.Counter()
for g in sv.by_cls['freetrain.world.rail.TrainGroup']:
    for it in sv.items(sv.f(sv.f(g, 'items'), 'CollectionBase+list')):
        if it.cls != 'freetrain.world.rail.Train': continue
        ty = sv.f(it, 'type'); tid = sv.f(ty, 'id') if ty is not None else None
        cars = sv.f(it, 'cars'); n = len(list(sv.items(cars))) if cars is not None else None
        if n is None:
            for k in it.fields:
                if 'car' in k.lower() and isinstance(it.fields[k], nrbf.Obj): n = len(list(sv.items(it.fields[k]))); break
        name, ps, plug = plugin_info(tid) if tid else (None, None, None)
        cn, cm = ctl(it)
        c[(sv.f(g, "name"), name or (tid or "")[-22:], plug, n, ps, cn, cm)] += 1
print('編成グループ｜車両（プラグイン）｜両数｜車両の速度｜ダイヤの指定｜編成の数')
for (g, name, plug, n, ps, cn, cm), v in sorted(c.items(), key=lambda kv: str(kv[0][0])):
    eff = cm if cm >= 0 else ps
    print(f'{g}｜{name}（{plug}）｜{n} 両｜{NAMES.get(ps, ps)}｜「{cn}」{NAMES[cm] if cm >= 0 else "なし"} → {NAMES.get(eff, eff)}｜{v}')
