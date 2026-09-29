# Extracted verbatim code cells from Adrianic_v3_8_Parity_Coalition_Structural_Plasticity_Lab_EXECUTED.ipynb
# Generated for inspection; notebook remains canonical experimental source.


# %% [notebook cell 3]

import matplotlib
matplotlib.use("Agg")

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json, hashlib, zipfile, shutil, copy, itertools

ROOT=Path("/mnt/data")
SOURCE_CANDIDATES=[
    ROOT/"adrianic_v37_no_buffer_results"/"v34_random_origin_source_v37.csv",
    ROOT/"v34_random_origin_source_v37.csv",
    ROOT/"adrianic_v36_online_seed_results"/"v34_random_origin_source_v36.csv",
    ROOT/"adrianic_v34_emergent_winding_results"/"random_origin_trajectories.csv",
]
SRC=next((p for p in SOURCE_CANDIDATES if p.exists()),None)
if SRC is None:
    raise FileNotFoundError("v3.8 requires the random-origin Adrianic trajectory source.")

V315=ROOT/"adrianic_v3_15_optimal_seven_slots.zip"
OUT=ROOT/"adrianic_v38_parity_coalition_results"
FIG=OUT/"figures"
if OUT.exists():
    shutil.rmtree(OUT)
FIG.mkdir(parents=True)

# -------------------------------------------------------------------------
# Source architecture notes from the user's v3.15 bundle
# -------------------------------------------------------------------------
v315_reference={}
if V315.exists():
    with zipfile.ZipFile(V315) as z:
        r=json.loads(z.read("adrianic_v3_15_optimal_seven_slots/results.json"))
    f=r["fault_coupled_search"]
    v315_reference={
        "fault_coupled_winner":f["ranked"][0],
        "fault_coupled_heldout_winner":f["heldout"][0],
        "fault_coupled_marginals":f["marginals"],
    }

# -------------------------------------------------------------------------
# Data / split
# -------------------------------------------------------------------------
SEQUENCE=[1,4,2,8,5,7]
OBS=["power","entropy","flow_energy","defect_density"]
TARGETS=["power","entropy","flow_energy"]

FOUNDATION=[0,1,2,3]
DEV=list(range(4,12))
VAL=list(range(12,16))
TEST=list(range(16,24))
REPLICATES=list(range(8))

RIDGE=1e-3
D=4
EPOCHS=3

FAULTS=["clean","single","double","coupled","catastrophic"]
FAULT_WEIGHTS={"clean":1.0,"single":1.0,"double":0.7,"coupled":1.2,"catastrophic":1.5}

# Structural consolidation thresholds are fractions of current validation loss.
EDGE_KEEP_FRAC=0.005
PAIR_GAIN_FRAC=0.010
PAIR_SYNERGY_FRAC=0.005

raw=pd.read_csv(SRC)

def label_features(df):
    X=np.zeros((len(df),6))
    mp={d:i for i,d in enumerate(SEQUENCE)}
    digits=df["digit"].astype(int).to_numpy()
    for j,d in enumerate(digits):
        X[j,mp[d]]=1.0
    ang=2*np.pi*digits/10.0
    return np.c_[X,np.cos(ang),np.sin(ang)]

def base_features(df):
    return np.c_[df[OBS].to_numpy(),label_features(df)]

def ridge_fit(X,Y,alpha=RIDGE):
    mu=X.mean(0); sd=X.std(0); sd[sd<1e-12]=1.0
    Z=np.c_[np.ones(len(X)),(X-mu)/sd]
    G=Z.T@Z+alpha*np.eye(Z.shape[1]); G[0,0]-=alpha
    B=np.linalg.solve(G,Z.T@Y)
    return mu,sd,B

def ridge_predict(model,X):
    mu,sd,B=model
    return np.c_[np.ones(len(X)),(X-mu)/sd]@B

def prepare_mode(mode):
    dm=raw[raw["mode"]==mode].sort_values(["seed","local_n"]).copy()
    for c in TARGETS:
        dm["target_"+c]=dm.groupby("seed")[c].shift(-1)
    dm=dm.dropna().copy()

    X=base_features(dm)
    Y=dm[["target_"+c for c in TARGETS]].to_numpy()
    foundation=dm["seed"].isin(FOUNDATION).to_numpy()
    visible=ridge_fit(X[foundation],Y[foundation])
    residual=Y-ridge_predict(visible,X)

    mu=residual[foundation].mean(0)
    sd=residual[foundation].std(0)
    sd[sd<1e-12]=1.0
    R=(residual-mu)/sd

    seq={}
    for s,ds in dm.groupby("seed"):
        ids=dm.index.get_indexer(ds.index)
        seq[int(s)]={"df":ds.reset_index(drop=True),"r":R[ids]}
    return dm,seq,visible,mu,sd

# -------------------------------------------------------------------------
# Provisional recurrent substrate
# -------------------------------------------------------------------------
class ProvisionalRNN:
    """
    Four-unit overcomplete recurrent substrate.

    During development every A/B edge is provisional HOLD: usable, trainable,
    but not yet permanently included. Structural consolidation happens only
    after DEV, using separate VAL trajectories.

    No spin/chirality oracle enters learning.
    """
    def __init__(self,d,seed):
        self.d=d; self.rin=3
        rng=np.random.default_rng(seed)
        self.A=np.eye(d)*0.5+rng.normal(scale=.05,size=(d,d))
        self.B=rng.normal(scale=.08,size=(d,self.rin))
        self.C=rng.normal(scale=.08,size=(self.rin,d))
        self.lrA=.005; self.lrB=.005; self.lrC=.010; self.reg=1e-4
        self.m={k:np.zeros_like(getattr(self,k)) for k in ["A","B","C"]}
        self.v={k:np.zeros_like(getattr(self,k)) for k in ["A","B","C"]}
        self.t={k:0 for k in ["A","B","C"]}
        self.reset()

    def reset(self):
        self.z=np.zeros(self.d)
        self.zprev=np.zeros(self.d)
        self.rprev=np.zeros(self.rin)
        self.have=False

    def _adam(self,name,g,lr):
        b1=.9;b2=.999;eps=1e-8
        self.t[name]+=1; t=self.t[name]
        self.m[name]=b1*self.m[name]+(1-b1)*g
        self.v[name]=b2*self.v[name]+(1-b2)*(g*g)
        mh=self.m[name]/(1-b1**t)
        vh=self.v[name]/(1-b2**t)
        setattr(self,name,getattr(self,name)-lr*mh/(np.sqrt(vh)+eps))

    def step(self,r,train=True):
        pred=self.C@self.z
        err=pred-r

        if train:
            self._adam("C",np.outer(err,self.z)+self.reg*self.C,self.lrC)
            if self.have:
                gz=self.C.T@err
                self._adam("A",np.outer(gz,self.zprev)+self.reg*self.A,self.lrA)
                self._adam("B",np.outer(gz,self.rprev)+self.reg*self.B,self.lrB)

            rho=max(np.abs(np.linalg.eigvals(self.A)))
            if rho>1.02:
                self.A*=1.02/rho

        old=self.z.copy()
        self.z=self.A@self.z+self.B@r
        n=np.linalg.norm(self.z)
        if n>8:
            self.z*=8/n

        self.zprev=old
        self.rprev=np.asarray(r,float).copy()
        self.have=True
        return pred

def train_provisional(seq,replicate):
    m=ProvisionalRNN(D,replicate)
    for _ in range(EPOCHS):
        for s in DEV:
            m.reset()
            for r in seq[s]["r"]:
                m.step(r,train=True)
    return m

# -------------------------------------------------------------------------
# Confidence + parity error management
# -------------------------------------------------------------------------
# P is a simple sum checksum.
# Q uses unique coefficients so a SINGLE-coordinate corruption can be located
# from the syndrome ratio Q/P.
P_COEF=np.ones(D)
Q_COEF=np.array([1.0,-1.0,2.0,-2.0])

def inject_fault(z,p_store,q_store,fault,rng):
    zobs=z.copy(); ps=float(p_store); qs=float(q_store)
    happened=False
    if fault=="clean":
        return zobs,ps,qs,happened

    prob={"single":.12,"double":.08,"coupled":.12,"catastrophic":.16}[fault]
    if rng.random()<prob:
        happened=True
        if fault=="double" or (fault in ["coupled","catastrophic"] and rng.random()<.25):
            inds=rng.choice(len(zobs),size=2,replace=False)
        else:
            inds=[rng.integers(len(zobs))]
        for i in inds:
            zobs[i]+=rng.normal(0,1.2)

        # Coupled faults may also damage checksum banks.
        if fault in ["coupled","catastrophic"]:
            if rng.random() < (.35 if fault=="coupled" else .55):
                ps+=rng.normal(0,1.0)
            if rng.random() < (.15 if fault=="coupled" else .35):
                qs+=rng.normal(0,1.0)
    return zobs,ps,qs,happened

def rollout(model,pack,guard,fault,rng):
    """
    guard:
      none
      confidence
      confidence+P
      confidence+P+Q

    Confidence is generated from the previous residual surprise.
    P/Q are stored with the latent state and checked before the corrupted state
    is used. Dual parity attempts one-coordinate correction.
    """
    A=model.A;B=model.B;C=model.C
    z=np.zeros(D)
    p_store=P_COEF@z
    q_store=Q_COEF@z
    prev_conf=1.0

    sq=[]; faults=0; detects=0; corrections=0

    for r in pack["r"]:
        zobs,ps,qs,happened=inject_fault(z,p_store,q_store,fault,rng)
        faults+=int(happened)

        dp=ps-P_COEF@zobs
        dq=qs-Q_COEF@zobs
        syndrome=float(np.hypot(dp,dq))
        if syndrome>1e-5:
            detects+=1

        conf=prev_conf

        if guard=="confidence+P":
            if abs(dp)>.08:
                conf*=.25

        elif guard=="confidence+P+Q":
            if syndrome>.08:
                repaired=False
                if abs(dp)>1e-6:
                    ratio=dq/dp
                    j=int(np.argmin(np.abs(Q_COEF-ratio)))
                    if abs(Q_COEF[j]-ratio)<.15:
                        # P coefficient is 1 for every component.
                        zobs[j]+=dp
                        dp2=ps-P_COEF@zobs
                        dq2=qs-Q_COEF@zobs
                        if np.hypot(dp2,dq2)<.12:
                            repaired=True
                            corrections+=1
                if repaired:
                    conf=max(conf,.95)
                else:
                    conf*=.20

        # Confidence-only has no checksum before-use correction.
        zuse=conf*zobs if (guard!="none" and conf<.5) else zobs

        pred=C@zuse
        e=pred-r
        sq.append(e*e)

        errn=float(np.sqrt(np.mean(e*e)))
        prev_conf=float(np.exp(-.35*errn)) if guard!="none" else 1.0

        z=A@zuse+B@r
        n=np.linalg.norm(z)
        if n>8:
            z*=8/n

        # Checksums are written alongside the intended state.
        p_store=P_COEF@z
        q_store=Q_COEF@z

    return {
        "mse":float(np.mean(sq)),
        "faults":faults,
        "detections":detects,
        "corrections":corrections,
    }

def fault_battery(model,seq,seeds,guard,reps=1,seed_base=0):
    rows=[]
    for fi,fault in enumerate(FAULTS):
        vals=[]
        det=[];corr=[];nf=[]
        for s in seeds:
            for k in range(reps):
                rng=np.random.default_rng(seed_base+fi*100000+s*100+k)
                r=rollout(model,seq[s],guard,fault,rng)
                vals.append(r["mse"]);det.append(r["detections"])
                corr.append(r["corrections"]);nf.append(r["faults"])
        rows.append({
            "fault":fault,
            "mse":float(np.mean(vals)),
            "mean_faults":float(np.mean(nf)),
            "mean_detections":float(np.mean(det)),
            "mean_corrections":float(np.mean(corr)),
        })
    d=pd.DataFrame(rows)
    weighted=float(np.average(
        d["mse"].to_numpy(),
        weights=np.array([FAULT_WEIGHTS[f] for f in d["fault"]])
    ))
    return weighted,d

# -------------------------------------------------------------------------
# Structural HOLD -> INCLUDE/EXCLUDE
# -------------------------------------------------------------------------
EDGES=[("A",i,j) for i in range(D) for j in range(D)]
EDGES += [("B",i,k) for i in range(D) for k in range(3)]

def model_with_keep(model,keep):
    q=copy.deepcopy(model)
    for typ,i,j in EDGES:
        if (typ,i,j) not in keep:
            getattr(q,typ)[i,j]=0.0
    return q

def ablate(model,edge_list):
    q=copy.deepcopy(model)
    for typ,i,j in edge_list:
        getattr(q,typ)[i,j]=0.0
    return q

def consolidate_structure(model,seq,replicate):
    """
    1) Every A/B edge spent DEV in provisional HOLD.
    2) Direct utility = extra validation loss caused by removing the edge.
    3) Naive controller keeps only directly positive edges.
    4) Coalition controller tests excluded A-edge pairs in the NAIVE sparse
       context. A pair survives only if:
         - adding the pair improves validation loss >=1%, and
         - joint gain exceeds the sum of positive individual gains by >=0.5%.
    """
    full_loss,_=fault_battery(
        model,seq,VAL,"confidence+P+Q",reps=1,seed_base=800000+replicate*1000
    )

    edge_utility={}
    for edge in EDGES:
        loss,_=fault_battery(
            ablate(model,[edge]),seq,VAL,"confidence+P+Q",
            reps=1,seed_base=800000+replicate*1000
        )
        edge_utility[edge]=loss-full_loss

    tau_edge=EDGE_KEEP_FRAC*full_loss
    direct_keep={e for e,u in edge_utility.items() if u>tau_edge}
    naive=model_with_keep(model,direct_keep)
    naive_loss,_=fault_battery(
        naive,seq,VAL,"confidence+P+Q",reps=1,seed_base=810000+replicate*1000
    )

    pruned_A=[e for e in EDGES if e[0]=="A" and e not in direct_keep]
    individual_add_gain={}
    for e in pruned_A:
        cand=model_with_keep(model,direct_keep|{e})
        l,_=fault_battery(
            cand,seq,VAL,"confidence+P+Q",reps=1,seed_base=810000+replicate*1000
        )
        individual_add_gain[e]=naive_loss-l

    tau_pair=PAIR_GAIN_FRAC*naive_loss
    tau_syn=PAIR_SYNERGY_FRAC*naive_loss
    candidate_pairs=[]

    for e1,e2 in itertools.combinations(pruned_A,2):
        cand=model_with_keep(model,direct_keep|{e1,e2})
        l,_=fault_battery(
            cand,seq,VAL,"confidence+P+Q",reps=1,seed_base=810000+replicate*1000
        )
        gain=naive_loss-l
        synergy=gain-max(individual_add_gain[e1],0)-max(individual_add_gain[e2],0)
        if gain>tau_pair and synergy>tau_syn:
            candidate_pairs.append((gain,synergy,e1,e2))

    # Greedy motif consolidation: an accepted pair must still help after any
    # previously accepted motif has been installed.
    candidate_pairs.sort(reverse=True,key=lambda x:x[0])
    coalition_keep=set(direct_keep)
    accepted=[]
    current_loss=naive_loss
    for nominal_gain,synergy,e1,e2 in candidate_pairs:
        cand=model_with_keep(model,coalition_keep|{e1,e2})
        l,_=fault_battery(
            cand,seq,VAL,"confidence+P+Q",reps=1,seed_base=820000+replicate*1000
        )
        actual_gain=current_loss-l
        if actual_gain>tau_pair:
            coalition_keep.update([e1,e2])
            accepted.append({
                "edge1":str(e1),"edge2":str(e2),
                "actual_gain":float(actual_gain),
                "synergy":float(synergy),
            })
            current_loss=l

    coalition=model_with_keep(model,coalition_keep)

    edge_rows=[]
    for e,u in edge_utility.items():
        edge_rows.append({
            "edge":str(e),"type":e[0],"i":e[1],"j":e[2],
            "direct_utility":float(u),
            "direct_keep":e in direct_keep,
            "coalition_keep":e in coalition_keep,
        })

    return {
        "full":model,
        "naive":naive,
        "coalition":coalition,
        "full_val_loss":full_loss,
        "naive_val_loss":naive_loss,
        "coalition_val_loss":current_loss,
        "direct_keep":direct_keep,
        "coalition_keep":coalition_keep,
        "accepted_pairs":accepted,
        "edge_rows":edge_rows,
    }

# -------------------------------------------------------------------------
# Post-hoc dynamical inspection
# -------------------------------------------------------------------------
def collect_clean_states(model,seq,seeds):
    rec=[]
    for s in seeds:
        z=np.zeros(D)
        df=seq[s]["df"]
        for t,r in enumerate(seq[s]["r"]):
            row={
                "seed":s,"local_n":int(df.loc[t,"local_n"]),
                "spin_sin":float(df.loc[t,"spin_sin"]),
                "spin_cos":float(df.loc[t,"spin_cos"]),
            }
            for j,v in enumerate(z):
                row[f"z{j}"]=float(v)
            rec.append(row)
            z=model.A@z+model.B@r
            n=np.linalg.norm(z)
            if n>8:z*=8/n
    return pd.DataFrame(rec)

def posthoc_dynamics(model,seq):
    S=collect_clean_states(model,seq,TEST)
    Zcols=[f"z{j}" for j in range(D)]
    X=[];Y=[]
    for s in TEST:
        q=S[S["seed"]==s].sort_values("local_n")
        z=q[Zcols].to_numpy()
        X.append(z[:-1]);Y.append(z[1:])
    X=np.vstack(X);Y=np.vstack(Y)
    M=np.linalg.solve(X.T@X+1e-4*np.eye(D),X.T@Y).T
    eig=np.linalg.eigvals(M)
    periods=[]
    for e in eig:
        ang=abs(float(np.angle(e)))
        if 1e-5<ang<np.pi-1e-5:
            periods.append(float(2*np.pi/ang))

    # Oracle comparison is strictly post-hoc.
    Str=collect_clean_states(model,seq,list(range(16)))
    Ztr=Str[Zcols].to_numpy()
    Otr=Str[["spin_sin","spin_cos"]].to_numpy()
    Zte=S[Zcols].to_numpy()
    Ote=S[["spin_sin","spin_cos"]].to_numpy()
    om=ridge_fit(Ztr,Otr)
    op=ridge_predict(om,Zte)
    r2=float(1-np.sum((op-Ote)**2)/(np.sum((Ote-Ote.mean(0))**2)+1e-30))

    return eig,periods,r2

# -------------------------------------------------------------------------
# Run experiment
# -------------------------------------------------------------------------
guard_rows=[]
structure_rows=[]
edge_rows=[]
pair_rows=[]
spectrum_rows=[]
oracle_rows=[]

for mode in ["double","single"]:
    _,seq,_,_,_=prepare_mode(mode)

    for rep in REPLICATES:
        full=train_provisional(seq,rep)

        # PARITY TEST: held-out fault battery on identical full graph.
        for guard in ["none","confidence","confidence+P","confidence+P+Q"]:
            _,fd=fault_battery(
                full,seq,TEST,guard,reps=3,seed_base=3000000+rep*1000
            )
            for _,r in fd.iterrows():
                guard_rows.append({
                    "mode":mode,"replicate":rep,"guard":guard,
                    "fault":r["fault"],"mse":r["mse"],
                    "mean_faults":r["mean_faults"],
                    "mean_detections":r["mean_detections"],
                    "mean_corrections":r["mean_corrections"],
                })

        # STRUCTURAL TEST
        con=consolidate_structure(full,seq,rep)

        for kind in ["full","naive","coalition"]:
            model=con[kind]
            weighted,fd=fault_battery(
                model,seq,TEST,"confidence+P+Q",
                reps=3,seed_base=4000000+rep*1000
            )
            structure_rows.append({
                "mode":mode,"replicate":rep,"architecture":kind,
                "weighted_fault_mse":weighted,
                "active_A":int(np.count_nonzero(model.A)),
                "active_B":int(np.count_nonzero(model.B)),
                "active_edges":int(np.count_nonzero(model.A)+np.count_nonzero(model.B)),
                "accepted_pairs":len(con["accepted_pairs"]) if kind=="coalition" else 0,
            })

        for r in con["edge_rows"]:
            r.update({"mode":mode,"replicate":rep})
            edge_rows.append(r)

        for p in con["accepted_pairs"]:
            p.update({"mode":mode,"replicate":rep})
            pair_rows.append(p)

        # Inspect only the coalition graph.
        eig,periods,oracle_r2=posthoc_dynamics(con["coalition"],seq)
        for j,e in enumerate(eig):
            ang=abs(float(np.angle(e)))
            spectrum_rows.append({
                "mode":mode,"replicate":rep,"eigen_index":j,
                "real":float(np.real(e)),"imag":float(np.imag(e)),
                "magnitude":float(np.abs(e)),
                "implied_period":float(2*np.pi/ang)
                    if 1e-5<ang<np.pi-1e-5 else np.nan,
            })
        oracle_rows.append({
            "mode":mode,"replicate":rep,
            "posthoc_spin_oracle_r2":oracle_r2,
            "median_complex_period":float(np.median(periods)) if periods else np.nan,
        })

guard_df=pd.DataFrame(guard_rows)
structure_df=pd.DataFrame(structure_rows)
edge_df=pd.DataFrame(edge_rows)
pair_df=pd.DataFrame(pair_rows)
spectrum_df=pd.DataFrame(spectrum_rows)
oracle_df=pd.DataFrame(oracle_rows)

guard_df.to_csv(OUT/"parity_fault_results.csv",index=False)
structure_df.to_csv(OUT/"structural_architecture_results.csv",index=False)
edge_df.to_csv(OUT/"edge_direct_and_coalition_value.csv",index=False)
pair_df.to_csv(OUT/"accepted_edge_coalitions.csv",index=False)
spectrum_df.to_csv(OUT/"coalition_recurrent_spectrum.csv",index=False)
oracle_df.to_csv(OUT/"posthoc_dynamics_summary.csv",index=False)

# Summaries
guard_summary=guard_df.groupby(["mode","guard","fault"])["mse"].agg(
    ["mean","median","std","count"]
).reset_index()
guard_summary.to_csv(OUT/"parity_fault_summary.csv",index=False)

structure_summary=structure_df.groupby(["mode","architecture"])[
    ["weighted_fault_mse","active_edges","accepted_pairs"]
].agg(["mean","median","std","count"])
structure_summary.to_csv(OUT/"structural_architecture_summary.csv")

pair_summary=(
    pair_df.groupby("mode").agg(
        accepted_pair_count=("edge1","count"),
        mean_actual_gain=("actual_gain","mean"),
        median_synergy=("synergy","median"),
    ).reset_index()
    if len(pair_df) else pd.DataFrame()
)
pair_summary.to_csv(OUT/"coalition_summary.csv",index=False)

# Key comparisons
def get_guard(mode,guard,fault):
    return float(guard_summary[
        (guard_summary["mode"]==mode)&
        (guard_summary["guard"]==guard)&
        (guard_summary["fault"]==fault)
    ]["mean"].iloc[0])

parity_comparisons=[]
for mode in ["double","single"]:
    for fault in FAULTS:
        none=get_guard(mode,"none",fault)
        pq=get_guard(mode,"confidence+P+Q",fault)
        parity_comparisons.append({
            "mode":mode,"fault":fault,
            "none_mse":none,"dual_parity_mse":pq,
            "relative_mse_reduction":(none-pq)/(none+1e-30),
        })
parity_comp_df=pd.DataFrame(parity_comparisons)
parity_comp_df.to_csv(OUT/"parity_comparisons.csv",index=False)

# Figures
fig,ax=plt.subplots(figsize=(8.0,4.6))
q=guard_summary[(guard_summary["mode"]=="double")&
                (guard_summary["fault"].isin(["single","coupled","catastrophic"]))]
for guard in ["none","confidence","confidence+P","confidence+P+Q"]:
    g=q[q["guard"]==guard]
    x=np.arange(len(g))
    ax.plot(g["fault"],g["mean"],marker="o",label=guard)
ax.set_ylabel("held-out residual MSE")
ax.set_title("Parity is error management, not representation")
ax.legend()
fig.tight_layout()
fig.savefig(FIG/"parity_fault_robustness.png",dpi=180)
plt.close(fig)

fig,ax=plt.subplots(figsize=(7.5,4.5))
q=structure_df[structure_df["mode"]=="double"]
for arch in ["full","naive","coalition"]:
    vals=q[q["architecture"]==arch]["weighted_fault_mse"]
    ax.scatter(np.full(len(vals),["full","naive","coalition"].index(arch)),vals,alpha=.7)
ax.set_xticks([0,1,2]);ax.set_xticklabels(["full HOLD","marginal-only","coalition-aware"])
ax.set_ylabel("held-out weighted fault MSE")
ax.set_title("Connection consolidation under fault-coupled utility")
fig.tight_layout()
fig.savefig(FIG/"structural_consolidation.png",dpi=180)
plt.close(fig)

fig,ax=plt.subplots(figsize=(7.5,4.5))
q=structure_df[structure_df["mode"]=="double"]
for arch in ["full","naive","coalition"]:
    vals=q[q["architecture"]==arch]["active_edges"]
    ax.scatter(np.full(len(vals),["full","naive","coalition"].index(arch)),vals,alpha=.7)
ax.set_xticks([0,1,2]);ax.set_xticklabels(["full HOLD","marginal-only","coalition-aware"])
ax.set_ylabel("active A+B connections")
ax.set_title("Edges have to earn permanent existence")
fig.tight_layout()
fig.savefig(FIG/"active_edges.png",dpi=180)
plt.close(fig)

# Decision
double_pc=parity_comp_df[parity_comp_df["mode"]=="double"].set_index("fault")
double_struct=structure_df[structure_df["mode"]=="double"].pivot(
    index="replicate",columns="architecture",values="weighted_fault_mse"
)
single_struct=structure_df[structure_df["mode"]=="single"].pivot(
    index="replicate",columns="architecture",values="weighted_fault_mse"
)

checks={
    "dual_parity_neutral_on_clean_double":
        bool(abs(double_pc.loc["clean","relative_mse_reduction"])<.03),
    "dual_parity_reduces_single_fault_mse_gt_20pct":
        bool(double_pc.loc["single","relative_mse_reduction"]>.20),
    "dual_parity_reduces_coupled_fault_mse_gt_10pct":
        bool(double_pc.loc["coupled","relative_mse_reduction"]>.10),
    "coalition_beats_full_on_median_double_fault_loss":
        bool(np.median(double_struct["coalition"]) < np.median(double_struct["full"])),
    "coalition_beats_marginal_only_in_majority_double_replicates":
        bool(np.mean(double_struct["coalition"] < double_struct["naive"])>.5),
    "coalition_graph_is_sparser_than_full":
        bool(
            structure_df[(structure_df["mode"]=="double")&
                         (structure_df["architecture"]=="coalition")]["active_edges"].median()
            < structure_df[(structure_df["mode"]=="double")&
                           (structure_df["architecture"]=="full")]["active_edges"].median()
        ),
}
decision=(
    "RETAIN PARITY-GUARDED, COALITION-AWARE CONNECTION CONSOLIDATION"
    if all(checks.values())
    else "CONTINUE TESTING / REVISE"
)

report=f"""Adrianic v3.8 — Parity-Guarded Coalition Structural Plasticity

Decision
========
{decision}

Source design evidence
======================
The user's v3.15 seven-slot bundle reported this held-out winner under its
fault-coupled search:

{json.dumps(v315_reference.get("fault_coupled_heldout_winner",{}),indent=2)}

That result motivated a direct test of confidence + dual parity as ERROR
MANAGEMENT around the recurrent state. Spin/chirality is not replaced by parity.

What v3.8 actually implements
=============================
1. A four-unit overcomplete recurrent substrate.
2. Every A/B connection begins as provisional HOLD: usable during development,
   but not automatically permanent.
3. A confidence signal derived from previous residual surprise.
4. Two latent-state checksums:
      P = z0 + z1 + z2 + z3
      Q = z0 - z1 + 2 z2 - 2 z3
   The two-syndrome ratio can locate and correct a single-coordinate corruption.
5. Explicit coupled fault injection that can corrupt latent state and checksum
   banks together.
6. Direct edge value by leave-one-edge-out consequence testing.
7. A naive marginal-only consolidation baseline.
8. A coalition-aware consolidation rule. Excluded recurrent-edge pairs get a
   second chance if their joint add-back is useful and super-additive.

No spin_sin/spin_cos oracle participates in training, parity, edge valuation,
or coalition selection. It is used only after the experiment for interpretation.

Parity results
==============
{guard_summary.to_string(index=False)}

Direct dual-parity comparison
=============================
{parity_comp_df.to_string(index=False)}

Structural results
==================
{structure_summary.to_string()}

Accepted coalitions
===================
{pair_summary.to_string(index=False) if len(pair_summary) else "No edge coalitions survived."}

Post-hoc dynamics
=================
{oracle_df.to_string(index=False)}

Checks
======
{json.dumps(checks,indent=2)}

Interpretation
==============
The parity channels behave as error-management redundancy rather than as an
alternative representation. On clean trajectories they should buy almost
nothing; under internal corruption they should reduce the damage, with dual
parity able to correct a subset of single-coordinate faults. Coupled checksum
faults deliberately limit that advantage.

Connection-level selection also exposes the issue seen in the user's v3.15
seven-slot search: marginal utility is not sufficient. Some recurrent edges that
fail the individual keep criterion become useful only when reintroduced as a
pair in the sparse graph. The coalition rule gives those motifs a provisional
second chance instead of deleting them independently.

Scientific boundary
===================
The P/Q checksum code is hand-designed error redundancy. This experiment does
not show that the agent discovered parity. It tests whether giving parity an
explicitly limited role around a spin/chirality-capable recurrent architecture
improves fault handling.

Likewise, the candidate pair search is an engineered structural-selection
mechanism. Its scientific target is narrower: does coalition-aware selection
preserve useful recurrent motifs that marginal-only pruning destroys?

Next test
=========
If retained, the next step is to make P/Q themselves developmental candidates:
start with no parity channels, let corruption residuals create pressure for
redundancy, and ask whether one or two independent checksum-like channels earn
their existence. That would remove another hand-specified architectural choice.
"""
(OUT/"REPORT.txt").write_text(report)

config={
    "source":str(SRC),
    "v315_reference":v315_reference,
    "sequence":SEQUENCE,
    "foundation":FOUNDATION,
    "development":DEV,
    "validation":VAL,
    "test":TEST,
    "replicates":REPLICATES,
    "latent_dimension":D,
    "epochs":EPOCHS,
    "faults":FAULTS,
    "fault_weights":FAULT_WEIGHTS,
    "structural_thresholds":{
        "edge_keep_fraction":EDGE_KEEP_FRAC,
        "pair_gain_fraction":PAIR_GAIN_FRAC,
        "pair_synergy_fraction":PAIR_SYNERGY_FRAC,
    },
    "parity":{
        "P":P_COEF.tolist(),
        "Q":Q_COEF.tolist(),
    },
}
(OUT/"config.json").write_text(json.dumps(config,indent=2))
(OUT/"checks.json").write_text(json.dumps(checks,indent=2))

# Archive exact input source and v3.15 bundle if present.
shutil.copy2(SRC,OUT/"source_random_origin_trajectories.csv")
if V315.exists():
    shutil.copy2(V315,OUT/V315.name)

manifest={"experiment":"Adrianic v3.8 parity coalition structural plasticity","files":[]}
for p in sorted(OUT.rglob("*")):
    if p.is_file():
        b=p.read_bytes()
        manifest["files"].append({
            "path":str(p.relative_to(OUT)),
            "bytes":len(b),
            "sha256":hashlib.sha256(b).hexdigest(),
        })
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2))

zip_path=ROOT/"Adrianic_v3_8_Parity_Coalition_Structural_Plasticity_Results.zip"
with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
    for p in OUT.rglob("*"):
        if p.is_file():
            z.write(p,arcname=p.relative_to(OUT))

print(report)
print("Results bundle:",zip_path)

