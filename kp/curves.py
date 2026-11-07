# curves from the drawn line: vertices turning the same way in a row make one curve; a turn the other way starts the
# next. A curve runs from the middle of the side before its first vertex to the middle of the side after its last, and
# its radius is that length over its total deflection. Transition curves at both ends (length from cant and speed).
import json,math,sys
import numpy as np
EPS=math.radians(0.2)   # a vertex turning less than this is no turn (it neither starts nor ends a curve)
def local(pts):
    lat0=pts[len(pts)//2][1]; k=111320*math.cos(math.radians(lat0))
    return np.array([((x-pts[0][0])*k,(y-pts[0][1])*110570) for x,y in pts])
def curves(pts,stops=None):
    P=local(pts); seg=np.diff(P,axis=0); L=np.hypot(seg[:,0],seg[:,1])
    keep=L>0.5
    # drop zero-length sides; the index of each kept vertex in the new list
    newi=np.concatenate([[0],np.cumsum(keep)])
    P=np.vstack([P[0],P[1:][keep]]); seg=np.diff(P,axis=0); L=np.hypot(seg[:,0],seg[:,1])
    cum=np.concatenate([[0],np.cumsum(L)])
    ang=np.arctan2(seg[:,1],seg[:,0]); th=np.angle(np.exp(1j*np.diff(ang)))   # turn at vertex i+1 (between side i and i+1)
    out=[];cur=None
    brk=set()   # vertices at the stops: a curve does not run through a stop (the train stops, and may reverse there)
    for v in (stops or []):
        brk.add(int(newi[v]))
    for i,t in enumerate(th):
        if i+1 in brk:
            if cur: out.append(cur)
            cur=None; continue
        if abs(t)<EPS: continue
        sg=1 if t>0 else -1
        if cur and cur['sign']==sg:
            cur['last']=i; cur['delta']+=t
        else:
            if cur: out.append(cur)
            cur={'sign':sg,'first':i,'last':i,'delta':t}
    if cur: out.append(cur)
    res=[]
    for c in out:
        a=cum[c['first']]+L[c['first']]/2          # middle of the side before the first turning vertex
        b=cum[c['last']+1]+L[c['last']+1]/2       # middle of the side after the last
        D=abs(c['delta']); Lc=b-a
        R=Lc/D; X=0.0; C=0.0; full=False
        for _ in range(4):   # a transition of X at each end: the circular arc turns D - X/R, the whole is R D + X long
            V=min(130.0,math.sqrt(R*165/11.8)+30)
            C,X=transition(R,V)
            if X<=Lc/2: R=(Lc-X)/D; full=False
            else: X=Lc/2; R=Lc/(2*D); full=True   # too short for a circular arc: transitions only (the least radius at the middle)
        res.append({'s0':float(a),'s1':float(b),'delta':float(math.degrees(D)),'R':float(R),'X':float(X),'C':float(C),'full':full,'dir':'左' if c['sign']>0 else '右'})
    return res,float(cum[-1])
def transition(R,V):
    """cant (mm) balanced at 0.8 V and capped at 105, and the transition length (m): the larger of 0.4 C and 0.007 C V"""
    C=min(105.0,11.8*(0.8*V)**2/R)
    return C,max(0.4*C,0.007*C*V)
if __name__=='__main__':
    r=json.load(open(sys.argv[1]))
    cs,total=curves(r['points'],[v for (n,_),v in zip(r['stations'],r['vidx']) if n in r['stops']])
    R=np.array([c['R'] for c in cs])
    print('曲線',len(cs),'本、経路の長さ',round(total/1000,2),'km（経路の距離との差',round(total-r['stations'][-1][1],1),'m）')
    for lo,hi in ((0,300),(300,400),(400,600),(600,800),(800,1200),(1200,2000),(2000,1e9)):
        m=(R>=lo)&(R<hi); print(f'  R {lo}〜{hi if hi<1e9 else "":>4} m: {m.sum():3d} 本、延長 {sum(c["s1"]-c["s0"] for c,mm in zip(cs,m) if mm)/1000:6.1f} km')
    json.dump(cs,open(sys.argv[2],'w'),ensure_ascii=False)
