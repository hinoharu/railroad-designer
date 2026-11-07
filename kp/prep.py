# the data of the alignment drawing (one JSON): stations, grades, curves, structures, limits, speeds, times
import json,math,sys
import numpy as np
import run
D=json.load(open(sys.argv[1] if len(sys.argv)>1 else 'design_mu30_nu20.json')); C=json.load(open(sys.argv[2] if len(sys.argv)>2 else 'curves_shibetoro_heishi.json'))
S=json.load(open(__import__('geo').FICTION_JSON,encoding='utf-8'))['stations']
kind={s[0]:s[4] for s in S if s[5]=='択捉'}; kana={s[0]:s[1] for s in S if s[5]=='択捉'}
s=np.array(D['s']); g=np.array(D['ground']); z=np.array(D['z']); sn=np.array(D['sn']); zn=np.array(D['zn'])
# grades: 100 m pieces, joined while the grade stays within 0.3 per mille
gr=np.diff(zn)/np.diff(sn)*1000; grades=[]
for k in range(len(gr)):
    if grades and abs(grades[-1][2]-gr[k])<0.3 and (grades[-1][1]-grades[-1][0])>0:
        L0=grades[-1][1]-grades[-1][0]; L1=sn[k+1]-sn[k]
        grades[-1]=[grades[-1][0],float(sn[k+1]),(grades[-1][2]*L0+gr[k]*L1)/(L0+L1)]
    else: grades.append([float(sn[k]),float(sn[k+1]),float(gr[k])])
grades=[[a,b,round(v,1)] for a,b,v in grades]
# structures: runs of B / T at 20 m, those under 40 m dropped
st=D['struct']; runs=[];i=0
while i<len(st):
    if st[i] in 'BT':
        j=i
        while j<len(st) and st[j]==st[i]: j+=1
        a,b=s[i],s[min(j,len(s)-1)]
        if b-a>=40: runs.append([st[i],float(a),float(b)])
        i=j
    else: i+=1
# limits and speeds (case A: the stops on the straight side), and case B
x,vA,t,si,stops,vh=run.simulate(D,False,C)
_,vB,tB,_,_,_=run.simulate(D,True,C)
lim=[];vk=np.round(vh*3.6/5)*5
for i in range(len(x)):
    if lim and lim[-1][2]==vk[i]: lim[-1][1]=float(x[i])
    else: lim.append([float(x[i]),float(x[i]),float(vk[i])])
step=5
rev=run.reversals(D)
dwell=[0]+[run.DWELL_REV if n in rev else run.DWELL for n in D['stops'][1:-1]]+[0]
# times: arrival and departure at each stop (from the start, s)
arr=[];dep=[];acc=0.0
for k,i in enumerate(si):
    if k==0: arr.append(None); dep.append(0.0); continue
    acc+=t[si[k]]-t[si[k-1]]; arr.append(acc); acc+=dwell[k]; dep.append(acc if k<len(si)-1 else None)
out={'route':'蘂取 → 兵至平','length':float(s[-1]),
 'stations':[{'n':n,'s':float(c),'k':kind.get(n,'駅'),'kana':kana.get(n,''),'stop':n in D['stops'],'rev':n in rev} for n,c in D['stations']],
 'stops':[{'n':n,'s':float(x[i]),'arr':a,'dep':b} for n,i,a,b in zip(D['stops'],si,arr,dep)],
 'ground':[[float(a),round(float(b),1)] for a,b in zip(s[::5],g[::5])],
 'z':[[float(a),round(float(b),2)] for a,b in zip(sn,zn)],
 'grades':grades,'curves':[{'s0':c['s0'],'s1':c['s1'],'R':round(c['R']),'X':round(c['X']),'d':c['dir'],'delta':round(c['delta'],1),'full':c['full']} for c in C],
 'struct':runs,'limits':lim,
 'speed':[[float(a),round(float(b)*3.6,1),round(float(c)*3.6,1)] for a,b,c in zip(x[::step],vA[::step],vB[::step])],
 'total':{'A':(t[si[-1]]-t[si[0]]+sum(dwell))/60,'B':(tB[si[-1]]-tB[si[0]]+sum(dwell))/60,'runA':(t[si[-1]]-t[si[0]])/60,'dwell':sum(dwell)/60},
 'assume':{'gmax':15,'ghard':33.3,'cant':run.C_CANT,'def':run.C_DEF,'tilt':30,'vmax':130,'dwell':run.DWELL,'dwell_rev':run.DWELL_REV,'train':run.TRAIN,'bridge':12,'tunnel':15}}
json.dump(out,open('linedata.json','w'),ensure_ascii=False,separators=(',',':'))
print('勾配の区間',len(grades),'曲線',len(C),'構造物',len(runs),'制限の区間',len(lim),'速度の点',len(out['speed']),'所要',round(out['total']['A'],1),'分',
      f"{len(json.dumps(out,ensure_ascii=False))//1024} KB")
