# ground elevation along a route, every STEP m, from GSI elevation tiles (dem_png, zoom 14; DEM10B)
import os, json,math,os,sys,subprocess
import numpy as np
from PIL import Image
from geo import metres
Z=14; STEP=20.0
def resample(pts,step):
    out=[pts[0]];cum=[0.0];acc=0.0;nxt=step
    for a,b in zip(pts,pts[1:]):
        L=metres(a,b)
        while acc+L>=nxt:
            t=(nxt-acc)/L; out.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))); cum.append(nxt); nxt+=step
        acc+=L
    out.append(pts[-1]); cum.append(acc)
    return out,cum
cache={}
os.makedirs('dem',exist_ok=True)   # 保存先はコミットしないので、新しい複製にはない（2026-11-07、国後島で全点が欠けた）
def tile(x,y):
    if (x,y) in cache: return cache[(x,y)]
    f=f'dem/{Z}_{x}_{y}.png'
    if not os.path.exists(f):
        r=subprocess.run(['curl','-s','-f','-o',f,f'https://cyberjapandata.gsi.go.jp/xyz/dem_png/{Z}/{x}/{y}.png'])
        if r.returncode!=0: cache[(x,y)]=None; return None
    a=np.asarray(Image.open(f).convert('RGB')).astype(np.int64)
    v=a[:,:,0]*65536+a[:,:,1]*256+a[:,:,2]
    h=np.where(v<2**23,v*0.01,np.where(v>2**23,(v-2**24)*0.01,np.nan))
    cache[(x,y)]=h; return h
def elev(lon,lat):
    n=2**Z; fx=(lon+180)/360*n*256; fy=(1-math.log(math.tan(math.radians(lat))+1/math.cos(math.radians(lat)))/math.pi)/2*n*256
    def px(ix,iy):
        h=tile(ix//256,iy//256)
        return np.nan if h is None else h[iy%256,ix%256]
    x0,y0=int(math.floor(fx-0.5)),int(math.floor(fy-0.5)); tx,ty=fx-0.5-x0,fy-0.5-y0
    v=[px(x0,y0),px(x0+1,y0),px(x0,y0+1),px(x0+1,y0+1)]
    if any(np.isnan(v)): return np.nanmean(v) if not all(np.isnan(v)) else np.nan
    return (v[0]*(1-tx)+v[1]*tx)*(1-ty)+(v[2]*(1-tx)+v[3]*tx)*ty
if __name__=='__main__':
    r=json.load(open(sys.argv[1]))
    pts,cum=resample([tuple(p) for p in r['points']],STEP)
    h=[float(elev(lo,la)) for lo,la in pts]
    r.update({'s':cum,'xy':pts,'ground':h})
    json.dump(r,open(sys.argv[2],'w'),ensure_ascii=False)
    g=np.array(h); print('点',len(h),'タイル',len(cache),'欠け',int(np.isnan(g).sum()),'標高 最低',round(np.nanmin(g),1),'最高',round(np.nanmax(g),1))
