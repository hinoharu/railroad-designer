# formation level by linear programming: nodes every NODE m; minimise |z - ground| + MU * |change of grade|,
# with |grade| <= GMAX and level in station yards. Then structures and curve radii (as design.py)
import json,math,sys
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix,csr_matrix,vstack,hstack,identity
from design import GMAX,STN_HALF,BRIDGE,TUNNEL,radius
NODE=100.0
MU=float(sys.argv[3]) if len(sys.argv)>3 else 30.0
GHARD=0.0333      # steeper grades allowed only where needed (user: up to 33.3, at most 40 per mille)
NU=float(sys.argv[4]) if len(sys.argv)>4 else 300.0  # weight on the grade beyond GMAX (per m of rise)
def formation_lp(s,g,stations):
    g=np.array(g,float); bad=np.isnan(g); idx=np.arange(len(g))
    if bad.any(): g[bad]=np.interp(idx[bad],idx[~bad],g[~bad])
    sn=np.arange(0,s[-1]+NODE/2,NODE); sn[-1]=s[-1]; n=len(sn)
    gn=np.array([np.median(g[(s>=x-NODE/2)&(s<=x+NODE/2)]) for x in sn])
    lim=np.full(n-1,GMAX)
    for _,c in stations:
        for k in range(n-1):
            if sn[k+1]>c-STN_HALF and sn[k]<c+STN_HALF: lim[k]=0.0
    # variables: z(n), t(n) >= |z-g|, u(n-2) >= |z[k-1]-2z[k]+z[k+1]|, e(n-1) >= |z[k+1]-z[k]| - GMAX ds (the rise beyond GMAX)
    nz,nt,nu,ne=n,n,n-2,n-1; N=nz+nt+nu+ne
    c=np.concatenate([np.zeros(nz),np.ones(nt),np.full(nu,MU),np.full(ne,NU)])
    rows=[];b=[]
    A=lil_matrix((2*nt+2*nu+2*(n-1),N))
    r=0
    for i in range(n):   # z - t <= g ; -z - t <= -g
        A[r,i]=1;A[r,nz+i]=-1;b.append(gn[i]);r+=1
        A[r,i]=-1;A[r,nz+i]=-1;b.append(-gn[i]);r+=1
    for k in range(1,n-1):
        j=nz+nt+k-1
        A[r,k-1]=1;A[r,k]=-2;A[r,k+1]=1;A[r,j]=-1;b.append(0);r+=1
        A[r,k-1]=-1;A[r,k]=2;A[r,k+1]=-1;A[r,j]=-1;b.append(0);r+=1
    for k in range(n-1):
        ds=sn[k+1]-sn[k]; d=lim[k]*ds; j=nz+nt+nu+k
        A[r,k+1]=1;A[r,k]=-1;A[r,j]=-1;b.append(d);r+=1
        A[r,k+1]=-1;A[r,k]=1;A[r,j]=-1;b.append(d);r+=1
    ub_e=[(0,(GHARD-lim[k])*(sn[k+1]-sn[k]) if lim[k]>0 else 0) for k in range(n-1)]
    res=linprog(c,A_ub=csr_matrix(A),b_ub=np.array(b),bounds=[(None,None)]*nz+[(0,None)]*(nt+nu)+ub_e,method='highs')
    if not res.success: raise SystemExit(res.message)
    zn=res.x[:nz]
    return g,np.interp(s,sn,zn),sn,zn
if __name__=='__main__':
    r=json.load(open(sys.argv[1])); s=np.array(r['s'])
    g,z,sn,zn=formation_lp(s,r['ground'],r['stations'])
    d=z-g
    struct=''.join(np.where(d>BRIDGE,'B',np.where(d<-TUNNEL,'T','-')))
    R=radius(r['xy'])
    gr=np.diff(zn)/np.diff(sn)*1000
    # grade change points (more than 1 per mille between neighbouring 100 m pieces)
    chg=int(np.sum(np.abs(np.diff(gr))>1.0))
    r.update({'ground':g.tolist(),'z':z.tolist(),'struct':struct,'R':[None if math.isinf(x) else x for x in R],'sn':sn.tolist(),'zn':zn.tolist()})
    json.dump(r,open(sys.argv[2],'w'),ensure_ascii=False)
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
    print(f"15‰超 {np.sum(np.abs(gr)>15.05)*NODE/1000:.1f} km（最急 {np.max(np.abs(gr)):.1f}‰）。重み {MU}: 勾配変化点 {chg}（1 km あたり {chg/s[-1]*1000:.2f}）")
    print(f"橋梁 {len(B)} か所 計 {sum(b-a for a,b in B)/1000:.1f} km（最長 {max([b-a for a,b in B]+[0]):.0f} m）")
    print(f"トンネル {len(T)} か所 計 {sum(b-a for a,b in T)/1000:.1f} km（最長 {max([b-a for a,b in T]+[0]):.0f} m）")
    print(f"地面との差 平均 {np.mean(np.abs(d)):.1f} m、勾配 最大 {np.max(np.abs(gr)):.1f}‰、10‰超 {np.sum(np.abs(gr)>10)*NODE/1000:.1f} km、5‰以下 {np.sum(np.abs(gr)<=5)*NODE/1000:.1f} km")
