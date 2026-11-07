#!/bin/sh
# 粗い間隔（H m）の自由曲線を出発点にして線形要素を計算し、縦断・走行まで進める。途中保存から再開できる
# 使い方：sh rerun_v.sh（自由曲線は fitk_v.py：場所ごとの間隔）
cd "$(dirname "$0")"
K=cv; E=sv; export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 LSMR=1
S=$(date +%s)
[ -s fit_$K.json ] || python3 fitk_v.py 100000 30 $K > sweep_$E.log 2>&1
F1=$(date +%s)
[ -s fit_$E.json ] || python3 fitel.py $K 100000 30 $E >> sweep_$E.log 2>&1
F2=$(date +%s)
sh pipe3.sh $E >> sweep_$E.log 2>&1
python3 wetland.py design_f$E.json wet_f$E.json >> sweep_$E.log 2>&1
sed "s/wet_fm1e5d30/wet_f$E/" height_spec.json > height_spec_$E.json
python3 design3.py ground_f$E.json costs_double.json design_f${E}h.json height_spec_$E.json >> sweep_$E.log 2>&1
for f in fit_ route_f curves_f curvelist_f; do cp ${f}$E.json ${f}${E}h.json; done
python3 run.py design_f${E}h.json run_f${E}h.json curves_f${E}h.json | grep "^B:" >> sweep_$E.log
echo "完了 自由曲線 $((F1-S)) 秒・線形要素 $((F2-F1)) 秒・全体 $(( $(date +%s)-S )) 秒" >> sweep_$E.log
