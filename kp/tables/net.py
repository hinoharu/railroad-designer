# 入力表（tables/sections.json・systems.json）を読む共通の部品（2026-11-06、⑤の段 2）。build.py・keito2.py が使う
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
def load(name): return json.load(open(os.path.join(HERE, name)))
SECTIONS = load('sections.json')['sections']; SEC = {s['id']: s for s in SECTIONS}
SYSTEMS = load('systems.json')['systems']
# 古い手順の区間の縦断のファイル（高さ指定なし、駅地平化）。ほかの区間は design_f<id>_free.json・design_f<id>.json
LEGACY_DESIGN = {'ipg': ('design_fipgh.json', 'design_fipgh_gs.json'), 'sanpu': ('design_fsanpu_free.json', 'design_fsanpu.json')}
def design_files(i):
    """（高さ指定なし、駅地平化）の縦断のファイル。profile.only_gs の区間は高さ指定なしを作らないので、両方とも駅地平化のファイル（2026-11-07、国後島）"""
    if i in LEGACY_DESIGN: return LEGACY_DESIGN[i]
    if SEC[i]['profile'].get('only_gs'): return (f'design_f{i}.json', f'design_f{i}.json')
    return (f'design_f{i}_free.json', f'design_f{i}.json')
DESIGN = {s['id']: design_files(s['id']) for s in SECTIONS}
RANK = {s['id']: s['rank'] for s in SECTIONS}
def deps(s):
    """区間 s の計算に使う上位の区間（線形の幹線、端の接続先、施工基面を合わせる区間）"""
    if s['method'] != 'branch': return []
    f = s['fit']; d = [] if f.get('free') else [f['trunk']]
    d += [v or f['trunk'] for v in f['ends'].values()]
    if 'start_z_from' in s['profile']: d.append(s['profile']['start_z_from'])
    return sorted(set(d))
