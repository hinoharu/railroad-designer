# a cleaner alignment from the drawn line: simplify it (Douglas-Peucker, TOL) into the tangents of a design (IPs), then
# at each IP a curve (transition + circular + transition) tangent to both sides, as large as the sides allow (half of
# each side at most) and no larger than RCAP. Legs between stops are done one by one (a stop stays where it is).
import json,math,sys
import numpy as np
from curves import local,transition
TOL=float(sys.argv[1]) if len(sys.argv)>1 else 30.0
FIT=len(sys.argv)>2 and sys.argv[2]=='fit'   # the sides fitted to the drawn points (least squares) instead of chords between them
RCAP=1600.0
r=json.load(open('route_shibetoro_heishi.json')); pts=r['points']
lat0=pts[len(pts)//2][1]; K=111320*math.cos(math.radians(lat0))
P=local(pts)
def dp(Q,tol):
    keep=np.zeros(len(Q),bool); keep[0]=keep[-1]=True; st=[(0,len(Q)-1)]
    while st:
        a,b=st.pop()
        if b<=a+1: continue
        A,B=Q[a],Q[b]; d=B-A; n=np.hypot(*d)
        if n<1e-9: dist=np.hypot(*(Q[a+1:b]-A).T)
        else: dist=np.abs(d[0]*(Q[a+1:b,1]-A[1])-d[1]*(Q[a+1:b,0]-A[0]))/n
        i=int(np.argmax(dist))
        if dist[i]>tol: keep[a+1+i]=True; st+=[(a,a+1+i),(a+1+i,b)]
    return Q[keep]
def dp_idx(Q,tol):
    keep=np.zeros(len(Q),bool); keep[0]=keep[-1]=True; st=[(0,len(Q)-1)]
    while st:
        a,b=st.pop()
        if b<=a+1: continue
        A,B=Q[a],Q[b]; d=B-A; n=np.hypot(*d)
        dist=np.hypot(*(Q[a+1:b]-A).T) if n<1e-9 else np.abs(d[0]*(Q[a+1:b,1]-A[1])-d[1]*(Q[a+1:b,0]-A[0]))/n
        i=int(np.argmax(dist))
        if dist[i]>tol: keep[a+1+i]=True; st+=[(a,a+1+i),(a+1+i,b)]
    return np.nonzero(keep)[0]
def fitted(Q,ix):
    """IPs from lines fitted to the drawn points of each side; the ends stay where they are"""
    lines=[]
    for a,b in zip(ix,ix[1:]):
        X=Q[a:b+1]
        # densify so that long sides weigh by length, not by vertex count
        D=[X[0]]
        for p,q in zip(X,X[1:]):
            m=max(1,int(np.hypot(*(q-p))//10)); D+=[p+(q-p)*t for t in np.linspace(0,1,m+1)[1:]]
        D=np.array(D); c=D.mean(axis=0); u=np.linalg.svd(D-c)[2][0]
        if u@(X[-1]-X[0])<0: u=-u
        lines.append((c,u))
    V=[Q[0]]
    for j in range(1,len(lines)):
        (c1,u1),(c2,u2)=lines[j-1],lines[j]; M=np.array([u1,-u2]).T
        if abs(np.linalg.det(M))<1e-3: V.append(Q[ix[j]]); continue
        t=np.linalg.solve(M,c2-c1); p=c1+u1*t[0]
        # an intersection far from the drawn corner (nearly straight on): keep the drawn vertex
        if np.hypot(*(p-Q[ix[j]]))>3*TOL: p=Q[ix[j]]
        V.append(p)
    V.append(Q[-1]); return np.array(V)
MID=len(sys.argv)>2 and sys.argv[2]=='mid'   # move each IP out along its bisector until the drawn points straddle the curve
cr=lambda a,b: a[0]*b[1]-a[1]*b[0]
def leg(Q):
    V=fitted(Q,dp_idx(Q,TOL)) if FIT else dp(Q,TOL)
    if not MID: return build(V)
    V=V.astype(float).copy(); V0=V.copy()
    for it in range(10):
        A,cv,_,info=build(V,True)
        # each drawn point's nearest point on the alignment
        near=np.array([int(np.argmin(np.hypot(*(A-p).T))) for p in Q])
        for i,(a,b,sg) in info.items():
            m_=(near>a)&(near<b)
            if not m_.any(): continue
            offs=[]
            for p,j in zip(Q[m_],near[m_]):
                d=float(np.hypot(*(A[j]-p)))
                if d>3*TOL: continue
                side=np.sign(cr(A[j+1]-A[j-1],p-A[j]))
                offs.append(-side*sg*d)
            if not offs: continue
            m=float(np.clip(np.mean(offs),-TOL/2,TOL/2))
            u0=V[i]-V[i-1]; u1=V[i+1]-V[i]; u0/=np.hypot(*u0); u1/=np.hypot(*u1)
            bis=u0-u1; nb=np.hypot(*bis)
            if nb<1e-9: continue
            P_=V[i]+bis/nb*m*0.8
            dv=P_-V0[i]; dn=np.hypot(*dv)
            if dn>1.5*TOL: P_=V0[i]+dv/dn*1.5*TOL
            V[i]=P_
    return build(V)
def build(V,want_info=False):
    """the alignment (dense points) and its curves along the IPs V"""
    n=len(V)
    seg=[V[i+1]-V[i] for i in range(n-1)]; Ls=[float(np.hypot(*s)) for s in seg]; U=[s/np.hypot(*s) for s in seg]
    curves=[]
    for i in range(1,n-1):
        a1,a2=math.atan2(U[i-1][1],U[i-1][0]),math.atan2(U[i][1],U[i][0]); D=math.atan2(math.sin(a2-a1),math.cos(a2-a1))
        if abs(D)<math.radians(0.3): curves.append(None); continue
        Tmax=min(Ls[i-1],Ls[i])/2; d=abs(D)
        R=RCAP; X=0.0
        for _ in range(6):
            V_=min(130.0,math.sqrt(R*165/11.8)+30); C,X=transition(R,V_)
            T=(R+X*X/(24*R))*math.tan(d/2)+X/2-X**3/(240*R*R)
            if T>Tmax:   # too large for the sides: shrink to fit
                R=max(20.0,(Tmax-X/2)/math.tan(d/2)) if Tmax>X/2 else max(20.0,Tmax/math.tan(d/2)); 
        T=(R+X*X/(24*R))*math.tan(d/2)+X/2-X**3/(240*R*R)
        if T>Tmax: X=0.0; R=Tmax/math.tan(d/2); T=Tmax
        curves.append({'ip':V[i],'D':D,'R':R,'X':X,'T':T,'u0':U[i-1],'u1':U[i]})
    # build: from start, straight to each TS, curve by curvature integration, on to the next
    out=[V[0].copy()]; cv=[]; info={}
    for i,c in enumerate(curves):
        if c is None: out.append(V[i+1].copy()); continue
        TS=c['ip']-c['u0']*c['T']; out.append(TS)
        s_start=len(out)-1
        sg=1 if c['D']>0 else -1; Lc=c['R']*abs(c['D'])+c['X']; X=c['X']; R=c['R']
        x,y=TS; th=math.atan2(c['u0'][1],c['u0'][0]); u=0.0; du=2.0
        def kap(u):
            if X<=0: return sg/R
            if u<X: return sg/R*u/X
            if u>Lc-X: return sg/R*max(0.0,(Lc-u))/X
            return sg/R
        while u<Lc:
            d_=min(du,Lc-u); km=kap(u+d_/2); x+=d_*math.cos(th+km*d_/2); y+=d_*math.sin(th+km*d_/2); th+=km*d_; u+=d_; out.append(np.array([x,y]))
        info[i+1]=(s_start,len(out)-1,sg)
        ST=c['ip']+c['u1']*c['T']; cv.append({'a':s_start,'b':len(out)-1,'R':R,'X':X,'delta':math.degrees(abs(c['D'])),'dir':'左' if sg>0 else '右','miss':float(np.hypot(x-ST[0],y-ST[1]))})
    out.append(V[-1].copy())
    if want_info: return np.array(out),cv,V,info
    return np.array(out),cv,V
# legs between stops
stop_v=[v for (n,_),v in zip(r['stations'],r['vidx']) if n in r['stops']]
ALL=[];CV=[];IPS=[]
for a,b in zip(stop_v,stop_v[1:]):
    A,cv,V=leg(P[a:b+1]); base=len(ALL)-1 if ALL else 0
    if ALL: A=A[1:]
    off=len(ALL)-(0 if not ALL else 1)
    for c in cv: c['a']+=max(off,0); c['b']+=max(off,0)
    ALL+= [tuple(p) for p in A]; CV+=cv; IPS+=[tuple(v) for v in V]
A=np.array(ALL); cum=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(A,axis=0).T))])
for c in CV: c['s0']=float(cum[c['a']]); c['s1']=float(cum[c['b']])
# deviation of the drawn line from the new alignment
def dist_to(Pq,poly):
    best=np.full(len(Pq),np.inf)
    for i in range(len(poly)-1):
        a,b=poly[i],poly[i+1]; d=b-a; l2=d@d
        t=np.clip(((Pq-a)@d)/l2 if l2>0 else 0,0,1); q=a+np.outer(t,d); best=np.minimum(best,np.hypot(*(Pq-q).T))
    return best
dev=dist_to(P,A)
R=np.array([c['R'] for c in CV]); miss=np.array([c['miss'] for c in CV])
print(f"許容 {TOL:.0f} m{'（当てはめ）' if FIT else '（交点を動かす）' if MID else ''}：IP {len(IPS)}、曲線 {len(CV)} 本（曲線の延長 {sum(c['s1']-c['s0'] for c in CV)/1000:.1f} km、直線 {(cum[-1]-sum(c['s1']-c['s0'] for c in CV))/1000:.1f} km）、全長 {cum[-1]/1000:.2f} km（元 {r['stations'][-1][1]/1000:.2f}）")
print(f"  元の線とのずれ：中央値 {np.median(dev):.1f} m、95% {np.percentile(dev,95):.1f} m、最大 {dev.max():.1f} m／曲線の終点の誤差 最大 {miss.max():.2f} m")
for lo,hi in ((0,300),(300,600),(600,1000),(1000,1600),(1600,1e9)):
    m=(R>=lo)&(R<hi); print(f"  R {lo}〜{'' if hi>1e8 else hi}: {m.sum()} 本")
json.dump({'tol':TOL,'A':[[x/K+pts[0][0],y/110570+pts[0][1]] for x,y in A],'s':cum.tolist(),'curves':[{k:v for k,v in c.items() if k not in('a','b')} for c in CV],
           'ips':[[x/K+pts[0][0],y/110570+pts[0][1]] for x,y in IPS],'dev':float(dev.max())},open(f'smooth_{int(TOL)}{"f" if FIT else "m" if MID else ""}.json','w'))
