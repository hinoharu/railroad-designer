# 交点法（全区間版、2026-11-03）：ipfit.py の試作を全区間に広げる。
#  - 折り返し駅で線を分け、それぞれを 1 本の折れ線として解く（ほかの停車駅では分けない。駅で線形が折れないように）
#  - 停車駅の頂点は簡略化でも残し、交点としては動かさない（まとめる・取り除く対象にもしない）
#  - 交点を動かす段は、5 つおきの交点（互いの影響の範囲 ±2 が重ならない）をまとめて並列に計算する
# 出力：fit_<名前>.json（A：経緯度、s、k：曲率、stopidx、elements_flat：[始点 m, 終点 m, 種類 S/T/C, 半径 or [曲率, 曲率]]）
# 使い方：python3 ipfit_all.py 名前
import json, math, sys, time, os
import numpy as np
from multiprocessing import Pool
from scipy.spatial import cKDTree
from curves import local
from speed import smooth
from run import reversals
D, LAM, H, W_D = 30.0, 1e5, 30.0, 10.0
RCAT = np.arange(160.0, 5000.1, 10.0); RC20 = RCAT[::2]
SWEEPS = int(os.environ.get('SWEEPS', '3')); OFFS = np.arange(-D, D + 0.1, 5.0)
NAME = sys.argv[1]; t0 = time.time(); REVERSE = bool(os.environ.get('REVERSE'))
r = json.load(open('route_shibetoro_heishi.json')); pts = r['points']; P = local(pts)
K = 111320 * math.cos(math.radians(pts[len(pts) // 2][1]))
stop_v = [v for (n, _), v in zip(r['stations'], r['vidx']) if n in r['stops']]
rev_v = [v for (n, _), v in zip(r['stations'], r['vidx']) if n in set(reversals(r))]
Vk = smooth(RCAT); C = np.minimum(7.552 * Vk * Vk / RCAT, 105.0); XL = np.maximum(np.maximum(0.4 * C, 0.007 * C * Vk), 1.0)
tau = XL / (2 * RCAT); pS = XL ** 2 / (24 * RCAT); mS = XL / 2 - XL ** 3 / (240 * RCAT ** 2)
# 曲線 1 つごとに、最高速度から制限速度へ減速し、また最高速度へ戻るのに余分にかかる時間（秒）。run.py の加速・減速・
# 走行抵抗・列車の長さから求める（2026-11-03。曲線の上を制限速度で走る時間だけでは、急な曲線の損を 1/5 ほどに見積もり、
# 交点法が急な曲線を多く選んで走行時間が 30 分長くなったため）
import run as _run
def _loss(v):
    V = _run.VMAX
    if v >= V - 1e-6: return 0.0
    t = d = 0.0; u = v
    while u < V:
        a = min(_run.A_ADH, _run.P_PER_T / max(u, 1.0)) / _run.MEFF - _run.resist(u, 1e9)
        un = min(V, u + 0.05); t += (un - u) / a; d += (un * un - u * u) / (2 * a); u = un
    return t + (V - v) / _run.BRAKE - (d + (V * V - v * v) / (2 * _run.BRAKE)) / V + _run.TRAIN * (1 / v - 1 / V)
def ftime(k): k = np.maximum(np.abs(k), 1e-9); return 3.6 / smooth(1 / k) - 3.6 / 130
LOSS = np.array([_loss(v / 3.6) for v in Vk])
def pen(d): e = np.maximum(0, d - D); return d * d + (W_D * e) ** 2
TREE = None
def dist(X): return TREE.query(X)[0]
def geom(V_):
    d = np.diff(V_, axis=0); L = np.hypot(*d.T); u = d / L[:, None]
    dl = np.arctan2(u[:-1, 0] * u[1:, 1] - u[:-1, 1] * u[1:, 0], (u[:-1] * u[1:]).sum(1))
    return L, u, dl
def tlen(dl):
    ad = np.abs(dl)[:, None]; T = (RCAT + pS) * np.tan(ad / 2) + mS
    return np.where(ad >= 2 * tau, T, np.inf)
def curve_pts(ip, uin, dl1, R, X):
    ad = abs(dl1); c = math.copysign(1 / R, dl1); A = R * ad - X
    T_ = (R + X * X / (24 * R)) * math.tan(ad / 2) + X / 2 - X ** 3 / (240 * R * R)
    Ltot = 2 * X + A; m = max(2, int(Ltot / 5)); s = np.linspace(0, Ltot, m + 1)
    k = np.where(s < X, c * s / X, np.where(s < X + A, c, c * (Ltot - s) / X))
    th0 = math.atan2(uin[1], uin[0]); h = np.diff(s)
    th = th0 + np.concatenate([[0], np.cumsum(h * (k[1:] + k[:-1]) / 2)]); ph = (th[1:] + th[:-1]) / 2
    Pc = ip - uin * T_ + np.vstack([[0, 0], np.cumsum(h[:, None] * np.c_[np.cos(ph), np.sin(ph)], axis=0)])
    return Pc, k, s, T_
def ipdata(V_, i, R):
    uin = V_[i] - V_[i - 1]; uin = uin / np.hypot(*uin); uo = V_[i + 1] - V_[i]; uo = uo / np.hypot(*uo)
    d1 = math.atan2(uin[0] * uo[1] - uin[1] * uo[0], uin @ uo); j = int(round((R - RCAT[0]) / 10))
    ad = abs(d1); T_ = (R + pS[j]) * math.tan(ad / 2) + mS[j] if ad >= 2 * tau[j] else math.inf
    return uin, uo, d1, T_, j
def defl(V_, i):
    u1 = V_[i] - V_[i - 1]; u2 = V_[i + 1] - V_[i]
    return math.atan2(u1[0] * u2[1] - u1[1] * u2[0], u1 @ u2)
def turnsum(V_, lo, hi):
    """交点 lo+1 〜 hi-1 の中心角（左を正）の合計。両端の直線（lo→lo+1、hi-1→hi）が変わらなければ、手を打っても変わらないはず。
    変わったら、どこかの交点の曲がりが 180° をまたいで裏返った（2026-11-04、ユーザーと合意した決まり：曲がった角度の合計を保つ）"""
    return sum(defl(V_, i) for i in range(lo + 1, hi))
def local_cost(V_, Rs, lo, hi, want_max=False):
    segs = []; ends = []
    for i in range(lo, hi + 1):
        if i == 0 or i == len(V_) - 1: ends.append((V_[i], V_[i])); continue
        uin, uo, d1, T_, j = ipdata(V_, i, Rs[i - 1])
        if not np.isfinite(T_): return (math.inf, math.inf) if want_max else math.inf
        ends.append((V_[i] - uin * T_, V_[i] + uo * T_))
        if lo < i < hi: segs.append((i, uin, d1, j))
    for i in range(hi - lo):
        if (ends[i + 1][0] - ends[i][1]) @ (V_[lo + i + 1] - V_[lo + i]) < -1e-6: return (math.inf, math.inf) if want_max else math.inf
    cost = 0.0; mx = 0.0
    for i in range(hi - lo):
        st = ends[i][1]; ts = ends[i + 1][0]; Ls = np.hypot(*(ts - st))
        if Ls > 0:
            m = max(1, int(Ls / 5)); X = st + (ts - st) * np.linspace(0, 1, m + 1)[:, None]
            dd = dist(X); cost += (pen(dd) * (Ls / m)).sum() / H; mx = max(mx, dd.max())
    for i, uin, d1, j in segs:
        Pc, k, s_, T_ = curve_pts(V_[i], uin, d1, RCAT[j], XL[j]); h = np.gradient(s_)
        dd = dist(Pc); cost += (pen(dd) * h).sum() / H + LAM * ((ftime(k) * h).sum() + LOSS[j]); mx = max(mx, dd.max())
    return (cost, mx) if want_max else cost
def best_move(args):
    V_, Rs, i = args
    lo, hi = max(0, i - 2), min(len(V_) - 1, i + 2)
    uin = V_[i] - V_[i - 1]; uin = uin / np.hypot(*uin); uo = V_[i + 1] - V_[i]; uo = uo / np.hypot(*uo)
    bis = uin - uo; nb = np.hypot(*bis)
    best_ = (local_cost(V_, Rs, lo, hi), 0.0, Rs[i - 1])
    if nb < 1e-9: return i, best_
    bis = bis / nb; V2 = V_.copy(); base = V_[i].copy(); S0 = turnsum(V_, lo, hi)
    for off in OFFS:
        V2[i] = base + bis * off
        if abs(turnsum(V2, lo, hi) - S0) > 1e-6: continue
        for R in RC20:
            Rs2 = list(Rs); Rs2[i - 1] = R
            c = local_cost(V2, Rs2, lo, hi)
            if c < best_[0] - 1e-6: best_ = (c, off, R)
    return i, (best_[0], float(bis[0] * best_[1]), float(bis[1] * best_[1]), best_[2])
def stop_here(V_, i, why):
    x, y = V_[min(i + 1, len(V_) - 1)]
    raise SystemExit(f"止めた：交点 {i + 1}（経度 {x / K + pts[0][0]:.5f}・緯度 {y / 110570 + pts[0][1]:.5f}）で{why}。描いた線のこの所は、規格の曲線では作れない")
def best_r(V_, Rs, i, lo, hi):
    """交点 i の半径を、ほかを固定して選び直す（20 m 刻み）"""
    best_ = (math.inf, Rs[i - 1])
    for R in RC20:
        Rs2 = list(Rs); Rs2[i - 1] = R; c = local_cost(V_, Rs2, lo, hi)
        if c < best_[0]: best_ = (c, R)
    return best_[1]
def topology(V_, Rs, fixed):
    """交点を取り除く・同じ向きの 2 つをまとめる（2026-11-03、ユーザーと合意した条件）：
    停車駅の交点は対象にしない。取り除いた／まとめたあとも曲線が入り、影響する範囲の元の線からのずれの最大が
    max(D, 取り除く前の最大) 以下で、費用（ずれ＋走行時間）が下がるときだけ採る"""
    nrem = nmer = 0; i = 1
    while i < len(V_) - 1:
        if fixed[i]: i += 1; continue
        lo, hi = max(0, i - 2), min(len(V_) - 1, i + 2)
        c0, m0 = local_cost(V_, Rs, lo, hi, True)
        lim = max(D, m0) + 1e-6
        # 取り除く
        V2 = np.delete(V_, i, axis=0); R2 = Rs[:i - 1] + Rs[i:]; f2 = np.delete(fixed, i)
        lo2, hi2 = lo, hi - 1
        for j in (i - 1, i):
            if 0 < j < len(V2) - 1 and not f2[j]: R2[j - 1] = best_r(V2, R2, j, lo2, hi2)
        c1, m1 = local_cost(V2, R2, lo2, hi2, True)
        if c1 < c0 - 1e-6 and m1 <= lim and abs(turnsum(V2, lo2, hi2) - turnsum(V_, lo, hi)) < 1e-6:
            V_, Rs, fixed = V2, R2, f2; nrem += 1; continue
        # 次の交点と同じ向きならまとめる
        if i + 1 < len(V_) - 1 and not fixed[i + 1]:
            u1 = V_[i] - V_[i - 1]; u2 = V_[i + 1] - V_[i]; u3 = V_[i + 2] - V_[i + 1]
            cr = lambda a, b: a[0] * b[1] - a[1] * b[0]
            if np.sign(cr(u1, u2)) == np.sign(cr(u2, u3)) and abs(cr(u1, u3)) > 1e-9:
                t = np.linalg.solve(np.array([u1, -u3]).T, V_[i + 2] - V_[i - 1])
                if t[0] > 0 and t[1] < 0:   # 交点が V[i-1] の前方、V[i+2] の手前にある（2026-11-03 に符号の誤りを直した）
                    X_ = V_[i - 1] + u1 * t[0]
                    hi3 = min(len(V_) - 1, i + 3); c0b, m0b = local_cost(V_, Rs, lo, hi3, True); limb = max(D, m0b) + 1e-6
                    V3 = np.vstack([V_[:i], [X_], V_[i + 2:]]); R3 = Rs[:i - 1] + [Rs[i - 1]] + Rs[i + 1:]; f3 = np.concatenate([fixed[:i], [False], fixed[i + 2:]])
                    R3[i - 1] = best_r(V3, R3, i, lo, hi3 - 1)
                    c3, m3 = local_cost(V3, R3, lo, hi3 - 1, True)
                    if c3 < c0b - 1e-6 and m3 <= limb and abs(turnsum(V3, lo, hi3 - 1) - turnsum(V_, lo, hi3)) < 1e-6:
                        V_, Rs, fixed = V3, R3, f3; nmer += 1; continue
        i += 1
    return V_, Rs, fixed, nrem, nmer
def choose_radii(V_):
    L, u, dl = geom(V_); T = tlen(dl); n = len(dl)
    COST = np.full((n, len(RCAT)), np.inf)
    for i in range(n):
        ip = V_[i + 1]; uin = u[i]; uout = u[i + 1]
        for j, R in enumerate(RCAT):
            if not np.isfinite(T[i, j]) or T[i, j] > L[i] or T[i, j] > L[i + 1]: continue
            Pc, k, s, T_ = curve_pts(ip, uin, dl[i], R, XL[j]); h = np.gradient(s)
            tl = np.linspace(0, T_, max(2, int(T_ / 5)) + 1)
            tp = np.vstack([ip - uin[None] * (T_ - tl)[:, None], ip + uout[None] * tl[:, None]])
            COST[i, j] = (pen(dist(Pc)) * h).sum() / H - (pen(dist(tp)) * (T_ / max(1, len(tl) - 1))).sum() / H + LAM * ((ftime(k) * h).sum() + LOSS[j]) \

    best = COST[0].copy(); back = np.zeros((n, len(RCAT)), int)
    for i in range(1, n):
        ok = (T[i - 1][:, None] + T[i][None, :]) <= L[i]
        tot = np.where(ok, best[:, None], np.inf); back[i] = tot.argmin(0); best = tot.min(0) + COST[i]
        if not np.isfinite(best).any(): stop_here(V_, i, '隣の曲線と重ならずに入る半径の組がない')
    if not np.isfinite(best).any(): stop_here(V_, n - 1, '曲線の入る半径がない')
    ch = [int(best.argmin())]
    for i in range(n - 1, 0, -1): ch.append(back[i][ch[-1]])
    ch = ch[::-1]
    return [RCAT[j] for j in ch]
def solve_chain(v0, v1):
    global TREE
    idx = list(range(v0, v1 + 1)); Q = []; qi = []
    for i in idx:
        if not Q or np.hypot(*(P[i] - Q[-1])) > 0.5: Q.append(P[i]); qi.append(i)
    Q = np.array(Q)
    if REVERSE: Q = Q[::-1].copy(); qi = qi[::-1]
    dense = [Q[0]]
    for p_, q_ in zip(Q, Q[1:]):
        n = max(1, int(np.hypot(*(q_ - p_)) / 2)); dense += [p_ + (q_ - p_) * t for t in np.linspace(0, 1, n + 1)[1:]]
    dense = np.array(dense); TREE = cKDTree(dense)
    # 簡略化（停車駅の頂点は必ず残す）
    forced = [0, len(qi) - 1]   # 線の端（始点・終点・折り返し駅）だけ。停車駅は線形を描いたあとに射影する
    sel = [forced[0]]
    def dp(i, j, out):
        A_, B_ = Q[i], Q[j]; d = B_ - A_; L = np.hypot(*d) or 1
        if j <= i + 1: return
        e = np.abs(d[0] * (Q[i + 1:j, 1] - A_[1]) - d[1] * (Q[i + 1:j, 0] - A_[0])) / L
        if e.max() > D: k = i + 1 + int(e.argmax()); dp(i, k, out); out.append(k); dp(k, j, out)
    for a_, b_ in zip(forced, forced[1:]):
        mid = []; dp(a_, b_, mid); sel += mid + [b_]
    V_ = Q[sel]; fixed = np.array([k in (0, len(qi) - 1) for k in sel])
    nm = nd = 0
    while True:
        L, u, dl = geom(V_); T = tlen(dl); Tmin = T.min(1)
        bad = [i for i in range(len(dl) - 1) if np.sign(dl[i]) == np.sign(dl[i + 1]) and Tmin[i] + Tmin[i + 1] > L[i + 1] and not fixed[i + 1] and not fixed[i + 2]]

        rev = [i for i in range(len(dl) - 1) if np.sign(dl[i]) != np.sign(dl[i + 1]) and Tmin[i] + Tmin[i + 1] > L[i + 1]]
        ends = [i for i in (0, len(dl) - 1) if Tmin[i] > L[i if i == 0 else i + 1] and not fixed[i + 1]]
        cand = [i for i in rev if not (fixed[i + 1] and fixed[i + 2])]
        if not bad and not cand and not ends:
            left = [i for i in range(len(dl) - 1) if Tmin[i] + Tmin[i + 1] > L[i + 1]]
            if left: stop_here(V_, left[0], '最小半径の曲線どうしでも重なる（線の端のそば）')
            break
        if bad:
            i = min(bad, key=lambda i: L[i + 1])
            p1, d1 = V_[i], u[i]; p2, d2 = V_[i + 3], -u[i + 2]
            t = np.linalg.solve(np.array([d1, -d2]).T, p2 - p1); X_ = p1 + d1 * t[0]
            V_ = np.vstack([V_[:i + 1], [X_], V_[i + 3:]]); fixed = np.concatenate([fixed[:i + 1], [False], fixed[i + 3:]]); nm += 1; continue
        if cand:
            i = min(cand, key=lambda i: L[i + 1])
            drop = i if (abs(dl[i]) < abs(dl[i + 1]) and not fixed[i + 1]) or fixed[i + 2] else i + 1
        else: drop = ends[0]
        V_ = np.delete(V_, drop + 1, axis=0); fixed = np.delete(fixed, drop + 1); nd += 1
    Rs = choose_radii(V_)
    # 交点を動かす（停車駅の交点は動かさない）。互いに影響しない 5 つおきの交点をまとめて並列に
    with Pool(4) as pool:
        for sw in range(SWEEPS):
            moved = 0
            for cls in range(5):
                ids = [i for i in range(1, len(V_) - 1) if i % 5 == cls and not fixed[i]]
                for i, res in pool.map(best_move, [(V_, Rs, i) for i in ids]):
                    if len(res) == 4 and (res[1] or res[2]):
                        V_[i] = V_[i] + np.array([res[1], res[2]]); Rs[i - 1] = res[3]; moved += 1
                    elif len(res) == 4: Rs[i - 1] = res[3]
            V_, Rs, fixed, nrem, nmer = topology(V_, Rs, fixed)
            print(f"    {sw + 1} 回目：動かした交点 {moved}・取り除いた {nrem}・まとめた {nmer}・残り {len(V_) - 2}（{time.time() - t0:.0f} 秒）", flush=True)
    Rs = choose_radii(V_)
    # 組み立て：10 m ごとの点と曲率、要素の並び
    L, u, dl = geom(V_)
    out = [(V_[0], 0.0)]; els = []; pos = 0.0; prev = V_[0]
    for i in range(1, len(V_) - 1):
        j = int(round((Rs[i - 1] - RCAT[0]) / 10))
        Pc, k, s, T_ = curve_pts(V_[i], u[i - 1], dl[i - 1], Rs[i - 1], XL[j])
        ls = np.hypot(*(Pc[0] - prev)); els.append([pos, pos + ls, 'S', 0]); pos += ls
        X = XL[j]; A = s[-1] - 2 * X; c = math.copysign(1 / Rs[i - 1], dl[i - 1])
        els += [[pos, pos + X, 'T', [0, round(c * 1e7)]], [pos + X, pos + X + A, 'C', Rs[i - 1]], [pos + X + A, pos + 2 * X + A, 'T', [round(c * 1e7), 0]]]
        pos += s[-1]; prev = Pc[-1]
        out += [(p_, kk) for p_, kk in zip(Pc, k)]
    ls = np.hypot(*(V_[-1] - prev)); els.append([pos, pos + ls, 'S', 0])
    out.append((V_[-1], 0.0))
    X = np.array([p_ for p_, _ in out]); kk = np.array([q for _, q in out])
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(X, axis=0).T))])
    sg = np.arange(0, s[-1], 10.0); sg = np.append(sg, s[-1])
    Xg = np.c_[np.interp(sg, s, X[:, 0]), np.interp(sg, s, X[:, 1])]
    kg = kk[np.minimum(np.searchsorted(s, sg, side='right'), len(kk) - 1)]
    if REVERSE:   # 元の向きに戻す（曲率の左右も入れ替わる）
        Xg = Xg[::-1].copy(); kg = -kg[::-1]; sg = sg[-1] - sg[::-1]
        els = [[sg[-1] - b_, sg[-1] - a_, t_, (x if t_ != 'T' else [-x[1], -x[0]])] for a_, b_, t_, x in els[::-1]]
    dv = dist(Xg); dB = cKDTree(Xg).query(dense)[0]
    print(f"  {len(V_) - 2} 交点（まとめた {nm}・取り除いた {nd}）：ずれ 中央値 {np.median(dv):.1f}・95% {np.percentile(dv, 95):.1f}・最大 {max(dv.max(), dB.max()):.1f} m（{time.time() - t0:.0f} 秒）", flush=True)
    return Xg, kg, sg, els, np.array(Rs), dv
# 折り返し駅で分ける
cuts = sorted(set([stop_v[0]] + rev_v + [stop_v[-1]]))
AX = []; AK = []; AS = []; EL = []; RS = []; DV = []; off = 0.0
for v0, v1 in zip(cuts, cuts[1:]):
    print(f"線 {v0}→{v1}", flush=True)
    Xg, kg, sg, els, Rs_, dv = solve_chain(v0, v1)
    if AX: Xg, kg, sg, dv = Xg[1:], kg[1:], sg[1:], dv[1:]
    AX += list(Xg); AK += list(kg); AS += list(sg + off); EL += [[a + off, b + off, t_, x] for a, b, t_, x in els]; RS += list(Rs_); DV += list(dv); off = AS[-1]
AX = np.array(AX); AS = np.array(AS)
# 停車駅の点の番号（並びの順に、最も近い点）
FIC = {x[0]: (x[3] / 1e5, x[2] / 1e5) for x in json.load(open(__import__('geo').FICTION_JSON, encoding='utf-8'))['stations'] if x[5] == '択捉'}
stop_names = [n for (n, _), vv in zip(r['stations'], r['vidx']) if n in r['stops']]
stopidx = []; last = 0; sdev = []
for nm, v in zip(stop_names, stop_v):
    lon_, lat_ = FIC.get(nm, (pts[v][0], pts[v][1])); q = np.array([(lon_ - pts[0][0]) * K, (lat_ - pts[0][1]) * 110570])
    d = np.hypot(*(AX[last:] - q).T); i = last + int(np.argmin(d)); stopidx.append(i); last = i; sdev.append((nm, float(d.min())))
print('停車駅の記号から線形までの距離：', '・'.join(f'{n} {x:.0f} m' for n, x in sdev))
# 駅の記号と線形が、ずれの上限 D（30 m）より離れたら警告（2026-11-04、ユーザーの指定。止めはしない）
for n_, x_ in sdev:
    if x_ > D: print(f'警告：{n_} 駅の記号から線形まで {x_:.0f} m（ずれの上限 {D:.0f} m を超える）')
lon = AX[:, 0] / K + pts[0][0]; lat = AX[:, 1] / 110570 + pts[0][1]
DV = np.array(DV); RS = np.array(RS)
print(f"全体：{len(RS)} 曲線（半径の中央値 {np.median(RS):.0f} m、300 m 未満 {np.sum(RS < 300)}）  ずれ 中央値 {np.median(DV):.1f}・95% {np.percentile(DV, 95):.1f}・最大 {DV.max():.1f} m  "
      f"曲線による時間の増分 {(ftime(np.array(AK)) * np.gradient(AS)).sum() / 60:.1f} 分  計算 {time.time() - t0:.0f} 秒")
json.dump({'A': np.c_[lon, lat].tolist(), 's': AS.tolist(), 'k': list(map(float, AK)), 'stopidx': stopidx, 'dev': DV.tolist(), 'elements_flat': EL}, open(f'fit_{NAME}.json', 'w'))
