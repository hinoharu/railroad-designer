# 択捉の残り 6 路線の経路のファイルを作る（2026-11-06）。作図の線を駅の並びで最短の道につなぐ（path.py の route）。
# これまで経路のファイルはその場のコマンドで作っていた（記録に残らなかった）。以後はこの形で残す
import json
from path import route
LINES = {   # 区間 id: 駅の並び（つながる区間の駅から先へ）
    'furu':    ['老門', '奧羅臼'],                         # 振別線の残り（特急の経路の老門から）
    'atosa_w': ['択捉神居古潭', '内保'],                   # 阿登佐線 西側（特急の経路の択捉神居古潭から）
    # 阿登佐線 東側：散布泊は両側の線が同じ側から入る駅（スイッチバック駅。作図では駅の約 150 m 先で線が 180° 折り返す）なので、
    # 散布泊で 2 区間に分ける（単冠山口と同じ扱い、2026-11-06）
    'atosa_e1': ['択捉神居古潭', '散布泊'],
    'atosa_e2': ['散布泊', '阿登佐岳'],
    'noto':    ['振別', '賢萌', '野斗路'],                 # 野斗路線（特急の経路の振別から）
    'yorib':   ['焼沼', '鬼門', '寄別'],                   # 寄別線（小田萌線の焼沼から）
    'otoshi':  ['乙知志', '択捉原', '北乙'],               # 乙知志線（茂世路線の乙知志から）
    'moke':    ['萌消', '満前'],                           # 萌消線（終点の満前で特急の経路につながる）
}
import math
def drop_turnback(pts, st, vidx, within=1000.0):
    # 始点の駅の先で線が折り返している（スイッチバック駅の行き止まりまで行って戻る）とき、その行き帰りを除き、戻る線分の上で駅に
    # 最も近い点から始める。折り返しは、始点から within m 以内で、隣り合う線分の向きが 150° 以上変わる所（点の間隔が粗く、戻る線分が
    # 1 本で駅の脇を通り抜けることがあるので、点の距離ではなく向きで見る。2026-11-06、散布泊）
    K = 111320 * math.cos(math.radians(pts[0][1])); xy = [((p[0] - pts[0][0]) * K, (p[1] - pts[0][1]) * 110540) for p in pts]
    s = 0.0
    for i in range(1, len(xy) - 1):
        ax, ay = xy[i][0] - xy[i - 1][0], xy[i][1] - xy[i - 1][1]; bx, by = xy[i + 1][0] - xy[i][0], xy[i + 1][1] - xy[i][1]
        s += math.hypot(ax, ay)
        if s > within: return pts, st, vidx
        ang = abs(math.degrees(math.atan2(ax * by - ay * bx, ax * bx + ay * by)))
        if ang >= 150:
            l2 = bx * bx + by * by or 1.0; t = max(0.0, min(1.0, (-xy[i][0] * bx - xy[i][1] * by) / l2))
            q = (xy[i][0] + bx * t, xy[i][1] + by * t); cut = s + math.hypot(bx, by) * t
            print(f'  折り返しを除いた：駅から {s:.0f} m 先で {ang:.0f}° 折り返し、戻る線分の駅から {math.hypot(*q):.0f} m の点から始める（{cut:.0f} m 分を除く）')
            new = [[pts[0][0] + q[0] / K, pts[0][1] + q[1] / 110540]] + pts[i + 1:]
            return new, [(n, max(0.0, c - cut)) for n, c in st], [0] + [v - i for v in vidx[1:]]
    return pts, st, vidx

for k, stops in LINES.items():
    pts, st, sn, vidx = route('択捉', stops)
    pts, st, vidx = drop_turnback(pts, st, vidx)
    json.dump({'points': pts, 'stations': st, 'stops': sn, 'vidx': vidx}, open(f'route_{k}.json', 'w'), ensure_ascii=False)
    print(k, round(st[-1][1] / 1000, 2), 'km', [(n, round(c / 1000, 2)) for n, c in st])
