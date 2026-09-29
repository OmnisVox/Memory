from __future__ import annotations

import argparse, json, math, random
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from common_v51 import (
    make_dataset, train_model, batchify, decode_class, parse_key,
    forecast_code, external_observation, evaluate_governance,
)

OUT = Path('/mnt/data/adrianic_v53_progressive_recall_results')
OUT.mkdir(parents=True, exist_ok=True)


def make_full_ranked_proposals(model, test_df):
    x, m, _ = batchify(test_df)
    model.eval()
    with torch.no_grad():
        ref_logits, rel_logits = model(x, m)
        ref_probs = F.softmax(ref_logits, dim=-1).cpu().numpy()
        rel_probs = F.softmax(rel_logits, dim=-1).cpu().numpy()

    rows = []
    for i, row in test_df.reset_index(drop=True).iterrows():
        joint = np.outer(ref_probs[i], rel_probs[i]).reshape(-1)
        joint /= joint.sum() + 1e-12
        order = np.argsort(-joint)
        keys, probs = [], []
        for cid in order:
            r, rel = decode_class(int(cid))
            keys.append(parse_key(r, rel))
            probs.append(float(joint[cid]))

        top1_ref, top1_rel = decode_class(int(order[0]))
        top1_key = parse_key(top1_ref, top1_rel)
        if top1_key == row.parse_key:
            et = 'correct'
        else:
            ref_ok = top1_ref == int(row.ref_idx)
            rel_ok = top1_rel == row.rel_label
            if ref_ok and not rel_ok:
                et = 'relation_only'
            elif rel_ok and not ref_ok:
                et = 'referent_only'
            else:
                et = 'both'

        out = dict(row)
        out.update({
            'ranked_keys': keys,
            'ranked_probs': probs,
            'top1_parse': top1_key,
            'top1_correct': int(top1_key == row.parse_key),
            'top1_error_type': et,
        })
        rows.append(out)
    return pd.DataFrame(rows)


class ProgressiveRecall:
    '''Demand-driven semantic capacity.

    Starts with a small proposal prefix. Evidence updates trust. If the active
    set cannot resolve, more hypotheses are recalled and prior evidence is
    replayed into only the newly recalled candidates.
    '''
    def __init__(self, keys, probs, initial_k=4, step_k=4, max_k=24,
                 lr=0.18, resolve_trust=0.78, resolve_margin=0.18):
        self.keys = list(keys)
        self.prior = {k: float(p) for k, p in zip(keys, probs)}
        self.initial_k = int(initial_k)
        self.step_k = int(step_k)
        self.max_k = min(int(max_k), len(self.keys))
        self.lr = float(lr)
        self.resolve_trust = float(resolve_trust)
        self.resolve_margin = float(resolve_margin)
        self.active = self.keys[:self.initial_k]
        self.trust = {k: 0.5 for k in self.active}
        self.history = []
        self.expansions = 0

    def _update_one(self, k, obs, forecast_fn):
        q = 1.0 if forecast_fn(k) == obs else 0.0
        self.trust[k] = (1.0 - self.lr) * self.trust[k] + self.lr * q

    def update(self, obs, forecast_fn):
        self.history.append(obs)
        for k in self.active:
            self._update_one(k, obs, forecast_fn)

    def score(self, k):
        t = min(1 - 1e-6, max(1e-6, self.trust[k]))
        return max(1e-12, self.prior[k]) * (t / (1 - t))

    def ranked(self):
        return sorted(self.active, key=lambda k: (self.score(k), self.trust[k]), reverse=True)

    def resolved(self):
        r = self.ranked()
        if not r:
            return False
        top = r[0]
        if len(r) == 1:
            margin = 1.0
        else:
            a, b = self.score(r[0]), self.score(r[1])
            margin = (a - b) / (abs(a) + 1e-12)
        return self.trust[top] >= self.resolve_trust and margin >= self.resolve_margin

    def maybe_expand(self, forecast_fn):
        if self.resolved() or len(self.active) >= self.max_k:
            return False
        old_n = len(self.active)
        new_n = min(self.max_k, old_n + self.step_k)
        new_keys = self.keys[old_n:new_n]
        self.active.extend(new_keys)
        for k in new_keys:
            self.trust[k] = 0.5
            for obs in self.history:
                self._update_one(k, obs, forecast_fn)
        self.expansions += 1
        return True

    def choose(self):
        return self.ranked()[0]


def evaluate_progressive(ranked_df, seed, noise, initial_k=4, step_k=4,
                         max_k=24, evidence_episodes=12):
    rng = random.Random(seed + 53001 + int(noise * 1000))
    rows = []
    for i, row in ranked_df.reset_index(drop=True).iterrows():
        case_id = f's{seed}_case{i}'
        true_key = row.parse_key
        ctrl = ProgressiveRecall(row.ranked_keys, row.ranked_probs,
                                 initial_k=initial_k, step_k=step_k, max_k=max_k)
        first_seen = 0 if true_key in ctrl.active else None
        for ep in range(1, evidence_episodes + 1):
            obs = external_observation(case_id, true_key, row.ranked_keys[:max_k], noise, rng)
            forecast_fn = lambda k, cid=case_id: forecast_code(cid, k)
            ctrl.update(obs, forecast_fn)
            ctrl.maybe_expand(forecast_fn)
            if first_seen is None and true_key in ctrl.active:
                first_seen = ep
        choice = ctrl.choose()
        rows.append({
            'seed': seed, 'noise': noise, 'case_id': case_id,
            'true_key': true_key, 'top1_correct': row.top1_correct,
            'top1_error_type': row.top1_error_type,
            'progressive_choice': choice,
            'progressive_correct': int(choice == true_key),
            'final_k': len(ctrl.active), 'expansions': ctrl.expansions,
            'resolved': int(ctrl.resolved()),
            'true_recalled': int(true_key in ctrl.active),
            'first_seen_episode': first_seen if first_seen is not None else evidence_episodes + 1,
        })
    return pd.DataFrame(rows)


def evaluate_fixed(ranked_df, seed, noise, k):
    tmp = ranked_df.copy()
    tmp['topk_parse_keys'] = [xs[:k] for xs in tmp.ranked_keys]
    tmp['topk_probs'] = [ps[:k] for ps in tmp.ranked_probs]
    tmp['topk_contains_true'] = [int(r.parse_key in r.topk_parse_keys) for _, r in tmp.iterrows()]
    return evaluate_governance(tmp, seed=seed, noise=noise)


def run_seed(seed, train_repeats=24, test_repeats=12, epochs=26):
    train_df, test_df = make_dataset(seed, train_repeats=train_repeats, test_repeats=test_repeats)
    model = train_model(seed, train_df, epochs=epochs)
    ranked = make_full_ranked_proposals(model, test_df)
    summaries, details = [], []
    for noise in (0.0, 0.15, 0.30):
        prog = evaluate_progressive(ranked, seed, noise)
        details.append(prog)
        fixed8 = evaluate_fixed(ranked, seed, noise, 8)
        fixed24 = evaluate_fixed(ranked, seed, noise, 24)
        hard = prog[prog.top1_correct == 0]
        summaries.append({
            'seed': seed, 'noise': noise,
            'top1_accuracy': float(ranked.top1_correct.mean()),
            'progressive_accuracy': float(prog.progressive_correct.mean()),
            'progressive_recall': float(prog.true_recalled.mean()),
            'progressive_mean_k': float(prog.final_k.mean()),
            'progressive_median_k': float(prog.final_k.median()),
            'progressive_mean_expansions': float(prog.expansions.mean()),
            'progressive_resolved_rate': float(prog.resolved.mean()),
            'progressive_hard_rescue': float(hard.progressive_correct.mean()),
            'fixed8_accuracy': float(fixed8.adaptive_correct.mean()),
            'fixed8_recall': float(fixed8.topk_covered.mean()),
            'fixed24_accuracy': float(fixed24.adaptive_correct.mean()),
            'fixed24_recall': float(fixed24.topk_covered.mean()),
        })
    return pd.DataFrame(summaries), pd.concat(details, ignore_index=True), ranked


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=4)
    ap.add_argument('--train-repeats', type=int, default=24)
    ap.add_argument('--test-repeats', type=int, default=12)
    ap.add_argument('--epochs', type=int, default=26)
    args = ap.parse_args(argv)

    ss, dd, rr = [], [], []
    for seed in range(args.seeds):
        print('seed', seed)
        s, d, r = run_seed(seed, args.train_repeats, args.test_repeats, args.epochs)
        ss.append(s); dd.append(d); r['seed'] = seed; rr.append(r)
        print(s.to_string(index=False))

    summary = pd.concat(ss, ignore_index=True)
    details = pd.concat(dd, ignore_index=True)
    ranked = pd.concat(rr, ignore_index=True)
    tag = f'{args.seeds}seed'
    summary.to_csv(OUT / f'{tag}_summary.csv', index=False)
    details.to_csv(OUT / f'{tag}_details.csv', index=False)
    ranked.to_csv(OUT / f'{tag}_ranked_proposals.csv', index=False)

    checks = {
        'progressive_beats_fixed8_accuracy_fraction': float(np.mean(summary.progressive_accuracy > summary.fixed8_accuracy)),
        'progressive_recall_above_fixed8_fraction': float(np.mean(summary.progressive_recall > summary.fixed8_recall)),
        'progressive_uses_less_than_full24_fraction': float(np.mean(summary.progressive_mean_k < 24)),
    }
    (OUT / f'{tag}_checks.json').write_text(json.dumps(checks, indent=2))
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
