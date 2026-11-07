# 入力表（sections.json）の初版を、今あるファイルとつなぎのスクリプト（chain_*.sh・rerun_*.sh）から作る（2026-11-06、⑤の段 1）。
# 一度だけ使う。以後は sections.json が正本で、人が直す。値の出どころは各項目の src に書く
import json, os
N = json.load(open('network.json'))
# つなぎのスクリプトから読み取った値（最後に実行されたもの）。route：経路のファイル（駅の並びは中の stops）、hybrid：地形からの探索、
# trunk：ipfit_branch.py の位置引数の幹線、ends：端ごとの接続（'' は幹線の線、区間名はその線、なし）、free：どの線にもつながらない
H = {
 'shibw':    dict(route='route_shibetoro_w.json', trunk='ipg', ends={'start': '', 'end': ''}, run=(130, 0, 170), gcap=0.0333, src='network.json の build、rerun_all.sh'),
 'shibr':    dict(route='route_shibetoro_r.json', trunk='ipg', ends={'start': '', 'end': ''}, run=(130, 0, 170), gcap=0.0333, src='chain_new.sh・rerun_all.sh'),
 'moyoro':   dict(route='route_moyoro.json', trunk='shibr', ends={'end': ''}, run=(130, 0, 170), gcap=0.035, src='chain_new.sh・rerun_all.sh'),
 'rakki':    dict(route='route_rakkibetsu.json', trunk='ipg', ends={'end': ''}, run=(130, 1, 160), gcap=0.025, src='rerun_tilt.sh'),
 'toshi':    dict(route='route_toshiruri.json', trunk='ipg', ends={'start': 'moyoro', 'end': 'ipg'}, run=(130, 1, 160), gcap=0.025, src='rerun_tilt.sh'),
 'otamoi':   dict(route='route_otamoi.json', trunk='ipg', ends={'start': 'shibw', 'end': 'moyoro'}, run=(130, 1, 160), gcap=0.025, src='rerun_tilt.sh'),
 'sesibe':   dict(route='route_sesibe.json', trunk='ipg', ends={'start': 'ipg', 'end': 'moyoro'}, run=(95, 0, 122), gcap=0.025, src='chain_new3.sh'),
 'tanne':    dict(route='route_tanne.json', trunk='ipg', ends={'start': ''}, run=(95, 0, 122), gcap=0.025, src='chain_new3.sh'),
 'kuko':     dict(route='route_kuko.json', trunk='ipg', ends={'start': 'shibw'}, run=(110, 0, 120), gcap=0.0333, kyaku25=[['択捉空港', '植別']], src='chain_new5.sh'),
 'sanroku_n': dict(route='route_sanroku_n.json', hybrid=dict(GDEF=0.025, GMAP={'入里節|特掟': 0.0333}, PREFIX='sr_'), trunk='shibw', ends={'start': 'shibw'}, run=(85, 0, 80), gcap=0.0333, kyaku25=[['特掟', '単冠山口']], src='chain_sanroku3.sh'),
 'sanroku_s': dict(route='route_sanroku_s.json', hybrid=dict(GDEF=0.025, PREFIX='sr_'), trunk='ipg', ends={'end': 'ipg'}, run=(85, 0, 80), gcap=0.025, start_z_from='sanroku_n', src='chain_sanroku3.sh'),
}
for b, t, e in (('furu', 'ipg', {'start': 'ipg'}), ('atosa_w', 'ipg', {'start': 'ipg'}), ('atosa_e1', 'ipg', {'start': 'ipg'}), ('noto', 'ipg', {'start': 'ipg'}),
                ('yorib', 'otamoi', {'start': 'otamoi'}), ('otoshi', 'moyoro', {'start': 'moyoro'}), ('moke', 'ipg', {'end': 'ipg'})):
    H[b] = dict(route=f'route_{b}.json', turnback=True, trunk=t, ends=e, run=(85, 0, 80), gcap=0.025, src='make_routes6.py・chain_new6.sh・chain_new6b.sh')
H['atosa_e2'] = dict(route='route_atosa_e2.json', turnback=True, trunk='ipg', ends={}, free=True, run=(85, 0, 80), gcap=0.025, start_z_from='atosa_e1', src='make_routes6.py・chain_new6b.sh')
LEGACY = {
 'ipg': '特急の経路。交点法（ipfit_all.py、pipe3.sh・rerun_ip.sh）。縦断は design3.py ground_fipg.json costs_single.json に height_spec_ipg.json（高さ指定なし側）と height_spec_ipgh_gs.json（駅地平化）。湿地は wetland.py（rerun_all.sh の 1・2）',
 'sanpu': '散布線。古い手順（rerun_branch.sh：ipfit_branch.py の位置引数だけ、端の高さは rerun_all.sh の resync、GCAP=0.035、系統は keito.py）',
}
out = []
for s in N['sections']:
    b = s['id']; r = dict(id=b, name=s['name'], rank=s['rank'], grade=s.get('grade'), parents=s['parents'])
    if b in LEGACY:
        r['method'] = 'legacy'; r['legacy'] = LEGACY[b]; out.append(r); continue
    h = H[b]; route = json.load(open(h['route']))
    r['method'] = 'branch'
    r['route'] = dict(stops=route['stops'], file=h['route'], turnback=h.get('turnback', False))
    if 'hybrid' in h: r['route']['hybrid'] = h['hybrid']
    r['fit'] = dict(trunk=h['trunk'], ends=h['ends'], free=h.get('free', False))
    r['run'] = dict(VMAX=h['run'][0], TILT=h['run'][1], TRAIN=h['run'][2])
    pf = dict(GCAP=h['gcap'], costs='single')
    if 'kyaku25' in h: pf['KYAKU25_ADD'] = h['kyaku25']
    if 'start_z_from' in h: pf['start_z_from'] = h['start_z_from']
    # 高さの指定：今のファイルと「全駅を地平、上位の線につながる端の駅を除く」の規則との差を例外として書く
    rr = h['route'].replace('.json', '_hyb.json') if 'hybrid' in h else h['route']
    st = [n for n, _ in json.load(open(rr))['stations']]
    joined = [st[0] if w == 'start' else st[-1] for w in h['ends']] + ([st[0]] if 'start_z_from' in h else [])
    for suf, key in (('_free', 'free'), ('', 'gs')):
        sp = json.load(open(f'height_spec_{b}{suf}.json'))
        rule = {} if key == 'free' else {n: '地平' for n in st if n not in joined}
        act = sp.get('stations', {}) if (key == 'gs' or 'stations' in sp) else {}
        exc = {n: v for n, v in act.items() if rule.get(n) != v}
        exc.update({n: '指定なし' for n in rule if n not in act})
        pf['double'] = sp.get('double', [])
        if exc: pf.setdefault('stations', {})[key] = exc
        extra = sorted(set(sp) - {'note', 'note_start', 'double', 'stations', 'start_z', 'end_z'})
        if extra: pf.setdefault('other_keys', {})[key] = extra
    r['profile'] = pf; r['src'] = h['src']; out.append(r)
json.dump({'note': '区間の表（⑤の段 1、2026-11-06）。人が決める値の正本。説明は README.md', 'sections': out}, open('tables/sections.json', 'w'), ensure_ascii=False, indent=1)
for r in out:
    p = r.get('profile', {}); print(r['id'], r['method'], p.get('stations'), p.get('other_keys'), p.get('double'))
