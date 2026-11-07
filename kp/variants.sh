#!/bin/sh
# 案の比較（2026-11-05、ユーザーの指定：「当初」から「最終」まで、いろいろな条件で計算した結果を比べるページ）のための案を、kp_var/<案> で計算する。
# 最終の結果（kp）は書き換えない。済んだ案は飛ばす（kp_var/<案>/done）
set -e
K=$(cd "$(dirname "$0")" && pwd); V=$K/../kp_var
prep() { d=$V/$1; mkdir -p $d; cd $d; ln -sfn $K/dem dem; cp $K/costs_single.json $K/costs_double.json .; for f in fit_ipg.json route_fipg.json design_fipgh.json design_fipgh_gs.json fit_shibr.json route_fshibr.json design_fshibr_free.json design_fshibr.json fit_moyoro.json route_fmoyoro.json design_fmoyoro_free.json design_fmoyoro.json fit_shibw.json route_fshibw.json design_fshibw_free.json design_fshibw.json; do [ -f $f ] || cp $K/$f .; done; }
done_() { [ -f $V/$1/done ]; }
py() { python3 $K/$1 "$@" ; }
sesibe_calc() {  # $1 経路 $2 GCAP
  rm -f branch_sesibe_cands.json
  VMAX=95 TILT=0 TRAIN=122 python3 $K/ipfit_branch.py sesibe $1 fit_ipg.json start=fit_ipg.json end=fit_moyoro.json > ipb.log 2>&1; grep '^sesibe：' ipb.log
  ROUTE=$1 python3 $K/fit2route.py sesibe > /dev/null; python3 $K/ground.py route_fsesibe.json ground_fsesibe.json > /dev/null
  rm -f height_spec_sesibe*.json; python3 $K/resync2.py sesibe $1 > /dev/null
  for suf in _free ""; do
    if ! GCAP=$2 python3 $K/design3.py ground_fsesibe.json costs_single.json design_fsesibe$suf.json height_spec_sesibe$suf.json > d$suf.log 2>&1; then
      # 解けないこと自体を結果として残す（S2：15‰ では解なし）。線形を見られるように、縦断は 25‰ で計算する（ページの備考に書く）
      echo "  $2 では縦断が解けない（$(tail -1 d$suf.log | cut -c1-60)）。縦断は 25‰ で計算する"; echo "$2" > infeasible
      GCAP=0.025 python3 $K/design3.py ground_fsesibe.json costs_single.json design_fsesibe$suf.json height_spec_sesibe$suf.json > d$suf.log 2>&1
    fi
    grep 最終 d$suf.log; grep 範囲外 d$suf.log || true
  done
}
# 背蘂線
if ! done_ S1; then echo "== S1 作図の線・25‰"; prep S1; cp $K/../kp_sesibe_draw/fit_sesibe.json $K/../kp_sesibe_draw/route_fsesibe.json $K/../kp_sesibe_draw/design_fsesibe.json $K/../kp_sesibe_draw/design_fsesibe_free.json $K/../kp_sesibe_draw/curvelist_fsesibe.json .; cp $K/route_sesibe.json route.json; touch done; fi
if ! done_ S2; then echo "== S2 天幕→上去家だけ 15‰ で探した線・縦断 15‰"; prep S2; cp $K/route_sesibe.json $K/dev2_tenmaku.json .
  python3 - <<'PY'
import json, sys
from geo import metres
r = json.load(open('route_sesibe.json')); n = [x for x, _ in r['stations']]; P = r['points']; V = r['vidx']; d = json.load(open('dev2_tenmaku.json'))['points']
k = n.index('天幕'); pts = P[:V[k] + 1] + d[1:-1] + P[V[k + 1]:]
st, vi, ch, out = [], [], 0.0, [pts[0]]
for q in pts[1:]: ch += metres(out[-1], q); out.append(q)
cum = [0.0]
for a, b in zip(out, out[1:]): cum.append(cum[-1] + metres(a, b))
idx = [V[i] if i <= k else V[i] - V[k + 1] + V[k] + len(d) - 1 for i in range(len(n))]
json.dump({'points': out, 'stations': [(x, cum[i]) for x, i in zip(n, idx)], 'stops': n, 'vidx': idx}, open('route.json', 'w'), ensure_ascii=False)
PY
  sesibe_calc route.json 0.015; touch done; fi
if ! done_ S3; then echo "== S3 駅の位置だけから引いた線・25‰"; prep S3; cp $K/route_sesibe_dev.json route.json; sesibe_calc route.json 0.025; touch done; fi
if ! done_ S4; then echo "== S4 作図に沿わせた線・25‰（探す勾配も 25‰）"; prep S4; (cd $K && ROUTE=route_sesibe.json OUT=$V/S4/route.json GSEG='{"蘂取|良宇仁": 0.025}' python3 devline_hybrid.py > /dev/null 2>&1); cd $V/S4; sesibe_calc route.json 0.025; touch done; fi
# 茂世路線（作図の線の線形は kp_before_moyoro）
moyoro_draw() { cp $K/../kp_before_moyoro/fit_moyoro.json .; cp $K/route_moyoro.json route.json; ROUTE=route.json python3 $K/fit2route.py moyoro > /dev/null; }
if ! done_ M1; then echo "== M1 作図の線・35‰（急行も 35‰）"; prep M1; moyoro_draw; cp $K/../kp_before_kyaku/design_fmoyoro.json $K/../kp_before_kyaku/design_fmoyoro_free.json .; touch done; fi
if ! done_ M2; then echo "== M2 作図の線・急行の区間 15‰"; prep M2; moyoro_draw; python3 $K/ground.py route_fmoyoro.json ground_fmoyoro.json > /dev/null; cp $K/../kp_before_moyoro/height_spec_moyoro*.json .
  for suf in _free ""; do KYAKU15_ADD='[["背祖曽","沼田"]]' KYAKU25_OFF=1 GCAP=0.035 python3 $K/design3.py ground_fmoyoro.json costs_single.json design_fmoyoro$suf.json height_spec_moyoro$suf.json > d$suf.log 2>&1; grep 最終 d$suf.log; grep 範囲外 d$suf.log || true; done; touch done; fi
if ! done_ M3; then echo "== M3 作図の線・急行の区間 25‰"; prep M3; moyoro_draw; cp $K/../kp_before_moyoro/design_fmoyoro.json $K/../kp_before_moyoro/design_fmoyoro_free.json .; touch done; fi
if ! done_ M4; then echo "== M4 作図に沿わせた線 1 回目（去家→背祖曽 35‰）"; prep M4; for f in fit_moyoro.json route_fmoyoro.json design_fmoyoro.json design_fmoyoro_free.json curvelist_fmoyoro.json; do cp $K/../kp_moyoro_v1/$f .; done; cp $K/../kp_moyoro_v1/route_moyoro_hyb_v1.json route.json; touch done; fi
# 蘂取線（紗那〜南留別）：線形は変えていない
if ! done_ R1; then echo "== R1 33‰（急行も 33‰）"; prep R1; cp $K/curvelist_fshibr.json $K/route_shibetoro_r.json .; cp $K/../kp_before_kyaku/design_fshibr.json $K/../kp_before_kyaku/design_fshibr_free.json .; touch done; fi
if ! done_ R2; then echo "== R2 急行の区間 15‰"; prep R2; cp $K/curvelist_fshibr.json $K/route_shibetoro_r.json $K/ground_fshibr.json $K/height_spec_shibr.json $K/height_spec_shibr_free.json .
  for suf in _free ""; do KYAKU15_ADD='[["沼田","南留別"]]' KYAKU25_OFF=1 GCAP=0.0333 python3 $K/design3.py ground_fshibr.json costs_single.json design_fshibr$suf.json height_spec_shibr$suf.json > d$suf.log 2>&1; grep 最終 d$suf.log; grep 範囲外 d$suf.log || true; done; touch done; fi
# 急行の性能（最終の線形で）
cd $K
for c in "K1|TRAIN=122" "K2|P_KW=1130 MASS_T=295 FMAX_KN=165 TRAIN=122" "K3|P_KW=2260 MASS_T=379 FMAX_KN=330 TRAIN=140"; do
  id=${c%%|*}; e=${c#*|}; mkdir -p $V/$id
  for v in "" gs; do env $e VMAX=95 TILT=0 python3 keito2.py sys_kyuko.json $v > $V/$id/k$v.log; head -1 $V/$id/k$v.log; cp "keito2_急行蘂取丹根萌${v:+_gs}.json" $V/$id/; done
done
sh run_kyuko.sh > /dev/null
echo 完了
