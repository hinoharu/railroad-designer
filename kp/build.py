# 入力表（tables/sections.json・systems.json）から、経路・線形・地盤・高さの指定表・縦断・系統の走行までを 1 本で計算する
# （2026-11-06、⑤プログラム化の段 2。それまでは区間ごとに chain_*.sh・rerun_*.sh を手で書いていた。手順の一覧は
# docs/inventory/steps.md）。
#
# 使い方：python3 build.py [--dry-run] [--only id,id] [--remake-route] [--no-systems] [--force]
#   既定では、入力表の行（と、つながる上位の区間の結果）が前回から変わった区間と、その下位の区間・系統だけを計算する。
#   区間の順は、上位の区間（deps）を先にする。手順ごとに済んだ印（.build/<id>_<手順>_<ハッシュ>.done）を残すので、
#   止まっても同じコマンドで続きから再開できる（2026-11-03、ユーザーの指定：長い計算は途中から再開できる作りに）
#   --dry-run：実行せずにコマンドだけを出す。--remake-route：経路のファイルがあっても駅の並びから作り直す（⑥の試験用）。
#   --force：済んだ印を無視して、対象の区間をすべて計算し直す
#   --routes-only：経路だけを作って止まる（区間を足したときに、駅の並びと折り返しを確かめる）
#   --mark-existing：結果のファイルがある段に、今のハッシュで済んだ印を付けて止まる（複製したばかりで印がないとき、ハッシュの付け方を変えたとき）
#   系統のあとに、駅レーダーサイトへ渡すファイルを export.py で書き出す（段 4、2026-11-07。--no-systems のときは書き出さない）
# 古い手順の区間（method が legacy：特急の経路 ipg、散布線 sanpu）は計算しない。縦断のファイルの中身のハッシュだけを、
# 下位の区間が変わったかの判定に使う
import hashlib, json, math, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tables'))
import net
import numpy as np

ARGS = sys.argv[1:]
DRY = '--dry-run' in ARGS; REMAKE = '--remake-route' in ARGS; FORCE = '--force' in ARGS; NOSYS = '--no-systems' in ARGS; CHECK = '--check-spec' in ARGS
ROUTES_ONLY = '--routes-only' in ARGS   # 経路だけを作って止まる（区間を足したときの確認用。2026-11-07）
MARK = '--mark-existing' in ARGS   # 結果のファイルがある段に、今のハッシュで済んだ印を付けて止まる（複製したばかりで印がないとき、ハッシュの付け方を変えたとき。2026-11-07）
ONLY = None
if '--only' in ARGS: ONLY = set(ARGS[ARGS.index('--only') + 1].split(','))
os.makedirs('.build', exist_ok=True)

def sha(*parts):
    h = hashlib.sha1()
    for p in parts: h.update(p if isinstance(p, bytes) else json.dumps(p, ensure_ascii=False, sort_keys=True).encode())
    return h.hexdigest()[:12]

def file_hash(*fs):
    return sha(*[open(f, 'rb').read() if os.path.exists(f) else b'(missing)' for f in fs])

def sh(cmd, env=None, log=None):
    """コマンドを実行する。env は追加の環境変数。log があれば標準出力・標準エラーをそこへ"""
    e = ' '.join(f"{k}='{v}'" for k, v in (env or {}).items())
    line = (e + ' ' if e else '') + cmd + (f' > {log} 2>&1' if log else '')
    print('  $', line, flush=True)
    if DRY: return
    full = dict(os.environ, **{k: str(v) for k, v in (env or {}).items()})
    r = subprocess.run(cmd + (f' > {log} 2>&1' if log else ''), shell=True, env=full)
    if r.returncode: raise SystemExit(f'失敗（終了コード {r.returncode}）：{line}')

def step(sid, name, h, fn):
    mark = f'.build/{sid}_{name}_{h}.done'
    if os.path.exists(mark) and not FORCE: print(f'  （済み）{name}'); return
    fn()
    if not DRY: open(mark, 'w').close()

# --- 経路 -----------------------------------------------------------------------------------------------------------
def drop_turnback(pts, st, vidx, within=1000.0):
    """make_routes6.py の drop_turnback と同じ（始点の駅の先の折り返しを除く。2026-11-06、散布泊）"""
    K = 111320 * math.cos(math.radians(pts[0][1])); xy = [((p[0] - pts[0][0]) * K, (p[1] - pts[0][1]) * 110540) for p in pts]
    s = 0.0
    for i in range(1, len(xy) - 1):
        ax, ay = xy[i][0] - xy[i - 1][0], xy[i][1] - xy[i - 1][1]; bx, by = xy[i + 1][0] - xy[i][0], xy[i + 1][1] - xy[i][1]
        s += math.hypot(ax, ay)
        if s > within: return pts, st, vidx
        ang = abs(math.degrees(math.atan2(ax * by - ay * bx, ax * bx + ay * by)))
        if ang >= 150:
            l2 = bx * bx + by * by or 1.0; t = max(0.0, min(1.0, (-xy[i][0] * bx - xy[i][1] * by) / l2))
            q = (xy[i][0] + bx * t, xy[i][1] + by * t); cut = s + math.hypot(bx, by) * t
            print(f'  折り返しを除いた：駅から {s:.0f} m 先で {ang:.0f}° 折り返し（{cut:.0f} m 分を除く）')
            new = [[pts[0][0] + q[0] / K, pts[0][1] + q[1] / 110540]] + pts[i + 1:]
            return new, [(n, max(0.0, c - cut)) for n, c in st], [0] + [v - i for v in vidx[1:]]
    return pts, st, vidx

def make_route(s):
    r = s['route']; f = r['file']
    print(f"  経路：{s['island']} {'・'.join(r['stops'])} → {f}")
    if DRY: return
    from path import route
    import re   # path.py の idx は駅名の末尾の「信号場」「仮乗降場」を除いて比べるので、同じく除いて渡す（古い経路のファイルは付けたまま記録している）
    pts, st, sn, vidx = route(s['island'], [re.sub('(信号場|仮乗降場)$', '', n) for n in r['stops']])
    # 同じ点が続く所（駅が作図の線のつなぎ目の頂点にあるとき）を 1 点にする（2026-11-07、国後島の底吼・浦雲泊。長さ 0 の線分を線形の当てはめに渡さない）
    keep = [i for i in range(len(pts)) if i == 0 or math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) > 1e-9]
    if len(keep) < len(pts):
        idx = {i: k for k, i in enumerate(keep)}; back = lambda v: idx[v] if v in idx else idx[max(i for i in keep if i < v)]
        print(f'  同じ点が続く所を {len(pts) - len(keep)} か所除いた'); vidx = [back(v) for v in vidx]; pts = [pts[i] for i in keep]
    if r.get('turnback'): pts, st, vidx = drop_turnback(pts, st, vidx)
    if r.get('turnback_end'):   # 終点の駅の先の折り返しも除く（2026-11-07、国後島の仁岸寄：駅の点が折り返しの頂点の 5 m 先にある）
        n = len(pts); pts, st, vidx = drop_turnback(pts[::-1], [(a, st[-1][1] - c) for a, c in st[::-1]], [n - 1 - v for v in vidx[::-1]])
        n = len(pts); pts, st, vidx = pts[::-1], [(a, st[-1][1] - c) for a, c in st[::-1]], [n - 1 - v for v in vidx[::-1]]
    json.dump({'points': pts, 'stations': st, 'stops': sn, 'vidx': vidx}, open(f, 'w'), ensure_ascii=False)

def route_file(s):
    r = s['route']; return r['file'].replace('.json', '_hyb.json') if 'hybrid' in r else r['file']

# --- 高さの指定表 -----------------------------------------------------------------------------------------------------
def make_spec(s):
    """規則：駅地平化の側は、経路の全駅を地平（−2〜+2 m）にする。ただし上位の線につながる端の駅と、施工基面を前の区間に
    合わせる始点の駅は除く（端の高さは上位の線の縦断で決まるため）。表の profile.stations はこの規則に対する例外。
    両側とも、端（分岐器の位置）の施工基面を上位の線の縦断に合わせ（resync2.py と同じ）、start_z_from があれば始点を
    その区間の終点に合わせる（スイッチバック駅。chain_sanroku3.sh・chain_new6b.sh と同じ）"""
    b = s['id']; pf = s['profile']; ends = s['fit']['ends']
    if DRY: print(f'  高さの指定表：height_spec_{b}_free.json・height_spec_{b}.json'); return
    st = [n for n, _ in json.load(open(route_file(s)))['stations']]
    fb = json.load(open(f'fit_{b}.json'))
    js = {} if s['fit'].get('free') else (fb['junctions'] if 'junctions' in fb else {'end': fb['junction']})
    joined = [st[0] if w == 'start' else st[-1] for w in ends] + ([st[0]] if 'start_z_from' in pf else [])
    for k, (suf, key) in enumerate((('_free', 'free'), ('', 'gs'))):
        sp = {'note': 'build.py が入力表から作った（端の施工基面は上位の線の縦断に合わせる）', 'double': pf.get('double', [])}
        stations = {} if key == 'free' else {n: '地平' for n in st if n not in joined}
        for n, v in pf.get('stations', {}).get(key, {}).items():
            if v == '指定なし': stations.pop(n, None)
            else: stations[n] = v
        if stations or key == 'gs': sp['stations'] = stations
        for w, j in js.items():
            sec = j['trunk'][4:-5]; fp = json.load(open(f'fit_{sec}.json')); rp = json.load(open(f'route_f{sec}.json'))
            d = json.load(open(net.design_files(sec)[k]))
            sj = float(np.interp(j['s'], fp['s'], rp['s'])); sp[w + '_z'] = float(np.interp(sj, d['s'], d['z']))
        if 'start_z_from' in pf:
            d = json.load(open(net.design_files(pf['start_z_from'])[k])); sp['start_z'] = d['z'][-1]
            sp['note_start'] = f"始点の施工基面を {pf['start_z_from']} の終点に合わせる（スイッチバック駅）"
        if CHECK:   # 今のファイルと比べるだけ（注記の項目は比べない。数値は 1 mm まで）
            old = json.load(open(f'height_spec_{b}{suf}.json')); strip = lambda d: {x: (round(y, 3) if isinstance(y, float) else y) for x, y in d.items() if not x.startswith('note')}
            a, c = strip(sp), strip(old); a.setdefault('double', []); c.setdefault('double', [])
            if 'stations' not in c and not a.get('stations'): a.pop('stations', None)
            print(f'  照合 {b}{suf or "_gs"}：', '一致' if a == c else f'不一致 新 {a} 旧 {c}'); continue
        json.dump(sp, open(f'height_spec_{b}{suf}.json', 'w'), ensure_ascii=False)
        print(f'  高さの指定表 {suf or "_gs"}：', {x: round(sp[x], 1) for x in sp if x.endswith('_z')}, len(stations), '駅を指定')

# --- 問題のある駅間の検出（自動の探索。2026-11-07、国後島） -------------------------------------------------------------
def detect_problems(s):
    """縦断（駅地平化）から、問題のある駅間を機械的に出す：準地平（地盤から −10〜+12 m）の外にある駅（トンネル駅・高架駅）の前後の
    駅間と、橋梁の高さが BRIDGE_H1 を超える点のある駅間。戻り値：[[A, B], ...]（駅の並びの順）"""
    rules = s['profile'].get('rules', {}); H1 = float(rules.get('BRIDGE_H1', 0))
    d = json.load(open(net.design_files(s['id'])[1])); sn = np.array(d['s']); g = np.array(d['ground'], float); z = np.array(d['z']); st = d['struct']
    names = [n for n, _ in d['stations']]; pos = [c for _, c in d['stations']]; bad = set()
    for k, (n, c) in enumerate(d['stations']):
        i = int(np.argmin(np.abs(sn - c))); hh = z[i] - g[i]
        if hh < -10 or hh > 12:
            if k > 0: bad.add((names[k - 1], n))
            if k + 1 < len(names): bad.add((n, names[k + 1]))
    if H1 > 0:
        for i in range(len(sn)):
            if st[i] == 'B' and z[i] - g[i] > H1:
                k = min(max(0, int(np.searchsorted(pos, sn[i])) - 1), len(names) - 2); bad.add((names[k], names[k + 1]))
    return sorted(bad, key=lambda ab: names.index(ab[0]))

def segs_file(b): return f'hyb_{b}_segs.json'
def hybrid_env(s, rf):
    """devline_hybrid.py の環境変数。auto の区間は、勾配の上限 GDEF を profile.GCAP、非電化（KYAKU25_ADD）の駅間の上限 GMAP を 25‰ にし、
    問題のある駅間 SEGS を hyb_<id>_segs.json から渡す"""
    hy = s['route']['hybrid']; pf = s['profile']; b = s['id']
    env = {'ROUTE': s['route']['file'], 'OUT': rf, 'PREFIX': hy.get('PREFIX', ''), 'GDEF': hy.get('GDEF', pf['GCAP'])}
    env.update(pf.get('rules', {}))   # 探索の費用も縦断と同じ橋梁の高さの費用にする（devline2.py の W_BH・BRIDGE_H1・W_BH2。2026-11-07）
    gmap = dict(hy.get('GMAP', {}))
    if hy.get('auto'):
        stops = s['route']['stops']
        for a_, b_ in pf.get('KYAKU25_ADD', []):
            lo, hi = sorted((stops.index(a_), stops.index(b_)))
            for k in range(lo, hi): gmap.setdefault(f'{stops[k]}|{stops[k + 1]}', min(0.025, float(env['GDEF'])))
        if os.path.exists(segs_file(b)): env['SEGS'] = json.dumps(json.load(open(segs_file(b))), ensure_ascii=False)
        if 'STAGES' in hy: env['STAGES'] = json.dumps(hy['STAGES'])
        if 'LAMBDA' in hy: env['LAMBDA'] = hy['LAMBDA']   # 連続的な基準（離れ 1 m² の重み）。与えなければ STAGES の段階的な基準
    if gmap: env['GMAP'] = json.dumps(gmap, ensure_ascii=False)
    if 'GSEG' in hy: env['GSEG'] = json.dumps(hy['GSEG'], ensure_ascii=False)
    return env

# --- 区間 -------------------------------------------------------------------------------------------------------------
H = {}    # 区間の id → 縦断までの結果を左右するもののハッシュ（系統の判定に使う）
HR = {}; HF = {}   # 経路のハッシュ、線形（当てはめ・キロ程・地盤）のハッシュ
def section_hash(s):
    """段ごとのハッシュ（2026-11-07）：経路は駅の並びなど、線形はそれに fit・run と上位の線形を足したもの、縦断はそれに profile と
    上位の縦断を足したもの。縦断の規則だけを変えたとき、線形の当てはめをやり直さないため。それまでは表のどこを変えても全段をやり直していた"""
    i = s['id']
    if s['method'] == 'legacy': HR[i] = HF[i] = H[i] = file_hash(*net.design_files(i)); return H[i]
    d = net.deps(s)
    HR[i] = sha(s['island'], s['route'])
    segs = file_hash(segs_file(i)) if s['route'].get('hybrid', {}).get('auto') else ''   # 自動の探索で探した駅間（hyb_<id>_segs.json）
    HF[i] = sha(HR[i], s['fit'], s['run'], [HF[x] for x in d], segs)
    H[i] = sha(HF[i], s['profile'], [H[x] for x in d])
    return H[i]

def build_section(s):
    b = s['id']; f = s['fit']; pf = s['profile']; h = H[b]; hr = HR[b]; hf = HF[b]; rf = route_file(s); run = s['run']
    print(f"== 区間 {b}（{s['name']}）ハッシュ 経路 {hr}・線形 {hf}・縦断 {h}", flush=True)
    if REMAKE or not os.path.exists(s['route']['file']):
        step(b, 'route', hr, lambda: make_route(s))
    if ROUTES_ONLY: return
    if 'hybrid' in s['route']:
        env = hybrid_env(s, rf)
        step(b, 'hybrid', hf, lambda: sh('python3 devline_hybrid.py', env, f'hyb_{b}.log'))
    if f.get('free'): ends = 'free'
    else: ends = ' '.join(w if not v else f'{w}=fit_{v}.json' for w, v in f['ends'].items())
    trunk = f'fit_{f["trunk"]}.json'
    step(b, 'fit', hf, lambda: (sh(f'rm -f branch_{b}_cands.json'),
                                sh(f'python3 ipfit_branch.py {b} {rf} {trunk} {ends}', dict(VMAX=run['VMAX'], TILT=run['TILT'], TRAIN=run['TRAIN']), f'ipb_{b}.log')))
    step(b, 'geo', hf, lambda: (sh(f'python3 fit2route.py {b}', {'ROUTE': rf}, f'geo_{b}.log'),
                                sh(f'python3 ground.py route_f{b}.json ground_f{b}.json', None, f'ground_{b}.log')))
    step(b, 'spec', h, lambda: make_spec(s))
    env = {'GCAP': pf['GCAP']}
    if 'KYAKU25_ADD' in pf: env['KYAKU25_ADD'] = json.dumps(pf['KYAKU25_ADD'], ensure_ascii=False)
    env.update(pf.get('rules', {}))   # 縦断の規則の値（橋梁の高さの境 BRIDGE_H1・H2・SPAN・W_BH2、駅の深さ DEPTH_MAX・EXIT_R。2026-11-07、国後島。説明は tables/README.md）
    costs = f"costs_{pf.get('costs', 'single')}.json"
    sufs = ('',) if pf.get('only_gs') else ('_free', '')   # only_gs：駅地平化だけ（高さ指定なしは作らない。2026-11-07、ユーザー）
    for suf in sufs:
        out = net.design_files(b)[1 if suf == '' else 0]
        step(b, 'design' + suf, h, lambda suf=suf, out=out: sh(f'python3 design3.py ground_f{b}.json {costs} {out} height_spec_{b}{suf}.json', env, f'd_{b}{suf}.log'))
    if not DRY:
        for suf in sufs:
            os.system(f"grep -h '範囲外' d_{b}{suf}.log | head -3")
    if DRY or not s['route'].get('hybrid', {}).get('auto'): return False
    # 自動の探索（2026-11-07）：縦断に問題（トンネル駅・高架駅・高い橋梁）が残る駅間を探す駅間に足し、増えたら探索からやり直す
    probs = detect_problems(s); old = [tuple(x) for x in json.load(open(segs_file(b)))] if os.path.exists(segs_file(b)) else []
    new = sorted(set(old) | set(probs), key=lambda ab: s['route']['stops'].index(ab[0]))
    if not probs: print('  問題のある駅間なし'); return False
    if new == old: print(f'  問題が残る駅間 {["・".join(x) for x in probs]}（探す駅間は増えないので、ここで止める）'); return False
    json.dump([list(x) for x in new], open(segs_file(b), 'w'), ensure_ascii=False)
    print(f'  問題のある駅間 {["・".join(x) for x in probs]} を探す駅間に足し（合計 {len(new)}）、探索からやり直す', flush=True); return True


# --- 系統 -------------------------------------------------------------------------------------------------------------
def build_system(y):
    i = y['id']; h = sha(y, [H[x] for x in y['sections']])
    print(f"== 系統 {i}（{y.get('name')}）ハッシュ {h}", flush=True)
    if 'pieces' not in y or y['id'] == 'futsu_sanpu':
        print('  古い手順の系統なので計算しない（', y['src'], '）'); return
    f = f'sys_{i}.json'
    if not DRY: json.dump({'name': y['sys_name'], 'note': y.get('note', ''), 'pieces': y['pieces'], 'stops': y['stops']}, open(f, 'w'), ensure_ascii=False)
    if 'perf' in y: env = dict(y['perf'])
    else:
        out = subprocess.run(['python3', 'veh_env.py', y['car_type'], str(y['cars'])], capture_output=True, text=True).stdout.split()
        env = dict(x.split('=') for x in out)
    env.update(VMAX=y['VMAX'], TILT=y['TILT'], TRAIN=y['TRAIN'])
    for v in ('', 'gs'):
        step(i, 'keito' + v, h, lambda v=v: sh(f'python3 keito2.py {f} {v}'.strip(), env, f'k_{i}{v}.log'))

# --- 順に実行 ---------------------------------------------------------------------------------------------------------
order, seen = [], set()
def visit(i):
    if i in seen: return
    seen.add(i)
    for d in net.deps(net.SEC[i]): visit(d)
    order.append(i)
for s in sorted(net.SECTIONS, key=lambda s: s['rank']): visit(s['id'])
for i in order:
    s = net.SEC[i]; H[i] = section_hash(s)
    if s['method'] == 'legacy': print(f'== 区間 {i}：古い手順（計算しない）。{s["legacy"][:60]}…'); continue
    if ONLY and i not in ONLY: continue
    if MARK:
        hr, hf, h = HR[i], HF[i], H[i]; done = []
        def mark(name, hh): open(f'.build/{i}_{name}_{hh}.done', 'w').close(); done.append(name)
        if os.path.exists(s['route']['file']): mark('route', hr)
        if 'hybrid' in s['route'] and os.path.exists(route_file(s)): mark('hybrid', hf)
        if os.path.exists(f'fit_{i}.json'): mark('fit', hf)
        if os.path.exists(f'route_f{i}.json') and os.path.exists(f'ground_f{i}.json'): mark('geo', hf)
        if os.path.exists(f'height_spec_{i}.json') and os.path.exists(f'height_spec_{i}_free.json'): mark('spec', h)
        for k, suf in ((0, '_free'), (1, '')):
            if (suf or not s['profile'].get('only_gs')) and os.path.exists(net.design_files(i)[k]): mark('design' + suf, h)
        print(f'== {i}：印を付けた段 {done}'); continue
    if CHECK:
        print(f'== {i}')
        if not all(os.path.exists(f) for f in (route_file(s), f'fit_{i}.json', f'height_spec_{i}.json', f'height_spec_{i}_free.json')): print('  未計算（経路・線形・高さの指定表のどれかがない）'); continue
        make_spec(s); continue
    for _pass in range(3):   # 自動の探索：探す駅間が増えたらハッシュを付け直して、もう 1 回（最大 3 回）
        if not build_section(s): break
        H[i] = section_hash(s)
if MARK:
    for y in net.SYSTEMS:
        if 'pieces' not in y or y['id'] == 'futsu_sanpu': continue
        h = sha(y, [H[x] for x in y['sections']]); done = []
        for v in ('', 'gs'):
            if os.path.exists(f"keito2_{y['sys_name']}{'_' + v if v else ''}.json"): open(f'.build/{y["id"]}_keito{v}_{h}.done', 'w').close(); done.append('keito' + v)
        print(f'== 系統 {y["id"]}：印を付けた段 {done}')
    raise SystemExit('印を付けて止まった')
if not NOSYS and not CHECK:
    for y in net.SYSTEMS:
        if ONLY and not (ONLY & set(y['sections'])): continue
        build_system(y)
    # 段 4（2026-11-07）：駅レーダーサイトへ渡すファイル（../export/）。すべての結果から作るので、毎回作り直す（2 秒ほど）
    print('== 書き出し（export.py）'); sh('python3 export.py')
print('完了')
