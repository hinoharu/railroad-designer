#!/usr/bin/env python3
# 駅レーダーサイト（hinoharu/eki-radar-dev）へ渡すファイルを書き出す（2026-11-07、⑤プログラム化の段 4。形の決まりは
# docs/exchange.md）。入力表（tables/）と計算の結果（fit_*・route_f*・design_f*・curvelist_f*・keito2_*）から、
#   ../export/<島>_lines.geojson     区間ごとの平面線形を約 10 m の折れ線にしたもの（作図の線と同じ形：LineString の集まり）
#   ../export/<島>_stations.geojson  駅の位置（作図の駅と同じ形：Point の集まり。name は「〜駅」「〜信号場」「〜仮乗降場」）
#   ../export/<島>_network.json      補足：区間（順位・等級・駅・長さなど）、区間をまとめた路線の名前、系統、車両の性能、出典
#   ../export/<島>_line_names.tsv・<島>_line_splits.tsv・<島>_yomi.tsv
#                                    駅レーダーサイトの scripts/fiction.py が読む表の、この島の行（線名、線を駅で分ける指示、駅の読み）
# を作る。駅レーダーサイトの fiction.py を変えずに読める形にする（作図の GeoJSON と同じ置き方）。
#
# 使い方：cd kp && python3 export.py        （build.py の最後でも呼ぶ）
import json, math, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, 'tables'); sys.path.insert(0, HERE)
import net
from geo import metres, project, FICTION_JSON

OUT = os.path.join(HERE, '..', 'export')
TOL = 10.0            # m：折れ線にするときの、線形からのずれの上限（駅レーダーサイトの線形の精度。docs/thresholds.md）
ISLAND_FILE = {'択捉': 'etorofu', '国後': 'kunashiri'}   # fiction.py の ISLANDS と同じ対応
FIT_NAME = {'ipg': 'ipgh'}   # 古い手順の区間の線形のファイル名（fit_ipgh.json。fit_ipg.json と同じ内容）


def simplify(pts, fixed, tol):
    """pts（経度・緯度）を、どの点も折れ線から tol m 以内に残る最少の頂点に減らす（Douglas–Peucker）。fixed の添字の点は必ず残す。
    返すのは残す添字（昇順）"""
    keep = set(fixed) | {0, len(pts) - 1}
    dist = lambda i, a, b: project(pts[i], pts[a], pts[b])[1]   # 距離の測り方は確かめる側（geo.project）と同じ
    stack = [(a, b) for a, b in zip(sorted(keep), sorted(keep)[1:])]
    while stack:
        a, b = stack.pop()
        if b - a < 2: continue
        i, d = max(((i, dist(i, a, b)) for i in range(a + 1, b)), key=lambda x: x[1])
        if d > tol:
            keep.add(i); stack += [(a, i), (i, b)]
    return sorted(keep)


def interp_point(A, S, s):
    """線形 A（点の列）の、地盤に沿った距離 S で s の位置の点"""
    import bisect
    i = min(max(bisect.bisect_right(S, s) - 1, 0), len(A) - 2)
    t = (s - S[i]) / (S[i + 1] - S[i]) if S[i + 1] > S[i] else 0.0
    t = max(0.0, min(1.0, t))
    return [A[i][0] + (A[i + 1][0] - A[i][0]) * t, A[i][1] + (A[i + 1][1] - A[i][1]) * t], i, t


def insert_point(A, S, s):
    """距離 s の点を A の頂点にして、その添字を返す（既に 0.01 m 以内に頂点があればそれ）"""
    p, i, t = interp_point(A, S, s)
    for j in (i, i + 1):
        if metres(p, A[j]) < 0.01: return j
    A.insert(i + 1, p); S.insert(i + 1, s)
    return i + 1


def nearest_s(p, A, S):
    """点 p に最も近い線形上の位置（距離 s）と、そこまでの距離 m"""
    best = None
    for k in range(len(A) - 1):
        q, d = project(p, A[k], A[k + 1])
        if best is None or d < best[0]:
            seg = metres(A[k], A[k + 1]); t = metres(A[k], q) / seg if seg else 0.0
            best = (d, S[k] + (S[k + 1] - S[k]) * t)
    return best[1], best[0]


def git_version():
    try:
        h = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, cwd=HERE).stdout.strip()
        dirty = subprocess.run(['git', 'status', '--porcelain', '--', 'tables', '*.json'], capture_output=True, text=True, cwd=HERE).stdout.strip()
        return h + ('（入力表か結果に未コミットの変更あり）' if dirty else '') if h else '記録なし'
    except Exception:
        return '記録なし'


def main():
    fic = json.load(open(FICTION_JSON, encoding='utf-8'))
    FS = fic['stations']   # [名前, 読み, 緯度×1e5, 経度×1e5, 種類, 島, 路線の番号]
    kind = {s[0]: s[4] for s in FS}; kana = {s[0]: s[1] for s in FS}
    routes = [(r[0], r[1], [FS[k][0] for k in r[3]]) for r in fic['routes']]   # 作図の路線：名前、読み、駅の並び
    secs = sorted(net.SECTIONS, key=lambda s: (s['rank'], net.SECTIONS.index(s)))   # 上位の線から（駅の位置は上位の線のものを使う）
    islands = sorted({s['island'] for s in secs}, key=list(ISLAND_FILE).index)
    vehicles = json.load(open('vehicles.json'))['vehicles']
    sys.path.insert(0, HERE)
    from run import simulate
    os.makedirs(OUT, exist_ok=True)
    for island in islands:
        tag = ISLAND_FILE[island]
        S_sec = [s for s in secs if s['island'] == island]
        geom = {}     # 区間 id → {'A': 点, 'S': 距離, 'fixed': 残す添字, 'stations': [(名前, s)]}
        junction_of = {}
        for s in S_sec:
            i = s['id']; t = FIT_NAME.get(i, i)
            fit = json.load(open(f'fit_{t}.json')); rt = json.load(open(f'route_f{t}.json')); des = json.load(open(net.design_files(i)[0]))
            A = [list(p) for p in fit['A']]; S = list(rt['s'])
            js = fit.get('junctions') or ({'end': fit['junction']} if 'junction' in fit else {})
            junction_of[i] = {w: (j['trunk'][4:-5], j['lonlat']) for w, j in js.items()}   # 端 → (幹線の区間 id, 分岐器の位置)
            geom[i] = {'A': A, 'S': S, 'fixed': set(), 'stations': [(n, c) for n, c in des['stations']], 'sec': s, 'fit': fit, 'rt': rt}
        # 残す頂点：駅の位置と、支線の分岐器の位置（幹線の上）。支線の端は分岐器の位置そのもの（build.py の ipfit_branch の結果）。
        # 頂点を差し込むと添字がずれるので、残す頂点は距離 s で集めてから差し込み、最後に添字にする
        for i, g in geom.items():
            g['fixed_s'] = {c for _, c in g['stations']}
            for w, (trunk, p) in junction_of[i].items():
                gt = geom[trunk]
                st, d = nearest_s(p, gt['A'], gt['S'])
                if d > 0.05: print(f'  注意：{i} の {w} の分岐器の位置が幹線 {trunk} の線形から {d:.2f} m 離れている')
                gt['fixed_s'].add(st)
        for i, g in geom.items():
            A, S = g['A'], g['S']
            vals = {S[insert_point(A, S, c)] for c in sorted(g['fixed_s'])}
            g['fixed'] = {k for k, v in enumerate(S) if v in vals}
        # 折れ線にする
        feats, stations, seen, dev_max = [], [], {}, 0.0
        for s in S_sec:
            i = s['id']; g = geom[i]; A, S = g['A'], g['S']
            keep = simplify(A, g['fixed'], TOL)
            P = [A[k] for k in keep]
            # 確かめる：落とした点はすべて折れ線から TOL 以内か（最大のずれを記録する）
            Pm = P; worst = 0.0; kk = 0
            for k in range(len(A)):
                while kk + 1 < len(keep) and keep[kk + 1] <= k: kk += 1
                q, d = project(A[k], Pm[kk], Pm[min(kk + 1, len(Pm) - 1)])
                worst = max(worst, d)
            dev_max = max(dev_max, worst)
            feats.append({'type': 'Feature', 'properties': {'section': i, 'name': s['name']},
                          'geometry': {'type': 'LineString', 'coordinates': [[round(p[0], 6), round(p[1], 6)] for p in P]}})
            g['n_points'] = len(P); g['dev'] = worst
            for n, c in g['stations']:
                if n in seen: continue
                p, _, _ = interp_point(A, S, c)
                k = kind.get(n)
                if k is None: print(f'  注意：{n} は data/fiction.json にない駅（種類を「駅」とみなす）'); k = '駅'
                shown = n + ('駅' if k == '駅' else '')   # 信号場・仮乗降場は名前に含まれている
                seen[n] = (i, p)
                stations.append({'type': 'Feature', 'properties': {'name': shown, 'kana': kana.get(n, '')},
                                 'geometry': {'type': 'Point', 'coordinates': [round(p[0], 6), round(p[1], 6)]}})
        # 区間をまとめた路線（作図の路線の駅の並びで、隣り合う駅の組が同じ路線に続けてあるものを、その路線の一部とする）
        pieces = {}   # 区間 id → [(路線名, 始めの駅, 終わりの駅)]
        line_kana = {r[0]: r[1] for r in routes}
        for s in S_sec:
            i = s['id']; st = [n for n, _ in geom[i]['stations']]; out = []
            for a, b in zip(st, st[1:]):
                found = [r[0] for r in routes if a in r[2] and b in r[2] and abs(r[2].index(a) - r[2].index(b)) == 1]
                name = found[0] if found else None
                if len(found) > 1: print(f'  注意：{i} の {a}〜{b} は作図の {len(found)} 路線にある（{found}。最初のものにした）')
                if not found: print(f'  注意：{i} の {a}〜{b} は作図のどの路線にもない（路線名なし）')
                if out and out[-1][0] == name: out[-1][2] = b
                else: out.append([name, a, b])
            pieces[i] = out
        lines = {}
        for i, out in pieces.items():
            for name, a, b in out:
                lines.setdefault(name, {'name': name, 'kana': line_kana.get(name, ''), 'pieces': []})['pieces'].append({'section': i, 'from': a, 'to': b})
        for name, L in lines.items():
            r = next((r for r in routes if r[0] == name), None)
            L['stations_drawn'] = r[2] if r else []
        # fiction.py の表：線名は「路線に沿った最初の駅〜最後の駅」で引くので、1 区間に 2 路線以上あれば駅で分け（line_splits）、
        # 分けたあとに同じ鍵で違う線名になるものは、途中の駅で分けて避ける（例：紗那〜南留別が蘂取線の shibr と留別線の特急の経路）
        splits, names, final = [], {}, []   # final: (鍵, 線名, 区間 id)
        key = lambda a, b: f'{a}〜{b}'
        multi = {i: out for i, out in pieces.items() if len(out) > 1}
        single = {i: out[0] for i, out in pieces.items() if len(out) == 1}
        coll_keys = {key(p[1], p[2]) for out in multi.values() for p in out}   # 複数の路線の区間を分けたあとにできる鍵
        for i, (name, a, b) in single.items():
            k = key(a, b); st = [n for n, _ in geom[i]['stations']]
            others = {k2: n2 for (k2, n2, _) in final} | {key(p[1], p[2]): p[0] for out in multi.values() for p in out}
            if k in others and others[k] != name and len(st) >= 3:
                mid = st[1]
                splits.append((k, mid, f'同じ両端の駅の別の線（{others[k]}）と区別するため、途中の駅で分ける（railroad-designer の書き出し）'))
                final += [(key(a, mid), name, i), (key(mid, b), name, i)]
            else:
                final.append((k, name, i))
        for i, out in multi.items():
            st = [n for n, _ in geom[i]['stations']]; cur = key(st[0], st[-1])
            for p in out[:-1]:
                splits.append((cur, p[2], f'区間 {i} の路線の境（railroad-designer の書き出し）'))
                final.append((key(p[1], p[2]), p[0], i)); cur = key(p[2], st[-1])
            final.append((key(out[-1][1], out[-1][2]), out[-1][0], i))
        for k, name, i in final:
            if k in names and names[k] != name: print(f'  注意：鍵 {k} が 2 つの線名（{names[k]}・{name}）に当たる。fiction.py では区別できない')
            names[k] = name
        # 補足：区間
        sec_out = []
        for s in S_sec:
            i = s['id']; g = geom[i]; lst = json.load(open(f'curvelist_f{FIT_NAME.get(i, i)}.json'))
            prof = {}
            for k, f in zip(('free', 'gs'), net.design_files(i)):
                d = json.load(open(f)); ds = d['s'][1] - d['s'][0]
                sn, zn = (d['sn'], d['zn']) if 'sn' in d else (d['s'], d['z'])
                grades = [abs(z2 - z1) / (s2 - s1) * 1000 for s1, s2, z1, z2 in zip(sn, sn[1:], zn, zn[1:]) if s2 > s1]
                prof[k] = {'file': f, 'max_grade_permille': round(max(grades), 1) if grades else 0.0,
                           'tunnel_m': d['struct'].count('T') * ds, 'bridge_m': d['struct'].count('B') * ds}
            sec_out.append({
                'id': i, 'name': s['name'], 'feature': [f['properties']['section'] for f in feats].index(i),
                'rank': s['rank'], 'grade': s['grade'], 'parents': s.get('parents', []), 'method': s['method'],
                'stations': [[n, round(c)] for n, c in g['stations']], 'length_m': round(g['S'][-1]),
                'lines': [{'line': p[0], 'from': p[1], 'to': p[2]} for p in pieces[i]],
                'run': s.get('run'), 'profile_input': {k: v for k, v in s.get('profile', {}).items() if k in ('GCAP', 'costs', 'double', 'KYAKU25_ADD')},
                'min_radius_m': round(min(c['R'] for c in lst)) if lst else None, 'profile': prof,
                'polyline': {'points': g['n_points'], 'max_deviation_m': round(g['dev'], 2)},
            })
        # 補足：系統
        sys_out = []
        for y in net.SYSTEMS:
            if not set(y['sections']) <= {s['id'] for s in S_sec}: continue
            run = {}
            if 'pieces' in y and y['id'] != 'futsu_sanpu':
                for k, suf in (('free', ''), ('gs', '_gs')):
                    f = f"keito2_{y['sys_name']}{suf}.json"
                    run[k] = round(json.load(open(f))['run_min'], 1) if os.path.exists(f) else None
            elif y['id'] == 'tokkyu':   # 古い手順：run.py で走らせる（page/scripts/fiction_align.py と同じ）
                cv = json.load(open('curves_fipgh.json'))
                for k, f in zip(('free', 'gs'), net.design_files('ipg')):
                    _, _, tt, si, _, _ = simulate(json.load(open(f)), True, cv)
                    run[k] = round(sum(tt[b] - tt[a] for a, b in zip(si, si[1:])) / 60, 1)
            elif y['id'] == 'futsu_sanpu':
                for k, f in (('free', 'keito_普通大岬紗那_free.json'), ('gs', 'keito_普通大岬紗那_gs.json')):
                    run[k] = round(json.load(open(f))['run_min'], 1) if os.path.exists(f) else None
            sys_out.append({'id': y['id'], 'name': y['name'], 'sections': y['sections'], 'stops': y.get('stops'),
                            'car': {'type': y.get('car_type'), 'cars': y.get('cars'), 'perf': y.get('perf'), 'source': y.get('car_source')},
                            'VMAX': y['VMAX'], 'TILT': y['TILT'], 'TRAIN': y['TRAIN'], 'run_min': run, 'note': y.get('note', '')})
        used = sorted({y['car']['type'] for y in sys_out if y['car']['type'] in vehicles})
        network = {
            'note': 'railroad-designer の書き出し（補足）。形の決まりは docs/exchange.md。駅の位置と線形は同じ名前の *_lines.geojson・*_stations.geojson',
            'island': island, 'files': {'lines': f'{tag}_lines.geojson', 'stations': f'{tag}_stations.geojson',
                                        'line_names': f'{tag}_line_names.tsv', 'line_splits': f'{tag}_line_splits.tsv', 'yomi': f'{tag}_yomi.tsv'},
            'built_with': {'repository': 'hinoharu/railroad-designer', 'commit': git_version()},
            'source': {'drawing': '作図した路線・駅（地理院地図で作図。駅レーダーサイトの data/fiction_src。この書き出しの駅の名前・読み・路線名はそれに合わせた）',
                       'elevation': '国土地理院 標高タイル（DEM10B）', 'method': '平面線形は交点法、縦断線形は構造物の概算費用による動的計画法（docs/align.md）'},
            'precision': {'polyline_tolerance_m': TOL, 'coordinate_decimals': 6},
            'profile_keys': {'free': '駅の高さを指定しない縦断', 'gs': '駅地平化（経路の全駅を地盤 ±2 m に置く）の縦断'},
            'sections': sec_out, 'lines': list(lines.values()), 'systems': sys_out,
            'vehicles': {k: vehicles[k] for k in used},
        }
        # 書き出す
        def w(name, text):
            p = os.path.join(OUT, name); open(p, 'w', encoding='utf-8').write(text); print(f'  {os.path.relpath(p, HERE)}  {os.path.getsize(p):,} bytes')
        w(f'{tag}_lines.geojson', json.dumps({'type': 'FeatureCollection', 'features': feats}, ensure_ascii=False, separators=(',', ':')) + '\n')
        w(f'{tag}_stations.geojson', json.dumps({'type': 'FeatureCollection', 'features': stations}, ensure_ascii=False, separators=(',', ':')) + '\n')
        w(f'{tag}_network.json', json.dumps(network, ensure_ascii=False, indent=1) + '\n')
        w(f'{tag}_line_names.tsv', 'island\tsegment\tline\tkana\tnote\n' + ''.join(f'{tag}\t{k}\t{n}\t{line_kana.get(n, "")}\trailroad-designer の書き出し\n' for k, n in names.items() if n))
        w(f'{tag}_line_splits.tsv', 'island\tsegment\tstation\tnote\n' + ''.join(f'{tag}\t{k}\t{st}\t{note}\n' for k, st, note in splits))
        # 読みの表の鍵は、fiction.py の kind_name と同じく「信号場」「仮乗降場」を除いた名前
        base = lambda n: n[:-3] if n.endswith('信号場') else n[:-4] if n.endswith('仮乗降場') else n
        w(f'{tag}_yomi.tsv', 'island\tname\tyomi\thow\n' + ''.join(f'{tag}\t{base(n)}\t{kana.get(n, "")}\trailroad-designer の書き出し（作図の読みを写した）\n' for n in seen))
        print(f'{island}：区間 {len(feats)}（頂点 {sum(len(f["geometry"]["coordinates"]) for f in feats)}、線形から最大 {dev_max:.2f} m）、'
              f'駅 {len(stations)}、路線 {len(lines)}、系統 {len(sys_out)}、線を分ける指示 {len(splits)}')


if __name__ == '__main__':
    main()
