# the route of a train along the drawn track: station-to-station pieces of the drawn lines, joined by shortest paths
import json,sys,heapq,re,math
from geo import metres, project
d=json.load(open(__import__('geo').FICTION_JSON,encoding='utf-8'));S=d['stations']
def dec(e):
    out=[];x=y=0
    for i in range(0,len(e),2): x+=e[i];y+=e[i+1]; out.append((x/1e5,y/1e5))
    return out
E={}  # (a,b) -> (length, points from a to b)
for k,e in d['lines']:
    L=dec(e); cum=[0]
    for a,b in zip(L,L[1:]): cum.append(cum[-1]+metres(a,b))
    pos=[]
    for i,s in enumerate(S):
        if k not in s[6]: continue
        p=(s[3]/1e5,s[2]/1e5)
        best=min(((project(p,a,b)[1],j,a,b) for j,(a,b) in enumerate(zip(L,L[1:]))),key=lambda x:x[0])
        if best[0]>12: continue
        q,_=project(p,best[2],best[3]); pos.append((cum[best[1]]+metres(best[2],q),best[1],q,i))
    pos.sort()
    for (p1,j1,q1,i1),(p2,j2,q2,i2) in zip(pos,pos[1:]):
        pts=[q1]+L[j1+1:j2+1]+[q2]
        w=p2-p1
        if w<=0: continue
        if (i1,i2) not in E or E[(i1,i2)][0]>w:
            E[(i1,i2)]=(w,pts); E[(i2,i1)]=(w,pts[::-1])
G={}
for (a,b),(w,_) in E.items(): G.setdefault(a,{})[b]=w
def idx(isl,name):
    for i,s in enumerate(S):
        if s[5]==isl and re.sub('(信号場|仮乗降場)$','',s[0])==name: return i
    raise KeyError(name)
def sp(a,b):
    dist={a:0};prev={};pq=[(0,a)]
    while pq:
        dd,u=heapq.heappop(pq)
        if u==b: break
        if dd>dist[u]: continue
        for v,w in G.get(u,{}).items():
            if dd+w<dist.get(v,1e18): dist[v]=dd+w; prev[v]=u; heapq.heappush(pq,(dist[v],v))
    seq=[b]
    while seq[-1]!=a: seq.append(prev[seq[-1]])
    return seq[::-1]
def route(isl,stops):
    ids=[idx(isl,s) for s in stops]; seq=[ids[0]]
    for a,b in zip(ids,ids[1:]): seq+=sp(a,b)[1:]
    pts=[];stations=[];ch=0.0;vidx=[]
    for a,b in zip(seq,seq[1:]):
        w,p=E[(a,b)]
        if not pts: pts=list(p); stations.append((S[a][0],0.0)); vidx.append(0)
        else: pts+=p[1:]
        ch+=w; stations.append((S[b][0],ch)); vidx.append(len(pts)-1)
    return pts,stations,[S[i][0] for i in ids],vidx
if __name__=='__main__':
    stops='蘂取・乙今牛・浜中・瀬石温泉・紗那・南留別・類平・振別・老門・択捉神居古潭・満前・択捉六甲・両牛・兵至平'.split('・')
    pts,st,stopnames,vidx=route('択捉',stops)
    json.dump({'points':pts,'stations':st,'stops':stopnames,'vidx':vidx},open('route_shibetoro_heishi.json','w'),ensure_ascii=False)
    print(len(pts),'点',round(st[-1][1]/1000,1),'km 駅',len(st))
    for n,c in st: print(f'  {c/1000:7.2f} km {n}{" ★停車" if n in stopnames else ""}')
