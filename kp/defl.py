import json,math,numpy as np
a=json.load(open('smooth_60.json')); b=json.load(open('smooth_60m.json'))
r=json.load(open('route_shibetoro_heishi.json')); lat0=r['points'][len(r['points'])//2][1]; K=111320*math.cos(math.radians(lat0))
xy=lambda q:np.array([[p[0]*K,p[1]*110570] for p in q])
A=xy(a['ips']); B=xy(b['ips']); print(len(A),len(B))
def D(V):
  out=[0.0]
  for i in range(1,len(V)-1):
    u=V[i]-V[i-1]; w=V[i+1]-V[i]
    if np.hypot(*u)<1e-6 or np.hypot(*w)<1e-6: out.append(0.0); continue
    t=math.degrees(math.atan2(u[0]*w[1]-u[1]*w[0],u@w)); out.append(t if abs(t)<150 else 0.0)
  return np.array(out+[0.0])
da=D(A); db=D(B); inc=np.abs(db)-np.abs(da)
print("合計 前 %.0f 新 %.0f"%(np.abs(da).sum(),np.abs(db).sum()))
mv=np.hypot(*(B-A).T)
# S字（隣の交点と曲がる向きが逆）かどうか
s=np.sign(da); S=np.array([i>0 and i<len(da)-1 and (s[i]*s[i-1]<0 or s[i]*s[i+1]<0) for i in range(len(da))])
print("増分の合計 %.0f°  うちS字の交点 %.0f°（交点の数 %d/%d）  同じ向きが続く交点 %.0f°"%(inc.sum(),inc[S].sum(),S.sum(),len(S),inc[~S].sum()))
# 交点の移動量と増分
print("移動量 中央値 %.1f m 最大 %.1f m"%(np.median(mv[mv>0]),mv.max()))
# 5交点の窓で増分の大きい所
W=5; sc=[(inc[i:i+W].sum(),i) for i in range(len(inc)-W)]; sc.sort(reverse=True)
# 元の経路でのキロ程
P=np.array([[p[0]*K,p[1]*110570] for p in r['points']]); cum=np.concatenate([[0],np.cumsum(np.hypot(*np.diff(P,axis=0).T))])
used=[]
for v,i in sc:
  if any(abs(i-j)<W for j in used): continue
  used.append(i); k=int(np.argmin(np.hypot(*(P-A[i+2]).T)))
  near=min(r['stations'],key=lambda s:abs(s[1]-cum[k]))
  print("交点 %d〜%d  増分 %+.0f°  %.1f km（%s 付近）"%(i,i+W-1,v,cum[k]/1000,near[0]))
  print("   前 ",np.round(da[i:i+W],1)," 新 ",np.round(db[i:i+W],1)," 移動 ",np.round(mv[i:i+W],0))
  if len(used)>=6: break
print("---- 兵至平付近")
for i in range(len(A)):
  k=int(np.argmin(np.hypot(*(P-A[i]).T)))
  if cum[k]>222000: print(i,"%.1f km"%(cum[k]/1000),"前 %+.1f 新 %+.1f 増 %+.1f 移動 %.0f m S字 %s"%(da[i],db[i],inc[i],mv[i],S[i]))
