from pathlib import Path
import numpy as np, json, zipfile
import matplotlib.pyplot as plt
ROOT=Path('/mnt/data/adrianic_v3_21_latent_common_cause'); ROOT.mkdir(exist_ok=True)
S=['A','B','C1','C2','C3','D','E','F']; I={s:i for i,s in enumerate(S)}
class World:
 def __init__(self,seed,scenario): self.r=np.random.default_rng(seed); self.scenario=scenario
 def bern(self,p,y): return y if self.r.random()<p else -y
 def report(self,y,t):
  r=self.r; v={'A':self.bern(.91,y),'B':self.bern(.78,y),'D':self.bern(.72,y),'E':self.bern(.84,y),'F':self.bern(.88,y)}
  parent=self.bern(.27,y)
  for c in ['C1','C2','C3']:
   z=parent if r.random()>.08 else -parent; v[c]=z
  if self.scenario=='common_mode' and r.random()<.2:
   for s in ['A','B','D','E']: v[s]=-y
  elif self.scenario=='factor_reversal':
   grp=['A','B','D','E'] if t<600 else ['A','C1','D','F']
   if r.random()<.2:
    for s in grp:v[s]=-y
  amp={'A':(.72,.98),'B':(.55,.95),'C1':(.74,.99),'C2':(.74,.99),'C3':(.74,.99),'D':(.45,.92),'E':(.62,.96),'F':(.68,.97)}
  return {s:float(v[s]*(amp[s][0]+(amp[s][1]-amp[s][0])*r.random())) for s in S}
class Ctl:
 def __init__(self,mode,vp,seed):
  self.mode=mode; self.vp=vp; self.r=np.random.default_rng(seed); n=len(S)
  self.rho=np.ones(n)*.5; self.bias=np.zeros(n); self.mu=np.zeros(n); self.cov=np.eye(n)*1e-3; self.nv=0; self.group=set(); self.groups=[]; self.load=np.zeros(n); self.loads=[]; self.strength=0
 def update(self,reps,y):
  if self.r.random()>=self.vp:return
  e=np.array([reps[s]-y for s in S]); q=np.exp(-np.abs(e)/.8); self.rho=.94*self.rho+.06*q; self.bias=.94*self.bias+.06*e
  self.mu=.945*self.mu+.055*e; d=e-self.mu; self.cov=.945*self.cov+.055*np.outer(d,d); self.nv+=1
  if self.nv>=8 and self.mode in ('graph','factor','multifactor'):
   if self.mode=='graph': self.learn_graph()
   elif self.mode=='factor': self.learn_factor()
   else:self.learn_multifactor()
 def corr(self):
  sd=np.sqrt(np.maximum(np.diag(self.cov),1e-9)); return np.clip(self.cov/(sd[:,None]*sd[None,:]+1e-12),-1,1)
 def learn_graph(self):
  C=self.corr(); adj={s:set() for s in S}
  for i,a in enumerate(S):
   for j in range(i+1,len(S)):
    if C[i,j]>.72: adj[a].add(S[j]);adj[S[j]].add(a)
  comps=[];seen=set()
  for s in S:
   if s in seen:continue
   st=[s];c=set()
   while st:
    x=st.pop();
    if x in seen:continue
    seen.add(x);c.add(x);st.extend(adj[x]-seen)
   comps.append(c)
  self.comps=comps
 def learn_factor(self):
  vals,vecs=np.linalg.eigh(self.cov); o=np.argsort(vals)[::-1]; vals=vals[o];v=vecs[:,o[0]]; self.load=np.abs(v); base=np.median(vals[1:])+1e-9; self.strength=max(0,float((vals[0]-base)/(vals[0]+1e-9))); mx=self.load.max()+1e-12
  g={S[i] for i,l in enumerate(self.load) if l/mx>.55}; self.group=g if len(g)>=2 and self.strength>.28 else set()
 def learn_multifactor(self):
  vals,vecs=np.linalg.eigh(self.cov);o=np.argsort(vals)[::-1];vals=vals[o];vecs=vecs[:,o];base=np.median(vals[3:])+1e-9 if len(vals)>3 else 1e-9
  groups=[];loads=[]
  for k in range(min(3,len(S))):
   strength=max(0,float((vals[k]-base)/(vals[k]+1e-9)))
   v=np.abs(vecs[:,k]);mx=v.max()+1e-12;g={S[i] for i,l in enumerate(v) if l/mx>.58}
   if len(g)>=2 and strength>.22 and not any(len(g&h)/len(g|h)>.75 for h in groups):
    groups.append(g);loads.append((v,strength))
  self.groups=groups;self.loads=loads
  if groups:self.group=groups[0];self.load=loads[0][0];self.strength=loads[0][1]
 def cap(self,raw,g):
  ns=[s for s in g if s in raw]
  if len(ns)<=1:return
  total=sum(raw[s] for s in ns);cap=max(raw[s] for s in ns);f=cap/(total+1e-12)
  for s in ns:raw[s]*=f
 def decide(self,reps,oracle=None):
  raw={s:(1. if self.mode=='equal' else float(self.rho[I[s]]**3)) for s in S}
  if self.mode=='oracle':
   for g in oracle:self.cap(raw,g)
  elif self.mode=='graph' and hasattr(self,'comps'):
   for g in self.comps:self.cap(raw,g)
  elif self.mode=='factor' and self.group:
   self.cap(raw,self.group);mx=max(self.load[I[s]] for s in self.group)+1e-12
   for s in self.group:raw[s]/=(1+1.6*self.strength*self.load[I[s]]/mx)
  elif self.mode=='multifactor' and self.groups:
   for g,(load,strength) in zip(self.groups,self.loads):
    self.cap(raw,g);mx=max(load[I[s]] for s in g)+1e-12
    for s in g:raw[s]/=(1+1.15*strength*load[I[s]]/mx)
  z=sum(raw.values())+1e-12;w={s:raw[s]/z for s in S};deb={s:reps[s]-(0 if self.mode=='equal' else self.bias[I[s]]) for s in S};U=sum(w[s]*deb[s] for s in S);dis=sum(w[s]*(deb[s]-U)**2 for s in S);hold=abs(U)<.1 or dis>.68; return (0 if hold else (1 if U>=0 else -1)),hold,w
class Mem:
 def __init__(self):self.sl=[];self.bad=0;self.writes=0
 def write(self,y,a,h,c):
  if h or c<.34:return
  self.writes+=1;self.bad+=int(a!=y);self.sl.append((y,a,c));self.sl=sorted(self.sl,key=lambda x:x[2],reverse=True)[:12]
 def recall(self,y):
  z=[x for x in self.sl if x[0]==y]
  if not z:return None
  return 1 if sum(a*c for _,a,c in z)>=0 else -1
MODES=['equal','scalar','graph','factor','multifactor','oracle']
def oracle_groups(sc,t):
 g=[{'C1','C2','C3'}]
 if sc=='common_mode':g.append({'A','B','D','E'})
 if sc=='factor_reversal':g.append({'A','B','D','E'} if t<600 else {'A','C1','D','F'})
 return g
def run(seed,sc,mode,vp=.1,T=1200):
 rng=np.random.default_rng(seed+99);w=World(seed,sc);c=Ctl(mode,vp,seed+7);m=Mem();y=1;ok=[];post=[];holds=[];matches=[]
 for t in range(T):
  if t and t%80==0 and rng.random()<.62:y=-y
  reps=w.report(y,t);a,h,ww=c.decide(reps,oracle_groups(sc,t) if mode=='oracle' else None)
  if h:
   r=m.recall(y);a=r if r is not None else (1 if rng.random()<.5 else -1)
  ok.append(int(a==y));post.append(int(a==y)) if t>=600 else None;holds.append(h);c.update(reps,y);m.write(y,a,h,max(ww.values()))
  if mode in ('factor','multifactor') and (c.group or c.groups):
   true={'A','B','D','E'} if sc=='common_mode' else ({'A','B','D','E'} if t<600 else {'A','C1','D','F'}) if sc=='factor_reversal' else set()
   if true:
    gs=c.groups if mode=='multifactor' and c.groups else [c.group]
    matches.append(max(len(g&true)/len(g|true) for g in gs if g))
 return {'acc':np.mean(ok),'post':np.mean(post) if post else np.nan,'hold':np.mean(holds),'bad':m.bad/max(1,m.writes),'match':np.mean(matches[-200:]) if matches else np.nan,'group':sorted(c.group),'load':c.load.tolist(),'corr':c.corr().tolist(),'strength':c.strength}
def agg(sc):
 out=[]
 for mode in MODES:
  vals=[run(1000+s,sc,mode) for s in range(14)]
  out.append({'scenario':sc,'mode':mode,'accuracy':float(np.median([v['acc'] for v in vals])),'post_accuracy':float(np.median([v['post'] for v in vals])),'bad_write_fraction':float(np.median([v['bad'] for v in vals])),'factor_match':float(np.nanmedian([v['match'] for v in vals])) if mode in ('factor','multifactor') else None})
 return out
summary=[]
for sc in ['independent','common_mode','factor_reversal']:summary+=agg(sc)
sweep=[]
for vp in [0,.02,.05,.1,.2,.3]:
 vals=[run(4000+s,'common_mode','multifactor',vp) for s in range(12)];sweep.append({'verify_prob':vp,'accuracy':float(np.median([v['acc'] for v in vals])),'factor_match':float(np.nanmedian([v['match'] for v in vals])) if vp>0 else 0.0,'bad_write_fraction':float(np.median([v['bad'] for v in vals]))})
rep=run(4242,'common_mode','multifactor',.1)
# plots
C=np.array(rep['corr']);plt.figure(figsize=(7,5.5));plt.imshow(C,vmin=-1,vmax=1);plt.xticks(range(len(S)),S);plt.yticks(range(len(S)),S);plt.colorbar();plt.title('Verified residual correlation');plt.tight_layout();plt.savefig(ROOT/'residual_correlation.png',dpi=180);plt.close()
plt.figure(figsize=(7,4.4));plt.bar(S,rep['load']);plt.ylabel('|top factor loading|');plt.title('Learned hidden-factor exposure');plt.tight_layout();plt.savefig(ROOT/'latent_factor_loadings.png',dpi=180);plt.close()
for sc in ['independent','common_mode','factor_reversal']:
 rows=[r for r in summary if r['scenario']==sc];plt.figure(figsize=(8,4.4));plt.bar([r['mode'] for r in rows],[r['accuracy'] for r in rows]);plt.ylim(0,1.05);plt.ylabel('accuracy');plt.title(sc);plt.tight_layout();plt.savefig(ROOT/f'{sc}_accuracy.png',dpi=180);plt.close()
plt.figure(figsize=(7,4.4));plt.plot([r['verify_prob'] for r in sweep],[r['accuracy'] for r in sweep],marker='o',label='accuracy');plt.plot([r['verify_prob'] for r in sweep],[r['factor_match'] for r in sweep],marker='o',label='factor match');plt.ylim(0,1.05);plt.legend();plt.xlabel('verification probability');plt.title('Hidden common-cause learning');plt.tight_layout();plt.savefig(ROOT/'verification_factor_sweep.png',dpi=180);plt.close()
rows=[r for r in summary if r['scenario']=='common_mode'];plt.figure(figsize=(8,4.4));plt.bar([r['mode'] for r in rows],[r['bad_write_fraction'] for r in rows]);plt.ylabel('bad durable-write fraction');plt.title('Common-mode memory contamination');plt.tight_layout();plt.savefig(ROOT/'common_mode_bad_writes.png',dpi=180);plt.close()
res={'summary':summary,'verification_sweep':sweep,'representative':{'group':rep['group'],'factor_strength':rep['strength'],'loadings':dict(zip(S,rep['load']))},'guardrails':['Latent-factor inference uses sparse verified residual covariance; it is not proof of causal direction.','The loading threshold and factor-strength threshold are hand-set.','Without independent verification the hidden factor cannot be grounded.','If every evidence source and verifier share the same hidden failure, the model cannot manufacture truth.']}
(ROOT/'results.json').write_text(json.dumps(res,indent=2));(ROOT/'V321_SPEC.md').write_text('Adrianic v3.21: top-eigenvector latent common-cause model over verified source residual covariance; compared with equal, scalar trust, hard graph, and oracle grouping.\n');(ROOT/'README.md').write_text('v3.21 latent common-cause experiment. See results.json and plots.\n')
zp=Path('/mnt/data/adrianic_v3_21_latent_common_cause.zip');
with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
 for fp in ROOT.rglob('*'):
  if fp.is_file():z.write(fp,fp.relative_to(ROOT.parent))
print('SUMMARY')
for r in summary:print(r)
print('SWEEP')
for r in sweep:print(r)
print('REP',res['representative'])
print('ZIP',zp)
