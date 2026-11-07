# 高さの指定の両端の施工基面（start_z・end_z）を、つながる上位の線の縦断に合わせ直す（端ごとに上位の線を fit の junctions[w].trunk から読む）。
# 指定のファイルがなければ作る（駅地平化の側は、端の駅以外を地平に）。ほかの指定（個別の駅・複線）はそのまま。2026-11-05
import json, sys, os, numpy as np
B, ROUTE = sys.argv[1:3]
DES = {'ipg': ('design_fipgh.json', 'design_fipgh_gs.json'), 'shibw': ('design_fshibw_free.json', 'design_fshibw.json'),
       'moyoro': ('design_fmoyoro_free.json', 'design_fmoyoro.json'), 'shibr': ('design_fshibr_free.json', 'design_fshibr.json'),
       'otamoi': ('design_fotamoi_free.json', 'design_fotamoi.json')}   # 寄別線が小田萌線から分かれる（2026-11-06）
fb = json.load(open(f'fit_{B}.json')); js = fb['junctions'] if 'junctions' in fb else {'end': fb['junction']}
st = [n for n, _ in json.load(open(ROUTE))['stations']]; ends = {'start': st[0], 'end': st[-1]}
for k, suf in ((0, '_free'), (1, '')):
    f = f'height_spec_{B}{suf}.json'
    sp = json.load(open(f)) if os.path.exists(f) else {'note': '端（分岐器の位置）の施工基面を、つながる上位の線の縦断に合わせる', 'double': []}
    if k == 1 and 'stations' not in sp: sp['stations'] = {n: '地平' for n in st if n not in [ends[w] for w in js]}
    for w, j in js.items():
        sec = j['trunk'][4:-5]; fp = json.load(open(f'fit_{sec}.json')); rp = json.load(open(f'route_f{sec}.json')); d = json.load(open(DES[sec][k]))
        sj = float(np.interp(j['s'], fp['s'], rp['s'])); sp[w + '_z'] = float(np.interp(sj, d['s'], d['z']))
    json.dump(sp, open(f, 'w'), ensure_ascii=False)
    print(B, suf or '_gs', {w: round(sp[w + '_z'], 1) for w in js})
