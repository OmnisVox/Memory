from __future__ import annotations

import ast
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "evidence" / "extracted" / "adrianic_v5_0_semantic_governance" / "8seed_semantic_proposals.csv"
OUT_CSV = ROOT / "logs" / "v50_oracle_control_source_exact.csv"
OUT_JSON = ROOT / "logs" / "v50_oracle_control_source_exact.json"
NOISE_LEVELS = (0.0, 0.15, 0.30)
LR = 0.18
EPISODES = 12
SHIFT_EPISODES = 12


def read_rows():
    by_seed = defaultdict(list)
    with PROPOSALS.open(newline="") as f:
        for row in csv.DictReader(f):
            row["seed"] = int(row["seed"])
            row["topk_labels"] = ast.literal_eval(row["topk_labels"])
            row["topk_probs"] = [float(x) for x in ast.literal_eval(row["topk_probs"])]
            by_seed[row["seed"]].append(row)
    return by_seed


def choose(labels, probs, trust):
    def score(i):
        t = min(1.0 - 1e-6, max(1e-6, trust[labels[i]]))
        return max(1e-12, probs[i]) * t / (1.0 - t)
    return labels[max(range(len(labels)), key=lambda i: (score(i), trust[labels[i]]))]


def evidence_label(rng, grounded, labels, noise):
    if rng.random() >= noise:
        return grounded
    alternatives = [x for x in labels if x != grounded]
    return rng.choice(alternatives) if alternatives else grounded


def update(trust, labels, observed_label):
    for label in labels:
        q = 1.0 if label == observed_label else 0.0
        trust[label] = (1.0 - LR) * trust[label] + LR * q


def run_seed(rows, seed, noise):
    rng = random.Random(seed + int(noise * 1000) + 50123)
    semantic_correct = []
    uniform_correct = []

    for row in rows:
        labels = list(row["topk_labels"])
        probs = list(row["topk_probs"])
        true_label = row["label"]
        if true_label not in labels:
            continue

        trust = {label: 0.5 for label in labels}
        for _ in range(EPISODES):
            observed = evidence_label(rng, true_label, labels, noise)
            update(trust, labels, observed)

        semantic_choice = choose(labels, probs, trust)
        uniform_choice = choose(labels, [1.0] * len(labels), trust)
        semantic_correct.append(semantic_choice == true_label)
        uniform_correct.append(uniform_choice == true_label)

        # Preserve the source script's RNG consumption. The post-shift phase shares the
        # same RNG before the next case is evaluated, even though those updates are not
        # needed for the prior-control score itself.
        alternatives = [x for x in labels if x != true_label]
        shift_target = alternatives[0] if alternatives else true_label
        for _ in range(SHIFT_EPISODES):
            evidence_label(rng, shift_target, labels, noise)

    n = len(semantic_correct)
    return {
        "seed": seed,
        "noise": noise,
        "covered_cases": n,
        "semantic_accuracy": sum(semantic_correct) / n,
        "uniform_accuracy": sum(uniform_correct) / n,
    }


def exact_all_same_sign_p(diffs):
    nonzero = [d for d in diffs if abs(d) > 1e-15]
    if not nonzero:
        return 1.0
    if all(d < 0 for d in nonzero) or all(d > 0 for d in nonzero):
        return min(1.0, 2.0 ** (1 - len(nonzero)))
    return None


def main():
    by_seed = read_rows()
    rows = []
    for seed in sorted(by_seed):
        for noise in NOISE_LEVELS:
            row = run_seed(by_seed[seed], seed, noise)
            row["difference"] = row["semantic_accuracy"] - row["uniform_accuracy"]
            rows.append(row)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

    summary = []
    for noise in NOISE_LEVELS:
        group = [r for r in rows if r["noise"] == noise]
        sem = sum(r["semantic_accuracy"] for r in group) / len(group)
        uni = sum(r["uniform_accuracy"] for r in group) / len(group)
        diffs = [r["difference"] for r in group]
        summary.append({
            "noise": noise,
            "semantic_seed_mean": sem,
            "uniform_seed_mean": uni,
            "difference_pp": 100.0 * (sem - uni),
            "semantic_wins": sum(d > 1e-15 for d in diffs),
            "ties": sum(abs(d) <= 1e-15 for d in diffs),
            "seeds": len(group),
            "exact_two_sided_p_when_all_nonzero_same_sign": exact_all_same_sign_p(diffs),
        })

    payload = {
        "purpose": "v5.0 no-retraining semantic-prior vs uniform-prior oracle control",
        "source": str(PROPOSALS.relative_to(ROOT)),
        "retraining": False,
        "rng_policy": "source-exact including post-shift RNG consumption",
        "summary": summary,
        "per_seed": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
