# 地形から駅と駅を結ぶ経路を探す・その 3：面的な探索（2026-11-08、ユーザーの提案の概念実証）。
# 考え方（docs/align.md に書く予定）：
#  - 格子（H m）の各点に、線路の高さ（施工基面）の階級（DZ m 刻み）を持たせ、状態＝（格子の点, 高さの階級, 進む向き 16 方向）とする。
#  - 隣へ移るとき、高さの差 ÷ 距離 が勾配の上限 GMAX 以下の遷移だけを許す（階級の差 k ＝ floor(GMAX × 距離 ÷ DZ)。勾配を超えない側に丸める）。
#    1 歩で TURN 刻み（22.5°）までしか曲がれない。桂馬跳び（長さ 2.24 H）を含む 16 方向。
#  - 費用は devline2.py と同じ：進んだ長さ × 1 m あたりの費用 cm(地盤 − 線路)（切土・盛土・トンネル・橋梁の最小。橋梁の高さの罰則つき）。
#    これに線路 1 m あたりの費用 C_TRACK と、作図の線があるときは離れの費用 LAMBDA × (作図の線からの距離 − DEV_FREE)+ を足す
#    （devline_hybrid の「建設費 ＋ λ × 離れの面積」と同じ尺度）。
#  - 探し方は A*（ユーザーの指定、2026-11-08：作図の線があるかないかで別のことをせず、同じ探索の優先順位を変える）：
#    優先度 f ＝ ここまでの費用 g ＋ 残りの費用の下限 h。h ＝ C_TRACK × max(終点までの直線距離, 終点の高さとの差 ÷ GMAX)
#    （残りの線はこれより短くならず、どの線も 1 m あたり最低 C_TRACK かかるので、最適を変えない）。
#    作図の線があれば λ の費用で線の近くが先に広がり、線から離れた所は費用が高くなった分だけ後回しになる（線が使えるなら、ほかはほとんど見ない）。
#    BOUND を与えると f がそれを超える状態を捨てる（作図の線の費用を上限にすると、線より高くつく所は探さない）。
#    MODE=dijkstra なら scipy のダイクストラ法で全状態を解く（比較用。辺を全部作るのでメモリを食う）。
#  - 終点は、駅 B の位置で、線路の高さが駅 B の地盤 ± END_TOL m の階級（向きは自由）。
# 使い方：python3 devline3.py 経路.json 駅A 駅B 出力.json
#   環境変数 GMAX・H・DZ・MARGIN・END_TOL・C_TRACK・LAMBDA・DEV_FREE・BOUND・ZLO・ZHI・TURN・HA（始点の向き 0..15。省略は作図の向き）・MODE・BRIDGE_H1・W_BH2
import json, sys, os, math, time, heapq
import numpy as np
from scipy.ndimage import gaussian_filter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ground import elev
import structdp
t0 = time.time()
GMAX = float(os.environ.get('GMAX', '0.015')); H = float(os.environ.get('H', '100')); MARGIN = float(os.environ.get('MARGIN', '3000'))
DZ = float(os.environ.get('DZ', str(GMAX * H))); END_TOL = float(os.environ.get('END_TOL', '10')); C_TRACK = float(os.environ.get('C_TRACK', '100'))
ZLO = float(os.environ.get('ZLO', '100')); ZHI = float(os.environ.get('ZHI', '100'))   # 線路の高さの範囲：地盤 − ZLO（深いトンネル）〜 地盤 ＋ ZHI（高い橋梁）
TURN = int(os.environ.get('TURN', '1')); MODE = os.environ.get('MODE', 'astar')   # astar（numba）／python（純 Python の A*）／dijkstra（scipy の全探索）
LAMBDA = float(os.environ.get('LAMBDA', '0')); DEV_FREE = float(os.environ.get('DEV_FREE', '30')); BOUND = float(os.environ.get('BOUND', 'inf'))
P = json.load(open('costs_single.json'))
W_BH = float(os.environ.get('W_BH', '1.0')); BRIDGE_H1 = float(os.environ.get('BRIDGE_H1', '0')); W_BH2 = float(os.environ.get('W_BH2', '100'))
hh = np.arange(-400, 400.01, 0.5); _C3 = structdp.costs_per_m(hh, P); _fil = np.maximum(-hh, 0)
_C3[2] = _C3[2] + P['b_cut'] * (W_BH * _fil + (W_BH2 * np.maximum(_fil - BRIDGE_H1, 0) if BRIDGE_H1 > 0 else 0))
CM = _C3.min(axis=0); CM_LIST = CM.tolist()
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
# 作図の線からの距離（格子の点ごと。LAMBDA > 0 のとき）と、終点までの直線距離
gx, gy = np.meshgrid(x0 + np.arange(nx) * H, y0 + np.arange(ny) * H)
DGOAL = np.hypot(gx - seg[-1][0], gy - seg[-1][1])
DLINE = np.zeros_like(G)
if LAMBDA > 0:
    DLINE[:] = np.inf
    for (ax_, ay_), (bx_, by_) in zip(seg, seg[1:]):
        vx, vy = bx_ - ax_, by_ - ay_; l2 = vx * vx + vy * vy or 1.0
        t = np.clip(((gx - ax_) * vx + (gy - ay_) * vy) / l2, 0, 1)
        DLINE = np.minimum(DLINE, np.hypot(gx - ax_ - t * vx, gy - ay_ - t * vy))
    DLINE = np.maximum(DLINE - DEV_FREE, 0)
# 高さの階級：z = m × DZ（m は整数）。各格子点で許す m の範囲は地盤 − ZLO 〜 地盤 ＋ ZHI
m_lo = np.floor((G - ZLO) / DZ).astype(int); m_hi = np.ceil((G + ZHI) / DZ).astype(int)
M0 = int(m_lo[~sea].min()); M1 = int(m_hi[~sea].max()); nz = M1 - M0 + 1
NH = 16; N = nx * ny * nz * NH
def node(i, j, m, h=0): return ((j * nx + i) * nz + (m - M0)) * NH + h
def decode(p): h = p % NH; q = p // NH; m = q % nz + M0; c = q // nz; return c % nx, c // nx, m, h
D16 = [(1, 0), (2, 1), (1, 1), (1, 2), (0, 1), (-1, 2), (-1, 1), (-2, 1), (-1, 0), (-2, -1), (-1, -1), (-1, -2), (0, -1), (1, -2), (1, -1), (2, -1)]
LEN = [H * math.hypot(*d) for d in D16]; KK = [int(math.floor(GMAX * L / DZ + 1e-9)) for L in LEN]
mA = int(round(zA / DZ)); ha = int(os.environ['HA']) if os.environ.get('HA') else heading(seg[min(3, len(seg) - 1)] - seg[0])
start = node(sa[0], sa[1], mA, ha)
print(f'{A}→{B}：作図 {Ldraw / 1000:.2f} km、駅の地盤 {zA:.0f} → {zB:.0f} m、格子 {nx}×{ny}（{H:.0f} m）、高さの階級 {nz}（{DZ:.2f} m）、状態 {N:,}、'
      f'{MODE}、C_TRACK {C_TRACK:g}、λ {LAMBDA:g}', flush=True)

def astar():
    """A*：優先度 f ＝ g ＋ C_TRACK × 終点までの直線距離。隣の状態はその場で作る（辺の表は作らない）"""
    Gl = G.tolist(); seal = sea.tolist(); mlo = m_lo.tolist(); mhi = m_hi.tolist(); dg = DGOAL.tolist(); dl = (DLINE * LAMBDA).tolist()
    def hfun(i, j, m):   # 残りの費用の下限：線路の費用 × 残りの長さの下限（直線距離と、高さの差を上限勾配で稼ぐ長さの大きい方）
        return C_TRACK * max(dg[j][i], abs(zB - m * DZ) / GMAX)
    g = {start: 0.0}; pred = {start: -1}; pq = [(hfun(sa[0], sa[1], mA), start)]; done = set(); n_exp = 0
    while pq:
        f, p = heapq.heappop(pq)
        if p in done: continue
        done.add(p); n_exp += 1
        i, j, m, h = decode(p); gp = g[p]
        if i == sb[0] and j == sb[1] and abs(m * DZ - zB) <= END_TOL: return gp, p, pred, n_exp
        for dh in range(-TURN, TURN + 1):
            h2 = (h + dh) % 16; dx, dy = D16[h2]; i2, j2 = i + dx, j + dy
            if not (0 <= i2 < nx and 0 <= j2 < ny) or seal[j2][i2]: continue
            L = LEN[h2]; k = KK[h2]; g2 = Gl[j2][i2]; lo2, hi2 = mlo[j2][i2], mhi[j2][i2]
            base = L * (C_TRACK + dl[j2][i2])
            for dm in range(-k, k + 1):
                m2 = m + dm
                if m2 < lo2 or m2 > hi2: continue
                hgoal = hfun(i2, j2, m2)
                hd = g2 - m2 * DZ; idx = int(round((hd + 400) * 2))
                c2 = gp + base + L * CM_LIST[0 if idx < 0 else 1600 if idx > 1600 else idx]
                if c2 + hgoal > BOUND: continue
                p2 = ((j2 * nx + i2) * nz + (m2 - M0)) * NH + h2
                if p2 in done: continue
                old = g.get(p2)
                if old is None or c2 < old:
                    g[p2] = c2; pred[p2] = p; heapq.heappush(pq, (c2 + hgoal, p2))
    return None, None, pred, n_exp

if MODE == 'astar':   # numba で変換した A*（astar_core.py）。MODE=python なら純 Python の同じ A*（確認用）
    import astar_core
    g_ = np.full(N, np.inf); pred_ = np.full(N, -1, np.int64); closed_ = np.zeros(N, np.uint8)
    c, goal, n_exp = astar_core.astar(G, sea, m_lo, m_hi, DLINE, DGOAL, CM, M0, nz, DZ, GMAX, C_TRACK, LAMBDA, BOUND, TURN,
                                      np.array(D16, np.int64), np.array(LEN), np.array(KK, np.int64), start, sb[0], sb[1], zB, END_TOL, g_, pred_, closed_, 60_000_000)
    print(f'  A*（numba）：展開した状態 {n_exp:,}（{time.time() - t0:.1f} 秒）', flush=True)
    if goal == -2: raise SystemExit(f'{A}→{B}：待ち行列があふれた')
    if goal < 0: raise SystemExit(f'{A}→{B}：経路が見つからない（駅 B の高さ ±{END_TOL} m に届く状態がない）')
    path = []; n = goal
    while n != -1: path.append(n); n = pred_[n]
elif MODE == 'python':
    c, goal, pred, n_exp = astar()
    print(f'  A*：展開した状態 {n_exp:,}（{time.time() - t0:.1f} 秒）', flush=True)
    if c is None: raise SystemExit(f'{A}→{B}：経路が見つからない（駅 B の高さ ±{END_TOL} m に届く状態がない）')
    path = []; n = goal
    while n != -1: path.append(n); n = pred[n]
else:
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    jj, ii = np.nonzero(~sea); rows, cols, wts = [], [], []
    def add_edges(dx, dy, h_from, h_to):
        L = H * math.hypot(dx, dy); k = int(math.floor(GMAX * L / DZ + 1e-9))
        i2, j2 = ii + dx, jj + dy; ok = (i2 >= 0) & (i2 < nx) & (j2 >= 0) & (j2 < ny)
        ok[ok] &= ~sea[j2[ok], i2[ok]]
        i1, j1, i2, j2 = ii[ok], jj[ok], i2[ok], j2[ok]
        lo1, hi1 = m_lo[j1, i1], m_hi[j1, i1]; lo2, hi2 = m_lo[j2, i2], m_hi[j2, i2]; g2 = G[j2, i2]; d2 = DLINE[j2, i2]
        for dm in range(-k, k + 1):
            a = np.maximum(lo1, lo2 - dm); b = np.minimum(hi1, hi2 - dm); cnt = np.maximum(b - a + 1, 0)
            sel = cnt > 0; a, cnt, i1s, j1s, i2s, j2s, g2s, d2s = a[sel], cnt[sel], i1[sel], j1[sel], i2[sel], j2[sel], g2[sel], d2[sel]
            if not len(a): continue
            base = np.repeat(a, cnt) + (np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt))
            src = ((np.repeat(j1s * nx + i1s, cnt)) * nz + (base - M0)) * NH + h_from
            dst = ((np.repeat(j2s * nx + i2s, cnt)) * nz + (base + dm - M0)) * NH + h_to
            z2 = (base + dm) * DZ; w = L * (cm(np.repeat(g2s, cnt) - z2) + C_TRACK + LAMBDA * np.repeat(d2s, cnt))
            rows.append(src.astype(np.int64)); cols.append(dst.astype(np.int64)); wts.append(w)
    for h2 in range(16):
        for dh in range(-TURN, TURN + 1): add_edges(*D16[h2], (h2 - dh) % 16, h2)
    rows = np.concatenate(rows); cols = np.concatenate(cols); wts = np.concatenate(wts)
    print(f'  辺 {len(rows):,}（{time.time() - t0:.1f} 秒）', flush=True)
    Gr = csr_matrix((wts, (rows, cols)), shape=(N, N)); del rows, cols, wts
    dist, pred = dijkstra(Gr, directed=True, indices=start, return_predecessors=True)
    print(f'  ダイクストラ法 {time.time() - t0:.1f} 秒、到達した状態 {np.isfinite(dist).sum():,}', flush=True)
    cands = [(dist[node(sb[0], sb[1], m, h)], m, h) for m in range(M0, M1 + 1) for h in range(NH)
             if abs(m * DZ - zB) <= END_TOL and np.isfinite(dist[node(sb[0], sb[1], m, h)])]
    if not cands: raise SystemExit(f'{A}→{B}：経路が見つからない（駅 B の高さ ±{END_TOL} m に届く状態がない）')
    c, mB, hB = min(cands); n = node(sb[0], sb[1], mB, hB); path = []
    while n >= 0: path.append(n); n = pred[n]
path = path[::-1]
dec = [decode(p) for p in path]
xy = np.array([(x0 + i * H, y0 + j * H) for i, j, _, _ in dec], float)
z = np.array([m * DZ for _, _, m, _ in dec]); gz = np.array([G[j, i] for i, j, _, _ in dec]); hs = gz - z
seglen = np.hypot(*np.diff(xy, axis=0).T); cost_dev2 = float((seglen * cm(hs[1:])).sum())   # devline2 と同じ尺度（C_TRACK・λ を含まない）
dev_area = float((seglen * DLINE[[j for _, j, _, _ in dec[1:]], [i for i, _, _, _ in dec[1:]]]).sum()) if LAMBDA > 0 else 0.0
gr = np.abs(np.diff(z)) / np.maximum(seglen, 1e-9)   # 勾配は格子の点で測る（端を駅の位置に置き換える前）
xy[0], xy[-1] = seg[0], seg[-1]; L = float(np.hypot(*np.diff(xy, axis=0).T).sum())
print(f'  見つけた経路：{L / 1000:.2f} km（作図より {L / 1000 - Ldraw / 1000:+.2f} km）、建設費 {cost_dev2:.3g}（線路の費用と離れの費用込み {c:.3g}、離れの面積 {dev_area:.3g} m²）、'
      f'地盤−線路 {hs.min():.0f}〜{hs.max():.0f} m、最急 {gr.max() * 1000:.1f}‰、点 {len(xy)}、{time.time() - t0:.1f} 秒', flush=True)
json.dump({'from': A, 'to': B, 'method': 'devline3', 'mode': MODE, 'points': [list(to_ll(x, y)) for x, y in xy], 'z': z.tolist(), 'h': hs.tolist(), 'length': L, 'cost': cost_dev2,
           'cost_total': float(c), 'dev_area': dev_area, 'heading_end': int(dec[-1][3]), 'heading_start': int(ha),
           'GMAX': GMAX, 'H': H, 'DZ': DZ, 'MARGIN': MARGIN, 'END_TOL': END_TOL, 'C_TRACK': C_TRACK, 'LAMBDA': LAMBDA, 'DEV_FREE': DEV_FREE, 'TURN': TURN, 'seconds': time.time() - t0},
          open(out, 'w'), ensure_ascii=False)
