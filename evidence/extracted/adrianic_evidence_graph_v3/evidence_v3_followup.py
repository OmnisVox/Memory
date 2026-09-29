exec(open('/mnt/data/evidence_v3_core.py').read())

# Gold-rate sweep under imperfect anchors + adaptive adversary
rows=[]
for gp in [0.003,0.01,0.03]:
    for cp in [0.10,0.20]:
        for policy in ['naive','robust']:
            for seed in range(12):
                r=run(seed,policy=policy,n=1000,anchor_corrupt=cp,gold_prob=gp)
                r.update(gold_prob=gp,anchor_corrupt=cp)
                rows.append(r)
g=pd.DataFrame(rows)
ga=g.groupby(['gold_prob','anchor_corrupt','policy']).agg(
 utility_capture=('utility_capture','mean'),post_capture=('post_capture','mean'),
 writes=('writes','mean'),unresolved=('unresolved','mean'),junk_slots=('junk_slots','mean'),
 anchor_trust=('anchor_trust','mean'),rho_A=('rho_A','mean'),rho_E=('rho_E','mean')).reset_index()
ga.to_csv(OUT/'gold_rate_sweep.csv',index=False)
print('Gold sweep:\n',ga.to_string(index=False))

# Improved zero-dropout repair + same 12D vector
def inpaint_amp(psi):
    a=np.abs(psi).copy(); mask=a<1e-12
    if mask.mean()<0.08:return a
    z=a.copy(); valid=~mask
    for _ in range(12):
        sums=np.zeros_like(z);cnt=np.zeros_like(z,float)
        for sh,ax in [(1,0),(-1,0),(1,1),(-1,1)]:
            zv=np.roll(z,sh,ax);vv=np.roll(valid,sh,ax);sums+=zv*vv;cnt+=vv
        fill=(~valid)&(cnt>0)
        z[fill]=sums[fill]/cnt[fill];valid[fill]=True
        if valid.all():break
    return z

def field_vec2(psi):
    a=inpaint_amp(psi);N=a.shape[0];sm=a.copy()
    for _ in range(8):sm=(4*sm+np.roll(sm,1,0)+np.roll(sm,-1,0)+np.roll(sm,1,1)+np.roll(sm,-1,1))/8
    work=sm.copy();work[:3,:]=np.inf;work[-3:,:]=np.inf;work[:,:3]=np.inf;work[:,-3:]=np.inf
    y1,x1=np.unravel_index(np.argmin(work),work.shape);yy,xx=np.mgrid[:N,:N];w2=work.copy();w2[(xx-x1)**2+(yy-y1)**2<=16]=np.inf;y2,x2=np.unravel_index(np.argmin(w2),w2.shape)
    pts=sorted([(x1/N,y1/N),(x2/N,y2/N)],key=lambda p:p[0]);(xa,ya),(xb,yb)=pts
    core=[xa,ya,xb,yb,(xa+xb)/2,(ya+yb)/2,np.hypot(xb-xa,yb-ya)]
    s=a.sum()+1e-15;y,x=np.mgrid[:N,:N];cx=(x*a).sum()/s/N;cy=(y*a).sum()/s/N;X=x/N-cx;Y=y/N-cy
    mom=[cx,cy,(X*X*a).sum()/s,(Y*Y*a).sum()/s,(X*Y*a).sum()/s]
    return np.array(core+mom,float)

def make_field(N=40,sep=10,shift=(0,0),chir=1):
    y,x=np.mgrid[:N,:N];sy,sx=shift;cy=N//2+sy;x1=N//2-sep//2+sx;x2=N//2+sep//2+sx
    r1=np.hypot(x-x1,y-cy);r2=np.hypot(x-x2,y-cy);th1=np.arctan2(y-cy,x-x1);th2=np.arctan2(y-cy,x-x2);A=np.tanh(r1/2)*np.tanh(r2/2)
    return .65*A*np.exp(1j*chir*(th1-th2))

def corrupt_field(psi,rng,kind):
    a=np.abs(psi);ph=np.angle(psi)
    if kind=='phase_wipe':return a.astype(complex)
    if kind=='mixed':return np.clip(a*(1+.18*rng.normal(size=a.shape)),0,None)*np.exp(1j*(.55*ph+.45*rng.normal(size=a.shape)))
    if kind=='dropout':
        z=psi.copy();z[rng.random(z.shape)<.35]=0;return z
    return psi.copy()
fields=[]
for sep in [8,12,16]:
    for sh in [(-5,-5),(0,0),(5,5),(5,-5)]:fields.append(make_field(sep=sep,shift=sh))
X=np.stack([field_vec2(f) for f in fields]);scale=np.maximum(X.std(axis=0),.02)
rows=[]
for kind in ['phase_wipe','mixed','dropout']:
    for target in range(len(fields)):
        for seed in range(20):
            rng=np.random.default_rng(700000+target*100+seed);q=corrupt_field(fields[target],rng,kind);v=field_vec2(q);D=np.linalg.norm((X-v)/scale,axis=1)/np.sqrt(X.shape[1]);o=np.argsort(D);rows.append({'corruption':kind,'correct':int(o[0]==target),'margin':D[o[1]]-D[o[0]]})
f=pd.DataFrame(rows);fa=f.groupby('corruption').agg(address_accuracy=('correct','mean'),margin=('margin','median')).reset_index();fa.to_csv(OUT/'field_reintegration_repaired.csv',index=False)
print('\nRepaired field reintegration:\n',fa.to_string(index=False))

# plots
fig,ax=plt.subplots(figsize=(8,4.8))
for (gp,p),gg in ga[ga.anchor_corrupt==0.20].groupby(['gold_prob','policy']):
    pass
for p,gg in ga[ga.anchor_corrupt==0.20].groupby('policy'):
    ax.plot(gg.gold_prob*100,gg.utility_capture,marker='o',label=p)
ax.set_xlabel('Gold calibration rate (%)');ax.set_ylabel('Utility captured');ax.set_title('20% corrupted routine anchors');ax.legend();fig.tight_layout();fig.savefig(OUT/'gold_calibration_sweep.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4.8));ax.bar(fa.corruption,fa.address_accuracy);ax.set_ylim(0,1.02);ax.set_ylabel('Exact field-memory address accuracy');ax.set_title('Field reintegration after dropout-aware repair');fig.tight_layout();fig.savefig(OUT/'field_reintegration_repaired.png',dpi=170);plt.close(fig)
