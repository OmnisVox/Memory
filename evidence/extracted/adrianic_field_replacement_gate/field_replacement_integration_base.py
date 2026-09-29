import numpy as np, pandas as pd, math, shutil, time
from pathlib import Path
from collections import defaultdict

OUT=Path('/mnt/data/adrianic_field_replacement_gate'); OUT.mkdir(exist_ok=True)

# ============================================================
# Complex vortex fields and transparent 12-D descriptor
# ============================================================
N=40

def make_pair(sep=12,shift=(0,0),core=2.0,amp=0.65):
    y,x=np.mgrid[:N,:N]; sy,sx=shift; cy=N//2+sy
    x1=N//2-sep//2+sx; x2=N//2+sep//2+sx
    r1=np.hypot(x-x1,y-cy); r2=np.hypot(x-x2,y-cy)
    th1=np.arctan2(y-cy,x-x1); th2=np.arctan2(y-cy,x-x2)
    A=np.tanh(r1/core)*np.tanh(r2/core)
    return (amp*A*np.exp(1j*(th1-th2))).astype(complex)

def smooth(a,rounds=5):
    z=a.astype(float).copy()
    for _ in range(rounds):
        z=(4*z+np.roll(z,1,0)+np.roll(z,-1,0)+np.roll(z,1,1)+np.roll(z,-1,1))/8
    return z

def inpaint(psi):
    a=np.abs(psi).copy(); mask=a<1e-12
    if mask.mean()<.08:return a
    z=a.copy(); valid=~mask
    for _ in range(10):
        sums=np.zeros_like(z); cnt=np.zeros_like(z,float)
        for sh,ax in [(1,0),(-1,0),(1,1),(-1,1)]:
            zv=np.roll(z,sh,ax); vv=np.roll(valid,sh,ax); sums+=zv*vv; cnt+=vv
        fill=(~valid)&(cnt>0); z[fill]=sums[fill]/cnt[fill]; valid[fill]=True
        if valid.all():break
    return z

def descriptor(psi):
    a=inpaint(psi); sm=smooth(a); pad=3
    work=sm.copy(); work[:pad,:]=np.inf; work[-pad:,:]=np.inf; work[:,:pad]=np.inf; work[:,-pad:]=np.inf
    y1,x1=np.unravel_index(np.argmin(work),work.shape)
    yy,xx=np.mgrid[:N,:N]; w2=work.copy(); w2[(xx-x1)**2+(yy-y1)**2<=4**2]=np.inf
    y2,x2=np.unravel_index(np.argmin(w2),w2.shape)
    pts=sorted([(x1/N,y1/N),(x2/N,y2/N)],key=lambda p:p[0]); (xa,ya),(xb,yb)=pts
    core=np.array([xa,ya,xb,yb,(xa+xb)/2,(ya+yb)/2,np.hypot(xb-xa,yb-ya)])
    s=a.sum()+1e-15; y,x=np.mgrid[:N,:N]; cx=float((x*a).sum()/s)/N; cy=float((y*a).sum()/s)/N
    X=x/N-cx; Y=y/N-cy
    moments=np.array([cx,cy,float((X*X*a).sum()/s),float((Y*Y*a).sum()/s),float((X*Y*a).sum()/s)])
    return np.concatenate([core,moments])

def corrupt(psi,kind,rng):
    a=np.abs(psi); ph=np.angle(psi)
    if kind=='clean':return psi.copy()
    if kind=='phase_wipe':return a.astype(complex)
    if kind=='dropout35':
        z=psi.copy(); z[rng.random(z.shape)<.35]=0; return z
    if kind=='mixed':
        aa=np.clip(a*(1+.18*rng.normal(size=a.shape)),0,None)
        return aa*np.exp(1j*(.55*ph+.45*rng.normal(size=a.shape)))
    if kind=='hard_mixed':
        aa=np.clip(a*(1+.28*rng.normal(size=a.shape)),0,None)
        z=aa*np.exp(1j*(.35*ph+.75*rng.normal(size=a.shape))); z[rng.random(z.shape)<.18]=0; return z
    raise ValueError(kind)

# 24 field memories
fields=[]; specs=[]
shifts=[(-6,-6),(-6,0),(-6,6),(0,-6),(0,0),(0,6),(6,-6),(6,6)]
for sep in [8,12,16]:
    for sh in shifts: fields.append(make_pair(sep,sh)); specs.append((sep,sh))
V=np.stack([descriptor(f) for f in fields]); VS=np.maximum(V.std(axis=0),.02)
def dist(a,b):return float(np.linalg.norm((a-b)/VS)/np.sqrt(12))

HIGH=set(range(0,6)); CRIT=set(range(6,9)); JUNK=set(range(9,14)); DIST=set(range(14,24))
U={i:(1.0 if i in HIGH else 4.5 if i in CRIT else .06 if i in JUNK else .10) for i in range(24)}
def role(i):return 'high' if i in HIGH else 'critical' if i in CRIT else 'junk' if i in JUNK else 'distractor'

# Precompute a fixed corruption atlas derived from actual complex fields.
KINDS=['clean','phase_wipe','dropout35','mixed','hard_mixed']
ATLAS={}
rng=np.random.default_rng(777)
for lab in range(24):
    for kind in KINDS:
        ATLAS[(lab,kind)]=[]
        for j in range(16):
            z=corrupt(fields[lab],kind,rng); ATLAS[(lab,kind)].append((descriptor(z),z))
print('atlas ready',sum(len(v) for v in ATLAS.values()))

# ============================================================
# Bank
# ============================================================
class Cand:
    def __init__(self,vec,field,t,label):self.vec=vec.copy(); self.field=field.copy(); self.n=1; self.last=t; self.values=[]; self.labels=[label]
    def update(self,vec,field,t,label):self.n+=1; self.vec+=(vec-self.vec)/self.n; self.field+=(field-self.field)/self.n; self.last=t; self.labels.append(label)
    @property
    def recent(self):
        if not self.values:return 0.
        a=np.array(self.values[-6:]); w=np.geomspace(.55,1,len(a)); return float(w@a/w.sum())
    @property
    def label(self):return max(set(self.labels),key=self.labels.count)
class Slot:
    def __init__(self,vec,field,t,u,label):self.vec=vec.copy(); self.field=field.copy(); self.last=t; self.uses=1; self.u=float(u); self.label=label
class Bank:
    def __init__(self,cap=8,margin=None):self.cap=cap; self.margin=margin; self.slots=[]; self.cands=[]; self.writes=0; self.repl=0; self.blocked=0; self.holds=0
    def address(self,vec):
        if not self.slots:return None,np.inf
        ds=np.array([dist(vec,s.vec) for s in self.slots]); order=np.argsort(ds); m=float(ds[order[1]]-ds[order[0]]) if len(order)>1 else np.inf
        if m<.035:return None,m
        return int(order[0]),m
    def touch(self,vec,label,t):
        i,m=self.address(vec)
        if i is None:return False,False,None
        s=self.slots[i]; s.uses+=1; s.last=t; return True,s.label==label,s.label
    def observe(self,vec,field,label,t):
        # Candidate clustering only; labels are scoring metadata, not used to match.
        if self.slots and min(dist(vec,s.vec) for s in self.slots)<.16:return None
        if self.cands:
            ds=[dist(vec,c.vec) for c in self.cands]; i=int(np.argmin(ds))
            if ds[i]<.22:self.cands[i].update(vec,field,t,label); return i
        self.cands.append(Cand(vec,field,t,label)); return len(self.cands)-1
    def weakest(self,t):
        return min(((s.u*np.sqrt(np.log1p(s.uses))/(1+.02*(t-s.last)),i) for i,s in enumerate(self.slots)))
    def evidence(self,ci,u,conf,t):
        if ci is None or ci>=len(self.cands):return 'NONE'
        c=self.cands[ci]; c.values.append(float(u)); score=.58*min(c.recent/1.5,1)+.18*min(c.n/3,1)+.24*conf
        if not (c.n>=2 and len(c.values)>=2 and c.recent>=.26 and score>=.53):
            if c.n>=5 and len(c.values)>=3 and c.recent<.12:self.cands.pop(ci); return 'EXCLUDE'
            return 'HOLD'
        slot=Slot(c.vec,c.field,t,c.recent,c.label)
        if len(self.slots)<self.cap:self.slots.append(slot); self.writes+=1; self.cands.pop(ci); return 'FREE'
        weak,idx=self.weakest(t)
        if self.margin is None:self.slots[idx]=slot; self.writes+=1; self.repl+=1; self.cands.pop(ci); return 'AUTO'
        support=min(c.n/3,1); cand=c.recent*(.65+.35*support)*(.75+.25*conf); delta=cand-weak
        if delta>self.margin:self.slots[idx]=slot; self.writes+=1; self.repl+=1; self.cands.pop(ci); return 'GATE'
        self.blocked+=1; self.holds+=1; return 'HOLD_REPLACEMENT'
    def expire(self,t):self.cands=[c for c in self.cands if t-c.last<=80]

def stream(seed,n):
    rng=np.random.default_rng(seed); p_hi=1/(np.arange(1,7)**.9); p_hi/=p_hi.sum(); p_cr=np.array([.5,.3,.2]); out=[]
    for t in range(n):
        q=rng.random()
        if q<.54:lab=int(rng.choice(np.array(sorted(HIGH)),p=p_hi))
        elif q<.67:lab=int(rng.choice(np.array(sorted(CRIT)),p=p_cr))
        elif q<.88:lab=int(rng.choice(np.array(sorted(JUNK))))
        else:lab=int(rng.choice(np.array(sorted(DIST))))
        kind=str(rng.choice(KINDS,p=[.22,.18,.20,.28,.12])); variant=int(rng.integers(0,16)); out.append((lab,kind,variant))
    return out

def value_obs(lab,rng,hard=False):
    y=U[lab]; z=max(0,y*(1+.18*rng.normal())+rng.normal(0,.04))
    if lab in JUNK and rng.random()<(0.06 if hard else .025):z+= (1.6 if hard else 1.2)
    if hard and rng.random()<.04:z=max(0,z+rng.normal(0,1.2))
    return z

def run(seed,margin,n=1400,hard_value=False):
    rng=np.random.default_rng(900000+seed); bank=Bank(8,margin); ev=stream(seed,n)
    total=cap=0.; resolved=correct=wrong=0; cn=defaultdict(int); ch=defaultdict(int)
    for t,(lab,kind,var) in enumerate(ev):
        vec,z=ATLAS[(lab,kind)][var]
        res,ok,pred=bank.touch(vec,lab,t); resolved+=res; correct+=res and ok; wrong+=res and not ok; total+=U[lab]; cn[role(lab)]+=1
        if res and ok:
            cap+=U[lab]; ch[role(lab)]+=1
            # update utility estimate of addressed slot
            i=next((i for i,s in enumerate(bank.slots) if s.label==pred),None)
            if i is not None:bank.slots[i].u=.88*bank.slots[i].u+.12*value_obs(lab,rng,hard_value)
        else:
            ci=bank.observe(vec,z,lab,t)
            if ci is not None:bank.evidence(ci,value_obs(lab,rng,hard_value),.88,t)
        bank.expire(t)
    roles=[role(s.label) for s in bank.slots]
    return {'seed':seed,'margin':'auto' if margin is None else str(margin),'hard_value':hard_value,'utility_capture':cap/(total+1e-15),'resolved_rate':resolved/n,'address_precision':correct/max(resolved,1),'wrong_address_rate':wrong/n,'writes':bank.writes,'replacements':bank.repl,'blocked':bank.blocked,'replacement_holds':bank.holds,'high_hit':ch['high']/max(cn['high'],1),'critical_hit':ch['critical']/max(cn['critical'],1),'junk_hit':ch['junk']/max(cn['junk'],1),'distractor_hit':ch['distractor']/max(cn['distractor'],1),'high_slots':roles.count('high'),'critical_slots':roles.count('critical'),'junk_slots':roles.count('junk'),'distractor_slots':roles.count('distractor')}

if __name__=='__main__':
    rows=[]; margins=[None,0.0,.08,.16,.28]
    t0=time.time()
    for hard in [False,True]:
        for seed in range(36):
            for m in margins:rows.append(run(seed,m,n=1400,hard_value=hard))
    df=pd.DataFrame(rows); df.to_csv(OUT/'field_replacement_trials.csv',index=False)
    agg=df.groupby(['hard_value','margin']).agg(utility_capture=('utility_capture','mean'),utility_std=('utility_capture','std'),resolved_rate=('resolved_rate','mean'),address_precision=('address_precision','mean'),wrong_address_rate=('wrong_address_rate','mean'),writes=('writes','mean'),replacements=('replacements','mean'),blocked=('blocked','mean'),replacement_holds=('replacement_holds','mean'),high_hit=('high_hit','mean'),critical_hit=('critical_hit','mean'),junk_hit=('junk_hit','mean'),distractor_hit=('distractor_hit','mean'),high_slots=('high_slots','mean'),critical_slots=('critical_slots','mean'),junk_slots=('junk_slots','mean'),distractor_slots=('distractor_slots','mean')).reset_index()
    agg.to_csv(OUT/'field_replacement_aggregate.csv',index=False); print(agg.to_string(index=False)); print('elapsed',time.time()-t0)
