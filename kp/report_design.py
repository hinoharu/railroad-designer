#!/usr/bin/env python3
# 縦断の結果（design_f<id>.json）を、今回の規則の観点で機械的に調べる（2026-11-07、国後島）：
#   駅ごとの高さ（施工基面−地盤）と構造物、深さ 40 m 超の駅とその出口（200 m 以内に地盤が施工基面＋40 m まで下がる所）、
#   橋梁の区間ごとの最大の高さ（60 m 超・100 m 超）、最急勾配、トンネル・橋梁の延長
# 使い方：python3 report_design.py design_fminami.json [design_fkita_w.json ...]
import json, sys
import numpy as np
DEPTH_MAX, EXIT_R, BRIDGE_H1, BRIDGE_H2 = 40.0, 200.0, 60.0, 100.0
for f in sys.argv[1:]:
    d = json.load(open(f)); s = np.array(d['s']); g = np.array(d['ground'], float); z = np.array(d['z']); st = d['struct']
    ds = float(np.median(np.diff(s))); h = z - g   # 施工基面−地盤（＋高架、−地下）
    print(f'== {f}：長さ {s[-1]/1000:.1f} km、トンネル {st.count("T")*ds/1000:.1f} km、橋梁 {st.count("B")*ds/1000:.1f} km、最急勾配 {max(abs(np.diff(z))/np.diff(s))*1000:.1f}‰')
    print('  駅（高さ＝施工基面−地盤 m、構造物、深い駅の出口）')
    for name, c in d['stations']:
        i = int(np.argmin(np.abs(s - c))); hh = h[i]; kind = {'-': '土工', 'T': 'トンネル', 'B': '橋梁'}[st[i]]
        note = ''
        if hh < -DEPTH_MAX:
            near = (np.abs(s - c) <= EXIT_R); up = (g[near] - z[near]) <= DEPTH_MAX
            note = f'  ★深さ {-hh:.0f} m：' + (f'{EXIT_R:.0f} m 以内に深さ {DEPTH_MAX:.0f} m 以下の所あり（出口）' if up.any() else '出口なし')
        elif hh < -10: note = f'  （深さ {-hh:.0f} m）'
        elif hh > 12: note = f'  （高さ {hh:.0f} m）'
        print(f'    {name:8s} {hh:+6.1f} m {kind}{note}')
    # 橋梁の区間ごとの最大の高さ
    runs = []; i = 0
    while i < len(st):
        if st[i] == 'B':
            j = i
            while j < len(st) and st[j] == 'B': j += 1
            hm = h[i:j].max(); k = i + int(np.argmax(h[i:j]))
            over1 = int(np.sum(h[i:j] > BRIDGE_H1)) * ds; over2 = int(np.sum(h[i:j] > BRIDGE_H2)) * ds
            runs.append((s[i], s[j - 1], hm, over1, over2, k)); i = j
        else: i += 1
    hi = [r for r in runs if r[2] > BRIDGE_H1]
    print(f'  橋梁 {len(runs)} か所、最大の高さ {max(r[2] for r in runs) if runs else 0:.0f} m。{BRIDGE_H1:.0f} m 超 {len(hi)} か所、{BRIDGE_H2:.0f} m 超 {sum(1 for r in runs if r[2] > BRIDGE_H2)} か所')
    for a, b, hm, o1, o2, k in sorted(hi, key=lambda r: -r[2]):
        near = min(d['stations'], key=lambda x: abs(x[1] - s[k]))
        print(f'    {a/1000:.2f}〜{b/1000:.2f} km（{(b-a)/1000:.2f} km）最大 {hm:.0f} m、{BRIDGE_H1:.0f} m 超の長さ {o1:.0f} m、{BRIDGE_H2:.0f} m 超 {o2:.0f} m、最寄り駅 {near[0]}（{abs(near[1]-s[k])/1000:.1f} km）')
    # トンネルの最大の深さ
    tr = [(s[i], g[i] - z[i]) for i in range(len(st)) if st[i] == 'T']
    if tr: print(f'  トンネルの最大の深さ {max(t[1] for t in tr):.0f} m（{max(tr, key=lambda t: t[1])[0]/1000:.2f} km）')
