# 線形の最適化：元の折れ線からのずれ（符号付きの横方向の距離の 2 乗の和）＋ LAM × 走行時間の増分 を最小にする。
# 変数は H m ごとの節点の座標。曲率は隣り合う 3 点の曲がる角度 ÷ 間隔。
# 制約（罰則として残差に入れる）：
#   ・曲率の変化の速さ ≤ 緩和曲線の規則（X = max(0.4C, 0.007CV)、C = 0.8V で釣り合うカント、105 mm まで）
#   ・ずれの絶対値 ≤ D
#   ・停車駅の位置は固定。折り返し駅（紗那）で鎖を分ける
# 使い方：python3 fit.py LAM D 名前   → fit_名前.json
import json,math,sys
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
sys.path.insert(0,'.')
from curves import local
from run import reversals
LAM=float(sys.argv[1]); D=float(sys.argv[2]); NAME=sys.argv[3]
H=20.0; SAMP=10.0
W_STOP=100.0; W_D=10.0; W_RATE=3e5; W_SP=0.3; MU=0.0
EPS=1e-4
r=json.load(open('route_shibetoro_heishi.json')); pts=r['points']
P0=local(pts)
lat0=pts[len(pts)//2][1]; K=111320*math.cos(math.radians(lat0))
stops=[v for (n,_),v in zip(r['stations'],r['vidx']) if n in r['stops']]
stopname=[n for (n,_),v in zip(r['stations'],r['vidx']) if n in r['stops']]
rev=set(reversals(r))

def vkmh(k):   # 曲線の制限速度（km/h）
    k=np.maximum(np.abs(k),1e-9); return np.minimum(130.0,np.sqrt(165/(11.8*k))+30)
def f_time(k): # 1 m あたりの時間の増分（秒）：130 km/h で走る場合との差
    return 3.6/vkmh(k)-3.6/130
def rate_max(k):  # 曲率の変化の上限（1/m²）。k は大きい側の曲率
    k=np.maximum(np.abs(k),1e-9); R=1/k; V=vkmh(k)
    C=np.minimum(7.552*V*V/R,105.0); X=np.maximum(0.4*C,0.007*C*V); X=np.maximum(X,1.0)
    return 1/(R*X)

def resample(Q,n):
    seg=np.hypot(*np.diff(Q,axis=0).T); c=np.concatenate([[0],np.cumsum(seg)])
    t=np.linspace(0,c[-1],n+1)
    return np.c_[np.interp(t,c,Q[:,0]),np.interp(t,c,Q[:,1])]
def densify(Q,step):
    out=[Q[0]]
    for a,b in zip(Q,Q[1:]):
        m=max(1,int(math.ceil(np.hypot(*(b-a))/step)))
        out+=[a+(b-a)*t for t in np.linspace(0,1,m+1)[1:]]
    return np.array(out)

# 鎖：折り返し駅で分ける
chains=[];cur=[0]
for k in range(1,len(stops)):
    cur.append(k)
    if stopname[k] in rev and k<len(stops)-1: chains.append(cur); cur=[k]
chains.append(cur)
import os
if os.environ.get('TEST'): chains=[[0,1,2]]

def solve_chain(sk):
    # 節点：停車駅のあいだをそれぞれ等間隔に
    nodes=[];legs=[];stopnode=[]
    for a,b in zip(sk,sk[1:]):
        Q=P0[stops[a]:stops[b]+1]; L=np.hypot(*np.diff(Q,axis=0).T).sum(); n=max(3,int(round(L/H)))
        X=resample(Q,n)
        if nodes: X=X[1:]
        else: stopnode.append(0)
        st=len(nodes)-(0 if not nodes else 1) if nodes else 0
        nodes+=list(X); stopnode.append(len(nodes)-1); legs.append((stopnode[-2],stopnode[-1]))
    X0=np.array(nodes); N=len(X0)
    # 元の折れ線の標本（10 m ごと）
    Qall=P0[stops[sk[0]]:stops[sk[-1]]+1]; S=densify(Qall,SAMP)
    # 初期値：元の折れ線を少しならす（端は固定）
    Xs=X0.copy()
    for _ in range(4):
        Xs[1:-1]=(Xs[:-2]+2*Xs[1:-1]+Xs[2:])/4
        Xs[stopnode]=X0[stopnode]
    # 標本と節点の区間の対応
    def assign(X,prev=None):
        out=np.zeros(len(S),int)
        for k,q in enumerate(S):
            if prev is None: lo,hi=0,N-1
            else: lo,hi=max(0,prev[k]-25),min(N-1,prev[k]+26)
            hi=min(hi,N-1);A=X[lo:hi];B=X[lo+1:hi+1];d=B-A;l2=(d*d).sum(1)
            t=np.clip(((q-A)*d).sum(1)/np.maximum(l2,1e-9),0,1); P=A+d*t[:,None]
            out[k]=lo+int(np.argmin(np.hypot(*(P-q).T)))
        return out
    cS=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(S,axis=0).T))]); cX=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(Xs,axis=0).T))])
    guess=np.clip(np.searchsorted(cX,cS*cX[-1]/cS[-1])-1,0,N-2)
    seg=assign(Xs,guess)
    # 区間ごとの順序を保つ（行ったり来たりの対応を防ぐ）
    seg=np.maximum.accumulate(seg)
    def kappa(X):
        a=X[1:-1]-X[:-2]; b=X[2:]-X[1:-1]
        ang=np.arctan2(a[:,0]*b[:,1]-a[:,1]*b[:,0],(a*b).sum(1))
        h=(np.hypot(*a.T)+np.hypot(*b.T))/2
        return ang/h,h
    def dev(X,seg):
        A=X[seg];B=X[seg+1];d=B-A;l=np.maximum(np.hypot(*d.T),1e-9)
        return (d[:,0]*(S[:,1]-A[:,1])-d[:,1]*(S[:,0]-A[:,0]))/l   # 正＝進行方向の左
    def resid(x,seg):
        X=x.reshape(-1,2); k,h=kappa(X); dv=dev(X,seg)
        r1=dv*math.sqrt(SAMP/H)
        r2=W_D*np.maximum(0,np.abs(dv)-D)
        r3=np.sqrt(LAM*h*f_time(k)+EPS)-math.sqrt(EPS)
        dk=np.abs(np.diff(k)); hm=(h[1:]+h[:-1])/2; km=np.maximum(np.abs(k[1:]),np.abs(k[:-1]))
        r4=W_RATE*np.maximum(0,dk/hm-rate_max(km))*hm
        r5=MU*np.diff(k)
        ls=np.hypot(*np.diff(X,axis=0).T); r6=W_SP*np.diff(ls)
        r7=W_STOP*(X[stopnode]-X0[stopnode]).ravel()
        return np.concatenate([r1,r2,r3,r4,r5,r6,r7])
    def sparsity(seg):
        n1=len(S); nk=N-2
        rows=[]
        J=lil_matrix((2*n1+nk+2*(nk-1)+(N-2)+2*len(stopnode),2*N),dtype=int)
        o=0
        for blk in range(2):
            for i,s_ in enumerate(seg):
                J[o+i,2*s_:2*s_+4]=1
            o+=n1
        for i in range(nk): J[o+i,2*i:2*i+6]=1
        o+=nk
        for blk in range(2):
            for i in range(nk-1): J[o+i,2*i:2*i+8]=1
            o+=nk-1
        for i in range(N-2): J[o+i,2*i:2*i+6]=1
        o+=N-2
        for j,s_ in enumerate(stopnode): J[o+2*j,2*s_]=1; J[o+2*j+1,2*s_+1]=1
        return J.tocsr()
    x=Xs.ravel().copy()
    for it in range(6):
        res=least_squares(resid,x,args=(seg,),jac_sparsity=sparsity(seg),method='trf',tr_solver='lsmr',x_scale=10.0,max_nfev=60,verbose=0)
        x=res.x
        Xt=x.reshape(-1,2); kt,ht=kappa(Xt); dkt=np.abs(np.diff(kt))/((ht[1:]+ht[:-1])/2); rt=dkt/rate_max(np.maximum(np.abs(kt[1:]),np.abs(kt[:-1])))
        if os.environ.get('TEST'): print(f"  繰り返し {it}: 目的 {res.cost:.3g} 評価 {res.nfev} 状態 {res.status} 違反 {np.sum(rt>1.05)}/{len(rt)} 最大 {rt.max():.2f} 倍 最小半径 {1/np.abs(kt).max():.0f} m",flush=True)
        seg=np.maximum.accumulate(assign(x.reshape(-1,2),seg))
    X=x.reshape(-1,2); k,h=kappa(X); dv=dev(X,seg)
    return X,np.concatenate([[0],k,[0]]),dv,S,stopnode

allX=[];allK=[];allD=[];allS=[];stopidx=[]
for c in chains:
    X,k,dv,S,sn=solve_chain(c)
    base=len(allX)-(1 if allX else 0)
    if allX: X=X[1:];k=k[1:]
    allX+=list(X); allK+=list(k); allD+=list(dv); allS+=list(S)
    for j in (sn if not stopidx else sn[1:]): stopidx.append(base+j)
X=np.array(allX); k=np.array(allK); dv=np.array(allD)
s=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(X,axis=0).T))])
# 時間の目安（曲線の制限速度だけで走る場合の増分）
dt=np.sum(np.gradient(s)*f_time(k))
print(f"LAM {LAM:g} D {D:g}: 全長 {s[-1]/1000:.2f} km  ずれ 中央値 {np.median(np.abs(dv)):.1f} m 95% {np.percentile(np.abs(dv),95):.1f} m 最大 {np.abs(dv).max():.1f} m  "
      f"左右 {np.mean(dv>0)*100:.0f}:{np.mean(dv<0)*100:.0f}（平均 {dv.mean():+.1f} m）  曲線による時間の増分の目安 {dt/60:.1f} 分")
hh=np.diff(s); dk=np.abs(np.diff(k)); km=np.maximum(np.abs(k[1:]),np.abs(k[:-1]))
ratio=dk/np.maximum(hh,1e-9)/rate_max(km)
Rk=1/np.maximum(np.abs(k),1e-9)
print(f"  緩和曲線の規則：曲率の変化が上限を 5% 超える節点 {np.sum(ratio>1.05)} / {len(ratio)}（最大 上限の {ratio.max():.2f} 倍）  最小半径 {Rk.min():.0f} m  半径 300 m 未満の延長 {np.sum(Rk<300)*H/1000:.1f} km  715 m 未満（130 km/h 未満）の延長 {np.sum(Rk<715)*H/1000:.1f} km")
lon=X[:,0]/K+pts[0][0]; lat=X[:,1]/110570+pts[0][1]
json.dump({'lam':LAM,'D':D,'A':np.c_[lon,lat].tolist(),'s':s.tolist(),'k':k.tolist(),'stopidx':stopidx,'dev':dv.tolist()},open(f'fit_{NAME}.json','w'))
