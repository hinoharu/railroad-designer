"""地形（50 m の格子）の上に線を描く（PIL）。使い方：python3 draw_lines.py 出力.png 経路.json 駅A 駅B 線1.json:色:名前 ..."""
import json, sys, math, numpy as np
from PIL import Image, ImageDraw
out, route, A, B = sys.argv[1:5]; lines = [x.split(':') for x in sys.argv[5:]]
r = json.load(open(route)); Pt = np.array(r['points']); names = [n for n, _ in r['stations']]
ia, ib = r['vidx'][names.index(A)], r['vidx'][names.index(B)]
lon0, lat0 = Pt[ia]; kx = math.cos(math.radians(lat0)) * 111320.0; ky = 110540.0
to_xy = lambda q: np.c_[(q[:, 0] - lon0) * kx, (q[:, 1] - lat0) * ky]
seg = to_xy(Pt[ia:ib + 1]); H = 50.0; MARGIN = 3000.0
box = seg[[0, -1]]; x0, y0 = box.min(0) - MARGIN
G = np.load(f'/home/user/railroad-designer/kp/devline_grid_{A}_{B}_50_3000.npy'); ny, nx = G.shape
S = 4  # 1 格子 = 4 画素
g = np.where(np.isnan(G), np.nan, G); lo, hi = np.nanmin(g), np.nanmax(g)
img = np.full((ny, nx, 3), 200, np.uint8)
land = ~np.isnan(g); v = ((g[land] - lo) / (hi - lo + 1e-9) * 200 + 40).astype(np.uint8)
img[land] = np.stack([v, v, v], 1); img[~land] = (170, 200, 230)
im = Image.fromarray(img[::-1]).resize((nx * S, ny * S), Image.NEAREST); d = ImageDraw.Draw(im)
def px(x, y): return ((x - x0) / H * S, (ny - 1 - (y - y0) / H) * S)
# 等高線（50 m ごと）
for lev in np.arange(math.ceil(lo / 50) * 50, hi, 50):
    m = (g >= lev); m = m & ~np.roll(m, 1, 0) | m & ~np.roll(m, 1, 1)
    for j, i in zip(*np.nonzero(m)): d.point(px(x0 + i * H, y0 + j * H), fill=(90, 90, 90))
d.line([tuple(px(x, y)) for x, y in seg], fill=(0, 0, 0), width=3)
legend = [('作図', (0, 0, 0))]
for f, col, name in lines:
    p = to_xy(np.array(json.load(open(f))['points'])); c = tuple(int(col[k:k + 2], 16) for k in (0, 2, 4))
    d.line([tuple(px(x, y)) for x, y in p], fill=c, width=3); legend.append((name, c))
for (x, y), n in ((seg[0], A), (seg[-1], B)):
    X, Y = px(x, y); d.ellipse([X - 6, Y - 6, X + 6, Y + 6], fill=(255, 0, 0))
from PIL import ImageFont
try: font = ImageFont.truetype('/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf', 22)
except Exception: font = ImageFont.load_default()
y = 10
for n, c in legend:
    d.rectangle([10, y, 40, y + 20], fill=c); d.text((50, y - 2), n, fill=(0, 0, 0), font=font); y += 28
im.save(out); print(out, im.size)
