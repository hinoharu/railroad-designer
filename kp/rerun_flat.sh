#!/bin/sh
# 地平駅の定義（厳密・準地平）と山中の駅で、［全駅を地平駅に］の側を計算し直す（2026-11-04）。済んだ段は飛ばす（*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f flat_$n.done ] && return 0; "$@"; touch flat_$n.done; }
step 1 sh -c 'python3 design3.py ground_fipg.json costs_single.json design_fipgh_gs.json height_spec_ipgh_gs.json > d_ipgh_gs.log 2>&1'
step 2 python3 - <<'PY'
import json, numpy as np
ft = json.load(open('fit_ipg.json')); rt = json.load(open('route_fipg.json')); dt = json.load(open('design_fipgh_gs.json'))
for br, ends in (('sanpu', ('end',)), ('shibw', ('start', 'end'))):
    fb = json.load(open(f'fit_{br}.json')); sp = json.load(open(f'height_spec_{br}.json'))
    for w in ends:
        jj = fb['junctions'][w] if 'junctions' in fb else fb['junction']
        sj = float(np.interp(jj['s'], ft['s'], rt['s'])); sp[w + '_z'] = float(np.interp(sj, dt['s'], dt['z']))
    json.dump(sp, open(f'height_spec_{br}.json', 'w'), ensure_ascii=False); print(br, {k: round(v, 1) for k, v in sp.items() if k.endswith('_z')})
PY
step 3 sh -c 'GCAP=0.035 python3 design3.py ground_fsanpu.json costs_single.json design_fsanpu.json height_spec_sanpu.json > d_sanpu.log 2>&1'
step 4 sh -c 'python3 design3.py ground_fshibw.json costs_single.json design_fshibw.json height_spec_shibw.json > d_shibw.log 2>&1'
S="大岬・散布・散布渓・紗万部・南散布・乳萌・別飛仮乗降場・瀬石温泉・東紗那・紗那"
step 5 sh -c "VMAX=100 TILT=0 TRAIN=85 DB=design_fsanpu.json DT=design_fipgh_gs.json OUT=_gs python3 keito.py 普通大岬紗那 sanpu ipg 紗那 '$S' > k_gs.log"
rm -f flat_*.done
echo 完了
