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
# 古い手順の区間（method が legacy：特急の経路 ipg、散布線 sanpu）は計算しない。縦断のファイルの中身のハッシュだけを、
# 下位の区間が変わったかの判定に使う
import hashlib, json, math, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tables'))
import net
import numpy as np

ARGS = sys.argv[1:]
DRY = '--dry-run' in ARGS; REMAKE = '--remake-route' in ARGS; FORCE = '--force' in ARGS; NOSYS = '--no-systems' in ARGS; CHECK = '--check-spec' in ARGS
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
    if r.get('turnback'): pts, st, vidx = drop_turnback(pts, st, vidx)
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

# --- 区間 -------------------------------------------------------------------------------------------------------------
H = {}   # 区間の id → その区間の結果を左右するもののハッシュ
def section_hash(s):
    if s['method'] == 'legacy': return file_hash(*net.design_files(s['id']))
    return sha(s, [H[d] for d in net.deps(s)])

def build_section(s):
    b = s['id']; f = s['fit']; pf = s['profile']; h = H[b]; rf = route_file(s); run = s['run']
    print(f"== 区間 {b}（{s['name']}）ハッシュ {h}", flush=True)
    if REMAKE or not os.path.exists(s['route']['file']):
        step(b, 'route', h, lambda: make_route(s))
    if 'hybrid' in s['route']:
        hy = s['route']['hybrid']; env = {'ROUTE': s['route']['file'], 'OUT': rf, 'PREFIX': hy.get('PREFIX', ''), 'GDEF': hy['GDEF']}
        if 'GMAP' in hy: env['GMAP'] = json.dumps(hy['GMAP'], ensure_ascii=False)
        if 'GSEG' in hy: env['GSEG'] = json.dumps(hy['GSEG'], ensure_ascii=False)
        step(b, 'hybrid', h, lambda: sh('python3 devline_hybrid.py', env, f'hyb_{b}.log'))
    if f.get('free'): ends = 'free'
    else: ends = ' '.join(w if not v else f'{w}=fit_{v}.json' for w, v in f['ends'].items())
    trunk = f'fit_{f["trunk"]}.json'
    step(b, 'fit', h, lambda: (sh(f'rm -f branch_{b}_cands.json'),
                               sh(f'python3 ipfit_branch.py {b} {rf} {trunk} {ends}', dict(VMAX=run['VMAX'], TILT=run['TILT'], TRAIN=run['TRAIN']), f'ipb_{b}.log')))
    step(b, 'geo', h, lambda: (sh(f'python3 fit2route.py {b}', {'ROUTE': rf}, f'geo_{b}.log'),
                               sh(f'python3 ground.py route_f{b}.json ground_f{b}.json', None, f'ground_{b}.log')))
    step(b, 'spec', h, lambda: make_spec(s))
    env = {'GCAP': pf['GCAP']}
    if 'KYAKU25_ADD' in pf: env['KYAKU25_ADD'] = json.dumps(pf['KYAKU25_ADD'], ensure_ascii=False)
    costs = f"costs_{pf.get('costs', 'single')}.json"
    for k, suf in ((0, '_free'), (1, '')):
        out = net.design_files(b)[k]
        step(b, 'design' + suf, h, lambda suf=suf, out=out: sh(f'python3 design3.py ground_f{b}.json {costs} {out} height_spec_{b}{suf}.json', env, f'd_{b}{suf}.log'))
    if not DRY:
        for suf in ('_free', ''):
            os.system(f"grep -h '範囲外' d_{b}{suf}.log | head -3")

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
    if CHECK: print(f'== {i}'); make_spec(s); continue
    build_section(s)
if not NOSYS and not CHECK:
    for y in net.SYSTEMS:
        if ONLY and not (ONLY & set(y['sections'])): continue
        build_system(y)
print('完了')
