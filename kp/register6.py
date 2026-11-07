# 択捉の残り 6 路線の区間と系統を登録する（2026-11-06）。これまで登録はその場のコマンドで行っていた（記録に残らなかった）。以後はこの形で残す。
# 書き込む先：sys_*.json（系統の経路と停車駅）、network.json（区間・系統）、keito2.py（DESIGN・RANK）、run_systems.sh（走行の計算）、
# ../page/scripts/fiction_align.py（ページの区間と系統）。何度実行しても同じ結果（同じ id は書き換えない）
import json, re
SEC = [  # id, 名前, つながる区間と位置, 経路
    ('furu', '振別線（老門〜奧羅臼）', [('ipg', '始点（老門）')], 'route_furu.json'),
    ('atosa_w', '阿登佐線 西側（択捉神居古潭〜内保）', [('ipg', '始点（択捉神居古潭）')], 'route_atosa_w.json'),
    # 散布泊は両側の線が同じ側から入る駅（スイッチバック駅）なので 2 区間（単冠山口と同じ）。atosa_e2 はどの線にもつながらない（散布泊の高さは atosa_e1 に合わせる）
    ('atosa_e1', '阿登佐線 東側（択捉神居古潭〜散布泊）', [('ipg', '始点（択捉神居古潭）')], 'route_atosa_e1.json'),
    ('atosa_e2', '阿登佐線 東側（散布泊〜阿登佐岳）', [], 'route_atosa_e2.json'),
    ('noto', '野斗路線（振別〜賢萌〜野斗路）', [('ipg', '始点（振別）')], 'route_noto.json'),
    ('yorib', '寄別線（焼沼〜鬼門〜寄別）', [('otamoi', '始点（焼沼）')], 'route_yorib.json'),
    ('otoshi', '乙知志線（乙知志〜択捉原〜北乙）', [('moyoro', '始点（乙知志）')], 'route_otoshi.json'),
    ('moke', '萌消線（萌消〜満前）', [('ipg', '終点（満前）')], 'route_moke.json'),
]
SYS = [  # id, 名前, 系統のファイル, 区間, 車両, 両数, 長さ, VMAX, 経路, 停車駅, 注記
    ('futsu_furu', '普通 留別→奧羅臼', 'sys_futsu_furu.json', ['ipg', 'furu'], 'キハ40形', 4, 80, 85,
     [['ipg', 'st:留別', 'J:furu:start'], ['furu', 'start', 'end']], ['留別', '南留別', '宇遠知', '類平', '西内保別', '振別', '西振別', '老門', '奧羅臼'],
     'ダイヤ a.oud2 の普通（上下 16 本ずつ）。セーブの「振別線 普通（留別行）」キハ40形 4 両'),
    ('futsu_atosa', '普通 内保→阿登佐岳', 'sys_futsu_atosa.json', ['atosa_w', 'ipg', 'atosa_e1', 'atosa_e2'], 'キハ40形', 4, 80, 85,
     [['atosa_w', 'end', 'start'], ['ipg', 'J:atosa_w:start', 'J:atosa_e1:start'], ['atosa_e1', 'start', 'end'], ['atosa_e2', 'start', 'end']], ['内保', '択捉神居古潭', '散布泊', '阿登佐岳'],
     'ダイヤ a.oud2 の普通（上下 16 本ずつ）。セーブの「阿登佐線 普通」は 731系だが、線は非電化で車両指定の誤り（ユーザー、11-05）。隣の老門線の普通と同じキハ40形として扱う'),
    ('futsu_noto', '普通 野斗路→仲芭蕉', 'sys_futsu_noto.json', ['noto', 'ipg', 'sanroku_s'], 'キハ40形', 4, 80, 85,
     [['noto', 'end', 'start'], ['ipg', 'J:noto:start', 'J:sanroku_s:end'], ['sanroku_s', 'end', 'st:仲芭蕉']],
     ['野斗路', '賢萌', '振別', '西振別', '老門', '採神威', '長生内', '来季萌', '仲芭蕉'],
     'ダイヤ a.oud2 の普通（上下 15 本ずつ）。セーブの「野斗路線 山麓乗入」キハ40形 4 両（ユーザー、11-06：キハ40 の想定。出力の大小は考えていない）。車両の設定は低速。速度の区分は参考で、線路の規格が低めなので最高速度 85 km/h（ユーザー、11-06）'),
    ('futsu_yorib', '普通 小田萌→寄別', 'sys_futsu_yorib.json', ['otamoi', 'yorib'], 'キハ40形', 4, 80, 85,
     [['otamoi', 'st:小田萌', 'J:yorib:start'], ['yorib', 'start', 'end']], ['小田萌', '鞍掛', '礼文尻', '焼沼', '鬼門', '寄別'],
     'ダイヤ a.oud2 の普通（上下 17 本ずつ）。セーブの「寄別線 普通」キハ40形 4 両'),
    ('futsu_otoshi', '普通 蘂取→北乙', 'sys_futsu_otoshi.json', ['sesibe', 'moyoro', 'otoshi'], 'キハ40形', 4, 80, 85,
     [['sesibe', 'start', 'end'], ['moyoro', 'J:sesibe:end', 'J:otoshi:start'], ['otoshi', 'start', 'end']],
     ['蘂取', '良宇仁', '睡名', '長根', '天幕', '上去家', '背祖曽', '応仁萌', '四谷', '渡刈', '東留茶留', '乙知志', '択捉原', '北乙'],
     'ダイヤ a.oud2 の普通（上下 12 本ずつ。ほかに四谷〜北乙が 2 本ずつ）。乙知志線の名前の編成はセーブにない。背蘂線を通るので「背蘂線 普通」（キハ40形 4 両）として扱う'),
    ('futsu_moke', '普通 満前→萌消', 'sys_futsu_moke.json', ['ipg', 'moke'], 'キハ150形', 3, 60, 85,
     [['moke', 'end', 'start']], ['満前', '萌消'],
     'ダイヤ a.oud2 の普通（上下 8 本ずつ）。セーブの「萌消線 普通」キハ150形 3 両'),
]
N = json.load(open('network.json')); ids = [s['id'] for s in N['sections']]; sids = [y['id'] for y in N['systems']]
for i, name, par, route in SEC:
    if i in ids: continue
    N['sections'].append({'id': i, 'name': name, 'rank': 5, 'grade': '丙線', 'parents': [{'section': p, 'at': a} for p, a in par],
        'build': f'make_routes6.py → chain_new6.sh・chain_new6b.sh（阿登佐線 東側）（VMAX=85 TRAIN=80、GCAP=0.025）', 'conditions': {'VMAX': 85, 'TILT': 0}, 'costs': 'costs_single.json',
        'note': '低速の普通（気動車）だけが走る。非電化・単線（セーブ）。線形は 85 km/h 前提（単冠山麓線と同じ）。2026-11-06'})
for i, name, f, secs, car, n, L, vmax, pieces, stops, note in SYS:
    json.dump({'name': name.replace(' ', '').replace('→', ''), 'note': note, 'pieces': pieces, 'stops': stops}, open(f, 'w'), ensure_ascii=False, indent=1)
    if i in sids: continue
    N['systems'].append({'id': i, 'name': name, 'sections': secs, 'keito2': f, 'car': f'{car}相当 {n} 両（{L} m）', 'car_type': car, 'cars': n,
                         'VMAX': vmax, 'TILT': 0, 'TRAIN': L, 'car_source': note})
json.dump(N, open('network.json', 'w'), ensure_ascii=False, indent=1)
# keito2.py：DESIGN と RANK
k = open('keito2.py').read()
for i, *_ in SEC:
    if f"'{i}': ('design_f{i}_free.json'" not in k:
        k = re.sub(r"(DESIGN = \{.*?)(\}\n)", lambda m: m.group(1) + f",\n          '{i}': ('design_f{i}_free.json', 'design_f{i}.json')" + m.group(2), k, count=1, flags=re.S)
    if f"'{i}': 5" not in k:
        k = re.sub(r"(RANK = \{[^}]*)\}", lambda m: m.group(1) + f", '{i}': 5}}", k, count=1)
open('keito2.py', 'w').write(k)
# run_systems.sh
r = open('run_systems.sh').read()
for i, name, f, secs, car, n, L, vmax, *_ in SYS:
    if f not in r: r = r.replace('\ndone', f'\n  env $(python3 veh_env.py {car} {n}) VMAX={vmax} TILT=0 TRAIN={L} python3 keito2.py {f} $v\ndone', 1)
open('run_systems.sh', 'w').write(r)
# fiction_align.py：区間と系統
p = __import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'page', 'scripts', 'fiction_align.py'); a = open(p).read()
par = {'ipg': 'trunk', 'otamoi': 'otamoi', 'moyoro': 'moyoro'}
anchor = '    sections = [trunk, sanpu, shibw, shibr, moyoro, rakki, toshi, otamoi, sesibe, tanne, kuko, sanroku_n, sanroku_s]'
if anchor in a:
    add = ''.join(f'    {i} = sec_simple("{i}", "{name}", "{route}", [{", ".join(par[q] for q, _ in pr)}])\n' for i, name, pr, route in SEC)
    a = a.replace(anchor, '    # 択捉の残り 6 路線（2026-11-06、register6.py が書いた）\n' + add + anchor[:-1] + ', ' + ', '.join(i for i, *_ in SEC) + ']')
a = re.sub(r'(K2 = \([^)]*)\)', lambda m: m.group(1) + ''.join(f', "{i}"' for i, *_ in SYS if f'"{i}"' not in m.group(1)) + ')', a, count=1)
open(p, 'w').write(a)
print('登録した：区間', len(SEC), '系統', len(SYS))
