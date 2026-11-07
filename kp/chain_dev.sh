#!/bin/sh
# 背蘂線を、駅の位置だけから引いた経路（route_sesibe_dev.json）で、線形 → キロ程 → 地盤 → 縦断 → 急行（2026-11-05、POC）。済んだ段は飛ばす（v_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f v_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch v_$n.done; }
step fit sh -c "rm -f branch_sesibe_cands.json; VMAX=95 TILT=0 TRAIN=122 python3 ipfit_branch.py sesibe route_sesibe_dev.json fit_ipg.json start=fit_ipg.json end=fit_moyoro.json > ipb_sesibe.log 2>&1; grep '^sesibe：' ipb_sesibe.log"
step geo sh -c "ROUTE=route_sesibe_dev.json python3 fit2route.py sesibe > /dev/null && python3 ground.py route_fsesibe.json ground_fsesibe.json"
step spec sh -c "rm -f height_spec_sesibe.json height_spec_sesibe_free.json; python3 resync2.py sesibe route_sesibe_dev.json"
for suf in _free ""; do
  step des$suf sh -c "GCAP=0.025 python3 design3.py ground_fsesibe.json costs_single.json design_fsesibe$suf.json height_spec_sesibe$suf.json > d_sesibe$suf.log 2>&1; grep 最終 d_sesibe$suf.log; grep 範囲外 d_sesibe$suf.log || true"
done
for v in "" gs; do VMAX=95 TILT=0 TRAIN=122 python3 keito2.py sys_kyuko.json $v > /dev/null; done
echo 完了
