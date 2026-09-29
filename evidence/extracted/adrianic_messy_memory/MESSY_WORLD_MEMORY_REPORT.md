# Adrianic Messy-World Memory Controller Study

## What was tested

The selective multi-slot memory system was pushed into less-clean streaming conditions:

- frequent useful memories,
- rare high-consequence memories,
- frequent low-value junk,
- one-off transient noise,
- delayed utility feedback,
- drifting representations,
- false reward / value poisoning,
- and a mid-run reversal of what is useful.

The controller remained glass-box. No opaque learned policy was used.

## Baseline messy stream

Across 40 seeds and 3,000 events per run:

Immediate storage captured about 0.676 of total downstream utility.
Recurrence-only storage captured about 0.777.
Value-aware selective storage captured about 0.848.

The value-aware controller made about 94 permanent writes per 3,000 events,
versus about 1,488 for immediate storage.

Rare-critical hit rate:
- immediate: about 0.537
- recurrence: about 0.847
- value-aware: about 0.937

Frequent-junk hit rate under value-aware storage fell to about 0.044.

So the controller was not merely remembering what happened often. It preferentially
preserved what was consequential.

## Delayed consequences

As downstream value feedback was delayed from tens to hundreds of events, performance
degraded gradually rather than collapsing. Increasing HOLD lifetime alone did not remove
the cost, because the memory is still unavailable while its value is unknown.

This supports a provisional memory tier that remains usable before permanent consolidation.

## Representation drift

A slow reconsolidation update was tested on stored address vectors. A moderate update rate
around 0.10 improved drifting-memory recall from about 0.782 to about 0.799 without a large
penalty to stable useful memories. Faster reconsolidation stopped helping.

This is consistent with the earlier result that memory updates should be slower than recall.

## False value / reward poisoning

False high-value feedback was deliberately injected into frequent junk.

This exposed a real weakness. At high poisoning rates, low-value memories can still compete
for permanent storage because the value signal itself is corrupted.

Reliability-aware utility estimation reduced write churn and some wrong recalls, but did not
fully solve the problem. If the source of utility information is untrustworthy, the memory
controller cannot infer truth from that signal alone.

## Utility reversal

Halfway through a run, previously useful memories were made low-value and previously low-value
memories became useful.

A lifetime-average utility estimate adapted too slowly.

Using a recent-value exponential moving estimate plus value-sensitive replacement improved
late post-change utility capture to about 0.881, compared with about 0.663 for the static
value-aware controller and about 0.630 for recurrence-only storage.

The adaptive-value controller ended with roughly 4.5 of the 5 newly useful memories stored,
all 3 rare-critical memories preserved on average, and essentially none of the now-low-value
old memories left in the bank.

## Main architectural result

The memory system now has several independently justified timescales:

1. fast recall,
2. slower learning,
3. provisional HOLD duration,
4. slower conditional reconsolidation,
5. recent-value adaptation.

A defensible current stack is:

experience
-> provisional HOLD
-> evidence accumulation
-> INCLUDE / EXCLUDE
-> multi-slot permanent memory
-> conditional reconsolidation
-> recent-value reprioritization

## Main remaining failure

The largest unresolved weakness is trust in the value signal.

The next memory-only extension should therefore track utility-source reliability, so one
corrupted feedback channel cannot permanently promote junk without corroboration.
