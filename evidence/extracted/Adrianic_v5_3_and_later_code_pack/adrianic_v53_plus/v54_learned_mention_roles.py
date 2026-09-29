from __future__ import annotations

import argparse, json, random, re
from pathlib import Path
from itertools import permutations
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

from common_v51 import (
    make_dataset, train_model, make_proposals, evaluate_governance,
)

OUT = Path('/mnt/data/adrianic_v54_learned_mentions_results')
OUT.mkdir(parents=True, exist_ok=True)
WORD_RE = re.compile(r"[A-Za-z]+|[.,]")
ROLE_NONE, ROLE_0, ROLE_1, ROLE_2, ROLE_T = range(5)
ROLE_NAMES = {ROLE_NONE:'none', ROLE_0:'n0', ROLE_1:'n1', ROLE_2:'n2', ROLE_T:'n3'}
CHARS = ['<pad>','<unk>'] + list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
C2I = {c:i for i,c in enumerate(CHARS)}


def words(text):
    return WORD_RE.findall(text)


def char_ids(token, max_chars=16):
    ids = [C2I.get(c, 1) for c in token[:max_chars]]
    return ids + [0] * (max_chars - len(ids))


def role_labels(row):
    toks = words(row.raw_text)
    lookup = {
        row.name0.lower(): ROLE_0,
        row.name1.lower(): ROLE_1,
        row.name2.lower(): ROLE_2,
        row.target_name.lower(): ROLE_T,
    }
    return toks, [lookup.get(t.lower(), ROLE_NONE) for t in toks]


def tensorize(df, max_tokens=40, max_chars=16):
    xs, masks, ys = [], [], []
    for _, row in df.iterrows():
        toks, labs = role_labels(row)
        toks = toks[:max_tokens]; labs = labs[:max_tokens]
        x = [char_ids(t, max_chars) for t in toks]
        mask = [1] * len(x)
        while len(x) < max_tokens:
            x.append([0] * max_chars); mask.append(0); labs.append(ROLE_NONE)
        xs.append(x); masks.append(mask); ys.append(labs)
    return (
        torch.tensor(xs, dtype=torch.long),
        torch.tensor(masks, dtype=torch.long),
        torch.tensor(ys, dtype=torch.long),
    )


class MentionRoleModel(nn.Module):
    '''Character token encoder + contextual transformer + token role head.'''
    def __init__(self, d_char=24, d_model=64, heads=4, layers=2, max_tokens=40):
        super().__init__()
        self.char_emb = nn.Embedding(len(CHARS), d_char, padding_idx=0)
        self.token_proj = nn.Linear(d_char, d_model)
        self.pos = nn.Embedding(max_tokens, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=heads, dim_feedforward=128,
            dropout=.1, batch_first=True, activation='gelu')
        self.enc = nn.TransformerEncoder(layer, num_layers=layers)
        self.out = nn.Linear(d_model, 5)

    def forward(self, chars, mask):
        # mean char embedding per token
        e = self.char_emb(chars)
        cmask = (chars != 0).float().unsqueeze(-1)
        tok = (e * cmask).sum(2) / (cmask.sum(2) + 1e-6)
        tok = self.token_proj(tok)
        t = tok.size(1)
        p = torch.arange(t, device=tok.device)[None, :].expand(tok.size(0), t)
        z = self.enc(tok + self.pos(p), src_key_padding_mask=(mask == 0))
        return self.out(z)


def train_mention_model(seed, train_df, epochs=16):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    model = MentionRoleModel()
    x, m, y = tensorize(train_df)
    opt = torch.optim.AdamW(model.parameters(), lr=.003, weight_decay=1e-4)
    n = len(train_df)
    # upweight entity-role tokens vs background
    weights = torch.tensor([.20, 1., 1., 1., 1.], dtype=torch.float)
    for ep in range(epochs):
        order = torch.randperm(n)
        for start in range(0, n, 64):
            idx = order[start:start+64]
            logits = model(x[idx], m[idx])
            loss = F.cross_entropy(
                logits.reshape(-1, 5), y[idx].reshape(-1), weight=weights,
                ignore_index=-100)
            opt.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    return model


def decode_roles(model, df):
    x, m, y = tensorize(df)
    model.eval()
    with torch.no_grad():
        probs = F.softmax(model(x, m), dim=-1).cpu().numpy()
    rows = []
    for i, (_, row) in enumerate(df.reset_index(drop=True).iterrows()):
        toks = words(row.raw_text)[:probs.shape[1]]
        n = len(toks)
        # Search a small distinct assignment over top candidates per role.
        role_cands = {}
        for role in (ROLE_0, ROLE_1, ROLE_2, ROLE_T):
            order = np.argsort(-probs[i, :n, role])[:5]
            role_cands[role] = list(map(int, order))
        best = None
        # brute-force 5^4 <= 625 assignments, reject duplicate token positions
        for a in role_cands[ROLE_0]:
            for b in role_cands[ROLE_1]:
                for c in role_cands[ROLE_2]:
                    for d in role_cands[ROLE_T]:
                        inds = (a,b,c,d)
                        if len(set(inds)) < 4: continue
                        score = (
                            np.log(probs[i,a,ROLE_0] + 1e-12) +
                            np.log(probs[i,b,ROLE_1] + 1e-12) +
                            np.log(probs[i,c,ROLE_2] + 1e-12) +
                            np.log(probs[i,d,ROLE_T] + 1e-12))
                        if best is None or score > best[0]:
                            best = (score, inds)
        inds = best[1]
        pred_names = [toks[j] for j in inds]
        true_names = [row.name0, row.name1, row.name2, row.target_name]
        rows.append({
            'pred_name0': pred_names[0], 'pred_name1': pred_names[1],
            'pred_name2': pred_names[2], 'pred_target': pred_names[3],
            'all_roles_correct': int(all(p.lower()==t.lower() for p,t in zip(pred_names,true_names))),
            'role0_correct': int(pred_names[0].lower()==row.name0.lower()),
            'role1_correct': int(pred_names[1].lower()==row.name1.lower()),
            'role2_correct': int(pred_names[2].lower()==row.name2.lower()),
            'target_correct': int(pred_names[3].lower()==row.target_name.lower()),
        })
    return pd.DataFrame(rows)


def normalize_detected(raw, predicted_names):
    out = raw.lower()
    # longest first
    for idx, name in sorted(enumerate(predicted_names), key=lambda x: len(x[1]), reverse=True):
        out = re.sub(rf'\b{re.escape(name.lower())}\b', f'<n{idx}>', out)
    return out


def run_seed(seed, train_repeats=24, test_repeats=12, mention_epochs=16, parser_epochs=26, top_k=8):
    train_df, test_df = make_dataset(seed, train_repeats=train_repeats, test_repeats=test_repeats)
    mention = train_mention_model(seed, train_df, epochs=mention_epochs)
    detected = decode_roles(mention, test_df)

    # Parser is trained on gold mention slots; test receives learned mention slots.
    parser = train_model(seed, train_df, epochs=parser_epochs)
    detected_test = test_df.copy().reset_index(drop=True)
    texts = []
    for i, row in detected_test.iterrows():
        pr = detected.iloc[i]
        texts.append(normalize_detected(row.raw_text, [pr.pred_name0, pr.pred_name1, pr.pred_name2, pr.pred_target]))
    detected_test['text'] = texts
    proposals = make_proposals(parser, detected_test, top_k=top_k)

    summaries, details = [], []
    for noise in (0.0, .15, .30):
        d = evaluate_governance(proposals, seed=seed, noise=noise)
        details.append(d)
        covered = d[d.topk_covered == 1]
        summaries.append({
            'seed': seed, 'noise': noise,
            'mention_all_roles_accuracy': float(detected.all_roles_correct.mean()),
            'mention_mean_role_accuracy': float(detected[['role0_correct','role1_correct','role2_correct','target_correct']].to_numpy().mean()),
            'semantic_top1_accuracy': float(proposals.top1_correct.mean()),
            'semantic_topk_coverage': float(proposals.topk_contains_true.mean()),
            'governed_accuracy_all': float(d.adaptive_correct.mean()),
            'governed_accuracy_covered': float(covered.adaptive_correct.mean()) if len(covered) else np.nan,
        })
    return pd.DataFrame(summaries), pd.concat(details, ignore_index=True), detected, proposals


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=4)
    ap.add_argument('--top-k', type=int, default=8)
    ap.add_argument('--mention-epochs', type=int, default=16)
    ap.add_argument('--parser-epochs', type=int, default=26)
    args = ap.parse_args(argv)
    ss, dd, mm, pp = [], [], [], []
    for seed in range(args.seeds):
        print('seed', seed)
        s,d,m,p = run_seed(seed, mention_epochs=args.mention_epochs, parser_epochs=args.parser_epochs, top_k=args.top_k)
        ss.append(s); dd.append(d); m['seed']=seed; mm.append(m); p['seed']=seed; pp.append(p)
        print(s.to_string(index=False))
    summary=pd.concat(ss,ignore_index=True); details=pd.concat(dd,ignore_index=True)
    mentions=pd.concat(mm,ignore_index=True); proposals=pd.concat(pp,ignore_index=True)
    tag=f'{args.seeds}seed'
    summary.to_csv(OUT/f'{tag}_summary.csv',index=False)
    details.to_csv(OUT/f'{tag}_details.csv',index=False)
    mentions.to_csv(OUT/f'{tag}_mentions.csv',index=False)
    proposals.to_csv(OUT/f'{tag}_proposals.csv',index=False)


if __name__ == '__main__':
    main()
