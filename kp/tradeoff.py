import json
S=json.load(open('summary.json'))
W,H=1100,640; L,R,T,B=90,40,70,90; pw,ph=W-L-R,H-T-B
x0,x1,y0,y1=0,55,148,172
X=lambda v:L+(v-x0)/(x1-x0)*pw; Y=lambda v:T+ph-(v-y0)/(y1-y0)*ph
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="WenQuanYi Zen Hei" font-size="15"><rect width="{W}" height="{H}" fill="#fff"/>',
   f'<text x="{L}" y="32" font-size="20" font-weight="bold">蘂取→兵至平の特急：元の線からのずれと所要時間</text>',
   f'<text x="{L}" y="54" font-size="14" fill="#555">左下ほど良い（元の線に近く、速い）。所要時間は停車駅の前後 110 m を分岐器で 45 km/h とした値</text>']
for v in range(0,56,10):
    o.append(f'<line x1="{X(v)}" y1="{T}" x2="{X(v)}" y2="{T+ph}" stroke="#eee"/><text x="{X(v)}" y="{T+ph+20}" text-anchor="middle">{v}</text>')
for v in range(148,173,4):
    o.append(f'<line x1="{L}" y1="{Y(v)}" x2="{L+pw}" y2="{Y(v)}" stroke="#eee"/><text x="{L-8}" y="{Y(v)+5}" text-anchor="end">{v}</text>')
o.append(f'<rect x="{L}" y="{T}" width="{pw}" height="{ph}" fill="none" stroke="#999"/>')
o.append(f'<text x="{L+pw/2}" y="{H-40}" text-anchor="middle">ずれ（元の折れ線の点の 95% が収まる距離、m）</text>')
o.append(f'<text transform="translate(28,{T+ph/2}) rotate(-90)" text-anchor="middle">所要時間（分）</text>')
# 最適化の系列を線で結ぶ
opt=[s for s in S if s['name'].startswith('最適化') and 'D 30' in s['name']]
o.append('<polyline points="'+' '.join(f"{X(s['p95']):.1f},{Y(s['min']):.1f}" for s in opt)+'" fill="none" stroke="#d62728" stroke-width="2"/>')
col=lambda s:'#1f5fa8' if not s['name'].startswith('最適化') else ('#e6862a' if 'D 60' in s['name'] else '#d62728')
off={'前の書き方（交点で角を削る）':(-10,24,'end'),'新しい書き方（交点を外へ動かす）':(-10,-12,'end'),'最適化 重み 100,000・D 60 m':(-10,20,'end')}
for s in S:
    cx,cy=X(s['p95']),Y(s['min']); dx,dy,an=off.get(s['name'],(12,5,'start'))
    o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{col(s)}" stroke="#fff" stroke-width="2"/>')
    o.append(f'<text x="{cx+dx:.1f}" y="{cy+dy:.1f}" text-anchor="{an}" font-size="14">{s["name"]}：{s["min"]:.1f} 分・最大 {s["max"]:.0f} m</text>')
o.append(f'<text x="{L}" y="{H-12}" font-size="13" fill="#555">赤の線：ずれの上限 D = 30 m で走行時間の重みを 0 → 3,000 → 30,000 → 100,000 と強めた順。橙：D = 60 m。青：交点を使う従来の 2 案</text>')
open('tradeoff.svg','w').write('\n'.join(o)+'</svg>')
