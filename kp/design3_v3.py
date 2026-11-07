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
G1, G2, GCAP = 0.015, 0.020, float(__import__('os').environ.get('GCAP', '0.025'))   # 上限は線の等級で変える（乙線 25‰、丙線 35‰。2026-11-04）
NU1, NU2 = 100.0, 300.0   # 15〜20‰、20〜25‰ の上りの罰則（上った高さ 1 m あたり）
# 客車列車（観光急行）が特急と同じ線路を走る区間：ダイヤ（a.oud2）の種別「急行」は蘂取〜丹根萌。特急の経路と共通なのは南留別〜択捉六甲
# （2026-11-03、ユーザーの指定：急行はこの種別だけ）。駅の名前で持ち、キロ程は線形ごとに引く
KYAKU_ST = [("蘂取", "標後"), ("南留別", "択捉六甲")]   # 蘂取〜標後は急行の回送（ダイヤの回送、上下 4 本ずつ。ユーザーの指定：除かない）
KYAKU = []
# 駅の高さの指定（2026-11-03、ユーザーの指定）：停車場中心の施工基面を、その地点の地盤からの高さの範囲 [下, 上]（m）に置く。
# 地平駅は [-2, 2]（地盤の高さを 0 として上下 2 m ずつ、幅 4 m）。駅の一部がトンネル・橋梁に入るのは構わない。
STN_H = []
# 橋梁の高さの費用（費用の表の c_bridge_h は 0：資料がない）。高さに費用がないと、高架を低く抑える理由がなく、勾配の変化の少なさだけで
# 高い所を通る（標後〜瀬石温泉で高さ 20〜29 m）。仮に、高さ 1 m あたり浅い土工 1 m 分の費用とする（根拠の記録なし。2026-11-03）
W_BH = float(__import__('os').environ.get('W_BH', '1.0'))   # (節点の番号, 下限の標高, 上限の標高)
def lp(sn, gn, lim, state, P, tang):
    n = len(sn); nz, nw, nu, ne, nsl = n, n, n - 2, 2 * (n - 1), n; N = nz + nw + nu + ne + nsl
    c = np.concatenate([np.zeros(nz), np.where(state == 0, 1.0, np.where(state == 2, W_BH, 0.0)), np.full(nu, MU), np.full(n - 1, NU1), np.full(n - 1, NU2), np.full(nsl, W_SLACK)])
    rows = []; b = []
    A = lil_matrix((n * len(tang) + n + 2 * nu + 2 * (n - 1) + n + 2 * len(STN_H), N)); r = 0
    for i in range(n):
        if state[i] == 2:   # 橋梁の高さの費用：w ≥ z − g（高さ 1 m あたり W_BH）
            A[r, i] = 1; A[r, nz + i] = -1; b.append(gn[i]); r += 1
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
    for k, lo_, hi_ in STN_H:   # 駅の高さ：lo ≤ z ≤ hi（守れないときはゆとりで受ける）
        sl = nz + nw + nu + ne + k
        A[r, k] = 1; A[r, sl] = -1; b.append(hi_); r += 1
        A[r, k] = -1; A[r, sl] = -1; b.append(-lo_); r += 1
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
    st_pos = dict(r["stations"]); KYAKU[:] = [(st_pos[a_], st_pos[b_]) for a_, b_ in KYAKU_ST if a_ in st_pos and b_ in st_pos]   # この線にある区間だけ（支線の計算、2026-11-04）
    stops = [c for n_, c in r["stations"] if n_ in r["stops"]]
    yard = np.zeros(len(s), bool)
    for c in stops: yard |= np.abs(s - c) <= STN_HALF
    tang = earth_tangents(P)
    # 高さの指定（4 番目の引数の JSON。なければ指定なし）
    spec = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
    for name, (lo_, hi_) in spec.get('stations', {}).items():
        c = st_pos[name]; k = int(np.argmin(np.abs(sn - c))); g0 = float(np.interp(c, s, g))
        STN_H.append((k, g0 + lo_, g0 + hi_))
    # 線の端の施工基面の標高（m）を固定する（支線が幹線につながる分岐器の位置。2026-11-04）：{"end_z": 標高}
    if 'end_z' in spec: STN_H.append((len(sn) - 1, spec['end_z'], spec['end_z']))
    if 'start_z' in spec: STN_H.append((0, spec['start_z'], spec['start_z']))   # 始点も幹線につながる線（両端の分岐、2026-11-04）
    # 高架にする区間：駅と駅の間の指定（両端の駅の構内 110 m と、地平から橋梁の最低の高さへ上がる長さ (2 + 3) m ÷ 25‰ = 200 m を除く）と、湿地
    force_B = np.zeros(len(s), bool)
    ramp = STN_HALF + (2 + P['b_min_height']) / GCAP
    for a_, b_ in spec.get('bridge', []):
        force_B |= (s >= st_pos[a_] + ramp) & (s <= st_pos[b_] - ramp)
    if spec.get('wetland'):
        force_B |= np.array(json.load(open(spec['wetland']))['wet'], bool)
    def classify(z):
        h = g - z; ds = np.gradient(s); C = structdp.costs_per_m(h, P) * ds
        C[2, yard] *= YARD_BRIDGE
        # 高架の指定の区間・湿地は橋梁だけ。いまの施工基面が低くても橋梁を選べるようにし（費用は最低の高さで数える）、
        # 高さは次の線形計画法で「施工基面−地盤 ≥ 橋梁の最低の高さ」に持ち上げる
        fil = np.maximum(-h, P['b_min_height'])
        C[2, force_B] = ((P['c_bridge'] + P['c_bridge_h'] * fil) * ds)[force_B]
        C[0:2, force_B] = np.inf   # 高架の駅は費用 2 倍。トンネルの中の駅・信号場は認める（2026-11-03、ユーザーの指定）
        st, tot = structdp.solve_C(s, h, P, C)
        return st, tot
    for it in range(3):
        st, tot = classify(z)
        # 節点ごとの状態（その節点の前後 50 m で最も多い状態）
        state = np.array([np.bincount(st[(s >= x - NODE / 2) & (s <= x + NODE / 2)], minlength=3).argmax() for x in sn])
        zn, slack = lp(sn, gn, lim, state, P, tang); z = np.interp(s, sn, zn)
        h = g - z; print(f"  くり返し {it + 1}：費用 {tot:.3g}  トンネル {np.sum(st == 1) * 20 / 1000:.1f} km・橋梁 {np.sum(st == 2) * 20 / 1000:.1f} km  条件のゆとり 最大 {slack.max():.1f} m", flush=True)
    st, tot = classify(z)
    for k, lo_, hi_ in STN_H:
        name = ([n_ for n_, c in r['stations'] if int(np.argmin(np.abs(sn - c))) == k] or ['線の端'])[0]
        print(f"  駅の高さ {name}: 施工基面 {zn[k]:.1f} m（指定 {lo_:.1f}〜{hi_:.1f} m）", flush=True)
    r.update({"ground": g.tolist(), "z": z.tolist(), "struct": "".join("-TB"[q] for q in st), "sn": sn.tolist(), "zn": zn.tolist(),
              "R": [None if math.isinf(x) else x for x in radius(r["xy"])]})
    json.dump(r, open(sys.argv[3], "w"), ensure_ascii=False)
    h = g - z; e = st == 0
    print(f"最終：費用 {tot:.3g}  トンネル {np.sum(st == 1) * 20 / 1000:.1f} km（{int(np.sum(np.diff((st == 1).astype(int)) == 1))} か所）・橋梁 {np.sum(st == 2) * 20 / 1000:.1f} km  "
          f"最も深い切土 {h[e].max():.1f} m・最も高い盛土 {(-h[e]).max():.1f} m  深さ 10 m 超の切土 {np.sum(e & (h > 10)) * 20 / 1000:.1f} km・高さ 8 m 超の盛土 {np.sum(e & (h < -8)) * 20 / 1000:.1f} km")
