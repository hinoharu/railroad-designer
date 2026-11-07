# 構造物（土工・トンネル・橋梁）を、線路 1 m あたりの概算の費用で比べて決める（動的計画法）。
# 施工基面の高さは design2.py の結果のまま。20 m ごとに 3 つの状態（E 土工＝切土か盛土、T トンネル、B 橋梁）から選び、
# 全体の費用が最小になる並びを求める。費用の数値は costs_<名前>.json（単線・複線など）で渡す。
#   切土：掘削の単価×(b·h + m·h²) ＋ のり面の単価×2·h·√(1+m²)        h：施工基面から地盤までの深さ
#   盛土：盛土の単価×(b'·h + m'·h²) ＋ のり面の単価×2·h·√(1+m'²)     h：地盤から施工基面までの高さ
#   トンネル：1 m あたり一定（中の深さ ≥ 断面の高さ＋最小の土かぶり）。坑口 1 か所ごとに一定（坑口の深さ ≥ 坑口の最低の深さ）
#   橋梁：1 m あたり（一定＋高さ×係数）。両端の橋台 1 か所ごとに一定
# 使い方：python3 structdp.py design_f名前.json costs_名前.json 出力.json
import json, math, sys
import numpy as np

def costs_per_m(h, P):
    """深さ h（＋は地盤が上＝切土、−は地盤が下＝盛土）での、各状態の 1 m あたりの費用（できない状態は inf）"""
    cut = np.maximum(h, 0); fil = np.maximum(-h, 0)
    E = (P["c_cut"] * (P["b_cut"] * cut + P["m_cut"] * cut ** 2) + P["c_slope"] * 2 * cut * math.sqrt(1 + P["m_cut"] ** 2)
         + P["c_fill"] * (P["b_fill"] * fil + P["m_fill"] * fil ** 2) + P["c_slope"] * 2 * fil * math.sqrt(1 + P["m_fill"] ** 2))
    T = np.where(h >= P["t_height"] + P["t_cover_min"], P["c_tunnel"], np.inf)
    B = np.where(-h >= P["b_min_height"], P["c_bridge"] + P["c_bridge_h"] * fil, np.inf)
    return np.vstack([E, T, B])

def solve(s, h, P, fixed_E=None):
    ds = np.gradient(s); C = costs_per_m(h, P) * ds
    if fixed_E is not None: C[1:, fixed_E] = np.inf
    return solve_C(s, h, P, C)

def solve_C(s, h, P, C):
    """区間ごとの費用の表 C（3×n）を受け取って解く"""
    n = len(s); INF = np.inf
    # 状態の切り替えの費用：E↔T は坑口（その位置の深さ ≥ 坑口の最低の深さ）、E↔B と T↔B は橋台
    def trans(i):
        t = np.zeros((3, 3))
        portal = P["c_portal"] if h[i] >= P["t_portal_min"] else INF
        t[0, 1] = t[1, 0] = portal
        t[0, 2] = t[2, 0] = P["c_abutment"]
        t[1, 2] = t[2, 1] = portal + P["c_abutment"]
        return t
    cost = C[:, 0].copy(); back = np.zeros((n, 3), int)
    cost[1] += P["c_portal"] if h[0] >= P["t_portal_min"] else INF; cost[2] += P["c_abutment"]
    for i in range(1, n):
        t = trans(i); tot = cost[:, None] + t; back[i] = np.argmin(tot, axis=0); cost = tot[back[i], [0, 1, 2]] + C[:, i]
    # 終点：トンネル・橋梁で終わるなら坑口・橋台
    end = cost + np.array([0, P["c_portal"] if h[-1] >= P["t_portal_min"] else INF, P["c_abutment"]])
    st = np.zeros(n, int); st[-1] = int(np.argmin(end))
    for i in range(n - 1, 0, -1): st[i - 1] = back[i, st[i]]
    return st, float(end.min())

if __name__ == "__main__":
    D = json.load(open(sys.argv[1])); P = json.load(open(sys.argv[2]))
    s = np.array(D["s"]); g = np.array(D["ground"], float); z = np.array(D["z"])
    g = np.where(np.isnan(g), z, g); h = g - z
    # 停車駅の構内（前後 110 m）は土工にする（構内の構造物は扱わない）
    stops = [c for n_, c in D["stations"] if n_ in D["stops"]]
    fixed = np.zeros(len(s), bool)
    for c in stops: fixed |= np.abs(s - c) <= 110
    st, total = solve(s, h, P, fixed)
    D["struct"] = "".join("-TB"[q] for q in st)
    json.dump(D, open(sys.argv[3], "w"), ensure_ascii=False)
    ds = np.gradient(s); k = lambda q: ds[st == q].sum() / 1000
    T_runs = sum(1 for i in range(1, len(st)) if st[i] == 1 and st[i - 1] != 1)
    cutp = (st == 0) & (h > 0); filp = (st == 0) & (h < 0)
    print(f"{P.get('name','')}: トンネル {k(1):.1f} km（{T_runs} か所）・橋梁 {k(2):.1f} km・土工 {k(0):.1f} km；"
          f"切土の最大の深さ {h[cutp].max() if cutp.any() else 0:.1f} m、盛土の最大の高さ {(-h[filp]).max() if filp.any() else 0:.1f} m；費用の合計 {total:.3g}")
