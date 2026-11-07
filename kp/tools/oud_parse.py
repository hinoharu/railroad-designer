import sys,re,json
def parse(path):
    lines=open(path,encoding='utf-8-sig').read().splitlines()
    root={'_t':'root','_c':[]}; st=[root]
    for ln in lines:
        if ln.endswith('.') and '=' not in ln and ln!='.':
            n={'_t':ln[:-1],'_c':[]}; st[-1]['_c'].append(n); st.append(n)
        elif ln=='.':
            if len(st) > 1: st.pop()   # 最上位の余分な「.」は読み飛ばす（generated のダイヤ）
        elif '=' in ln:
            k,v=ln.split('=',1); st[-1].setdefault(k,[]).append(v) if False else st[-1].__setitem__(k, st[-1].get(k)+[v] if isinstance(st[-1].get(k),list) else ([st[-1][k],v] if k in st[-1] else v))
    return root
def kids(n,t): return [c for c in n['_c'] if c['_t']==t]
if __name__=='__main__':
    r=parse(sys.argv[1]); rosen=kids(r,'Rosen')[0]
    eki=kids(rosen,'Eki'); syu=kids(rosen,'Ressyasyubetsu')
    print('駅',len(eki)); print(' '.join(e['Ekimei'] for e in eki))
    print('種別',[s.get('Syubetsumei') for s in syu])
    for dia in kids(rosen,'Dia'):
        print('ダイヤ',dia.get('DiaName'))
        for dirn in ('Kudari','Nobori'):
            for d in kids(dia,dirn):
                rs=kids(d,'Ressya'); from collections import Counter
                print(' ',dirn,len(rs),Counter(syu[int(x.get('Syubetsu',0))].get('Syubetsumei') for x in rs))
