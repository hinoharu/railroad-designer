# 支線の交点法（2026-11-04、ユーザーと決めた規則。両端の分岐に広げた版。片端だけの版は ipfit_branch_v1.py）：
#  - 支線の端が幹線（線の順位が上の線）の線形につながるとき、支線の線形はその端で幹線の上の 1 点（分岐器の位置 J）に着く。
#    J での向きは、幹線の向きに分岐器の角度 θ＝atan(1/12)（12 番）を加えた向きで、作図で支線がある側から寄せる。
#    支線がどちら向きに分かれるか（幹線のキロ程の増える向きか減る向きか）は、作図の線の向きから決める
#  - 候補：作図の支線が幹線の線形から D（30 m）以内にある点を幹線に射影した範囲を 10 m 刻みで。D 以内の点がない端は、
#    作図の端の点を射影した位置だけ。D 以内の作図の点は幹線に重なる部分とみなし、ずれを測る線から除く
#  - 選び方：端ごとに、端から最寄りの駅（端の駅を除く）までの部分だけを解いて費用（ずれ＋走行時間）が最も小さい候補を選び、
#    そのあと全体を 1 回解く（両端の組み合わせをすべて解くと時間がかかりすぎるため。区切りに駅を使い、距離のしきい値を置かない）
#  - 端の交点 W は、J を通り J での向きの直線の上だけを動かす（端の直線の向きを保つ）。W は取り除かない。W の隣の交点とは
#    まとめてよい（まとめた点は同じ直線の上にあるので、新しい W になる）
# 使い方：VMAX=100 TILT=0 TRAIN=85 python3 ipfit_branch.py 名前 経路.json 幹線の fit.json [start] [end]
#   start / end：その端を幹線につなぐ（省略すると end だけ）。候補ごとの結果を branch_<名前>_cands.json に保存し、途中から再開できる
import json, math, sys, os, time
import numpy as np
from multiprocessing import Pool
from scipy.spatial import cKDTree
import ipfit_all as F
SWEEP_STOP = os.environ.get('SWEEP_STOP', '1') != '0'   # なめ直しで何も変わらなければ止める（結果は同じ。2026-11-08）
JSCAN = os.environ.get('JSCAN', 'coarse')   # 分岐器の候補：full＝10 m 刻みを全部。coarse＝100 m 刻み → 最良の周り ±100 m を 10 m 刻み（2026-11-08）
FAST = os.environ.get('FAST', '1') != '0'   # 機械語の版（ipfit_fast.py）を使う（2026-11-08）。FAST=0 で元のまま
if FAST: import ipfit_fast as _X
NAME, ROUTE, TRUNK = sys.argv[1], sys.argv[2], sys.argv[3]
# 端ごとに、つながる上位の線を替えられる（「start=fit_x.json」の形。両端が別々の線につながる線：冬知里支線・小田萌線。2026-11-04）
ENDS = [a.split('=')[0] for a in sys.argv[4:] if a.split('=')[0] in ('start', 'end')] or ['end']
# どちらの端も上位の線につながない（引数 free。スイッチバック駅で分けた先の区間：阿登佐線の散布泊〜阿登佐岳、2026-11-06）
if 'free' in sys.argv[4:]: ENDS = []
TRUNKS = {w: TRUNK for w in ENDS}; TRUNKS.update({a.split('=')[0]: a.split('=')[1] for a in sys.argv[4:] if '=' in a})
D = F.D; THETA = math.atan(1 / 12); STEP = 10.0
F.load_route(ROUTE)
P = F.P; pts = F.pts; K = F.K
TR = {}
for w_, f_ in TRUNKS.items():
    T_ = json.load(open(f_)); TA_ = np.array(T_['A']); TS_ = np.array(T_['s'])
    TP_ = np.c_[(TA_[:, 0] - pts[0][0]) * K, (TA_[:, 1] - pts[0][1]) * 110570]
    dq_, iq_ = cKDTree(TP_).query(P); TR[w_] = (TS_, TP_, dq_, iq_)
def trunk_at(s, w):
    TS, TP = TR[w][0], TR[w][1]
    f = lambda q: np.array([np.interp(q, TS, TP[:, 0]), np.interp(q, TS, TP[:, 1])])
    t = f(s + 5) - f(s - 5); return f(s), t / np.hypot(*t)
rot = lambda v, a: np.array([math.cos(a) * v[0] - math.sin(a) * v[1], math.sin(a) * v[0] + math.cos(a) * v[1]])

def end_info(idx, w):
    """端の情報。idx：作図の点の番号を、その端へ向かう順に並べたもの。返す：重なりの手前の番号の並び、候補のキロ程、向きの決め方"""
    TS, TP, dq, iq = TR[w]
    near = [k for k, i in enumerate(idx) if dq[i] <= D]
    # 重なり：端から続けて D 以内にある点（途中で D を超えたら、そこまで）
    m = len(idx)
    while m > 0 and dq[idx[m - 1]] <= D: m -= 1
    if m == len(idx): m = len(idx) - 1   # D 以内の点がない端：端の点だけを幹線に重なる点とする
    cand_s = sorted(TS[iq[idx[k]]] for k in range(m, len(idx)))
    lo, hi = cand_s[0], cand_s[-1]
    # 向き：重なりの手前の 3 点の向き（端へ向かう向き）と、幹線の向き
    # 幹線の向きは候補の範囲の中央で測る（作図の点に最も近い幹線の点で測ると、幹線が同じ所を 2 回通る駅（紗那の折り返し）で
    # 反対向きの線を拾い、支線が逆向きに出た。2026-11-04）
    a, b = idx[max(0, m - 3)], idx[m - 1]
    u = P[b] - P[a]; J0, t0 = trunk_at((lo + hi) / 2, w)
    tau = 1.0 if u @ t0 >= 0 else -1.0
    side = []
    for k in range(max(0, m - 3), m):
        v = P[idx[k]] - J0; base = t0 * tau
        side.append(np.sign(base[0] * v[1] - base[1] * v[0]))
    sig = 1.0 if sum(side) > 0 else -1.0
    # 分かれる向きの指定（環境変数 DIR_start・DIR_end：支線を分岐点に向かって走ってきた列車が幹線をキロ程の増える向きに進むなら forward、減る向きなら backward。
    # 2026-11-07、国後空港線：作図の支線が幹線とほぼ直角で、内積の符号による判定が逆向きになった。入力表 fit.dir）
    dir_ = os.environ.get(f'DIR_{w}')
    if dir_ in ('forward', 'backward'):
        tau2 = 1.0 if dir_ == 'forward' else -1.0
        if tau2 != tau:
            print(f'  {w}：分かれる向きを指定 {dir_} に合わせる（作図から判定した向きと逆）', flush=True)
            tau = tau2; sig = -sig   # 向きを反転すると、作図の支線がある側も左右が入れ替わる
    return idx[:m], lo, hi, tau, sig, w

def junction(sj, tau, sig, w):
    """J と、J へ向かう向き h（支線は幹線の向き τ t に、作図の側 σ から θ で寄せる）"""
    J, t = trunk_at(sj, w); return J, rot(t * tau, -sig * THETA)

OFFS = F.OFFS
def best_move_w(args):
    """端の交点 W を、J を通る直線（J から W への単位ベクトル e）の上で動かす（半径も選び直す）"""
    V_, Rs, i, J, e = args
    lo, hi = max(0, i - 2), min(len(V_) - 1, i + 2)
    best_ = (F.local_cost(V_, Rs, lo, hi), 0.0, Rs[i - 1]); V2 = V_.copy(); base = V_[i].copy(); S0 = F.turnsum(V_, lo, hi)
    a0 = float((base - J) @ e)
    for off in OFFS:
        if a0 + off <= 1.0: continue
        V2[i] = base + e * off
        if abs(F.turnsum(V2, lo, hi) - S0) > 1e-6: continue
        for R in F.RC20:
            Rs2 = list(Rs); Rs2[i - 1] = R; c = F.local_cost(V2, Rs2, lo, hi)
            if c < best_[0] - 1e-6: best_ = (c, off, R)
    return i, (best_[0], float(e[0] * best_[1]), float(e[1] * best_[1]), best_[2])

def solve(core, js, je, sweeps=F.SWEEPS):
    """core：作図の点の番号（重なりを除く、始点から終点の順）。js / je：始点・終点の (J, h) または None（作図の点で止める）。
    h は、始点では J から離れる向き、終点では J へ向かう向き"""
    Q = [P[i] for i in core]; fixed_idx = []
    if js is not None:
        J, h = js; ag = max(10.0, float((Q[0] - J) @ h)); Q = [J, J + h * ag] + Q
    if je is not None:
        J, h = je; ag = max(10.0, float((J - Q[-1]) @ h)); Q = Q + [J - h * ag, J]
    Q = np.array([q for k, q in enumerate(Q) if k == 0 or np.hypot(*(q - Q[k - 1])) > 0.5])
    if FAST: _X.set_polyline(Q)   # 元の折れ線（線分への距離を測る。線分を格子に登録する）
    dense = [Q[0]]
    for p_, q_ in zip(Q, Q[1:]):
        n = max(1, int(np.hypot(*(q_ - p_)) / 2)); dense += [p_ + (q_ - p_) * u for u in np.linspace(0, 1, n + 1)[1:]]
    dense = np.array(dense); F.TREE = cKDTree(dense)
    a_ = 1 if js is not None else 0; b_ = len(Q) - 2 if je is not None else len(Q) - 1
    sel = list(range(0, a_ + 1))
    def dp(i, j, out):
        A_, B_ = Q[i], Q[j]; d = B_ - A_; L = np.hypot(*d) or 1
        if j <= i + 1: return
        e = np.abs(d[0] * (Q[i + 1:j, 1] - A_[1]) - d[1] * (Q[i + 1:j, 0] - A_[0])) / L
        if e.max() > D: k = i + 1 + int(e.argmax()); dp(i, k, out); out.append(k); dp(k, j, out)
    mid = []; dp(a_, b_, mid); sel += mid + list(range(b_, len(Q)))
    sel = sorted(set(sel)); V_ = Q[sel]
    n = len(V_); fixed = np.zeros(n, bool); fixed[0] = fixed[-1] = True
    WS = 1 if js is not None else None
    if js is not None: fixed[1] = True
    if je is not None: fixed[n - 2] = True
    def wlist(V_):
        out = []
        if js is not None: out.append((1, js[0]))
        if je is not None: out.append((len(V_) - 2, je[0]))
        return out
    # 曲線の入らない並びを整える（ipfit_all.solve_chain と同じ手順。端と W は動かさない。W とその隣はまとめてよい）
    while True:
        L, u, dl = F.geom(V_); Tt = F.tlen(dl); Tmin = Tt.min(1); nW = len(V_) - 2
        isW = lambda k: (js is not None and k == 1) or (je is not None and k == nW)
        bad = [i for i in range(len(dl) - 1) if np.sign(dl[i]) == np.sign(dl[i + 1]) and Tmin[i] + Tmin[i + 1] > L[i + 1]
               and (not fixed[i + 1] or isW(i + 1)) and (not fixed[i + 2] or isW(i + 2)) and not (isW(i + 1) and isW(i + 2))]
        rev = [i for i in range(len(dl) - 1) if np.sign(dl[i]) != np.sign(dl[i + 1]) and Tmin[i] + Tmin[i + 1] > L[i + 1]]
        cand = [i for i in rev if not (fixed[i + 1] and fixed[i + 2])]
        ends = [i for i in (0, len(dl) - 1) if Tmin[i] > L[i if i == 0 else i + 1] and not fixed[i + 1]]   # 作図の点で止まる端（W のない端）
        if ends and not bad and not cand:
            V_ = np.delete(V_, ends[0] + 1, axis=0); fixed = np.delete(fixed, ends[0] + 1); continue
        if not bad and not cand:
            left = [i for i in range(len(dl) - 1) if Tmin[i] + Tmin[i + 1] > L[i + 1]]
            moved = False
            for k, J in wlist(V_):   # W の曲線が J の手前に入らない：W を J から遠ざける
                Lk = L[0] if k == 1 else L[-1]; Tk = Tmin[0] if k == 1 else Tmin[-1]
                if Tk > Lk:
                    e = (V_[k] - J) / np.hypot(*(V_[k] - J)); V_[k] = J + e * (np.hypot(*(V_[k] - J)) + 10.0); moved = True
                    if np.hypot(*(V_[k] - J)) > 3000: solve.why = 'W を 3 km 遠ざけても入らない'; return None
            if moved: continue
            if left: solve.why = f'隣り合う曲線が重なる（交点 {left[0] + 1}、全 {len(V_) - 2}）'; return None
            break
        if bad:
            i = min(bad, key=lambda i: L[i + 1])
            p1, d1 = V_[i], u[i]; p2, d2 = V_[i + 3], -u[i + 2]
            tt = np.linalg.solve(np.array([d1, -d2]).T, p2 - p1); X_ = p1 + d1 * tt[0]
            newW = isW(i + 1) or isW(i + 2)
            if newW:
                J, e = (V_[0], u[0]) if isW(i + 1) else (V_[-1], -u[-1])
                if not (float((X_ - J) @ e) > 1.0): solve.why = 'W とその隣をまとめた点が J の外にある'; return None
            V_ = np.vstack([V_[:i + 1], [X_], V_[i + 3:]]); fixed = np.concatenate([fixed[:i + 1], [newW], fixed[i + 3:]]); continue
        i = min(cand, key=lambda i: L[i + 1])
        drop = i if (abs(dl[i]) < abs(dl[i + 1]) and not fixed[i + 1]) or fixed[i + 2] else i + 1
        V_ = np.delete(V_, drop + 1, axis=0); fixed = np.delete(fixed, drop + 1)
    try: Rs = F.choose_radii(V_)
    except SystemExit as e: solve.why = '半径を選べない：' + str(e); return None
    with Pool(4) as pool:
        for sw in range(sweeps):
            changed = 0
            for cls in range(5):
                ws = wlist(V_)
                ids = [i for i in range(1, len(V_) - 1) if i % 5 == cls and not fixed[i]]
                res = pool.map(F.best_move, [(V_, Rs, i) for i in ids])
                for k, J in ws:
                    if k % 5 == cls: res.append(best_move_w((V_, Rs, k, J, (V_[k] - J) / np.hypot(*(V_[k] - J)))))
                for i, r_ in res:
                    if len(r_) == 4 and (r_[1] or r_[2]): V_[i] = V_[i] + np.array([r_[1], r_[2]]); changed += 1
                    if len(r_) == 4:
                        if Rs[i - 1] != r_[3]: changed += 1
                        Rs[i - 1] = r_[3]
            V_, Rs, fixed, nrem, nmer = F.topology(V_, Rs, fixed)
            if SWEEP_STOP and changed == 0 and nrem == 0 and nmer == 0: break   # 何も変わらなければ、残りのなめ直しは同じ結果なので止める（2026-11-08）
    try: Rs = F.choose_radii(V_)
    except SystemExit as e: solve.why = '半径を選べない（後）：' + str(e); return None
    cost, mx = F.local_cost(V_, Rs, 0, len(V_) - 1, True)
    return dict(cost=float(cost), maxdev=float(mx), V=V_.tolist(), Rs=list(map(float, Rs)), dense=dense.tolist())

# 分岐器の候補の制限（2026-11-08、ユーザーの指摘：分岐器が停車場中心の真上に置かれ、構内の有効長が取れない。分岐点の本線が急勾配）
# JMIN：停車場中心から分岐器までの最小距離（m）。列車が幹線から支線へ入るときに通る駅の、進行方向の先（−τ の側）に置く。
#   候補の範囲がすべて近すぎるときは、最小距離の所から JEXT（300 m）先まで 10 m 刻みで候補を延ばす。幹線が駅で終わっていて置けないときは今までどおり（注意を出す）
# GJ：分岐点の本線の勾配の上限（‰）。超える候補は除く（残らなければ除かずに注意を出す）
JMIN = float(os.environ.get('JMIN', '0')); GJ = float(os.environ.get('GJ', '0')); JEXT = float(os.environ.get('JEXT', '300'))
# VCR：縦曲線の半径（m）。幹線の勾配変化点（変化 0.5‰ 以上）から接線長 T ＝ VCR × |Δi| ÷ 2 未満の候補は除く（縦曲線に分岐器を設けない。解釈基準 Ⅲ－１２(3)①。
#   docs/vertical_curve.md 4.3。残らなければ除かずに注意を出す）。0 で切
VCR = float(os.environ.get('VCR', '0'))
def restrict(lo, hi, tau, w):
    """候補 sj の並びと、基準にした幹線の駅（名前、幹線のキロ程）"""
    TS = TR[w][0]; tid = TRUNKS[w][4:-5]
    cands = list(np.arange(math.ceil(lo / STEP) * STEP, hi + 0.1, STEP)) if hi - lo >= STEP else [round(lo)]
    if JMIN <= 0 and GJ <= 0: return cands, None
    rt = json.load(open(f'route_f{tid}.json')); RS = np.array(rt['s'])
    fit_of = lambda sg: float(np.interp(sg, RS, TS)); ground_of = lambda sf: float(np.interp(sf, TS, RS))
    name, c = min(((n_, fit_of(c_)) for n_, c_ in rt['stations']), key=lambda x: abs(x[1] - (lo + hi) / 2))
    if JMIN > 0:
        side = -tau   # 列車が幹線から支線へ入るときに通る駅の先（進行方向の先）に置く。start・end とも −τ の側（2026-11-08 に確かめた：国後空港線・古釜布支線）
        ok = [s_ for s_ in cands if side * (s_ - c) >= JMIN]
        if not ok:
            a_ = c + side * JMIN; b_ = a_ + side * JEXT; a_, b_ = sorted((a_, b_))
            a_, b_ = max(a_, float(TS[0])), min(b_, float(TS[-1]))
            if b_ - a_ >= STEP: ok = list(np.arange(math.ceil(a_ / STEP) * STEP, b_ + 0.1, STEP)); print(f'  {w}：停車場中心（{name}）から {JMIN:.0f} m 以内の候補しかないので、{a_:.0f}〜{b_:.0f} m に候補を延ばす', flush=True)
            else: print(f'  {w}：幹線が駅（{name}）で終わっていて、停車場中心から {JMIN:.0f} m 離した所に分岐器を置けない。今までどおりの候補で続ける', flush=True); ok = cands
        else: print(f'  {w}：停車場中心（{name}）から {JMIN:.0f} m 以上離れた候補 {len(ok)}（{len(cands)} のうち）', flush=True)
        cands = ok
    # 幹線の縦断（駅地平化）は tables/net.py の design_files で引く（古い手順の ipg は design_fipgh_gs.json。design_f{tid}.json を直接
    # 探していて ipg につながる端で GJ が効いていなかった。2026-11-08）
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tables')); import net as _net
    dfile_ = _net.design_files(tid)[1] if tid in _net.SEC else f'design_f{tid}.json'
    if GJ > 0 and os.path.exists(dfile_):
        d_ = json.load(open(dfile_)); ds_ = np.array(d_['s']); dz_ = np.array(d_['z'])
        def grade(sf):
            sg = ground_of(sf); z1 = float(np.interp(sg - 50, ds_, dz_)); z2 = float(np.interp(sg + 50, ds_, dz_)); return (z2 - z1) / 100 * 1000
        ok = [s_ for s_ in cands if abs(grade(s_)) <= GJ + 1e-9]
        if ok: print(f'  {w}：分岐点の本線の勾配が {GJ:.0f}‰ 以下の候補 {len(ok)}（{len(cands)} のうち）', flush=True); cands = ok
        else: print(f'  {w}：分岐点の本線の勾配が {GJ:.0f}‰ 以下の候補がない（最小 {min(abs(grade(s_)) for s_ in cands):.1f}‰）。除かずに続ける', flush=True)
    if VCR > 0 and os.path.exists(dfile_):
        d_ = json.load(open(dfile_)); sn_ = np.array(d_['sn']); zn_ = np.array(d_['zn']); g_ = np.diff(zn_) / np.diff(sn_) * 1000; di_ = np.diff(g_)
        chg = [(sn_[k + 1], VCR * abs(di_[k]) / 1000 / 2) for k in range(len(di_)) if abs(di_[k]) >= 0.5]   # （変化点の位置, 接線長 T）
        def clear(sf):
            sg = ground_of(sf); return all(abs(sg - x_) >= t_ - 1e-9 for x_, t_ in chg)
        ok = [s_ for s_ in cands if clear(s_)]
        if ok: print(f'  {w}：幹線の縦曲線（R {VCR:.0f} m）の外の候補 {len(ok)}（{len(cands)} のうち）', flush=True); cands = ok
        else: print(f'  {w}：幹線の縦曲線の外に候補がない。除かずに続ける', flush=True)
    return cands, (name, c)

def station_cut(which):
    """端から最寄りの駅（端の駅を除く）の作図の点の番号"""
    vs = sorted(set(F.r['vidx']))
    return vs[1] if which == 'start' else vs[-2]

if FAST: _X.install()
if __name__ == '__main__':
    t0 = time.time(); fn = f'branch_{NAME}_cands.json'
    done = json.load(open(fn)) if os.path.exists(fn) else {}
    n = len(P); info = {}
    if 'start' in ENDS: info['start'] = end_info(list(range(n - 1, -1, -1)), 'start')
    if 'end' in ENDS: info['end'] = end_info(list(range(n)), 'end')
    lo_core = (n - 1 - (len(info['start'][0]) - 1)) if 'start' in info else 0
    hi_core = (len(info['end'][0]) - 1) if 'end' in info else n - 1
    best = {}
    for w, (core_rev, lo, hi, tau, sig, _w) in list(info.items()):
        print(f'{NAME}・{w}：幹線のキロ程 {lo:.0f}〜{hi:.0f} m、支線は幹線の{"左" if sig > 0 else "右"}側、幹線のキロ程が{"増える" if tau > 0 else "減る"}向きにつながる', flush=True)
        cut = station_cut(w)
        cands, near_st = restrict(lo, hi, tau, w); info[w] = info[w] + (near_st,)
        if JSCAN == 'coarse' and len(cands) > 20:   # 100 m 刻みで見てから、最良の周り ±100 m を 10 m 刻みで（候補の費用は位置に対して滑らか）
            coarse = cands[::10] + ([cands[-1]] if cands[-1] not in cands[::10] else [])
            print(f'  {w}：候補 {len(cands)} のうち、まず 100 m 刻みの {len(coarse)} を解く', flush=True)
        else: coarse = None
        for sj in (coarse if coarse else cands) + (['refine'] if coarse else []):
            if sj == 'refine':   # 粗い段の最良の周りを細かく
                ok0 = [v for k, v in done.items() if k.startswith(w + ':') and v['cost'] is not None and any(abs(v['sj'] - s_) < 0.5 for s_ in coarse)]
                if not ok0: break
                b0 = min(ok0, key=lambda v: v['cost'])['sj']; fine = [s_ for s_ in cands if abs(s_ - b0) <= 100 + 0.5 and s_ not in coarse]
                print(f'  {w}：粗い段の最良 {b0:.0f} m の周りの {len(fine)} を解く', flush=True); cands = coarse + fine
                for sj in fine:
                    key = f'{w}:{sj:.0f}'
                    if key not in done:
                        J, h = junction(sj, tau, sig, w)
                        if w == 'end': r_ = solve(list(range(cut, hi_core + 1)), None, (J, h))
                        else: r_ = solve(list(range(lo_core, cut + 1)), (J, -h), None)
                        done[key] = {'sj': float(sj), 'cost': r_['cost'], 'maxdev': r_['maxdev']} if r_ else {'sj': float(sj), 'cost': None, 'why': getattr(solve, 'why', '')}
                        json.dump(done, open(fn, 'w'))
                    v = done[key]
                    print(f'  {w} {sj:.0f} m：' + (f'費用 {v["cost"]:.0f}、ずれの最大 {v["maxdev"]:.1f} m' if v['cost'] is not None else '曲線が入らない：' + v.get('why', '')) + f'（{time.time() - t0:.0f} 秒）', flush=True)
                break
            key = f'{w}:{sj:.0f}'
            if key not in done:
                J, h = junction(sj, tau, sig, w)
                if w == 'end': r_ = solve(list(range(cut, hi_core + 1)), None, (J, h))
                else: r_ = solve(list(range(lo_core, cut + 1)), (J, -h), None)
                done[key] = {'sj': float(sj), 'cost': r_['cost'], 'maxdev': r_['maxdev']} if r_ else {'sj': float(sj), 'cost': None, 'why': getattr(solve, 'why', '')}
                json.dump(done, open(fn, 'w'))
            v = done[key]
            print(f'  {w} {sj:.0f} m：' + (f'費用 {v["cost"]:.0f}、ずれの最大 {v["maxdev"]:.1f} m' if v['cost'] is not None else '曲線が入らない：' + v.get('why', '')) + f'（{time.time() - t0:.0f} 秒）', flush=True)
        ok = [v for k, v in done.items() if k.startswith(w + ':') and v['cost'] is not None and any(abs(v['sj'] - s_) < 0.5 for s_ in cands)]
        best[w] = min(ok, key=lambda v: v['cost'])['sj']
        print(f'  選んだ分岐器の位置（{w}）：幹線のキロ程 {best[w]:.0f} m', flush=True)
    js = junction(best['start'], *info['start'][3:6]) if 'start' in best else None
    if js: js = (js[0], -js[1])
    je = junction(best['end'], *info['end'][3:6]) if 'end' in best else None
    res = solve(list(range(lo_core, hi_core + 1)), js, je)
    if res is None: raise SystemExit('全体：曲線が入らない：' + getattr(solve, 'why', ''))
    print(f'全体：費用 {res["cost"]:.0f}、ずれの最大 {res["maxdev"]:.1f} m、交点 {len(res["V"]) - 2}（{time.time() - t0:.0f} 秒）', flush=True)
    # 組み立て（ipfit_all.solve_chain の最後と同じ）：10 m ごとの点と曲率、要素の並び
    V_ = np.array(res['V']); Rs = res['Rs']; F.TREE = cKDTree(np.array(res['dense']))
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
    # 停車駅：作図の駅の記号を線形に射影する（並びの順に）。端の駅は幹線の駅なので警告しない
    FIC = {x[0]: (x[3] / 1e5, x[2] / 1e5) for x in json.load(open(__import__('geo').FICTION_JSON, encoding='utf-8'))['stations'] if x[5] == '択捉'}
    stopidx = []; last = 0; names = [nm for (nm, _), v in zip(F.r['stations'], F.r['vidx']) if nm in F.r['stops']]
    for k_, ((nm, _), v) in enumerate((x for x in zip(F.r['stations'], F.r['vidx']) if x[0][0] in F.r['stops'])):
        lon_, lat_ = FIC.get(nm, tuple(pts[v])); q = np.array([(lon_ - pts[0][0]) * K, (lat_ - pts[0][1]) * 110570])
        d = np.hypot(*(Xg[last:] - q).T); i = last + int(np.argmin(d)); stopidx.append(i); last = i
        at_end = (k_ == 0 and js is not None) or (k_ == len(names) - 1 and je is not None)
        print(f'  駅 {nm}：記号から線形まで {d.min():.0f} m' + ('（端の駅：幹線の駅）' if at_end else '（D を超える）' if d.min() > D else ''))
    lon = Xg[:, 0] / K + pts[0][0]; lat = Xg[:, 1] / 110570 + pts[0][1]
    RS = np.array(Rs)
    print(f'{NAME}：{len(RS)} 曲線（半径の中央値 {np.median(RS):.0f} m、300 m 未満 {np.sum(RS < 300)}）、長さ {sg[-1] / 1000:.2f} km、ずれ 中央値 {np.median(dv):.1f}・95% {np.percentile(dv, 95):.1f}・最大 {dv.max():.1f} m')
    jinfo = {}
    for w, jj in (('start', js), ('end', je)):
        if jj is not None:
            jinfo[w] = {'trunk': TRUNKS[w], 's': best[w], 'lonlat': [jj[0][0] / K + pts[0][0], jj[0][1] / 110570 + pts[0][1]], 'angle_deg': math.degrees(THETA),
                        'tau': info[w][3], 'station': info[w][6][0] if len(info[w]) > 6 and info[w][6] else None, 'station_s': info[w][6][1] if len(info[w]) > 6 and info[w][6] else None}   # τ：分かれる向き（+1＝幹線のキロ程の増える向きに進む）。2026-11-08
    out_ = {'A': np.c_[lon, lat].tolist(), 's': sg.tolist(), 'k': list(map(float, kg)), 'stopidx': stopidx, 'dev': dv.tolist(), 'elements_flat': els, 'junctions': jinfo}
    if 'end' in jinfo: out_['junction'] = jinfo['end']   # 片端の版（ipfit_branch_v1.py）と同じ名前でも読めるように
    json.dump(out_, open(f'fit_{NAME}.json', 'w'))
