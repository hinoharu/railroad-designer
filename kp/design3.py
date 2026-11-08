# 施工基面の高さと構造物の種類を、構造物の費用を見て決める（2026-11-03、ユーザーの了承）。
#  1. 構造物の種類を、いまの施工基面で決める（structdp.py の動的計画法）
#  2. その種類のもとで、施工基面の高さを線形計画法で決める：
#     土工の節点は、切土・盛土の費用（深さの 2 乗に近い増え方）を接線の折れ線で近似して最小にする。
#     トンネルの節点は「地盤−施工基面 ≥ 断面の高さ＋最小の土かぶり」、橋梁の節点は「施工基面−地盤 ≥ 橋梁の最低の高さ」を守る
#     （守れないときは、大きな罰則の付いたゆとりで受ける）。勾配の変化の少なさ（MU）と、15‰ を超える上りの罰則（NU）はいままでどおり
#  3. 1 と 2 を 3 回くり返す
# 仮定：駅の構内（STN_HALF）は、トンネルを認め、高架（橋梁）は費用を 2 倍にする。構内の勾配は YARD_GRADE（停車場ごとの上限。2026-11-08）。橋台は橋梁の 75 m 分（高架から下ろしてまた上げる
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
# 地平駅の高さ（2026-11-04、ユーザーの指定）：駅の高さ＝施工基面−地盤。厳密な地平 −2〜+2 m は罰則なし。準地平 −10〜−2 m（掘割：上を道路・構造物で
# ふさげる深さまで）と +2〜+12 m（盛土・高架）は罰則付きで認め、高架の側を重くする。その外は W_SLACK（守れないときのゆとり）。
# 罰則（高さ 1 m あたり）は勾配の罰則にそろえた仮の値（根拠の記録なし）：掘割 NU1＝100、高架 NU2＝300
FLAT_IN = (-2.0, 2.0); FLAT_SEMI = (-10.0, 12.0)
FLAT_MODE = __import__("os").environ.get("FLAT_MODE", "lex")   # lex：駅ありき（2 段で解く）、penalty：準地平に罰則（下の重み。試算で使った）
W_FLAT_CUT, W_FLAT_UP = float(__import__("os").environ.get("W_FLAT_CUT", "100")), float(__import__("os").environ.get("W_FLAT_UP", "300"))   # 内部の重み。費用の単位（切土 1 m³＝1）では ×500（節点 100 m × 底の幅 5 m）

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
KYAKU_ST = [("蘂取", "標後"), ("南留別", "択捉六甲"),
]   # 11-03 の決まり（単機の客車列車）。2026-11-05 に急行の全区間へ広げたのは誤タップによる指定で、取り消した
# 急行は DD51形の重連（7 両、約 379 t）を想定し、25‰ まで（2026-11-05、ユーザーの指定：重連で現実的な速度が出る勾配を限界とする）。
# 均衡速度の概算は 25‰ で約 72 km/h、28‰ で約 66 km/h で、11-03 の決まり（単機で 15‰）の約 70 km/h を保てるのは 25‰ まで。
# 電化の線（33・35‰）でも、急行の区間は 25‰ が上限：茂世路線（背祖曽〜沼田）・蘂取線（沼田〜南留別）。非電化の線は線の上限がもともと 25‰
KYAKU25_ST = [("背祖曽", "沼田"), ("沼田", "南留別")]
KYAKU25 = []
# 案の比較（2026-11-05）のための上書き：KYAKU15_ADD（15‰ にする駅の組を JSON で足す）、KYAKU25_OFF=1（25‰ の指定を外す）。ふだんは使わない
import json as _json, os as _os
KYAKU_ST = KYAKU_ST + [tuple(p_) for p_ in _json.loads(_os.environ.get("KYAKU15_ADD", "[]"))]
if _os.environ.get("KYAKU25_OFF") == "1": KYAKU25_ST = []
# 1 本の線の中で電化区間と非電化区間が混じる線（択捉空港線・単冠山麓線、2026-11-05）：非電化区間を KYAKU25_ADD（駅の組の JSON）で 25‰ まで
KYAKU25_ST = KYAKU25_ST + [tuple(p_) for p_ in _json.loads(_os.environ.get("KYAKU25_ADD", "[]"))]
# 背蘂線（蘂取〜背祖曽）は、15‰ では単機で無理（天幕→上去家だけで +16.6 km）なので、DD51形の重連の想定で線の上限 25‰（ユーザーの了承「一両ではむりむりなら重連」）   # 蘂取〜標後は急行の回送（ダイヤの回送、上下 4 本ずつ。ユーザーの指定：除かない）
KYAKU = []
# 駅の高さの指定（2026-11-03、ユーザーの指定）：停車場中心の施工基面を、その地点の地盤からの高さの範囲 [下, 上]（m）に置く。
# 地平駅は [-2, 2]（地盤の高さを 0 として上下 2 m ずつ、幅 4 m）。駅の一部がトンネル・橋梁に入るのは構わない。
STN_H = []
END_G = []   # (節点の番号 0 か n−1, 勾配) 端の勾配の指定（高さの指定の JSON の start_g・end_g。2026-11-08）
# 橋梁の高さの費用（費用の表の c_bridge_h は 0：資料がない）。高さに費用がないと、高架を低く抑える理由がなく、勾配の変化の少なさだけで
# 高い所を通る（標後〜瀬石温泉で高さ 20〜29 m）。仮に、高さ 1 m あたり浅い土工 1 m 分の費用とする（根拠の記録なし。2026-11-03）
W_BH = float(__import__('os').environ.get('W_BH', '1.0'))   # (節点の番号, 下限の標高, 上限の標高)
# 橋梁の高さの境（2026-11-07、ユーザーの判断。国後島から）：高さ（施工基面−地盤）が BRIDGE_H1（60 m）を超える分に、1 m あたり W_BH2 の
# 非常に大きな罰則。深い谷の河川（峡谷）を渡る所＝橋梁の区間のうち H1 超の部分が連続 BRIDGE_SPAN（300 m）以下で、両側に H1 以下の
# 地盤がある所は、境を BRIDGE_H2（100 m、高千穂橋梁の程度）にする。大河川のように両脇に高い地盤がない所はだめ。BRIDGE_H1 を 0 にすると切
BRIDGE_H1 = float(_os.environ.get('BRIDGE_H1', '0')); BRIDGE_H2 = float(_os.environ.get('BRIDGE_H2', '100')); BRIDGE_SPAN = float(_os.environ.get('BRIDGE_SPAN', '300'))
W_BH2 = float(_os.environ.get('W_BH2', '100'))   # 境を超える高さ 1 m あたりの重み（浅い土工 1 m 分の 100 倍。仮の値）
# 駅の深さ（2026-11-07、ユーザーの判断）：停車場中心の施工基面 z ≥（中心から EXIT_R 以内の地盤の最低の標高）− DEPTH_MAX。
# 「深さ 40 m まで。100〜200 m の水平移動で地表に出られるなら不問」を 1 本の条件にした。DEPTH_MAX を 0 にすると切
DEPTH_MAX = float(_os.environ.get('DEPTH_MAX', '0')); EXIT_R = float(_os.environ.get('EXIT_R', '200'))
# 駅の構内（停車場中心の両側で水平にする長さ、m。design.py の STN_HALF 110 が既定）。2026-11-08、分岐器の規則（docs/junction.md 2.④）：
# build.py が入力表 profile.STN_HALF（"auto" なら TRAIN ÷ 2 ＋ 72 m）から渡す。構内の端の分岐器（JMIN）とその外方 20 m まで水平にするため
STN_HALF = float(_os.environ.get('STN_HALF', STN_HALF))
BRIDGE_THR = None   # 節点ごとの境（lp の前に決める）
def lp(sn, gn, lim, state, Pn, tangn):
    """Pn・tangn：節点ごとの費用の表と土工の接線（単線と複線を区間ごとに使い分ける。2026-11-04）"""
    n = len(sn); nz, nw, nu, ne, nsl = n, n, n - 2, 2 * (n - 1), n
    FL = [q for q in STN_H if q[3]]; nf = 2 * len(FL)
    HB = [i for i in range(n) if state[i] == 2 and BRIDGE_H1 > 0]; nb2 = len(HB)   # 境を超える高さの変数（橋梁の節点ごと）
    N = nz + nw + nu + ne + nf + nsl + nb2   # 地平駅ごとに準地平の分（上・下）の変数
    c = np.concatenate([np.zeros(nz), np.where(state == 0, 1.0, np.where(state == 2, W_BH, 0.0)), np.full(nu, MU), np.full(n - 1, NU1), np.full(n - 1, NU2),
                        np.tile([W_FLAT_UP, W_FLAT_CUT], len(FL)), np.full(nsl, W_SLACK), np.full(nb2, W_BH2)])
    rows = []; b = []
    A = lil_matrix((sum(len(q) for q in tangn) + n + 2 * nu + 2 * (n - 1) + n + 2 * len(STN_H) + nb2 + 2 * len(END_G) + 2 * (n - 2), N)); r = 0
    for i in range(n):
        if state[i] == 2:   # 橋梁の高さの費用：w ≥ z − g（高さ 1 m あたり W_BH）
            A[r, i] = 1; A[r, nz + i] = -1; b.append(gn[i]); r += 1
    for j, i in enumerate(HB):   # 境を超える分：w2 ≥ z − g − thr（1 m あたり W_BH2）
        A[r, i] = 1; A[r, nz + nw + nu + ne + nf + nsl + j] = -1; b.append(gn[i] + (BRIDGE_THR[i] if BRIDGE_THR is not None else BRIDGE_H1)); r += 1
    for i in range(n):
        if state[i] != 0: continue
        for side, a, k0 in tangn[i]:   # w ≥ a·side·(g−z) + k0   →  −a·side·z − w ≤ −k0 − a·side·g
            A[r, i] = -a * side; A[r, nz + i] = -1; b.append(-k0 - a * side * gn[i]); r += 1
    for k in range(1, n - 1):
        j = nz + nw + k - 1
        A[r, k - 1] = 1; A[r, k] = -2; A[r, k + 1] = 1; A[r, j] = -1; b.append(0); r += 1
        A[r, k - 1] = -1; A[r, k] = 2; A[r, k + 1] = -1; A[r, j] = -1; b.append(0); r += 1
    for k in range(n - 2):   # 構内（lim ＜ GMAX の続く節点）は 1 つの勾配にする（2026-11-08）：節点ごとに ±上限の間で勾配を変えると、構内の中に大きな勾配変化点ができるため
        if lim[k] < GMAX and lim[k + 1] < GMAX:
            A[r, k] = 1; A[r, k + 1] = -2; A[r, k + 2] = 1; b.append(0); r += 1
            A[r, k] = -1; A[r, k + 1] = 2; A[r, k + 2] = -1; b.append(0); r += 1
    for k in range(n - 1):   # |z[k+1] − z[k]| ≤ lim·ds + e1 + e2（e1：15〜20‰ の分、e2：20〜25‰ の分）
        d = lim[k] * (sn[k + 1] - sn[k]); j1 = nz + nw + nu + k; j2 = j1 + (n - 1)
        A[r, k + 1] = 1; A[r, k] = -1; A[r, j1] = -1; A[r, j2] = -1; b.append(d); r += 1
        A[r, k + 1] = -1; A[r, k] = 1; A[r, j1] = -1; A[r, j2] = -1; b.append(d); r += 1
    for i in range(n):
        sl = nz + nw + nu + ne + nf + i
        if state[i] == 1:    # トンネル：g − z ≥ 断面の高さ＋最小の土かぶり   →  z − sl ≤ g − need
            A[r, i] = 1; A[r, sl] = -1; b.append(gn[i] - Pn[i]["t_height"] - Pn[i]["t_cover_min"]); r += 1
        elif state[i] == 2:  # 橋梁：z − g ≥ 最低の高さ   →  −z − sl ≤ −g − hmin
            A[r, i] = -1; A[r, sl] = -1; b.append(-gn[i] - Pn[i]["b_min_height"]); r += 1
    fi = 0
    for k, gk in END_G:   # 端の勾配（2026-11-08）：z[k+1] − z[k] ＝ gk·Δs（端のゆとりで受ける）。支線の端を幹線の分岐点の勾配に合わせる
        k0, k1 = (0, 1) if k == 0 else (n - 2, n - 1); sl = nz + nw + nu + ne + nf + k; d_ = gk * (sn[k1] - sn[k0])
        A[r, k1] = 1; A[r, k0] = -1; A[r, sl] = -1; b.append(d_); r += 1
        A[r, k1] = -1; A[r, k0] = 1; A[r, sl] = -1; b.append(-d_); r += 1
    for k, lo_, hi_, flat in STN_H:   # 駅の高さ：lo ≤ z ≤ hi（守れないときはゆとりで受ける）。地平駅は準地平の分 a_up・a_dn を足して受ける
        sl = nz + nw + nu + ne + nf + k
        A[r, k] = 1; A[r, sl] = -1
        if flat: A[r, nz + nw + nu + ne + fi] = -1
        b.append(hi_); r += 1
        A[r, k] = -1; A[r, sl] = -1
        if flat: A[r, nz + nw + nu + ne + fi + 1] = -1; fi += 2
        b.append(-lo_); r += 1
    A = csr_matrix(A[:r]); b = np.array(b)
    def kyaku(k): return any(a_ <= sn[k + 1] and sn[k] <= b_ for a_, b_ in KYAKU)
    def kyaku25(k): return any(a_ <= sn[k + 1] and sn[k] <= b_ for a_, b_ in KYAKU25)
    ub_e = [(0, 0 if (lim[k] < GMAX or kyaku(k)) else (G2 - G1) * (sn[k + 1] - sn[k])) for k in range(n - 1)] + \
           [(0, 0 if (lim[k] < GMAX or kyaku(k)) else ((min(GCAP, 0.025) if kyaku25(k) else GCAP) - G2) * (sn[k + 1] - sn[k])) for k in range(n - 1)]   # 構内（lim ＜ GMAX）では 15‰ 超のゆとりを使わない
    if FLAT_MODE == 'lex':
        # 駅ありき（2026-11-04、ユーザーの判断）：第 1 段で地平（FLAT_IN）からの離れの合計を最小にし（工事費は見ない。守るべき条件のゆとりも同じ重み）、
        # 第 2 段でその離れを超えない範囲で工事費を最小にする。罰則の数値を使わない
        bnd = [(None, None)] * nz + [(0, None)] * (nw + nu) + ub_e + [(0, None)] * nf + [(0, None)] * nsl + [(0, None)] * nb2
        # 優先の順：個別の高さの指定・分岐器の高さ・構造物の条件（ゆとり sl）＞ 地平駅の離れ ＞ 工事費。第 1 段で sl を W_SLACK 倍に重くして、
        # 地平駅のために指定の駅を動かさない（2026-11-04、振別が指定から +19 m 外れたため）
        c1 = np.zeros(N); c1[nz + nw + nu + ne:nz + nw + nu + ne + nf] = 1.0; c1[nz + nw + nu + ne + nf:nz + nw + nu + ne + nf + nsl] = W_SLACK
        r1 = linprog(c1, A_ub=A, b_ub=b, bounds=bnd, method="highs")
        if not r1.success: raise SystemExit(r1.message)
        D1 = float(r1.x[nz + nw + nu + ne:nz + nw + nu + ne + nf].sum()); S1 = float(r1.x[nz + nw + nu + ne + nf:nz + nw + nu + ne + nf + nsl].sum())
        row = np.zeros((2, N)); row[0, nz + nw + nu + ne:nz + nw + nu + ne + nf] = 1; row[1, nz + nw + nu + ne + nf:nz + nw + nu + ne + nf + nsl] = 1
        from scipy.sparse import vstack as _vs
        c2 = c.copy(); c2[nz + nw + nu + ne:nz + nw + nu + ne + nf] = 0
        res = linprog(c2, A_ub=_vs([A, csr_matrix(row)]).tocsr(), b_ub=np.concatenate([b, [D1 + 0.01 + 1e-4 * D1, S1 + 0.01 + 1e-4 * S1]]), bounds=bnd, method="highs")
    else:
        res = linprog(c, A_ub=A, b_ub=b, bounds=[(None, None)] * nz + [(0, None)] * (nw + nu) + ub_e + [(0, FLAT_SEMI[1] - FLAT_IN[1]), (0, FLAT_IN[0] - FLAT_SEMI[0])] * len(FL) + [(0, None)] * nsl + [(0, None)] * nb2, method="highs")
    if not res.success: raise SystemExit(res.message)
    return res.x[:nz], res.x[nz + nw + nu + ne + nf:nz + nw + nu + ne + nf + nsl]

def solve_C_mixed(s, h, C, Pof):
    """structdp.solve_C と同じ（構造物の切り替えの費用：坑口・橋台）。費用の表を位置ごとに Pof(i) で選ぶ（単線・複線、2026-11-04）"""
    n = len(s); INF = np.inf
    def trans(i):
        P_ = Pof(i); t = np.zeros((3, 3)); portal = P_["c_portal"] if h[i] >= P_["t_portal_min"] else INF
        t[0, 1] = t[1, 0] = portal; t[0, 2] = t[2, 0] = P_["c_abutment"]; t[1, 2] = t[2, 1] = portal + P_["c_abutment"]
        return t
    P0, P1 = Pof(0), Pof(n - 1)
    cost = C[:, 0].copy(); back = np.zeros((n, 3), int)
    cost[1] += P0["c_portal"] if h[0] >= P0["t_portal_min"] else INF; cost[2] += P0["c_abutment"]
    for i in range(1, n):
        t = trans(i); tot = cost[:, None] + t; back[i] = np.argmin(tot, axis=0); cost = tot[back[i], [0, 1, 2]] + C[:, i]
    end = cost + np.array([0, P1["c_portal"] if h[-1] >= P1["t_portal_min"] else INF, P1["c_abutment"]])
    st = np.zeros(n, int); st[-1] = int(np.argmin(end))
    for i in range(n - 1, 0, -1): st[i - 1] = back[i, st[i]]
    return st, float(end.min())

if __name__ == "__main__":
    r = json.load(open(sys.argv[1])); P = json.load(open(sys.argv[2])); s = np.array(r["s"])
    P = dict(P, c_abutment=ABUT_M * P["c_bridge"])
    # 単線・複線を区間ごとに使い分ける（2026-11-04、FreeTrain のセーブから読み取り、ユーザーが確かめた）：高さの指定の JSON の
    # "double"：[[駅, 駅], ...] の区間（停車場中心から停車場中心まで）は複線の表 costs_double.json、ほかは 2 番目の引数の表
    _spec0 = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
    PD = json.load(open('costs_double.json')); PD = dict(PD, c_abutment=ABUT_M * PD["c_bridge"])
    g, z, sn, zn = formation_lp(s, r["ground"], r["stations"])          # 出発点：いまの決め方
    lim = np.full(len(sn) - 1, GMAX)
    # 構内の勾配の上限（2026-11-08、ユーザーの判断。docs/vertical_curve.md 4・junction.md 2）：YARD_G（JSON {"棒線": 上限, "分岐器あり": 上限}）。
    # 棒線駅はオプションの PLAIN_STATIONS（JSON の駅名の一覧）。指定のない停車場は行き違い駅（分岐器あり）。YARD_G がなければ水平（それまでの決め方）。
    # 縦曲線が構内に食い込まないよう、上限の区間を接線長の最悪の値 VC_R × (上限 ＋ GCAP) ÷ 2 だけ両側に延ばす
    YARD_G = json.loads(_os.environ.get('YARD_G', '{}')); VC_R = float(_os.environ.get('VC_R', '0')); PLAIN = set(json.loads(_os.environ.get('PLAIN_STATIONS', '[]')))
    for name, c in r["stations"]:
        yg = YARD_G.get('棒線' if name in PLAIN else '分岐器あり', 0.0) if YARD_G else 0.0; ext = VC_R * (yg + GCAP) / 2
        for k in range(len(sn) - 1):
            if sn[k + 1] > c - STN_HALF - ext and sn[k] < c + STN_HALF + ext: lim[k] = min(lim[k], yg)
    gn = np.array([np.median(g[(s >= x - NODE / 2) & (s <= x + NODE / 2)]) for x in sn])
    st_pos = dict(r["stations"]); KYAKU[:] = [(st_pos[a_], st_pos[b_]) for a_, b_ in KYAKU_ST if a_ in st_pos and b_ in st_pos]; KYAKU25[:] = [(st_pos[a_], st_pos[b_]) for a_, b_ in KYAKU25_ST if a_ in st_pos and b_ in st_pos]   # この線にある区間だけ（支線の計算、2026-11-04）
    stops = [c for n_, c in r["stations"] if n_ in r["stops"]]
    yard = np.zeros(len(s), bool)
    for c in stops: yard |= np.abs(s - c) <= STN_HALF
    st_c = dict(r["stations"])
    dbl = np.zeros(len(s), bool)
    for a_, b_ in _spec0.get('double', []):
        lo_, hi_ = sorted((st_c[a_], st_c[b_])); dbl |= (s >= lo_) & (s <= hi_)
    dbn = np.array([bool(dbl[int(np.argmin(np.abs(s - x)))]) for x in sn])
    tangS, tangD = earth_tangents(P), earth_tangents(PD)
    Pn = [PD if q else P for q in dbn]; tangn = [tangD if q else tangS for q in dbn]
    if dbl.any(): print(f"  複線の区間：{dbl.sum() * float(np.median(np.diff(s))) / 1000:.1f} km（{len(_spec0['double'])} 区間）", flush=True)
    # 高さの指定（4 番目の引数の JSON。なければ指定なし）
    spec = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
    for name, v in spec.get('stations', {}).items():   # [下, 上]（m）か "地平"（上の FLAT_IN・FLAT_SEMI）
        c = st_pos[name]; k = int(np.argmin(np.abs(sn - c))); g0 = float(np.interp(c, s, g))
        lo_, hi_ = FLAT_IN if v == '地平' else v
        STN_H.append((k, g0 + lo_, g0 + hi_, v == '地平'))
    # 線の端の施工基面の標高（m）を固定する（支線が幹線につながる分岐器の位置。2026-11-04）：{"end_z": 標高}
    if 'end_z' in spec: STN_H.append((len(sn) - 1, spec['end_z'], spec['end_z'], False))
    if DEPTH_MAX > 0:   # 駅の深さの上限（2026-11-07）：z ≥（中心から EXIT_R 以内の地盤の最低）− DEPTH_MAX。上限は置かない（大きな値）
        for name, c in r["stations"]:
            k = int(np.argmin(np.abs(sn - c))); gmin = float(np.nanmin(g[np.abs(s - c) <= EXIT_R]))
            STN_H.append((k, gmin - DEPTH_MAX, 1e4, False))
    if 'start_z' in spec: STN_H.append((0, spec['start_z'], spec['start_z'], False))   # 始点も幹線につながる線（両端の分岐、2026-11-04）
    # 端の勾配（2026-11-08、ユーザーの指摘：古釜布支線が本線の 15‰ の途中から 0‰ で分かれていた）：幹線の分岐点の勾配に合わせる
    if 'end_g' in spec: END_G.append((len(sn) - 1, float(spec['end_g'])))
    if 'start_g' in spec: END_G.append((0, float(spec['start_g'])))
    # 高架にする区間：駅と駅の間の指定（両端の駅の構内 110 m と、地平から橋梁の最低の高さへ上がる長さ (2 + 3) m ÷ 25‰ = 200 m を除く）と、湿地
    force_B = np.zeros(len(s), bool)
    ramp = STN_HALF + (2 + P['b_min_height']) / GCAP
    for a_, b_ in spec.get('bridge', []):
        force_B |= (s >= st_pos[a_] + ramp) & (s <= st_pos[b_] - ramp)
    if spec.get('wetland'):
        force_B |= np.array(json.load(open(spec['wetland']))['wet'], bool)
    def classify(z):
        h = g - z; ds = np.gradient(s)
        C = np.where(dbl[None, :], structdp.costs_per_m(h, PD), structdp.costs_per_m(h, P)) * ds
        C[2, yard] *= YARD_BRIDGE
        # 高架の指定の区間・湿地は橋梁だけ。いまの施工基面が低くても橋梁を選べるようにし（費用は最低の高さで数える）、
        # 高さは次の線形計画法で「施工基面−地盤 ≥ 橋梁の最低の高さ」に持ち上げる
        fil = np.maximum(-h, P['b_min_height'])
        cb_ = np.where(dbl, PD['c_bridge'], P['c_bridge']); C[2, force_B] = ((cb_ + P['c_bridge_h'] * fil) * ds)[force_B]
        C[0:2, force_B] = np.inf   # 高架の駅は費用 2 倍。トンネルの中の駅・信号場は認める（2026-11-03、ユーザーの指定）
        st, tot = solve_C_mixed(s, h, C, lambda i: PD if dbl[i] else P)
        return st, tot
    # 最初の高さ（2026-11-04）：構造物をすべて土工とみなし、高さの指定（個別の指定・分岐器の高さ・地平駅）を守る高さを一度解いてから、
    # 構造物と高さを交互に解く。指定を入れずに決めた高さから始めると、1 回目に指定の駅の前後がトンネルと決まり、トンネルの条件
    # （地盤−施工基面 ≥ 8 m）で指定の高さに届かないまま抜けられなかった（沼田）。INIT_SPEC=0 で、それまでの決め方（出発点そのまま）
    if STN_H and __import__('os').environ.get('INIT_SPEC', '1') == '1':
        zn, _ = lp(sn, gn, lim, np.zeros(len(sn), int), Pn, tangn); z = np.interp(s, sn, zn)
    def bridge_thr(state, zn):
        """節点ごとの橋梁の高さの境：ふつう BRIDGE_H1。橋梁の連続する節点のうち、いまの高さが H1 を超える部分が BRIDGE_SPAN 以下で
        両側に H1 以下の橋梁の節点か橋梁でない節点がある（峡谷）なら BRIDGE_H2（2026-11-07）"""
        thr = np.full(len(sn), BRIDGE_H1); hb = zn - gn; i = 0
        while i < len(sn):
            if state[i] == 2 and hb[i] > BRIDGE_H1:
                j = i
                while j < len(sn) and state[j] == 2 and hb[j] > BRIDGE_H1: j += 1
                if sn[j - 1] - sn[i] <= BRIDGE_SPAN and i > 0 and j < len(sn): thr[i:j] = BRIDGE_H2
                i = j
            else: i += 1
        return thr
    for it in range(3):
        st, tot = classify(z)
        # 節点ごとの状態（その節点の前後 50 m で最も多い状態）
        state = np.array([np.bincount(st[(s >= x - NODE / 2) & (s <= x + NODE / 2)], minlength=3).argmax() for x in sn])
        if BRIDGE_H1 > 0: BRIDGE_THR = bridge_thr(state, np.interp(sn, s, z))
        zn, slack = lp(sn, gn, lim, state, Pn, tangn); z = np.interp(s, sn, zn)
        h = g - z; print(f"  くり返し {it + 1}：費用 {tot:.3g}  トンネル {np.sum(st == 1) * 20 / 1000:.1f} km・橋梁 {np.sum(st == 2) * 20 / 1000:.1f} km  条件のゆとり 最大 {slack.max():.1f} m", flush=True)
    st, tot = classify(z)
    for k, lo_, hi_, flat in STN_H:
        name = ([n_ for n_, c in r['stations'] if int(np.argmin(np.abs(sn - c))) == k] or ['線の端'])[0]
        if flat:
            hh = zn[k] - (lo_ - FLAT_IN[0]); cls = '地平' if FLAT_IN[0] - 0.05 <= hh <= FLAT_IN[1] + 0.05 else ('準地平' if FLAT_SEMI[0] - 0.05 <= hh <= FLAT_SEMI[1] + 0.05 else '範囲外')
            print(f"  駅の高さ {name}: 地盤から {hh:+.1f} m（地平駅：{cls}）", flush=True)
        else: print(f"  駅の高さ {name}: 施工基面 {zn[k]:.1f} m（指定 {lo_:.1f}〜{hi_:.1f} m）", flush=True)
    r.update({"ground": g.tolist(), "z": z.tolist(), "struct": "".join("-TB"[q] for q in st), "sn": sn.tolist(), "zn": zn.tolist(),
              "R": [None if math.isinf(x) else x for x in radius(r["xy"])]})
    json.dump(r, open(sys.argv[3], "w"), ensure_ascii=False)
    h = g - z; e = st == 0
    print(f"最終：費用 {tot:.3g}  トンネル {np.sum(st == 1) * 20 / 1000:.1f} km（{int(np.sum(np.diff((st == 1).astype(int)) == 1))} か所）・橋梁 {np.sum(st == 2) * 20 / 1000:.1f} km  "
          f"最も深い切土 {h[e].max():.1f} m・最も高い盛土 {(-h[e]).max():.1f} m  深さ 10 m 超の切土 {np.sum(e & (h > 10)) * 20 / 1000:.1f} km・高さ 8 m 超の盛土 {np.sum(e & (h < -8)) * 20 / 1000:.1f} km")
