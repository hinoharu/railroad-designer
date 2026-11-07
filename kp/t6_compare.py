# ⑥：入力表から作り直した結果（A の写し）と今の結果（B）を区間・系統ごとに比べる（2026-11-06）。使い方：python3 t6_compare.py 作り直した方 今の方
import json, os, sys, glob, numpy as np
sys.path.insert(0, 'tables'); import net
A, B = sys.argv[1:3]
def num(x, y):
    try:
        x = np.array(x, float); y = np.array(y, float)
    except Exception: return '同じ' if x == y else '違う'
    if x.shape != y.shape: return f'点の数 {x.shape}→{y.shape}'
    return '同じ' if np.array_equal(x, y) else f'最大差 {np.abs(x - y).max():.3g}'
def cmp(f, keys):
    pa, pb = os.path.join(A, f), os.path.join(B, f)
    if not os.path.exists(pa) or not os.path.exists(pb): return {'(ファイル)': 'なし'}
    a, b = json.load(open(pa)), json.load(open(pb)); r = {}
    for k in keys:
        if k in a or k in b: r[k] = num(a.get(k), b.get(k))
    return r
rows = []
for s in net.SECTIONS:
    if s['method'] != 'branch': continue
    i = s['id']; rf = s['route']['file']; df = net.design_files(i)
    res = {'経路': cmp(rf, ['points', 'stations'])}
    if 'hybrid' in s['route']: res['探索後の経路'] = cmp(rf.replace('.json', '_hyb.json'), ['points', 'stations'])
    res['線形'] = cmp(f'fit_{i}.json', ['s', 'dev', 'k'])
    res['高さ指定'] = {**cmp(f'height_spec_{i}_free.json', ['start_z', 'end_z']), **{'gs_' + k: v for k, v in cmp(f'height_spec_{i}.json', ['start_z', 'end_z', 'stations']).items()}}
    res['縦断'] = cmp(df[0], ['z']); res['縦断（駅地平化）'] = cmp(df[1], ['z'])
    ok = all(v == '同じ' for d in res.values() for v in d.values())
    rows.append((i, ok, res))
for i, ok, res in rows:
    print(f"{i:10s} {'一致' if ok else '違いあり'}")
    if not ok:
        for k, d in res.items():
            bad = {x: v for x, v in d.items() if v != '同じ'}
            if bad: print('   ', k, bad)
print('-- 系統')
for f in sorted(glob.glob(os.path.join(A, 'keito2_*.json'))):
    g = os.path.join(B, os.path.basename(f))
    if os.path.getmtime(f) < os.path.getmtime(os.path.join(A, 'build.py')): continue
    same = os.path.exists(g) and open(f, 'rb').read() == open(g, 'rb').read()
    print(f"{os.path.basename(f):40s} {'一致' if same else '違いあり'}")
