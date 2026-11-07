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
# 探す勾配は上限の 25‰。ただし、25‰ ちょうどで探した結果、縦断で駅が範囲外になった駅間は 1‰ 低く探す（線形の当てはめと駅の前後の水平な区間の余裕）：
# 蘂取→良宇仁（25‰ では良宇仁 −11.8 m。蘂取の高さは特急の経路の起点で決まり、良宇仁へ上る長さが足りない）
GSEG = {('蘂取', '良宇仁'): 0.024}; GSEG.update({tuple(k.split('|')): v for k, v in json.loads(os.environ.get('GSEG', '{}')).items()})
r = json.load(open(ROUTE)); names = [n for n, _ in r['stations']]; P = r['points']; V = r['vidx']
pts, stations, vidx, computed, rows = [], [], [], [], []
for k, (a, b) in enumerate(zip(names, names[1:])):
    D = P[V[k]:V[k + 1] + 1]; Ld = sum(metres(u, v) for u, v in zip(D, D[1:]))
    G = GMAP.get((a, b), GDEF)
    za, zb = elev(*D[0]), elev(*D[-1]); need = 110 + abs(zb - za) / G
    use = D; how = '作図の線'
    if need > Ld:
        res = {}
        for W in [0] + WS:
            GS = GSEG.get((a, b), G); f = f"{PREFIX}{'dev4' if GS == G else 'dev7'}_{a}_{b}_{W}.json"
            if not os.path.exists(f):
                env = dict(os.environ, GMAX=str(GS), K='1500', MARGIN='3000', STATION_ONLY='0', HB='draw', CORRIDOR=str(W))
                subprocess.run(['python3', 'devline2.py', ROUTE, a, b, f], env=env, stdout=subprocess.DEVNULL, check=False)
                # 幅 K=1500 で見つからないとき（残した状態がすべて行き止まりに入った。2026-11-05、単冠山麓線の西映→上伏古信号場）は K=8000 でもう一度探す
                if not os.path.exists(f):
                    subprocess.run(['python3', 'devline2.py', ROUTE, a, b, f], env=dict(env, K='8000'), stdout=subprocess.DEVNULL, check=False)
            res[W] = json.load(open(f)) if os.path.exists(f) else None
        if res[0] is None: raise SystemExit(f'{a}→{b}：帯の制限なしでも経路が見つからない')
        base = res[0]['cost']
        ok = [W for W in WS if res[W] and res[W]['cost'] <= RATIO * base]
        Wc = ok[0] if ok else 0; use = res[Wc]['points']; computed.append([a, b])
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
