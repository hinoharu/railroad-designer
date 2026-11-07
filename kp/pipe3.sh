#!/bin/sh
# 使い方：sh pipe3.sh 名前（fit_名前.json から走行時間まで。縦断は構造物の費用を見て決める design3.py、複線の費用）
t=$1
python3 fit2route.py $t && python3 ground.py route_f$t.json ground_f$t.json && python3 design3.py ground_f$t.json costs_double.json design_f$t.json | tail -1 && python3 run.py design_f$t.json run_f$t.json curves_f$t.json | grep -E "^B:" && python3 terrain.py design_f$t.json
