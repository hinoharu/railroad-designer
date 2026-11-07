# 距離と、点を線分に下ろす計算（2026-11-07、駅レーダーサイト hinoharu/eki-radar-dev の scripts/fiction.py の metres・project から写した。
# 共通ライブラリは作らない決定：docs/README.md「分け方の決定」。元を直したときに合わせるかは、そのときに判断する）
import math, os

# 作図から作った路線・駅のデータ（駅レーダーサイトの data/fiction.json の写し。経路の探索 path.py が読む）
FICTION_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'fiction.json')


def metres(a, b):
    return math.hypot((a[0] - b[0]) * 111320 * math.cos(math.radians(a[1])), (a[1] - b[1]) * 110570)


def project(p, a, b):
    """the nearest point to p on the segment a-b, and its distance (m)"""
    k = math.cos(math.radians(p[1]))
    bx, by, px, py = (b[0] - a[0]) * k, b[1] - a[1], (p[0] - a[0]) * k, p[1] - a[1]
    l2 = bx * bx + by * by
    t = max(0.0, min(1.0, (px * bx + py * by) / l2)) if l2 else 0.0
    q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    return q, metres(p, q)
