# formation level (grade-limited, level in stations), structures, curve radii along a route
import json,math,sys
import numpy as np
from scipy.ndimage import minimum_filter1d
GMAX=0.015      # ruling grade (15 per mille), assumed for a trunk line
STN_HALF=110.0  # m each side of a station's centre: the station yard (8 cars 160 m + turnouts)
BRIDGE=12.0     # m of fill above which a bridge is assumed
TUNNEL=15.0     # m of cut below which a tunnel is assumed
DH=0.05         # m: height grid of the search
def formation(s,g,stations):
    g=np.array(g,float); n=len(g)
    bad=np.isnan(g); idx=np.arange(n)
    if bad.any(): g[bad]=np.interp(idx[bad],idx[~bad],g[~bad])
    lim=np.full(n-1,GMAX)
    for _,c in stations:
        lo,hi=np.searchsorted(s,c-STN_HALF),np.searchsorted(s,c+STN_HALF)
        lim[max(0,lo):max(0,hi)]=0.0
    H=np.arange(g.min()-40,g.max()+40,DH); cost=np.abs(H-g[0]); back=np.zeros((n,len(H)),np.int16)
    for i in range(1,n):
        w=int(round(lim[i-1]*(s[i]-s[i-1])/DH))
        if w>0:
            # where the minimum came from (for backtracking): search the window
            best=np.full(len(H),np.inf); arg=np.zeros(len(H),np.int16)
            for k in range(-w,w+1):
                sh=np.roll(cost,-k)
                if k>0: sh[-k:]=np.inf
                elif k<0: sh[:-k]=np.inf
                upd=sh<best; best=np.where(upd,sh,best); arg=np.where(upd,k,arg)
            cost=best+np.abs(H-g[i]); back[i]=arg
        else:
            cost=cost+np.abs(H-g[i]); back[i]=0
    j=int(np.argmin(cost)); z=np.zeros(n)
    for i in range(n-1,-1,-1):
        z[i]=H[j]; j+=int(back[i][j])
    return g,z
def radius(xy):
    lat0=xy[len(xy)//2][1]; k=111320*math.cos(math.radians(lat0))
    P=np.array([((x-xy[0][0])*k,(y-xy[0][1])*110570) for x,y in xy])
    n=len(P); R=np.full(n,np.inf); off=3   # points 60 m before and after
    for i in range(off,n-off):
        a,b,c=P[i-off],P[i],P[i+off]
        ab,bc,ca=np.linalg.norm(b-a),np.linalg.norm(c-b),np.linalg.norm(a-c)
        cr=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
        if cr>1e-6: R[i]=ab*bc*ca/(2*cr)
    return R
if __name__=='__main__':
    r=json.load(open(sys.argv[1])); s=np.array(r['s'])
    g,z=formation(s,r['ground'],r['stations'])
    d=z-g
    struct=np.where(d>BRIDGE,'B',np.where(d<-TUNNEL,'T','-'))
    R=radius(r['xy'])
    r.update({'ground':g.tolist(),'z':z.tolist(),'struct':''.join(struct),'R':[None if math.isinf(x) else x for x in R]})
    json.dump(r,open(sys.argv[2],'w'),ensure_ascii=False)
    grade=np.diff(z)/np.diff(s)*1000
    def runs(ch):
        out=[];i=0
        while i<len(struct):
            if struct[i]==ch:
                j=i
                while j<len(struct) and struct[j]==ch: j+=1
                out.append((s[i],s[min(j,len(s)-1)])); i=j
            else: i+=1
        return out
    B,T=runs('B'),runs('T')
    print(f"橋梁 {len(B)} か所 計 {sum(b-a for a,b in B)/1000:.1f} km（最長 {max([b-a for a,b in B]+[0]):.0f} m）")
    print(f"トンネル {len(T)} か所 計 {sum(b-a for a,b in T)/1000:.1f} km（最長 {max([b-a for a,b in T]+[0]):.0f} m）")
    print(f"切土・盛土の高さの差 平均 {np.mean(np.abs(d)):.1f} m、勾配 最大 {np.max(np.abs(grade)):.1f}‰、10‰超の区間 {np.sum(np.abs(grade)>10)*0.02:.1f} km")
    Rv=R[np.isfinite(R)]
    for lim in (300,400,600,800,1200):
        print(f"  半径 {lim} m 未満の点 {np.sum(Rv<lim)*0.02:.1f} km")
