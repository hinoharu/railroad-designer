#!/bin/sh
# 背蘂線（sesibe、蘂取〜背祖曽）・丹根萌線（tanne、択捉六甲〜丹根萌）：平面 → キロ程 → 地盤 → 縦断（高さ指定なし・駅地平化）と、急行 蘂取→丹根萌（2026-11-05）。
# 急行（観光急行。セーブでは EF81＋24系・ED79＋E26系の 6 両）をディーゼル機関車 DD51形相当として計算する（ユーザーの指定）：VMAX=95 TILT=0 TRAIN=122。
# 2 線とも単線（セーブ）。非電化として勾配の上限 25‰。済んだ段は飛ばす（n3_*.done）。rerun_tilt.sh が終わってから動かす
set -e
cd "$(dirname "$0")"
while pgrep -f rerun_tilt.sh > /dev/null; do sleep 30; done
step() { n=$1; shift; [ -f n3_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch n3_$n.done; }
C="VMAX=95 TILT=0 TRAIN=122"
fit() { b=$1; r=$2; shift 2; sh -c "$C python3 ipfit_branch.py $b $r fit_ipg.json $* > ipb_$b.log 2>&1"; grep "^$b：" ipb_$b.log; }
geo() { sh -c "ROUTE=$2 python3 fit2route.py $1 > /dev/null && python3 ground.py route_f$1.json ground_f$1.json > /dev/null"; }
des() { b=$1; g=$2; for suf in _free ""; do GCAP=$g python3 design3.py ground_f$b.json costs_single.json design_f$b$suf.json height_spec_$b$suf.json > d_$b$suf.log 2>&1; grep "最終" d_$b$suf.log; grep "範囲外" d_$b$suf.log || true; done; }
for B in sesibe:route_sesibe.json:"start=fit_ipg.json end=fit_moyoro.json":0.025 tanne:route_tanne.json:"start":0.025; do
  b=$(echo $B | cut -d: -f1); r=$(echo $B | cut -d: -f2); e=$(echo $B | cut -d: -f3); g=$(echo $B | cut -d: -f4)
  step f_$b fit $b $r $e
  step g_$b geo $b $r
  step s_$b python3 resync2.py $b $r
  step d_$b des $b $g
done
for v in "" gs; do VMAX=95 TILT=0 TRAIN=122 python3 keito2.py sys_kyuko.json $v; done
echo 完了
