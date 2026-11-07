#!/bin/sh
# 蘂取線 紗那〜南留別（shibr）と茂世路線（moyoro）：平面 → キロ程 → 地盤 → 縦断（高さ指定なし・駅地平化）（2026-11-04）。済んだ段は飛ばす（new_*.done）
set -e
cd "$(dirname "$0")"
step() { n=$1; shift; [ -f new_$n.done ] && return 0; echo "== $n"; "$@"; touch new_$n.done; }
# 1. shibr の平面（ipfit_branch は別に起動済み。終わるのを待つ）
while pgrep -f "ipfit_branch.py shibr" >/dev/null; do sleep 20; done
grep -q "^shibr：" ipb_shibr.log
step 2 sh -c 'ROUTE=route_shibetoro_r.json python3 fit2route.py shibr && python3 ground.py route_fshibr.json ground_fshibr.json'
# 高さの指定：両端を幹線の縦断に合わせる（高さ指定なしは design_fipgh、駅地平化は design_fipgh_gs）。複線は沼田〜南留別
mkspec() { python3 - "$@" <<'PY'
import json, sys, numpy as np
B, PARENT, PROUTE, PFREE, PGS, DBL, STN = sys.argv[1:8]
fb = json.load(open(f'fit_{B}.json')); fp = json.load(open(PARENT)); rp = json.load(open(PROUTE))
route = json.load(open({'shibr': 'route_shibetoro_r.json', 'moyoro': 'route_moyoro.json'}[B]))
ends = [n for n, _ in route['stations']]
dbl = [DBL.split('〜')] if DBL else []
for suf, pd in (('_free', PFREE), ('', PGS)):
    d = json.load(open(pd)); sp = {'note': '両端（分岐器の位置）の施工基面を上位の線の縦断に合わせる（2026-11-04）', 'double': dbl}
    for w, j in fb['junctions'].items():
        sj = float(np.interp(j['s'], fp['s'], rp['s'])); sp[w + '_z'] = float(np.interp(sj, d['s'], d['z']))
    if suf == '': sp['stations'] = {n: '地平' for n in ends if n not in STN.split('・')}
    # 個別に高さを指定した駅（ユーザーの指定）：FIX の駅を地平 [-2, 2] に。駅地平化の地平駅より優先して守る（2026-11-04：沼田）
    for n in filter(None, __import__('os').environ.get('FIX', '').split('・')):
        sp.setdefault('stations', {})[n] = [-2, 2]
    json.dump(sp, open(f'height_spec_{B}{suf}.json', 'w'), ensure_ascii=False)
    print(B, suf or '_gs', {k: round(v, 1) for k, v in sp.items() if k.endswith('_z')}, len(sp.get('stations', {})), '駅を地平')
PY
}
step 3 env FIX=沼田 sh -c 'true' && FIX=沼田 mkspec shibr fit_ipg.json route_fipg.json design_fipgh.json design_fipgh_gs.json 沼田〜南留別 紗那・南留別
step 4 sh -c 'python3 design3.py ground_fshibr.json costs_single.json design_fshibr_free.json height_spec_shibr_free.json > d_shibr_free.log 2>&1'
step 5 sh -c 'python3 design3.py ground_fshibr.json costs_single.json design_fshibr.json height_spec_shibr.json > d_shibr.log 2>&1'
# 6. 茂世路線：沼田で蘂取線（shibr）につながる。特急 茂世路→択捉六甲（789系 8 両）の条件
step 6 sh -c 'VMAX=130 TILT=0 TRAIN=170 python3 ipfit_branch.py moyoro route_moyoro.json fit_shibr.json end > ipb_moyoro.log 2>&1'
step 7 sh -c 'ROUTE=route_moyoro.json python3 fit2route.py moyoro && python3 ground.py route_fmoyoro.json ground_fmoyoro.json'
step 8 mkspec moyoro fit_shibr.json route_fshibr.json design_fshibr_free.json design_fshibr.json 背祖曽〜沼田 沼田
step 9 sh -c 'GCAP=0.035 python3 design3.py ground_fmoyoro.json costs_single.json design_fmoyoro_free.json height_spec_moyoro_free.json > d_moyoro_free.log 2>&1'
step 10 sh -c 'GCAP=0.035 python3 design3.py ground_fmoyoro.json costs_single.json design_fmoyoro.json height_spec_moyoro.json > d_moyoro.log 2>&1'
for f in d_shibr_free d_shibr d_moyoro_free d_moyoro; do echo "== $f"; grep -E "複線の区間|最終|範囲外" $f.log || true; done
echo 完了
