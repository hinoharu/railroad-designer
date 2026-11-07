#!/bin/sh
# 地平駅の定義（厳密・準地平）と山中の駅で、［全駅を地平駅に］の側を計算し直す（2026-11-04）。済んだ段は飛ばす（*.done）
set -e
export W_FLAT_CUT=10 W_FLAT_UP=20
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f flatL_$n.done ] && return 0; "$@"; touch flatL_$n.done; }
step 1 sh -c 'python3 design3.py ground_fipg.json costs_single.json design_fipgh_gsL.json height_spec_ipgh_gs.json > d_ipgh_gsL.log 2>&1'
step 2 python3 - <<'PY'
import json, numpy as np
ft = json.load(open('fit_ipg.json')); rt = json.load(open('route_fipg.json')); dt = json.load(open('design_fipgh_gsL.json'))
for br, ends in (('sanpu', ('end',)), ('shibw', ('start', 'end'))):
    fb = json.load(open(f'fit_{br}.json')); sp = json.load(open(f'height_spec_{br}.json'))
    for w in ends:
        jj = fb['junctions'][w] if 'junctions' in fb else fb['junction']
        sj = float(np.interp(jj['s'], ft['s'], rt['s'])); sp[w + '_z'] = float(np.interp(sj, dt['s'], dt['z']))
    json.dump(sp, open(f'height_spec_{br}_L.json', 'w'), ensure_ascii=False); print(br, {k: round(v, 1) for k, v in sp.items() if k.endswith('_z')})
PY
step 3 sh -c 'GCAP=0.035 python3 design3.py ground_fsanpu.json costs_single.json design_fsanpu_L.json height_spec_sanpu_L.json > d_sanpu_L.log 2>&1'
step 4 sh -c 'python3 design3.py ground_fshibw.json costs_single.json design_fshibw_L.json height_spec_shibw_L.json > d_shibw_L.log 2>&1'
S="大岬・散布・散布渓・紗万部・南散布・乳萌・別飛仮乗降場・瀬石温泉・東紗那・紗那"
step 5 sh -c "VMAX=100 TILT=0 TRAIN=85 DB=design_fsanpu_L.json DT=design_fipgh_gsL.json OUT=_gsL python3 keito.py 普通大岬紗那 sanpu ipg 紗那 '$S' > k_gsL.log"
rm -f flatL_*.done
echo 完了
