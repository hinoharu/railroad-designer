#!/bin/sh
# 折れ線から作った出発点（seed_poly.py）で線形要素を計算し、縦断・走行まで進める（自由曲線の計算を飛ばす）。途中保存から再開できる
# 使い方：sh rerun_p.sh 名前（例 q1e5d30）
cd "$(dirname "$0")"
E=$1; SEED=${2:-p0}; export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 LSMR=1
S=$(date +%s)
[ -s fit_$SEED.json ] || python3 seed_poly.py $SEED > sweep_$E.log 2>&1
[ -s fit_$E.json ] || python3 fitel.py $SEED 100000 30 $E >> sweep_$E.log 2>&1
F=$(date +%s)
sh pipe3.sh $E >> sweep_$E.log 2>&1
python3 wetland.py design_f$E.json wet_f$E.json >> sweep_$E.log 2>&1
sed "s/wet_fm1e5d30/wet_f$E/" height_spec.json > height_spec_$E.json
python3 design3.py ground_f$E.json costs_double.json design_f${E}h.json height_spec_$E.json >> sweep_$E.log 2>&1
for f in fit_ route_f curves_f curvelist_f; do cp ${f}$E.json ${f}${E}h.json; done
python3 run.py design_f${E}h.json run_f${E}h.json curves_f${E}h.json | grep "^B:" >> sweep_$E.log
echo "完了 線形要素 $((F-S)) 秒・全体 $(( $(date +%s)-S )) 秒" >> sweep_$E.log
