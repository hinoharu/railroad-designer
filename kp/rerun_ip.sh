#!/bin/sh
# 交点法の結果（fit_<名前>.json）から、縦断・走行まで（高さ指定なし・あり）
cd "$(dirname "$0")"
E=$1
sh pipe3.sh $E >> sweep_$E.log 2>&1
python3 wetland.py design_f$E.json wet_f$E.json >> sweep_$E.log 2>&1
sed "s/wet_fm1e5d30/wet_f$E/" height_spec.json > height_spec_$E.json
python3 design3.py ground_f$E.json costs_double.json design_f${E}h.json height_spec_$E.json >> sweep_$E.log 2>&1
for f in fit_ route_f curves_f curvelist_f; do cp ${f}$E.json ${f}${E}h.json; done
python3 run.py design_f${E}h.json run_f${E}h.json curves_f${E}h.json | grep "^B:" >> sweep_$E.log
echo "完了" >> sweep_$E.log
