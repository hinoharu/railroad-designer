# fit_名前.json → route_f名前.json（駅の位置つき）と curves_f名前.json（run.py の形：曲線ごとに最小の半径）
import json,math,sys
import numpy as np
t=sys.argv[1]; M=json.load(open(f'fit_{t}.json')); R=json.load(open('route_shibetoro_heishi.json'))
F=json.load(open(__import__('geo').FICTION_JSON,encoding='utf-8'))
xy={s[0]:(s[3]/1e5,s[2]/1e5) for s in F['stations'] if s[5]=='択捉'}
A=M['A']; k=np.array(M['k'])
# キロ程は地球上の距離で測る（縦断の ground.py と同じ。平面の座標で測ると、緯度で縮尺がずれて最大 230 m 食い違った）
from geo import metres
s=np.concatenate([[0],np.cumsum([metres(a,b) for a,b in zip(A,A[1:])])])
K=111320*math.cos(math.radians(A[len(A)//2][1]))
AP=np.array([((p[0]-A[0][0])*K,(p[1]-A[0][1])*110570) for p in A])
st=[];vidx=[];last=0;si=iter(M['stopidx'])
for n,c in R['stations']:
    if n in R['stops']: i=next(si)
    else:
        p=xy[n]; q=np.array([(p[0]-A[0][0])*K,(p[1]-A[0][1])*110570]); d=np.hypot(*(AP[last:]-q).T); i=last+int(np.argmin(d))
    st.append((n,float(s[i]))); vidx.append(int(i)); last=i
json.dump({'points':A,'stations':st,'stops':R['stops'],'vidx':vidx,'s':s.tolist()},open(f'route_f{t}.json','w'),ensure_ascii=False)
# 曲線：同じ向きに曲がり続ける範囲（|κ| > 1/5000）
cv=[];i=0;n=len(k);KMIN=1/5000
while i<n:
    if abs(k[i])<=KMIN: i+=1; continue
    j=i; sg=np.sign(k[i])
    while j+1<n and np.sign(k[j+1])==sg and abs(k[j+1])>KMIN: j+=1
    seg=k[i:j+1]; Rmin=1/np.abs(seg).max()
    delta=math.degrees(abs(np.sum(seg[:-1]*np.diff(s[i:j+1])))) if j>i else 0
    cv.append({'s0':float(s[i]),'s1':float(s[j]),'R':float(Rmin),'X':0.0,'dir':'左' if sg>0 else '右','delta':delta,'full':False})
    i=j+1
json.dump(cv,open(f'curvelist_f{t}.json','w'),ensure_ascii=False)
# 走行計算用：節点ごとの区間に、前後 WIN m の中で最も急な曲率の半径を当てる（緩和曲線には隣の円曲線の制限が当たる）
WIN=100.0
from scipy.ndimage import maximum_filter1d
hh=np.median(np.diff(s)); w=int(round(WIN/hh))
km=maximum_filter1d(np.abs(k),size=2*w+1,mode='nearest')
pieces=[{'s0':float(s[i]),'s1':float(s[i+1]),'R':float(1/km[i]),'X':0.0,'dir':'','delta':0.0,'full':False} for i in range(n-1) if km[i]>1/5000]
if 'elements_flat' in M:
    # 線形要素（交点法）：円曲線ごとに、前の緩和曲線の始点から後ろの緩和曲線の終点までに、その円曲線の半径を当てる
    # （速度制限標識・解除標識の位置。2 つの円曲線にはさまれた緩和曲線は重なり、run.py が遅い方を取る。2026-11-04、ユーザーの判断で案B）
    # 要素の境目は平面の距離なので、地球上のキロ程 s に写す
    fs=np.array(M['s']); g=lambda x: float(np.interp(x,fs,s))
    el=M['elements_flat']; pieces=[]
    for i,(a,b,kind,R_) in enumerate(el):
        if kind!='C': continue
        if i>0 and el[i-1][2]=='T': a=el[i-1][0]
        if i+1<len(el) and el[i+1][2]=='T': b=el[i+1][1]
        pieces.append({'s0':g(a),'s1':g(b),'R':float(R_),'X':0.0,'dir':'','delta':0.0,'full':False})
json.dump(pieces,open(f'curves_f{t}.json','w'),ensure_ascii=False)
Rs=np.array([c['R'] for c in cv])
print(t,'曲線',len(cv),'転向角計 %.0f°'%sum(c['delta'] for c in cv),'半径の中央値 %.0f m'%np.median(Rs[Rs<1600]),'（1600 m 未満の曲線 %d）'%np.sum(Rs<1600))
