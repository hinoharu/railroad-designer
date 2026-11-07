# 系統（2026-11-04、ユーザーと決めた「まず線形ありき」）：線形の区間をつないだ経路を、系統の車両の条件で走らせる。
# いまは「支線の全部 → 幹線の分岐器の位置から終点の駅まで」の形だけ（普通 大岬→紗那）。
# 使い方：VMAX=100 TILT=0 TRAIN=40 python3 keito.py 系統名 支線の名前 幹線の名前 終点の駅 停車駅（・区切り）
#   支線：fit_<支線>.json（junction）・design_f<支線>.json・curves_f<支線>.json
#   幹線：fit_<幹線>.json・route_f<幹線>.json・design_f<幹線>h.json・curves_f<幹線>h.json
import json, sys
import numpy as np
import run
NAME, BR, TR, END = sys.argv[1:5]; STOPS = sys.argv[5].split('・')
import os
# 縦断のファイルは環境変数で替えられる（駅の高さの指定のあり・なしを比べるため、2026-11-04）：DB 支線、DT 幹線、OUT 出力の名前に付ける語
DB = os.environ.get('DB', f'design_f{BR}.json'); DT = os.environ.get('DT', f'design_f{TR}h.json'); SUF = os.environ.get('OUT', '')
fb = json.load(open(f'fit_{BR}.json')); db = json.load(open(DB)); cb = json.load(open(f'curves_f{BR}.json'))
ft = json.load(open(f'fit_{TR}.json')); rt = json.load(open(f'route_f{TR}.json'))
dt = json.load(open(DT)); ct = json.load(open(f'curves_f{TR}h.json'))
# 分岐器の位置：幹線の平面のキロ程 → 地球上のキロ程（縦断と同じ）
sj = float(np.interp(fb['junction']['s'], ft['s'], rt['s']))
st_t = dict(dt['stations']); se = st_t[END]
Lb = db['s'][-1]
# 縦断：支線の全部と、幹線の sj〜終点の駅
sb, zb = np.array(db['s']), np.array(db['z']); s_t, z_t = np.array(dt['s']), np.array(dt['z'])
m = (s_t > sj) & (s_t <= se)
s = np.concatenate([sb, Lb + s_t[m] - sj]); z = np.concatenate([zb, z_t[m]])
# 分岐器の位置の高さの差（縦断の設計で支線の端を幹線に合わせたかの確認）
print(f'{NAME}：支線 {Lb / 1000:.2f} km ＋ 幹線 {(se - sj) / 1000:.2f} km（分岐器の位置 {sj:.0f} m、高さの差 {zb[-1] - float(np.interp(sj, s_t, z_t)):+.2f} m）')
# 駅：支線の駅のうち幹線の区間にない駅と、幹線の sj〜終点の駅
names_t = [(n, c) for n, c in dt['stations'] if sj < c <= se + 0.5]
stations = [(n, c) for n, c in db['stations'] if n not in dict(names_t) and c < Lb - 1] + [(n, Lb + c - sj) for n, c in names_t]
miss = [n for n in STOPS if n not in dict(stations)]
if miss: raise SystemExit(f'停車駅が経路にない：{miss}')
# 曲線（制限速度の区間）：支線と、幹線の sj〜終点を切り出してずらす
cv = [dict(c) for c in cb] + [dict(c, s0=Lb + max(c['s0'], sj) - sj, s1=Lb + min(c['s1'], se) - sj) for c in ct if c['s1'] > sj and c['s0'] < se]
d = {'s': s.tolist(), 'z': z.tolist(), 'stations': stations, 'stops': STOPS}
x, v, t, si, stops, vh = run.simulate(d, True, cv)
legs = [t[b] - t[a] for a, b in zip(si, si[1:])]
print(f'  走行 {sum(legs) / 60:.1f} 分（停車を除く）、最高 {v.max() * 3.6:.0f} km/h')
for (a, b), L_ in zip(zip(STOPS, STOPS[1:]), legs): print(f'    {a}→{b} {L_ / 60:.1f} 分')
json.dump({'name': NAME, 'branch': BR, 'trunk': TR, 'sj': sj, 'Lb': Lb, 's': s.tolist(), 'z': z.tolist(), 'stations': stations, 'stops': STOPS,
           'x': x.tolist(), 'v': (v * 3.6).tolist(), 'lim': (vh * 3.6).tolist(), 'zone': (run.simulate.vl * 3.6).tolist(), 'run_min': sum(legs) / 60},
          open(f'keito_{NAME}{SUF}.json', 'w'), ensure_ascii=False)
