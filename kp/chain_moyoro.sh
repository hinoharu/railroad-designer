#!/bin/sh
# 茂世路線を、作図の線に沿わせて無理な 2 駅間（去家→背祖曽、背祖曽→応仁萌）だけ地形から引いた経路（route_moyoro_hyb.json）で計算し直し、
# つながる冬知里支線・小田萌線・背蘂線も分岐器の位置から計算し直す（2026-11-05、ユーザーの指定：駅の地平化は最後までがんばる）。済んだ段は飛ばす（m_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f m_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch m_$n.done; }
D() { out=$1; shift; sh -c "$*" > $out 2>&1; grep -E "最終" $out; grep "範囲外" $out || true; }
step fit_moyoro sh -c "rm -f branch_moyoro_cands.json; VMAX=130 TILT=0 TRAIN=170 python3 ipfit_branch.py moyoro route_moyoro_hyb.json fit_shibr.json end > ipb_moyoro.log 2>&1; grep '^moyoro：' ipb_moyoro.log"
step geo_moyoro sh -c "ROUTE=route_moyoro_hyb.json python3 fit2route.py moyoro > /dev/null && python3 ground.py route_fmoyoro.json ground_fmoyoro.json > /dev/null"
step s_moyoro python3 resync2.py moyoro route_moyoro_hyb.json
step d_moyoro_free D d_moyoro_free.log GCAP=0.035 python3 design3.py ground_fmoyoro.json costs_single.json design_fmoyoro_free.json height_spec_moyoro_free.json
step d_moyoro_gs D d_moyoro.log GCAP=0.035 python3 design3.py ground_fmoyoro.json costs_single.json design_fmoyoro.json height_spec_moyoro.json
for B in "toshi|route_toshiruri.json|start=fit_moyoro.json end=fit_ipg.json|VMAX=130 TILT=1 TRAIN=160" "otamoi|route_otamoi.json|start=fit_shibw.json end=fit_moyoro.json|VMAX=130 TILT=1 TRAIN=160" "sesibe|route_sesibe_hyb.json|start=fit_ipg.json end=fit_moyoro.json|VMAX=95 TILT=0 TRAIN=122"; do
  b=$(echo "$B" | cut -d'|' -f1); r=$(echo "$B" | cut -d'|' -f2); e=$(echo "$B" | cut -d'|' -f3); c=$(echo "$B" | cut -d'|' -f4)
  step fit_$b sh -c "rm -f branch_${b}_cands.json; $c python3 ipfit_branch.py $b $r fit_ipg.json $e > ipb_$b.log 2>&1; grep '^$b：' ipb_$b.log"
  step geo_$b sh -c "ROUTE=$r python3 fit2route.py $b > /dev/null && python3 ground.py route_f$b.json ground_f$b.json > /dev/null"
  step s_$b python3 resync2.py $b $r
  step d_${b}_free D d_${b}_free.log GCAP=0.025 python3 design3.py ground_f$b.json costs_single.json design_f${b}_free.json height_spec_${b}_free.json
  step d_${b}_gs D d_$b.log GCAP=0.025 python3 design3.py ground_f$b.json costs_single.json design_f$b.json height_spec_$b.json
done
step sys sh -c "sh run_systems.sh > /dev/null"
for v in "" gs; do VMAX=95 TILT=0 TRAIN=122 python3 keito2.py sys_kyuko.json $v > /dev/null; done
echo 完了
