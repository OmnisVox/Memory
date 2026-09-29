exec(open('/mnt/data/evidence_v3_core.py').read())

def verify_filtered(anchors,a,vreps,hist):
    vm,vc=anchors.aggregate_verifiers(vreps);ac=max(0,a-anchors.anchor_bias);d=abs(ac-vm);hist.append(d)
    if len(hist)>40:
        arr=np.array(hist[-300:]);med=np.median(arr);mad=np.median(np.abs(arr-med))+1e-6;th=med+2.8*1.4826*mad
    else:th=1.0
    flagged=d>th
    if flagged:
        return vm,float(.85*vc),True
    # blend when routine anchor is not anomalous
    wa=max(.01,anchors.anchor_trust)**3;wv=max(.01,vc)**3;m=float((wa*ac+wv*vm)/(wa+wv+1e-15));conf=float(np.clip((wa*anchors.anchor_trust+wv*vc)/(wa+wv+1e-15)*np.exp(-d/(.5+m)),0,1));return m,conf,False

def run_filtered(seed,n=1000,anchor_corrupt=.2,gold_prob=.01):
    rng=np.random.default_rng(6000000+seed);stream=make_stream(seed,n);trust=Trust(SOURCES,.5);graph=Graph(SOURCES);anchors=AnchorLayer();mem=Memory(10);adv=AdaptiveAdversary(7000000+seed);hist=[];flags=0;total=captured=0.;pre=[0.,0.];post=[0.,0.]
    for block0 in range(0,n,100):
        trust.decay();graph.common*=.94;pending=[]
        for t,cls,label,y in stream[block0:min(n,block0+100)]:
            hit=mem.touch(label,t);total+=y;captured+=y if hit else 0;(pre if t<n//2 else post)[0]+=y;(pre if t<n//2 else post)[1]+=y if hit else 0
            mem.observe(label,cls,t);reps=base_reports(y,cls,rng);reps,_=adv.apply(reps,y,cls,trust.effdict(),graph.common,t,n);m,conf,w,vals,red=graph.aggregate(reps,trust);mem.value(label,m,conf,t,False);dev=[trust.eff(s)*abs(vals[i]-m)/(max(.25,trust.mae[s])+.25) for i,s in enumerate(SOURCES)];diag=.63*min(max(dev),3)/3+.2*(1-conf)+.1*min(m/3,1)+.07*graph.common;pending.append((diag,label,y,reps));mem.expire(t)
        ridx=int(rng.integers(0,len(pending)));didx=int(np.argmax([p[0] for p in pending]));didx=(didx+1)%len(pending) if didx==ridx else didx
        for kind,idx in [('random',ridx),('target',didx)]:
            _,label,y,reps=pending[idx];a,_=anchors.routine_anchor(y,rng,anchor_corrupt);vreps=anchors.verifier_reports(y,rng)
            if rng.random()<gold_prob:anchors.calibrate_from_gold(a,vreps,y)
            vy,vconf,flag=verify_filtered(anchors,a,vreps,hist);flags+=int(flag)
            if kind=='random' and vconf>=.48:
                for s,x in reps.items():trust.calibration(s,x,vy)
                graph.update(reps,vy)
            elif kind=='target' and vconf>=.52:
                attribute_incident(trust,graph,reps,vy)
            mem.value(label,vy,vconf,block0+99,verified=(vconf>=.70))
    cls=[s.cls for s in mem.slots]
    return {'seed':seed,'utility_capture':captured/(total+1e-15),'post_capture':post[1]/(post[0]+1e-15),'writes':mem.writes,'unresolved':mem.unresolved,'junk_slots':cls.count('junk'),'rho_A':trust.eff('A'),'rho_E':trust.eff('E'),'flags':flags}

rows=[]
for cp in [.1,.2,.35]:
    for seed in range(16):
        r=run_filtered(seed,n=1000,anchor_corrupt=cp,gold_prob=.01);r['anchor_corrupt']=cp;rows.append(r)
df=pd.DataFrame(rows);agg=df.groupby('anchor_corrupt').agg(utility_capture=('utility_capture','mean'),post_capture=('post_capture','mean'),writes=('writes','mean'),unresolved=('unresolved','mean'),junk_slots=('junk_slots','mean'),rho_A=('rho_A','mean'),rho_E=('rho_E','mean'),flags=('flags','mean')).reset_index();df.to_csv(OUT/'filtered_end_to_end_trials.csv',index=False);agg.to_csv(OUT/'filtered_end_to_end_aggregate.csv',index=False);print(agg.to_string(index=False))
