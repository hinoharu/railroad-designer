#!/bin/sh
# 支線の線形（交点法）→ 経路 → 地盤 → 縦断 → 系統の走行（2026-11-04）
# 使い方：sh rerun_branch.sh 支線の名前 経路.json 幹線の名前 費用の表 系統名 終点の駅 停車駅（・区切り）
# 例：VMAX=100 TILT=0 TRAIN=40 sh rerun_branch.sh sanpu route_sanpu.json ipg costs_single.json 普通大岬紗那 紗那 大岬・散布・…・紗那
set -e
cd "$(dirname "$0")"
B=$1; ROUTE=$2; T=$3; COSTS=$4; K=$5; END=$6; STOPS=$7
python3 ipfit_branch.py $B $ROUTE fit_$T.json
ROUTE=$ROUTE python3 fit2route.py $B
python3 ground.py route_f$B.json ground_f$B.json
# 分岐器の位置の施工基面の標高を、幹線（高さ指定あり）に合わせる
python3 - "$B" "$T" <<'EOF'
import json, sys
import numpy as np
B, T = sys.argv[1:3]
fb = json.load(open(f'fit_{B}.json')); ft = json.load(open(f'fit_{T}.json')); rt = json.load(open(f'route_f{T}.json')); dt = json.load(open(f'design_f{T}h.json'))
sj = float(np.interp(fb['junction']['s'], ft['s'], rt['s'])); z = float(np.interp(sj, dt['s'], dt['z']))
json.dump({'note': '支線の端（分岐器の位置）の施工基面の標高を幹線に合わせる', 'end_z': z}, open(f'height_spec_{B}.json', 'w'), ensure_ascii=False)
print(f'分岐器の位置 {sj:.0f} m、幹線の施工基面 {z:.1f} m')
EOF
python3 design3.py ground_f$B.json $COSTS design_f$B.json height_spec_$B.json
python3 keito.py $K $B $T $END "$STOPS"
