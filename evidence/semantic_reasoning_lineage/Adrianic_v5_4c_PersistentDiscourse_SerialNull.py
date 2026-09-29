from __future__ import annotations

import argparse
import json
import math
import random
import re
import itertools
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from scipy.optimize import minimize_scalar
from scipy.stats import wilcoxon

# =============================================================================
# Adrianic v5.4c — Persistent-Discourse + Serial-Null Semantic Coupling
#
# Purpose
# -------
# 1) Restore the coupled benchmark's observed per-edge constraints: every edge
#    has a fresh referent permutation, family permutation, and direction XOR.
# 2) Persist discourse context within each chain: same four names, same scenario,
#    same context sentence; vary only referring expression and relation template.
# 3) Separate three emission controls: accuracy only; accuracy + sharpness;
#    accuracy + sharpness + empirical confusion identity. Test controls are
#    marginal-accuracy locked to the semantic arm on the evaluated corpus.
# 4) Score serial error dependence against an empirical independent-error null
#    on the exact same latent chains/edges. Direction edge-coherence is omitted
#    because for binary direction it is algebraically pinned by the transition.
# 5) Keep candidate ranking diagnostic with a shuffled-edge pressure control.
# 6) Export clauses, persistent discourse IDs, and actual edge constraints.
#
# Reproducibility: all RNGs are seed-derived, every run writes config + per-seed
# summaries + position-level data + clause/edge exports.
# =============================================================================

RELATIONS = ("contains", "supports", "precedes", "maps")
DIRECTIONS = ("fwd", "rev")
N_REF = 3
N_FAM = len(RELATIONS)
N_DIR = len(DIRECTIONS)
N_STATES = N_REF * N_FAM * N_DIR

SCENARIOS = {
    "carry": {
        "train_context": ["{a} carried {b} while {c} watched.", "While {c} watched, {a} carried {b}."],
        "test_context": ["{b} was carried by {a} as {c} watched.", "{c} observed {a} carrying {b}."],
        "train_ref": {0: ["the carrier", "the one carrying"], 1: ["the carried one", "the one being carried"], 2: ["the watcher", "the one watching"]},
        "test_ref": {0: ["the person doing the carrying", "the carrier in that scene"], 1: ["the person in transit", "the one transported"], 2: ["the observer", "the witness to the carrying"]},
    },
    "handoff": {
        "train_context": ["{a} handed {b} to {c}.", "{a} passed {b} over to {c}."],
        "test_context": ["{c} received {b} from {a}.", "From {a}, {c} was given {b}."],
        "train_ref": {0: ["the giver", "the one handing it over"], 1: ["the transferred one", "the one being handed over"], 2: ["the receiver", "the one receiving it"]},
        "test_ref": {0: ["the source of the handoff", "the person who gave it"], 1: ["the transferred participant", "the handoff target object"], 2: ["the recipient", "the person who got it"]},
    },
    "follow": {
        "train_context": ["{a} followed {b} while {c} observed.", "With {c} observing, {a} followed {b}."],
        "test_context": ["{b} was followed by {a} as {c} looked on.", "{c} saw {a} trailing {b}."],
        "train_ref": {0: ["the follower", "the one following"], 1: ["the one being followed", "the leader"], 2: ["the observer", "the one observing"]},
        "test_ref": {0: ["the person trailing behind", "the pursuer"], 1: ["the person out front", "the one ahead"], 2: ["the witness", "the person looking on"]},
    },
    "escort": {
        "train_context": ["{a} escorted {b} while {c} waited.", "While {c} waited, {a} escorted {b}."],
        "test_context": ["{b} was escorted by {a} as {c} waited.", "{c} waited while {a} guided {b}."],
        "train_ref": {0: ["the escort", "the guide"], 1: ["the escorted one", "the one being guided"], 2: ["the waiter", "the one waiting"]},
        "test_ref": {0: ["the person doing the guiding", "the guide in that event"], 1: ["the person under escort", "the guided person"], 2: ["the person who stayed behind", "the waiting observer"]},
    },
}

REL_TRAIN = {
    ("contains", "fwd"): ["{ref} contains {d}.", "{ref} has {d} inside."],
    ("contains", "rev"): ["{ref} is inside {d}.", "{ref} is contained by {d}."],
    ("supports", "fwd"): ["{ref} supports {d}.", "{ref} holds up {d}."],
    ("supports", "rev"): ["{ref} is supported by {d}.", "{ref} rests on {d}."],
    ("precedes", "fwd"): ["{ref} precedes {d}.", "{ref} comes before {d}."],
    ("precedes", "rev"): ["{ref} follows {d}.", "{ref} comes after {d}."],
    ("maps", "fwd"): ["{ref} maps to {d}.", "{ref} points to {d}."],
    ("maps", "rev"): ["{ref} is mapped from {d}.", "{ref} is the target of {d}."],
}
REL_TEST = {
    ("contains", "fwd"): ["Inside {ref} is {d}.", "{d} remains within {ref}."],
    ("contains", "rev"): ["Inside {d} is {ref}.", "{d} keeps {ref} within."],
    ("supports", "fwd"): ["Support for {d} comes from {ref}.", "{d} is held up by {ref}."],
    ("supports", "rev"): ["Support for {ref} comes from {d}.", "{d} holds up {ref}."],
    ("precedes", "fwd"): ["Before {d} comes {ref}.", "{d} trails behind {ref}."],
    ("precedes", "rev"): ["After {d} comes {ref}.", "{ref} trails behind {d}."],
    ("maps", "fwd"): ["To {d}, {ref} points.", "{d} is the target of {ref}."],
    ("maps", "rev"): ["To {ref}, {d} points.", "{ref} is the target of {d}."],
}

SYL1 = ("na", "ta", "ve", "ri", "lo", "ke", "mi", "sa", "do", "fi", "ga", "po")
SYL2 = ("ra", "ven", "ko", "lin", "ma", "tor", "shi", "del", "rin", "ka", "mo", "se")
TOKEN_RE = re.compile(r"<n\d>|[a-z]+|[.,]")


def state_id(ref: int, fam: int, direc: int) -> int:
    return (int(ref) * N_FAM + int(fam)) * N_DIR + int(direc)


def decode_state(s: int) -> Tuple[int, int, int]:
    s = int(s)
    direc = s % N_DIR
    x = s // N_DIR
    fam = x % N_FAM
    ref = x // N_FAM
    return ref, fam, direc


STATE_FACTORS = np.array([decode_state(s) for s in range(N_STATES)], dtype=int)


def unique_names(rng: random.Random, n: int = 4) -> List[str]:
    out = []
    while len(out) < n:
        x = (rng.choice(SYL1) + rng.choice(SYL2)).capitalize()
        if x not in out:
            out.append(x)
    return out


def normalize_names(text: str, names: List[str]) -> str:
    out = text.lower()
    for idx, name in sorted(enumerate(names), key=lambda kv: len(kv[1]), reverse=True):
        out = re.sub(rf"\b{re.escape(name.lower())}\b", f"<n{idx}>", out)
    return out


def sample_discourse_context(rng: random.Random, split: str = "test") -> Dict:
    """Sample the chain-level context that persists across every clause."""
    names = unique_names(rng, 4)
    scenario_key = rng.choice(list(SCENARIOS.keys()))
    scenario = SCENARIOS[scenario_key]
    context_key = "train_context" if split == "train" else "test_context"
    a, b, c, _ = names
    context_template = rng.choice(scenario[context_key])
    context = context_template.format(a=a, b=b, c=c)
    return {
        "names": names,
        "scenario_key": scenario_key,
        "context": context,
    }


def render_clause(ref: int, fam: int, direc: int, rng: random.Random, split: str = "test",
                  discourse: Dict | None = None) -> Dict:
    # Independent rendering remains available for training/vocab construction.
    if discourse is None:
        discourse = sample_discourse_context(rng, split=split)
    names = list(discourse["names"])
    a, b, c, d = names
    scenario_key = str(discourse["scenario_key"])
    scenario = SCENARIOS[scenario_key]
    ref_key = "train_ref" if split == "train" else "test_ref"
    rel_table = REL_TRAIN if split == "train" else REL_TEST
    context = str(discourse["context"])
    # Only these two linguistic choices vary within a chain.
    ref_phrase = rng.choice(scenario[ref_key][int(ref)])
    relation_template = rng.choice(rel_table[(RELATIONS[int(fam)], DIRECTIONS[int(direc)])])
    target = relation_template.format(ref=ref_phrase, d=d)
    raw = context + " " + target
    return {
        "raw_text": raw,
        "text": normalize_names(raw, names),
        "ref": int(ref),
        "fam": int(fam),
        "dir": int(direc),
        "state_id": state_id(ref, fam, direc),
        "scenario": scenario_key,
        "context_text": context,
        "entity_0": names[0],
        "entity_1": names[1],
        "entity_2": names[2],
        "entity_3": names[3],
    }


def build_vocab() -> Tuple[Dict[str, int], List[str]]:
    toks = {"<pad>", "<unk>", "<cls>"}
    rng = random.Random(123)
    for split in ("train", "test"):
        for r in range(N_REF):
            for f in range(N_FAM):
                for d in range(N_DIR):
                    for _ in range(6):
                        row = render_clause(r, f, d, rng, split=split)
                        toks.update(TOKEN_RE.findall(row["text"].lower()))
    for i in range(4):
        toks.add(f"<n{i}>")
    itos = sorted(toks)
    return {t: i for i, t in enumerate(itos)}, itos


STOI, ITOS = build_vocab()
PAD = STOI["<pad>"]
UNK = STOI["<unk>"]
CLS = STOI["<cls>"]


def encode(text: str, max_len: int = 48) -> Tuple[List[int], List[int]]:
    toks = ["<cls>"] + TOKEN_RE.findall(text.lower())
    ids = [STOI.get(t, UNK) for t in toks[:max_len]]
    mask = [1] * len(ids)
    while len(ids) < max_len:
        ids.append(PAD); mask.append(0)
    return ids, mask


class FactorTransformer(nn.Module):
    def __init__(self, d_model: int = 48, nhead: int = 4, layers: int = 1, ff: int = 96, max_len: int = 48):
        super().__init__()
        self.emb = nn.Embedding(len(ITOS), d_model, padding_idx=PAD)
        self.pos = nn.Embedding(max_len, d_model)
        layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=ff, dropout=0.10, batch_first=True, activation="gelu")
        self.enc = nn.TransformerEncoder(layer, num_layers=layers)
        self.ref_out = nn.Linear(d_model, N_REF)
        self.fam_out = nn.Linear(d_model, N_FAM)
        self.dir_out = nn.Linear(d_model, N_DIR)

    def forward(self, ids, mask):
        b, t = ids.shape
        pos = torch.arange(t, device=ids.device)[None, :].expand(b, t)
        z = self.enc(self.emb(ids) + self.pos(pos), src_key_padding_mask=(mask == 0))
        h = z[:, 0, :]
        return self.ref_out(h), self.fam_out(h), self.dir_out(h)


@dataclass
class Config:
    seeds: int = 8
    chains_per_seed: int = 8
    chain_len: int = 80
    train_repeats_per_state: int = 14
    transformer_epochs: int = 8
    label_noise: float = 0.04
    semantic_backend: str = "tiny"
    pretrained_model: str = "distilbert-base-uncased"
    pretrained_epochs: int = 4
    pretrained_batch_size: int = 16
    pretrained_lr: float = 2e-5
    # Coupled-benchmark edge reliability. Each edge has fresh permutations/XOR.
    edge_ref_reliability: float = 0.78
    edge_fam_reliability: float = 0.75
    edge_dir_reliability: float = 0.78
    max_k: int = 12
    min_k: int = 2
    null_simulations: int = 500
    output_dir: str = "/mnt/data/adrianic_v54c_persistent_discourse_results"


def _factor_transition(n: int, perm: np.ndarray, reliability: float) -> np.ndarray:
    if not (0.0 < reliability < 1.0):
        raise ValueError("edge reliability must lie in (0,1)")
    out = np.full((n, n), (1.0 - reliability) / (n - 1), float)
    for prev in range(n):
        out[prev, int(perm[prev])] = reliability
    return out


def edge_log_matrix(ref_perm, fam_perm, dir_xor: int, cfg: Config) -> np.ndarray:
    ref_perm = np.asarray(ref_perm, int)
    fam_perm = np.asarray(fam_perm, int)
    if sorted(ref_perm.tolist()) != list(range(N_REF)):
        raise ValueError("ref_perm is not a permutation")
    if sorted(fam_perm.tolist()) != list(range(N_FAM)):
        raise ValueError("fam_perm is not a permutation")
    if int(dir_xor) not in (0, 1):
        raise ValueError("dir_xor must be 0/1")
    Tr = _factor_transition(N_REF, ref_perm, cfg.edge_ref_reliability)
    Tf = _factor_transition(N_FAM, fam_perm, cfg.edge_fam_reliability)
    Td = np.full((N_DIR, N_DIR), 1.0 - cfg.edge_dir_reliability, float)
    for prev in range(N_DIR):
        Td[prev, prev ^ int(dir_xor)] = cfg.edge_dir_reliability
    r, f, d = STATE_FACTORS.T
    T = (Tr[r[:, None], r[None, :]] *
         Tf[f[:, None], f[None, :]] *
         Td[d[:, None], d[None, :]])
    assert np.allclose(T.sum(axis=1), 1.0)
    return np.log(T + 1e-300)


def sample_chain(rng: np.random.Generator, length: int, cfg: Config, chain_id: str):
    states = np.empty(length, dtype=int)
    states[0] = int(rng.integers(N_STATES))
    edge_logs, edge_meta = [], []
    for t in range(length - 1):
        ref_perm = rng.permutation(N_REF).astype(int)
        fam_perm = rng.permutation(N_FAM).astype(int)
        dir_xor = int(rng.integers(2))
        logT = edge_log_matrix(ref_perm, fam_perm, dir_xor, cfg)
        Trow = np.exp(logT[states[t]])
        states[t + 1] = int(rng.choice(N_STATES, p=Trow))
        edge_logs.append(logT)
        edge_meta.append({
            "chain_id": chain_id,
            "src_position": int(t),
            "dst_position": int(t + 1),
            "ref_perm": ref_perm.tolist(),
            "fam_perm": fam_perm.tolist(),
            "dir_xor": dir_xor,
        })
    return states, edge_logs, edge_meta


def make_chain_dataframe(seed: int, cfg: Config, split: str = "test", tag: str = "test"):
    nrng = np.random.default_rng(seed + 9000)
    rrng = random.Random(seed + 19000)
    rows, edge_rows = [], []
    edge_tables = {}
    for c in range(cfg.chains_per_seed):
        cid = f"{tag}_s{seed}_c{c}"
        chain, logs, meta = sample_chain(nrng, cfg.chain_len, cfg, cid)
        edge_tables[cid] = logs
        clause_ids = [f"{cid}_p{p}" for p in range(cfg.chain_len)]
        discourse = sample_discourse_context(rrng, split=split)
        for pos, s in enumerate(chain):
            r, f, d = decode_state(int(s))
            x = render_clause(r, f, d, rrng, split=split, discourse=discourse)
            x.update({"seed": seed, "chain_id": cid, "position": pos, "clause_id": clause_ids[pos],
                      "discourse_id": cid})
            rows.append(x)
        for e in meta:
            e = dict(e)
            e.update({
                "seed": seed,
                "src_clause_id": clause_ids[e["src_position"]],
                "dst_clause_id": clause_ids[e["dst_position"]],
                "edge_type": "observed_permutation_xor",
                "edge_ref_reliability": cfg.edge_ref_reliability,
                "edge_fam_reliability": cfg.edge_fam_reliability,
                "edge_dir_reliability": cfg.edge_dir_reliability,
                "ref_perm": json.dumps(e["ref_perm"]),
                "fam_perm": json.dumps(e["fam_perm"]),
            })
            edge_rows.append(e)
    df = pd.DataFrame(rows)
    # Persistent-discourse invariant: every chain keeps exactly one scenario,
    # context sentence, and four entity identities.
    for cid, g in df.groupby("chain_id"):
        for col in ("scenario","context_text","entity_0","entity_1","entity_2","entity_3"):
            if g[col].nunique(dropna=False) != 1:
                raise AssertionError(f"persistent discourse invariant failed for {cid} column {col}")
    return df, edge_tables, pd.DataFrame(edge_rows)


def shuffled_edge_tables(edge_tables: Dict[str, List[np.ndarray]], seed: int) -> Dict[str, List[np.ndarray]]:
    """Pressure-preserving null: same edge matrices, assigned to the wrong adjacencies."""
    rng = np.random.default_rng(seed + 47000)
    flat = [m for cid in edge_tables for m in edge_tables[cid]]
    order = rng.permutation(len(flat))
    shuffled = [flat[int(i)] for i in order]
    out, k = {}, 0
    for cid, mats in edge_tables.items():
        out[cid] = shuffled[k:k + len(mats)]
        k += len(mats)
    return out


def make_train_dataframe(seed: int, cfg: Config) -> pd.DataFrame:
    rrng = random.Random(seed + 29000)
    rows = []
    for s in range(N_STATES):
        r, f, d = decode_state(s)
        for _ in range(cfg.train_repeats_per_state):
            rows.append(render_clause(r, f, d, rrng, split="train"))
    rrng.shuffle(rows)
    return pd.DataFrame(rows)


def make_calibration_dataframe(seed: int, cfg: Config):
    # Independent chain-distributed calibration set: same held-out renderer, fresh edges/text.
    return make_chain_dataframe(seed + 700_000, cfg, split="test", tag="calib")


def tensorize(df: pd.DataFrame):
    ids, masks = zip(*(encode(x) for x in df.text.tolist()))
    return (
        torch.tensor(ids, dtype=torch.long),
        torch.tensor(masks, dtype=torch.long),
        torch.tensor(df.ref.to_numpy(), dtype=torch.long),
        torch.tensor(df.fam.to_numpy(), dtype=torch.long),
        torch.tensor(df.dir.to_numpy(), dtype=torch.long),
    )


def train_transformer(seed: int, train_df: pd.DataFrame, cfg: Config) -> FactorTransformer:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    model = FactorTransformer()
    opt = torch.optim.AdamW(model.parameters(), lr=0.0035, weight_decay=1e-4)
    ids, mask, yr, yf, yd = tensorize(train_df)
    n = len(train_df)
    for _ in range(cfg.transformer_epochs):
        order = torch.randperm(n)
        for start in range(0, n, 64):
            idx = order[start:start+64]
            rr, ff, dd = model(ids[idx], mask[idx])
            ar, af, ad = yr[idx].clone(), yf[idx].clone(), yd[idx].clone()
            if cfg.label_noise > 0:
                nm = torch.rand(len(idx)) < cfg.label_noise
                if int(nm.sum()):
                    ar[nm] = torch.randint(0, N_REF, (int(nm.sum()),))
                    af[nm] = torch.randint(0, N_FAM, (int(nm.sum()),))
                    ad[nm] = torch.randint(0, N_DIR, (int(nm.sum()),))
            loss = F.cross_entropy(rr, ar) + F.cross_entropy(ff, af) + F.cross_entropy(dd, ad)
            opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    return model


def transformer_logits(model: FactorTransformer, df: pd.DataFrame) -> Dict[str, np.ndarray]:
    ids, mask, *_ = tensorize(df)
    out = {"ref": [], "fam": [], "dir": []}
    model.eval()
    with torch.no_grad():
        for start in range(0, len(df), 128):
            rr, ff, dd = model(ids[start:start+128], mask[start:start+128])
            out["ref"].append(rr.numpy()); out["fam"].append(ff.numpy()); out["dir"].append(dd.numpy())
    return {k: np.concatenate(v, axis=0) for k, v in out.items()}



def require_transformers():
    try:
        from transformers import AutoTokenizer, AutoModel
        return AutoTokenizer, AutoModel
    except ImportError as e:
        raise RuntimeError(
            "Pretrained backend requires transformers. In Colab run: "
            "!pip -q install transformers sentencepiece"
        ) from e


class PretrainedFactorHeads(nn.Module):
    def __init__(self, model_name: str):
        super().__init__()
        _, AutoModel = require_transformers()
        self.encoder = AutoModel.from_pretrained(model_name)
        hidden = int(self.encoder.config.hidden_size)
        self.ref_out = nn.Linear(hidden, N_REF)
        self.fam_out = nn.Linear(hidden, N_FAM)
        self.dir_out = nn.Linear(hidden, N_DIR)

    def forward(self, **batch):
        out = self.encoder(**batch)
        h = out.last_hidden_state[:, 0, :]
        return self.ref_out(h), self.fam_out(h), self.dir_out(h)


def train_pretrained(seed: int, train_df: pd.DataFrame, cfg: Config):
    AutoTokenizer, _ = require_transformers()
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(cfg.pretrained_model)
    model = PretrainedFactorHeads(cfg.pretrained_model).to(device)
    enc = tokenizer(
        train_df.raw_text.tolist(), padding=True, truncation=True,
        max_length=96, return_tensors="pt"
    )
    yr = torch.tensor(train_df.ref.to_numpy(), dtype=torch.long)
    yf = torch.tensor(train_df.fam.to_numpy(), dtype=torch.long)
    yd = torch.tensor(train_df.dir.to_numpy(), dtype=torch.long)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.pretrained_lr, weight_decay=1e-4)
    n = len(train_df)
    for epoch in range(cfg.pretrained_epochs):
        order = torch.randperm(n)
        model.train(); running = 0.0
        for start in range(0, n, cfg.pretrained_batch_size):
            idx = order[start:start+cfg.pretrained_batch_size]
            batch = {k: v[idx].to(device) for k,v in enc.items()}
            rr, ff, dd = model(**batch)
            loss = (F.cross_entropy(rr, yr[idx].to(device)) +
                    F.cross_entropy(ff, yf[idx].to(device)) +
                    F.cross_entropy(dd, yd[idx].to(device)))
            opt.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
            running += float(loss.item()) * len(idx)
        print(f"    pretrained epoch {epoch+1}/{cfg.pretrained_epochs} loss={running/n:.4f}", flush=True)
    return tokenizer, model


def pretrained_logits(tokenizer, model: PretrainedFactorHeads, df: pd.DataFrame) -> Dict[str, np.ndarray]:
    device = next(model.parameters()).device
    enc = tokenizer(df.raw_text.tolist(), padding=True, truncation=True, max_length=96, return_tensors="pt")
    out = {"ref": [], "fam": [], "dir": []}
    model.eval()
    with torch.no_grad():
        for start in range(0, len(df), 64):
            sl = slice(start, min(len(df), start+64))
            batch = {k: v[sl].to(device) for k,v in enc.items()}
            rr, ff, dd = model(**batch)
            out["ref"].append(rr.cpu().numpy()); out["fam"].append(ff.cpu().numpy()); out["dir"].append(dd.cpu().numpy())
    return {k: np.concatenate(v, axis=0) for k,v in out.items()}


def acc_from_logits(logits: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(np.argmax(logits, axis=1) == y))


def tune_signal_to_accuracy(y: np.ndarray, noise: np.ndarray, target_acc: float) -> float:
    def acc(sig):
        z = noise.copy(); z[np.arange(len(y)), y] += sig
        return np.mean(np.argmax(z, axis=1) == y)
    lo, hi = 0.0, 12.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if acc(mid) < target_acc: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def empirical_confusion(logits: np.ndarray, y: np.ndarray, k: int) -> np.ndarray:
    pred = np.argmax(logits, axis=1)
    C = np.zeros((k, k), float)
    for true in range(k):
        idx = np.flatnonzero(y == true)
        if not len(idx):
            C[true] = 1.0 / k
            continue
        counts = np.bincount(pred[idx], minlength=k).astype(float)
        C[true] = counts / counts.sum()
    return C


def _tune_class_signal(noise: np.ndarray, true_class: int, target_acc: float) -> float:
    target_acc = float(np.clip(target_acc, 0.0, 1.0))
    # Allow negative signal so a control can match semantic per-class accuracy
    # below the uninformed Gaussian baseline. Accuracy is monotone in this shift.
    lo, hi = -12.0, 12.0
    for _ in range(60):
        mid = (lo + hi) / 2
        z = noise.copy(); z[:, true_class] += mid
        a = float(np.mean(np.argmax(z, axis=1) == true_class))
        if a < target_acc:
            lo = mid
        else:
            hi = mid
    # Finite samples make the objective stepwise; choose the closer endpoint.
    candidates = (lo, (lo+hi)/2, hi)
    best = None
    for sig in candidates:
        z = noise.copy(); z[:, true_class] += sig
        a = float(np.mean(np.argmax(z, axis=1) == true_class))
        key = (abs(a-target_acc), abs(sig))
        if best is None or key < best[0]: best = (key, sig)
    return float(best[1])


def make_accuracy_controls(seed: int, calib_df: pd.DataFrame, test_df: pd.DataFrame,
                           sem_calib: Dict[str, np.ndarray], sem_test: Dict[str, np.ndarray]):
    """Independent Gaussian controls. Calibration controls match calibration
    semantic accuracy; evaluated test controls are separately locked to the
    semantic arm's per-class marginal accuracy on the current test corpus.
    This uses semantic outcomes only to set one-site marginals, never row-level
    correctness or serial placement."""
    ys_cal = {"ref": calib_df.ref.to_numpy(int), "fam": calib_df.fam.to_numpy(int), "dir": calib_df.dir.to_numpy(int)}
    ys_test = {"ref": test_df.ref.to_numpy(int), "fam": test_df.fam.to_numpy(int), "dir": test_df.dir.to_numpy(int)}
    sizes = {"ref": N_REF, "fam": N_FAM, "dir": N_DIR}
    rng = np.random.default_rng(seed + 39000)
    cal_out, test_out, signals, confusions_cal, confusions_test = {}, {}, {}, {}, {}
    for h in ("ref", "fam", "dir"):
        K = sizes[h]
        Ccal = empirical_confusion(sem_calib[h], ys_cal[h], K)
        Ctest = empirical_confusion(sem_test[h], ys_test[h], K)
        confusions_cal[h] = Ccal; confusions_test[h] = Ctest
        ncal = rng.normal(size=(len(calib_df), K))
        ntest = rng.normal(size=(len(test_df), K))
        zcal = ncal.copy(); ztest = ntest.copy()
        sig_cal = np.zeros(K, float); sig_test = np.zeros(K, float)
        for cls in range(K):
            idx = np.flatnonzero(ys_cal[h] == cls)
            sigc = _tune_class_signal(ncal[idx], cls, Ccal[cls, cls]) if len(idx) else 0.0
            sig_cal[cls] = sigc
            zcal[idx, cls] += sigc
            idt = np.flatnonzero(ys_test[h] == cls)
            sigt = _tune_class_signal(ntest[idt], cls, Ctest[cls, cls]) if len(idt) else 0.0
            sig_test[cls] = sigt
            ztest[idt, cls] += sigt
        cal_out[h] = zcal; test_out[h] = ztest
        signals[h] = {"calibration": sig_cal, "test": sig_test}
        # Assert the evaluated control matches semantic per-class accuracy to
        # finite-sample resolution (ties in the signal search can differ by 1 row).
        for cls in range(K):
            idt = np.flatnonzero(ys_test[h] == cls)
            if len(idt):
                a_sem = np.mean(np.argmax(sem_test[h][idt], axis=1) == cls)
                a_syn = np.mean(np.argmax(ztest[idt], axis=1) == cls)
                if abs(a_sem - a_syn) > (1.01 / len(idt)):
                    raise AssertionError(f"{h} class {cls} marginal accuracy lock failed: {a_syn} vs {a_sem}")
    return cal_out, test_out, signals, confusions_cal, confusions_test


def impose_confusion_identity(logits: np.ndarray, y: np.ndarray, C: np.ndarray,
                              seed: int) -> np.ndarray:
    """Change only WHICH wrong class wins. Preserve correctness, true logit,
    true margin, centered strength, and the full row-wise multiset of logits."""
    rng = np.random.default_rng(seed)
    z = logits.copy()
    before_correct = np.argmax(z, axis=1) == y
    before_true = z[np.arange(len(y)), y].copy()
    before_sorted = np.sort(z, axis=1).copy()
    K = z.shape[1]
    for true in range(K):
        idx = np.flatnonzero((y == true) & (~before_correct))
        if not len(idx):
            continue
        probs = C[true].copy(); probs[true] = 0.0
        if probs.sum() <= 0:
            probs[:] = 1.0; probs[true] = 0.0
        probs /= probs.sum()
        raw = probs * len(idx)
        counts = np.floor(raw).astype(int)
        rem = len(idx) - int(counts.sum())
        frac_order = np.argsort(-(raw - counts))
        for j in frac_order:
            if rem <= 0: break
            if j == true: continue
            counts[j] += 1; rem -= 1
        targets = np.concatenate([np.full(counts[j], j, int) for j in range(K) if j != true])
        rng.shuffle(targets)
        if len(targets) != len(idx):
            raise AssertionError("confusion allocation size mismatch")
        for ii, target in zip(idx, targets):
            cur = int(np.argmax(z[ii]))
            target = int(target)
            if cur != target:
                z[ii, cur], z[ii, target] = z[ii, target], z[ii, cur]
    after_correct = np.argmax(z, axis=1) == y
    assert np.array_equal(before_correct, after_correct), "confusion remap changed row correctness"
    assert np.allclose(before_true, z[np.arange(len(y)), y]), "confusion remap changed true logits"
    assert np.allclose(before_sorted, np.sort(z, axis=1)), "confusion remap changed logit spectrum"
    return z


def log_softmax_np(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    return z - np.log(np.exp(z).sum(axis=1, keepdims=True) + 1e-300)


def centered_strength(z: np.ndarray) -> np.ndarray:
    c = z - z.mean(axis=1, keepdims=True)
    return np.linalg.norm(c, axis=1)


def true_margin(z: np.ndarray, y: np.ndarray) -> np.ndarray:
    zy = z[np.arange(len(y)), y]
    tmp = z.copy(); tmp[np.arange(len(y)), y] = -np.inf
    return zy - tmp.max(axis=1)


def fit_temperature(source_logits: np.ndarray, target_logits: np.ndarray, y: np.ndarray) -> float:
    src_correct = np.argmax(source_logits, axis=1) == y
    tgt_correct = np.argmax(target_logits, axis=1) == y
    qs = np.array([0.1, 0.25, 0.5, 0.75, 0.9])

    def features(z, mask):
        if mask.sum() < 8:
            mask = np.ones(len(z), dtype=bool)
        s = centered_strength(z[mask]); m = true_margin(z[mask], y[mask])
        return np.r_[np.quantile(s, qs), np.quantile(m, qs)]

    target_vec = np.r_[features(target_logits, tgt_correct), features(target_logits, ~tgt_correct)]
    scale = np.maximum(np.abs(target_vec), 0.25)

    def objective(logT):
        T = math.exp(logT)
        z = source_logits / T
        src_vec = np.r_[features(z, src_correct), features(z, ~src_correct)]
        return float(np.mean(((src_vec - target_vec) / scale) ** 2))

    res = minimize_scalar(objective, bounds=(math.log(0.25), math.log(8.0)), method="bounded")
    return float(math.exp(res.x))


def joint_log_emission(head_logits: Dict[str, np.ndarray]) -> np.ndarray:
    lr = log_softmax_np(head_logits["ref"])
    lf = log_softmax_np(head_logits["fam"])
    ld = log_softmax_np(head_logits["dir"])
    out = np.empty((len(lr), N_STATES), float)
    for s, (r, f, d) in enumerate(STATE_FACTORS):
        out[:, s] = lr[:, r] + lf[:, f] + ld[:, d]
    return out


def forward_backward(log_emission: np.ndarray, edge_tables: Dict[str, List[np.ndarray]], chain_ids: np.ndarray) -> np.ndarray:
    post = np.empty_like(log_emission)
    for cid in dict.fromkeys(chain_ids.tolist()):
        idx = np.flatnonzero(chain_ids == cid)
        E = log_emission[idx]
        edges = edge_tables[str(cid)]
        L = len(idx)
        if len(edges) != L - 1:
            raise AssertionError("edge count does not match chain length")
        a = np.empty_like(E); b = np.empty_like(E)
        a[0] = E[0] - math.log(N_STATES)
        for t in range(1, L):
            m = a[t-1][:, None] + edges[t-1]
            mx = m.max(axis=0)
            a[t] = E[t] + mx + np.log(np.exp(m - mx).sum(axis=0) + 1e-300)
        b[-1] = 0.0
        for t in range(L-2, -1, -1):
            m = edges[t] + E[t+1][None, :] + b[t+1][None, :]
            mx = m.max(axis=1)
            b[t] = mx + np.log(np.exp(m - mx[:, None]).sum(axis=1) + 1e-300)
        q = a + b
        q -= q.max(axis=1, keepdims=True)
        q -= np.log(np.exp(q).sum(axis=1, keepdims=True) + 1e-300)
        post[idx] = q
    return post


def one_pass_coupling_scores(log_emission: np.ndarray, edge_tables: Dict[str, List[np.ndarray]], chain_ids: np.ndarray) -> np.ndarray:
    # One local-neighbor sum-product pass. No candidate set enters the score.
    p = np.exp(log_emission - log_emission.max(axis=1, keepdims=True))
    p /= p.sum(axis=1, keepdims=True)
    scores = log_emission.copy()
    for cid in dict.fromkeys(chain_ids.tolist()):
        idx = np.flatnonzero(chain_ids == cid)
        edges = edge_tables[str(cid)]
        for j, ii in enumerate(idx):
            msg = np.zeros(N_STATES); count = 0
            if j > 0:
                T = np.exp(edges[j-1])
                msg += np.log(p[idx[j-1]] @ T + 1e-300); count += 1
            if j < len(idx)-1:
                T = np.exp(edges[j])
                msg += np.log(T @ p[idx[j+1]] + 1e-300); count += 1
            if count:
                scores[ii] += msg / count
    return scores


def entropy_soft_k(log_scores: np.ndarray, min_k: int, max_k: int) -> np.ndarray:
    z = log_scores - log_scores.max(axis=1, keepdims=True)
    p = np.exp(z); p /= p.sum(axis=1, keepdims=True)
    H = -(p * np.log(p + 1e-300)).sum(axis=1)
    k = np.ceil(np.exp(H)).astype(int)
    return np.clip(k, min_k, max_k)


def topk_mask(scores: np.ndarray, ks: np.ndarray) -> np.ndarray:
    mask = np.zeros_like(scores, dtype=bool)
    order = np.argsort(-scores, axis=1)
    for i, k in enumerate(ks): mask[i, order[i, :int(k)]] = True
    return mask


def masked_forward_backward(log_emission: np.ndarray, edge_tables: Dict[str, List[np.ndarray]], chain_ids: np.ndarray, mask: np.ndarray) -> np.ndarray:
    E = log_emission.copy(); E[~mask] = -1e12
    return forward_backward(E, edge_tables, chain_ids)


def factor_metrics(logits: Dict[str, np.ndarray], df: pd.DataFrame) -> Dict[str, float]:
    ys = {"ref": df.ref.to_numpy(int), "fam": df.fam.to_numpy(int), "dir": df.dir.to_numpy(int)}
    out = {}
    for k in ys:
        z = logits[k]; y = ys[k]
        out[f"{k}_acc"] = acc_from_logits(z, y)
        out[f"{k}_strength"] = float(centered_strength(z).mean())
        out[f"{k}_margin"] = float(true_margin(z, y).mean())
    return out


def exact_state_accuracy(log_scores: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(np.argmax(log_scores, axis=1) == y))


def candidate_diagnostic(localE, exact_post, rank_scores, shuffled_scores, df, edge_tables, cfg):
    y = df.state_id.to_numpy(int)
    chains = df.chain_id.to_numpy()
    ks = entropy_soft_k(localE, cfg.min_k, cfg.max_k)
    local_mask = topk_mask(localE, ks)
    coupling_mask = topk_mask(rank_scores, ks)
    shuffled_mask = topk_mask(shuffled_scores, ks)
    local_cov = local_mask[np.arange(len(y)), y]
    coupling_cov = coupling_mask[np.arange(len(y)), y]
    shuffled_cov = shuffled_mask[np.arange(len(y)), y]
    rescued = coupling_cov & (~local_cov)

    soft_post = masked_forward_backward(localE, edge_tables, chains, coupling_mask)
    cond = exact_post.copy(); cond[~coupling_mask] = -1e12

    def acc_on(scores, mask):
        return float(np.mean(np.argmax(scores[mask], axis=1) == y[mask])) if mask.any() else float('nan')

    return {
        "mean_k": float(ks.mean()),
        "local_coverage": float(local_cov.mean()),
        "coupling_coverage": float(coupling_cov.mean()),
        "shuffled_coverage": float(shuffled_cov.mean()),
        "coupling_minus_local_pp": float(100*(coupling_cov.mean()-local_cov.mean())),
        "coupling_minus_shuffled_pp": float(100*(coupling_cov.mean()-shuffled_cov.mean())),
        "rescued_n": int(rescued.sum()),
        "rescued_fraction": float(rescued.mean()),
        "rescued_local_argmax": acc_on(localE, rescued),
        "rescued_coupling_softwall": acc_on(soft_post, rescued),
        "rescued_structured_exact": acc_on(exact_post, rescued),
        "rescued_structured_exact_candidate_conditioned": acc_on(cond, rescued),
    }


def _prepare_serial_index(df: pd.DataFrame, edges_df: pd.DataFrame) -> Dict:
    row_by_clause = {cid: i for i, cid in enumerate(df.clause_id.tolist())}
    src = np.array([row_by_clause[x] for x in edges_df.src_clause_id.tolist()], dtype=int)
    dst = np.array([row_by_clause[x] for x in edges_df.dst_clause_id.tolist()], dtype=int)
    ref_perm = np.array([json.loads(x) for x in edges_df.ref_perm.tolist()], dtype=int)
    fam_perm = np.array([json.loads(x) for x in edges_df.fam_perm.tolist()], dtype=int)
    chain_names = list(dict.fromkeys(df.chain_id.tolist()))
    chain_code_map = {c:i for i,c in enumerate(chain_names)}
    chain_codes = np.array([chain_code_map[c] for c in df.chain_id.tolist()], dtype=int)
    chain_counts = np.bincount(chain_codes, minlength=len(chain_names)).astype(float)
    return {"src":src, "dst":dst, "ref_perm":ref_perm, "fam_perm":fam_perm,
            "chain_codes":chain_codes, "chain_counts":chain_counts, "n_chains":len(chain_names)}


def _serial_metrics_from_preds(preds: Dict[str, np.ndarray], df: pd.DataFrame, edges_df: pd.DataFrame,
                               prepared: Dict | None = None) -> Dict[str, float]:
    truths = {"ref": df.ref.to_numpy(int), "fam": df.fam.to_numpy(int), "dir": df.dir.to_numpy(int)}
    q = _prepare_serial_index(df, edges_df) if prepared is None else prepared
    src, dst = q["src"], q["dst"]
    out = {}
    for h in ("ref", "fam", "dir"):
        err = (preds[h] != truths[h]).astype(float)
        e0, e1 = err[src], err[dst]
        out[f"{h}_error_lag1_corr"] = float(np.corrcoef(e0, e1)[0,1]) if e0.std() > 0 and e1.std() > 0 else float("nan")
        sums = np.bincount(q["chain_codes"], weights=err, minlength=q["n_chains"])
        rates = sums / q["chain_counts"]
        out[f"{h}_chain_error_rate_var"] = float(np.var(rates, ddof=1)) if len(rates) > 1 else float("nan")
        if h in ("ref", "fam"):
            both = (e0 > 0.5) & (e1 > 0.5)
            if np.any(both):
                perm = q["ref_perm"] if h == "ref" else q["fam_perm"]
                expected = perm[np.arange(len(src)), preds[h][src]]
                coherent = preds[h][dst] == expected
                out[f"{h}_both_wrong_edge_coherence"] = float(np.mean(coherent[both]))
                out[f"{h}_both_wrong_edges"] = int(np.sum(both))
            else:
                out[f"{h}_both_wrong_edge_coherence"] = float("nan")
                out[f"{h}_both_wrong_edges"] = 0
    return out


def _sample_independent_preds(y: np.ndarray, C: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    p = np.empty(len(y), dtype=int)
    for cls in range(C.shape[0]):
        idx = np.flatnonzero(y == cls)
        if len(idx):
            probs = np.asarray(C[cls], float)
            probs = probs / probs.sum()
            p[idx] = rng.choice(C.shape[1], size=len(idx), p=probs)
    return p


def serial_error_against_independent_null(logits: Dict[str, np.ndarray], df: pd.DataFrame, edges_df: pd.DataFrame,
                                          seed: int, simulations: int = 500) -> Dict[str, float]:
    """Compare observed serial diagnostics with independent errors sampled from
    the arm's own empirical one-site confusion matrix on the exact same chains."""
    ys = {"ref": df.ref.to_numpy(int), "fam": df.fam.to_numpy(int), "dir": df.dir.to_numpy(int)}
    sizes = {"ref": N_REF, "fam": N_FAM, "dir": N_DIR}
    obs_preds = {h: np.argmax(logits[h], axis=1) for h in ("ref","fam","dir")}
    prepared = _prepare_serial_index(df, edges_df)
    observed = _serial_metrics_from_preds(obs_preds, df, edges_df, prepared=prepared)
    Cs = {h: empirical_confusion(logits[h], ys[h], sizes[h]) for h in sizes}
    metric_names = []
    for h in ("ref","fam","dir"):
        metric_names += [f"{h}_error_lag1_corr", f"{h}_chain_error_rate_var"]
        if h in ("ref","fam"):
            metric_names.append(f"{h}_both_wrong_edge_coherence")
    sims = {k: [] for k in metric_names}
    rng = np.random.default_rng(seed)
    for _ in range(int(simulations)):
        pp = {h: _sample_independent_preds(ys[h], Cs[h], rng) for h in ("ref","fam","dir")}
        m = _serial_metrics_from_preds(pp, df, edges_df, prepared=prepared)
        for k in metric_names:
            if np.isfinite(m[k]): sims[k].append(float(m[k]))
    out = dict(observed)
    for k in metric_names:
        arr = np.asarray(sims[k], float)
        mu = float(arr.mean()) if len(arr) else float("nan")
        sd = float(arr.std(ddof=1)) if len(arr) > 1 else float("nan")
        obs = float(observed[k])
        z = (obs-mu)/sd if np.isfinite(obs) and np.isfinite(sd) and sd > 0 else float("nan")
        p = ((1 + np.sum(np.abs(arr-mu) >= abs(obs-mu))) / (len(arr)+1)) if len(arr) and np.isfinite(obs) else float("nan")
        out[f"{k}_null_mean"] = mu
        out[f"{k}_null_sd"] = sd
        out[f"{k}_excess"] = obs - mu if np.isfinite(obs) and np.isfinite(mu) else float("nan")
        out[f"{k}_z"] = float(z)
        out[f"{k}_p_two_sided"] = float(p)
    out["direction_edge_coherence_omitted"] = 1.0
    return out


def self_test():
    cfg = Config(seeds=1, chains_per_seed=1, chain_len=3)
    ident_r = np.arange(N_REF); ident_f = np.arange(N_FAM)
    logT = edge_log_matrix(ident_r, ident_f, 0, cfg)
    edge_tables = {"x": [logT, logT]}
    E = np.full((3, N_STATES), -math.log(N_STATES))
    target = state_id(1, 2, 0)
    E[0, target] += 5.0; E[2, target] += 5.0
    chains = np.array(["x", "x", "x"])
    base_margin = E[1, target] - np.max(np.delete(E[1], target))
    scores = one_pass_coupling_scores(E, edge_tables, chains)
    after_margin = scores[1, target] - np.max(np.delete(scores[1], target))
    assert after_margin > base_margin, "edge coupling failed directional self-test"
    assert int(np.argmax(scores[1])) == target, "edge coupling selected wrong state"
    # Confusion remap must be evidence-geometry preserving.
    z = np.array([[3., 2., 0.], [0., 3., 2.], [2., 0., 3.], [2., 3., 0.]])
    y = np.array([0, 0, 2, 0])
    C = np.array([[.5, .1, .4], [.2, .6, .2], [.3, .2, .5]])
    zz = impose_confusion_identity(z, y, C, 123)
    assert np.array_equal(np.argmax(z,1)==y, np.argmax(zz,1)==y)
    ks = np.array([5, 7, 11]); m = topk_mask(scores, ks)
    assert np.all(m.sum(axis=1) == ks), "candidate capacity invariant failed"
    print("SELF TEST: PASS")


def paired_wilcoxon(x: List[float]) -> Dict:
    x = np.asarray(x, float)
    nonzero = x[np.abs(x) > 1e-12]
    if len(nonzero) == 0:
        p = 1.0
    else:
        try: p = float(wilcoxon(x, alternative="two-sided", zero_method="wilcox").pvalue)
        except Exception: p = float('nan')
    return {"mean": float(x.mean()), "positive": int((x > 0).sum()), "n": int(len(x)), "p": p}


def run_seed(seed: int, cfg: Config, outdir: Path):
    train_df = make_train_dataframe(seed, cfg)
    calib_df, calib_edges, calib_edges_df = make_calibration_dataframe(seed, cfg)
    test_df, edge_tables, edges_df = make_chain_dataframe(seed, cfg, split="test", tag="test")

    if cfg.semantic_backend == "pretrained":
        tokenizer, model = train_pretrained(seed, train_df, cfg)
        sem_cal = pretrained_logits(tokenizer, model, calib_df)
        sem = pretrained_logits(tokenizer, model, test_df)
    elif cfg.semantic_backend == "tiny":
        model = train_transformer(seed, train_df, cfg)
        sem_cal = transformer_logits(model, calib_df)
        sem = transformer_logits(model, test_df)
    else:
        raise ValueError(f"unknown semantic_backend={cfg.semantic_backend}")

    syn_cal, syn_acc, signals, confusions_cal, confusions_test = make_accuracy_controls(seed, calib_df, test_df, sem_cal, sem)
    ys_cal = {"ref": calib_df.ref.to_numpy(int), "fam": calib_df.fam.to_numpy(int), "dir": calib_df.dir.to_numpy(int)}
    ys_test = {"ref": test_df.ref.to_numpy(int), "fam": test_df.fam.to_numpy(int), "dir": test_df.dir.to_numpy(int)}

    temps, syn_sharp, syn_conf = {}, {}, {}
    for h in ("ref", "fam", "dir"):
        # Fit on independent calibration data, then freeze for test.
        T = fit_temperature(syn_cal[h], sem_cal[h], ys_cal[h])
        temps[h] = T
        syn_sharp[h] = syn_acc[h] / T
        syn_conf[h] = impose_confusion_identity(
            syn_sharp[h], ys_test[h], confusions_test[h], seed + {"ref":51000,"fam":52000,"dir":53000}[h]
        )

    chains = test_df.chain_id.to_numpy()
    ystate = test_df.state_id.to_numpy(int)
    shuffled_edges = shuffled_edge_tables(edge_tables, seed)

    arms = (
        ("synthetic_accuracy_only", syn_acc),
        ("synthetic_sharpness_matched", syn_sharp),
        ("synthetic_confusion_matched", syn_conf),
        ("semantic_raw", sem),
    )
    arm_data = {}
    row = {"seed": seed}
    for h in ("ref", "fam", "dir"):
        row[f"temperature_{h}"] = temps[h]
        for split_name in ("calibration","test"):
            for cls, sig in enumerate(signals[h][split_name]): row[f"signal_{split_name}_{h}_{cls}"] = float(sig)
        for cname, C in (("calib", confusions_cal[h]), ("test", confusions_test[h])):
            for i in range(C.shape[0]):
                for j in range(C.shape[1]): row[f"{cname}_confusion_{h}_{i}_{j}"] = float(C[i,j])

    for arm, logits in arms:
        E = joint_log_emission(logits)
        P = forward_backward(E, edge_tables, chains)
        Ps = forward_backward(E, shuffled_edges, chains)
        local = exact_state_accuracy(E, ystate); coupled = exact_state_accuracy(P, ystate); shuf = exact_state_accuracy(Ps, ystate)
        row[f"{arm}_local_acc"] = local
        row[f"{arm}_coupled_acc"] = coupled
        row[f"{arm}_shuffled_acc"] = shuf
        row[f"{arm}_delta"] = coupled - local
        row[f"{arm}_coupling_minus_shuffled"] = coupled - shuf
        for k,v in factor_metrics(logits, test_df).items(): row[f"{arm}_{k}"] = v
        serial = serial_error_against_independent_null(
            logits, test_df, edges_df, seed + {
                "synthetic_accuracy_only":61000, "synthetic_sharpness_matched":62000,
                "synthetic_confusion_matched":63000, "semantic_raw":64000
            }[arm], simulations=cfg.null_simulations
        )
        for k,v in serial.items(): row[f"{arm}_{k}"] = v
        arm_data[arm] = (E, P)

    # Candidate diagnostic on the accuracy-only Gaussian arm for continuity.
    E, P = arm_data["synthetic_accuracy_only"]
    rank_scores = one_pass_coupling_scores(E, edge_tables, chains)
    shuf_scores = one_pass_coupling_scores(E, shuffled_edges, chains)
    diag = candidate_diagnostic(E, P, rank_scores, shuf_scores, test_df, edge_tables, cfg)
    row.update({f"diag_{k}": v for k,v in diag.items()})

    pos = test_df[["seed","chain_id","discourse_id","position","clause_id","state_id","ref","fam","dir","scenario","context_text","entity_0","entity_1","entity_2","entity_3","raw_text","text"]].copy()
    for arm, (E,P) in arm_data.items():
        pos[f"{arm}_local_pred"] = np.argmax(E, axis=1)
        pos[f"{arm}_coupled_pred"] = np.argmax(P, axis=1)
        pos[f"{arm}_local_correct"] = (pos[f"{arm}_local_pred"].to_numpy() == ystate).astype(int)
        pos[f"{arm}_coupled_correct"] = (pos[f"{arm}_coupled_pred"].to_numpy() == ystate).astype(int)
    pos.to_csv(outdir / f"seed{seed}_positions.csv", index=False)
    test_df[["seed","chain_id","discourse_id","position","clause_id","scenario","context_text","entity_0","entity_1","entity_2","entity_3","raw_text","text","ref","fam","dir","state_id"]].to_csv(outdir / f"seed{seed}_clauses.csv", index=False)
    edges_df.to_csv(outdir / f"seed{seed}_edges.csv", index=False)
    calib_edges_df.to_csv(outdir / f"seed{seed}_calibration_edges.csv", index=False)
    with open(outdir / f"seed{seed}_confusions.json", "w") as f:
        json.dump({"calibration": {h: confusions_cal[h].tolist() for h in confusions_cal},
                   "test": {h: confusions_test[h].tolist() for h in confusions_test}}, f, indent=2)
    return row, test_df, edges_df


def make_report(summary: pd.DataFrame, cfg: Config) -> str:
    def weighted_metric(value_col: str) -> float:
        vals = summary[value_col].to_numpy(float); w = summary["diag_rescued_n"].to_numpy(float)
        ok = np.isfinite(vals) & (w > 0)
        return float(np.average(vals[ok], weights=w[ok])) if ok.any() else float("nan")

    lines = [
        "# Adrianic v5.4c Persistent-Discourse + Serial-Null Report", "",
        f"Semantic backend: {cfg.semantic_backend}",
        f"Model: {cfg.pretrained_model if cfg.semantic_backend == 'pretrained' else 'v5.1 tiny transformer control'}",
        f"Seeds: {cfg.seeds}", f"Clauses/seed: {cfg.chains_per_seed*cfg.chain_len}",
        f"Total clauses: {cfg.seeds*cfg.chains_per_seed*cfg.chain_len}",
        f"Edge reliability ref/fam/dir: {cfg.edge_ref_reliability:.3f}/{cfg.edge_fam_reliability:.3f}/{cfg.edge_dir_reliability:.3f}",
        "Every adjacency uses a freshly sampled ref permutation, fam permutation, and dir XOR; inference sees the exact edge constraint.",
        "Within each chain, the same four entity names, scenario, and context sentence persist; only referring expression and relation template vary.",
        f"Independent-error null simulations per arm/seed: {cfg.null_simulations}", ""
    ]
    arms = ("synthetic_accuracy_only","synthetic_sharpness_matched","synthetic_confusion_matched","semantic_raw")
    for arm in arms:
        loc=summary[f"{arm}_local_acc"].mean(); coup=summary[f"{arm}_coupled_acc"].mean(); sh=summary[f"{arm}_shuffled_acc"].mean()
        stat=paired_wilcoxon(summary[f"{arm}_delta"].tolist()); nullstat=paired_wilcoxon(summary[f"{arm}_coupling_minus_shuffled"].tolist())
        lines += [f"## {arm}", f"local/coupled/shuffled: {loc:.4f}/{coup:.4f}/{sh:.4f}",
                  f"coupled-local: {100*(coup-loc):+.3f} pp; {stat['positive']}/{stat['n']} positive, p={stat['p']:.4g}",
                  f"coupled-shuffled-edge: {100*(coup-sh):+.3f} pp; {nullstat['positive']}/{nullstat['n']} positive, p={nullstat['p']:.4g}", ""]

    lines += ["## Emission-control audit"]
    for h in ("ref","fam","dir"):
        a=summary[f"synthetic_accuracy_only_{h}_acc"].mean(); b=summary[f"synthetic_sharpness_matched_{h}_acc"].mean(); c=summary[f"synthetic_confusion_matched_{h}_acc"].mean(); s=summary[f"semantic_raw_{h}_acc"].mean()
        sa=summary[f"synthetic_accuracy_only_{h}_strength"].mean(); sb=summary[f"synthetic_sharpness_matched_{h}_strength"].mean(); sc=summary[f"synthetic_confusion_matched_{h}_strength"].mean(); ss=summary[f"semantic_raw_{h}_strength"].mean()
        lines.append(f"{h}: acc A/S/C/semantic={a:.3f}/{b:.3f}/{c:.3f}/{s:.3f}; strength={sa:.3f}/{sb:.3f}/{sc:.3f}/{ss:.3f}; calibration T={summary[f'temperature_{h}'].mean():.3f}")
    lines += ["", "The evaluated Gaussian controls are marginal-accuracy locked to semantic per-class accuracy on the current persistent-context corpus. Confusion matching changes only wrong-class identity: row correctness, true logit, true margin, centered strength, and sorted logit spectrum are invariant by assertion.", ""]

    lines += ["## Serial error dependence vs empirical independent-error null"]
    for arm in ("synthetic_sharpness_matched","synthetic_confusion_matched","semantic_raw"):
        lines.append(f"### {arm}")
        for h in ("ref","fam","dir"):
            lag=summary[f"{arm}_{h}_error_lag1_corr"].mean(); lnull=summary[f"{arm}_{h}_error_lag1_corr_null_mean"].mean(); lex=summary[f"{arm}_{h}_error_lag1_corr_excess"].mean(); lz=summary[f"{arm}_{h}_error_lag1_corr_z"].mean()
            vr=summary[f"{arm}_{h}_chain_error_rate_var"].mean(); vnull=summary[f"{arm}_{h}_chain_error_rate_var_null_mean"].mean(); vex=summary[f"{arm}_{h}_chain_error_rate_var_excess"].mean()
            lines.append(f"{h}: lag1 obs/null/excess={lag:+.4f}/{lnull:+.4f}/{lex:+.4f} (mean z={lz:+.2f}); chain-error variance obs/null/excess={vr:.5f}/{vnull:.5f}/{vex:+.5f}")
            if h in ("ref","fam"):
                coh=summary[f"{arm}_{h}_both_wrong_edge_coherence"].mean(); cnull=summary[f"{arm}_{h}_both_wrong_edge_coherence_null_mean"].mean(); cex=summary[f"{arm}_{h}_both_wrong_edge_coherence_excess"].mean(); cz=summary[f"{arm}_{h}_both_wrong_edge_coherence_z"].mean(); n=summary[f"{arm}_{h}_both_wrong_edges"].sum()
                lines.append(f"  both-wrong edge coherence obs/null/excess={coh:.4f}/{cnull:.4f}/{cex:+.4f} (mean z={cz:+.2f}, observed edges={int(n)})")
        lines.append("direction edge-coherence intentionally omitted: binary XOR makes it non-diagnostic when conditioning on both wrong.")
    lines.append("")

    cov_local=summary.diag_local_coverage.mean(); cov_c=summary.diag_coupling_coverage.mean(); cov_s=summary.diag_shuffled_coverage.mean()
    stat_l=paired_wilcoxon(summary.diag_coupling_minus_local_pp.tolist()); stat_s=paired_wilcoxon(summary.diag_coupling_minus_shuffled_pp.tolist())
    lines += ["## Candidate diagnostic", f"mean candidate budget: {summary.diag_mean_k.mean():.3f}",
              f"coverage local/coupling/shuffled-edge: {cov_local:.4f}/{cov_c:.4f}/{cov_s:.4f}",
              f"coupling-local: {summary.diag_coupling_minus_local_pp.mean():+.3f} pp; {stat_l['positive']}/{stat_l['n']} positive, p={stat_l['p']:.4g}",
              f"coupling-shuffled: {summary.diag_coupling_minus_shuffled_pp.mean():+.3f} pp; {stat_s['positive']}/{stat_s['n']} positive, p={stat_s['p']:.4g}",
              f"rescued clauses: {int(summary.diag_rescued_n.sum())}",
              f"rescued local argmax: {weighted_metric('diag_rescued_local_argmax'):.4f}",
              f"rescued coupling softwall: {weighted_metric('diag_rescued_coupling_softwall'):.4f}",
              f"rescued structured exact: {weighted_metric('diag_rescued_structured_exact'):.4f}",
              f"rescued exact candidate-conditioned: {weighted_metric('diag_rescued_structured_exact_candidate_conditioned'):.4f}", ""]
    lines += ["## Interpretation ladder",
              "A → S isolates sharpness after accuracy calibration.",
              "S → C isolates marginal confusion identity while preserving every row's evidence geometry.",
              "C → semantic is the residual after matching one-site marginals; persistent discourse gives that residual a legitimate serial channel.",
              "Raw serial statistics are never compared to naive chance. They are compared with independent predictions sampled from the arm's own one-site confusion matrix on the exact same chains.",
              "A positive null-adjusted lag/chain-variance signal indicates dependence beyond one-site confusion and is the primary semantic diagnostic.",
              "Ref/fam edge-coherence is retained only as a negative-control/leakage check: persistent discourse does not reveal the fresh random edge permutation to the clause model. Direction edge-coherence is omitted entirely."]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=8)
    p.add_argument("--chains", type=int, default=8)
    p.add_argument("--chain-len", type=int, default=80)
    p.add_argument("--train-repeats", type=int, default=14)
    p.add_argument("--epochs", type=int, default=8, help="tiny backend epochs")
    p.add_argument("--backend", choices=["tiny","pretrained"], default="tiny")
    p.add_argument("--model", type=str, default="distilbert-base-uncased")
    p.add_argument("--pretrained-epochs", type=int, default=4)
    p.add_argument("--null-sims", type=int, default=500)
    p.add_argument("--out", type=str, default="/mnt/data/adrianic_v54c_persistent_discourse_results")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()
    cfg = Config(seeds=args.seeds, chains_per_seed=args.chains, chain_len=args.chain_len, train_repeats_per_state=args.train_repeats, transformer_epochs=args.epochs, semantic_backend=args.backend, pretrained_model=args.model, pretrained_epochs=args.pretrained_epochs, null_simulations=args.null_sims, output_dir=args.out)
    if args.smoke:
        cfg.seeds=min(cfg.seeds,2); cfg.chains_per_seed=min(cfg.chains_per_seed,2); cfg.chain_len=min(cfg.chain_len,40); cfg.train_repeats_per_state=min(cfg.train_repeats_per_state,6); cfg.transformer_epochs=min(cfg.transformer_epochs,3)
    outdir = Path(cfg.output_dir); outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "config.json").write_text(json.dumps(asdict(cfg), indent=2))
    self_test()
    rows=[]; all_clauses=[]; all_edges=[]
    for seed in range(cfg.seeds):
        print(f"seed {seed+1}/{cfg.seeds}", flush=True)
        row, clauses, edges = run_seed(seed, cfg, outdir)
        rows.append(row); all_clauses.append(clauses); all_edges.append(edges)
        print(f"  A Δ={100*row['synthetic_accuracy_only_delta']:+.2f}pp S Δ={100*row['synthetic_sharpness_matched_delta']:+.2f}pp C Δ={100*row['synthetic_confusion_matched_delta']:+.2f}pp semantic Δ={100*row['semantic_raw_delta']:+.2f}pp rescued={row['diag_rescued_n']}", flush=True)
    summary=pd.DataFrame(rows); summary.to_csv(outdir/"summary.csv", index=False)
    pd.concat(all_clauses, ignore_index=True).to_csv(outdir/"clauses.csv", index=False)
    pd.concat(all_edges, ignore_index=True).to_csv(outdir/"edges.csv", index=False)
    report=make_report(summary,cfg); (outdir/"REPORT.md").write_text(report); print("\n"+report)


if __name__ == "__main__":
    main()
