# running time of an express (KiHa 283 like: tilting DMU, 130 km/h) along a designed route
import json,math,sys
import numpy as np
from scipy.ndimage import median_filter,minimum_filter1d
import os
# 線区ごとの条件（2026-11-04）：環境変数 VMAX（km/h）・TRAIN（m）。指定がなければ択捉の特急（130 km/h・8 両 160 m）
VMAX=float(os.environ.get('VMAX','130'))/3.6
TRAIN=float(os.environ.get('TRAIN','160'))  # m: a limit is kept until the rear has left it
C_CANT,C_DEF=105,60  # mm: cant and cant deficiency (本則)
TILT=30/3.6          # 振子: 本則 + 30 km/h
A_ADH=0.55           # m/s2: starting acceleration (about 2.0 km/h/s)
P_PER_T=365e3/48e3   # W per kg-ish: 365 kW at the rail per car of 48 t
MEFF=1.08            # rotating masses
# 車両ごとの性能（2026-11-05、ユーザーの指定：重連の性能で確かめる）：列車全体のレールでの出力 P_KW（kW）、重さ MASS_T（t）、最大引張力 FMAX_KN（kN）を
# 環境変数で与えると、上の 1 両あたりの値の代わりに使う（出力÷重さ、起動の加速度＝最大引張力÷重さ）。与えないときはキハ283系相当のまま
if os.environ.get('P_KW'):
    _M = float(os.environ['MASS_T']) * 1e3
    P_PER_T = float(os.environ['P_KW']) * 1e3 / _M
    A_ADH = float(os.environ['FMAX_KN']) * 1e3 / _M
BRAKE=0.75           # m/s2 (2.7 km/h/s)
DWELL=45             # s at each stop on the way
DWELL_REV=300        # s at a stop where the train reverses (a switchback: 紗那 about 5 min, user)
TURNOUT=45/3.6       # the diverging side of a turnout
DS=10.0
# fixed limits that replace the curve limits over a stretch: (station, from m, to m past it, km/h). 紗那: the branch
# joining just past the station is drawn badly (a quick left then right); the user takes it as 45 km/h
FIXED=[('紗那',0.0,1000.0,45.0)]
def resist(v,R):     # m/s2: running resistance (kgf/t, v in km/h) and curve resistance 700/R kgf/t
    vk=v*3.6
    r=1.6+0.03*vk+0.0003*vk*vk+(700/R if R<5000 else 0)
    return r*9.81/1000
def simulate(d,turnout=False,curves=None):
    s=np.array(d['s']); z=np.array(d['z'])
    x=np.arange(0,s[-1],DS); x=np.append(x,s[-1])
    zx=np.interp(x,s,z)
    if curves is None:
        R=np.array([x_ if x_ else 1e9 for x_ in d['R']],float); R=median_filter(R,5,mode='nearest'); Rx=np.interp(x,s,R)
    else:   # one radius over each curve (its transitions included)
        Rx=np.full(len(x),1e9)
        for c in curves:
            m=(x>=c['s0'])&(x<=c['s1']); Rx[m]=np.minimum(Rx[m],c['R'])
    grade=np.gradient(zx,x)
    from speed import limit
    vl=np.minimum(VMAX,limit(Rx)/3.6)  # curve limit (m/s): speed.py（半径 600 m 以上は本則＋30、未満は振子式のカント不足量、5 km/h 単位に切り捨て）
    pos=dict(d['stations'])
    for n,a,b,v in FIXED:
        if n in pos:
            m=(x>=pos[n]+a)&(x<=pos[n]+b); vl[m]=v/3.6
    stops=[c for n,c in d['stations'] if n in d['stops']]
    if turnout:
        for c in stops:
            vl[(x>=c-110)&(x<=c+110)]=np.minimum(vl[(x>=c-110)&(x<=c+110)],TURNOUT)
    simulate.vl = vl.copy()  # 線路そのものの制限（列車の長さを考える前。標識の位置に使う）
    # a limit holds for the head until the rear has passed: min over the TRAIN behind
    w=int(TRAIN/DS)
    vh=np.array([vl[max(0,i-w):i+1].min() for i in range(len(x))])
    stop_i=[int(np.argmin(np.abs(x-c))) for c in stops]
    cap=vh.copy()
    for i in stop_i: cap[i]=0.0
    # braking curve (backward)
    for i in range(len(x)-2,-1,-1):
        cap[i]=min(cap[i],math.sqrt(cap[i+1]**2+2*BRAKE*(x[i+1]-x[i])))
    # acceleration (forward)
    v=np.zeros(len(x)); 
    for i in range(len(x)-1):
        if i in stop_i: v[i]=0.0
        a=min(A_ADH,P_PER_T/max(v[i],1.0))/MEFF-resist(v[i],Rx[i])-9.81*grade[i]
        nv=math.sqrt(max(0.0,v[i]**2+2*a*(x[i+1]-x[i])))
        v[i+1]=min(nv,cap[i+1])
        if v[i+1]<0.5 and (i+1) not in stop_i: v[i+1]=min(cap[i+1],0.5)
    # time
    t=np.zeros(len(x))
    for i in range(len(x)-1):
        vm=(v[i]+v[i+1])/2
        t[i+1]=t[i]+(x[i+1]-x[i])/max(vm,0.3)
    return x,v,t,stop_i,stops,vh
def reversals(d):
    """the stops where the route turns back (the directions in and out more than 150 degrees apart)"""
    pts=d['points']; out=[]
    for (n,_),v in zip(d['stations'],d['vidx']):
        if n not in d['stops'] or v<=0 or v>=len(pts)-1: continue
        def dirn(a,b):
            k=math.cos(math.radians(a[1])); return math.atan2(b[1]-a[1],(b[0]-a[0])*k)
        # the directions are measured to points at least 50 m away (not the next point: the station's point is put back at the
        # station itself, which can bend the last few metres of a finely spaced alignment)
        def far(i,step):
            k=math.cos(math.radians(pts[v][1]))
            while 0<i<len(pts)-1 and math.hypot((pts[i][0]-pts[v][0])*k*111320,(pts[i][1]-pts[v][1])*110570)<50: i+=step
            return i
        i=far(v-1,-1); j=far(v+1,1)
        a1=dirn(pts[i],pts[v]); a2=dirn(pts[v],pts[j])
        if abs(math.degrees(math.atan2(math.sin(a2-a1),math.cos(a2-a1))))>150: out.append(n)
    return out
if __name__=='__main__':
    d=json.load(open(sys.argv[1]))
    res={}
    cv=json.load(open(sys.argv[3])) if len(sys.argv)>3 else None
    for case,to in (('A',False),('B',True)):
        x,v,t,si,stops,vh=simulate(d,to,cv)
        legs=[];tot=0
        for a,b in zip(si,si[1:]):
            legs.append(t[b]-t[a])
        rev=reversals(d)
        dw=[DWELL_REV if n in rev else DWELL for n in d['stops'][1:-1]]
        run=sum(legs); total=run+sum(dw)
        res[case]=(legs,run,total,v,x)
    names=d['stops']
    print('区間                 距離    A走行  B走行')
    for k,(a,b) in enumerate(zip(names,names[1:])):
        dist=(dict(d['stations'])[b]-dict(d['stations'])[a])/1000 if False else None
    st=[c for n,c in d['stations'] if n in names]
    for k in range(len(names)-1):
        print(f"{names[k]}→{names[k+1]:6s} {(st[k+1]-st[k])/1000:6.1f}km {res['A'][0][k]/60:6.1f}分 {res['B'][0][k]/60:6.1f}分")
    for c in 'AB':
        legs,run,total,v,x=res[c]
        print(f"{c}: 走行 {run/60:.1f} 分 + 停車 {(total-run)/60:.1f} 分（折り返し {'・'.join(reversals(d)) or 'なし'} は {DWELL_REV//60} 分、ほかは {DWELL} 秒） = {total/60:.1f} 分、表定 {x[-1]/1000/(total/3600):.1f} km/h、最高 {v.max()*3.6:.0f} km/h、130 km/h で走る距離 {np.sum(v>=VMAX-0.1)*DS/1000:.1f} km")
    json.dump({'x':res['A'][4].tolist(),'vA':(res['A'][3]*3.6).tolist(),'vB':(res['B'][3]*3.6).tolist()},open(sys.argv[2],'w'))
