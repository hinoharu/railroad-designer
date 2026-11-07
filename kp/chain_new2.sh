#!/bin/sh
# 酪別線（rakki）・冬知里支線（toshi）・小田萌線（otamoi）：平面 → キロ程 → 地盤 → 縦断（高さ指定なし・駅地平化）（2026-11-04）。
# 特急 酪別→年萌（789系 8 両）の条件。3 線とも単線（セーブ）、電化なので勾配の上限 33‰。済んだ段は飛ばす（n2_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f n2_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch n2_$n.done; }
C="VMAX=130 TILT=0 TRAIN=170"
step 1 sh -c "$C python3 ipfit_branch.py rakki route_rakkibetsu.json fit_ipg.json end > ipb_rakki.log 2>&1"
step 2 sh -c "$C python3 ipfit_branch.py toshi route_toshiruri.json fit_ipg.json start=fit_moyoro.json end=fit_ipg.json > ipb_toshi.log 2>&1"
step 3 sh -c "$C python3 ipfit_branch.py otamoi route_otamoi.json fit_ipg.json start=fit_shibw.json end=fit_moyoro.json > ipb_otamoi.log 2>&1"
for B in rakki:route_rakkibetsu.json toshi:route_toshiruri.json otamoi:route_otamoi.json; do
  b=${B%%:*}; r=${B#*:}
  step g_$b sh -c "ROUTE=$r python3 fit2route.py $b && python3 ground.py route_f$b.json ground_f$b.json"
done
# 高さの指定：端ごとに、つながる上位の線の縦断に合わせる（高さ指定なしは上位の高さ指定なし、駅地平化は上位の駅地平化）。端の駅（上位の線の駅）以外は駅地平化で地平
spec() { python3 - "$1" "$2" <<'PY'
import json, sys, numpy as np
B, ROUTE = sys.argv[1:3]
DES = {'ipg': ('design_fipgh.json', 'design_fipgh_gs.json'), 'shibw': ('design_fshibw_free.json', 'design_fshibw.json'),
       'moyoro': ('design_fmoyoro_free.json', 'design_fmoyoro.json'), 'shibr': ('design_fshibr_free.json', 'design_fshibr.json')}
fb = json.load(open(f'fit_{B}.json')); js = fb['junctions']
st = [n for n, _ in json.load(open(ROUTE))['stations']]
ends = {'start': st[0], 'end': st[-1]}
for k, suf in ((0, '_free'), (1, '')):
    sp = {'note': '端（分岐器の位置）の施工基面を、つながる上位の線の縦断に合わせる（2026-11-04）', 'double': []}
    for w, j in js.items():
        sec = j['trunk'][4:-5]; fp = json.load(open(f'fit_{sec}.json')); rp = json.load(open(f'route_f{sec}.json')); d = json.load(open(DES[sec][k]))
        sj = float(np.interp(j['s'], fp['s'], rp['s'])); sp[w + '_z'] = float(np.interp(sj, d['s'], d['z']))
    if k == 1: sp['stations'] = {n: '地平' for n in st if n not in [ends[w] for w in js]}
    json.dump(sp, open(f'height_spec_{B}{suf}.json', 'w'), ensure_ascii=False)
    print(B, suf or '_gs', {w: round(sp[w + '_z'], 1) for w in js}, len(sp.get('stations', {})), '駅を地平')
PY
}
for B in rakki:route_rakkibetsu.json toshi:route_toshiruri.json otamoi:route_otamoi.json; do
  b=${B%%:*}; r=${B#*:}
  step s_$b spec $b $r
  step df_$b sh -c "GCAP=0.0333 python3 design3.py ground_f$b.json costs_single.json design_f${b}_free.json height_spec_${b}_free.json > d_${b}_free.log 2>&1"
  step dg_$b sh -c "GCAP=0.0333 python3 design3.py ground_f$b.json costs_single.json design_f$b.json height_spec_$b.json > d_$b.log 2>&1"
done
for f in ipb_rakki ipb_toshi ipb_otamoi; do echo "== $f"; grep -v "^  start\|^  end" $f.log | tail -12; done
for f in d_rakki_free d_rakki d_toshi_free d_toshi d_otamoi_free d_otamoi; do echo "== $f"; grep -E "最終|範囲外|施工基面" $f.log || true; done
echo 完了
