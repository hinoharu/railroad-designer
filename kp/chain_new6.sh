#!/bin/sh
# 択捉の残り 6 路線（7 区間）の線形・縦断を計算する（2026-11-06、ユーザーの指定「全路線制覇」、まず択捉）。経路は make_routes6.py。
# どの線も低速の普通（気動車）だけが走る：非電化・単線・勾配の上限 25‰、線形は 85 km/h 前提（単冠山麓線と同じ考え、芸備線・木次線のイメージ）。
# 列車の長さ 80 m（4 両）。済んだ段は飛ばす（n6_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f n6_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch n6_$n.done; }
D() { out=$1; shift; sh -c "$*" > $out 2>&1; grep -E "最終" $out; grep "範囲外" $out || true; }
for B in "furu|fit_ipg.json|start=fit_ipg.json" "atosa_w|fit_ipg.json|start=fit_ipg.json" "atosa_e|fit_ipg.json|start=fit_ipg.json" "noto|fit_ipg.json|start=fit_ipg.json" \
         "yorib|fit_otamoi.json|start=fit_otamoi.json" "otoshi|fit_moyoro.json|start=fit_moyoro.json" "moke|fit_ipg.json|end=fit_ipg.json"; do
  b=$(echo "$B" | cut -d'|' -f1); t=$(echo "$B" | cut -d'|' -f2); e=$(echo "$B" | cut -d'|' -f3); r=route_$b.json
  step fit_$b sh -c "rm -f branch_${b}_cands.json; VMAX=85 TILT=0 TRAIN=80 python3 ipfit_branch.py $b $r $t $e > ipb_$b.log 2>&1; grep '^$b：\|D を超える' ipb_$b.log"
  step geo_$b sh -c "ROUTE=$r python3 fit2route.py $b > /dev/null && python3 ground.py route_f$b.json ground_f$b.json > /dev/null"
  step s_$b python3 resync2.py $b $r
  step d_${b}_free D d_${b}_free.log "GCAP=0.025 python3 design3.py ground_f$b.json costs_single.json design_f${b}_free.json height_spec_${b}_free.json"
  step d_${b}_gs D d_$b.log "GCAP=0.025 python3 design3.py ground_f$b.json costs_single.json design_f$b.json height_spec_$b.json"
done
python3 chk_flat.py furu atosa_w atosa_e noto yorib otoshi moke
echo 完了
