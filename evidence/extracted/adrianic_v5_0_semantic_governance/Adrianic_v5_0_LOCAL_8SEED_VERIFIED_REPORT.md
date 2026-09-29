# Adrianic v5.0 — Semantic Proposal + Consequence Governance

## Eight-seed local verification

This is the first direct bridge from a learned semantic transformer into the
Adrianic evidence/trust substrate.

The transformer is **not treated as an oracle**.

It sees natural-language relation sentences and emits a probability distribution
over eight relation/direction hypotheses:

- contains forward / reverse
- supports forward / reverse
- precedes forward / reverse
- maps forward / reverse

The Adrianic layer retains the top **five** semantic proposals.

Transformer probability acts as a semantic prior. Repeated downstream
forecast-vs-observation agreement contributes empirical consequence odds.

## Critical interface boundary

Entity identities are intentionally abstracted into `<e1>` and `<e2>` slots.

So this experiment isolates **relation semantics** and semantic uncertainty.

It does **not** yet test open-ended entity recognition/coreference from raw text.

## Held-out language

Training and test use different sentence arrangements/templates.

The semantic transformer therefore cannot solve the benchmark by memorizing the
exact evaluation strings.

## Eight-seed median metrics

```text
       seed  semantic_top1_accuracy  semantic_topk_coverage  adaptive_accuracy_all  adaptive_accuracy_covered  shuffled_trust_accuracy_covered  hard_case_count  hard_case_rescue_rate  post_shift_adaptive_accuracy  post_shift_frozen_accuracy  median_switch_episode
noise                                                                                                                                                                                                                                                                  
0.00    3.5                   0.275                  0.7875                 0.7500                   0.976303                         0.230769             38.5               0.962855                      0.954765                    0.023697                    2.0
0.15    3.5                   0.275                  0.7875                 0.6125                   0.815273                         0.292308             38.5               0.709722                      0.897950                    0.181107                    2.0
0.30    3.5                   0.275                  0.7875                 0.5250                   0.700000                         0.320513             38.5               0.492230                      0.863576                    0.284994                    2.0
```

## Pooled metrics

```text
 noise  cases  semantic_top1_accuracy  semantic_topk_coverage  adaptive_accuracy_all  adaptive_accuracy_covered  shuffled_trust_accuracy_covered  hard_case_count  hard_case_rescue_rate  post_shift_adaptive_accuracy  post_shift_frozen_accuracy  median_switch_episode
  0.00    640                0.260937                0.767188               0.740625                   0.965377                         0.232179              324               0.947531                      0.947047                    0.034623                    2.0
  0.15    640                0.260937                0.767188               0.598437                   0.780041                         0.287169              324               0.666667                      0.898167                    0.209776                    2.0
  0.30    640                0.260937                0.767188               0.509375                   0.663951                         0.301426              324               0.490741                      0.859470                    0.315682                    2.0
```

## The important result

The semantic transformer itself is currently weak on the held-out syntax:

- pooled top-1 semantic accuracy: **0.261**
- pooled top-5 proposal coverage: **0.767**

That is a feature of this test, not something hidden.

When the correct semantic hypothesis survives into the five retained proposals,
the consequence-governed layer reaches:

- **0.965** clean-anchor accuracy
- **0.780** at 15% consequence noise
- **0.664** at 30% consequence noise

Overall clean accuracy rises from transformer top-1 **0.261**
to governed semantic choice **0.741**.

The proposal ceiling is **0.767**, so the governed
system captures about **96.5%** of the available clean
top-k ceiling.

## Hard semantic errors

The most useful subset is where:

1. the transformer ranked the correct semantic parse below #1;
2. the correct parse still survived in top-k.

There are **324** such clean-anchor cases pooled across
the eight seeds.

The Adrianic consequence layer rescues **0.948** of
them.

That is the behavior we wanted:

> semantic confidence proposes; consequences are allowed to overrule it.

The shuffled-trust control only reaches
**0.232** on covered clean cases.

## Grounding-shift control

The sentence and transformer probabilities are frozen.

The environment then changes which retained semantic proposal is externally
supported. This is a synthetic context/convention shift, **not** a claim that
ordinary English meanings literally reverse.

After the shift:

- adaptive trust accuracy: **0.947** clean,
  **0.859** at 30% noise
- frozen trust accuracy: **0.035** clean,
  **0.316** at 30% noise
- median adaptive switch latency: **2.0** clean
  evidence episodes

## Checks

```json
{
  "noise0_adaptive_beats_semantic_seed_fraction": 1.0,
  "noise0_adaptive_beats_shuffled_seed_fraction": 1.0,
  "noise0_covered_accuracy_median": 0.9763026970411102,
  "noise0_hard_rescue_median": 0.9628552971576227,
  "noise0_post_shift_adaptive_median": 0.9547646383467279,
  "noise0_post_shift_frozen_median": 0.023697302958889763,
  "noise0_switch_episode_median": 2.0,
  "noise15_adaptive_beats_semantic_seed_fraction": 1.0,
  "noise15_adaptive_beats_shuffled_seed_fraction": 1.0,
  "noise15_covered_accuracy_median": 0.8152734778121775,
  "noise15_hard_rescue_median": 0.7097222222222221,
  "noise15_post_shift_adaptive_median": 0.8979500891265597,
  "noise15_post_shift_frozen_median": 0.18110661268556005,
  "noise15_switch_episode_median": 2.0,
  "noise30_adaptive_beats_semantic_seed_fraction": 1.0,
  "noise30_adaptive_beats_shuffled_seed_fraction": 1.0,
  "noise30_covered_accuracy_median": 0.7,
  "noise30_hard_rescue_median": 0.4922297297297298,
  "noise30_post_shift_adaptive_median": 0.8635759388501163,
  "noise30_post_shift_frozen_median": 0.28499369482976045,
  "noise30_switch_episode_median": 2.0,
  "semantic_topk_coverage_median": 0.7875
}
```

## What this supports

Within this controlled semantic benchmark:

1. A transformer can be used as a **proposal generator** rather than a truth source.
2. Retaining multiple plausible parses materially matters.
3. Downstream consequence evidence can rescue semantic hypotheses that the
   transformer did not rank first.
4. Shuffling consequence trust destroys most of the gain.
5. When grounding changes while semantic priors remain fixed, adaptive trust
   follows the new evidence and frozen trust does not.

## The failure we should care about

The bottleneck moved.

It is no longer primarily the arbitration layer.

The current tiny transformer only places the correct held-out parse in its top
five about **76.7%** of the time.

When the correct proposal is absent, the structural system cannot invent it.

So the next semantic target is extremely concrete:

> improve **proposal recall** without collapsing back into single-answer
> semantic confidence.

A stronger pretrained transformer should be tested primarily on whether it
raises top-k semantic recall while preserving calibrated uncertainty.

## Interpretation boundary

This is a synthetic relation-semantic interface test with a real learned
TransformerEncoder.

It does not establish unrestricted natural-language understanding, autonomous
ontology formation, or AGI.

But it demonstrates the architectural interface we needed:

> **semantic model proposes several meanings; Adrianic consequence governance
> decides which meaning earns belief.**
