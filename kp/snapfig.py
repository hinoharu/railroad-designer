# 繰り返しごとの線形の推移の図（平面図・曲率図・規則の比）。python3 snapfig.py snap.json 出力.svg 題名 km0 km1
import json,sys,math
import numpy as np
d=json.load(open(sys.argv[1])); out=sys.argv[2]; title=sys.argv[3]; k0,k1=float(sys.argv[4]),float(sys.argv[5])
Q=np.array(d['Q']); SN=d['snaps']; Q=Q-Q[0]
pick=[s for s in SN if s['it'] in (0,1,2,3,4,9)]
cols=['#c6dbef','#9ecae1','#6baed6','#4292c6','#2171b5','#d62728']
W,Hh=1100,1170; L=70; PW=W-L-30
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{Hh}" font-family="WenQuanYi Zen Hei" font-size="15"><rect width="{W}" height="{Hh}" fill="#fff"/>',
     f'<text x="20" y="32" font-size="20" font-weight="bold">{title}</text>']
# 平面図：範囲の節点で回転をそろえる
last=pick[-1]; h=last['h']; P=np.array(last['P'])-np.array(last['P'])[0]
i0,i1=int(k0*1000/h),int(k1*1000/h); seg=P[i0:i1]; c=seg.mean(0); u=seg[-1]-seg[0]; u/=np.hypot(*u); R=np.array([u,[-u[1],u[0]]])
def tr(A): return (np.asarray(A)-c)@R.T
allp=np.vstack([tr(np.array(s['P'])-np.array(s['P'])[0])[int(k0*1000/s['h']):int(k1*1000/s['h'])] for s in pick])
sc=PW/(np.ptp(allp[:,0])*1.05); y0p=60; ph=380
cx=(allp[:,0].min()+allp[:,0].max())/2; cy=(allp[:,1].min()+allp[:,1].max())/2
X=lambda p: L+PW/2+(p[0]-cx)*sc; Y=lambda p: y0p+ph/2-(p[1]-cy)*sc
def pl(A,st): return '<polyline points="'+' '.join(f'{X(p):.1f},{Y(p):.1f}' for p in A)+f'" fill="none" {st}/>'
svg.append(f'<text x="{L}" y="{y0p+12}" fill="#333">平面図（縦横同じ縮尺。縮尺の棒は 100 m）</text>')
svg.append(f'<line x1="{L}" y1="{y0p+ph-10}" x2="{L+100*sc:.1f}" y2="{y0p+ph-10}" stroke="#333" stroke-width="3"/>')
qt=tr(Q); m=(qt[:,0]>allp[:,0].min()-50)&(qt[:,0]<allp[:,0].max()+50)&(np.abs(qt[:,1]-cy)<ph/sc)
svg.append(f'<clipPath id="cp"><rect x="{L}" y="{y0p}" width="{PW}" height="{ph}"/></clipPath><g clip-path="url(#cp)">')
svg.append(pl(qt,'stroke="#222" stroke-width="1.5"'))
for p in qt: svg.append(f'<circle cx="{X(p):.1f}" cy="{Y(p):.1f}" r="3.5" fill="#222"/>')
for s,col in zip(pick,cols):
    A=tr(np.array(s['P'])-np.array(s['P'])[0]); a,b=int((k0-0.3)*1000/s['h']),int((k1+0.3)*1000/s['h'])
    svg.append(pl(A[a:b],f'stroke="{col}" stroke-width="{3 if s is pick[-1] else 2}"'))
svg.append('</g>')
# 曲率図・比
def panel(y0,hgt,key,ylab,fn,ymin,ymax,ref=None):
    svg.append(f'<text x="{L}" y="{y0-8}" fill="#333">{ylab}</text>')
    svg.append(f'<rect x="{L}" y="{y0}" width="{PW}" height="{hgt}" fill="none" stroke="#bbb"/>')
    xs=lambda km: L+(km-k0)/(k1-k0)*PW; ys=lambda v: y0+hgt-(v-ymin)/(ymax-ymin)*hgt
    for g in np.linspace(ymin,ymax,5):
        svg.append(f'<line x1="{L}" y1="{ys(g):.1f}" x2="{L+PW}" y2="{ys(g):.1f}" stroke="#eee"/><text x="{L-6}" y="{ys(g)+5:.1f}" text-anchor="end" font-size="13">{g:g}</text>')
    if ref is not None: svg.append(f'<line x1="{L}" y1="{ys(ref):.1f}" x2="{L+PW}" y2="{ys(ref):.1f}" stroke="#000" stroke-dasharray="6 4"/>')
    for s,col in zip(pick,cols):
        v=np.array(fn(s)); km=np.arange(len(v))*s['h']/1000; mm=(km>=k0)&(km<=k1)
        pts=' '.join(f'{xs(a):.1f},{ys(np.clip(b,ymin,ymax)):.1f}' for a,b in zip(km[mm],v[mm]))
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{2.5 if s is pick[-1] else 1.6}"/>')
    for km in np.arange(math.ceil(k0*10)/10,k1+1e-9,0.2):
        svg.append(f'<text x="{xs(km):.1f}" y="{y0+hgt+17}" text-anchor="middle" font-size="13">{km:.1f}</text>')
panel(500,260,'k','曲率図：曲率 × 1000（＝1000 ÷ 半径。正は左、負は右。±3.33 が半径 300 m）',lambda s:np.array(s['k'])*1000,-8,8,None)
panel(830,230,'rt','曲率の変化の速さ ÷ 上限（破線の 1 を超えた所が規則の違反）　横軸：区間の始点（蘂取）からの距離 km',lambda s:s['rt'],0,3,1.0)
# 凡例
y=Hh-70; x=L
for s,col in zip(pick,cols):
    svg.append(f'<line x1="{x}" y1="{y}" x2="{x+30}" y2="{y}" stroke="{col}" stroke-width="3"/><text x="{x+36}" y="{y+5}" font-size="14">{s["it"]+1} 回目（罰則の重み {s["W"]:.0e}）</text>'); x+=330
    if x>W-330: x=L; y+=24
svg.append(f'<text x="{L}" y="{Hh-8}" font-size="14" fill="#333">● ─ 元の折れ線と頂点（黒）</text>')
open(out,'w').write('\n'.join(svg)+'</svg>')
