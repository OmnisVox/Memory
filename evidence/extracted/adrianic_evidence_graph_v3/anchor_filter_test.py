import numpy as np,pandas as pd,matplotlib.pyplot as plt
from pathlib import Path
OUT=Path('/mnt/data/adrianic_evidence_graph_v3');OUT.mkdir(exist_ok=True)

def ver_reports(y,rng):
    return {'V1':max(0,y+rng.normal(0,.18)),'V2':max(0,y+rng.normal(0,.38)),'V3':max(0,2.4-.25*y+rng.normal(0,.35))}

def anchor(y,rng,p):
    bad=rng.random()<p
    if bad:
        a=max(0,2.5+rng.normal(0,.2)) if y<.2 else max(0,.25*y+rng.normal(0,.15))
    else:a=max(0,y+rng.normal(0,.05))
    return a,bad

class VTrust:
    def __init__(self):self.rho={n:.5 for n in ['V1','V2','V3']};self.bias={n:0. for n in self.rho}
    def update(self,n,x,y):
        q=np.exp(-abs(x-y));eta=.1;self.rho[n]=(1-eta)*self.rho[n]+eta*q;self.bias[n]=(1-eta)*self.bias[n]+eta*(x-y)
    def combine(self,reps):
        names=list(reps);w=np.array([max(.01,self.rho[n])**3 for n in names]);w/=w.sum()+1e-15;vals=np.array([max(0,reps[n]-self.bias[n]) for n in names]);return float(w@vals)

def run(seed,p=.2,n=5000,gold=.01):
    rng=np.random.default_rng(seed);vt=VTrust();ds=[];flag_hist=[];errors_raw=[];errors_filt=[];correct=[]
    # running robust disagreement stats
    hist=[]
    for t in range(n):
        # mixture of utilities incl many near zero and some critical
        u=rng.choice([0.0,.05,1.0,4.5],p=[.15,.35,.42,.08]);u=max(0,u*(1+.2*rng.normal()))
        a,bad=anchor(u,rng,p);vr=ver_reports(u,rng)
        if rng.random()<gold:
            for name,x in vr.items():vt.update(name,x,u)
        vm=vt.combine(vr);d=abs(a-vm);hist.append(d)
        if len(hist)>40:
            arr=np.array(hist[-300:]);med=np.median(arr);mad=np.median(np.abs(arr-med))+1e-6;th=med+2.8*1.4826*mad
        else:th=1.0
        flag=d>th
        filt=vm if flag else (0.70*a+0.30*vm)
        ds.append({'t':t,'bad':int(bad),'disagreement':d,'threshold':th,'flag':int(flag),'raw_error':abs(a-u),'filtered_error':abs(filt-u)})
    df=pd.DataFrame(ds)
    tp=((df.bad==1)&(df.flag==1)).sum();fp=((df.bad==0)&(df.flag==1)).sum();fn=((df.bad==1)&(df.flag==0)).sum();tn=((df.bad==0)&(df.flag==0)).sum()
    return {'seed':seed,'corrupt_prob':p,'precision':tp/max(tp+fp,1),'recall':tp/max(tp+fn,1),'false_positive_rate':fp/max(fp+tn,1),'raw_mae':df.raw_error.mean(),'filtered_mae':df.filtered_error.mean(),'error_reduction':1-df.filtered_error.mean()/df.raw_error.mean()},df

rows=[]
for p in [.05,.1,.2,.35]:
    for seed in range(30):
        r,_=run(1000+seed,p=p,n=3000,gold=.01);rows.append(r)
agg=pd.DataFrame(rows).groupby('corrupt_prob').agg(precision=('precision','mean'),recall=('recall','mean'),false_positive_rate=('false_positive_rate','mean'),raw_mae=('raw_mae','mean'),filtered_mae=('filtered_mae','mean'),error_reduction=('error_reduction','mean')).reset_index();agg.to_csv(OUT/'anchor_filter_aggregate.csv',index=False);print(agg.to_string(index=False))
_,ex=run(999,p=.2,n=3000,gold=.01);ex.to_csv(OUT/'anchor_filter_example.csv',index=False)
fig,ax=plt.subplots(figsize=(8,4.8));ax.plot(agg.corrupt_prob*100,agg.raw_mae,marker='o',label='raw routine anchor');ax.plot(agg.corrupt_prob*100,agg.filtered_mae,marker='o',label='cross-checked anchor');ax.set_xlabel('Corrupted routine anchors (%)');ax.set_ylabel('Mean absolute verification error');ax.set_title('Verifier cross-check detects imperfect anchors');ax.legend();fig.tight_layout();fig.savefig(OUT/'anchor_filter_mae.png',dpi=170);plt.close(fig)
