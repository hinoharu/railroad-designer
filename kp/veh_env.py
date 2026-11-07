# 車両の性能の表（vehicles.json）から、走行の計算（run.py）に渡す環境変数を作る（2026-11-06、ユーザーの指定：系統ごとの車両の性能）
# 使い方：env $(python3 veh_env.py 719系 6) VMAX=110 ... python3 keito2.py ...
# 表の 1 両あたりの質量 mass_t・レールでの出力 p_kw と起動加速度 a0（km/h/s）から、列車全体の P_KW・MASS_T・FMAX_KN（= 質量 × a0 ÷ 3.6）
import json, sys
V = json.load(open('vehicles.json'))['vehicles']
t, n = sys.argv[1], int(sys.argv[2]); v = V[t]
m = v['mass_t'] * n; p = v['p_kw'] * n
print(f"P_KW={p:.0f} MASS_T={m:.1f} FMAX_KN={m * v['a0'] / 3.6:.1f}")
