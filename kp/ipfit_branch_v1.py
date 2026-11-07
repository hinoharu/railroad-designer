# 支線の交点法（2026-11-04、ユーザーと決めた規則）：
#  - 支線の線形は、幹線の線形の上の 1 点（分岐器の位置 J）で終わる。J での向きは、幹線の向き（キロ程の増える向き）に
#    分岐器の角度 θ＝atan(1/12)（12 番）を加えた向きで、作図で支線がある側から寄せる
#  - J の位置は、作図の支線が幹線の線形から D（30 m）以内にある範囲を 10 m 刻みで動かし、費用（ずれ＋走行時間）が
#    最も小さい所に決める。分岐器そのものの長さと形は省く
#  - 最後の交点 W は、J を通り向き h の直線の上だけを動かす（最後の直線の向きを保つ）。W は取り除かない
#  - 作図の支線のうち、幹線から D 以内の部分は幹線に重なる部分とみなし、ずれを測る線から除く
# 使い方：VMAX=100 TILT=0 TRAIN=40 python3 ipfit_branch.py 名前 経路.json 幹線の fit.json
# 候補ごとの結果を branch_<名前>_cands.json に保存し、途中から再開できる
import json, math, sys, os, time
import numpy as np
from multiprocessing import Pool
from scipy.spatial import cKDTree
import ipfit_all as F
NAME, ROUTE, TRUNK = sys.argv[1], sys.argv[2], sys.argv[3]
D = F.D; THETA = math.atan(1 / 12); STEP = 10.0
F.load_route(ROUTE)
P = F.P; pts = F.pts; K = F.K
T = json.load(open(TRUNK)); TA = np.array(T['A']); TS = np.array(T['s'])
TP = np.c_[(TA[:, 0] - pts[0][0]) * K, (TA[:, 1] - pts[0][1]) * 110570]
def trunk_at(s):
    x = np.interp(s, TS, TP[:, 0]); y = np.interp(s, TS, TP[:, 1])
    x1 = np.interp(s + 5, TS, TP[:, 0]); y1 = np.interp(s + 5, TS, TP[:, 1])
    x0 = np.interp(s - 5, TS, TP[:, 0]); y0 = np.interp(s - 5, TS, TP[:, 1])
    t = np.array([x1 - x0, y1 - y0]); return np.array([x, y]), t / np.hypot(*t)
# 作図の支線の点（重なりを除く）と、幹線に重なる範囲
tree_t = cKDTree(TP); dq, iq = tree_t.query(P)
near = np.where(dq <= D)[0]
if not len(near): raise SystemExit('支線の端が幹線から D 以内に来ない')
m = near.min()          # ここから先は幹線に重なる部分
s_lo, s_hi = TS[iq[near]].min(), TS[iq[near]].max()
# 支線がある側：重なる直前の点（D を超える最後の 3 点）で、幹線の向きに対して左（+1）か右（-1）か
side = []
for j in range(max(0, m - 3), m):
    J0, t0 = trunk_at(TS[iq[j]]); v = P[j] - J0; side.append(np.sign(t0[0] * v[1] - t0[1] * v[0]))
SIG = 1.0 if sum(side) > 0 else -1.0
print(f'{NAME}：作図 {len(P)} 点、幹線に重なる部分は点 {m} から（幹線のキロ程 {s_lo:.0f}〜{s_hi:.0f} m）、支線は幹線の{"左" if SIG > 0 else "右"}側', flush=True)
OFFS = F.OFFS
def best_move_w(args):
    """最後の交点 W を、J を通る向き h の直線の上で動かす（半径も選び直す）"""
    V_, Rs, i, h = args
    lo, hi = max(0, i - 2), min(len(V_) - 1, i + 2)
    best_ = (F.local_cost(V_, Rs, lo, hi), 0.0, Rs[i - 1]); V2 = V_.copy(); base = V_[i].copy(); S0 = F.turnsum(V_, lo, hi)
    a0 = float((V_[-1] - base) @ h)
    for off in OFFS:
        if a0 - off <= 1.0: continue
        V2[i] = base + h * off
        if abs(F.turnsum(V2, lo, hi) - S0) > 1e-6: continue
        for R in F.RC20:
            Rs2 = list(Rs); Rs2[i - 1] = R; c = F.local_cost(V2, Rs2, lo, hi)
            if c < best_[0] - 1e-6: best_ = (c, off, R)
    return i, (best_[0], float(h[0] * best_[1]), float(h[1] * best_[1]), best_[2])
def solve(sj):
    J, t = trunk_at(sj)
    c, s_ = math.cos(-SIG * THETA), math.sin(-SIG * THETA)
    h = np.array([c * t[0] - s_ * t[1], s_ * t[0] + c * t[1]])   # J へ向かう支線の向き
    # 作図の支線（幹線に重なる部分を除く）の終わりに、最後の直線上の点 G（作図の最後の点を、J を通り向き h の直線に射影した点）と J を加える
    #（回り込んで合流する支線でも、曲がりが手前の複数の交点に分かれるように。G は簡略化でも残し、W として直線の上だけを動かす）
    ag = max(10.0, float((J - P[m - 1]) @ h)); G = J - h * ag
    Q = list(P[:m]) + [G, J]; Q = np.array([q for k, q in enumerate(Q) if k == 0 or np.hypot(*(q - Q[k - 1])) > 0.5])
    dense = [Q[0]]
    for p_, q_ in zip(Q, Q[1:]):
        n = max(1, int(np.hypot(*(q_ - p_)) / 2)); dense += [p_ + (q_ - p_) * u for u in np.linspace(0, 1, n + 1)[1:]]
    dense = np.array(dense); F.TREE = cKDTree(dense)
    sel = [0]
    def dp(i, j, out):
        A_, B_ = Q[i], Q[j]; d = B_ - A_; L = np.hypot(*d) or 1
        if j <= i + 1: return
        e = np.abs(d[0] * (Q[i + 1:j, 1] - A_[1]) - d[1] * (Q[i + 1:j, 0] - A_[0])) / L
        if e.max() > D: k = i + 1 + int(e.argmax()); dp(i, k, out); out.append(k); dp(k, j, out)
    mid = []; dp(0, len(Q) - 2, mid); sel += mid + [len(Q) - 2, len(Q) - 1]
    V_ = Q[sel]
    # W：最後の直線（J を通り向き h）の上。最初は、簡略化した折れ線の J の手前の頂点をこの直線に射影した位置
    #（支線が幹線に大きく回り込んで合流するとき、W の曲線が J の手前に入らなければ、入るまで 10 m ずつ J から遠ざける）
    a0 = ag
    fixed = np.array([True] + [False] * (len(V_) - 3) + [True, True])
    iw = len(V_) - 2
    # 曲線の入らない並びを整える（ipfit_all.solve_chain と同じ手順。端と W は動かさない）
    while True:
        L, u, dl = F.geom(V_); Tt = F.tlen(dl); Tmin = Tt.min(1)
        nW = len(V_) - 2   # W の番号。W とその手前の交点は、まとめてよい（まとめた点は最後の直線の上にあるので、新しい W になる）
        bad = [i for i in range(len(dl) - 1) if np.sign(dl[i]) == np.sign(dl[i + 1]) and Tmin[i] + Tmin[i + 1] > L[i + 1] and not fixed[i + 1] and (not fixed[i + 2] or i + 2 == nW)]
        rev = [i for i in range(len(dl) - 1) if np.sign(dl[i]) != np.sign(dl[i + 1]) and Tmin[i] + Tmin[i + 1] > L[i + 1]]
        ends = [i for i in (0, len(dl) - 1) if Tmin[i] > L[i if i == 0 else i + 1] and not fixed[i + 1]]
        cand = [i for i in rev if not (fixed[i + 1] and fixed[i + 2])]
        if not bad and not cand and not ends:
            left = [i for i in range(len(dl) - 1) if Tmin[i] + Tmin[i + 1] > L[i + 1]]
            if Tmin[-1] > L[-1]:   # W の曲線が J の手前に入らない：W を遠ざける
                V_[-2] = V_[-1] - h * (float((V_[-1] - V_[-2]) @ h) + 10.0)
                if np.hypot(*(V_[-1] - V_[-2])) > 3000: solve.why = '整える途中で W を 3 km 遠ざけても入らない'; return None
                continue
            if left: solve.why = f'隣り合う曲線が重なる（交点 {left[0] + 1}、全 {len(V_) - 2}）'; return None
            break
        if bad:
            i = min(bad, key=lambda i: L[i + 1])
            p1, d1 = V_[i], u[i]; p2, d2 = V_[i + 3], -u[i + 2]
            tt = np.linalg.solve(np.array([d1, -d2]).T, p2 - p1); X_ = p1 + d1 * tt[0]
            if i + 2 == nW and not (tt[0] > 0 and float((J - X_) @ h) > 1.0):
                solve.why = 'W の手前の交点と W をまとめた点が、J の手前にない'; return None
            V_ = np.vstack([V_[:i + 1], [X_], V_[i + 3:]]); fixed = np.concatenate([fixed[:i + 1], [i + 2 == nW], fixed[i + 3:]]); continue
        if cand:
            i = min(cand, key=lambda i: L[i + 1])
            drop = i if (abs(dl[i]) < abs(dl[i + 1]) and not fixed[i + 1]) or fixed[i + 2] else i + 1
        else: drop = ends[0]
        V_ = np.delete(V_, drop + 1, axis=0); fixed = np.delete(fixed, drop + 1)
    try: Rs = F.choose_radii(V_)
    except SystemExit as e: solve.why = '半径を選べない：' + str(e); return None
    with Pool(4) as pool:
        for sw in range(F.SWEEPS):
            iw = len(V_) - 2
            for cls in range(5):
                ids = [i for i in range(1, len(V_) - 1) if i % 5 == cls and not fixed[i]]
                jobs = [(V_, Rs, i) for i in ids]
                res = pool.map(F.best_move, jobs)
                if iw % 5 == cls: res.append(best_move_w((V_, Rs, iw, h)))
                for i, r_ in res:
                    if len(r_) == 4 and (r_[1] or r_[2]): V_[i] = V_[i] + np.array([r_[1], r_[2]])
                    if len(r_) == 4: Rs[i - 1] = r_[3]
            V_, Rs, fixed, nrem, nmer = F.topology(V_, Rs, fixed)
    try: Rs = F.choose_radii(V_)
    except SystemExit as e: solve.why = '半径を選べない（後）：' + str(e); return None
    cost, mx = F.local_cost(V_, Rs, 0, len(V_) - 1, True)
    return dict(sj=float(sj), cost=float(cost), maxdev=float(mx), V=V_.tolist(), Rs=list(map(float, Rs)), J=J.tolist(), h=h.tolist(), dense=dense.tolist())
if __name__ == '__main__':
    t0 = time.time(); fn = f'branch_{NAME}_cands.json'
    done = json.load(open(fn)) if os.path.exists(fn) else {}
    for sj in np.arange(math.ceil(s_lo / STEP) * STEP, s_hi + 0.1, STEP):
        key = f'{sj:.0f}'
        if key in done: continue
        r_ = solve(sj); done[key] = r_ or {'sj': float(sj), 'cost': None}
        json.dump(done, open(fn, 'w'))
        print(f'  分岐器の位置 {sj:.0f} m：' + (f'費用 {r_["cost"]:.0f}、ずれの最大 {r_["maxdev"]:.1f} m、交点 {len(r_["V"]) - 2}' if r_ else '曲線が入らない：' + getattr(solve, 'why', '')) + f'（{time.time() - t0:.0f} 秒）', flush=True)
    ok = [v for v in done.values() if v.get('cost') is not None]
    best = min(ok, key=lambda v: v['cost'])
    print(f'選んだ分岐器の位置：幹線のキロ程 {best["sj"]:.0f} m（費用 {best["cost"]:.0f}、ずれの最大 {best["maxdev"]:.1f} m）')
    json.dump(best, open(f'branch_{NAME}_best.json', 'w'))
    # 組み立て（ipfit_all.solve_chain の最後と同じ）：10 m ごとの点と曲率、要素の並び
    V_ = np.array(best['V']); Rs = best['Rs']; F.TREE = cKDTree(np.array(best['dense']))
    L, u, dl = F.geom(V_); out = [(V_[0], 0.0)]; els = []; pos = 0.0; prev = V_[0]
    for i in range(1, len(V_) - 1):
        j = int(round((Rs[i - 1] - F.RCAT[0]) / 10))
        Pc, k, s, T_ = F.curve_pts(V_[i], u[i - 1], dl[i - 1], Rs[i - 1], F.XL[j])
        ls = np.hypot(*(Pc[0] - prev)); els.append([pos, pos + ls, 'S', 0]); pos += ls
        X = F.XL[j]; A = s[-1] - 2 * X; c = math.copysign(1 / Rs[i - 1], dl[i - 1])
        els += [[pos, pos + X, 'T', [0, round(c * 1e7)]], [pos + X, pos + X + A, 'C', Rs[i - 1]], [pos + X + A, pos + 2 * X + A, 'T', [round(c * 1e7), 0]]]
        pos += s[-1]; prev = Pc[-1]; out += [(p_, kk) for p_, kk in zip(Pc, k)]
    ls = np.hypot(*(V_[-1] - prev)); els.append([pos, pos + ls, 'S', 0]); out.append((V_[-1], 0.0))
    X = np.array([p_ for p_, _ in out]); kk = np.array([q for _, q in out])
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(X, axis=0).T))])
    sg = np.append(np.arange(0, s[-1], 10.0), s[-1])
    Xg = np.c_[np.interp(sg, s, X[:, 0]), np.interp(sg, s, X[:, 1])]
    kg = kk[np.minimum(np.searchsorted(s, sg, side='right'), len(kk) - 1)]
    dv = F.dist(Xg)
    # 停車駅：作図の駅の記号を線形に射影する（並びの順に）
    FIC = {x[0]: (x[3] / 1e5, x[2] / 1e5) for x in json.load(open(__import__('geo').FICTION_JSON, encoding='utf-8'))['stations'] if x[5] == '択捉'}
    stopidx = []; last = 0
    for (nm, _), v in zip(F.r['stations'], F.r['vidx']):
        if nm not in F.r['stops']: continue
        lon_, lat_ = FIC.get(nm, tuple(pts[v])); q = np.array([(lon_ - pts[0][0]) * K, (lat_ - pts[0][1]) * 110570])
        d = np.hypot(*(Xg[last:] - q).T); i = last + int(np.argmin(d)); stopidx.append(i); last = i
        print(f'  駅 {nm}：記号から線形まで {d.min():.0f} m' + ('（D を超える）' if d.min() > D else ''))
    lon = Xg[:, 0] / K + pts[0][0]; lat = Xg[:, 1] / 110570 + pts[0][1]
    RS = np.array(Rs)
    print(f'{NAME}：{len(RS)} 曲線（半径の中央値 {np.median(RS):.0f} m、300 m 未満 {np.sum(RS < 300)}）、長さ {sg[-1] / 1000:.2f} km、ずれ 中央値 {np.median(dv):.1f}・95% {np.percentile(dv, 95):.1f}・最大 {dv.max():.1f} m')
    Jl = [best['J'][0] / K + pts[0][0], best['J'][1] / 110570 + pts[0][1]]
    json.dump({'A': np.c_[lon, lat].tolist(), 's': sg.tolist(), 'k': list(map(float, kg)), 'stopidx': stopidx, 'dev': dv.tolist(), 'elements_flat': els,
               'junction': {'trunk': TRUNK, 's': best['sj'], 'lonlat': Jl, 'side': '左' if SIG > 0 else '右', 'angle_deg': math.degrees(THETA)}},
              open(f'fit_{NAME}.json', 'w'))
