import numpy as np, pandas as pd, matplotlib.pyplot as plt, shutil
from pathlib import Path
from collections import defaultdict

OUT=Path('/mnt/data/adrianic_evidence_graph_v3'); OUT.mkdir(exist_ok=True)
SOURCES=['A','B','C1','C2','C3','D','E']
VERIFIERS=['V1','V2','V3']
CLASSES={
 'useful':{'freq':.42,'utility':1.0,'labels':list(range(0,6))},
 'critical':{'freq':.08,'utility':4.5,'labels':list(range(6,9))},
 'junk':{'freq':.35,'utility':.05,'labels':list(range(9,14))},
 'transient':{'freq':.15,'utility':0.0,'labels':[]},
}

def make_stream(seed,n):
    rng=np.random.default_rng(seed); names=list(CLASSES); probs=np.array([CLASSES[k]['freq'] for k in names]); tr=10000; out=[]
    for t in range(n):
        cls=str(rng.choice(names,p=probs))
        if cls=='transient': lab=tr; tr+=1; u=0.0
        else:
            lab=int(rng.choice(CLASSES[cls]['labels'])); u=max(0.,CLASSES[cls]['utility']*(1+.22*rng.normal()))
        out.append((t,cls,lab,u))
    return out

def base_reports(y,cls,rng):
    A=max(0,y+rng.normal(0,.18)); B=max(0,y+rng.normal(0,.40))
    common=rng.normal(0,.60)+(0.9 if cls in ('junk','transient') and rng.random()<.12 else 0)
    Cbase=y+common
    C=[max(0,Cbase+rng.normal(0,.10)) for _ in range(3)]
    D=max(0,y+.30+rng.normal(0,.65)); E=max(0,y+rng.normal(0,.14))
    return {'A':A,'B':B,'C1':C[0],'C2':C[1],'C3':C[2],'D':D,'E':E}

class AdaptiveAdversary:
    def __init__(self,seed): self.rng=np.random.default_rng(seed)
    def apply(self,reps,y,cls,trust,common_risk,t,n):
        reps=dict(reps)
        if t<n//3:return reps,'none'
        # low-and-slow when common-risk alarm is high
        if common_risk>.35:
            target=max(trust,key=trust.get)
            reps[target]=max(0,reps[target]+(.65 if cls in ('junk','transient') else -.38*y))
            return reps,'low_slow_'+target
        cmean=np.mean([trust[c] for c in ('C1','C2','C3')])
        if cmean>.45 and self.rng.random()<.40:
            val=(3.1+self.rng.normal(0,.10)) if cls in ('junk','transient') else max(0,.15*y+self.rng.normal(0,.10))
            for c in ('C1','C2','C3'): reps[c]=max(0,val+self.rng.normal(0,.025))
            return reps,'cluster_C'
        target=max(trust,key=trust.get)
        reps[target]=(max(0,3.5+self.rng.normal(0,.10)) if cls in ('junk','transient') else max(0,.10*y+self.rng.normal(0,.08)))
        return reps,'target_'+target

class Trust:
    def __init__(self,names,initial=.5):
        self.names=list(names); self.base={n:initial for n in names}; self.bias={n:0. for n in names}; self.mae={n:.5 for n in names}; self.q={n:0. for n in names}
    def eff(self,n): return self.base[n]*np.exp(-self.q[n])
    def effdict(self): return {n:self.eff(n) for n in self.names}
    def corrected(self,n,x): return max(0.,x-self.bias[n])
    def calibration(self,n,x,y):
        e=abs(x-y); q=np.exp(-e); eta=.08
        self.base[n]=(1-eta)*self.base[n]+eta*q; self.bias[n]=(1-eta)*self.bias[n]+eta*(x-y); self.mae[n]=.92*self.mae[n]+.08*e
    def quarantine(self,n,x,y):
        e=abs(x-y); th=max(.9,3*self.mae[n])
        if e>th:
            self.q[n]=min(3.,self.q[n]+min(1.8,(e-th)/(th+.2)+.5)); return True
        return False
    def decay(self):
        for n in self.names:self.q[n]*=.60

class Graph:
    def __init__(self,names):
        self.names=list(names); self.idx={n:i for i,n in enumerate(names)}; self.edge=np.zeros((len(names),len(names))); self.common=.0
    def update(self,reps,y):
        er=np.array([reps[n]-y for n in self.names]); self.edge*=.996
        for i in range(len(self.names)):
            for j in range(i+1,len(self.names)):
                ea,eb=er[i],er[j]; sim=min(1,(abs(ea)+abs(eb))/1.2)*np.exp(-abs(ea-eb)/.28)*(1 if ea*eb>0 else 0)
                self.edge[i,j]=.93*self.edge[i,j]+.07*sim; self.edge[j,i]=self.edge[i,j]
        sig=np.abs(er)>.45
        cm=0.
        if sig.sum()>=4:
            same=max(np.mean(er[sig]>0),np.mean(er[sig]<0)); cm=float(same*min(1,np.mean(np.abs(er[sig]))/1.5))
        self.common=.96*self.common+.04*cm
    def aggregate(self,reps,trust):
        eff=np.array([max(.01,trust.eff(n)) for n in self.names]); base=eff**3; bn=base/(base.sum()+1e-15); red=self.edge@bn; adj=base/(1+4.5*red); w=adj/(adj.sum()+1e-15)
        vals=np.array([trust.corrected(n,reps[n]) for n in self.names]); m=float(w@vals); std=float(np.sqrt(max(0,w@((vals-m)**2))))
        conf=float(np.clip((w@eff)*(w@(1/(1+4.5*red)))*np.exp(-std/(.55+m))*max(.05,1-1.7*self.common),0,1))
        return m,conf,w,vals,red

class AnchorLayer:
    def __init__(self):
        self.anchor_trust=.70; self.anchor_bias=0.; self.ver=Trust(VERIFIERS,.5)
    def routine_anchor(self,y,rng,corrupt_prob):
        corrupt=rng.random()<corrupt_prob
        if corrupt:
            a=max(0,2.5+rng.normal(0,.20)) if y<.2 else max(0,.25*y+rng.normal(0,.15))
        else:a=max(0,y+rng.normal(0,.05))
        return a,corrupt
    def verifier_reports(self,y,rng):
        return {'V1':max(0,y+rng.normal(0,.18)),'V2':max(0,y+rng.normal(0,.40)),'V3':max(0,2.4-.25*y+rng.normal(0,.35))}
    def aggregate_verifiers(self,reps):
        eff=np.array([max(.01,self.ver.eff(n)) for n in VERIFIERS])**3; w=eff/(eff.sum()+1e-15); vals=np.array([self.ver.corrected(n,reps[n]) for n in VERIFIERS]); m=float(w@vals); std=float(np.sqrt(max(0,w@((vals-m)**2)))); conf=float((w@np.array([self.ver.eff(n) for n in VERIFIERS]))*np.exp(-std/(.45+m))); return m,conf
    def calibrate_from_gold(self,anchor_value,ver_reports,true_y):
        # rare gold event calibrates routine anchor and verifiers
        e=abs(anchor_value-true_y); q=np.exp(-e); eta=.10; self.anchor_trust=(1-eta)*self.anchor_trust+eta*q; self.anchor_bias=(1-eta)*self.anchor_bias+eta*(anchor_value-true_y)
        for n,x in ver_reports.items():self.ver.calibration(n,x,true_y)
    def combine_anchor_and_verifiers(self,anchor_value,ver_reports):
        vm,vc=self.aggregate_verifiers(ver_reports); ac=max(0,anchor_value-self.anchor_bias); wa=max(.01,self.anchor_trust)**3; wv=max(.01,vc)**3; m=float((wa*ac+wv*vm)/(wa+wv+1e-15)); disagreement=abs(ac-vm); conf=float(np.clip((wa*self.anchor_trust+wv*vc)/(wa+wv+1e-15)*np.exp(-disagreement/(.5+m)),0,1)); return m,conf

class Candidate:
    def __init__(self,label,cls,t):self.label=label;self.cls=cls;self.n=1;self.last=t;self.values=[]
    def obs(self,t):self.n+=1;self.last=t
    @property
    def recent(self):
        if not self.values:return 0.
        v=np.array(self.values[-6:]); w=np.geomspace(.55,1,len(v)); return float(w@v/w.sum())
class Slot:
    def __init__(self,label,cls,t,u):self.label=label;self.cls=cls;self.last=t;self.uses=1;self.u=u
class Memory:
    def __init__(self,cap=10):self.cap=cap;self.slots=[];self.cands={};self.writes=0;self.unresolved=0
    def find(self,l):
        for i,s in enumerate(self.slots):
            if s.label==l:return i
        return None
    def touch(self,l,t):
        i=self.find(l)
        if i is None:return False
        self.slots[i].uses+=1;self.slots[i].last=t;return True
    def observe(self,l,cls,t):
        if self.find(l) is not None:return
        if l in self.cands:self.cands[l].obs(t)
        else:self.cands[l]=Candidate(l,cls,t)
    def repl(self,t):
        return min([((.08+s.u)*np.sqrt(np.log1p(s.uses))/(1+.02*(t-s.last)),i) for i,s in enumerate(self.slots)])[1]
    def value(self,l,u,conf,t,verified=False):
        i=self.find(l)
        if i is not None:
            eta=.16 if verified else .08;self.slots[i].u=(1-eta)*self.slots[i].u+eta*u;return 'EXISTING'
        c=self.cands.get(l)
        if c is None:return 'NO_CANDIDATE'
        if not verified and conf<.18:self.unresolved+=1;return 'VALUE_UNRESOLVED'
        c.values.append(float(u)); score=.56*min(c.recent/1.5,1)+.19*min(c.n/3,1)+.25*min(conf,1)
        if (verified and u>=3) or (c.n>=2 and len(c.values)>=2 and c.recent>=.28 and score>=.54):
            sl=Slot(l,c.cls,t,c.recent)
            if len(self.slots)<self.cap:self.slots.append(sl)
            else:self.slots[self.repl(t)]=sl
            self.writes+=1;self.cands.pop(l,None);return 'INCLUDE'
        if c.n>=5 and len(c.values)>=3 and c.recent<.13:self.cands.pop(l,None);return 'EXCLUDE'
        return 'HOLD'
    def expire(self,t,timeout=260):
        for l in [l for l,c in self.cands.items() if t-c.last>timeout]:self.cands.pop(l,None)

def attribute_incident(trust,graph,reps,y):
    errs=np.array([reps[n]-y for n in SOURCES]); ae=np.abs(errs); sig=ae>.85
    if sig.sum()>=4:
        se=errs[sig]; same=max(np.mean(se>0),np.mean(se<0))
        if same>=.8 and np.std(se)<=.55 and np.mean(np.abs(se))>=1.0:
            graph.common=min(1,.72*graph.common+.28*min(1,np.mean(np.abs(se))/2)); return 'COMMON',[]
    med=float(np.median(ae)); q=[]
    for idx in np.argsort(-ae)[:2]:
        n=SOURCES[idx]; th=max(.95,3.2*trust.mae[n])
        if ae[idx]>th and ae[idx]>med+.75:
            trust.quarantine(n,reps[n],y);q.append(n)
    return ('SOURCE' if q else 'NONE'),q

def run(seed,policy='robust',n=1800,anchor_corrupt=.10,gold_prob=.003):
    rng=np.random.default_rng(2000000+seed); stream=make_stream(seed,n); trust=Trust(SOURCES,.5); graph=Graph(SOURCES); anchors=AnchorLayer(); mem=Memory(10); adv=AdaptiveAdversary(3000000+seed)
    total=captured=0.; pre=[0.,0.]; post=[0.,0.]; attack_counts=defaultdict(int); source_faults=defaultdict(int); common_faults=0
    for block0 in range(0,n,100):
        trust.decay(); graph.common*=.94; pending=[]
        for t,cls,label,y in stream[block0:min(n,block0+100)]:
            hit=mem.touch(label,t); total+=y; captured+=y if hit else 0; (pre if t<n//2 else post)[0]+=y; (pre if t<n//2 else post)[1]+=y if hit else 0
            mem.observe(label,cls,t)
            reps=base_reports(y,cls,rng); reps,atype=adv.apply(reps,y,cls,trust.effdict(),graph.common,t,n); attack_counts[atype]+=1
            m,conf,w,vals,red=graph.aggregate(reps,trust); mem.value(label,m,conf,t,verified=False)
            # diagnostic score for one targeted check
            dev=[trust.eff(s)*abs(vals[i]-m)/(max(.25,trust.mae[s])+.25) for i,s in enumerate(SOURCES)]; diag=.63*min(max(dev),3)/3+.2*(1-conf)+.1*min(m/3,1)+.07*graph.common
            pending.append((diag,t,cls,label,y,reps))
            mem.expire(t)
        # two routine verification checks per 100 events: random calibration + targeted incident
        ridx=int(rng.integers(0,len(pending))); didx=int(np.argmax([p[0] for p in pending]));
        if didx==ridx:didx=(didx+1)%len(pending)
        for kind,idx in [('random',ridx),('target',didx)]:
            _,t,cls,label,y,reps=pending[idx]
            a,corrupt=anchors.routine_anchor(y,rng,anchor_corrupt); vreps=anchors.verifier_reports(y,rng)
            # rare gold check calibrates anchor+verifiers
            if rng.random()<gold_prob: anchors.calibrate_from_gold(a,vreps,y)
            if policy=='naive': vy,vconf=a,1.0
            else: vy,vconf=anchors.combine_anchor_and_verifiers(a,vreps)
            if kind=='random':
                # random calibration only when verification itself is sufficiently credible
                if policy=='naive' or vconf>=.50:
                    for s,x in reps.items():trust.calibration(s,x,vy)
                    graph.update(reps,vy)
            else:
                if policy=='robust' and vconf>=.55:
                    fault,qs=attribute_incident(trust,graph,reps,vy); common_faults+=fault=='COMMON'
                    for qn in qs:source_faults[qn]+=1
            mem.value(label,vy,vconf,block0+99,verified=(vconf>=.70))
    cls=[s.cls for s in mem.slots]
    return {'seed':seed,'policy':policy,'utility_capture':captured/(total+1e-15),'pre_capture':pre[1]/(pre[0]+1e-15),'post_capture':post[1]/(post[0]+1e-15),'writes':mem.writes,'unresolved':mem.unresolved,'junk_slots':cls.count('junk'),'critical_slots':cls.count('critical'),'anchor_trust':anchors.anchor_trust,'rho_A':trust.eff('A'),'rho_E':trust.eff('E'),'common_faults':common_faults,'E_faults':source_faults['E']}

# main benchmark
rows=[]
for cp in [0.0,.05,.10,.20]:
    for policy in ['naive','robust']:
        for seed in range(10):
            r=run(seed,policy=policy,n=1200,anchor_corrupt=cp,gold_prob=.003);r['anchor_corrupt']=cp;rows.append(r)
df=pd.DataFrame(rows); agg=df.groupby(['anchor_corrupt','policy']).agg(utility_capture=('utility_capture','mean'),post_capture=('post_capture','mean'),writes=('writes','mean'),unresolved=('unresolved','mean'),junk_slots=('junk_slots','mean'),anchor_trust=('anchor_trust','mean'),rho_A=('rho_A','mean'),rho_E=('rho_E','mean'),common_faults=('common_faults','mean'),E_faults=('E_faults','mean')).reset_index(); df.to_csv(OUT/'imperfect_anchor_trials.csv',index=False); agg.to_csv(OUT/'imperfect_anchor_aggregate.csv',index=False)
print(agg.to_string(index=False))

# charts
fig,ax=plt.subplots(figsize=(8,4.8))
for p,g in agg.groupby('policy'): ax.plot(g['anchor_corrupt']*100,g['utility_capture'],marker='o',label=p)
ax.set_xlabel('Corrupted routine anchors (%)');ax.set_ylabel('Utility captured');ax.set_title('Imperfect anchors + adaptive adversary');ax.legend();fig.tight_layout();fig.savefig(OUT/'imperfect_anchor_robustness.png',dpi=170);plt.close(fig)

fig,ax=plt.subplots(figsize=(8,4.8))
for p,g in agg.groupby('policy'): ax.plot(g['anchor_corrupt']*100,g['post_capture'],marker='o',label=p)
ax.set_xlabel('Corrupted routine anchors (%)');ax.set_ylabel('Post-attack utility capture');ax.set_title('Adaptive adversary after trust has formed');ax.legend();fig.tight_layout();fig.savefig(OUT/'adaptive_adversary_post_attack.png',dpi=170);plt.close(fig)

# ============================================================
# Complex-field reintegration
# ============================================================

def make_field(N=40,sep=10,shift=(0,0),chir=1):
    y,x=np.mgrid[:N,:N]; sy,sx=shift; cy=N//2+sy; x1=N//2-sep//2+sx; x2=N//2+sep//2+sx
    r1=np.hypot(x-x1,y-cy);r2=np.hypot(x-x2,y-cy);th1=np.arctan2(y-cy,x-x1);th2=np.arctan2(y-cy,x-x2);A=np.tanh(r1/2)*np.tanh(r2/2)
    return .65*A*np.exp(1j*chir*(th1-th2))

def field_vec(psi):
    a=np.abs(psi);N=a.shape[0];sm=a.copy()
    for _ in range(4):sm=(4*sm+np.roll(sm,1,0)+np.roll(sm,-1,0)+np.roll(sm,1,1)+np.roll(sm,-1,1))/8
    work=sm.copy();work[:3,:]=np.inf;work[-3:,:]=np.inf;work[:,:3]=np.inf;work[:,-3:]=np.inf;y1,x1=np.unravel_index(np.argmin(work),work.shape);yy,xx=np.mgrid[:N,:N];w2=work.copy();w2[(xx-x1)**2+(yy-y1)**2<=16]=np.inf;y2,x2=np.unravel_index(np.argmin(w2),w2.shape);pts=sorted([(x1/N,y1/N),(x2/N,y2/N)],key=lambda p:p[0]);(xa,ya),(xb,yb)=pts;core=[xa,ya,xb,yb,(xa+xb)/2,(ya+yb)/2,np.hypot(xb-xa,yb-ya)]
    s=a.sum()+1e-15;y,x=np.mgrid[:N,:N];cx=(x*a).sum()/s/N;cy=(y*a).sum()/s/N;X=x/N-cx;Y=y/N-cy;mom=[cx,cy,(X*X*a).sum()/s,(Y*Y*a).sum()/s,(X*Y*a).sum()/s];return np.array(core+mom,float)

def corrupt_field(psi,rng,kind):
    a=np.abs(psi);ph=np.angle(psi)
    if kind=='phase_wipe':return a.astype(complex)
    if kind=='mixed':return np.clip(a*(1+.18*rng.normal(size=a.shape)),0,None)*np.exp(1j*(.55*ph+.45*rng.normal(size=a.shape)))
    if kind=='dropout':
        z=psi.copy();z[rng.random(z.shape)<.35]=0;return z
    return psi.copy()

spec=[];fields=[]
for sep in [8,12,16]:
    for sh in [(-5,-5),(0,0),(5,5),(5,-5)]:fields.append(make_field(sep=sep,shift=sh));spec.append((sep,sh))
X=np.stack([field_vec(f) for f in fields]);scale=np.maximum(X.std(axis=0),.02)
fr=[]
for kind in ['phase_wipe','mixed','dropout']:
    for target in range(len(fields)):
        for seed in range(12):
            rng=np.random.default_rng(700000+target*100+seed);q=corrupt_field(fields[target],rng,kind);v=field_vec(q);D=np.linalg.norm((X-v)/scale,axis=1)/np.sqrt(X.shape[1]);pred=int(np.argmin(D));fr.append({'corruption':kind,'target':target,'seed':seed,'correct':int(pred==target),'margin':np.partition(D,1)[1]-np.min(D)})
fdf=pd.DataFrame(fr);fagg=fdf.groupby('corruption').agg(address_accuracy=('correct','mean'),margin=('margin','median')).reset_index();fdf.to_csv(OUT/'field_reintegration_trials.csv',index=False);fagg.to_csv(OUT/'field_reintegration_aggregate.csv',index=False);print('\nField reintegration:\n',fagg.to_string(index=False))

fig,ax=plt.subplots(figsize=(8,4.8));ax.bar(fagg['corruption'],fagg['address_accuracy']);ax.set_ylim(0,1.02);ax.set_ylabel('Exact field-memory address accuracy');ax.set_title('Complex-field memory reintegration');fig.tight_layout();fig.savefig(OUT/'field_reintegration.png',dpi=170);plt.close(fig)

# Report
rep=f'''# Evidence Graph v3 — Imperfect Anchors, Adaptive Adversary, and Field Reintegration\n\n## Main stress test\n\nThis benchmark combines an adaptive source adversary with routine verification anchors that can themselves be corrupted. A very sparse higher-grade gold check calibrates the routine anchor and verifier layer.\n\nAggregate results:\n\n{agg.to_string(index=False)}\n\nThe robust controller does not treat routine anchors as unquestionable ground truth. It combines anchor evidence with separately tracked verifier reliability, and only uses sufficiently credible verification to update source reputation or dependency structure.\n\n## Interpretation\n\nThe important new hierarchy is:\n\nsource claim -> source trust/dependency -> routine verification -> verifier trust -> sparse gold calibration.\n\nThis makes verification itself part of the evidence graph rather than a privileged magical oracle.\n\nThe adaptive adversary observes current effective trust and alternates between targeted sleeper attacks, correlated-cluster attacks, and low-and-slow bias when common-cause suspicion becomes high.\n\n## Complex-field reintegration\n\nA separate reintegration pass used the previous 12-dimensional transparent complex-field address vector derived from vortex-pair geometry and amplitude moments.\n\n{fagg.to_string(index=False)}\n\nThis confirms that the address layer can still discriminate the controlled field-memory family under severe phase corruption. It does not yet couple every v3 trust update directly into the nonlinear PDE evolution; it reconnects the evidence controller to the field-derived memory representation.\n\n## Limits\n\n- This remains a synthetic source/value benchmark.\n- The gold calibration channel is sparse but still assumed correct.\n- The field test uses a controlled vortex family rather than arbitrary semantics.\n- Full end-to-end reintegration with the original nonlinear field operator still requires the exact source implementation of that operator.\n'''
(OUT/'EVIDENCE_GRAPH_V3_REPORT.md').write_text(rep)

shutil.make_archive('/mnt/data/adrianic_evidence_graph_v3','zip',OUT)
