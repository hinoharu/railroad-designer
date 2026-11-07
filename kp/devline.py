# 勾配の上限を守って駅と駅を結ぶ経路を、地形（地理院の標高タイル）から探す（2026-11-05、ユーザーの選択「地形から自動で探す」）。
# 作図の線のままでは勾配の上限で駅が地盤に届かない駅間に、展開線（等高線に沿って延ばした線）を作る。作図にない「計算で作った形」。
# 考え方：
#  - 駅 A・B の間の作図の線のまわり（MARGIN）に、H 間隔の格子を置き、各点の地盤の高さを標高タイルから取り、SIGMA でならす
#    （ならすのは、小さな谷・尾根は橋梁・切土で越える前提のため）
#  - 状態は（格子の点、進む向き 16 方向、直前に曲がったか）。隣へ進むとき、ならした地盤の勾配が GMAX 以下の動きだけを許す
#    （線路が地盤に沿って上下する前提。実際の縦断は、このあと design3.py が切土・盛土・トンネル・橋梁を含めて決める）
#  - 曲がりは 1 回に 22.5° まで、続けて曲がらない（曲線半径がおよそ 250 m を下回らないように。最終の曲線は ipfit_branch.py が決める）
#  - 費用は長さ（勾配の条件を満たす中で最も短い経路）。駅では作図の線の向きに合わせる（±22.5°）
# 使い方：python3 devline.py 経路.json 駅A 駅B 出力.json   （環境変数 GMAX・H・SIGMA・MARGIN）
import json, sys, os, math, heapq
import numpy as np
from scipy.ndimage import gaussian_filter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ground import elev
GMAX = float(os.environ.get('GMAX', '0.025')); H = float(os.environ.get('H', '50')); SIGMA = float(os.environ.get('SIGMA', '100'))
MARGIN = float(os.environ.get('MARGIN', '3000'))
route, A, B, out = sys.argv[1:5]
r = json.load(open(route)); P = np.array(r['points']); names = [n for n, _ in r['stations']]
ia, ib = r['vidx'][names.index(A)], r['vidx'][names.index(B)]
lon0, lat0 = P[ia]; kx = math.cos(math.radians(lat0)) * 111320.0; ky = 110540.0
to_xy = lambda q: np.c_[(q[:, 0] - lon0) * kx, (q[:, 1] - lat0) * ky]
to_ll = lambda x, y: (lon0 + x / kx, lat0 + y / ky)
seg = to_xy(P[ia:ib + 1])
x0, y0 = seg.min(0) - MARGIN; x1, y1 = seg.max(0) + MARGIN
nx, ny = int((x1 - x0) / H) + 1, int((y1 - y0) / H) + 1
cachef = f'devline_grid_{A}_{B}_{int(H)}_{int(MARGIN)}.npy'
if os.path.exists(cachef): G = np.load(cachef)
else:
    G = np.array([[elev(*to_ll(x0 + i * H, y0 + j * H)) for i in range(nx)] for j in range(ny)], dtype=float)  # G[j, i]
    np.save(cachef, G)
G = np.where(np.isnan(G), -1e9, G)             # 海（値なし）は通れない（勾配の条件で自然に外れる）
Gs = gaussian_filter(G, SIGMA / H)
D16 = [(2, 0), (2, 1), (1, 1), (1, 2), (0, 2), (-1, 2), (-1, 1), (-2, 1), (-2, 0), (-2, -1), (-1, -1), (-1, -2), (0, -2), (1, -2), (1, -1), (2, -1)]
D16 = [(dx // 2, dy // 2) if dx % 2 == 0 and dy % 2 == 0 else (dx, dy) for dx, dy in D16]
def cell(p): return int(round((p[0] - x0) / H)), int(round((p[1] - y0) / H))
def heading(v): return int(round(math.atan2(v[1], v[0]) / (2 * math.pi / 16))) % 16
sa, sb = cell(seg[0]), cell(seg[-1])
ha = heading(seg[min(3, len(seg) - 1)] - seg[0]); hb = heading(seg[-1] - seg[max(0, len(seg) - 4)])
print(f'{A}→{B}：作図の長さ {np.hypot(*np.diff(seg, axis=0).T).sum() / 1000:.2f} km、格子 {nx}×{ny}（{H:.0f} m）、地盤 {G[sa[1], sa[0]]:.0f} → {G[sb[1], sb[0]]:.0f} m、'
      f'直線距離 {np.hypot(*(seg[-1] - seg[0])) / 1000:.2f} km、勾配の上限での最短 {abs(G[sb[1], sb[0]] - G[sa[1], sa[0]]) / GMAX / 1000:.2f} km')
# Dijkstra：状態 (i, j, 向き, 直前に曲がったか)
INF = float('inf'); dist = {}; prev = {}
st = (sa[0], sa[1], ha, 0); dist[st] = 0.0; pq = [(0.0, st)]; goal = None
while pq:
    d, s = heapq.heappop(pq)
    if d > dist.get(s, INF): continue
    i, j, h, t = s
    if (i, j) == sb and min((h - hb) % 16, (hb - h) % 16) <= 1: goal = s; break
    for dh in (-1, 0, 1):
        if dh and t: continue
        h2 = (h + dh) % 16; dx, dy = D16[h2]; i2, j2 = i + dx, j + dy
        if not (0 <= i2 < nx and 0 <= j2 < ny): continue
        L = H * math.hypot(dx, dy)
        if abs(Gs[j2, i2] - Gs[j, i]) > GMAX * L: continue
        s2 = (i2, j2, h2, 1 if dh else 0); d2 = d + L
        if d2 < dist.get(s2, INF): dist[s2] = d2; prev[s2] = s; heapq.heappush(pq, (d2, s2))
if goal is None: raise SystemExit(f'{A}→{B}：勾配 {GMAX * 1000:.0f}‰ で通れる経路が見つからない（ならし {SIGMA:.0f} m）')
path = [goal]
while path[-1] != st: path.append(prev[path[-1]])
path = path[::-1]
xy = np.array([(x0 + i * H, y0 + j * H) for i, j, _, _ in path]); xy[0], xy[-1] = seg[0], seg[-1]
ll = [list(to_ll(x, y)) for x, y in xy]
gpath = [float(Gs[j, i]) for i, j, _, _ in path]
L = np.hypot(*np.diff(xy, axis=0).T).sum()
print(f'  見つけた経路：{L / 1000:.2f} km（作図より {L / 1000 - np.hypot(*np.diff(seg, axis=0).T).sum() / 1000:+.2f} km）、点 {len(ll)}、'
      f'ならした地盤 {min(gpath):.0f}〜{max(gpath):.0f} m、探した状態 {len(dist)}')
json.dump({'from': A, 'to': B, 'points': ll, 'ground_s': gpath, 'length': L, 'GMAX': GMAX, 'H': H, 'SIGMA': SIGMA, 'MARGIN': MARGIN}, open(out, 'w'), ensure_ascii=False)
