from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F


ROOT = Path("/mnt/data")
OUT = ROOT / "adrianic_v51_entity_coreference_results"
OUT.mkdir(parents=True, exist_ok=True)

RELATIONS = ("contains", "supports", "precedes", "maps")
DIRECTIONS = ("fwd", "rev")
REL_LABELS = tuple(
    f"{r}:{d}"
    for r in RELATIONS
    for d in DIRECTIONS
)
REL_TO_ID = {x: i for i, x in enumerate(REL_LABELS)}
ID_TO_REL = {i: x for x, i in REL_TO_ID.items()}

N_REFERENTS = 3
N_CLASSES = N_REFERENTS * len(REL_LABELS)


# =============================================================================
# Discourse/coreference templates
# =============================================================================

SCENARIOS = {
    "carry": {
        "train_context": [
            "{a} carried {b} while {c} watched.",
            "While {c} watched, {a} carried {b}.",
        ],
        "test_context": [
            "{b} was carried by {a} as {c} watched.",
            "{c} observed {a} carrying {b}.",
        ],
        "train_ref": {
            0: ["the carrier", "the one carrying"],
            1: ["the carried one", "the one being carried"],
            2: ["the watcher", "the one watching"],
        },
        "test_ref": {
            0: ["the person doing the carrying", "the carrier in that scene"],
            1: ["the person in transit", "the one transported"],
            2: ["the observer", "the witness to the carrying"],
        },
    },
    "handoff": {
        "train_context": [
            "{a} handed {b} to {c}.",
            "{a} passed {b} over to {c}.",
        ],
        "test_context": [
            "{c} received {b} from {a}.",
            "From {a}, {c} was given {b}.",
        ],
        "train_ref": {
            0: ["the giver", "the one handing it over"],
            1: ["the transferred one", "the one being handed over"],
            2: ["the receiver", "the one receiving it"],
        },
        "test_ref": {
            0: ["the source of the handoff", "the person who gave it"],
            1: ["the transferred participant", "the handoff target object"],
            2: ["the recipient", "the person who got it"],
        },
    },
    "follow": {
        "train_context": [
            "{a} followed {b} while {c} observed.",
            "With {c} observing, {a} followed {b}.",
        ],
        "test_context": [
            "{b} was followed by {a} as {c} looked on.",
            "{c} saw {a} trailing {b}.",
        ],
        "train_ref": {
            0: ["the follower", "the one following"],
            1: ["the one being followed", "the leader"],
            2: ["the observer", "the one observing"],
        },
        "test_ref": {
            0: ["the person trailing behind", "the pursuer"],
            1: ["the person out front", "the one ahead"],
            2: ["the witness", "the person looking on"],
        },
    },
    "escort": {
        "train_context": [
            "{a} escorted {b} while {c} waited.",
            "While {c} waited, {a} escorted {b}.",
        ],
        "test_context": [
            "{b} was escorted by {a} as {c} waited.",
            "{c} waited while {a} guided {b}.",
        ],
        "train_ref": {
            0: ["the escort", "the guide"],
            1: ["the escorted one", "the one being guided"],
            2: ["the waiter", "the one waiting"],
        },
        "test_ref": {
            0: ["the person doing the guiding", "the guide in that event"],
            1: ["the person under escort", "the guided person"],
            2: ["the person who stayed behind", "the waiting observer"],
        },
    },
}

REL_TRAIN = {
    "contains:fwd": [
        "{ref} contains {d}.",
        "{ref} has {d} inside.",
    ],
    "contains:rev": [
        "{ref} is inside {d}.",
        "{ref} is contained by {d}.",
    ],
    "supports:fwd": [
        "{ref} supports {d}.",
        "{ref} holds up {d}.",
    ],
    "supports:rev": [
        "{ref} is supported by {d}.",
        "{ref} rests on {d}.",
    ],
    "precedes:fwd": [
        "{ref} precedes {d}.",
        "{ref} comes before {d}.",
    ],
    "precedes:rev": [
        "{ref} follows {d}.",
        "{ref} comes after {d}.",
    ],
    "maps:fwd": [
        "{ref} maps to {d}.",
        "{ref} points to {d}.",
    ],
    "maps:rev": [
        "{ref} is mapped from {d}.",
        "{ref} is the target of {d}.",
    ],
}

REL_TEST = {
    "contains:fwd": [
        "Inside {ref} is {d}.",
        "{d} remains within {ref}.",
    ],
    "contains:rev": [
        "Inside {d} is {ref}.",
        "{d} keeps {ref} within.",
    ],
    "supports:fwd": [
        "Support for {d} comes from {ref}.",
        "{d} is held up by {ref}.",
    ],
    "supports:rev": [
        "Support for {ref} comes from {d}.",
        "{d} holds up {ref}.",
    ],
    "precedes:fwd": [
        "Before {d} comes {ref}.",
        "{d} trails behind {ref}.",
    ],
    "precedes:rev": [
        "After {d} comes {ref}.",
        "{ref} trails behind {d}.",
    ],
    "maps:fwd": [
        "To {d}, {ref} points.",
        "{d} is the target of {ref}.",
    ],
    "maps:rev": [
        "To {ref}, {d} points.",
        "{ref} is the target of {d}.",
    ],
}


# =============================================================================
# Names and slot normalization
# =============================================================================

SYL1 = ("na", "ta", "ve", "ri", "lo", "ke", "mi", "sa", "do", "fi", "ga", "po")
SYL2 = ("ra", "ven", "ko", "lin", "ma", "tor", "shi", "del", "rin", "ka", "mo", "se")


def make_name(rng: random.Random):
    return (
        rng.choice(SYL1)
        + rng.choice(SYL2)
    ).capitalize()


def unique_names(rng: random.Random, n=4):
    out = []
    while len(out) < n:
        x = make_name(rng)
        if x not in out:
            out.append(x)
    return out


def normalize_names(text: str, names: list[str]):
    """
    Entity mention boundaries are supplied by a deterministic name slotter.

    This is intentionally NOT claimed as open-ended NER.
    The transformer must solve discourse binding among three entity candidates.
    """
    out = text.lower()

    # Longest first avoids pathological substring replacements.
    pairs = sorted(
        enumerate(names),
        key=lambda kv: len(kv[1]),
        reverse=True,
    )

    for idx, name in pairs:
        out = re.sub(
            rf"\b{re.escape(name.lower())}\b",
            f"<n{idx}>",
            out,
        )

    return out


TOKEN_RE = re.compile(r"<n\d>|[a-z]+|[.,]")


def tokenize(text: str):
    return TOKEN_RE.findall(text.lower())


# Build vocabulary from templates and slots only.
def build_vocab():
    toks = {"<pad>", "<unk>", "<cls>"}
    fake = ["Nara", "Teko", "Vemi", "Saro"]

    for table in (SCENARIOS,):
        for spec in table.values():
            for key in ("train_context", "test_context"):
                for t in spec[key]:
                    rendered = t.format(
                        a=fake[0],
                        b=fake[1],
                        c=fake[2],
                    )
                    toks.update(
                        tokenize(
                            normalize_names(
                                rendered,
                                fake[:3],
                            )
                        )
                    )

            for key in ("train_ref", "test_ref"):
                for phrases in spec[key].values():
                    for p in phrases:
                        toks.update(tokenize(p))

    for table in (REL_TRAIN, REL_TEST):
        for templates in table.values():
            for t in templates:
                rendered = t.format(
                    ref="the participant",
                    d=fake[3],
                )
                toks.update(
                    tokenize(
                        normalize_names(
                            rendered,
                            fake,
                        )
                    )
                )

    for i in range(4):
        toks.add(f"<n{i}>")

    itos = sorted(toks)
    stoi = {t: i for i, t in enumerate(itos)}
    return stoi, itos


STOI, ITOS = build_vocab()
PAD = STOI["<pad>"]
UNK = STOI["<unk>"]
CLS = STOI["<cls>"]


def encode(text: str, max_len: int = 44):
    toks = ["<cls>"] + tokenize(text)
    ids = [
        STOI.get(t, UNK)
        for t in toks[:max_len]
    ]
    mask = [1] * len(ids)

    while len(ids) < max_len:
        ids.append(PAD)
        mask.append(0)

    return ids, mask


# =============================================================================
# Parse classes
# =============================================================================

def class_id(ref_idx: int, rel_label: str):
    return ref_idx * len(REL_LABELS) + REL_TO_ID[rel_label]


def decode_class(cid: int):
    ref_idx = int(cid) // len(REL_LABELS)
    rel_id = int(cid) % len(REL_LABELS)
    return ref_idx, ID_TO_REL[rel_id]


def parse_key(ref_idx: int, rel_label: str):
    return f"ref{ref_idx}|{rel_label}"


def decode_key(key: str):
    ref, rel = key.split("|", 1)
    return int(ref[3:]), rel


# =============================================================================
# Dataset
# =============================================================================

def make_dataset(
    seed: int,
    train_repeats: int = 18,
    test_repeats: int = 12,
):
    rng = random.Random(seed + 5100)

    train_rows = []
    test_rows = []

    scenario_names = list(SCENARIOS)

    for ref_idx in range(N_REFERENTS):
        for rel_label in REL_LABELS:
            for split, repeats in (
                ("train", train_repeats),
                ("test", test_repeats),
            ):
                for rep in range(repeats):
                    names = unique_names(rng, 4)
                    a, b, c, d = names

                    scenario_name = rng.choice(
                        scenario_names
                    )
                    scenario = SCENARIOS[
                        scenario_name
                    ]

                    if split == "train":
                        context = rng.choice(
                            scenario["train_context"]
                        )
                        ref = rng.choice(
                            scenario["train_ref"][ref_idx]
                        )
                        rel_template = rng.choice(
                            REL_TRAIN[rel_label]
                        )
                    else:
                        context = rng.choice(
                            scenario["test_context"]
                        )
                        ref = rng.choice(
                            scenario["test_ref"][ref_idx]
                        )
                        rel_template = rng.choice(
                            REL_TEST[rel_label]
                        )

                    context_text = context.format(
                        a=a,
                        b=b,
                        c=c,
                    )
                    target_text = rel_template.format(
                        ref=ref,
                        d=d,
                    )

                    raw = (
                        context_text
                        + " "
                        + target_text
                    )

                    normalized = normalize_names(
                        raw,
                        names,
                    )

                    row = {
                        "split": split,
                        "scenario": scenario_name,
                        "raw_text": raw,
                        "text": normalized,
                        "name0": a,
                        "name1": b,
                        "name2": c,
                        "target_name": d,
                        "ref_idx": ref_idx,
                        "rel_label": rel_label,
                        "parse_key": parse_key(
                            ref_idx,
                            rel_label,
                        ),
                        "class_id": class_id(
                            ref_idx,
                            rel_label,
                        ),
                    }

                    if split == "train":
                        train_rows.append(row)
                    else:
                        test_rows.append(row)

    rng.shuffle(train_rows)
    rng.shuffle(test_rows)

    return (
        pd.DataFrame(train_rows),
        pd.DataFrame(test_rows),
    )


# =============================================================================
# Tiny discourse transformer
# =============================================================================

class DiscourseTransformer(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        n_classes: int = N_CLASSES,
        d_model: int = 48,
        nhead: int = 4,
        layers: int = 1,
        ff: int = 96,
        max_len: int = 44,
    ):
        super().__init__()

        self.emb = nn.Embedding(
            vocab_size,
            d_model,
            padding_idx=PAD,
        )
        self.pos = nn.Embedding(
            max_len,
            d_model,
        )

        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=ff,
            dropout=0.10,
            batch_first=True,
            activation="gelu",
        )

        self.enc = nn.TransformerEncoder(
            layer,
            num_layers=layers,
        )

        self.ref_out = nn.Linear(
            d_model,
            N_REFERENTS,
        )
        self.rel_out = nn.Linear(
            d_model,
            len(REL_LABELS),
        )

    def forward(self, ids, mask):
        b, t = ids.shape
        pos = torch.arange(
            t,
            device=ids.device,
        )[None, :].expand(b, t)

        x = self.emb(ids) + self.pos(pos)

        z = self.enc(
            x,
            src_key_padding_mask=(mask == 0),
        )

        h = z[:, 0, :]
        return (
            self.ref_out(h),
            self.rel_out(h),
        )


def batchify(df):
    ids = []
    masks = []

    for text in df.text:
        a, b = encode(text)
        ids.append(a)
        masks.append(b)

    return (
        torch.tensor(ids, dtype=torch.long),
        torch.tensor(masks, dtype=torch.long),
        torch.tensor(
            df.class_id.to_numpy(),
            dtype=torch.long,
        ),
    )


def train_model(
    seed: int,
    train_df: pd.DataFrame,
    epochs: int = 18,
    label_noise: float = 0.03,
):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    model = DiscourseTransformer(
        len(ITOS)
    )

    opt = torch.optim.AdamW(
        model.parameters(),
        lr=0.0035,
        weight_decay=1e-4,
    )

    x, m, y_clean = batchify(train_df)
    n = len(train_df)

    for epoch in range(epochs):
        order = torch.randperm(n)
        y = y_clean.clone()

        if label_noise:
            nm = torch.rand(n) < label_noise
            k = int(nm.sum())
            if k:
                y[nm] = torch.randint(
                    0,
                    N_CLASSES,
                    (k,),
                )

        for start in range(0, n, 64):
            idx = order[start:start + 64]
            ref_logits, rel_logits = model(
                x[idx],
                m[idx],
            )

            ref_y = y[idx] // len(REL_LABELS)
            rel_y = y[idx] % len(REL_LABELS)

            loss = (
                F.cross_entropy(
                    ref_logits,
                    ref_y,
                )
                + F.cross_entropy(
                    rel_logits,
                    rel_y,
                )
            )

            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0,
            )
            opt.step()

    return model


def make_proposals(
    model,
    test_df,
    top_k: int = 8,
):
    x, m, _ = batchify(test_df)

    model.eval()
    with torch.no_grad():
        ref_logits, rel_logits = model(
            x,
            m,
        )
        ref_probs = F.softmax(
            ref_logits,
            dim=-1,
        ).cpu().numpy()
        rel_probs = F.softmax(
            rel_logits,
            dim=-1,
        ).cpu().numpy()

    rows = []

    for i, row in test_df.reset_index(
        drop=True
    ).iterrows():
        joint = np.outer(
            ref_probs[i],
            rel_probs[i],
        ).reshape(-1)

        order = np.argsort(-joint)
        top = order[:top_k]

        keys = []
        top_probs = []

        for cid in top:
            ref_idx, rel = decode_class(
                int(cid)
            )
            keys.append(
                parse_key(
                    ref_idx,
                    rel,
                )
            )
            top_probs.append(
                float(joint[cid])
            )

        top1_ref, top1_rel = decode_class(
            int(order[0])
        )

        true_cid = int(row.class_id)

        out = dict(row)
        out["top1_parse"] = parse_key(
            top1_ref,
            top1_rel,
        )
        out["top1_correct"] = int(
            int(order[0]) == true_cid
        )
        out["topk_parse_keys"] = keys
        out["topk_probs"] = top_probs
        out["topk_contains_true"] = int(
            true_cid in top
        )

        out["top1_ref_correct"] = int(
            top1_ref == row.ref_idx
        )
        out["top1_rel_correct"] = int(
            top1_rel == row.rel_label
        )

        if out["top1_correct"]:
            et = "correct"
        elif (
            out["top1_ref_correct"]
            and not out["top1_rel_correct"]
        ):
            et = "relation_only"
        elif (
            out["top1_rel_correct"]
            and not out["top1_ref_correct"]
        ):
            et = "referent_only"
        else:
            et = "both"

        out["top1_error_type"] = et
        rows.append(out)

    return pd.DataFrame(rows)


# =============================================================================
# Consequence governance
# =============================================================================

class ParseHypothesisSet:
    def __init__(
        self,
        keys,
        probs,
        lr: float = 0.18,
    ):
        self.lr = float(lr)
        self.probs = {
            k: float(p)
            for k, p in zip(keys, probs)
        }
        self.trust = {
            k: 0.5
            for k in keys
        }

    def update(
        self,
        observation: str,
        forecast_fn,
    ):
        for key in self.probs:
            pred = forecast_fn(key)
            q = 1.0 if pred == observation else 0.0

            self.trust[key] = (
                (1.0 - self.lr)
                * self.trust[key]
                + self.lr * q
            )

    def score(self, key):
        t = min(
            1.0 - 1e-6,
            max(1e-6, self.trust[key]),
        )
        odds = t / (1.0 - t)

        return (
            max(1e-12, self.probs[key])
            * odds
        )

    def choose(self):
        return max(
            self.probs,
            key=lambda k: (
                self.score(k),
                self.trust[k],
            ),
        )

    def snapshot(self):
        return dict(self.trust)


def forecast_code(
    case_id: str,
    parse_key_: str,
):
    h = hashlib.sha256(
        f"{case_id}|{parse_key_}".encode()
    ).hexdigest()[:16]
    return f"obs_{h}"


def external_observation(
    case_id: str,
    grounded_key: str,
    keys: list[str],
    noise: float,
    rng: random.Random,
):
    if rng.random() >= noise:
        return forecast_code(
            case_id,
            grounded_key,
        )

    wrongs = [
        k for k in keys
        if k != grounded_key
    ]

    if not wrongs:
        return (
            f"noise_{rng.randrange(1_000_000)}"
        )

    return forecast_code(
        case_id,
        rng.choice(wrongs),
    )


def shuffled_choice(
    keys,
    probs,
    trust,
    seed,
):
    vals = [trust[k] for k in keys]
    rng = random.Random(seed)
    rng.shuffle(vals)

    scores = {}

    for k, p, t in zip(
        keys,
        probs,
        vals,
    ):
        t = min(
            1.0 - 1e-6,
            max(1e-6, t),
        )
        scores[k] = (
            max(1e-12, p)
            * t / (1.0 - t)
        )

    return max(
        keys,
        key=lambda k: scores[k],
    )


def frozen_choice(
    keys,
    probs,
    trust,
):
    scores = {}

    for k, p in zip(
        keys,
        probs,
    ):
        t = min(
            1.0 - 1e-6,
            max(1e-6, trust[k]),
        )
        scores[k] = (
            max(1e-12, p)
            * t / (1.0 - t)
        )

    return max(
        keys,
        key=lambda k: scores[k],
    )


def evaluate_governance(
    proposals: pd.DataFrame,
    seed: int,
    noise: float,
    evidence_episodes: int = 12,
    shift_episodes: int = 12,
):
    rng = random.Random(
        seed
        + 51001
        + int(noise * 1000)
    )

    rows = []

    for i, row in proposals.reset_index(
        drop=True
    ).iterrows():
        keys = list(
            row.topk_parse_keys
        )
        probs = list(
            row.topk_probs
        )
        true_key = row.parse_key
        case_id = f"s{seed}_case{i}"

        if true_key not in keys:
            rows.append({
                "seed": seed,
                "noise": noise,
                "case_id": case_id,
                "true_key": true_key,
                "top1_parse": row.top1_parse,
                "top1_correct": row.top1_correct,
                "top1_error_type":
                    row.top1_error_type,
                "topk_covered": 0,
                "adaptive_choice":
                    row.top1_parse,
                "adaptive_correct": 0,
                "shuffled_correct": 0,
                "rescued": 0,
                "post_shift_adaptive_correct":
                    np.nan,
                "post_shift_frozen_correct":
                    np.nan,
                "switch_episode": np.nan,
            })
            continue

        hs = ParseHypothesisSet(
            keys,
            probs,
        )

        for _ in range(
            evidence_episodes
        ):
            obs = external_observation(
                case_id,
                true_key,
                keys,
                noise,
                rng,
            )
            hs.update(
                obs,
                lambda k: forecast_code(
                    case_id,
                    k,
                ),
            )

        adaptive = hs.choose()
        trust_snap = hs.snapshot()

        shuffled = shuffled_choice(
            keys,
            probs,
            trust_snap,
            seed * 100000 + i * 131,
        )

        # Grounding shift chooses a retained parse that differs from the true
        # parse in at least one dimension. Prefer an entity-binding change when
        # available, because this directly stress-tests coreference revision.
        true_ref, true_rel = decode_key(
            true_key
        )

        entity_shift = [
            k for k in keys
            if decode_key(k)[0] != true_ref
            and decode_key(k)[1] == true_rel
        ]

        relation_shift = [
            k for k in keys
            if decode_key(k)[0] == true_ref
            and decode_key(k)[1] != true_rel
        ]

        alternatives = [
            k for k in keys
            if k != true_key
        ]

        if entity_shift:
            shift_target = entity_shift[0]
            shift_type = "entity"
        elif relation_shift:
            shift_target = relation_shift[0]
            shift_type = "relation"
        else:
            shift_target = alternatives[0]
            shift_type = "both"

        frozen = frozen_choice(
            keys,
            probs,
            trust_snap,
        )

        first_switch = None

        for ep in range(
            1,
            shift_episodes + 1,
        ):
            obs = external_observation(
                case_id,
                shift_target,
                keys,
                noise,
                rng,
            )

            hs.update(
                obs,
                lambda k: forecast_code(
                    case_id,
                    k,
                ),
            )

            if (
                first_switch is None
                and hs.choose()
                == shift_target
            ):
                first_switch = ep

        post_adaptive = hs.choose()

        rows.append({
            "seed": seed,
            "noise": noise,
            "case_id": case_id,
            "true_key": true_key,
            "top1_parse": row.top1_parse,
            "top1_correct": row.top1_correct,
            "top1_error_type":
                row.top1_error_type,
            "topk_covered": 1,
            "adaptive_choice": adaptive,
            "adaptive_correct": int(
                adaptive == true_key
            ),
            "shuffled_correct": int(
                shuffled == true_key
            ),
            "rescued": int(
                row.top1_correct == 0
                and adaptive == true_key
            ),
            "shift_target": shift_target,
            "shift_type": shift_type,
            "post_shift_adaptive_correct":
                int(
                    post_adaptive
                    == shift_target
                ),
            "post_shift_frozen_correct":
                int(
                    frozen
                    == shift_target
                ),
            "switch_episode": (
                first_switch
                if first_switch is not None
                else shift_episodes + 1
            ),
            "trust_snapshot":
                json.dumps(trust_snap),
        })

    return pd.DataFrame(rows)


# =============================================================================
# Seed / multi-seed runners
# =============================================================================

def run_seed(
    seed: int,
    top_k: int = 8,
    train_repeats: int = 24,
    test_repeats: int = 12,
    epochs: int = 26,
):
    train_df, test_df = make_dataset(
        seed,
        train_repeats=train_repeats,
        test_repeats=test_repeats,
    )

    model = train_model(
        seed,
        train_df,
        epochs=epochs,
    )

    proposals = make_proposals(
        model,
        test_df,
        top_k=top_k,
    )

    summary_rows = []
    details = []

    for noise in (0.0, 0.15, 0.30):
        d = evaluate_governance(
            proposals,
            seed=seed,
            noise=noise,
        )
        details.append(d)

        covered = d[
            d.topk_covered == 1
        ]
        hard = covered[
            covered.top1_correct == 0
        ]

        rescue = {}

        for et in (
            "relation_only",
            "referent_only",
            "both",
        ):
            g = hard[
                hard.top1_error_type == et
            ]
            rescue[et] = (
                float(g.rescued.mean())
                if len(g)
                else np.nan
            )

        summary_rows.append({
            "seed": seed,
            "noise": noise,

            "top1_parse_accuracy":
                float(
                    proposals.top1_correct.mean()
                ),
            "top1_ref_accuracy":
                float(
                    proposals.top1_ref_correct.mean()
                ),
            "top1_rel_accuracy":
                float(
                    proposals.top1_rel_correct.mean()
                ),
            "topk_parse_coverage":
                float(
                    proposals.topk_contains_true.mean()
                ),

            "adaptive_accuracy_all":
                float(
                    d.adaptive_correct.mean()
                ),
            "adaptive_accuracy_covered":
                float(
                    covered.adaptive_correct.mean()
                ) if len(covered) else np.nan,
            "shuffled_accuracy_covered":
                float(
                    covered.shuffled_correct.mean()
                ) if len(covered) else np.nan,

            "hard_case_count": int(
                len(hard)
            ),
            "hard_rescue_rate":
                float(
                    hard.rescued.mean()
                ) if len(hard) else np.nan,

            "relation_error_rescue":
                rescue["relation_only"],
            "referent_error_rescue":
                rescue["referent_only"],
            "both_error_rescue":
                rescue["both"],

            "post_shift_adaptive_accuracy":
                float(
                    covered.post_shift_adaptive_correct.mean()
                ) if len(covered) else np.nan,
            "post_shift_frozen_accuracy":
                float(
                    covered.post_shift_frozen_correct.mean()
                ) if len(covered) else np.nan,
            "median_switch_episode":
                float(
                    covered.switch_episode.median()
                ) if len(covered) else np.nan,
        })

    return (
        pd.DataFrame(summary_rows),
        pd.concat(
            details,
            ignore_index=True,
        ),
        proposals,
    )


def run_many(
    seeds: int = 8,
    **kwargs,
):
    summaries = []
    details = []
    proposals = []

    for seed in range(seeds):
        print("seed", seed)

        s, d, p = run_seed(
            seed,
            **kwargs,
        )

        summaries.append(s)
        details.append(d)
        p["seed"] = seed
        proposals.append(p)

        print(
            s[[
                "noise",
                "top1_parse_accuracy",
                "top1_ref_accuracy",
                "top1_rel_accuracy",
                "topk_parse_coverage",
                "adaptive_accuracy_all",
                "adaptive_accuracy_covered",
                "shuffled_accuracy_covered",
                "hard_case_count",
                "hard_rescue_rate",
                "referent_error_rescue",
                "relation_error_rescue",
                "post_shift_adaptive_accuracy",
                "post_shift_frozen_accuracy",
                "median_switch_episode",
            ]].to_string(index=False)
        )

    return (
        pd.concat(
            summaries,
            ignore_index=True,
        ),
        pd.concat(
            details,
            ignore_index=True,
        ),
        pd.concat(
            proposals,
            ignore_index=True,
        ),
    )


def make_checks(summary):
    checks = {}

    for noise in sorted(
        summary.noise.unique()
    ):
        g = summary[
            summary.noise == noise
        ]
        tag = int(round(
            noise * 100
        ))

        checks[
            f"noise{tag}_adaptive_beats_top1_seed_fraction"
        ] = float(np.mean(
            g.adaptive_accuracy_all
            > g.top1_parse_accuracy
        ))

        checks[
            f"noise{tag}_adaptive_beats_shuffle_seed_fraction"
        ] = float(np.mean(
            g.adaptive_accuracy_covered
            > g.shuffled_accuracy_covered
        ))

        checks[
            f"noise{tag}_covered_accuracy_median"
        ] = float(np.nanmedian(
            g.adaptive_accuracy_covered
        ))

        checks[
            f"noise{tag}_hard_rescue_median"
        ] = float(np.nanmedian(
            g.hard_rescue_rate
        ))

        checks[
            f"noise{tag}_referent_rescue_median"
        ] = float(np.nanmedian(
            g.referent_error_rescue
        ))

        checks[
            f"noise{tag}_relation_rescue_median"
        ] = float(np.nanmedian(
            g.relation_error_rescue
        ))

        checks[
            f"noise{tag}_post_shift_adaptive_median"
        ] = float(np.nanmedian(
            g.post_shift_adaptive_accuracy
        ))

        checks[
            f"noise{tag}_post_shift_frozen_median"
        ] = float(np.nanmedian(
            g.post_shift_frozen_accuracy
        ))

    checks[
        "topk_parse_coverage_median"
    ] = float(np.median(
        summary.topk_parse_coverage
    ))

    return checks


def main(argv=None):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seeds",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--train-repeats",
        type=int,
        default=18,
    )
    parser.add_argument(
        "--test-repeats",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=18,
    )

    args = parser.parse_args(argv)

    summary, details, proposals = run_many(
        seeds=args.seeds,
        top_k=args.top_k,
        train_repeats=args.train_repeats,
        test_repeats=args.test_repeats,
        epochs=args.epochs,
    )

    tag = f"{args.seeds}seed"

    summary.to_csv(
        OUT / f"{tag}_summary.csv",
        index=False,
    )
    details.to_csv(
        OUT / f"{tag}_details.csv",
        index=False,
    )
    proposals.to_csv(
        OUT / f"{tag}_proposals.csv",
        index=False,
    )

    checks = make_checks(summary)

    (
        OUT / f"{tag}_checks.json"
    ).write_text(
        json.dumps(
            checks,
            indent=2,
        )
    )

    med = summary.groupby(
        "noise"
    ).median(
        numeric_only=True
    )

    report = f"""Adrianic v5.1 — Entity/Coreference Semantic Governance

Seeds: {args.seeds}
Parse classes: {N_CLASSES}
Retained proposals: {args.top_k}

Question
========
Can the semantic front end propose BOTH:
- which discourse entity an anaphoric phrase refers to
- which relation/direction is being asserted

and can downstream consequence governance correct the parse when the
transformer's first choice is wrong?

Entity boundary
===============
Raw generated names are present in the text.

A deterministic name slotter maps the four known generated names into stable
mention slots <n0>..<n3> before the transformer.

Therefore this test advances from fixed <e1>/<e2> relation semantics to
multi-entity discourse/coreference binding.

It does NOT yet establish open-ended named-entity recognition.

Held-out language
=================
Training and test use different context syntax, coreference phrases and
relation sentence arrangements.

Candidate space
===============
3 possible discourse referents x 8 relation/direction hypotheses = 24 parses.

Transformer confidence is a proposal prior.
Consequence agreement contributes empirical odds.

Median metrics
==============
{med.to_string()}

Checks
======
{json.dumps(checks, indent=2)}

Interpretation boundary
=======================
A positive result supports correction of both semantic relation errors and
entity/coreference binding errors when the correct parse survives in the
retained proposal set and consequences distinguish the hypotheses.

It does not establish unrestricted NER, unrestricted coreference, or AGI.
"""

    (
        OUT / f"{tag}_REPORT.txt"
    ).write_text(report)

    print(report)


if __name__ == "__main__":
    main()
