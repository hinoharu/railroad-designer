# 縦曲線の調査：今の縦断（design3 の結果、節点 100 m の区分線形）の勾配変化点を全区間で機械的に数える。
# 使い方：cd kp; python3 check_vcurve.py [R（既定 3000 m）]。結果の読み方と規定は docs/vertical_curve.md
# 調べること：(a) 変化量 Δi の分布と、必要な縦曲線の長さ L = R·Δi、接線長 T = L/2。(b) 隣り合う変化点の間に縦曲線が収まるか（T_k + T_k+1 ≤ 節点の間隔）。
# (c) 駅の構内（停車場中心 ± STN_HALF）の端の外の最初の勾配変化点の縦曲線が構内に食い込む長さ。(d) 分岐器（支線の fit.junctions）が幹線の縦曲線の中に入るか。(e) 変化点が緩和曲線の中か。
import sys, json, os, numpy as np
sys.path.insert(0, 'tables'); import net
R = float(sys.argv[1]) if len(sys.argv) > 1 else 3000.0
TH = 0.5   # これ未満の勾配の変化（‰）は「変化なし」とみなす（LP の数値のゆらぎ）
def yard_half(s):
    v = s.get('profile', {}).get('STN_HALF'); tr = s.get('run', {}).get('TRAIN')
    if v == 'auto' and tr: return tr / 2 + 72
    return float(v) if isinstance(v, (int, float)) else 110.0
rows = []; all_di = []; yard = []; junc = []; trans = []; gap_bad = 0; nodes_total = 0
D = {}
for sid, s in net.SEC.items():
    f = net.design_files(sid)[1]
    if not os.path.exists(f): print(sid, 'なし', f); continue
    d = json.load(open(f)); D[sid] = d
    sn, zn = np.array(d['sn']), np.array(d['zn']); g = np.diff(zn) / np.diff(sn) * 1000   # ‰
    di = np.diff(g)   # 節点 k+1 での変化（‰）
    idx = np.where(np.abs(di) >= TH)[0] + 1   # 変化点の節点
    T = R * np.abs(di[idx - 1]) / 1000 / 2    # 接線長 m
    nodes_total += len(sn) - 2
    # (b) 隣り合う変化点の間
    bad = sum(1 for a, b, ta, tb in zip(idx[:-1], idx[1:], T[:-1], T[1:]) if ta + tb > sn[b] - sn[a] + 1e-6)
    gap_bad += bad
    all_di += list(np.abs(di[idx - 1]))
    # (c) 駅の構内の端
    half = yard_half(s); fit = json.load(open(f'fit_{sid}.json')) if os.path.exists(f'fit_{sid}.json') else None
    for name, s0 in d['stations']:
        for side in (-1, 1):
            # 構内の端（停車場中心 ± half）から外へ向かって最初の勾配変化点（構内の勾配 → 線の勾配）。構内に勾配を認めるので、勾配 ≠ 0 ではなく変化点で見る
            ks = [k for k in idx if (side > 0 and sn[k] >= s0 + half - 1e-6) or (side < 0 and sn[k] <= s0 - half + 1e-6)]
            if not ks: continue
            k0 = min(ks) if side > 0 else max(ks)
            dik = abs(di[k0 - 1]); t = R * dik / 1000 / 2
            gap = abs(sn[k0] - (s0 + side * half)); intr = max(0.0, t - gap)
            yard.append((sid, name, '後' if side > 0 else '前', dik, t, gap, intr))
    # (e) 緩和曲線の中の変化点（fit の elements_flat と同じ距離程と仮定）
    if fit:
        els = fit['elements_flat']
        for k, t in zip(idx, T):
            sk = sn[k]
            for a, b, kind, par in els:
                if a - 1e-6 <= sk <= b + 1e-6:
                    if kind == 'T': trans.append((sid, sk, abs(di[k - 1]), kind))
                    if kind == 'C' and par <= 800: trans.append((sid, sk, abs(di[k - 1]), f'C{int(par)}'))
                    break
    rows.append((sid, len(sn), len(idx), int((np.abs(di[idx - 1]) >= 10).sum()), float(np.abs(di[idx - 1]).max()) if len(idx) else 0, float(T.max()) if len(idx) else 0, bad))
# (d) 分岐器と幹線の縦曲線
for sid, s in net.SEC.items():
    if not os.path.exists(f'fit_{sid}.json'): continue
    for w, j in json.load(open(f'fit_{sid}.json')).get('junctions', {}).items():
        tid = j['trunk'].replace('fit_', '').replace('.json', '')
        if tid not in D: junc.append((sid, w, tid, None, None, None)); continue
        d = D[tid]; sn, zn = np.array(d['sn']), np.array(d['zn']); g = np.diff(zn) / np.diff(sn) * 1000; di = np.diff(g)
        idx = np.where(np.abs(di) >= TH)[0] + 1
        if not len(idx): junc.append((sid, w, tid, 0, 0, 0)); continue
        # 分岐点の s は幹線の線形の上の距離程。縦断の節点 sn は地形の上の距離程なので、route_f<幹線>.json（地形）と fit_<幹線>.json（線形）の点ごとの対応で変換する（ipfit_branch の ground_of と同じ）
        js = j['s']
        if os.path.exists(f'route_f{tid}.json'):
            rs = np.array(json.load(open(f'route_f{tid}.json'))['s']); fs = np.array(json.load(open(f'fit_{tid}.json'))['s'])
            if len(rs) == len(fs): js = float(np.interp(j['s'], fs, rs))
        k = idx[np.argmin(np.abs(sn[idx] - js))]; t = R * abs(di[k - 1]) / 1000 / 2; dist = abs(sn[k] - js)
        junc.append((sid, w, tid, dist, t, abs(di[k - 1])))
print(f'縦曲線の半径 R = {R:.0f} m、勾配の変化 {TH}‰ 未満は無視。区間 {len(rows)}、節点 {nodes_total}')
print('区間 | 節点 | 変化点 | うち ≥10‰ | 最大 Δi ‰ | 最大 T m | 隣と重なる')
for r in rows: print(' | '.join(str(x if not isinstance(x, float) else round(x, 1)) for x in r))
a = np.array(all_di); print(f'\n変化点 {len(a)}：Δi の分布（‰）：<5 {int((a<5).sum())}、5〜10 {int(((a>=5)&(a<10)).sum())}、10〜20 {int(((a>=10)&(a<20)).sum())}、20〜30 {int(((a>=20)&(a<30)).sum())}、≥30 {int((a>=30).sum())}、最大 {a.max():.1f}')
print(f'必要な縦曲線の長さ L = R·Δi：最大 {R*a.max()/1000:.0f} m、≥10‰ の変化点の L の合計 {R*a[a>=10].sum()/1000/1000:.1f} km。隣の変化点と縦曲線が重なる所 {gap_bad}')
y = [r for r in yard if r[6] > 0]; print(f'\n駅の構内の端 {len(yard)} か所（{len(set((r[0],r[1]) for r in yard))} 駅）：縦曲線が構内に食い込む所 {len(y)}、食い込みの最大 {max((r[6] for r in yard), default=0):.1f} m、構内の端の変化量 Δi の分布（‰）：≤10 {sum(1 for r in yard if r[3]<=10)}、10〜15 {sum(1 for r in yard if 10<r[3]<=15)}、15〜20 {sum(1 for r in yard if 15<r[3]<=20)}、>20 {sum(1 for r in yard if r[3]>20)}')
for r in sorted(yard, key=lambda r: -r[6])[:12]: print(f'  {r[0]} {r[1]} {r[2]}：Δi {r[3]:.1f}‰、T {r[4]:.1f} m、端から変化点まで {r[5]:.0f} m、食い込み {r[6]:.1f} m')
jb = [r for r in junc if r[3] is not None and r[3] < r[4]]; print(f'\n分岐器 {len(junc)}：幹線の縦曲線の中に入る所 {len(jb)}')
for r in junc: print(f'  {r[0]} {r[1]} 幹線 {r[2]}：最寄りの変化点まで {r[3] if r[3] is None else round(r[3])} m、その T {r[4] if r[4] is None else round(r[4],1)} m（Δi {r[5] if r[5] is None else round(r[5],1)}‰）{"← 中" if r in jb else ""}')
print(f'\n緩和曲線の中の変化点 {sum(1 for r in trans if r[3]=="T")}、半径 800 m 以下の円曲線の中の変化点 {sum(1 for r in trans if r[3]!="T")}（≥10‰：{sum(1 for r in trans if r[2]>=10)}）')
for r in [r for r in trans if r[2] >= 10][:10]: print(f'  {r[0]} s={r[1]:.0f} Δi {r[2]:.1f}‰ {r[3]}')
