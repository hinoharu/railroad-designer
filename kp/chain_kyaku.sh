#!/bin/sh
# 急行の全区間を 15‰（15‰ で駅が届かない茂世路線・蘂取線 沼田〜南留別・背蘂線は、重連の想定で 25‰）（2026-11-05、ユーザーの指定）：design3.py の KYAKU_ST に急行の経路の残りを加えたので、縦断を計算し直す（線形は変えない）。
# 蘂取線（紗那〜南留別）→ 茂世路線 → 冬知里支線・小田萌線（端の高さを合わせ直す）、丹根萌線。背蘂線は経路を探し直すので別（devline.py）。済んだ段は飛ばす（k_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f k_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch k_$n.done; }
D() { out=$1; shift; sh -c "$*" > $out 2>&1; grep -E "最終" $out; grep "範囲外" $out || true; }
step shibr_free D d_shibr_free.log GCAP=0.0333 python3 design3.py ground_fshibr.json costs_single.json design_fshibr_free.json height_spec_shibr_free.json
step shibr_gs D d_shibr.log GCAP=0.0333 python3 design3.py ground_fshibr.json costs_single.json design_fshibr.json height_spec_shibr.json
step s_moyoro python3 resync2.py moyoro route_moyoro.json
step moyoro_free D d_moyoro_free.log GCAP=0.035 python3 design3.py ground_fmoyoro.json costs_single.json design_fmoyoro_free.json height_spec_moyoro_free.json
step moyoro_gs D d_moyoro.log GCAP=0.035 python3 design3.py ground_fmoyoro.json costs_single.json design_fmoyoro.json height_spec_moyoro.json
for B in toshi:route_toshiruri.json otamoi:route_otamoi.json tanne:route_tanne.json; do
  b=${B%%:*}; r=${B#*:}
  step s_$b python3 resync2.py $b $r
  step ${b}_free D d_${b}_free.log GCAP=0.025 python3 design3.py ground_f$b.json costs_single.json design_f${b}_free.json height_spec_${b}_free.json
  step ${b}_gs D d_$b.log GCAP=0.025 python3 design3.py ground_f$b.json costs_single.json design_f$b.json height_spec_$b.json
done
step s_sesibe python3 resync2.py sesibe route_sesibe_dev.json
step sesibe_free D d_sesibe_free.log GCAP=0.025 python3 design3.py ground_fsesibe.json costs_single.json design_fsesibe_free.json height_spec_sesibe_free.json
step sesibe_gs D d_sesibe.log GCAP=0.025 python3 design3.py ground_fsesibe.json costs_single.json design_fsesibe.json height_spec_sesibe.json
step sys sh run_systems.sh
for v in "" gs; do VMAX=95 TILT=0 TRAIN=122 python3 keito2.py sys_kyuko.json $v > /dev/null; done
echo 完了
