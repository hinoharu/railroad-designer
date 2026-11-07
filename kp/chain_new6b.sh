#!/bin/sh
# 阿登佐線 東側を散布泊（スイッチバック駅）で 2 区間に分けて計算し直す（2026-11-06）。条件は chain_new6.sh と同じ。
# 散布泊の施工基面は、atosa_e2 を atosa_e1 の終点に合わせる（単冠山麓線の単冠山口と同じ）。済んだ段は飛ばす（n6b_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f n6b_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch n6b_$n.done; }
D() { out=$1; shift; sh -c "$*" > $out 2>&1; grep -E "最終" $out; grep "範囲外" $out || true; }
for B in "atosa_e1|fit_ipg.json|start=fit_ipg.json" "atosa_e2|fit_ipg.json|free"; do
  b=$(echo "$B" | cut -d'|' -f1); t=$(echo "$B" | cut -d'|' -f2); e=$(echo "$B" | cut -d'|' -f3); r=route_$b.json
  step fit_$b sh -c "rm -f branch_${b}_cands.json; VMAX=85 TILT=0 TRAIN=80 python3 ipfit_branch.py $b $r $t $e > ipb_$b.log 2>&1; grep '^$b：\|D を超える' ipb_$b.log"
  step geo_$b sh -c "ROUTE=$r python3 fit2route.py $b > /dev/null && python3 ground.py route_f$b.json ground_f$b.json > /dev/null"
  [ "$e" != free ] && step s_$b python3 resync2.py $b $r
  if [ "$b" = atosa_e2 ]; then
    step z_$b python3 -c "
import json, os
for suf in ('_free', ''):
    d = json.load(open(f'design_fatosa_e1{suf}.json')); f = f'height_spec_atosa_e2{suf}.json'; sp = json.load(open(f)) if os.path.exists(f) else {'double': []}
    if suf == '' and 'stations' not in sp: sp['stations'] = {'阿登佐岳': '地平'}
    sp['start_z'] = d['z'][-1]; sp['note_start'] = '散布泊の施工基面を atosa_e1 の終点に合わせる'; json.dump(sp, open(f, 'w'), ensure_ascii=False); print(suf or '_gs', round(d['z'][-1], 1))
"
  fi
  step d_${b}_free D d_${b}_free.log "GCAP=0.025 python3 design3.py ground_f$b.json costs_single.json design_f${b}_free.json height_spec_${b}_free.json"
  step d_${b}_gs D d_$b.log "GCAP=0.025 python3 design3.py ground_f$b.json costs_single.json design_f$b.json height_spec_$b.json"
done
python3 chk_flat.py atosa_e1 atosa_e2
echo 完了
