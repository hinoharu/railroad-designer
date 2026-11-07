# a route JSON (as path.py writes) on a smoothed alignment, and its curves in the curves.py form
import json,sys,math
import numpy as np
from geo import metres
t=sys.argv[1]; M=json.load(open(f'smooth_{t}.json')); R=json.load(open('route_shibetoro_heishi.json'))
F=json.load(open(__import__('geo').FICTION_JSON,encoding='utf-8'))
xy={s[0]:(s[3]/1e5,s[2]/1e5) for s in F['stations'] if s[5]=='択捉'}
A=M['A']; s=np.array(M['s'])
lat0=A[len(A)//2][1]; K=111320*math.cos(math.radians(lat0))
AP=np.array([((p[0]-A[0][0])*K,(p[1]-A[0][1])*110570) for p in A])
st=[];vidx=[];last=0
for n,c in R['stations']:
    p=xy[n]; q=np.array([(p[0]-A[0][0])*K,(p[1]-A[0][1])*110570])
    # the nearest vertex at or after the last one (the route may pass a place twice)
    d=np.hypot(*(AP[last:]-q).T); i=last+int(np.argmin(d)); st.append((n,float(s[i]))); vidx.append(i); last=i
json.dump({'points':A,'stations':st,'stops':R['stops'],'vidx':vidx},open(f'route_s{t}.json','w'),ensure_ascii=False)
json.dump([{'s0':c['s0'],'s1':c['s1'],'R':c['R'],'X':c['X'],'dir':c['dir'],'delta':c['delta'],'full':False} for c in M['curves']],open(f'curves_s{t}.json','w'),ensure_ascii=False)
print(t,'駅',len(st),'全長',round(s[-1]/1000,2))
