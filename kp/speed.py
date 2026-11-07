# 曲線の制限速度（km/h）。振子式の気動車（キハ 283 系相当、最高 130 km/h）。2026-11-03、ユーザーの指定：
#   半径 600 m 以上：本則＋30。本則 = √(R×(105+60)/11.8)（カント 105 mm、カント不足量 60 mm）
#   半径 600 m 未満：√(R×(105+110)/11.8)（振子式に許されるカント不足量 110 mm。振子の上乗せは半径 600 m 以上の条件のため）
#   走行の計算では 5 km/h 単位に切り捨てる（本則の値は 5 km/h 単位に切り捨てた値。調査は検索結果の要約によるもので原文は未照合）
# 最適化では、切り捨てない値を使い、半径 560〜600 m の飛びを直線でつなぐ（速度が階段状だと勾配がなく、最適化が進まない）
# 線区ごとの条件（2026-11-04）：環境変数 VMAX（km/h）・TILT（1＝振子式、0＝本則）。指定がなければ択捉の特急（130・振子式）
#   本則（振子なし）：すべての半径で √(R×(105+60)/11.8)
import os
import numpy as np
VMAX = float(os.environ.get('VMAX', '130'))
TILT = os.environ.get('TILT', '1') == '1'
def _small(R): return np.sqrt(R * 215 / 11.8)
def _large(R): return np.sqrt(R * 165 / 11.8) + 30
def _honsoku(R): return np.sqrt(R * 165 / 11.8)
MARGIN = 1.0   # km/h：標識の制限速度を 1 km/h 超えて走っても、曲線を安全に通れる速度を超えないための余裕（2026-11-03、ユーザーの指定）
def limit(R):
    """標識の制限速度（走行の計算に使う）：曲線を安全に通れる速度から 1 km/h を引き、5 km/h 単位に切り捨てる"""
    R = np.asarray(R, float)
    if not TILT: return np.minimum(VMAX, np.floor((_honsoku(R) - MARGIN) / 5 + 1e-9) * 5)
    v = np.where(R >= 600, _large(R), _small(R)) - MARGIN
    return np.minimum(VMAX, np.floor(v / 5 + 1e-9) * 5)
def smooth(R):
    """最適化に使う制限速度（切り捨てず、560〜600 m をなめらかにつなぐ。余裕の 1 km/h は同じに引く）"""
    R = np.asarray(R, float)
    if not TILT: return np.minimum(VMAX, _honsoku(R) - MARGIN)
    t = np.clip((R - 560) / 40, 0, 1)
    v = (1 - t) * _small(R) + t * _large(R) - MARGIN
    return np.minimum(VMAX, v)
if __name__ == "__main__":
    for R in [160, 180, 200, 250, 300, 400, 500, 599, 600, 715, 720, 730, 800]:
        print(R, round(float(smooth(R)), 1), float(limit(R)))
