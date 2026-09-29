from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F


ROOT = Path("/mnt/data")
OUT = ROOT / "adrianic_v50_semantic_proposal_results"
OUT.mkdir(parents=True, exist_ok=True)

RELATIONS = ("contains", "supports", "precedes", "maps")
DIRECTIONS = ("fwd", "rev")
LABELS = tuple(
    f"{r}:{d}"
    for r in RELATIONS
    for d in DIRECTIONS
)
LABEL_TO_ID = {x: i for i, x in enumerate(LABELS)}
ID_TO_LABEL = {i: x for x, i in LABEL_TO_ID.items()}

TOKEN_RE = re.compile(r"[a-z0-9_<>']+")


# =============================================================================
# Natural-language semantic templates
# =============================================================================

TRAIN_TEMPLATES = {
    # Label meaning is canonical relation direction, not surface word order.
    # Example: contains:fwd means <e1> CONTAINS <e2>, whether active or passive.
    "contains:fwd": [
        "<e1> contains <e2>",
        "<e2> is inside <e1>",
        "<e1> encloses <e2>",
        "<e2> is enclosed by <e1>",
    ],
    "contains:rev": [
        "<e2> contains <e1>",
        "<e1> is inside <e2>",
        "<e2> encloses <e1>",
        "<e1> is enclosed by <e2>",
    ],
    "supports:fwd": [
        "<e1> supports <e2>",
        "<e2> is supported by <e1>",
        "<e1> backs <e2>",
        "<e2> rests on <e1>",
    ],
    "supports:rev": [
        "<e2> supports <e1>",
        "<e1> is supported by <e2>",
        "<e2> backs <e1>",
        "<e1> rests on <e2>",
    ],
    "precedes:fwd": [
        "<e1> precedes <e2>",
        "<e2> follows <e1>",
        "<e1> comes before <e2>",
        "<e2> comes after <e1>",
    ],
    "precedes:rev": [
        "<e2> precedes <e1>",
        "<e1> follows <e2>",
        "<e2> comes before <e1>",
        "<e1> comes after <e2>",
    ],
    "maps:fwd": [
        "<e1> maps to <e2>",
        "<e2> is mapped from <e1>",
        "<e1> points to <e2>",
        "<e2> is the target of <e1>",
    ],
    "maps:rev": [
        "<e2> maps to <e1>",
        "<e1> is mapped from <e2>",
        "<e2> points to <e1>",
        "<e1> is the target of <e2>",
    ],
}

# Held-out surface arrangements use the same semantic vocabulary but different
# order/composition. A few cues remain intentionally ambiguous across classes.
TEST_TEMPLATES = {
    "contains:fwd": [
        "inside <e1> is <e2>",
        "within <e1> sits <e2>",
        "<e1> has <e2> inside",
    ],
    "contains:rev": [
        "inside <e2> is <e1>",
        "within <e2> sits <e1>",
        "<e2> has <e1> inside",
    ],
    "supports:fwd": [
        "support for <e2> comes from <e1>",
        "<e2> is held up by <e1>",
        "backing <e2> is <e1>",
    ],
    "supports:rev": [
        "support for <e1> comes from <e2>",
        "<e1> is held up by <e2>",
        "backing <e1> is <e2>",
    ],
    "precedes:fwd": [
        "before <e2> comes <e1>",
        "<e2> trails <e1>",
        "<e1> is ahead of <e2>",
    ],
    "precedes:rev": [
        "before <e1> comes <e2>",
        "<e1> trails <e2>",
        "<e2> is ahead of <e1>",
    ],
    "maps:fwd": [
        "to <e2> <e1> points",
        "from <e1> <e2> is mapped",
        "the target of <e1> is <e2>",
    ],
    "maps:rev": [
        "to <e1> <e2> points",
        "from <e2> <e1> is mapped",
        "the target of <e2> is <e1>",
    ],
}

FILLERS = (
    "",
    "directly",
    "usually",
    "in context",
    "for this case",
)


def tokenize(text: str):
    return TOKEN_RE.findall(text.lower())


def build_vocab():
    toks = {"<pad>", "<unk>", "<cls>"}
    for table in (TRAIN_TEMPLATES, TEST_TEMPLATES):
        for templates in table.values():
            for t in templates:
                toks.update(tokenize(t))
    toks.update(tokenize(" ".join(FILLERS)))
    itos = sorted(toks)
    stoi = {t: i for i, t in enumerate(itos)}
    return stoi, itos


STOI, ITOS = build_vocab()
PAD_ID = STOI["<pad>"]
UNK_ID = STOI["<unk>"]
CLS_ID = STOI["<cls>"]


def encode(text: str, max_len: int = 14):
    toks = ["<cls>"] + tokenize(text)
    ids = [STOI.get(t, UNK_ID) for t in toks[:max_len]]
    mask = [1] * len(ids)

    while len(ids) < max_len:
        ids.append(PAD_ID)
        mask.append(0)

    return ids, mask


def render_template(template: str, filler: str):
    # Entity identities are handled by the structural layer. The semantic
    # transformer sees stable entity slots, not memorized entity names.
    text = template

    if filler:
        # Put filler in different harmless positions to discourage exact-string
        # memorization without changing relation semantics.
        if text.startswith("<e1>"):
            text = f"{filler} {text}"
        else:
            text = f"{text} {filler}"

    return " ".join(text.split())


def semantic_dataset(
    seed: int,
    train_repeats: int = 10,
    test_repeats: int = 10,
):
    rng = random.Random(seed + 5000)
    train_rows = []
    test_rows = []

    for label in LABELS:
        for _ in range(train_repeats):
            template = rng.choice(TRAIN_TEMPLATES[label])
            filler = rng.choice(FILLERS)
            train_rows.append({
                "text": render_template(template, filler),
                "label": label,
                "label_id": LABEL_TO_ID[label],
            })

        for _ in range(test_repeats):
            template = rng.choice(TEST_TEMPLATES[label])
            filler = rng.choice(FILLERS)
            test_rows.append({
                "text": render_template(template, filler),
                "label": label,
                "label_id": LABEL_TO_ID[label],
            })

    rng.shuffle(train_rows)
    rng.shuffle(test_rows)

    return pd.DataFrame(train_rows), pd.DataFrame(test_rows)


# =============================================================================
# Tiny semantic transformer
# =============================================================================

class SemanticTransformer(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        n_labels: int,
        d_model: int = 48,
        nhead: int = 4,
        layers: int = 2,
        ff: int = 96,
        max_len: int = 14,
    ):
        super().__init__()

        self.emb = nn.Embedding(
            vocab_size,
            d_model,
            padding_idx=PAD_ID,
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
        self.out = nn.Linear(
            d_model,
            n_labels,
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

        cls = z[:, 0, :]
        return self.out(cls)


def frame_batch(df: pd.DataFrame):
    ids = []
    masks = []

    for text in df.text:
        a, b = encode(text)
        ids.append(a)
        masks.append(b)

    x = torch.tensor(
        ids,
        dtype=torch.long,
    )
    m = torch.tensor(
        masks,
        dtype=torch.long,
    )
    y = torch.tensor(
        df.label_id.to_numpy(),
        dtype=torch.long,
    )

    return x, m, y


def train_semantic_transformer(
    seed: int,
    train_df: pd.DataFrame,
    epochs: int = 22,
    label_noise: float = 0.04,
):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    model = SemanticTransformer(
        len(ITOS),
        len(LABELS),
    )
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=0.004,
        weight_decay=1e-4,
    )

    x, m, y_clean = frame_batch(train_df)
    n = len(train_df)

    for epoch in range(epochs):
        order = torch.randperm(n)
        y = y_clean.clone()

        # Small symmetric label noise prevents a trivially overconfident parser.
        if label_noise > 0:
            noise_mask = torch.rand(n) < label_noise
            n_noisy = int(noise_mask.sum())
            if n_noisy:
                y[noise_mask] = torch.randint(
                    0,
                    len(LABELS),
                    (n_noisy,),
                )

        for start in range(0, n, 32):
            idx = order[start:start + 32]
            logits = model(
                x[idx],
                m[idx],
            )
            loss = F.cross_entropy(
                logits,
                y[idx],
            )

            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0,
            )
            opt.step()

    return model


def proposal_table(
    model,
    test_df: pd.DataFrame,
    top_k: int = 3,
):
    x, m, _ = frame_batch(test_df)

    model.eval()
    with torch.no_grad():
        probs = F.softmax(
            model(x, m),
            dim=-1,
        ).cpu().numpy()

    rows = []

    for i, base in test_df.reset_index(drop=True).iterrows():
        order = np.argsort(-probs[i])
        top = order[:top_k]

        row = dict(base)
        row["top1_label"] = ID_TO_LABEL[int(order[0])]
        row["top1_prob"] = float(probs[i, order[0]])
        row["true_prob"] = float(
            probs[i, base.label_id]
        )
        row["topk_labels"] = [
            ID_TO_LABEL[int(j)]
            for j in top
        ]
        row["topk_probs"] = [
            float(probs[i, j])
            for j in top
        ]
        row["top1_correct"] = int(
            order[0] == base.label_id
        )
        row["topk_contains_true"] = int(
            base.label_id in top
        )
        rows.append(row)

    return pd.DataFrame(rows)


# =============================================================================
# Adrianic semantic hypothesis governance
# =============================================================================

@dataclass
class HypothesisState:
    label: str
    semantic_prob: float
    trust: float = 0.5


class SemanticHypothesisSet:
    """
    Keeps multiple semantic proposals alive.

    Transformer confidence is a proposal prior, not truth.
    Downstream forecast-vs-observation agreement updates trust.
    """

    def __init__(
        self,
        labels: list[str],
        probs: list[float],
        lr: float = 0.18,
    ):
        self.lr = float(lr)
        self.states = {
            label: HypothesisState(
                label=label,
                semantic_prob=float(prob),
                trust=0.5,
            )
            for label, prob in zip(
                labels,
                probs,
            )
        }

    def update(
        self,
        observation: str,
        forecast_fn,
    ):
        for state in self.states.values():
            prediction = forecast_fn(
                state.label
            )

            q = 1.0 if (
                prediction == observation
            ) else 0.0

            state.trust = (
                (1.0 - self.lr)
                * state.trust
                + self.lr * q
            )

    def score(self, label: str):
        s = self.states[label]

        # Bayesian-style arbitration with no tuned mixing coefficient:
        #
        # semantic_prob acts as the proposal prior.
        # consequence trust contributes empirical odds.
        #
        # Strong downstream disagreement can therefore overturn a confident
        # semantic prior instead of the transformer permanently dominating.
        t = min(1.0 - 1e-6, max(1e-6, s.trust))
        consequence_odds = t / (1.0 - t)

        return (
            max(1e-12, s.semantic_prob)
            * consequence_odds
        )

    def choose(self):
        return max(
            self.states,
            key=lambda label: (
                self.score(label),
                self.states[label].trust,
            ),
        )

    def snapshot_trust(self):
        return {
            label: float(state.trust)
            for label, state in self.states.items()
        }


class FrozenHypothesisSet:
    def __init__(
        self,
        labels,
        probs,
        trust_snapshot,
    ):
        self.states = {
            label: HypothesisState(
                label=label,
                semantic_prob=float(prob),
                trust=float(
                    trust_snapshot[label]
                ),
            )
            for label, prob in zip(
                labels,
                probs,
            )
        }

    def score(self, label):
        s = self.states[label]
        t = min(1.0 - 1e-6, max(1e-6, s.trust))
        return (
            max(1e-12, s.semantic_prob)
            * (t / (1.0 - t))
        )

    def choose(self):
        return max(
            self.states,
            key=lambda label: (
                self.score(label),
                self.states[label].trust,
            ),
        )


def forecast_code(
    case_id: str,
    label: str,
):
    # Opaque deterministic forecast. No relation class receives privileged
    # consequence symbols.
    h = hashlib.sha256(
        f"{case_id}|{label}".encode()
    ).hexdigest()[:16]

    return f"obs_{h}"


def external_observation(
    case_id: str,
    grounded_label: str,
    candidate_labels: list[str],
    noise: float,
    rng: random.Random,
):
    if rng.random() >= noise:
        return forecast_code(
            case_id,
            grounded_label,
        )

    alternatives = [
        label
        for label in candidate_labels
        if label != grounded_label
    ]

    if not alternatives:
        return f"noise_{rng.randrange(1_000_000)}"

    wrong = rng.choice(alternatives)
    return forecast_code(
        case_id,
        wrong,
    )


def shuffled_trust_choice(
    labels,
    probs,
    trust_snapshot,
    seed,
):
    vals = [
        trust_snapshot[x]
        for x in labels
    ]

    rng = random.Random(seed)
    rng.shuffle(vals)

    scores = {}
    for label, prob, trust in zip(labels, probs, vals):
        t = min(1.0 - 1e-6, max(1e-6, trust))
        scores[label] = (
            max(1e-12, prob)
            * (t / (1.0 - t))
        )

    return max(
        labels,
        key=lambda x: scores[x],
    )


def run_grounding_condition(
    proposals: pd.DataFrame,
    seed: int,
    noise: float,
    evidence_episodes: int = 12,
    shift_episodes: int = 12,
):
    rng = random.Random(
        seed + int(noise * 1000) + 50123
    )

    rows = []

    for i, row in proposals.reset_index(drop=True).iterrows():
        labels = list(row.topk_labels)
        probs = list(row.topk_probs)
        true_label = row.label
        case_id = f"s{seed}_case{i}"

        semantic_only = labels[0]
        covered = true_label in labels

        if not covered:
            rows.append({
                "seed": seed,
                "noise": noise,
                "case_id": case_id,
                "text": row.text,
                "true_label": true_label,
                "top1_label": semantic_only,
                "top1_correct": int(
                    semantic_only == true_label
                ),
                "topk_covered": 0,
                "adaptive_choice": semantic_only,
                "adaptive_correct": 0,
                "shuffled_choice": semantic_only,
                "shuffled_correct": 0,
                "rescued_from_top1_error": 0,
                "shift_target": None,
                "post_shift_adaptive_choice": None,
                "post_shift_frozen_choice": None,
                "post_shift_adaptive_correct": np.nan,
                "post_shift_frozen_correct": np.nan,
                "switch_episode": np.nan,
            })
            continue

        hs = SemanticHypothesisSet(
            labels,
            probs,
        )

        # Evidence phase: multiple semantic hypotheses remain alive.
        for _ in range(evidence_episodes):
            obs = external_observation(
                case_id,
                true_label,
                labels,
                noise,
                rng,
            )

            hs.update(
                obs,
                lambda label: forecast_code(
                    case_id,
                    label,
                ),
            )

        adaptive_choice = hs.choose()
        snap = hs.snapshot_trust()

        shuffled_choice = shuffled_trust_choice(
            labels,
            probs,
            snap,
            seed=(
                seed * 100000
                + i * 97
                + int(noise * 100)
            ),
        )

        # Grounding-shift control:
        # keep the sentence and transformer probabilities fixed, but change
        # which proposal the external environment consistently supports.
        #
        # This is a synthetic context/convention shift, NOT a claim that normal
        # English relation meanings reverse.
        alternatives = [
            x for x in labels
            if x != true_label
        ]

        shift_target = (
            alternatives[0]
            if alternatives
            else true_label
        )

        frozen = FrozenHypothesisSet(
            labels,
            probs,
            snap,
        )

        first_switch = None

        for ep in range(1, shift_episodes + 1):
            obs = external_observation(
                case_id,
                shift_target,
                labels,
                noise,
                rng,
            )

            hs.update(
                obs,
                lambda label: forecast_code(
                    case_id,
                    label,
                ),
            )

            if (
                first_switch is None
                and hs.choose()
                == shift_target
            ):
                first_switch = ep

        post_shift_adaptive = hs.choose()
        post_shift_frozen = frozen.choose()

        rows.append({
            "seed": seed,
            "noise": noise,
            "case_id": case_id,
            "text": row.text,
            "true_label": true_label,
            "top1_label": semantic_only,
            "top1_correct": int(
                semantic_only == true_label
            ),
            "topk_covered": 1,
            "adaptive_choice": adaptive_choice,
            "adaptive_correct": int(
                adaptive_choice == true_label
            ),
            "shuffled_choice": shuffled_choice,
            "shuffled_correct": int(
                shuffled_choice == true_label
            ),
            "rescued_from_top1_error": int(
                semantic_only != true_label
                and adaptive_choice
                == true_label
            ),
            "shift_target": shift_target,
            "post_shift_adaptive_choice":
                post_shift_adaptive,
            "post_shift_frozen_choice":
                post_shift_frozen,
            "post_shift_adaptive_correct": int(
                post_shift_adaptive
                == shift_target
            ),
            "post_shift_frozen_correct": int(
                post_shift_frozen
                == shift_target
            ),
            "switch_episode": (
                first_switch
                if first_switch is not None
                else shift_episodes + 1
            ),
            "trust_snapshot": json.dumps(snap),
            "labels": json.dumps(labels),
            "probs": json.dumps(probs),
        })

    return pd.DataFrame(rows)


# =============================================================================
# Seed runner
# =============================================================================

def run_seed(
    seed: int,
    top_k: int = 3,
    train_repeats: int = 10,
    test_repeats: int = 10,
    epochs: int = 22,
):
    train_df, test_df = semantic_dataset(
        seed,
        train_repeats=train_repeats,
        test_repeats=test_repeats,
    )

    model = train_semantic_transformer(
        seed,
        train_df,
        epochs=epochs,
    )

    proposals = proposal_table(
        model,
        test_df,
        top_k=top_k,
    )

    semantic_top1 = float(
        proposals.top1_correct.mean()
    )
    topk_coverage = float(
        proposals.topk_contains_true.mean()
    )

    condition_rows = []
    summary_rows = []

    for noise in (0.0, 0.15, 0.30):
        detail = run_grounding_condition(
            proposals,
            seed=seed,
            noise=noise,
        )
        condition_rows.append(detail)

        covered = detail[
            detail.topk_covered == 1
        ]

        hard = covered[
            covered.top1_correct == 0
        ]

        summary_rows.append({
            "seed": seed,
            "noise": noise,

            "semantic_top1_accuracy":
                semantic_top1,
            "semantic_topk_coverage":
                topk_coverage,

            "adaptive_accuracy_all":
                float(
                    detail.adaptive_correct.mean()
                ),
            "adaptive_accuracy_covered":
                float(
                    covered.adaptive_correct.mean()
                ) if len(covered) else np.nan,

            "shuffled_trust_accuracy_covered":
                float(
                    covered.shuffled_correct.mean()
                ) if len(covered) else np.nan,

            "hard_case_count": int(
                len(hard)
            ),
            "hard_case_rescue_rate":
                float(
                    hard.rescued_from_top1_error.mean()
                ) if len(hard) else np.nan,

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
            condition_rows,
            ignore_index=True,
        ),
        proposals,
    )


def run_many(
    seeds: int = 4,
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
                "semantic_top1_accuracy",
                "semantic_topk_coverage",
                "adaptive_accuracy_all",
                "adaptive_accuracy_covered",
                "shuffled_trust_accuracy_covered",
                "hard_case_count",
                "hard_case_rescue_rate",
                "post_shift_adaptive_accuracy",
                "post_shift_frozen_accuracy",
                "median_switch_episode",
            ]].to_string(index=False)
        )

    return (
        pd.concat(summaries, ignore_index=True),
        pd.concat(details, ignore_index=True),
        pd.concat(proposals, ignore_index=True),
    )


def make_checks(summary: pd.DataFrame):
    checks = {}

    for noise in sorted(summary.noise.unique()):
        g = summary[
            summary.noise == noise
        ]

        tag = int(round(noise * 100))

        checks[
            f"noise{tag}_adaptive_beats_semantic_seed_fraction"
        ] = float(np.mean(
            g.adaptive_accuracy_all
            > g.semantic_top1_accuracy
        ))

        checks[
            f"noise{tag}_adaptive_beats_shuffled_seed_fraction"
        ] = float(np.mean(
            g.adaptive_accuracy_covered
            > g.shuffled_trust_accuracy_covered
        ))

        checks[
            f"noise{tag}_covered_accuracy_median"
        ] = float(np.median(
            g.adaptive_accuracy_covered
        ))

        checks[
            f"noise{tag}_hard_rescue_median"
        ] = float(np.nanmedian(
            g.hard_case_rescue_rate
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
            f"noise{tag}_switch_episode_median"
        ] = float(np.nanmedian(
            g.median_switch_episode
        ))

    checks[
        "semantic_topk_coverage_median"
    ] = float(np.median(
        summary.semantic_topk_coverage
    ))

    return checks


def main(argv=None):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seeds",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--train-repeats",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--test-repeats",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=30,
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
        OUT / f"{tag}_semantic_proposals.csv",
        index=False,
    )

    checks = make_checks(summary)

    (
        OUT / f"{tag}_checks.json"
    ).write_text(
        json.dumps(checks, indent=2)
    )

    med = summary.groupby(
        "noise"
    ).median(numeric_only=True)

    report = f"""Adrianic v5.0 — Semantic Proposal + Consequence Governance

Seeds: {args.seeds}
Semantic classes: {len(LABELS)}
Top-k proposals retained: {args.top_k}

Question
========
Can a transformer act as a semantic proposal generator rather than a semantic
oracle?

Architecture
============
A small TransformerEncoder sees normalized natural-language relation sentences
and returns a probability distribution over relation/direction hypotheses.

The Adrianic layer retains the top-k proposals.

Transformer confidence is treated as a proposal prior, not truth.

Each semantic hypothesis predicts an opaque downstream observation.
Forecast-vs-observation agreement updates consequence trust.

Decision score is a Bayesian-style combination:
- transformer proposal probability acts as a prior
- downstream consequence trust contributes empirical odds

This lets repeated prediction error overturn a confident semantic prior.

Controls
========
- transformer top-1 semantics alone
- shuffled consequence trust
- frozen trust after a grounding shift

Held-out semantics
==================
Training and test use different sentence orders/templates.
Entity names are abstracted into <e1>/<e2> identity slots so the test isolates
relation semantics rather than entity memorization.

Median metrics
==============
{med.to_string()}

Checks
======
{json.dumps(checks, indent=2)}

Grounding-shift boundary
========================
The shift test deliberately changes which retained semantic proposal receives
external support while the sentence and transformer probabilities remain fixed.

This models a synthetic context/convention shift.

It is NOT a claim that ordinary English relation meanings literally reverse.

Interpretation boundary
=======================
A positive result means the structural layer can rescue a plausible semantic
proposal that the transformer did not rank first, provided the correct proposal
remains in its retained candidate set and later consequences distinguish it.

It does not establish unrestricted semantic understanding or AGI.
"""

    (
        OUT / f"{tag}_REPORT.txt"
    ).write_text(report)

    print(report)


if __name__ == "__main__":
    main()
