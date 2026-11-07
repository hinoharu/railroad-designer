#!/bin/sh
# 択捉空港線（kuko：西単冠〜択捉空港〜植別）・単冠山麓線（sanroku：入里節〜特掟〜…〜長生内）：平面 → キロ程 → 地盤 → 縦断（2026-11-05）。
# 単線（セーブ）。電化区間（空港線 西単冠〜択捉空港、山麓線 入里節〜特掟）は 33‰、非電化区間は 25‰（KYAKU25_ADD）。済んだ段は飛ばす（n5_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f n5_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch n5_$n.done; }
D() { out=$1; shift; sh -c "$*" > $out 2>&1; grep -E "最終" $out; grep "範囲外" $out || true; }
for B in "kuko|route_kuko.json|start=fit_shibw.json|VMAX=110 TILT=0 TRAIN=120|[[\"択捉空港\",\"植別\"]]" "sanroku|route_sanroku.json|start=fit_shibw.json end=fit_ipg.json|VMAX=120 TILT=0 TRAIN=120|[[\"特掟\",\"長生内\"]]"; do
  b=$(echo "$B" | cut -d'|' -f1); r=$(echo "$B" | cut -d'|' -f2); e=$(echo "$B" | cut -d'|' -f3); c=$(echo "$B" | cut -d'|' -f4); k=$(echo "$B" | cut -d'|' -f5)
  step fit_$b sh -c "rm -f branch_${b}_cands.json; $c python3 ipfit_branch.py $b $r fit_ipg.json $e > ipb_$b.log 2>&1; grep '^$b：' ipb_$b.log"
  step geo_$b sh -c "ROUTE=$r python3 fit2route.py $b > /dev/null && python3 ground.py route_f$b.json ground_f$b.json > /dev/null"
  step s_$b python3 resync2.py $b $r
  step d_${b}_free D d_${b}_free.log "KYAKU25_ADD='$k' GCAP=0.0333 python3 design3.py ground_f$b.json costs_single.json design_f${b}_free.json height_spec_${b}_free.json"
  step d_${b}_gs D d_$b.log "KYAKU25_ADD='$k' GCAP=0.0333 python3 design3.py ground_f$b.json costs_single.json design_f$b.json height_spec_$b.json"
done
echo 完了
