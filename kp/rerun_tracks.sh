#!/bin/sh
# 複線・単線を区間ごとに使い分けて、縦断と系統を計算し直す（2026-11-04）
set -e
cd "$(dirname "$0")"
python3 design3.py ground_fipg.json costs_single.json design_fipgh.json height_spec_ipg.json > d_ipgh.log 2>&1
python3 design3.py ground_fipg.json costs_single.json design_fipgh_gs.json height_spec_ipgh_gs.json > d_ipgh_gs.log 2>&1
# 支線の両端の高さ：地平の指定なしの支線はいまの幹線（design_fipgh）、ありの支線は全駅地平の幹線（design_fipgh_gs）に合わせる
python3 - <<'PY'
import json, numpy as np
ft = json.load(open('fit_ipg.json')); rt = json.load(open('route_fipg.json'))
for br, ends in (('sanpu', ('end',)), ('shibw', ('start', 'end'))):
    fb = json.load(open(f'fit_{br}.json'))
    for suf, trunk in (('_free', 'design_fipgh.json'), ('', 'design_fipgh_gs.json')):
        dt = json.load(open(trunk)); sp = json.load(open(f'height_spec_{br}{suf}.json'))
        for w in ends:
            jj = fb['junctions'][w] if 'junctions' in fb else fb['junction']
            sj = float(np.interp(jj['s'], ft['s'], rt['s'])); sp[w + '_z'] = float(np.interp(sj, dt['s'], dt['z']))
        json.dump(sp, open(f'height_spec_{br}{suf}.json', 'w'), ensure_ascii=False)
        print(br, suf or '_gs', {k: round(v, 1) for k, v in sp.items() if k.endswith('_z')})
PY
GCAP=0.035 python3 design3.py ground_fsanpu.json costs_single.json design_fsanpu_free.json height_spec_sanpu_free.json > d_sanpu_free.log 2>&1
GCAP=0.035 python3 design3.py ground_fsanpu.json costs_single.json design_fsanpu.json height_spec_sanpu.json > d_sanpu.log 2>&1
python3 design3.py ground_fshibw.json costs_single.json design_fshibw_free.json height_spec_shibw_free.json > d_shibw_free.log 2>&1
python3 design3.py ground_fshibw.json costs_single.json design_fshibw.json height_spec_shibw.json > d_shibw.log 2>&1
S="大岬・散布・散布渓・紗万部・南散布・乳萌・別飛仮乗降場・瀬石温泉・東紗那・紗那"
VMAX=100 TILT=0 TRAIN=85 DB=design_fsanpu_free.json DT=design_fipgh.json OUT=_free python3 keito.py 普通大岬紗那 sanpu ipg 紗那 "$S" > k_free.log
VMAX=100 TILT=0 TRAIN=85 DB=design_fsanpu.json DT=design_fipgh_gs.json OUT=_gs python3 keito.py 普通大岬紗那 sanpu ipg 紗那 "$S" > k_gs.log
for f in d_ipgh d_ipgh_gs d_sanpu_free d_sanpu d_shibw_free d_shibw; do echo "== $f"; grep -E "複線の区間|最終" $f.log; done
echo 完了
