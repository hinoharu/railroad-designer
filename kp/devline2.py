# 勾配の上限を守って駅と駅を結ぶ経路を、地形（地理院の標高タイル）から探す・その 2（2026-11-05、ユーザーの選択「地形から自動で探す」）。
# 作図の線のままでは、勾配の上限（急行の区間は 15‰、ユーザーの指定）で駅が地盤に届かない駅間に、展開線（地形に沿って延ばした線）を作る。
# 作図にない「計算で作った形」で、ページでは見分けられるようにする。
# その 1（devline.py：地盤の勾配が上限以下の所だけを通る）は、谷を横切る所で必ず上限を超え、経路が見つからなかった。
# 考え方：
#  - 線路の高さは「駅 A の構内（STN_HALF）は水平、そこから上限いっぱいで駅 B の高さまで上り下りし、あとは水平」と決める（展開線の考え方）
#  - 駅 A・B の間の作図の線のまわり（MARGIN）に H 間隔の格子を置き、地盤の高さを標高タイルから取り、H でならす
#  - 状態は（格子の点、進む向き 16 方向、直前に曲がったか、進んだ距離）。曲がりは 1 回に 22.5° まで、続けて曲がらない
#  - 費用は、線路と地盤の高さの差を切土・盛土・トンネル・橋梁で埋める 1 m あたりの費用（縦断の計算と同じ費用の表、structdp.costs_per_m の
#    3 つのうち最小）の合計。坑口・橋台の費用は数えない（縦断の計算が決める）
#  - 駅 B の高さに着いたあとは、駅 B に近づく動きだけを許す。駅では作図の線の向きに合わせる（±22.5°）
#  - 進んだ距離の刻み（BIN）ごとに、費用の小さい K 個の状態だけを残して先へ進める（距離ごとの動的計画法を、幅 K で打ち切る）
# 使い方：python3 devline2.py 経路.json 駅A 駅B 出力.json   （環境変数 GMAX・H・MARGIN・K・BIN）
import json, sys, os, math
import numpy as np
from scipy.ndimage import gaussian_filter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ground import elev
import structdp
GMAX = float(os.environ.get('GMAX', '0.015')); H = float(os.environ.get('H', '50')); MARGIN = float(os.environ.get('MARGIN', '4000'))
K = int(os.environ.get('K', '1500')); BIN = float(os.environ.get('BIN', '10')); STN_HALF = 55.0
P = json.load(open('costs_single.json'))
# 橋梁の高さの費用を縦断の計算（design3.py の W_BH・W_BH2）と同じにする（2026-11-07、国後島の笛島線：探索の費用に高さの費用がなく、
# 高い橋梁を避けなかった）。縦断では高さ 1 m あたり W_BH（浅い土工 1 m 分＝b_cut m³）、境 BRIDGE_H1 を超える分は W_BH2
W_BH = float(os.environ.get('W_BH', '1.0')); BRIDGE_H1 = float(os.environ.get('BRIDGE_H1', '0')); W_BH2 = float(os.environ.get('W_BH2', '100'))
hh = np.arange(-400, 400.01, 0.5); _C3 = structdp.costs_per_m(hh, P); _fil = np.maximum(-hh, 0)
_C3[2] = _C3[2] + P['b_cut'] * (W_BH * _fil + (W_BH2 * np.maximum(_fil - BRIDGE_H1, 0) if BRIDGE_H1 > 0 else 0))
CM = _C3.min(axis=0)   # 高さの差 h（地盤−線路）→ 1 m あたりの最小の費用
cm = lambda h: CM[int(round((min(max(h, -400), 400) + 400) / 0.5))]
route, A, B, out = sys.argv[1:5]
r = json.load(open(route)); Pt = np.array(r['points']); names = [n for n, _ in r['stations']]
ia, ib = r['vidx'][names.index(A)], r['vidx'][names.index(B)]
lon0, lat0 = Pt[ia]; kx = math.cos(math.radians(lat0)) * 111320.0; ky = 110540.0
to_xy = lambda q: np.c_[(q[:, 0] - lon0) * kx, (q[:, 1] - lat0) * ky]
to_ll = lambda x, y: (lon0 + x / kx, lat0 + y / ky)
seg = to_xy(Pt[ia:ib + 1]); Ldraw = np.hypot(*np.diff(seg, axis=0).T).sum()
# 駅の位置だけを拘束条件にする（STATION_ONLY=1、2026-11-05 のユーザーの指定：将来、駅の位置だけから線を描くための POC）：探す範囲は 2 駅を囲む範囲から MARGIN
SO = os.environ.get('STATION_ONLY', '1') == '1'
box = seg[[0, -1]] if SO else seg
x0, y0 = box.min(0) - MARGIN; x1, y1 = box.max(0) + MARGIN
nx, ny = int((x1 - x0) / H) + 1, int((y1 - y0) / H) + 1
cachef = f'devline_grid_{A}_{B}_{int(H)}_{int(MARGIN)}{"_so" if SO else ""}.npy'
if os.path.exists(cachef): G = np.load(cachef)
else:
    G = np.array([[elev(*to_ll(x0 + i * H, y0 + j * H)) for i in range(nx)] for j in range(ny)], dtype=float); np.save(cachef, G)
sea = np.isnan(G); G = gaussian_filter(np.where(sea, 0, G), 1.0)
# 作図の線に沿わせる（CORRIDOR=W m、2026-11-05 のユーザーの指定「可能な範囲で当初の折れ線にそわせる。無理なところのみ独自経路」）：作図の駅間の線から W より遠い点は通らない
CORR = float(os.environ.get('CORRIDOR', '0'))
if CORR > 0:
    gx, gy = np.meshgrid(x0 + np.arange(nx) * H, y0 + np.arange(ny) * H); dmin = np.full(gx.shape, np.inf)
    for (ax_, ay_), (bx_, by_) in zip(seg, seg[1:]):
        vx, vy = bx_ - ax_, by_ - ay_; l2 = vx * vx + vy * vy or 1.0
        t = np.clip(((gx - ax_) * vx + (gy - ay_) * vy) / l2, 0, 1)
        dmin = np.minimum(dmin, np.hypot(gx - ax_ - t * vx, gy - ay_ - t * vy))
    sea = sea | (dmin > CORR)
D16 = [(1, 0), (2, 1), (1, 1), (1, 2), (0, 1), (-1, 2), (-1, 1), (-2, 1), (-1, 0), (-2, -1), (-1, -1), (-1, -2), (0, -1), (1, -2), (1, -1), (2, -1)]
LEN = [H * math.hypot(*d) for d in D16]; NB = [int(L // BIN) for L in LEN]   # 距離の刻みは切り捨て（線路の高さの変化を小さめに見積もる＝勾配を超えない側）
def cell(p): return int(round((p[0] - x0) / H)), int(round((p[1] - y0) / H))
def heading(v): return int(round(math.atan2(v[1], v[0]) / (2 * math.pi / 16))) % 16
sa, sb = cell(seg[0]), cell(seg[-1])
# 駅での向き：HA・HB（16 方向の番号）で与える。与えないとき、駅 A は作図の向き、駅 B は自由（HB=-1）。駅 B の作図の向きを使うときは HB=draw
ha = int(os.environ['HA']) if os.environ.get('HA') else heading(seg[min(3, len(seg) - 1)] - seg[0])
_hb = os.environ.get('HB', '-1'); hb = heading(seg[-1] - seg[max(0, len(seg) - 4)]) if _hb == 'draw' else int(_hb)
HBTOL = int(os.environ.get('HBTOL', '1'))   # 駅 B での向きの許容（16 方向の刻み。1＝±22.5°、2＝±45°。2026-11-07、国後島の南利寄→利寄）
hok = lambda h: hb < 0 or min((h - hb) % 16, (hb - h) % 16) <= HBTOL
zA, zB = float(G[sa[1], sa[0]]), float(G[sb[1], sb[0]]); dZ = zB - zA; sg = 1 if dZ > 0 else -1
s_need = 2 * STN_HALF + abs(dZ) / GMAX
def zt(s): return zA + sg * min(max(s - STN_HALF, 0) * GMAX, abs(dZ))
db = lambda i, j: math.hypot(i - sb[0], j - sb[1]) * H
print(f'{A}→{B}：作図 {Ldraw / 1000:.2f} km、駅の地盤 {zA:.0f} → {zB:.0f} m、{GMAX * 1000:.0f}‰ で要る長さ {s_need / 1000:.2f} km、格子 {nx}×{ny}（{H:.0f} m）、幅 K={K}', flush=True)
# 元の折れ線の費用 C(0) を同じ尺度で出すだけ（EVAL_DRAW=出力.json。段階的な探索の基準。2026-11-07、国後島）：作図の線を BIN ごとに
# たどり、同じ展開線の高さ zt(s) との差の費用を足す。線が短くて駅 B の高さに届かない場合もそのまま足す（勾配で届かない駅間は別の規則）
if os.environ.get('EVAL_DRAW'):
    from scipy.ndimage import map_coordinates
    cum = np.r_[0, np.cumsum(np.hypot(*np.diff(seg, axis=0).T))]; ss = np.arange(0, cum[-1], BIN)
    px = np.interp(ss, cum, seg[:, 0]); py = np.interp(ss, cum, seg[:, 1])
    gz = map_coordinates(G, [(py - y0) / H, (px - x0) / H], order=1, mode='nearest')
    cdraw = float(sum(BIN * cm(float(gz[k]) - zt(float(ss[k]))) for k in range(len(ss))))
    print(f'  元の折れ線の費用 {cdraw:.3g}（{cum[-1] / 1000:.2f} km）', flush=True)
    json.dump({'from': A, 'to': B, 'cost_draw': cdraw, 'length': float(cum[-1]), 'GMAX': GMAX, 'H': H, 'MARGIN': MARGIN}, open(os.environ['EVAL_DRAW'], 'w'), ensure_ascii=False)
    raise SystemExit
maxbin = int((s_need + 3 * math.hypot(*(seg[-1] - seg[0])) + 3000) / BIN)
layers = {0: {(sa[0], sa[1], ha, 0): (0.0, None)}}   # 距離の刻み → {状態: (費用, (前の刻み, 前の状態))}
best = None
for b in range(maxbin + 1):
    L_ = layers.pop(b, None)
    if not L_: continue
    items = sorted(L_.items(), key=lambda kv: kv[1][0])[:K]
    keep = dict(items); layers[('k', b)] = keep
    s = b * BIN
    for (i, j, h, t), (c, _) in items:
        if (i, j) == sb and s >= s_need and hok(h):
            if best is None or c < best[0]: best = (c, b, (i, j, h, t))
            continue
        for dh in (-1, 0, 1):
            if dh and t: continue
            h2 = (h + dh) % 16; dx, dy = D16[h2]; i2, j2 = i + dx, j + dy
            if not (0 <= i2 < nx and 0 <= j2 < ny) or sea[j2, i2]: continue
            b2 = b + NB[h2]; s2 = b2 * BIN
            if s >= s_need and db(i2, j2) >= db(i, j): continue      # 駅 B の高さに着いたら、駅 B に近づくだけ
            if s2 > s_need and db(i2, j2) > (maxbin * BIN - s2): continue
            c2 = c + LEN[h2] * cm(G[j2, i2] - zt(s2))
            st2 = (i2, j2, h2, 1 if dh else 0); Lb = layers.setdefault(b2, {})
            if st2 not in Lb or c2 < Lb[st2][0]: Lb[st2] = (c2, (b, (i, j, h, t)))
    if b % 200 == 0: print(f'  {s / 1000:.1f} km：状態 {len(items)}、最良 {best[0]:.3g}' if best else f'  {s / 1000:.1f} km：状態 {len(items)}', flush=True)
    if best and s > best[1] * BIN + 2000: break
if best is None: raise SystemExit(f'{A}→{B}：経路が見つからない')
c, b, stt = best; path = []
while stt is not None:
    path.append((b, stt)); prev = layers[('k', b)][stt][1]
    if prev is None: break
    b, stt = prev
path = path[::-1]
xy = np.array([(x0 + st[0] * H, y0 + st[1] * H) for _, st in path]); xy[0], xy[-1] = seg[0], seg[-1]
L = np.hypot(*np.diff(xy, axis=0).T).sum()
hs = [float(G[st[1], st[0]] - zt(bb * BIN)) for bb, st in path]
print(f'  見つけた経路：{L / 1000:.2f} km（作図より {L / 1000 - Ldraw / 1000:+.2f} km）、費用 {c:.3g}、地盤−線路 {min(hs):.0f}〜{max(hs):.0f} m、点 {len(xy)}', flush=True)
json.dump({'from': A, 'to': B, 'heading_end': path[-1][1][2], 'heading_start': ha, 'station_only': SO, 'points': [list(to_ll(x, y)) for x, y in xy], 'h': hs, 'length': L, 'cost': c,
           'GMAX': GMAX, 'H': H, 'MARGIN': MARGIN, 'K': K, 'BIN': BIN}, open(out, 'w'), ensure_ascii=False)
