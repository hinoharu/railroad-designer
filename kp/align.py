# the alignment drawn as curves: each curve from its start on the drawn line, with the heading of the side it starts
# on, its curvature rising over the transition to 1/R, held, and falling again; straights between keep the drawn line.
# Points carry the chainage of the drawn line (a curve is as long as the drawn line it replaces)
import json,math,sys
import numpy as np
from curves import local
r=json.load(open('route_shibetoro_heishi.json')); C=json.load(open('curves_shibetoro_heishi.json'))
pts=r['points']; lat0=pts[len(pts)//2][1]; k=111320*math.cos(math.radians(lat0))
P=local(pts); seg=np.diff(P,axis=0); L=np.hypot(seg[:,0],seg[:,1]); keep=L>0.5
P=np.vstack([P[0],P[1:][keep]]); seg=np.diff(P,axis=0); L=np.hypot(seg[:,0],seg[:,1]); cum=np.concatenate([[0],np.cumsum(L)])
def at(s):
    i=min(max(int(np.searchsorted(cum,s))-1,0),len(L)-1); t=(s-cum[i])/L[i]
    return P[i]+t*seg[i], math.atan2(seg[i][1],seg[i][0])
out=[];gaps=[];prev=0.0
for c in sorted(C,key=lambda c:c['s0']):
    a,b=c['s0'],c['s1']
    # the drawn line from the end of the last curve to the start of this one (a straight)
    for s in np.arange(prev,a,10.0): out.append((s,*at(s)[0]))
    p,h=at(a); sg=1 if c['dir']=='左' else -1; Lc=b-a; X=c['X']; R=c['R']
    if out: gaps.append(math.hypot(out[-1][1]-p[0],out[-1][2]-p[1]))
    def kappa(u):
        if c['full']: return sg/R*(u/X if u<=X else (Lc-u)/X)
        if u<X: return sg/R*u/X
        if u>Lc-X: return sg/R*(Lc-u)/X
        return sg/R
    x,y,th=p[0],p[1],h; du=2.0; u=0.0
    while u<Lc:
        out.append((a+u,x,y)); d=min(du,Lc-u); km=kappa(u+d/2)
        x+=d*math.cos(th+km*d/2); y+=d*math.sin(th+km*d/2); th+=km*d; u+=d
    out.append((b,x,y)); prev=b
    # where the drawn line goes on from (the next straight starts on it)
    q,_=at(b); c['endgap']=math.hypot(x-q[0],y-q[1])
for s in np.arange(prev,cum[-1],10.0): out.append((s,*at(s)[0]))
out.append((cum[-1],*P[-1]))
eg=[c['endgap'] for c in C]
print('曲線の終点と元の折れ線のずれ（m）：中央値',round(float(np.median(eg)),1),'90%',round(float(np.percentile(eg,90)),1),'最大',round(max(eg),1))
xy=[(pts[0][0]+x/k, pts[0][1]+y/110570) for _,x,y in out]
json.dump({'s':[o[0] for o in out],'xy':xy},open('align_shibetoro_heishi.json','w'))
# the largest gaps: where
big=sorted(C,key=lambda c:-c['endgap'])[:6]
for c in big: print(f"  ずれ {c['endgap']:6.1f} m：{c['s0']/1000:.2f} km、{c['dir']}R{c['R']}、交角 {c['delta']}°")
