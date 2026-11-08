# 背蘂線を、作図の線に沿わせて引き直す（2026-11-05、ユーザーの指定：可能な範囲で当初の折れ線に沿わせ、無理なところのみ独自経路。駅は基本地平。ループ可）。
#  1. 駅間ごとに、作図の線のままで勾配の上限（25‰、重連）に収まるかを見る：要る長さ＝構内 2×55 m＋|駅の地盤の差|÷上限 が作図の長さ以下なら作図の線を使う
#  2. 収まらない駅間は devline2.py で探す。作図の線から幅 W の帯の中だけを探し、W を広げていく。費用が制限なし（作図の線のまわり 3 km）の
#     RATIO 倍以内になる最も狭い W を選ぶ（RATIO＝1.1 は仮の値、根拠の記録なし）。駅での向きは両端とも作図の向き（となりの駅間が作図の線のため）
#  3. つないで route_sesibe_hyb.json（computed：探した駅間）。途中の結果はファイルに残し、再開できる
import json, os, subprocess, sys
import numpy as np
from geo import metres, project
sys.path.insert(0, '.')
from ground import elev
# どの線にも使えるように（2026-11-05、茂世路線にも使う）：ROUTE（作図の経路）、OUT（出力）、PREFIX（探した結果のファイルの頭）、
# GMAP（駅間ごとの勾配の上限：{"A|B": 0.035}、書かない駅間は GDEF）
ROUTE = os.environ.get('ROUTE', 'route_sesibe.json'); OUT = os.environ.get('OUT', 'route_sesibe_hyb.json'); PREFIX = os.environ.get('PREFIX', '')
GDEF = float(os.environ.get('GDEF', '0.025')); GMAP = {tuple(k.split('|')): v for k, v in json.loads(os.environ.get('GMAP', '{}')).items()}
RATIO = 1.1; WS = [300, 600, 1000, 1500, 2000]
# 問題の残る駅間（SEGS：[["A","B"], ...]。縦断でトンネル駅・高架駅・高い橋梁が出た駅間。build.py が hyb_<id>_segs.json に書く）は、
# 元の折れ線の費用 C(0) と比べ、帯 W で探した費用 C(W) が C(0)÷R 以下になる最初の段（STAGES：[[W, R], ...]）を採る
# （2026-11-07、ユーザー：橋梁の高さなどがどうしても高くなりすぎる場合、段階的に広げる。数値は仮：docs/thresholds.md）
SEGS = {tuple(x) for x in json.loads(os.environ.get('SEGS', '[]'))}
STAGES = [tuple(x) for x in json.loads(os.environ.get('STAGES', '[[300, 3], [300, 2], [600, 2], [1000, 2], [1500, 2], [2000, 2]]'))]
# 連続的な基準（LAMBDA を与えたとき。2026-11-07、ユーザー「段階的でなく連続的でもいい」）：候補（元の折れ線と、帯 W ごとに探した線）の
# 総費用 ＝ 建設費 C ＋ LAMBDA × A（A：元の折れ線からの離れのうち D_FREE＝30 m（線形の当てはめのずれの上限 D と同じ）を超える分を
# 線に沿って積分した面積 m²）が最小の候補を採る。勾配で届かない駅間（元の折れ線は候補にならない）も同じ式で帯を選ぶ（1.1 倍の規則の代わり）
LAMBDA = float(os.environ['LAMBDA']) if os.environ.get('LAMBDA') else None; D_FREE = 30.0
def dev_area(pts, D):
    """pts（探した線）の、作図の駅間の線 D からの離れの面積（m²）：各点の離れ d のうち D_FREE を超える分を、点の間隔で積分"""
    d = [min(project(tuple(q), tuple(u), tuple(v))[1] for u, v in zip(D, D[1:])) for q in pts]
    return sum(0.5 * (max(0.0, d[i] - D_FREE) + max(0.0, d[i + 1] - D_FREE)) * metres(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
# 探す勾配は上限の 25‰。ただし、25‰ ちょうどで探した結果、縦断で駅が範囲外になった駅間は 1‰ 低く探す（線形の当てはめと駅の前後の水平な区間の余裕）：
# 蘂取→良宇仁（25‰ では良宇仁 −11.8 m。蘂取の高さは特急の経路の起点で決まり、良宇仁へ上る長さが足りない）
GSEG = {('蘂取', '良宇仁'): 0.024}; GSEG.update({tuple(k.split('|')): v for k, v in json.loads(os.environ.get('GSEG', '{}')).items()})
def search(a, b, f, env, Kuse):
    """devline2.py で駅間 a→b を探す。見つからなければ K=8000、終点の向き ±45°、向き自由、の順に緩める（2026-11-07、国後島の南利寄→利寄：
    作図の向きに合わせると K=8000 でも見つからなかった）。戻り値：(使った K, 向きの緩和の段 0〜2)。緩めた段はログに出す"""
    steps = [(Kuse, 0)] + ([('8000', 0)] if Kuse != '8000' else []) + [('8000', 1), ('8000', 2)]
    for K, relax in steps:
        e = dict(env, K=K)
        if relax == 1: e['HBTOL'] = '2'
        if relax == 2: e['HB'] = '-1'
        subprocess.run(['python3', 'devline2.py', ROUTE, a, b, f], env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if os.path.exists(f):
            if (K, relax) != steps[0]: print(f'  {a}→{b}（帯 {env.get("CORRIDOR", "0")}）：{"K=8000" if relax == 0 else "終点の向き ±45°" if relax == 1 else "終点の向き自由"} で見つけた', flush=True)
            return K, relax
    return Kuse, -1
# 面的な探索（devline3.py、2026-11-08、ユーザーの提案）：帯 W の段階をなくし、1 回の A* で「建設費 ＋ 線路の費用 ＋ λ × 離れの面積」が最小の線を探す。
# 作図の線が使える駅間では、作図の線に貼り付けた探索（λ を非常に大きく）と比べ、総費用が同じか高ければ作図の線をそのまま使う。
# SEARCH=devline2 で今までの探索に戻せる（kp_var の案の比較）。λ を与えない（LAMBDA=None）ときは devline2 の段階的な探索のまま
SEARCH = os.environ.get('SEARCH', 'devline3'); LAMBDA_FIX = 1000.0   # 作図の線に貼り付ける λ（離れ 1 m² に切土 1,000 m³ 分。離れない線だけが残る）
C_TRACK = os.environ.get('C_TRACK', '100'); C_TRACK_F = float(C_TRACK)
def search3(a, b, f, GS, lam, hb='draw'):
    """devline3 で駅間 a→b を探す（λ＝lam）。見つからなければ終点の向きを ±45°、自由、と緩める（devline2 の search と同じ段）。戻り値：結果の辞書か None"""
    for relax in (0, 1, 2):
        e = dict(os.environ, GMAX=str(GS), MARGIN='3000', LAMBDA=str(lam), C_TRACK=C_TRACK, HB=hb if relax < 2 else '-1', HBTOL='1' if relax == 0 else '2')
        subprocess.run(['python3', 'devline3.py', ROUTE, a, b, f], env=e, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if os.path.exists(f):
            if relax: print(f'  {a}→{b}（λ={lam:g}）：{"終点の向き ±45°" if relax == 1 else "終点の向き自由"} で見つけた', flush=True)
            return json.load(open(f))
    return None
r = json.load(open(ROUTE)); names = [n for n, _ in r['stations']]; P = r['points']; V = r['vidx']
pts, stations, vidx, computed, rows = [], [], [], [], []
for k, (a, b) in enumerate(zip(names, names[1:])):
    D = P[V[k]:V[k + 1] + 1]; Ld = sum(metres(u, v) for u, v in zip(D, D[1:]))
    G = GMAP.get((a, b), GDEF)
    za, zb = elev(*D[0]), elev(*D[-1]); need = 110 + abs(zb - za) / G
    use = D; how = '作図の線'
    if SEARCH == 'devline3' and LAMBDA is not None and (need > Ld or (a, b) in SEGS):   # 面的な探索（2026-11-08）
        GS = GSEG.get((a, b), G); f = f"{PREFIX}d3_{a}_{b}_l{LAMBDA:g}.json"; ff = f"{PREFIX}d3_{a}_{b}_fix.json"
        d3 = search3(a, b, f, GS, LAMBDA) if not os.path.exists(f) else json.load(open(f))
        if d3 is None: raise SystemExit(f'{a}→{b}：面的な探索で経路が見つからない')
        fix = None
        if need <= Ld:   # 作図の線が勾配で足りる駅間：作図の線に貼り付けた探索と比べる
            fix = search3(a, b, ff, GS, LAMBDA_FIX) if not os.path.exists(ff) else json.load(open(ff))
        tot3 = d3['cost'] + C_TRACK_F * d3['length'] + LAMBDA * d3['dev_area']
        totf = fix['cost'] + C_TRACK_F * fix['length'] if fix else None
        if fix and totf <= tot3 * (1 + 1e-6):
            how = f'作図の線（面的な探索でも離れない：総費用 {totf:.3g} ≤ {tot3:.3g}）'
        else:
            use = d3['points']; computed.append([a, b])
            how = f'面的な探索の線（建設費 {d3["cost"]:.3g}、離れの面積 {d3["dev_area"]:.3g} m²、λ={LAMBDA:g}' + (f'。作図の線に貼り付けると {totf:.3g} ＞ {tot3:.3g}' if fix else '。作図の線は勾配で足りない') + '）'
        print(f'{a}→{b}：{"要る長さ " + f"{need / 1000:.2f} km ＞ 作図 {Ld / 1000:.2f} km" if need > Ld else "問題の残る駅間"} → {how}（{d3["seconds"]:.1f} 秒）', flush=True)
    elif need <= Ld and (a, b) in SEGS and LAMBDA is not None:   # 連続的な基準（問題の残る駅間。devline2）
        GS = GSEG.get((a, b), G); env0 = dict(os.environ, GMAX=str(GS), K='1500', MARGIN='3000', STATION_ONLY='0', HB='draw')
        f0 = f"{PREFIX}draw_{a}_{b}.json"
        if not os.path.exists(f0): subprocess.run(['python3', 'devline2.py', ROUTE, a, b, f0], env=dict(env0, CORRIDOR='0', EVAL_DRAW=f0), stdout=subprocess.DEVNULL, check=False)
        c0 = json.load(open(f0))['cost_draw']; cand = [(c0, 0.0, 0.0, None)]   # (総費用, 建設費, 離れの面積, 帯)
        for W in WS:
            f = f"{PREFIX}{'dev4' if GS == G else 'dev7'}_{a}_{b}_{W}.json"
            if not os.path.exists(f): env0['K'], _ = search(a, b, f, dict(env0, CORRIDOR=str(W)), env0['K'])
            if os.path.exists(f):
                dd = json.load(open(f)); Ax = dev_area(dd['points'], D); cand.append((dd['cost'] + LAMBDA * Ax, dd['cost'], Ax, W))
        tot, cw, Ax, Wc = min(cand, key=lambda x: x[0])
        if Wc is not None: use = json.load(open(f"{PREFIX}{'dev4' if GS == G else 'dev7'}_{a}_{b}_{Wc}.json"))['points']; computed.append([a, b]); how = f'探した線（帯 {Wc} m、建設費 {cw / c0:.0%}、離れの面積 {Ax:.3g} m²、λ={LAMBDA:g}）'
        print(f'{a}→{b}：問題の残る駅間。元の折れ線 {c0:.3g}、候補 ' + '、'.join(f'帯 {W}：建設費 {c:.3g}＋λA {LAMBDA * A:.3g}＝{tt:.3g}' for tt, c, A, W in cand[1:]) + f' → {how}', flush=True)
    elif need <= Ld and (a, b) in SEGS:   # 段階的な探索（問題の残る駅間。LAMBDA を与えないとき）
        GS = GSEG.get((a, b), G); env0 = dict(os.environ, GMAX=str(GS), K='1500', MARGIN='3000', STATION_ONLY='0', HB='draw')
        f0 = f"{PREFIX}draw_{a}_{b}.json"
        if not os.path.exists(f0): subprocess.run(['python3', 'devline2.py', ROUTE, a, b, f0], env=dict(env0, CORRIDOR='0', EVAL_DRAW=f0), stdout=subprocess.DEVNULL, check=False)
        c0 = json.load(open(f0))['cost_draw']; tried = []
        for W, R in STAGES:
            f = f"{PREFIX}{'dev4' if GS == G else 'dev7'}_{a}_{b}_{W}.json"
            if not os.path.exists(f): env0['K'], _ = search(a, b, f, dict(env0, CORRIDOR=str(W)), env0['K'])
            cw = json.load(open(f))['cost'] if os.path.exists(f) else None; tried.append((W, R, cw))
            if cw is not None and cw <= c0 / R:
                use = json.load(open(f))['points']; computed.append([a, b]); how = f'探した線（帯 {W} m、費用 {cw / c0:.0%}。段 {len(tried)}）'; break
        print(f'{a}→{b}：問題の残る駅間。元の折れ線の費用 {c0:.3g}、段ごと ' + '、'.join(f'帯 {W}・1/{R}：{cw:.3g}（{cw / c0:.0%}）' if cw is not None else f'帯 {W}：なし' for W, R, cw in tried) + f' → {how}', flush=True)
    if need > Ld and not (SEARCH == 'devline3' and LAMBDA is not None):
        res = {}; Kuse = '1500'
        for W in [0] + WS:
            GS = GSEG.get((a, b), G); f = f"{PREFIX}{'dev4' if GS == G else 'dev7'}_{a}_{b}_{W}.json"
            if not os.path.exists(f):
                # 幅 K=1500 で見つからないとき（残した状態がすべて行き止まりに入った。2026-11-05、単冠山麓線の西映→上伏古信号場）は K=8000、
                # それでも見つからなければ終点の向きを緩める（search）。一度 8000 が要った駅間は、以後の幅も 8000 から（2026-11-07）
                env = dict(os.environ, GMAX=str(GS), MARGIN='3000', STATION_ONLY='0', HB='draw', CORRIDOR=str(W))
                Kuse, _ = search(a, b, f, env, Kuse)
            res[W] = json.load(open(f)) if os.path.exists(f) else None
        if res[0] is None: raise SystemExit(f'{a}→{b}：帯の制限なしでも経路が見つからない')
        base = res[0]['cost']
        if LAMBDA is not None:   # 連続的な基準：帯ごとの建設費＋λ×離れの面積が最小の候補（帯の制限なしも候補）
            cand = [(res[W]['cost'] + LAMBDA * dev_area(res[W]['points'], D), W) for W in [0] + WS if res[W]]
            Wc = min(cand)[1]
        else:
            ok = [W for W in WS if res[W] and res[W]['cost'] <= RATIO * base]
            Wc = ok[0] if ok else 0
        use = res[Wc]['points']; computed.append([a, b])
        how = f'探した線（帯 {Wc} m）' if Wc else '探した線（帯の制限なし）'
        print(f'{a}→{b}：要る長さ {need / 1000:.2f} km ＞ 作図 {Ld / 1000:.2f} km。帯ごとの費用 ' + '、'.join(f'{W or "制限なし"}：{res[W]["cost"]:.3g}' if res[W] else f'{W}：なし' for W in [0] + WS) + f' → {how}', flush=True)
    if not pts: pts = [list(use[0])]; stations.append((a, 0.0)); vidx.append(0)
    ch = stations[-1][1]
    for q in use[1:]: ch += metres(pts[-1], q); pts.append(list(q))
    stations.append((b, ch)); vidx.append(len(pts) - 1)
    dev = [min(project(tuple(q), tuple(u), tuple(v))[1] for u, v in zip(D, D[1:])) for q in use]
    rows.append((a, b, how, Ld, ch - stations[-2][1], max(dev), float(np.median(dev))))
json.dump({'points': pts, 'stations': stations, 'stops': names, 'vidx': vidx, 'computed': computed,
           'note': f'作図の線に沿わせ、勾配の上限（既定 {GDEF * 1000:.1f}‰、駅間ごとの指定 {dict(("|".join(k), v) for k, v in GMAP.items())}）に収まらない駅間だけ地形から探した線（devline_hybrid.py）'}, open(OUT, 'w'), ensure_ascii=False)
print('駅間｜線｜作図の長さ｜新しい長さ｜差｜作図の線からの離れ 最大・中央値')
for a, b, how, Ld, L, mx, md in rows: print(f'{a}→{b}｜{how}｜{Ld / 1000:.2f} km｜{L / 1000:.2f} km｜{(L - Ld) / 1000:+.2f} km｜{mx:.0f} m・{md:.0f} m')
print(f'全体：{sum(x[3] for x in rows) / 1000:.2f} km → {stations[-1][1] / 1000:.2f} km')
