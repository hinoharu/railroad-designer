# 湿地を通る区間を、地理院の標準地図（ズームレベル 16、1 画素 約 1.7 m）の湿地の記号（白地に青い横線が等間隔に並ぶ）から読み取る。
# 経路の 20 m ごとの点で、その点を中心とする 24 画素（約 40 m）四方の窓を調べ、「濃い青が横に 8 画素以上続く行」が、
# 白い行を挟んで 3 本以上あれば湿地とする（湖・川は薄い青の塗りと縁なので、横線が何本も並ぶことはない）。
# タイルは tiles_std16/ に保存し、2 回目からは読まない（途中から再開できる）。
# 使い方：python3 wetland.py design_f名前.json 出力.json
import json, math, os, sys, io, urllib.request
import numpy as np
from PIL import Image
Z = 16; WIN = 12; RUN = 8; LINES = 3
os.makedirs('tiles_std16', exist_ok=True)
cache = {}
def tile(x, y):
    if (x, y) in cache: return cache[(x, y)]
    f = f'tiles_std16/{x}_{y}.png'
    if not os.path.exists(f):
        try: open(f, 'wb').write(urllib.request.urlopen(f'https://cyberjapandata.gsi.go.jp/xyz/std/{Z}/{x}/{y}.png', timeout=30).read())
        except Exception: open(f, 'wb').close()
    a = np.asarray(Image.open(f).convert('RGB'), dtype=int) if os.path.getsize(f) else np.full((256, 256, 3), 255)
    cache[(x, y)] = a; return a
def px(lon, lat):
    n = 2 ** Z; X = (lon + 180) / 360 * n * 256
    Y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n * 256
    return X, Y
def window(X, Y):
    x0, y0 = int(X) - WIN, int(Y) - WIN; out = np.zeros((2 * WIN, 2 * WIN, 3), int)
    for ty in range(y0 // 256, (y0 + 2 * WIN) // 256 + 1):
        for tx in range(x0 // 256, (x0 + 2 * WIN) // 256 + 1):
            a = tile(tx, ty)
            ya, yb = max(y0, ty * 256), min(y0 + 2 * WIN, ty * 256 + 256); xa, xb = max(x0, tx * 256), min(x0 + 2 * WIN, tx * 256 + 256)
            out[ya - y0:yb - y0, xa - x0:xb - x0] = a[ya - ty * 256:yb - ty * 256, xa - tx * 256:xb - tx * 256]
    return out
def is_wet(w):
    blue = (w[..., 2] > 200) & (w[..., 0] < 120) & (w[..., 1] < 170)        # 濃い青（湿地の記号・川の縁）
    rows = []
    for r in range(w.shape[0]):
        run = best = 0
        for v in blue[r]:
            run = run + 1 if v else 0; best = max(best, run)
        rows.append(best >= RUN)
    # 横線の行を数える（続けて濃い青の行は 1 本と数える）
    n = sum(1 for i, v in enumerate(rows) if v and (i == 0 or not rows[i - 1]))
    return n >= LINES
d = json.load(open(sys.argv[1])); s = np.array(d['s']); xy = d['xy']
wet = np.array([is_wet(window(*px(lon, lat))) for lon, lat in xy])
runs = []; a = None
for i, v in enumerate(list(wet) + [False]):
    if v and a is None: a = i
    if not v and a is not None: runs.append([float(s[a]), float(s[i - 1])]); a = None
json.dump({'wet': wet.astype(int).tolist(), 'runs': runs}, open(sys.argv[2], 'w'))
st = d['stations']
def near(x): return min(st, key=lambda q: abs(q[1] - x))[0]
print(f'湿地の点 {wet.sum()} / {len(wet)}（{wet.sum() * 20 / 1000:.1f} km）、区間 {len(runs)}')
for a, b in runs: print(f'  {a / 1000:7.2f}〜{b / 1000:7.2f} km（{b - a + 20:5.0f} m）  {near(a)} 付近')
