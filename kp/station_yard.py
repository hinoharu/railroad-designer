# セーブの線路のマスから、駅ごとに「ホームに面する線路の本数」と「ホームの近くの分岐器のマスの数」を数え、棒線駅（分岐器なし・1 線）を分ける。
# 使い方：cd kp; python3 station_yard.py tables/saves/rails_etorofu.json tables/saves/rails_kunashiri.json → tables/station_yard.json（棒線駅の一覧。オプションの入力）
# これは FreeTrain のセーブという 1 つのデータ源のための道具で、計算の本体（build.py・design3.py）は一覧を受け取るだけ（データ源ごとの特別な入口は作らない。2026-11-08、ユーザーの方針）
# 線路のマスは save_rails.py がセーブ（freetrain-saves の 択捉島90x21_004re3_20260929…・国後島003_540x1584_20261025…）から取り出したもの。1 マス ≈ 110 m。
# 規則：信号場は行き違いのためにあるので、セーブに分岐器がなくても「分岐器あり」（2026-11-08、ユーザー。新白糠信号場だけが該当）。表にない停車場は「分岐器あり」（安全側）
import sys, json, re, os, collections
KP = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(KP, 'tables')); import net
D = int(os.environ.get('D', 6))   # ホームのマスから分岐器を探す範囲（マス）
norm = lambda n: re.sub(r'（信）|\(信\)|信号場$|仮乗降場$|（仮）|\(仮\)', '', n).replace('安渡移矢港', '安渡移矢岬').replace('板蘂内', '渓臼').replace('白糸', '璃瑠篠')
JUNC = ('JunctionRailRoad', 'IndependentJunctionRailRoad', 'EmptyDirectionJunctionRailRoad', 'SlipRailRoad')
info = {}
for f in sys.argv[1:]:
    R = json.load(open(f)); occ = collections.defaultdict(set)
    for c in R['cells']: occ[(c[0], c[1])].add(c[3])
    plat = {(c[0], c[1]) for c in R['cells'] if c[3] == 'ThinPlatform+RailRoadImpl'}
    junc = {p for p, ks in occ.items() if ks & set(JUNC)}
    # ホームのマスを 8 近傍でつなげて塊にし、駅の baseLocation に最も近い塊（10 マス以内）をその駅のホームとする
    comp = {}; cid = 0
    for p in plat:
        if p in comp: continue
        cid += 1; stack = [p]; comp[p] = cid
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in plat and q not in comp: comp[q] = cid; stack.append(q)
    groups = collections.defaultdict(list)
    for p, c in comp.items(): groups[c].append(p)
    for name, loc in R['stations']:
        if not loc: continue
        x0, y0 = loc[0], loc[1]
        near = [g for g in groups.values() if min(max(abs(x - x0), abs(y - y0)) for x, y in g) <= 10]
        cells = [p for g in near for p in g]
        if not cells:   # ホームがない停車場（信号場）：baseLocation の周りの線路のマスを構内とみなす
            cells = [q for q in occ if max(abs(q[0] - x0), abs(q[1] - y0)) <= 3] or [(x0, y0)]
            nj = sum(1 for j in junc if min(max(abs(j[0] - x), abs(j[1] - y)) for x, y in cells) <= D)
            info[norm(name)] = (name, 0, 1, nj); continue
        # ホームの線路の本数：塊の長い向きに直角な位置の種類（0.6 マスより離れた所で分ける）
        xs = [p[0] for p in cells]; ys = [p[1] for p in cells]
        along_x = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        perp = sorted(set((p[1] if along_x else p[0]) for p in cells)); tracks = 1 + sum(1 for a, b in zip(perp, perp[1:]) if b - a > 1)
        nj = sum(1 for j in junc if min(max(abs(j[0] - x), abs(j[1] - y)) for x, y in cells) <= D)
        info[norm(name)] = (name, len(cells), tracks, nj)
rows = []; miss = []
for sid, s in net.SEC.items():
    f = os.path.join(KP, net.design_files(sid)[1])
    if not os.path.exists(f): continue
    d = json.load(open(f))
    for name, s0 in d['stations']:
        if name not in d['stops']: continue
        k = norm(name)
        if k not in info: miss.append((sid, name)); continue
        rows.append((sid, name) + info[k])
seen = set(); uniq = [r for r in rows if not (r[1] in seen or seen.add(r[1]))]
kind = lambda r: '分岐器あり' if r[1].endswith('信号場') else ('棒線' if r[5] == 0 and r[4] <= 1 else ('分岐器なし・複数線' if r[5] == 0 else '分岐器あり'))
cnt = collections.Counter(kind(r) for r in uniq)
print(f'停車場 {len(uniq)}（区間の重なりを除く）、照合できない {len(miss)}：{miss}')
print('分類：', dict(cnt), f'（分岐器を探す範囲 {D} マス）')
print('信号場：', [(r[1], r[4], r[5]) for r in uniq if '信号場' in r[1]])
print('棒線駅：', [(r[1], r[3]) for r in uniq if kind(r) == '棒線'])
print('分岐器なし・複数線：', [(r[1], r[3], r[4]) for r in uniq if kind(r) == '分岐器なし・複数線'])
import glob
br = set()
for f in glob.glob(os.path.join(KP, 'fit_*.json')):
    for w, j in json.load(open(f)).get('junctions', {}).items(): br.add(j['station'])
print('分岐駅（支線がつながる停車場）のうち棒線と判定：', [r[1] for r in uniq if r[1] in br and kind(r) == '棒線'], '／分岐駅', len(br & {r[1] for r in uniq}))
print('ホームのマスが見つからない：', [r[1] for r in uniq if r[3] == 0])
ev = {r[1]: {'save_name': r[2], 'platform_cells': r[3], 'tracks': r[4], 'junctions': r[5]} for r in uniq}
json.dump({"_about": "棒線駅の一覧（オプションの入力。2026-11-08、ユーザーの方針：駅の点だけで計算できることが基本で、棒線駅の指定は任意。指定のない停車場はすべて行き違い駅（分岐器あり）とみなす）",
           "_source": "FreeTrain のセーブの線路の配置から station_yard.py で読み取った（ホームに面する線路 1 本・ホームから 6 マス以内に分岐器なし。信号場は除く）。別のデータ源では手で書くか省く",
           "plain_stations": sorted(r[1] for r in uniq if kind(r) == '棒線'), "_evidence": ev}, open(os.path.join(KP, 'tables', 'station_yard.json'), 'w'), ensure_ascii=False, indent=1)
