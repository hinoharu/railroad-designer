#!/bin/sh
# 背蘂線の全駅間を、駅の位置だけを拘束条件に地形から引き直す（POC、2026-11-05）。急行は DD51形の重連の想定で 25‰（ユーザーの了承：単機で無理なら重連）。
# 駅での向きは前の駅間の到着の向きを引き継ぐ。両端（蘂取：特急の経路の起点、背祖曽：茂世路線）は作図の向き。済んだ駅間は飛ばす（出力のファイルがあれば）
cd "$(dirname "$0")"
set -e
ST="蘂取 良宇仁 睡名 長根 天幕 上去家 中去家信号場 背祖曽"; prev=""; HA=""
set -- $ST
while [ $# -ge 2 ]; do
  a=$1; b=$2; shift; f=dev3_${a}_${b}.json
  hbopt=-1; [ $# -eq 1 ] && hbopt=draw
  if [ ! -f $f ]; then echo "== $a→$b $(date +%H:%M)"; GMAX=0.025 K=800 MARGIN=3000 HA=$HA HB=$hbopt python3 devline2.py route_sesibe.json $a $b $f | grep -v "km：状態"; fi
  HA=$(python3 -c "import json;print(json.load(open('$f'))['heading_end'])")
done
echo 完了
