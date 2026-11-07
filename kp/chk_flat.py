import json,sys
for t in sys.argv[1:]:
    for f in (f"design_f{t}_free.json", f"design_f{t}.json"):
        try: d=json.load(open(f))
        except Exception as e: print(f, "なし"); continue
        out=[]
        for n,c in d["stations"]:
            i=min(range(len(d["s"])),key=lambda j:abs(d["s"][j]-c)); g=d["ground"][i]
            if g is None: continue
            h=d["z"][i]-g; out.append(f"{n} {h:+.1f}{' ×' if not -10<=h<=12 else ''}")
        print(f, round(d["s"][-1]/1000,2),"km:", "、".join(out))
