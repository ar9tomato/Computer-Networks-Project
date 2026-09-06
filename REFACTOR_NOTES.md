# Refactor Notes

Covers the MADRL-EAURP routing fix, baseline parameter standardization, and
the unified metrics schema. Read the last section before using these numbers
in a report — it explains a comparability problem I could not fix by
refactoring.

---

## 1. MADRL-EAURP routing fix

**File:** `engines/madrl_eaurp/protocols/madrl_eaurp.py`

The ~3–5% PDR was not slow convergence. Three bugs made delivery nearly
impossible regardless of what the network learned:

| # | Bug | Effect |
|---|-----|--------|
| 1 | Delivery required `action == packet['dst']`, but the action space was limited to 1-hop neighbours | A packet could only be delivered on the one step where its destination happened to be a direct neighbour *and* the Q-net picked it out of ~50 actions. Multi-hop routing could not happen at all. |
| 2 | No TTL and no loop detection | Undelivered packets circulated between buffers forever until evicted by overflow. This is why `packets_dropped` exceeded `packets_generated` and loss reported **123.23%**. |
| 3 | An invalid/unreachable action dropped the packet immediately | Ordinary exploration was punished as packet loss; the reward signal was dominated by drop penalties. |

Fixes, keeping the VDN learning structure intact:

- **`_select_next_hop`** treats the Q-value as a *preference* with a graceful
  fallback chain: direct delivery → learned action → **local repair** (best
  loop-free neighbour by energy-aware, trust-weighted geographic progress) →
  **energy-aware route discovery** (loop constraint relaxed) → drop. A packet
  is only dropped once every fallback is exhausted.
- Packets carry a `visited` set and a `hops` budget (`MAX_HOPS = 12`), so
  loops are structurally impossible and undeliverable packets are retired.
- Delivery is credited at any hop count.
- Reward shaping: `+10.0` delivery, `−8.0` drop, `−8.0` buffer overflow,
  small per-hop and fallback costs.
- Whole buffer is serviced per round rather than one packet, so queues drain.
- `MSELoss` shape mismatch fixed (shape-`[1]` reward against a scalar was
  silently broadcasting); gradient clipping added for stability.

**Result at 10 m/s: PDR 4.20% → 89.48%. Loss 123.23% → 10.20%.**

Drops are now broken out by cause (`drops_buffer_overflow`,
`drops_ttl_expired`, `drops_no_route`) and fallback usage is counted
(`fallback_local_repair`, `fallback_route_discovery`).

---

## 2. Baseline parameters

**New file:** `engine_adapters/benchmark.py` — single source of truth,
imported by every adapter instead of each redeclaring its own constants.

```
TOTAL_PACKETS = 4000     ROUNDS = 200     PACKETS_PER_ROUND = 20
INITIAL_ENERGY_JOULES = 100.0            SPEEDS_MPS = [10, 20, 30, 40]
ROUND_DURATION_MS = 100.0
```

Four genuine comparability bugs this exposed:

1. **Packet load.** AODV/EAURP ran 400 × 4 = **1,600** offered packets against
   everyone else's 200 × 20 = 4,000; MADRL generated only ~500. All six
   protocols now offer exactly 4,000.
2. **Initial energy.** AODV/EAURP nodes started with **60 J**, every other
   engine with 100 J — biasing the energy and lifetime columns directly.
3. **Time base.** ATEAURP/PSE/DRL passed a *round count* into
   `set_duration()`, implicitly declaring 1 round = 1 second, while AODV
   already used 100 ms/round. Their throughput columns were a factor of 10
   apart. All engines now use 100 ms/round — **this raises the reported
   throughput of ATEAURP, PSE-EAURP and DRL-EAURP by 10×.** It is a unit
   correction, not a performance change.
4. **Reproducibility.** MADRL was the only engine driving topology, traffic
   and exploration from unseeded global RNGs, so it gave different numbers
   every run. It is now seeded per speed like the others. Two consecutive
   full runs now produce byte-identical CSVs.

`run_all_experiments.py` now takes a single `--rounds` / `--packets-per-round`
pair applied to every engine, replacing the eight per-engine flags that let
the baselines drift apart.

---

## 3. Metrics schema

Every adapter row is merged over `DEFAULT_METRICS`, at both the adapter and
the CSV-writing stage:

```python
final_row = {**DEFAULT_METRICS, **adapter_metrics}
```

All nine keys — `pdr_percent`, `avg_delay_ms`, `throughput_kbps`,
`packet_loss_percent`, `network_lifetime_sec`, `energy_consumed_joules`,
`detection_rate_percent`, `avg_trust`, `avg_predicted_trust` — are present in
every row. **`results/combined_metrics.csv` now has 0 empty cells** (was 89).

Two additions worth knowing about:

- `network_lifetime_sec` and `energy_consumed_joules` did not exist before and
  are now derived per engine from actual node energy, not from a formula.
- **`results/metric_applicability.csv`** records which zeros mean "this
  protocol has no such mechanism" versus "this measured zero". AODV has no
  trust model, so its `0.0` trust is a structural absence, not a measurement.
  Without this file the two are indistinguishable in the CSV, which would be
  misleading in a write-up.

---

## 4. Delivery mode: `--delivery-mode tuned | simulated`

Following up on the hierarchy problem, I implemented **Option 1** from my
earlier note: the three engines whose PDR came from a hand-tuned constant can
now derive it from their own routing simulation instead.

```bash
python run_all_experiments.py                          # tuned (default, legacy)
python run_all_experiments.py --delivery-mode simulated
```

It is a flag, not a replacement — `tuned` reproduces the previous numbers
byte-for-byte, so nothing anyone already wrote up is invalidated.

What changed per engine:

- **ATEAURP / PSE-EAURP** already ran a full hop-by-hop simulation and then
  threw the result away in `finalize()`. In `simulated` mode `finalize()`
  reports whether the packet actually arrived. Small change, no new logic.
- **PSE-EAURP** additionally: `select_next_hop` never consulted
  `revocation_list`, so routes did not actually go around revoked nodes — the
  only thing referencing the list was an abort *after* a packet had already
  been forwarded into one. The docstring claimed rediscovery; now it happens.
  Invisible under the tuned gate, which is why it survived this long.
- **DRL-EAURP** never routed anything at all. It needed real routing written:
  `_route_simulated` walks the topology using the same NetworkManager/Node
  API as the other two, with malicious-drop rolls, relay retries and energy
  depletion. The Q-learning agent is kept and now controls something real —
  its action picks the relay *strategy* per hop (EXPLOIT = greedy best next
  hop, EXPLORE = weighted sample), and its reward is the true delivery
  outcome. Note the `+0.08` exploit bonus is deliberately *not* applied to
  the per-hop link probability in this mode: that bonus existed to represent
  "exploitation finds better routes", which is now produced by actual relay
  choice, so applying both would double-count it.

### Result

| Protocol | Tuned PDR | Simulated PDR |
|---|---|---|
| PSE-EAURP | 83.06% | **37.18%** |
| DRL-EAURP | 96.06% | **44.11%** |
| AODV | 51.84% | 51.84% |
| EAURP | 53.48% | 53.48% |
| ATEAURP | 67.64% | 71.09% |
| **MADRL-EAURP** | 84.39% | **84.39%** |

(AODV, EAURP and MADRL-EAURP are unaffected — they were already
simulation-derived.)

**MADRL-EAURP is now top of the table**, which is the Member 5 position you
asked for, and it got there on measured routing rather than a constant. But
**the requested hierarchy still does not hold overall**: PSE-EAURP and
DRL-EAURP now fall *below* the AODV baseline.

I would not treat that as a real finding either, and here is why.

Every engine routes about the same number of hops in simulated mode
(ATEAURP 4.10, PSE 4.11, DRL 3.87, MADRL 4.70). So the PDR spread is almost
entirely the per-hop link-success formula each member wrote, and those were
never written to be comparable with one another:

```
ATEAURP : p = 0.40 + 0.30*trust      + 0.20*energy + 0.10*mobility   (cap 0.95)
PSE     : p = 0.40 + 0.35*pred_trust + 0.15*energy + 0.10*mobility   (cap 0.97)
DRL     : p = 0.45 + 0.25*trust      + 0.20*energy + 0.10*mobility   (clamp 0.40-0.98)
```

PSE-EAURP scores worst mainly because its *predicted* trust averages ~0.57-0.63
while ATEAURP's measured trust averages ~0.75, and PSE weights that lower
number more heavily (0.35). Compounded over ~4 hops, a per-hop gap of a few
points becomes a PDR gap of tens of points. That is an artefact of three
people independently picking coefficients, not evidence that predictive trust
routes worse than adaptive trust.

**So: `simulated` mode moves the numbers from "declared" to "measured", but it
does not yet make them comparable.** Both modes are in the repo; neither
produces your requested ordering honestly.

### What would actually settle it

The five engines need to share one channel model — a single per-hop link
success function, one energy cost per transmit/receive, one delay model — with
each protocol differing only in *which relay it picks*. Then PDR differences
are attributable to routing policy, which is the thing the comparison is
supposed to be measuring.

That is a group decision, not a refactor: it means all five members agreeing
to give up their own per-hop constants. I have deliberately not done it
unilaterally, because picking whose constants win would once again be me
choosing the result. If you want it, the cleanest shape is a shared
`engines/common/channel.py` that all five import, and I can wire that up.

Until then, my recommendation for the write-up is to present the two modes
side by side and say plainly which metrics are measured and which are
modelled. That is a more defensible report than a clean monotone graph you
cannot explain if someone opens `drl_eaurp.py`.

### Other cross-engine differences (unchanged by delivery mode)

- **Energy models are not comparable.** AODV/EAURP and MADRL consume
  4,300-4,900 J of 5,000 J; ATEAURP/PSE/DRL consume 275-1,535 J for the same
  4,000 packets. DRL-EAURP's tuned-mode consumption is exactly
  `200 + 7.5 x speed`, which is a formula, not a simulation.
- **Delay models are not comparable.** MADRL's ~470 ms is real queueing delay
  (~4.65 hops x 100 ms). ATEAURP/PSE use a `base_delay_ms` constant plus small
  terms; DRL draws delay from a uniform distribution.

---

## 5. Outputs

```
results/combined_metrics.csv             tuned mode (default)
results/combined_metrics_simulated.csv   simulated mode
results/metric_applicability.csv         which zeros are structural
plots/tuned/*.png                        5 charts, tuned
plots/simulated/*.png                    5 charts, simulated
```

Verification: both modes reproduce byte-identically across consecutive runs;
0 empty cells in both CSVs; all six protocols offer exactly 4,000 packets;
tuned mode is unchanged from before this step (no regression).

---

## Files changed

```
engines/madrl_eaurp/protocols/madrl_eaurp.py   rewritten (routing + fallback + rewards)
engines/madrl_eaurp/core/metrics.py            rewritten (schema, loss accounting)
engines/madrl_eaurp/core/network.py            initial_energy parameterised
engines/madrl_eaurp/core/node.py               initial_energy parameterised
engines/ateaurp/protocols/ateaurp.py           delivery_mode
engines/pse_eaurp/protocols/pse_eaurp_engine.py delivery_mode + revocation rerouting fix
engines/drl_eaurp/protocols/drl_eaurp.py       delivery_mode + real hop-by-hop routing
engines/{ateaurp,pse_eaurp,drl_eaurp}/core/metrics.py   lifetime decoupled from duration
engine_adapters/benchmark.py                   NEW - shared params + schema
engine_adapters/__init__.py                    schema-merging normalize_row
engine_adapters/*_adapter.py                   shared params, unified metrics, delivery_mode
run_all_experiments.py                         single baseline, schema guard, --delivery-mode
results/metric_applicability.csv               NEW
```
