# 施工基面の高さと構造物の種類を、構造物の費用を見て決める（2026-11-03、ユーザーの了承）。
#  1. 構造物の種類を、いまの施工基面で決める（structdp.py の動的計画法）
#  2. その種類のもとで、施工基面の高さを線形計画法で決める：
#     土工の節点は、切土・盛土の費用（深さの 2 乗に近い増え方）を接線の折れ線で近似して最小にする。
#     トンネルの節点は「地盤−施工基面 ≥ 断面の高さ＋最小の土かぶり」、橋梁の節点は「施工基面−地盤 ≥ 橋梁の最低の高さ」を守る
#     （守れないときは、大きな罰則の付いたゆとりで受ける）。勾配の変化の少なさ（MU）と、15‰ を超える上りの罰則（NU）はいままでどおり
#  3. 1 と 2 を 3 回くり返す
# 仮定：駅の構内（前後 110 m）は、トンネルを認め、高架（橋梁）は費用を 2 倍にする。橋台は橋梁の 75 m 分（高架から下ろしてまた上げる
#       短い地上区間を避けるため。根拠のない仮の値）
# 使い方：python3 design3.py ground_f名前.json costs_名前.json 出力.json
import json, math, sys
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix, csr_matrix
from design import GMAX, STN_HALF, radius
_argv = sys.argv; sys.argv = sys.argv[:1]          # design2 は読み込むときに引数を読むので、空にして読み込む
from design2 import formation_lp, NODE, MU, GHARD, NU
sys.argv = _argv
import design2
MU, NU = 30.0, 300.0; design2.MU, design2.NU = MU, NU   # pipe.sh（design2.py … 30 20）と同じ重み
import structdp

YARD_BRIDGE = 2.0; ABUT_M = 75.0; W_SLACK = 1e4

def earth_tangents(P, hmax=60.0, n=12):
    """土工の 1 m あたりの費用 E(h)（h＞0 切土、h＜0 盛土）を、接線の折れ線で近似する。費用は「掘削 1 m³＝1」を、
    浅いときの傾き（≒底の幅）で割り、いままでの |z−g| と同じ「m」の尺度にそろえる"""
    sc = P["b_cut"]
    def E(h): return float(structdp.costs_per_m(np.array([h]), P)[0][0]) / sc
    out = []
    for side in (1, -1):
        for h in np.linspace(0, hmax, n):
            a = (E(side * (h + 0.01)) - E(side * h)) / 0.01; out.append((side, a, E(side * h) - a * h))
    return out

# 勾配（2026-11-03、ユーザーの指定）：原則 15‰。15‰ を超える分と 20‰ を超える分に段階的に罰則を付け、上限は 25‰（非電化。33.3‰ は
# 電化区間だけの最後の手段なので使わない）。客車列車が走る区間（KYAKU、キロ程 m の組。あとで教わる）は 15‰ が上限
G1, G2, GCAP = 0.015, 0.020, 0.025
NU1, NU2 = 100.0, 300.0   # 15〜20‰、20〜25‰ の上りの罰則（上った高さ 1 m あたり）
# 客車列車（観光急行）が特急と同じ線路を走る区間：ダイヤ（a.oud2）の種別「急行」は蘂取〜丹根萌。特急の経路と共通なのは南留別〜択捉六甲
# （2026-11-03、ユーザーの指定：急行はこの種別だけ）。駅の名前で持ち、キロ程は線形ごとに引く
KYAKU_ST = [("蘂取", "標後"), ("南留別", "択捉六甲")]   # 蘂取〜標後は急行の回送（ダイヤの回送、上下 4 本ずつ。ユーザーの指定：除かない）
KYAKU = []
def lp(sn, gn, lim, state, P, tang):
    n = len(sn); nz, nw, nu, ne, nsl = n, n, n - 2, 2 * (n - 1), n; N = nz + nw + nu + ne + nsl
    c = np.concatenate([np.zeros(nz), np.where(state == 0, 1.0, 0.0), np.full(nu, MU), np.full(n - 1, NU1), np.full(n - 1, NU2), np.full(nsl, W_SLACK)])
    rows = []; b = []
    A = lil_matrix((n * len(tang) + 2 * nu + 2 * (n - 1) + n, N)); r = 0
    for i in range(n):
        if state[i] != 0: continue
        for side, a, k0 in tang:   # w ≥ a·side·(g−z) + k0   →  −a·side·z − w ≤ −k0 − a·side·g
            A[r, i] = -a * side; A[r, nz + i] = -1; b.append(-k0 - a * side * gn[i]); r += 1
    for k in range(1, n - 1):
        j = nz + nw + k - 1
        A[r, k - 1] = 1; A[r, k] = -2; A[r, k + 1] = 1; A[r, j] = -1; b.append(0); r += 1
        A[r, k - 1] = -1; A[r, k] = 2; A[r, k + 1] = -1; A[r, j] = -1; b.append(0); r += 1
    for k in range(n - 1):   # |z[k+1] − z[k]| ≤ lim·ds + e1 + e2（e1：15〜20‰ の分、e2：20〜25‰ の分）
        d = lim[k] * (sn[k + 1] - sn[k]); j1 = nz + nw + nu + k; j2 = j1 + (n - 1)
        A[r, k + 1] = 1; A[r, k] = -1; A[r, j1] = -1; A[r, j2] = -1; b.append(d); r += 1
        A[r, k + 1] = -1; A[r, k] = 1; A[r, j1] = -1; A[r, j2] = -1; b.append(d); r += 1
    for i in range(n):
        sl = nz + nw + nu + ne + i
        if state[i] == 1:    # トンネル：g − z ≥ 断面の高さ＋最小の土かぶり   →  z − sl ≤ g − need
            A[r, i] = 1; A[r, sl] = -1; b.append(gn[i] - P["t_height"] - P["t_cover_min"]); r += 1
        elif state[i] == 2:  # 橋梁：z − g ≥ 最低の高さ   →  −z − sl ≤ −g − hmin
            A[r, i] = -1; A[r, sl] = -1; b.append(-gn[i] - P["b_min_height"]); r += 1
    A = csr_matrix(A[:r]); b = np.array(b)
    def kyaku(k): return any(a_ <= sn[k + 1] and sn[k] <= b_ for a_, b_ in KYAKU)
    ub_e = [(0, 0 if (lim[k] == 0 or kyaku(k)) else (G2 - G1) * (sn[k + 1] - sn[k])) for k in range(n - 1)] + \
           [(0, 0 if (lim[k] == 0 or kyaku(k)) else (GCAP - G2) * (sn[k + 1] - sn[k])) for k in range(n - 1)]
    res = linprog(c, A_ub=A, b_ub=b, bounds=[(None, None)] * nz + [(0, None)] * (nw + nu) + ub_e + [(0, None)] * nsl, method="highs")
    if not res.success: raise SystemExit(res.message)
    return res.x[:nz], res.x[N - nsl:]

if __name__ == "__main__":
    r = json.load(open(sys.argv[1])); P = json.load(open(sys.argv[2])); s = np.array(r["s"])
    P = dict(P, c_abutment=ABUT_M * P["c_bridge"])
    g, z, sn, zn = formation_lp(s, r["ground"], r["stations"])          # 出発点：いまの決め方
    lim = np.full(len(sn) - 1, GMAX)
    for _, c in r["stations"]:
        for k in range(len(sn) - 1):
            if sn[k + 1] > c - STN_HALF and sn[k] < c + STN_HALF: lim[k] = 0.0
    gn = np.array([np.median(g[(s >= x - NODE / 2) & (s <= x + NODE / 2)]) for x in sn])
    st_pos = dict(r["stations"]); KYAKU[:] = [(st_pos[a_], st_pos[b_]) for a_, b_ in KYAKU_ST]
    stops = [c for n_, c in r["stations"] if n_ in r["stops"]]
    yard = np.zeros(len(s), bool)
    for c in stops: yard |= np.abs(s - c) <= STN_HALF
    tang = earth_tangents(P)
    def classify(z):
        h = g - z; ds = np.gradient(s); C = structdp.costs_per_m(h, P) * ds
        C[2, yard] *= YARD_BRIDGE   # 高架の駅は費用 2 倍。トンネルの中の駅・信号場は認める（2026-11-03、ユーザーの指定）
        st, tot = structdp.solve_C(s, h, P, C)
        return st, tot
    for it in range(3):
        st, tot = classify(z)
        # 節点ごとの状態（その節点の前後 50 m で最も多い状態）
        state = np.array([np.bincount(st[(s >= x - NODE / 2) & (s <= x + NODE / 2)], minlength=3).argmax() for x in sn])
        zn, slack = lp(sn, gn, lim, state, P, tang); z = np.interp(s, sn, zn)
        h = g - z; print(f"  くり返し {it + 1}：費用 {tot:.3g}  トンネル {np.sum(st == 1) * 20 / 1000:.1f} km・橋梁 {np.sum(st == 2) * 20 / 1000:.1f} km  条件のゆとり 最大 {slack.max():.1f} m", flush=True)
    st, tot = classify(z)
    r.update({"ground": g.tolist(), "z": z.tolist(), "struct": "".join("-TB"[q] for q in st), "sn": sn.tolist(), "zn": zn.tolist(),
              "R": [None if math.isinf(x) else x for x in radius(r["xy"])]})
    json.dump(r, open(sys.argv[3], "w"), ensure_ascii=False)
    h = g - z; e = st == 0
    print(f"最終：費用 {tot:.3g}  トンネル {np.sum(st == 1) * 20 / 1000:.1f} km（{int(np.sum(np.diff((st == 1).astype(int)) == 1))} か所）・橋梁 {np.sum(st == 2) * 20 / 1000:.1f} km  "
          f"最も深い切土 {h[e].max():.1f} m・最も高い盛土 {(-h[e]).max():.1f} m  深さ 10 m 超の切土 {np.sum(e & (h > 10)) * 20 / 1000:.1f} km・高さ 8 m 超の盛土 {np.sum(e & (h < -8)) * 20 / 1000:.1f} km")
