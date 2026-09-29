# Adrianic v3.16 — Behavioral Consolidation and Fault-Tolerant Memory

## Goal

Move beyond "reconstruct the damaged field."

The system now receives a transient context cue and must continue selecting the
correct control action after the cue disappears.  The score is task reward and
action accuracy.

## Seven persistent roles

1. active field
2. working memory
3. consolidated bank A
4. consolidated bank B
5. confidence / source trust
6. parity P
7. parity Q

Derivative, prediction and phase-velocity quantities are computed transiently
rather than occupying permanent memory slots.

## Adaptive consolidation

A working state is committed only if:
- confidence is high;
- recent reward is high and stable;
- context has stabilized;
- the candidate is novel relative to stored banks;
- enough time has passed since the last checkpoint.

A/B are overwritten one at a time.  Parity is re-encoded after an accepted
checkpoint.

## Behavioral tests

- delayed action after the sensory cue disappears;
- transient distractor episodes that should not be consolidated;
- mid-run corruption of one consolidated bank;
- comparison against periodic consolidation, working-memory-only, and
  no-memory controls;
- a remapped sensor convention with the same frozen memory/consolidation
  parameters.

This remains an engineered computational task, not evidence of cognition or
consciousness.


## Hard behavioral stress test

A second task makes durable consolidation necessary.

Each long block has one true hidden context.  Mid-block, the system receives a
brief opposite-sign false cue, but the correct behavior does not change.
Working memory is then erased.  The agent must recover the original behavior
from consolidated memory.  Later, one consolidated bank is corrupted.

Comparisons:
- adaptive consolidation + parity;
- adaptive consolidation without parity;
- periodic consolidation + parity;
- working memory only;
- no memory.

This directly tests resistance to transient misinformation, recovery from
working-memory interference, and behavioral robustness after durable-memory
damage.


## Corrected hard-control test

The working-only control is now prohibited from writing or reading consolidated
banks.

Later in the task, **both** consolidated banks are corrupted while parity
channels remain intact. Repeated working-memory wipes then force the system to
use durable storage. This makes parity behaviorally consequential rather than
merely a reconstruction demonstration.

A bad-consolidation metric also records whether a committed checkpoint encodes
the wrong task action after misleading transient cues.


## Cold-start parity behavior probe

After a long stable-context training period:

1. erase working memory and cue belief;
2. randomize the last volatile action;
3. corrupt both consolidated data banks A and B;
4. preserve parity P and Q;
5. remove the sensory cue;
6. freeze further consolidation;
7. score behavior, not reconstruction.

This isolates whether parity-protected durable memory can restore the correct
task policy after volatile and primary durable memory are simultaneously lost.
