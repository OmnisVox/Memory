from __future__ import annotations

import argparse, hashlib, json, math, random
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
import pandas as pd
import torch

from common_v51 import make_dataset, train_model, batchify, REL_LABELS

OUT = Path('/mnt/data/adrianic_v55_ontology_growth_results')
OUT.mkdir(parents=True, exist_ok=True)


def consequence_vector(rel_label, dim=12):
    '''Opaque environment consequence signature used only as observed outcome.'''
    h = hashlib.sha256(rel_label.encode()).digest()
    vals = np.frombuffer((h * ((dim // len(h)) + 1))[:dim], dtype=np.uint8).astype(float)
    vals = (vals - 127.5) / 127.5
    return vals / (np.linalg.norm(vals) + 1e-12)


def semantic_vectors(model, df):
    x, m, _ = batchify(df)
    model.eval()
    with torch.no_grad():
        ref_logits, rel_logits = model(x, m)
    z = rel_logits.cpu().numpy().astype(float)
    z /= np.linalg.norm(z, axis=1, keepdims=True) + 1e-12
    return z


class Prototype:
    def __init__(self, z, y, step):
        self.z = np.array(z, float)
        self.y = np.array(y, float)
        self.n = 1
        self.last = int(step)

    def update(self, z, y, step, lr=None):
        self.n += 1
        a = (1.0 / self.n) if lr is None else float(lr)
        self.z = (1-a) * self.z + a * z
        self.y = (1-a) * self.y + a * y
        self.z /= np.linalg.norm(self.z) + 1e-12
        self.y /= np.linalg.norm(self.y) + 1e-12
        self.last = int(step)


class ConsequenceOntology:
    '''Growing unlabeled concept slots.

    Slots are born only when an observation is poorly explained in BOTH:
      semantic representation space
      downstream consequence space

    Relation names never enter growth or assignment. They are evaluation-only.
    '''
    def __init__(self, birth_sem=0.30, birth_conseq=0.30, max_slots=24,
                 prune_after=400, min_count=2):
        self.birth_sem = float(birth_sem)
        self.birth_conseq = float(birth_conseq)
        self.max_slots = int(max_slots)
        self.prune_after = int(prune_after)
        self.min_count = int(min_count)
        self.slots = []
        self.births = 0
        self.prunes = 0

    @staticmethod
    def cosine_distance(a, b):
        return float(1.0 - np.dot(a, b) / ((np.linalg.norm(a)+1e-12)*(np.linalg.norm(b)+1e-12)))

    def distances(self, z, y):
        out = []
        for i, p in enumerate(self.slots):
            ds = self.cosine_distance(z, p.z)
            dc = self.cosine_distance(y, p.y)
            # balanced structural evidence; no semantic label weighting
            out.append((0.5*ds + 0.5*dc, ds, dc, i))
        return sorted(out)

    def assign_update(self, z, y, step):
        if not self.slots:
            self.slots.append(Prototype(z, y, step)); self.births += 1
            return 0, True

        best, ds, dc, idx = self.distances(z, y)[0]
        born = False
        if (ds > self.birth_sem and dc > self.birth_conseq and len(self.slots) < self.max_slots):
            self.slots.append(Prototype(z, y, step)); idx = len(self.slots)-1
            self.births += 1; born = True
        else:
            self.slots[idx].update(z, y, step)

        self.prune(step)
        return idx, born

    def assign_only(self, z, y):
        if not self.slots:
            return -1
        return self.distances(z, y)[0][3]

    def prune(self, step):
        keep = []
        for p in self.slots:
            stale = (step - p.last) > self.prune_after
            weak = p.n < self.min_count
            if stale and weak:
                self.prunes += 1
            else:
                keep.append(p)
        self.slots = keep


def cluster_purity(assignments, labels):
    groups = defaultdict(list)
    for a, y in zip(assignments, labels):
        groups[int(a)].append(y)
    correct = 0
    for vals in groups.values():
        correct += Counter(vals).most_common(1)[0][1]
    return correct / max(1, len(labels))


def relation_coverage(assignments, labels):
    # Number of ground-truth relation categories having a dominant dedicated slot.
    mapping = defaultdict(Counter)
    for a, y in zip(assignments, labels):
        mapping[int(a)][y] += 1
    dominant = {cnt.most_common(1)[0][0] for cnt in mapping.values() if cnt}
    return len(dominant) / len(REL_LABELS)


def run_seed(seed, train_repeats=24, test_repeats=12, epochs=26):
    train_df, test_df = make_dataset(seed, train_repeats=train_repeats, test_repeats=test_repeats)
    model = train_model(seed, train_df, epochs=epochs)
    z_train = semantic_vectors(model, train_df)
    z_test = semantic_vectors(model, test_df)

    onto = ConsequenceOntology()
    train_assign = []
    for step, (z, rel) in enumerate(zip(z_train, train_df.rel_label)):
        y = consequence_vector(rel)
        a, born = onto.assign_update(z, y, step)
        train_assign.append(a)

    test_assign = []
    for z, rel in zip(z_test, test_df.rel_label):
        y = consequence_vector(rel)
        test_assign.append(onto.assign_only(z, y))

    # Ablation: semantic-only nearest prototype (ignore consequence at assignment).
    semantic_only = []
    for z in z_test:
        if not onto.slots:
            semantic_only.append(-1); continue
        ds = [onto.cosine_distance(z, p.z) for p in onto.slots]
        semantic_only.append(int(np.argmin(ds)))

    return {
        'seed': seed,
        'slots_final': len(onto.slots),
        'births': onto.births,
        'prunes': onto.prunes,
        'test_purity_full': cluster_purity(test_assign, list(test_df.rel_label)),
        'test_purity_semantic_only': cluster_purity(semantic_only, list(test_df.rel_label)),
        'relation_coverage_full': relation_coverage(test_assign, list(test_df.rel_label)),
        'relation_coverage_semantic_only': relation_coverage(semantic_only, list(test_df.rel_label)),
    }, pd.DataFrame({'seed':seed, 'slot':test_assign, 'semantic_only_slot':semantic_only, 'relation_eval_only':list(test_df.rel_label)})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=4)
    ap.add_argument('--epochs', type=int, default=26)
    args = ap.parse_args(argv)
    rows, details = [], []
    for seed in range(args.seeds):
        print('seed', seed)
        r,d = run_seed(seed, epochs=args.epochs)
        rows.append(r); details.append(d); print(r)
    summary = pd.DataFrame(rows); detail = pd.concat(details, ignore_index=True)
    tag=f'{args.seeds}seed'
    summary.to_csv(OUT/f'{tag}_summary.csv', index=False)
    detail.to_csv(OUT/f'{tag}_details.csv', index=False)
    print(summary.to_string(index=False))


if __name__ == '__main__':
    main()
