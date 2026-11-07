#!/bin/sh
# 全線の縦断を、今の design3.py（最初の高さで指定を守る。2026-11-04）で上位の区間から順に計算し直す。分岐器の高さは上位の縦断に合わせ直す。
# 勾配の上限（GCAP）：特急の経路 25‰（乙線）、散布線 35‰（丙線）、蘂取線の 2 区間 33‰（乙線・電化：789系・719系だけが走る。ユーザーの了承）、
# 茂世路線 35‰（丙線）。済んだ段は飛ばす（all_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f all_$n.done ] && return 0; echo "== $n $(date +%H:%M)"; "$@"; touch all_$n.done; }
resync() { python3 - "$@" <<'PY'
import json, sys, numpy as np
B, PARENT, PROUTE, PFREE, PGS = sys.argv[1:6]
fb = json.load(open(f'fit_{B}.json')); fp = json.load(open(PARENT)); rp = json.load(open(PROUTE))
js = fb['junctions'] if 'junctions' in fb else {'end': fb['junction']}
for suf, pd in (('_free', PFREE), ('', PGS)):
    d = json.load(open(pd)); f = f'height_spec_{B}{suf}.json'; sp = json.load(open(f))
    for w, j in js.items():
        sj = float(np.interp(j['s'], fp['s'], rp['s'])); sp[w + '_z'] = float(np.interp(sj, d['s'], d['z']))
    json.dump(sp, open(f, 'w'), ensure_ascii=False)
    print(B, suf or '_gs', {k: round(v, 1) for k, v in sp.items() if k.endswith('_z')})
PY
}
D() { out=$1; shift; sh -c "$*" > $out 2>&1; grep -E "最終" $out; }
step 1 D d_ipgh.log python3 design3.py ground_fipg.json costs_single.json design_fipgh.json height_spec_ipg.json
step 2 D d_ipgh_gs.log python3 design3.py ground_fipg.json costs_single.json design_fipgh_gs.json height_spec_ipgh_gs.json
step 3 sh -c 'true'
resync sanpu fit_ipg.json route_fipg.json design_fipgh.json design_fipgh_gs.json
resync shibw fit_ipg.json route_fipg.json design_fipgh.json design_fipgh_gs.json
resync shibr fit_ipg.json route_fipg.json design_fipgh.json design_fipgh_gs.json
step 4 D d_sanpu_free.log GCAP=0.035 python3 design3.py ground_fsanpu.json costs_single.json design_fsanpu_free.json height_spec_sanpu_free.json
step 5 D d_sanpu.log GCAP=0.035 python3 design3.py ground_fsanpu.json costs_single.json design_fsanpu.json height_spec_sanpu.json
step 6 D d_shibw_free.log GCAP=0.0333 python3 design3.py ground_fshibw.json costs_single.json design_fshibw_free.json height_spec_shibw_free.json
step 7 D d_shibw.log GCAP=0.0333 python3 design3.py ground_fshibw.json costs_single.json design_fshibw.json height_spec_shibw.json
step 8 D d_shibr_free.log GCAP=0.0333 python3 design3.py ground_fshibr.json costs_single.json design_fshibr_free.json height_spec_shibr_free.json
step 9 D d_shibr.log GCAP=0.0333 python3 design3.py ground_fshibr.json costs_single.json design_fshibr.json height_spec_shibr.json
resync moyoro fit_shibr.json route_fshibr.json design_fshibr_free.json design_fshibr.json
step 10 D d_moyoro_free.log GCAP=0.035 python3 design3.py ground_fmoyoro.json costs_single.json design_fmoyoro_free.json height_spec_moyoro_free.json
step 11 D d_moyoro.log GCAP=0.035 python3 design3.py ground_fmoyoro.json costs_single.json design_fmoyoro.json height_spec_moyoro.json
S="大岬・散布・散布渓・紗万部・南散布・乳萌・別飛仮乗降場・瀬石温泉・東紗那・紗那"
step 12 sh -c "VMAX=100 TILT=0 TRAIN=85 DB=design_fsanpu_free.json DT=design_fipgh.json OUT=_free python3 keito.py 普通大岬紗那 sanpu ipg 紗那 '$S' > k_free.log && VMAX=100 TILT=0 TRAIN=85 DB=design_fsanpu.json DT=design_fipgh_gs.json OUT=_gs python3 keito.py 普通大岬紗那 sanpu ipg 紗那 '$S' > k_gs.log"
step 13 sh run_systems.sh
echo 完了
