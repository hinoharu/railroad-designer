# 地形から駅と駅を結ぶ経路を探す・その 3：面的な探索（2026-11-08、ユーザーの提案の概念実証）。
# 考え方（docs/align.md に書く予定）：
#  - 格子（H m）の各点に、線路の高さ（施工基面）の階級（DZ m 刻み）を持たせ、状態＝（格子の点, 高さの階級[, 進む向き]）とする。
#  - 隣の点へ移るとき、高さの差 ÷ 距離 が勾配の上限 GMAX 以下の遷移だけを許す（階級の差 k ＝ floor(GMAX × 距離 ÷ DZ)。勾配を超えない側に丸める）。
#  - 費用は devline2.py と同じ：進んだ長さ × 1 m あたりの費用 cm(地盤 − 線路)（切土・盛土・トンネル・橋梁の最小。橋梁の高さの罰則つき）。
#    これに線路 1 m あたりの費用 C_TRACK を足す（地盤に沿って長く回る線と、土工で短く行く線の釣り合い。0 だと長さに費用がつかず、等高線に沿って蛇行する）。
#  - 始点の状態から、費用の小さい順に確定していく（ダイクストラ法。scipy.sparse.csgraph）。高さを状態に持つので、「一度上がって下がる」
#    線も、鞍部を越える線も、費用が最小なら選ばれる（点ごとに 1 つの高さしか残さないと局所的な谷に落ちる）。
#  - 終点は、駅 B の位置で、線路の高さが駅 B の地盤 ± END_TOL m の階級のうち費用が最小のもの。
#  - 向き：HEAD=0 なら持たない（8 方向。速いが、折り返し（ヘアピン）も平気で作る）。HEAD=16 なら devline2 と同じ 16 方向（桂馬跳びを含む）を
#    状態に持ち、1 歩で TURN 刻み（22.5°）までしか曲がれない（H=200 m なら桂馬跳び 447 m で 22.5°：半径 約 1,100 m 相当）。
# 使い方：python3 devline3.py 経路.json 駅A 駅B 出力.json
#   環境変数 GMAX・H・DZ・MARGIN・END_TOL・C_TRACK・ZLO・ZHI・HEAD・TURN・HA（始点の向き 0..15。省略は作図の向き）・BRIDGE_H1・W_BH2
import json, sys, os, math, time
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ground import elev
import structdp
t0 = time.time()
GMAX = float(os.environ.get('GMAX', '0.015')); H = float(os.environ.get('H', '100')); MARGIN = float(os.environ.get('MARGIN', '3000'))
DZ = float(os.environ.get('DZ', str(GMAX * H))); END_TOL = float(os.environ.get('END_TOL', '10')); C_TRACK = float(os.environ.get('C_TRACK', '0.001'))
ZLO = float(os.environ.get('ZLO', '150')); ZHI = float(os.environ.get('ZHI', '120'))   # 線路の高さの範囲：地盤 − ZLO（深いトンネル）〜 地盤 ＋ ZHI（高い橋梁）
HEAD = int(os.environ.get('HEAD', '0')); TURN = int(os.environ.get('TURN', '1'))
P = json.load(open('costs_single.json'))
W_BH = float(os.environ.get('W_BH', '1.0')); BRIDGE_H1 = float(os.environ.get('BRIDGE_H1', '0')); W_BH2 = float(os.environ.get('W_BH2', '100'))
hh = np.arange(-400, 400.01, 0.5); _C3 = structdp.costs_per_m(hh, P); _fil = np.maximum(-hh, 0)
_C3[2] = _C3[2] + P['b_cut'] * (W_BH * _fil + (W_BH2 * np.maximum(_fil - BRIDGE_H1, 0) if BRIDGE_H1 > 0 else 0))
CM = _C3.min(axis=0)
def cm(h): return CM[np.clip(np.round((h + 400) / 0.5).astype(int), 0, len(CM) - 1)]   # 高さの差 h（地盤−線路）→ 1 m あたりの最小の費用（配列）

route, A, B, out = sys.argv[1:5]
r = json.load(open(route)); Pt = np.array(r['points']); names = [n for n, _ in r['stations']]
ia, ib = r['vidx'][names.index(A)], r['vidx'][names.index(B)]
lon0, lat0 = Pt[ia]; kx = math.cos(math.radians(lat0)) * 111320.0; ky = 110540.0
to_xy = lambda q: np.c_[(q[:, 0] - lon0) * kx, (q[:, 1] - lat0) * ky]
to_ll = lambda x, y: (lon0 + x / kx, lat0 + y / ky)
seg = to_xy(Pt[ia:ib + 1]); Ldraw = np.hypot(*np.diff(seg, axis=0).T).sum()
box = seg[[0, -1]]; x0, y0 = box.min(0) - MARGIN; x1, y1 = box.max(0) + MARGIN
nx, ny = int((x1 - x0) / H) + 1, int((y1 - y0) / H) + 1
# 地盤の格子：devline2 と同じ置き場（devline_grid_<A>_<B>_<H>_<MARGIN>.npy）。50 m の格子があって H がその倍数なら間引いて使う
cachef = f'devline_grid_{A}_{B}_{int(H)}_{int(MARGIN)}.npy'; c50 = f'devline_grid_{A}_{B}_50_{int(MARGIN)}.npy'
if os.path.exists(cachef): G = np.load(cachef)
elif os.path.exists(c50) and H % 50 == 0:
    k_ = int(H // 50); G = np.load(c50)[::k_, ::k_]
else:
    G = np.array([[elev(*to_ll(x0 + i * H, y0 + j * H)) for i in range(nx)] for j in range(ny)], dtype=float); np.save(cachef, G)
ny, nx = G.shape
sea = np.isnan(G); G = gaussian_filter(np.where(sea, 0, G), 50.0 / H)
def cell(p): return int(round((p[0] - x0) / H)), int(round((p[1] - y0) / H))
def heading(v): return int(round(math.atan2(v[1], v[0]) / (2 * math.pi / 16))) % 16
sa, sb = cell(seg[0]), cell(seg[-1]); zA, zB = float(G[sa[1], sa[0]]), float(G[sb[1], sb[0]])
# 高さの階級：z = m × DZ（m は整数）。各格子点で許す m の範囲は地盤 − ZLO 〜 地盤 ＋ ZHI
m_lo = np.floor((G - ZLO) / DZ).astype(int); m_hi = np.ceil((G + ZHI) / DZ).astype(int)
M0 = int(m_lo[~sea].min()); M1 = int(m_hi[~sea].max()); nz = M1 - M0 + 1
NH = HEAD if HEAD > 0 else 1
N = nx * ny * nz * NH
def node(i, j, m, h=0): return ((j * nx + i) * nz + (m - M0)) * NH + h
D16 = [(1, 0), (2, 1), (1, 1), (1, 2), (0, 1), (-1, 2), (-1, 1), (-2, 1), (-1, 0), (-2, -1), (-1, -1), (-1, -2), (0, -1), (1, -2), (1, -1), (2, -1)]
D8 = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (-1, -1), (1, -1)]
print(f'{A}→{B}：作図 {Ldraw / 1000:.2f} km、駅の地盤 {zA:.0f} → {zB:.0f} m、格子 {nx}×{ny}（{H:.0f} m）、高さの階級 {nz}（{DZ:.2f} m）、向き {NH}、状態 {N:,}', flush=True)
jj, ii = np.nonzero(~sea)
rows, cols, wts = [], [], []
def add_edges(dx, dy, h_from, h_to):
    """格子の全点から (dx, dy) へ、向き h_from → h_to で移る辺。高さの差は −k..k 階級"""
    L = H * math.hypot(dx, dy); k = int(math.floor(GMAX * L / DZ + 1e-9))
    i2, j2 = ii + dx, jj + dy; ok = (i2 >= 0) & (i2 < nx) & (j2 >= 0) & (j2 < ny)
    ok[ok] &= ~sea[j2[ok], i2[ok]]
    i1, j1, i2, j2 = ii[ok], jj[ok], i2[ok], j2[ok]
    lo1, hi1 = m_lo[j1, i1], m_hi[j1, i1]; lo2, hi2 = m_lo[j2, i2], m_hi[j2, i2]; g2 = G[j2, i2]
    for dm in range(-k, k + 1):
        a = np.maximum(lo1, lo2 - dm); b = np.minimum(hi1, hi2 - dm); cnt = np.maximum(b - a + 1, 0)
        sel = cnt > 0; a, cnt, i1s, j1s, i2s, j2s, g2s = a[sel], cnt[sel], i1[sel], j1[sel], i2[sel], j2[sel], g2[sel]
        if not len(a): continue
        base = np.repeat(a, cnt) + (np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt))   # 各セルの a..b を並べた m
        src = ((np.repeat(j1s * nx + i1s, cnt)) * nz + (base - M0)) * NH + h_from
        dst = ((np.repeat(j2s * nx + i2s, cnt)) * nz + (base + dm - M0)) * NH + h_to
        z2 = (base + dm) * DZ; w = L * (cm(np.repeat(g2s, cnt) - z2) + C_TRACK)
        rows.append(src.astype(np.int64)); cols.append(dst.astype(np.int64)); wts.append(w)
if HEAD > 0:
    for h2 in range(16):
        for dh in range(-TURN, TURN + 1): add_edges(*D16[h2], (h2 - dh) % 16, h2)
else:
    for dx, dy in D8: add_edges(dx, dy, 0, 0)
rows = np.concatenate(rows); cols = np.concatenate(cols); wts = np.concatenate(wts)
print(f'  辺 {len(rows):,}（{time.time() - t0:.1f} 秒）', flush=True)
Gr = csr_matrix((wts, (rows, cols)), shape=(N, N)); del rows, cols, wts
mA = int(round(zA / DZ))
ha = (int(os.environ['HA']) if os.environ.get('HA') else heading(seg[min(3, len(seg) - 1)] - seg[0])) if HEAD > 0 else 0
start = node(sa[0], sa[1], mA, ha)
dist, pred = dijkstra(Gr, directed=True, indices=start, return_predecessors=True)
print(f'  ダイクストラ法 {time.time() - t0:.1f} 秒、到達した状態 {np.isfinite(dist).sum():,}', flush=True)
cands = [(dist[node(sb[0], sb[1], m, h)], m, h) for m in range(M0, M1 + 1) for h in range(NH)
         if abs(m * DZ - zB) <= END_TOL and np.isfinite(dist[node(sb[0], sb[1], m, h)])]
if not cands: raise SystemExit(f'{A}→{B}：経路が見つからない（駅 B の高さ ±{END_TOL} m に届く状態がない）')
c, mB, hB = min(cands); n = node(sb[0], sb[1], mB, hB); path = []
while n >= 0: path.append(n); n = pred[n]
path = path[::-1]
cells = [((p // NH) // nz) % nx for p in path], [((p // NH) // nz) // nx for p in path], [(p // NH) % nz + M0 for p in path]
xy = np.array([(x0 + i * H, y0 + j * H) for i, j in zip(cells[0], cells[1])], float)
z = np.array([m * DZ for m in cells[2]]); gz = np.array([G[j, i] for i, j in zip(cells[0], cells[1])]); hs = gz - z
seglen = np.hypot(*np.diff(xy, axis=0).T); cost_dev2 = float((seglen * cm(hs[1:])).sum())   # devline2 と同じ尺度（C_TRACK を含まない）
gr = np.abs(np.diff(z)) / np.maximum(seglen, 1e-9)   # 勾配は格子の点で測る（端を駅の位置に置き換える前）
xy[0], xy[-1] = seg[0], seg[-1]; L = float(np.hypot(*np.diff(xy, axis=0).T).sum())
print(f'  見つけた経路：{L / 1000:.2f} km（作図より {L / 1000 - Ldraw / 1000:+.2f} km）、費用 {cost_dev2:.3g}（線路の費用込み {c:.3g}）、地盤−線路 {hs.min():.0f}〜{hs.max():.0f} m、'
      f'最急 {gr.max() * 1000:.1f}‰、点 {len(xy)}、{time.time() - t0:.1f} 秒', flush=True)
json.dump({'from': A, 'to': B, 'method': 'devline3', 'points': [list(to_ll(x, y)) for x, y in xy], 'z': z.tolist(), 'h': hs.tolist(), 'length': L, 'cost': cost_dev2,
           'cost_with_track': float(c), 'heading_end': int(hB) if HEAD > 0 else None, 'heading_start': int(ha) if HEAD > 0 else None,
           'GMAX': GMAX, 'H': H, 'DZ': DZ, 'MARGIN': MARGIN, 'END_TOL': END_TOL, 'C_TRACK': C_TRACK, 'HEAD': HEAD, 'TURN': TURN, 'seconds': time.time() - t0},
          open(out, 'w'), ensure_ascii=False)
