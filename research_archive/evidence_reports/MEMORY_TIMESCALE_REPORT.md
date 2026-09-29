# Adrianic Memory Timescale & Interference Study

## Question
Does separating the learning and recall timescales improve a complex dynamical memory,
and can a transparent controller exploit that separation?

## Memory primitive
The tested phase-sensitive memory uses:

\[
\frac{\partial \chi}{\partial t}
=
D_\chi \nabla^2 \chi
+
L(t)\frac{\psi-\chi}{\tau_L}
\]

with recall feedback

\[
\left.\frac{\partial \psi}{\partial t}\right|_{\rm recall}
=
R(t)\,\mu_R(\chi-\psi).
\]

Here:
- \(\tau_L\) is the learning time constant.
- \(1/\mu_R\) is the approximate recall time constant.
- \(L(t)\) and \(R(t)\) are transparent learn/recall gates.

## 1. Continuous-rate separation
A grid sweep varied recall strength \(\mu_R\) and learning time constant \(\tau_L\).
The benchmark combines:
1. resistance to a short false/competing state, and
2. ability to learn a sustained legitimate state change.

The best tested continuous-rate regime was:

- \(\mu_R = 5\)
- \(\tau_L = 2\)

This corresponds to an approximate recall time constant

\[
\tau_R \approx \frac{1}{\mu_R} = 0.2,
\]

so learning is about **10× slower than recall**.

Top balanced score: **0.948763**.

## 2. Independent cadence separation
Recall and learning updates were then scheduled independently. Event increments were
time-normalized so cadence changes did not simply increase the mean integrated gain.

Best tested cadence:
- recall period: 0.008
- learning period: 0.192

So recall updated about **24× more frequently than learning**.

Balanced score:
- 24:1 fast-recall/slow-learning cadence: **0.974725**
- equal continuous cadence at the same rates: **0.948749**

In a 12-seed validation, the separated-cadence result had a minimum balanced score of
**0.974697**.

## 3. Timestep refinement
The advantage remained after halving the numerical timestep:

   dt        mode  retention_median  update_median  balanced_median
0.004       equal          0.969780       0.931417         0.950393
0.004 fastR_slowL          0.963580       0.973684         0.968612
0.008       equal          0.971898       0.926157         0.948751
0.008 fastR_slowL          0.976291       0.973159         0.974722

This reduces, but does not eliminate, the possibility that the effect is a timestep artifact.

## 4. No single static cadence is optimal for every failure mode
The corruption battery showed a stability/plasticity tradeoff.

A slow-learning regime is useful when the **active state** is suddenly unreliable, because
it prevents a transient disturbance from being written into memory.

A faster-learning / unrestricted regime is preferable when the **memory itself** is
corrupted, because the intact active state must rapidly re-teach the memory.

This means fixed timescale separation is useful, but **adaptive separation is better
motivated than one permanent ratio**.

## 5. Glass-box source-of-surprise controller
A transparent controller was built from three directly measurable quantities:

\[
S_\psi = 1-\operatorname{overlap}(\psi_{t^-},\psi_t)
\]

\[
S_\chi = 1-\operatorname{overlap}(\chi_{t^-},\chi_t)
\]

\[
E = 1-\operatorname{overlap}(\psi_t,\chi_t).
\]

Controller rules:

1. **Active-state surprise**:
   if \(S_\psi > S_\chi + 0.08\) and \(E>0.08\),
   freeze learning temporarily and recall from memory.

2. **Memory surprise**:
   if \(S_\chi > S_\psi + 0.08\) and \(E>0.08\),
   freeze recall and re-teach memory from the active state.

3. **Both channels changed**:
   use equal repair rather than allowing either one to dominate.

4. After triage, return to fast-recall / slow-learning cadence.

For memory damage, the write-only repair interval was tied to the learning time constant:

\[
T_{\rm repair}
=
\operatorname{clip}\left[
\tau_L(0.5+2S_\chi),\,1,\,5
\right].
\]

This is fully inspectable; no learned black-box policy is involved.

## 6. Held-out corruption results
Fresh held-out seeds produced:

          challenge    joint    state   memory  gate_time  joint_min  baseline    delta
active_random_phase 0.997490 0.995464 0.999517   0.600000   0.997476  0.994936 0.002554
     both_corrupted 0.744730 0.744681 0.744984   0.000000   0.723605  0.744730 0.000000
 brief_false_memory 0.997481 0.995453 0.999510   0.600000   0.997471  0.995181 0.002300
  memory_dropout_50 0.890052 0.878898 0.903237   2.170006   0.876639  0.767758 0.122293
 memory_phase_noise 0.801698 0.788834 0.813634   3.080402   0.783670  0.543152 0.258547
memory_random_phase 0.627426 0.620040 0.634840   4.866572   0.621986  0.091479 0.535948

The strongest improvements were when the stored memory itself was damaged:

- 50% memory dropout: **0.768 → 0.890**
- phase-noisy memory: **0.543 → 0.802**
- fully randomized memory phase: **0.091 → 0.627**

For simultaneous corruption of both active state and memory, the controller deliberately
falls back to the equal-repair mode, matching the static baseline rather than pretending
it knows which source is trustworthy.

## 7. Sequential endurance
A 24-event mixed-abuse sequence repeatedly corrupted active state and memory. Complete
memory-phase randomizations were deliberately inserted at events 8, 16 and 24.

At event 24:
- static continuous equal: median joint overlap ≈ **0.212**
- earlier hybrid controller: ≈ **0.370**
- severity-scaled controller: ≈ **0.519**

So adaptive gating substantially slows cumulative degradation, but **does not yet solve
repeated catastrophic memory destruction**.

## What is actually established by these numerical tests
1. Learning and recall benefit from distinct dynamical timescales in this model.
2. The best tested continuous regime made recall about 10× faster than learning.
3. Independently slowing learning updates relative to recall improved the stability/plasticity
   benchmark further; the best tested cadence used ~24 recall events per learning event.
4. The correct direction of timescale separation depends on which channel is damaged.
5. Explicit learn/recall gates dramatically improve recovery from memory corruption.
6. A fully glass-box controller can select these modes using only measured state changes.
7. Severe repeated corruption still causes cumulative loss, so the memory is not yet
   indefinitely self-healing.

## Important scope
These are computational experiments on a specific nonlinear complex-field model. They
demonstrate a functional memory/control mechanism inside that model; they do not establish
a biological mechanism, cognition, consciousness, or a universal physical law.
