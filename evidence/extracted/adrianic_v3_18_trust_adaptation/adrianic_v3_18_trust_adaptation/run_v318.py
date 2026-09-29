
from pathlib import Path
import numpy as np, json, zipfile, shutil
import matplotlib.pyplot as plt

ROOT=Path("/mnt/data/adrianic_v3_18_trust_adaptation")
N=12; DT=.05; X=np.arange(N)

def lap(z): return np.roll(z,1)+np.roll(z,-1)-2*z
def mode(m): return np.exp(1j*2*np.pi*m*X/N)

class Env:
    def __init__(self, regime=0):
        if regime==0:
            self.k=.075; self.lam=.18; self.g=.045; self.D=.012; self.gam=.09
            self.beta=.055; self.drive=.018; self.m=3; self.omega=.50
        else:
            self.k=.11; self.lam=.12; self.g=.055; self.D=.007; self.gam=.055
            self.beta=.072; self.drive=.028; self.m=5; self.omega=.82
        self.p=mode(self.m)
    def step(self,psi,phi,a,cue,t):
        forcing=self.drive*self.p*np.exp(1j*(self.omega*t+a*.72))
        dpsi=-1j*(self.k*lap(psi)+self.g*phi*psi+forcing+.020*cue*self.p)-self.lam*np.tanh(np.abs(psi)**2/.12)*psi
        dphi=self.D*lap(phi)-self.gam*phi+self.beta*np.abs(psi)**2
        return psi+DT*dpsi, np.real(phi+DT*dphi)

def init_field(seed,m=3):
    rng=np.random.default_rng(seed)
    xx=X-(N-1)/2
    z=.075*np.exp(-(xx*xx)/(2*(.25*N)**2))*mode(m)+.002*(rng.normal(size=N)+1j*rng.normal(size=N))
    return z.astype(complex),np.zeros(N)

def modal_report(psi,m):
    c=np.vdot(mode(m),psi)/N
    # Deliberately imperfect current-state source.
    return float(np.tanh(4*np.sin(np.angle(c))))

class Trust:
    def __init__(self, config="adaptive", verify_prob=.10):
        self.config=config; self.verify_prob=verify_prob
        self.names=["cue","field","work","A","B","recurrence"]
        self.rho={n:.5 for n in self.names}
        self.bias={n:0. for n in self.names}
        self.eta=.08; self.sigma=.80; self.gamma=3.0
        self.prov={"cue":"sensory","field":"field","work":"volatile","recurrence":"recurrence","A":"durable","B":"durable"}
        self.freeze=False
        self.holds=0; self.decisions=0
    def update(self,reports,y,rng):
        if self.config=="equal" or self.freeze or rng.random()>=self.verify_prob:
            return False
        for n,u in reports.items():
            if u is None: continue
            q=np.exp(-abs(u-y)/self.sigma)
            self.rho[n]=(1-self.eta)*self.rho[n]+self.eta*q
            self.bias[n]=(1-self.eta)*self.bias[n]+self.eta*(u-y)
        return True
    def aggregate(self,reports,y_oracle=None):
        avail=[n for n,u in reports.items() if u is not None]
        if not avail:
            self.holds+=1; self.decisions+=1
            return 0.0, True, {}
        if self.config=="oracle" and y_oracle is not None:
            raw={n:np.exp(-3*abs(reports[n]-y_oracle)) for n in avail}
        elif self.config=="equal":
            raw={n:1. for n in avail}
        else:
            raw={n:self.rho[n]**self.gamma for n in avail}

        # provenance cap: A/B are one evidence family unless explicitly disabled
        if self.config!="adaptive_no_prov":
            groups={}
            for n in avail: groups.setdefault(self.prov[n],[]).append(n)
            for g,ns in groups.items():
                if len(ns)>1:
                    total=sum(raw[n] for n in ns)
                    cap=max(raw[n] for n in ns)
                    if total>0:
                        scale=cap/total
                        for n in ns: raw[n]*=scale

        s=sum(raw.values())+1e-12
        w={n:raw[n]/s for n in avail}
        deb={n:reports[n]-(0 if self.config in ("equal","oracle") else self.bias[n]) for n in avail}
        U=sum(w[n]*deb[n] for n in avail)
        disagreement=sum(w[n]*(deb[n]-U)**2 for n in avail)

        # VALUE_UNRESOLVED/HOLD: insufficient signed evidence or severe disagreement.
        trusted_mass=sum(w[n] for n in avail if (self.config in ("equal","oracle") or self.rho[n]>.25))
        unresolved = (abs(U)<.12) or (disagreement>.55) or (trusted_mass<.55)
        self.decisions+=1
        if unresolved: self.holds+=1
        return float(U), bool(unresolved), w

class Memory:
    def __init__(self):
        self.work=0.; self.A=0.; self.B=0.; self.P=0.; self.Q=0.; self.alpha=1.7
        self.cA=.0; self.cB=.0; self.ageA=999; self.ageB=999
        self.last=1; self.since=0; self.recent=[]; self.commits=0
    def repair(self):
        badA=self.cA<.15; badB=self.cB<.15
        if badA and not badB:
            self.A=self.P-self.B; self.cA=.8*self.cB; return True
        if badB and not badA:
            self.B=self.P-self.A; self.cB=.8*self.cA; return True
        if badA and badB:
            M=np.array([[1.,1.],[1.,self.alpha]])
            self.A,self.B=np.linalg.inv(M)@np.array([self.P,self.Q])
            self.cA=self.cB=.75; return True
        return False
    def reports(self,cue,field):
        return {
            "cue": None if cue==0 else float(cue),
            "field": float(field),
            "work": None if abs(self.work)<.05 else float(np.clip(self.work,-1,1)),
            "A": None if self.cA<.05 else float(np.clip(self.A,-1,1)),
            "B": None if self.cB<.05 else float(np.clip(self.B,-1,1)),
            "recurrence": float(self.last)
        }
    def update_work(self,decision,reward,resolved):
        if resolved:
            self.work=.90*self.work+.10*decision
        self.recent=(self.recent+[reward])[-12:]
    def maybe_commit(self, resolved, trust_score):
        self.since+=1; self.ageA+=1; self.ageB+=1
        if not resolved or len(self.recent)<12: return False
        rr=np.array(self.recent)
        good=rr.mean()>.45 and rr.std()<.28 and trust_score>.45 and self.since>45
        if not good: return False
        if self.cA<.3 or self.ageA>=self.ageB:
            self.A=self.work; self.cA=.95; self.ageA=0
        else:
            self.B=self.work; self.cB=.95; self.ageB=0
        self.P=self.A+self.B; self.Q=self.A+self.alpha*self.B
        self.since=0; self.commits+=1
        return True
    def corrupt_banks(self,rng):
        self.A=float(rng.uniform(-1,1)); self.B=float(rng.uniform(-1,1)); self.cA=self.cB=0.

def schedule():
    # The control polarity reverses after the regime switch.
    # Cues always report the currently correct action for a short window.
    blocks=[]
    ctx=1
    for b in range(12):
        if b in [2,4,7,9,11]: ctx=-ctx
        blocks.append((ctx,72))
    return blocks

CONFIGS=["equal","frozen_trust","adaptive","adaptive_no_prov","oracle"]

def run(config,seed=0,verify_prob=.10,bank_damage=True):
    rng=np.random.default_rng(seed)
    env0=Env(0); env1=Env(1)
    psi,phi=init_field(seed+100,3)
    trust=Trust("adaptive" if config=="frozen_trust" else config,verify_prob)
    mem=Memory()
    t=0.; g=0; switched=False; damaged=False
    rec=[]
    for bi,(ctx,L) in enumerate(schedule()):
        for s in range(L):
            if g<432:
                env=env0; polarity=1
            else:
                env=env1; polarity=-1
                if not switched:
                    switched=True
                    if config=="frozen_trust": trust.freeze=True
            y=int(ctx*polarity)
            cue=y if s<10 else 0

            mem.repair()
            field=modal_report(psi,env.m)
            reps=mem.reports(cue,field)
            U,hold,w=trust.aggregate(reps,y_oracle=y if config=="oracle" else None)

            if hold:
                # HOLD does not silently become recurrence-only.
                if cue!=0:
                    a=cue
                else:
                    a=1 if field>=0 else -1
                resolved=False
            else:
                a=1 if U>=0 else -1
                resolved=True

            psi,phi=env.step(psi,phi,a,cue,t)
            r=1.0 if a==y else -1.0
            verified=trust.update(reps,y,rng)

            # direct verified consequence is a higher evidence tier:
            if verified:
                mem.work=.85*mem.work+.15*y

            mem.last=a
            mem.update_work(U if not hold else a,r,resolved or verified)
            meanrho=float(np.mean([trust.rho[n] for n,u in reps.items() if u is not None]))
            mem.maybe_commit(resolved or verified,meanrho)

            # Physical integrity failure later: parity should restore contents,
            # but trust still determines whether restored contents deserve use.
            if bank_damage and not damaged and g==650:
                mem.corrupt_banks(rng); damaged=True

            rec.append({
                "g":g,"correct":int(a==y),"hold":int(hold),"y":y,"cue":cue,
                "rho_cue":trust.rho["cue"],"rho_field":trust.rho["field"],
                "rho_work":trust.rho["work"],"rho_A":trust.rho["A"],"rho_B":trust.rho["B"],
                "switched":int(g>=432)
            })
            t+=DT; g+=1
    return rec,mem,trust

def summarize(config,seeds=28,verify_prob=.10):
    rows=[]
    for s in range(seeds):
        rec,mem,tr=run(config,2000+s,verify_prob)
        pre=[r["correct"] for r in rec if r["g"]<432]
        early=[r["correct"] for r in rec if 432<=r["g"]<540]
        late=[r["correct"] for r in rec if r["g"]>=600]
        tail=[r for r in rec if r["g"]>=760]
        rows.append({
            "pre":np.mean(pre),"early":np.mean(early),"late":np.mean(late),
            "rhoA":tail[-1]["rho_A"],"rhoB":tail[-1]["rho_B"],
            "rhoWork":tail[-1]["rho_work"],"rhoField":tail[-1]["rho_field"],
            "hold":np.mean([r["hold"] for r in rec]),
            "commits":mem.commits
        })
    return {
        "config":config,
        "pre_accuracy":float(np.median([x["pre"] for x in rows])),
        "early_post_switch_accuracy":float(np.median([x["early"] for x in rows])),
        "late_post_switch_accuracy":float(np.median([x["late"] for x in rows])),
        "final_rho_A":float(np.median([x["rhoA"] for x in rows])),
        "final_rho_B":float(np.median([x["rhoB"] for x in rows])),
        "final_rho_work":float(np.median([x["rhoWork"] for x in rows])),
        "final_rho_field":float(np.median([x["rhoField"] for x in rows])),
        "hold_fraction":float(np.median([x["hold"] for x in rows])),
        "commits":float(np.median([x["commits"] for x in rows])),
    }

def main():
    summaries=[summarize(c) for c in CONFIGS]

    # Verification sweep for adaptive trust.
    vs=[]
    for vp in [0.0,.02,.05,.10,.30]:
        vals=[]
        for s in range(20):
            rec,_,_=run("adaptive",7000+s,vp,bank_damage=False)
            vals.append(np.mean([r["correct"] for r in rec if r["g"]>=600]))
        vs.append({"verify_prob":vp,"late_accuracy":float(np.median(vals))})

    # One representative trust trajectory.
    rec,_,_=run("adaptive",4242,.10)
    xs=np.array([r["g"] for r in rec])
    plt.figure(figsize=(8.5,4.8))
    for k,label in [("rho_work","working"),("rho_A","bank A"),("rho_B","bank B"),("rho_field","field")]:
        plt.plot(xs,[r[k] for r in rec],label=label)
    plt.axvline(432,linestyle="--")
    plt.axvline(650,linestyle=":")
    plt.ylim(0,1.02); plt.xlabel("task step"); plt.ylabel("learned reliability")
    plt.title("Adaptive source trust across regime reversal")
    plt.legend(); plt.tight_layout()
    plt.savefig(ROOT/"trust_reversal_trajectory.png",dpi=180); plt.close()

    plt.figure(figsize=(8.5,4.6))
    x=np.arange(len(summaries)); w=.34
    plt.bar(x-w/2,[r["early_post_switch_accuracy"] for r in summaries],w,label="early")
    plt.bar(x+w/2,[r["late_post_switch_accuracy"] for r in summaries],w,label="late")
    plt.xticks(x,[r["config"] for r in summaries],rotation=18)
    plt.ylim(0,1.05); plt.ylabel("behavioral accuracy")
    plt.title("Regime reversal: does adaptive trust recover?")
    plt.legend(); plt.tight_layout()
    plt.savefig(ROOT/"regime_reversal_accuracy.png",dpi=180); plt.close()

    plt.figure(figsize=(7,4.5))
    plt.plot([r["verify_prob"] for r in vs],[r["late_accuracy"] for r in vs],marker="o")
    plt.ylim(0,1.05); plt.xlabel("objective verification probability"); plt.ylabel("late post-switch accuracy")
    plt.title("How much verification is needed?")
    plt.tight_layout(); plt.savefig(ROOT/"verification_sweep.png",dpi=180); plt.close()

    results={
        "source_basis":{
            "trust_update":"q_s=exp(-|u_s-y|/sigma); rho_s<-(1-eta)rho_s+eta q_s",
            "bias_update":"b_s<-(1-eta)b_s+eta(u_s-y)",
            "weighting":"w_s proportional to rho_s^3",
            "provenance":"A and B share one durable-memory provenance group in the main adaptive controller",
            "hold":"VALUE_UNRESOLVED/HOLD when evidence is weak or strongly conflicting; HOLD does not fall back to recurrence-only",
            "verified_consequence":"sparse objective verification directly updates both source trust and working memory"
        },
        "experiment":{
            "switch_step":432,
            "pre_switch":"baseline Adrianic-like field; action polarity +1",
            "post_switch":"changed dispersion/damping/slow field/mode/drive; actuator/task polarity reverses",
            "bank_damage_step":650,
            "interpretation":"old memories remain structurally valid but become semantically wrong after the switch; later both durable banks are physically corrupted and parity reconstructs them"
        },
        "summaries":summaries,
        "verification_sweep":vs,
        "guardrails":[
            "The polarity reversal is an engineered structural regime shift intended to make old memories wrong, not a claim that the original Adrianic PDE naturally flips semantics.",
            "Trust equations and evidence hierarchy are taken from the uploaded trust-calibration patch/report.",
            "Objective verification is required to ground trust; source agreement alone is not treated as truth.",
            "Parity repairs storage integrity but cannot decide whether a perfectly reconstructed memory remains relevant in a new regime."
        ]
    }
    (ROOT/"results.json").write_text(json.dumps(results,indent=2))

    (ROOT/"V318_SPEC.md").write_text("""# Adrianic v3.18 — Trust-Calibrated Regime Adaptation

v3.18 combines the seven-role fault-tolerant memory with the uploaded transparent
trust-calibration layer.

Per-source reliability uses:

    q_s = exp(-|u_s-y|/sigma)
    rho_s <- (1-eta)rho_s + eta q_s
    b_s <- (1-eta)b_s + eta(u_s-y)

and trust weights are proportional to rho_s^3.

Sources are cue/current evidence, current field, working memory, durable A/B,
and recurrence. A/B share a provenance group so duplicate memory evidence does
not multiply its voting power.

If evidence is insufficient or highly conflicting, the controller returns
VALUE_UNRESOLVED/HOLD rather than silently falling back to recurrence.

The hard test changes the field physics and reverses the action polarity
mid-run, making previously useful durable memories semantically wrong. Trust
must adapt from sparse verified consequences. Later, A/B are physically
corrupted; parity repairs their integrity, while trust determines whether the
repaired memories deserve influence.
""")

    (ROOT/"README.md").write_text("""# Adrianic v3.18 trust-calibrated regime adaptation

Tests:
- equal source weighting
- frozen trust after the regime switch
- adaptive trust with provenance control
- adaptive trust without provenance control
- oracle source weighting

Also includes a sparse-verification sweep, source-trust trajectories, and a
late dual-bank integrity failure repaired by parity.

See results.json and V318_SPEC.md.
""")

    zip_path=Path("/mnt/data/adrianic_v3_18_trust_adaptation.zip")
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
        for fp in ROOT.rglob("*"):
            if fp.is_file():
                z.write(fp,fp.relative_to(ROOT.parent))

    print("SUMMARIES")
    for r in summaries: print(r)
    print("\\nVERIFICATION SWEEP")
    for r in vs: print(r)
    print("\\nCreated:",zip_path)

if __name__=="__main__":
    main()
