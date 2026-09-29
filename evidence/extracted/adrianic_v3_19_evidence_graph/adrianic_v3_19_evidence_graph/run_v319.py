from pathlib import Path
import numpy as np, json, zipfile, shutil
import matplotlib.pyplot as plt

ROOT=Path('/mnt/data/adrianic_v3_19_evidence_graph')
if ROOT.exists(): shutil.rmtree(ROOT)
ROOT.mkdir()
N=10; DT=.05; X=np.arange(N)
def lap(z): return np.roll(z,1)+np.roll(z,-1)-2*z
def mode(m): return np.exp(1j*2*np.pi*m*X/N)

class Env:
    def __init__(self,regime=0):
        if regime==0: p=(.075,.18,.045,.012,.09,.055,.018,2,.50)
        elif regime==1: p=(.11,.12,.055,.007,.055,.072,.028,4,.82)
        else: p=(.082,.17,.043,.011,.085,.058,.019,2,.54)
        self.k,self.lam,self.g,self.D,self.gam,self.beta,self.drive,self.m,self.omega=p; self.p=mode(self.m)
    def step(self,psi,phi,a,cue,t):
        forcing=self.drive*self.p*np.exp(1j*(self.omega*t+a*.72))
        dpsi=-1j*(self.k*lap(psi)+self.g*phi*psi+forcing+.020*cue*self.p)-self.lam*np.tanh(np.abs(psi)**2/.12)*psi
        dphi=self.D*lap(phi)-self.gam*phi+self.beta*np.abs(psi)**2
        return psi+DT*dpsi, np.real(phi+DT*dphi)

def init_field(seed,m=2):
    rng=np.random.default_rng(seed); xx=X-(N-1)/2
    z=.075*np.exp(-(xx*xx)/(2*(.25*N)**2))*mode(m)+.002*(rng.normal(size=N)+1j*rng.normal(size=N))
    return z.astype(complex),np.zeros(N)

def field_report(psi,m):
    c=np.vdot(mode(m),psi)/N
    return float(np.tanh(4*np.sin(np.angle(c))))

class Memory:
    def __init__(self):
        self.work=0.; self.last=1; self.banks=[]; self.max_banks=4
        self.recent=[]; self.since=0; self.active_regime=0; self.commits=0; self.reactivations=0
    def reports(self,cue,field):
        r={'cue':None if cue==0 else float(cue),'field':float(field),'work':None if abs(self.work)<.05 else float(np.clip(self.work,-1,1)),'recurrence':float(self.last)}
        cand=[b for b in self.banks if b['regime']==self.active_regime and b['conf']>.05]
        cand=sorted(cand,key=lambda b:b['conf']*np.exp(-b['age']/300),reverse=True)[:2]
        for i,b in enumerate(cand): r[f'bank{i+1}']=float(np.clip(b['value'],-1,1))
        return r
    def tick(self):
        for b in self.banks:b['age']+=1
    def update_work(self,val,reward,allow=True):
        if allow:self.work=.88*self.work+.12*val
        self.recent=(self.recent+[reward])[-12:]
    def maybe_commit(self,resolved,trust_score):
        self.since+=1; self.tick()
        if not resolved or len(self.recent)<12:return False
        rr=np.array(self.recent)
        if not(rr.mean()>.5 and rr.std()<.27 and trust_score>.44 and self.since>38):return False
        same=[b for b in self.banks if b['regime']==self.active_regime]
        if len(same)<2:self.banks.append({'value':float(self.work),'conf':.95,'regime':self.active_regime,'age':0})
        else:max(same,key=lambda b:b['age']).update(value=float(self.work),conf=.95,age=0)
        if len(self.banks)>self.max_banks:
            self.banks.sort(key=lambda b:b['conf']*np.exp(-b['age']/350));self.banks=self.banks[-self.max_banks:]
        self.since=0;self.commits+=1;return True
    def quarantine(self,newreg): self.active_regime=newreg;self.work=0.;self.since=0
    def reactivate(self,reg):
        old=[b for b in self.banks if b['regime']==reg and b['conf']>.25]
        if old:self.active_regime=reg;self.work=float(np.mean([b['value'] for b in old]));self.reactivations+=1;return True
        return False

class Graph:
    def __init__(self,kind='graph',vp=.2,vnoise=0.):
        self.kind=kind;self.vp=vp;self.vnoise=vnoise;self.gamma=3.;self.sigma=.8
        self.rf={};self.rs={};self.bias={};self.hist={};self.prov={};self.vrho=.85
        self.cscore=0.;self.chits=0;self.changes=[];self.holds=0;self.decisions=0
    def ensure(self,n):
        if n not in self.rf:self.rf[n]=self.rs[n]=.5;self.bias[n]=0.;self.hist[n]=[];self.prov[n]='durable' if n.startswith('bank') else n
    def rho(self,n,after=False):
        self.ensure(n);return (.75*self.rf[n]+.25*self.rs[n]) if after else (.35*self.rf[n]+.65*self.rs[n])
    def update(self,reports,y,rng):
        if rng.random()>=self.vp:return False,None
        yo=y if rng.random()>=self.vnoise else -y
        self.vrho=.94*self.vrho+.06*(1. if yo==y else 0.)
        errs=[]
        for n,u in reports.items():
            if u is None:continue
            self.ensure(n);e=float(u-yo);q=np.exp(-abs(e)/self.sigma);qe=self.vrho*q+(1-self.vrho)*.5
            self.rf[n]=.72*self.rf[n]+.28*qe;self.rs[n]=.955*self.rs[n]+.045*qe;self.bias[n]=.94*self.bias[n]+.06*e
            self.hist[n]=(self.hist[n]+[e])[-24:];errs.append(abs(e))
        if errs:
            self.cscore=.80*self.cscore+.20*np.mean(errs)
            self.chits=self.chits+1 if self.cscore>.92 else max(0,self.chits-1)
        if self.chits>=2:
            self.changes.append(self.cscore);self.chits=0;self.cscore=0.
            for n in self.rf:self.rf[n]=.6*self.rf[n]+.4*.5
            return True,'CHANGE'
        return True,None
    def corr_pen(self,n,avail):
        if self.kind!='graph':return 1.
        h=self.hist.get(n,[]); pens=[]
        if len(h)<8:return 1.
        for m in avail:
            if m==n:continue
            hm=self.hist.get(m,[]);L=min(len(h),len(hm),18)
            if L<8:continue
            a=np.array(h[-L:]);b=np.array(hm[-L:])
            if a.std()<1e-6 or b.std()<1e-6:continue
            c=abs(np.corrcoef(a,b)[0,1])
            if c>.75 and self.prov.get(n,n)!=self.prov.get(m,m):pens.append(c)
        return max(.25,1-.65*max(pens)) if pens else 1.
    def aggregate(self,reports,after=False):
        av=[n for n,u in reports.items() if u is not None]
        for n in av:self.ensure(n)
        if not av:self.holds+=1;self.decisions+=1;return 0.,True,{}
        raw={n:(1. if self.kind=='equal' else self.rho(n,after)**3*self.corr_pen(n,av)) for n in av}
        if self.kind in ('graph','dual'):
            groups={}
            for n in av:groups.setdefault(self.prov[n],[]).append(n)
            for ns in groups.values():
                if len(ns)>1:
                    tot=sum(raw[n] for n in ns);cap=max(raw[n] for n in ns);sc=cap/(tot+1e-12)
                    for n in ns:raw[n]*=sc
        s=sum(raw.values())+1e-12;w={n:raw[n]/s for n in av};deb={n:reports[n]-(0 if self.kind=='equal' else self.bias[n]) for n in av}
        U=sum(w[n]*deb[n] for n in av);dis=sum(w[n]*(deb[n]-U)**2 for n in av);mt=max(self.rho(n,after) for n in av)
        hold=(abs(U)<.1) or (dis>.6) or (mt<.24) or (self.vrho<.35)
        self.decisions+=1;self.holds+=int(hold);return float(U),hold,w

CONFIGS=['equal','single','dual','graph']
def schedule():
    ctx=1;out=[]
    for b in range(12):
        if b in [2,4,6,8,10]:ctx=-ctx
        out.append((ctx,56))
    return out

def run(kind,seed=0,vp=.2,vnoise=0.):
    rng=np.random.default_rng(seed);envs=[Env(0),Env(1),Env(2)];psi,phi=init_field(seed+100,2);mem=Memory();gph=Graph('equal' if kind=='equal' else ('graph' if kind=='graph' else 'dual'),vp,vnoise)
    t=0.;g=0;after=999;phase_prev=0;rec=[]
    for ctx,L in schedule():
        for s in range(L):
            if g<224:phase=0;pol=1
            elif g<448:phase=1;pol=-1
            else:phase=2;pol=1
            env=envs[phase];y=int(ctx*pol);cue=y if s<8 else 0
            reps=mem.reports(cue,field_report(psi,env.m))
            if kind=='single':
                for n in list(gph.rf):
                    a=.5*(gph.rf[n]+gph.rs[n]);gph.rf[n]=gph.rs[n]=a
            U,hold,_=gph.aggregate(reps,after<75);field=reps['field']
            a=(cue if cue!=0 else (1 if field>=0 else -1)) if hold else (1 if U>=0 else -1)
            resolved=not hold;psi,phi=env.step(psi,phi,a,cue,t);r=1. if a==y else -1.
            verified,event=gph.update(reps,y,rng)
            if event=='CHANGE':
                after=0;desired=0 if env.m==2 and mem.active_regime>0 else mem.active_regime+1
                if not(desired==0 and mem.reactivate(0)):mem.quarantine(desired)
            if verified:mem.work=.82*mem.work+.18*y
            mem.last=a;mem.update_work(U if not hold else a,r,resolved or verified)
            ar=[gph.rho(n,after<75) for n,u in reps.items() if u is not None];mem.maybe_commit(resolved or verified,float(np.mean(ar)) if ar else 0)
            rec.append({'g':g,'phase':phase,'correct':int(a==y),'hold':int(hold),'active_regime':mem.active_regime,'vrho':gph.vrho})
            after+=1;t+=DT;g+=1
    return rec,mem,gph

def summarize(kind,seeds=16,vp=.2,vnoise=0.):
    vals=[]
    for s in range(seeds):
        rec,mem,gph=run(kind,2000+s,vp,vnoise)
        vals.append((np.mean([r['correct'] for r in rec if r['phase']==0]),np.mean([r['correct'] for r in rec if r['phase']==1 and r['g']<320]),np.mean([r['correct'] for r in rec if r['phase']==1 and r['g']>=350]),np.mean([r['correct'] for r in rec if r['phase']==2 and r['g']<520]),np.mean([r['correct'] for r in rec if r['phase']==2 and r['g']>=560]),np.mean([r['hold'] for r in rec]),mem.reactivations,len(gph.changes),gph.vrho))
    return {'config':kind,'old':float(np.median([v[0] for v in vals])),'new_early':float(np.median([v[1] for v in vals])),'new_late':float(np.median([v[2] for v in vals])),'return_early':float(np.median([v[3] for v in vals])),'return_late':float(np.median([v[4] for v in vals])),'hold':float(np.median([v[5] for v in vals])),'reactivations':float(np.median([v[6] for v in vals])),'changes':float(np.median([v[7] for v in vals])),'verifier_rho':float(np.median([v[8] for v in vals]))}

main=[summarize(c) for c in CONFIGS]
sweep=[]
for vp in [0,.02,.05,.1,.2,.3]:
    vals=[]
    for s in range(12):
        rec,mem,gph=run('graph',7000+s,vp,0)
        vals.append((np.mean([r['correct'] for r in rec if r['phase']==1 and r['g']>=350]),np.mean([r['correct'] for r in rec if r['phase']==2 and r['g']>=560]),len(gph.changes)))
    sweep.append({'verify_prob':vp,'new_late':float(np.median([v[0] for v in vals])),'return_late':float(np.median([v[1] for v in vals])),'changes':float(np.median([v[2] for v in vals]))})
vnoise=[]
for noise in [0,.05,.1,.2,.35]:
    vals=[]
    for s in range(12):
        rec,mem,gph=run('graph',9000+s,.2,noise);vals.append((np.mean([r['correct'] for r in rec if r['phase']==1 and r['g']>=350]),gph.vrho))
    vnoise.append({'verifier_noise':noise,'new_late':float(np.median([v[0] for v in vals])),'verifier_rho':float(np.median([v[1] for v in vals]))})

rec,mem,gph=run('graph',4242,.2,0);c=np.array([r['correct'] for r in rec],float);win=35;roll=np.convolve(c,np.ones(win)/win,mode='valid')
plt.figure(figsize=(8,4.5));plt.plot(np.arange(win-1,len(c)),roll);plt.axvline(224,ls='--');plt.axvline(448,ls='--');plt.ylim(0,1.05);plt.xlabel('task step');plt.ylabel('rolling accuracy');plt.title('Evidence-graph adaptation and return');plt.tight_layout();plt.savefig(ROOT/'regime_return_accuracy.png',dpi=180);plt.close()
plt.figure(figsize=(8,4.5));x=np.arange(len(main));w=.23;plt.bar(x-w,[r['new_early'] for r in main],w,label='new early');plt.bar(x,[r['new_late'] for r in main],w,label='new late');plt.bar(x+w,[r['return_early'] for r in main],w,label='return early');plt.xticks(x,[r['config'] for r in main]);plt.ylim(0,1.05);plt.ylabel('accuracy');plt.title('Evidence graph vs simpler trust');plt.legend();plt.tight_layout();plt.savefig(ROOT/'controller_comparison.png',dpi=180);plt.close()
plt.figure(figsize=(7,4.4));plt.plot([r['verify_prob'] for r in sweep],[r['new_late'] for r in sweep],marker='o',label='new');plt.plot([r['verify_prob'] for r in sweep],[r['return_late'] for r in sweep],marker='o',label='return');plt.ylim(0,1.05);plt.xlabel('verification probability');plt.ylabel('late accuracy');plt.title('Verification requirement');plt.legend();plt.tight_layout();plt.savefig(ROOT/'verification_sweep.png',dpi=180);plt.close()
plt.figure(figsize=(7,4.4));plt.plot([r['verifier_noise'] for r in vnoise],[r['new_late'] for r in vnoise],marker='o',label='behavior');plt.plot([r['verifier_noise'] for r in vnoise],[r['verifier_rho'] for r in vnoise],marker='o',label='verifier trust');plt.ylim(0,1.05);plt.xlabel('verifier corruption probability');plt.title('Verifier confidence stress');plt.legend();plt.tight_layout();plt.savefig(ROOT/'verifier_confidence.png',dpi=180);plt.close()

results={'improvements':['dual-timescale source reliability','verified-consequence change detection','regime quarantine instead of deletion','regime-tagged durable memories and reactivation','provenance caps','correlated-error penalties','verifier confidence','VALUE_UNRESOLVED/HOLD'],'main':main,'verification_sweep':sweep,'verifier_noise':vnoise,'guardrails':['Regime change is inferred from verified consequence error, not directly supplied to the controller.','Return matching uses observable field mode as a simple first regime key.','Correlated-error penalties still cannot solve arbitrary common-mode failure without independent evidence.','Verifier confidence here is audited against the simulated objective outcome; a real verifier audit would itself need justified provenance.']}
(ROOT/'results.json').write_text(json.dumps(results,indent=2))
(ROOT/'README.md').write_text('Adrianic v3.19 evidence-graph memory: dual-timescale trust, regime quarantine/reactivation, provenance, correlated-error penalties, verifier confidence, and HOLD.\n')
(ROOT/'V319_SPEC.md').write_text('''# Adrianic v3.19 — Evidence-Graph Regime Memory\n\nAdds dual-timescale trust, consequence-driven regime change detection, regime-tagged durable memory, quarantine/reactivation, provenance caps, correlated-error penalties, verifier reliability, and VALUE_UNRESOLVED/HOLD.\n''')
zp=Path('/mnt/data/adrianic_v3_19_evidence_graph.zip')
if zp.exists():zp.unlink()
with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
    for fp in ROOT.rglob('*'):
        if fp.is_file():z.write(fp,fp.relative_to(ROOT.parent))
print('MAIN')
for r in main:print(r)
print('\nSWEEP')
for r in sweep:print(r)
print('\nVERIFIER')
for r in vnoise:print(r)
print('\nCreated',zp)
