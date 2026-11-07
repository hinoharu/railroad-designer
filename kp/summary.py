# 全案のずれ（元の折れ線の 10 m ごとの点 → 線形までの距離）と所要時間の一覧
import json,math,re,numpy as np
from scipy.spatial import cKDTree
r=json.load(open('route_shibetoro_heishi.json')); pts=r['points']
K=111320*math.cos(math.radians(pts[len(pts)//2][1]))
xy=lambda A:np.array([((p[0]-pts[0][0])*K,(p[1]-pts[0][1])*110570) for p in A])
def dens(Q,st):
    out=[Q[0]]
    for a,b in zip(Q,Q[1:]):
        m=max(1,int(math.ceil(np.hypot(*(b-a))/st))); out+=[a+(b-a)*t for t in np.linspace(0,1,m+1)[1:]]
    return np.array(out)
Q=dens(xy(pts),10.0)
cases=[('前の書き方（交点で角を削る）','smooth_60.json','dchk_s60.json','curves_s60.json'),
       ('新しい書き方（交点を外へ動かす）','smooth_60m.json','dchk_s60m.json','curves_s60m.json'),
       ('最適化 重み 0・D 30 m','fit_k0.json','design_fk0.json','curves_fk0.json'),
       ('最適化 重み 3,000・D 30 m','fit_k3000.json','design_fk3000.json','curves_fk3000.json'),
       ('最適化 重み 30,000・D 30 m','fit_k30000.json','design_fk30000.json','curves_fk30000.json'),
       ('最適化 重み 100,000・D 30 m','fit_k1e5.json','design_fk1e5.json','curves_fk1e5.json'),
       ('最適化 重み 100,000・D 60 m','fit_k1e5d60.json','design_fk1e5d60.json','curves_fk1e5d60.json')]
from run import simulate,reversals,DWELL,DWELL_REV
out=[]
for name,fa,fd,fc in cases:
    A=dens(xy(json.load(open(fa))['A']),2.0); d,_=cKDTree(A).query(Q)
    D=json.load(open(fd)); C=json.load(open(fc))
    x,v,t,si,stops,vh=simulate(D,True,C)
    run=sum(t[b]-t[a] for a,b in zip(si,si[1:])); rev=reversals(D)
    tot=run+sum(DWELL_REV if n in rev else DWELL for n in D['stops'][1:-1])
    out.append({'name':name,'med':float(np.median(d)),'p95':float(np.percentile(d,95)),'max':float(d.max()),'min':tot/60,'v130':float(np.sum(v>=130/3.6-0.1)*10/1000)})
    print(f"{name:28s} ずれ 中央値 {np.median(d):5.1f} m 95% {np.percentile(d,95):5.1f} m 最大 {d.max():6.1f} m  所要 {tot/60:6.1f} 分  130km/h {out[-1]['v130']:5.1f} km")
json.dump(out,open('summary.json','w'),ensure_ascii=False)
