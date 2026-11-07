#!/bin/sh
# 単冠山麓線を、最高速度 85 km/h の前提で当てはめ直す（2026-11-06、ユーザーの指定：芸備線・木次線のイメージ、85 km/h）。それまでの 120 km/h 前提の結果は kp_var/N3。もとは（2026-11-05、ユーザーの選択：単冠山口は両側の線が同じ側から入る駅＝スイッチバック駅）。
# 北側 sanroku_n（入里節〜単冠山口、入里節〜特掟は電化 33.3‰、ほかは 25‰）、南側 sanroku_s（単冠山口〜長生内、25‰）。
# 収まらない駅間は元の折れ線の帯の中で探した線（chain_sanroku.sh で探した sr_*.json を使う）。単冠山口の高さは南側を北側に合わせる。済んだ段は飛ばす（q3_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f q3_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch q3_$n.done; }
D() { out=$1; shift; sh -c "$*" > $out 2>&1; grep -E "最終" $out; grep "範囲外" $out || true; }
step hyb_n sh -c "ROUTE=route_sanroku_n.json OUT=route_sanroku_n_hyb.json PREFIX=sr_ GDEF=0.025 GMAP='{\"入里節|特掟\": 0.0333}' python3 devline_hybrid.py | tail -7"
step hyb_s sh -c "ROUTE=route_sanroku_s.json OUT=route_sanroku_s_hyb.json PREFIX=sr_ GDEF=0.025 python3 devline_hybrid.py | tail -7"
# 北側
step fit_n sh -c "rm -f branch_sanroku_n_cands.json; VMAX=85 TILT=0 TRAIN=80 python3 ipfit_branch.py sanroku_n route_sanroku_n_hyb.json fit_shibw.json start=fit_shibw.json > ipb_sanroku_n.log 2>&1; grep '^sanroku_n：\|D を超える' ipb_sanroku_n.log"
step geo_n sh -c "ROUTE=route_sanroku_n_hyb.json python3 fit2route.py sanroku_n > /dev/null && python3 ground.py route_fsanroku_n.json ground_fsanroku_n.json > /dev/null"
step s_n python3 resync2.py sanroku_n route_sanroku_n_hyb.json
k='[["特掟","単冠山口"]]'
step d_n_free D d_sanroku_n_free.log "KYAKU25_ADD='$k' GCAP=0.0333 python3 design3.py ground_fsanroku_n.json costs_single.json design_fsanroku_n_free.json height_spec_sanroku_n_free.json"
step d_n_gs D d_sanroku_n.log "KYAKU25_ADD='$k' GCAP=0.0333 python3 design3.py ground_fsanroku_n.json costs_single.json design_fsanroku_n.json height_spec_sanroku_n.json"
# 南側
step fit_s sh -c "rm -f branch_sanroku_s_cands.json; VMAX=85 TILT=0 TRAIN=80 python3 ipfit_branch.py sanroku_s route_sanroku_s_hyb.json fit_ipg.json end=fit_ipg.json > ipb_sanroku_s.log 2>&1; grep '^sanroku_s：\|D を超える' ipb_sanroku_s.log"
step geo_s sh -c "ROUTE=route_sanroku_s_hyb.json python3 fit2route.py sanroku_s > /dev/null && python3 ground.py route_fsanroku_s.json ground_fsanroku_s.json > /dev/null"
step s_s python3 resync2.py sanroku_s route_sanroku_s_hyb.json
step z_s python3 -c "
import json
for suf in ('_free', ''):
    d = json.load(open(f'design_fsanroku_n{suf}.json')); f = f'height_spec_sanroku_s{suf}.json'; sp = json.load(open(f))
    sp['start_z'] = d['z'][-1]; sp['note_start'] = '単冠山口の施工基面を北側（sanroku_n）の終点に合わせる'; json.dump(sp, open(f, 'w'), ensure_ascii=False); print(suf or '_gs', round(d['z'][-1], 1))
"
step d_s_free D d_sanroku_s_free.log "GCAP=0.025 python3 design3.py ground_fsanroku_s.json costs_single.json design_fsanroku_s_free.json height_spec_sanroku_s_free.json"
step d_s_gs D d_sanroku_s.log "GCAP=0.025 python3 design3.py ground_fsanroku_s.json costs_single.json design_fsanroku_s.json height_spec_sanroku_s.json"
python3 chk_flat.py sanroku_n sanroku_s
echo 完了
