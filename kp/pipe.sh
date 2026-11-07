#!/bin/sh
# 使い方：sh pipe.sh 名前（fit_名前.json から走行時間まで）
t=$1
python3 fit2route.py $t && python3 ground.py route_f$t.json ground_f$t.json && python3 design2.py ground_f$t.json design_f$t.json 30 20 > /dev/null && python3 run.py design_f$t.json run_f$t.json curves_f$t.json | grep -E "^B:" && python3 terrain.py design_f$t.json
