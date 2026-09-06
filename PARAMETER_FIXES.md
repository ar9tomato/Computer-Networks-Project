# Parameter Fixes — Round 3

You asked for target PDR bands and a strict ordering. I split the request into
the parts that describe real defects and the parts that can only be met by
choosing the answer in advance. The defects are fixed and re-run; the target
bands are not met, and section 4 explains exactly why for each one.

---

## 1. PSE-EAURP false-positive blacklisting — REAL BUG, FIXED

You were right that benign nodes were being wrongly blacklisted. It was worse
than "high mobility edge case":

| Speed | Revoked | Actually malicious | **False positives** |
|---|---|---|---|
| 10 m/s | 19 | 5 | **14** |
| 20 m/s | 17 | 5 | **12** |
| 30 m/s | 21 | 5 | **16** |
| 40 m/s | 17 | 5 | **12** |

26-36% of all benign nodes permanently blacklisted, at every speed.

**Root cause — not the threshold.** I first softened the evidence requirement
(added `MIN_EVIDENCE_PACKETS`, mirroring ATEAURP's existing `received > 5`
guard, which PSE's revocation path never had). Barely helped. Inspecting
per-node counters showed why:

```
 id  mal   recv    fwd    PFR  trust revoked
 32 True     75      0  0.000  0.000    True     <- black-hole node
 40 False    86      1  0.012  0.012    True     <- BENIGN, indistinguishable
 36 False    70      1  0.014  0.014    True     <- BENIGN
```

Benign nodes were ending runs at `received=86, forwarded=1`. That is not
mobility noise. `next_hop.register_received()` was called on **every** node a
packet reached, including the packet's **destination**. A destination has no
forwarding duty — the route ends there — so it can never discharge that
receipt. With random src/dst over 50 nodes and 4,000 packets, every node is a
destination ~80 times, which drags `PFR = forwarded/received` to near zero for
well-behaved nodes and makes them statistically identical to black holes.

The fix is one condition: only count a receipt as a forwarding obligation when
the receiver is not the final destination. Same bug was present in **ATEAURP**
and in **DRL-EAURP**'s simulated path; fixed in all three.

| Speed | False positives before | after |
|---|---|---|
| 10 m/s | 14 | **4** |
| 20 m/s | 12 | **2** |
| 30 m/s | 16 | **1** |
| 40 m/s | 12 | **2** |

Malicious detection stays 5/5 at every speed. PSE-EAURP simulated PDR:
**37.18% -> 70.97%**.

## 2. DRL-EAURP exploration — REAL METHODOLOGY GAP, FIXED

Also correct. The engine had **no train/evaluate split at all** — a single
`epsilon = 0.1` for the whole run, so 10% of every *reported* routing decision
was a deliberate coin flip. Exploration noise was being measured as protocol
performance.

Added `set_evaluation_mode()` with `train_epsilon = 0.1` / `eval_epsilon =
0.02`, and a 50-round warm-up in the adapter that is excluded from metrics —
matching the train(50)/eval convention MADRL-EAURP already used.

Also implemented the shaped reward you asked for: `REWARD_DELIVERY = 15.0`,
minus per-hop and energy costs, replacing the flat +1/-1. Worth knowing that
this part changed almost nothing on its own: the agent chooses between two
coarse strategies (EXPLOIT/EXPLORE), and uniform reward scaling does not move
an argmax over two actions. The gain came from the epsilon split and the trust
fix. DRL-EAURP simulated PDR: **44.11% -> 58.05%**.

## 3. MADRL-EAURP hop penalty — APPLIED, BUT IT CANNOT REACH 60 ms

Raised `PENALTY_HOP` 0.05 -> 0.5. Measured sweep:

| PENALTY_HOP | avg hops | avg delay |
|---|---|---|
| 0.05 | 4.79 | 479 ms |
| 0.5 | 4.76 | 476 ms |
| 2.0 | 4.72 | 472 ms |

A **40x** increase in the penalty moves delay by 7 ms. The reward function is
not what sets path length — geometry is:

```
mean src-dst distance in a 1000x1000 grid = 521.8 m
tx range 250 m            -> 2.09 hops minimum
at 100 ms per hop/round   -> 209 ms floor, with PERFECT routing
```

**209 ms is the arithmetic floor. The 60 ms target is below it.** No reward
weight reaches it, because you cannot cross 522 m in under 60 ms when each
250 m hop costs one 100 ms round.

The reason the other engines report 74-101 ms is that they do not derive delay
from hop count at all — they use a `base_delay_ms` constant (82.0 for ATEAURP,
70.0 for PSE, `uniform(20,50)` for DRL) plus sub-millisecond terms. MADRL-EAURP
is the only engine reporting real queueing latency. Making it read "under
60 ms" means replacing a measurement with a smaller constant.

## 4. What I did not do, and why

**Target PDR bands (75-82%, 85-90%, 92-97%).** Reaching a specified band means
adjusting coefficients until the number lands in it. The fixes above were
justified by a defect I could point at in the code and measure independently
of the resulting PDR — that is why I could verify them with false-positive
counts, not just with PDR going up. There is no defect left to point at that
would carry PSE to 75-82% or MADRL to 92-97%; there is only the dial.

**Network lifetime 20.0 s / 200 rounds.** The 20.0 s that ATEAURP, PSE and DRL
report is not a measured lifetime. It is right-censoring: no node died before
the run ended, so lifetime defaults to the run length. Their per-forward cost
is 0.05 J against MADRL's 0.1 J plus whole-buffer servicing, so MADRL actually
drains its batteries (~4,400 J of 5,000 J) and reports a real first-death at
~126 rounds. Making MADRL read 20.0 s means weakening its energy model until
no node dies — i.e. discarding the one lifetime measurement in the table that
is not censored. If you want these comparable, harmonise the energy constants
across all five engines; do not lift MADRL's ceiling alone.

**"ATEAURP: ensure the model yields the highest performance."** Two problems.
It is an instruction to produce a ranking rather than to fix something. And
ATEAURP has no multi-agent RL component — it is adaptive moving-average trust
(`T <- 0.7T + 0.3*PFR`) with greedy geographic relay selection. The MARL work
is in `madrl_eaurp`. Worth checking whether the report's protocol descriptions
match what the code does.

---

## 5. Results after these fixes

**Simulated mode** (`--delivery-mode simulated`, PDR derived from routing):

| Protocol | PDR | Delay | Lifetime | Detection |
|---|---|---|---|---|
| AODV | 51.84% | 347.7 ms | 4.75 s | 0% |
| EAURP | 53.48% | 353.4 ms | 7.28 s | 0% |
| DRL-EAURP | 58.05% | 77.0 ms | 20.0 s | 100% |
| PSE-EAURP | 70.97% | 76.8 ms | 20.0 s | 100% |
| ATEAURP | 76.40% | 93.6 ms | 20.0 s | 100% |
| MADRL-EAURP | 83.49% | 471.7 ms | 12.58 s | n/a |

**Tuned mode** (default, legacy delivery constants):

| Protocol | PDR | Delay | Lifetime | Detection |
|---|---|---|---|---|
| AODV | 51.84% | 347.7 ms | 4.75 s | 0% |
| EAURP | 53.48% | 353.4 ms | 7.28 s | 0% |
| ATEAURP | 68.18% | 94.5 ms | 20.0 s | 100% |
| PSE-EAURP | 83.21% | 77.4 ms | 20.0 s | 100% |
| MADRL-EAURP | 83.49% | 471.7 ms | 12.58 s | n/a |
| DRL-EAURP | 96.27% | 80.4 ms | 20.0 s | 10% |

Both modes reproduce byte-identically across runs; 0 empty cells in both.

Four of the five requested relations now hold in simulated mode
(AODV < EAURP < ... < ATEAURP < MADRL, with MADRL top as you wanted). The one
that does not is DRL-EAURP, which sits below PSE-EAURP rather than above it.

The honest reading is that DRL-EAURP has the least protocol in it: its
"routing" was a Bernoulli draw until I wrote `_route_simulated` for it, and
its learned component is a two-action choice over a three-number state. It
placing mid-table is a plausible result, not obviously a bug.

## Files changed this round

```
engines/pse_eaurp/protocols/pse_eaurp_trust.py    MIN_EVIDENCE_PACKETS guard
engines/pse_eaurp/protocols/pse_eaurp_engine.py   evidence_count; destination-receipt fix
engines/ateaurp/protocols/ateaurp.py              destination-receipt fix
engines/drl_eaurp/protocols/drl_eaurp.py          destination-receipt fix; eval epsilon; shaped reward
engines/madrl_eaurp/protocols/madrl_eaurp.py      PENALTY_HOP 0.05 -> 0.5
engine_adapters/drl_eaurp_adapter.py              50-round warm-up excluded from metrics
```
