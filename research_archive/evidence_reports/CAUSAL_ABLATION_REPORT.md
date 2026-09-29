# Causal Ablation Ledger for Verification → Memory

## Purpose
This benchmark asks a narrow question: **when an imperfect verification anchor is corrected, where does that information go in the memory controller?**

Every verification event is cloned into two controller states from the exact same pre-event state:

1. raw-anchor branch,
2. corrected-anchor branch.

Both branches then receive the exact same next 50 events and source reports. The ledger records differences in source trust, immediate slot state, later decisions, write counts, final slot contents, and captured downstream utility.

This is a structural controller benchmark, not a full nonlinear-field simulation.

## Aggregate results

                                             metric       value
                            all verification events 2100.000000
                                  corrupted anchors  388.000000
                          anchors changed by filter  324.000000
                          mean raw anchor abs error    0.380074
                    mean corrected anchor abs error    0.073165
                           mean trust path distance    0.015806
               fraction immediate slot paths differ    0.046190
                     fraction end slot paths differ    0.053333
                  fraction future decisions diverge    0.116190
                         mean horizon utility delta    0.093376
    mean horizon utility delta on corrupted anchors    0.512729
fraction corrected path better on corrupted anchors    0.332474
 fraction corrected path worse on corrupted anchors    0.157216

## Causal propagation funnel

                       stage  fraction_events
            anchor corrected         0.154286
         trust state changed         0.154286
immediate slot state changed         0.046190
future decision path changed         0.116190
  50-step slot state changed         0.053333
     50-step utility changed         0.092381

The important result is that anchor correction almost always changes the **trust state**, but only a subset of those changes survive all the way into a different permanent-memory state or a measurable 50-step utility difference.

That localizes the bottleneck: the information is usually **not lost at verification**. It is compressed or cancelled later by commit thresholds, replacement logic, repeated subsequent evidence, and finite-slot competition.

## Corrupted-anchor counterfactuals

On genuinely corrupted anchors, the corrected branch had higher 50-step utility in about **33.2%** of cases and lower utility in about **15.7%**.

Mean corrected-minus-raw horizon utility on corrupted anchors was **0.5127**.

That means correcting an anchor is directionally useful on average, but **not sufficient to guarantee a locally better memory outcome**. A corrected value can still change which slot is written or replaced in a way that loses future utility.

## Why the sign can flip

The ledger exposes several mechanisms:

- a corrected anchor changes source trust but never crosses a commit threshold;
- both branches eventually receive enough later evidence to reconverge;
- a corrected anchor commits a moderately useful memory earlier and displaces a more useful slot;
- a bad raw anchor occasionally suppresses writes, accidentally acting as a crude regularizer;
- finite-capacity replacement converts a locally better value estimate into a globally worse storage choice.

So the earlier paradox is explained: **verification quality and storage quality are separated by a resource-allocation problem.**

## Most important architectural implication

The commit controller should not ask only:

> Is this candidate valuable enough to store?

When the bank is full, it must ask the comparative question:

> Is this candidate's expected future utility greater than the expected future utility of the slot I would destroy?

A stronger replacement rule is therefore:

V_replace = E[U_candidate] - E[U_evicted] - interference_cost.

Only replace when V_replace > margin.

That is the cleanest next improvement suggested by this causal ledger.

## 12. Follow-up: comparative replacement gate

The causal ledger suggested that locally improved verification could still cause globally worse memory because a newly committed candidate could evict a more valuable existing slot.

A replacement gate was therefore added. Once the bank is full, a candidate is not allowed to replace the weakest slot merely because it passes the ordinary commit threshold. Instead a transparent candidate-future-value proxy is compared with the weakest retained-slot value, and replacement is allowed only when the difference exceeds a margin.

A sweep over replacement margins gave:

| margin | utility capture | writes | replacements | junk slots |
|---:|---:|---:|---:|---:|
| automatic replacement | 0.8266 | 67.63 | 59.63 | 0.125 |
| 0.00 | 0.8388 | 23.13 | 15.13 | 0.042 |
| 0.08 | 0.8441 | 17.71 | 9.71 | 0.000 |
| 0.16 | **0.8471** | 13.42 | 5.42 | 0.042 |
| 0.28 | 0.8462 | 11.75 | 3.75 | 0.042 |

The best tested margin was 0.16. Against automatic replacement on the same 24 seeds, it improved utility capture by about **0.0205 absolute on average**, with a median improvement of **0.0212**, and improved 79.2% of paired seeds. The 5th-percentile paired difference was still negative, so the gate is not universally superior in every run.

This validates the causal-ledger diagnosis: part of the verification-to-memory bottleneck was finite-capacity replacement, not verification itself.

The resulting separation is now:

1. Is the candidate sufficiently supported to be considered for storage?
2. If there is free capacity, include it.
3. If capacity is full, compare candidate future value with the value of the slot that would be destroyed.
4. Replace only if the comparative margin is positive enough.

This makes storage a resource-allocation decision instead of an absolute threshold decision.
