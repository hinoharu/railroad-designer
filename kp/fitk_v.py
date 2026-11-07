# 線形の最適化（曲率を変数にする版。節点の間隔を場所ごとに変える版、2026-11-03、ユーザーの提案）。
# 節点の間隔＝区間ごとの倍率 hh × 場所ごとの比率 w。比率は元の折れ線の曲率から、1 節点あたりに曲がる角度を
# これまでの「最小半径 160 m・間隔 30 m」と同じ（30/160 rad）以下にするように決め、間隔を HMIN〜HMAX m に収める。
# 最小にするもの：Σ（元の折れ線の標本の、線形からの符号付きの横方向の距離）² ＋ LAM × 走行時間の増分（秒）
# 変数：停車駅のあいだの区間ごとに、H m（区間ごとに伸縮）ごとの節点の曲率 κ と、節点の間隔 h。
# 罰則：緩和曲線の規則（曲率の変化の速さ）、ずれ > D、終点の駅の位置。始点の向きは前の区間の終点の向きを引き継ぐ
# （折り返し駅では自由）。使い方：python3 fitk.py LAM D 名前 → fit_名前.json（fit2route.py が読む形）
import json,math,sys,os,time
import numpy as np
from scipy.optimize import least_squares
from scipy.ndimage import maximum_filter1d
from curves import local
from run import reversals
LAM=float(sys.argv[1]); D=float(sys.argv[2]); NAME=sys.argv[3]
HMIN=float(os.environ.get('HMIN','30')); HMAX=float(os.environ.get('HMAX','90')); TURN=30/160
H=HMIN; SAMP=10.0
WIN=int(round(300/HMAX)); W_D=10.0; W_RATE=float(os.environ.get('W_RATE','3e4')); W_END=30.0; EPS=1e-4
# 曲率の 2 乗の和の重み：大きな半径ほど少し得をする（半径 730→800 m の得が、元の線から 1.5 m 離れる損と同じくらい）
MU2 = float(os.environ.get('MU2', '2.4e5'))
r=json.load(open('route_shibetoro_heishi.json')); pts=r['points']
P0=local(pts); K=111320*math.cos(math.radians(pts[len(pts)//2][1]))
stops=[v for (n,_),v in zip(r['stations'],r['vidx']) if n in r['stops']]
names=[n for (n,_),v in zip(r['stations'],r['vidx']) if n in r['stops']]
rev=set(reversals(r))
J90=np.array([[0,-1],[1,0]])

from speed import smooth as _vsmooth
def vkmh(k):
    k = np.maximum(np.abs(k), 1e-9); return _vsmooth(1 / k)
def f_time(k): return 3.6/vkmh(k)-3.6/130
def df_time(k):  # d f / d κ（数値微分）
    e = np.maximum(np.abs(k), 1e-9) * 1e-4 + 1e-9
    return (f_time(k + e) - f_time(k - e)) / (2 * e)
def rate_max(k):
    k=np.maximum(np.abs(k),1e-9); R=1/k; V=vkmh(k)
    C=np.minimum(7.552*V*V/R,105.0); X=np.maximum(np.maximum(0.4*C,0.007*C*V),1.0)
    return 1/(R*X)
OLDRULE=bool(os.environ.get('OLDRULE'))
RMIN=float(os.environ.get('RMIN','160')); RMIN_YARD=160.0; YARD=110.0
# 最小曲線半径の段階：300 m 未満・200 m 未満に罰則（重みは環境変数で変えられる）。160 m 未満は認めない（RMIN）
R_STD=300.0; R_EXC=200.0; W_STD=float(os.environ.get('W_STD','500')); W_EXC=float(os.environ.get('W_EXC','5000'))
def kref(kk):
    if OLDRULE: return np.maximum(np.abs(kk[1:]),np.abs(kk[:-1]))   # 規則の上限に使う曲率：前後 WIN 節点の中の最大（変曲点では前後の曲線の速度で決まるため）
    a=maximum_filter1d(np.abs(kk),size=2*WIN+1,mode='nearest'); return np.maximum(a[1:],a[:-1])
def densify(Q,step):
    out=[Q[0]]
    for a,b in zip(Q,Q[1:]):
        m=max(1,int(math.ceil(np.hypot(*(b-a))/step)))
        out+=[a+(b-a)*t for t in np.linspace(0,1,m+1)[1:]]
    return np.array(out)
def forward(th0,hs,k):
    th=th0+np.concatenate([[0],np.cumsum(hs*(k[1:]+k[:-1])/2)])
    ph=(th[1:]+th[:-1])/2
    P=np.vstack([[0,0],np.cumsum(hs[:,None]*np.c_[np.cos(ph),np.sin(ph)],axis=0)])
    return P,th
def spacing(Q):
    """元の折れ線の曲率から、節点の位置（区間の始点からの距離の比率）を決める"""
    c=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(Q,axis=0).T))]); L=c[-1]
    g=np.arange(0,L+10,10.0); X=np.c_[np.interp(g,c,Q[:,0]),np.interp(g,c,Q[:,1])]
    for _ in range(6): X[1:-1]=(X[:-2]+2*X[1:-1]+X[2:])/4
    ph=np.unwrap(np.arctan2(*np.diff(X,axis=0).T[::-1])); kap=np.abs(np.gradient(ph,10.0))
    kap=maximum_filter1d(kap,size=int(HMAX/10)*2+1,mode='nearest')   # 次の節点までの間の最大の曲率で決める
    hloc=np.clip(TURN/np.maximum(kap,1e-9),HMIN,HMAX); gs=g[:-1]
    pos=[0.0]
    while pos[-1]<L: pos.append(pos[-1]+float(np.interp(pos[-1],gs,hloc)))
    pos=np.array(pos); pos*=L/pos[-1]   # 終点に合わせて伸縮する
    return pos/L

def solve_leg(Q,start,th0,fix_th0):
    S=densify(Q,SAMP); L=np.hypot(*np.diff(Q,axis=0).T).sum()
    fr=spacing(Q); N=len(fr)-1; w=np.diff(fr)*N            # 区間ごとの比率（平均 1）
    wn=np.concatenate([[w[0]/2],(w[1:]+w[:-1])/2,[w[-1]/2]])  # 節点の受け持つ長さの比率
    # 初期値：元の折れ線を等間隔に取り直してならし、向きと曲率を出す
    c=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(Q,axis=0).T))]); t=fr*c[-1]
    X=np.c_[np.interp(t,c,Q[:,0]),np.interp(t,c,Q[:,1])]
    for _ in range(6): X[1:-1]=(X[:-2]+2*X[1:-1]+X[2:])/4
    seg=np.diff(X,axis=0); phs=np.unwrap(np.arctan2(seg[:,1],seg[:,0])); h=L/N
    thn=np.concatenate([[phs[0]],(phs[1:]+phs[:-1])/2,[phs[-1]]])
    k=np.gradient(thn,t)
    if not fix_th0: th0=thn[0]
    end=Q[-1]-start
    sn=fr*L; yard=(sn<YARD)|(sn>L-YARD)
    kmax_n=np.where(yard,1/RMIN_YARD,1/RMIN) if RMIN>0 else np.full(N+1,1e9)
    nyard=(~yard).astype(float)
    # 標本の対応（節点の番号＋区間内の位置）。距離の比率から始める
    cS=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(S,axis=0).T))]); u=np.interp(cS/cS[-1],fr,np.arange(N+1))
    def unpack(x):
        if fix_th0: return th0,math.exp(x[0]),x[1:]
        return x[0],math.exp(x[1]),x[2:]
    def project(x,u):
        a,hh,kk=unpack(x); P,_=forward(a,hh*w,kk); P=P+start
        out=np.empty(len(S))
        for i,q in enumerate(S):
            lo=max(0,int(u[i])-25); hi=min(N,int(u[i])+26)
            A=P[lo:hi];B=P[lo+1:hi+1];d=B-A;l2=(d*d).sum(1)
            tt=np.clip(((q-A)*d).sum(1)/np.maximum(l2,1e-9),0,1); C=A+d*tt[:,None]
            j=int(np.argmin(np.hypot(*(C-q).T))); out[i]=lo+j+tt[j]
        return np.maximum.accumulate(out)
    def parts(x,u):
        a,hh,kk=unpack(x); P,th=forward(a,hh*w,kk); P=P+start
        ia=np.minimum(u.astype(int),N-1); tt=u-ia
        Pu=P[ia]*(1-tt)[:,None]+P[ia+1]*tt[:,None]
        d=P[ia+1]-P[ia]; d/=np.maximum(np.hypot(*d.T),1e-9)[:,None]; nrm=d@J90.T   # 左向きの法線
        dv=((Pu-S)*nrm).sum(1)
        return P,th,ia,tt,nrm,dv,hh,kk
    def resid(x,u):
        P,th,ia,tt,nrm,dv,hh,kk=parts(x,u)
        e=np.maximum(0,np.abs(dv)-D)
        r1=np.sign(dv)*np.sqrt(dv*dv+(W_D*e)**2)*math.sqrt(SAMP/H)
        hn=hh*wn; hs=hh*w; sw=np.sqrt(wn)
        r2=np.sqrt(LAM*hn*f_time(kk)+EPS)-math.sqrt(EPS)
        dk=np.diff(kk); km=kref(kk)
        r2b=np.sqrt(MU2*hn)*kk
        r3=W_RATE*np.sign(dk)*np.maximum(0,np.abs(dk)-hs*rate_max(km))/hs*H
        r4=W_END*(P[-1]-Q[-1])
        r5=W_RATE*np.maximum(0,np.abs(kk)-kmax_n)*H*sw
        r6=W_STD*np.maximum(0,np.abs(kk)-1/R_STD)*H*nyard*sw
        r7=W_EXC*np.maximum(0,np.abs(kk)-1/R_EXC)*H*nyard*sw
        return np.concatenate([r1,r2,r3,r4,r5,r6,r7,r2b])
    def jac(x,u):
        P,th,ia,tt,nrm,dv,hh,kk=parts(x,u)
        n=N+1
        # dP_m/dκ_j ≈ h·J(P_m − P_j)（m > j）
        Dm=P[:,None,:]-P[None,:,:]                      # m, j
        hn=hh*wn; hs=hh*w; sw=np.sqrt(wn)
        G=hn[None,:,None]*np.einsum('ab,mjb->mja',J90,Dm);
        mask=np.arange(n)[:,None]>np.arange(n)[None,:]
        G*=mask[:,:,None]
        Gt=np.einsum('ab,mb->ma',J90,P-start)            # dP_m/dθ0
        # 間隔 h（対数）：数値微分
        x2=x.copy(); ih=0 if fix_th0 else 1; x2[ih]+=1e-6
        a2,h2,k2=unpack(x2); P2,_=forward(a2,h2*w,k2); Gh=(P2+start-P)/1e-6
        nv=len(x); nS=len(S)
        Jm=np.zeros((nS+N+1+N+2+4*(N+1),nv))
        off=0 if fix_th0 else 1
        # 標本
        GP=G[ia]*(1-tt)[:,None,None]+G[ia+1]*tt[:,None,None]
        e=np.maximum(0,np.abs(dv)-D); rr=np.sqrt(dv*dv+(W_D*e)**2)
        fac=np.where(np.abs(dv)<1e-9,1.0,(np.abs(dv)+W_D**2*e)/np.maximum(rr,1e-9))*math.sqrt(SAMP/H)
        Jm[:nS,off+1:]=np.einsum('sjb,sb->sj',GP,nrm)*fac[:,None]
        Jm[:nS,off]=((Gh[ia]*(1-tt)[:,None]+Gh[ia+1]*tt[:,None])*nrm).sum(1)*fac
        if not fix_th0: Jm[:nS,0]=((Gt[ia]*(1-tt)[:,None]+Gt[ia+1]*tt[:,None])*nrm).sum(1)*fac
        # 時間
        o=nS; ft=f_time(kk); sq=np.sqrt(LAM*hn*ft+EPS)
        Jm[o+np.arange(N+1),off+1+np.arange(N+1)]=LAM*hn*df_time(kk)/(2*sq)
        Jm[o:o+N+1,off]=LAM*hn*ft/(2*sq)
        # 規則
        o+=N+1; dk=np.diff(kk); km=kref(kk); act=(np.abs(dk)-hs*rate_max(km))>0
        idx=np.arange(N)
        Jm[o+idx,off+1+idx+1]=W_RATE*act/hs*H
        Jm[o+idx,off+1+idx]=-W_RATE*act/hs*H
        # 終点
        o+=N
        Jm[o:o+2,off+1:]=W_END*G[-1].T
        Jm[o:o+2,off]=W_END*Gh[-1]
        if not fix_th0: Jm[o:o+2,0]=W_END*Gt[-1]
        o+=2; act=np.abs(kk)>kmax_n
        Jm[o+np.arange(N+1),off+1+np.arange(N+1)]=W_RATE*act*np.sign(kk)*H*sw
        o+=N+1; Jm[o+np.arange(N+1),off+1+np.arange(N+1)]=W_STD*(np.abs(kk)>1/R_STD)*np.sign(kk)*H*nyard*sw
        o+=N+1; Jm[o+np.arange(N+1),off+1+np.arange(N+1)]=W_EXC*(np.abs(kk)>1/R_EXC)*np.sign(kk)*H*nyard*sw
        o+=N+1; Jm[o+np.arange(N+1),off+1+np.arange(N+1)]=np.sqrt(MU2*hn)
        return Jm
    x=np.concatenate(([] if fix_th0 else [[th0]])+[[math.log(h)],k])
    global W_RATE
    for it in range(10):
        W_RATE=1e3*10**min(it,4)
        res=least_squares(resid,x,jac=jac,args=(u,),method='trf',tr_solver='lsmr',max_nfev=80,x_scale='jac')
        x=res.x; u=project(x,u)
        if os.environ.get('SNAP'):
            P_,th_,ia_,tt_,nrm_,dv_,hh_,kk_=parts(x,u)
            rt_=np.abs(np.diff(kk_))/hh_/rate_max(kref(kk_))
            SNAPS.append({'it':it,'W':W_RATE,'P':(P_).tolist(),'k':kk_.tolist(),'rt':rt_.tolist(),'lim':(hh_*rate_max(kref(kk_))).tolist(),'h':hh_,'dv':dv_.tolist()})
    P,th,ia,tt,nrm,dv,hh,kk=parts(x,u)
    rt=np.abs(np.diff(kk))/(hh*w)/rate_max(kref(kk))
    bad=np.nonzero(rt>1.05)[0]
    if len(bad): print("    違反の位置（区間の始点から km）:",' '.join(f"{fr[i]*L/1000:.2f}({rt[i]:.2f},R{1/max(abs(kk[i]),abs(kk[i+1]),1e-9):.0f})" for i in bad[:40]))
    print(f"    終了時の目的 {res.cost:.3g} 状態 {res.status} 規則の違反の比 中央値 {np.median(rt):.2f} 99% {np.percentile(rt,99):.2f}",flush=True)
    return P,th,kk,dv,hh*N/L*L/N,rt

t0=time.time()
SNAPS=[]
legs=list(zip(range(len(stops)-1),range(1,len(stops))))
if os.environ.get('TEST'): legs=legs[:int(os.environ['TEST'])]
allP=[];allK=[];allD=[];stopidx=[0];th_end=None;RT=[]
for a,b in legs:
    Q=P0[stops[a]:stops[b]+1]
    start=allP[-1] if allP else Q[0]
    fix=th_end is not None and names[a] not in rev
    ck=f'ckpt/{NAME}_{a}.npz'
    if os.path.exists(ck):   # 区間ごとの保存（コンテナの再起動に備える）
        z=np.load(ck); P,th,kk,dv,rt=z['P'],z['th'],z['kk'],z['dv'],z['rt']; hh=float(z['hh'])
    else:
        P,th,kk,dv,hh,rt=solve_leg(Q,np.array(start),th_end if fix else 0.0,fix)
        os.makedirs('ckpt',exist_ok=True); np.savez(ck,P=P,th=th,kk=kk,dv=dv,hh=hh,rt=rt)
    P[-1]=Q[-1]   # 駅の位置にそろえる（残る誤差は print で示す）
    gap=np.hypot(*(P[-2]-Q[-1]))
    if allP: P=P[1:];kk_=kk[1:]
    else: kk_=kk
    allP+=list(P); allK+=list(kk_); allD+=list(dv); RT+=list(rt); stopidx.append(len(allP)-1); th_end=th[-1]
    print(f"  {names[a]}→{names[b]}: 節点 {len(kk)} 間隔 平均 {np.hypot(*np.diff(P,axis=0).T).mean():.1f} m ずれ 最大 {np.abs(dv).max():.1f} m 規則の違反 {np.sum(rt>1.05)} 最大 {rt.max():.2f} 倍 最小半径 {1/np.abs(kk).max():.0f} m  ({time.time()-t0:.0f} 秒)",flush=True)
X=np.array(allP); k=np.array(allK); dv=np.array(allD); RT=np.array(RT)
s=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(X,axis=0).T))])
dt=np.sum(np.gradient(s)*f_time(k)); Rk=1/np.maximum(np.abs(k),1e-9)
print(f"LAM {LAM:g} D {D:g}: 全長 {s[-1]/1000:.2f} km  ずれ 中央値 {np.median(np.abs(dv)):.1f} m 95% {np.percentile(np.abs(dv),95):.1f} m 最大 {np.abs(dv).max():.1f} m  "
      f"左右 {np.mean(dv>0)*100:.0f}:{np.mean(dv<0)*100:.0f}（平均 {dv.mean():+.1f} m）  曲線による時間の増分の目安 {dt/60:.1f} 分")
print(f"  緩和曲線の規則：上限を 5% 超える節点 {np.sum(RT>1.05)} / {len(RT)}（最大 {RT.max():.2f} 倍）  最小半径 {Rk.min():.0f} m  300 m 未満 {np.gradient(s)[Rk<300].sum()/1000:.1f} km  730 m 未満 {np.gradient(s)[Rk<730].sum()/1000:.1f} km")
lon=X[:,0]/K+pts[0][0]; lat=X[:,1]/110570+pts[0][1]
if os.environ.get('SNAP'): json.dump({'Q':P0[stops[0]:stops[1]+1].tolist(),'snaps':SNAPS},open(os.environ['SNAP'],'w'))
json.dump({'lam':LAM,'D':D,'A':np.c_[lon,lat].tolist(),'s':s.tolist(),'k':k.tolist(),'stopidx':stopidx,'dev':dv.tolist()},open(f'fit_{NAME}.json','w'))
