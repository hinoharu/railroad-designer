#!/bin/sh
# 単冠山麓線を、元の折れ線に沿わせて、収まらない 3 駅間（樺里信号場→単冠山口、西映→上伏古信号場、来季萌→長生内）だけ地形から引いた経路
# （route_sanroku_hyb.json）で計算し直す（2026-11-05、駅は基本地平）。入里節→特掟は電化 33.3‰、ほかは非電化 25‰。済んだ段は飛ばす（q_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f q_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch q_$n.done; }
D() { out=$1; shift; sh -c "$*" > $out 2>&1; grep -E "最終" $out; grep "範囲外" $out || true; }
step hyb sh -c "ROUTE=route_sanroku.json OUT=route_sanroku_hyb.json PREFIX=sr_ GDEF=0.025 GMAP='{\"入里節|特掟\": 0.0333}' python3 devline_hybrid.py"
k='[["特掟","長生内"]]'
step fit sh -c "rm -f branch_sanroku_cands.json; VMAX=120 TILT=0 TRAIN=120 python3 ipfit_branch.py sanroku route_sanroku_hyb.json fit_ipg.json start=fit_shibw.json end=fit_ipg.json > ipb_sanroku.log 2>&1; grep '^sanroku：' ipb_sanroku.log"
step geo sh -c "ROUTE=route_sanroku_hyb.json python3 fit2route.py sanroku > /dev/null && python3 ground.py route_fsanroku.json ground_fsanroku.json > /dev/null"
step s python3 resync2.py sanroku route_sanroku_hyb.json
step d_free D d_sanroku_free.log "KYAKU25_ADD='$k' GCAP=0.0333 python3 design3.py ground_fsanroku.json costs_single.json design_fsanroku_free.json height_spec_sanroku_free.json"
step d_gs D d_sanroku.log "KYAKU25_ADD='$k' GCAP=0.0333 python3 design3.py ground_fsanroku.json costs_single.json design_fsanroku.json height_spec_sanroku.json"
python3 chk_flat.py sanroku
echo 完了
