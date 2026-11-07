from oud_parse import parse,kids
from collections import defaultdict
def sec(t):
    if not t: return None
    t=t.zfill(6) if len(t)>4 else t.zfill(4)+'00'
    return int(t[:2])*3600+int(t[2:4])*60+int(t[4:6])
def trains(path, want):
    r=parse(path); ro=kids(r,'Rosen')[0]; eki=[e['Ekimei'] for e in kids(ro,'Eki')]; syu=kids(ro,'Ressyasyubetsu')
    out=[]
    for dia in kids(ro,'Dia'):
        for dirn in ('Kudari','Nobori'):
            for d in kids(dia,dirn):
                for x in kids(d,'Ressya'):
                    name=syu[int(x.get('Syubetsu',0))].get('Syubetsumei')
                    if name not in want: continue
                    cells=x.get('EkiJikoku','').split(',')
                    idx=range(len(cells)) if dirn=='Kudari' else range(len(cells))
                    seq=[]
                    for i,c in enumerate(cells):
                        if not c: continue
                        kind,_,rest=c.partition(';'); tm,_,trk=rest.partition('$')
                        a,_,dp=tm.partition('/') if '/' in tm else (tm,'','')
                        if '/' not in tm: a,dp=('',tm) if True else (tm,'')
                        st=eki[i] if dirn=='Kudari' else eki[len(eki)-1-i]
                        seq.append((i,st,kind,sec(a),sec(dp)))
                    out.append((dirn,name,x.get('Ressyabangou',''),x.get('Ressyamei',''),seq))
    return out
