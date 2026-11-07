# 地形への干渉の集計：トンネル・橋梁の延長、切土・盛土の量（構造物の区間を除く。高さの差 × 距離、m²）、最も深い切土
import json,sys
import numpy as np
for f in sys.argv[1:]:
    d=json.load(open(f)); s=np.array(d['s']); g=np.array(d['ground'],float); z=np.array(d['z']); st=np.array(list(d['struct']))
    ds=np.gradient(s); h=z-g; ok=~np.isnan(h)
    cut=(st=='-')&(h<0)&ok; fill=(st=='-')&(h>0)&ok
    print(f"{f:22s} トンネル {np.sum(ds[st=='T'])/1000:5.1f} km  橋梁 {np.sum(ds[st=='B'])/1000:5.1f} km  切土 {np.sum(-h[cut]*ds[cut])/1e3:6.0f}×10³ m²（最深 {(-h[cut]).max() if cut.any() else 0:4.1f} m）  盛土 {np.sum(h[fill]*ds[fill])/1e3:6.0f}×10³ m²")
