# 線路網の表（network.json）から、区間 X を直したときに計算し直す区間と系統を、順位の順に出す（2026-11-04）
# 使い方：python3 order.py 区間の id
import json, sys
N = json.load(open('network.json')); S = {s['id']: s for s in N['sections']}
for s in N['sections']:
    for p in s['parents']:
        if S[p['section']]['rank'] >= s['rank']: raise SystemExit(f"順位の誤り：{s['id']} が順位の同じか低い {p['section']} に合わせている")
todo = {sys.argv[1]}; changed = True
while changed:
    changed = False
    for s in N['sections']:
        if s['id'] not in todo and any(p['section'] in todo for p in s['parents']): todo.add(s['id']); changed = True
for s in sorted((S[i] for i in todo), key=lambda s: s['rank']): print('区間', s['rank'], s['id'], s['name'], '：', s['build'])
for k in N['systems']:
    if todo & set(k['sections']): print('系統', k['id'], k['name'])
