#!/bin/sh
# 特急 酪別→年萌だけは気動車（キハ283系相当、振子式）として、この特急のための 3 線（酪別線・冬知里支線・小田萌線）を平面から計算し直す
# （2026-11-05、ユーザーの指定。3 線は非電化で 25‰。特急 茂世路→択捉六甲は車両のとおり 789系1000番台の電車で、蘂取線・茂世路線は電化のまま）。条件は特急の経路と同じ VMAX=130 TILT=1 TRAIN=160。済んだ段は飛ばす（t_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f t_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch t_$n.done; }
C="VMAX=130 TILT=1 TRAIN=160"
fit() { b=$1; r=$2; shift 2; rm -f branch_${b}_cands.json; sh -c "$C python3 ipfit_branch.py $b $r fit_ipg.json $* > ipb_$b.log 2>&1"; grep "^$b：" ipb_$b.log; }
geo() { sh -c "ROUTE=$2 python3 fit2route.py $1 > /dev/null && python3 ground.py route_f$1.json ground_f$1.json > /dev/null"; }
des() { b=$1; g=$2; for suf in _free ""; do GCAP=$g python3 design3.py ground_f$b.json costs_single.json design_f$b$suf.json height_spec_$b$suf.json > d_$b$suf.log 2>&1; grep "最終" d_$b$suf.log; grep "範囲外" d_$b$suf.log || true; done; }
for B in rakki:route_rakkibetsu.json:"end":0.025; do
  b=$(echo $B | cut -d: -f1); r=$(echo $B | cut -d: -f2); e=$(echo $B | cut -d: -f3); g=$(echo $B | cut -d: -f4)
  step f_$b fit $b $r $e
  step g_$b geo $b $r
  step s_$b python3 resync2.py $b $r
  step d_$b des $b $g
done
for B in toshi:route_toshiruri.json:"start=fit_moyoro.json end=fit_ipg.json":0.025 otamoi:route_otamoi.json:"start=fit_shibw.json end=fit_moyoro.json":0.025; do
  b=$(echo $B | cut -d: -f1); r=$(echo $B | cut -d: -f2); e=$(echo $B | cut -d: -f3); g=$(echo $B | cut -d: -f4)
  step f_$b fit $b $r $e
  step g_$b geo $b $r
  step s_$b python3 resync2.py $b $r
  step d_$b des $b $g
done
step sys sh run_systems.sh
echo 完了
