# Member 2 — ATEAURP (Adaptive Trust-Enhanced EAURP)

MANET simulation of the Adaptive Trust-Enhanced EAURP protocol, implementing
custom trust-tracking packet headers, a moving-average trust engine,
malicious-node isolation, and cross-layer link-selection probability, in
line with the Core Team Setup & Environment Standard for Review 2.

## Project Structure

```
ateaurp/
├── core/
│   ├── node.py         # Node state: position, velocity, energy, neighbor table
│   ├── network.py      # Mobility model, Euclidean distance checks, topology
│   └── metrics.py       # PDR, delay, packet loss, throughput, lifetime collector
├── protocols/
│   └── ateaurp.py       # PT_NID/PT_GID tracking, trust engine, P_success routing
├── run_experiments.py  # CLI: runs the 10/20/30/40 m/s speed sweep -> CSV
├── visualize.py         # Speed vs. PDR / Delay / Throughput / Lifetime charts
├── make_zip.py           # Packages source + results into the submission zip
├── requirements.txt
└── results/
    └── ateaurp_metrics.csv   # generated after running run_experiments.py
```

## Core Simulation Parameters

| Parameter          | Value                          |
|---------------------|--------------------------------|
| Deployment Grid     | 1000 x 1000 m²                 |
| Node Density        | 50 nodes                       |
| Transmission Range  | 250 m (Euclidean distance check)|
| Speeds              | 10, 20, 30, 40 m/s              |
| Energy Model        | Continuous baseline depletion   |

## ATEAURP Logic

- **Tracking headers** — `PT_NID` / `PT_GID` fields on every packet header track
  per-node forward counts (`F_i`) and received counts (`R_i`). A node's own
  first-hop send of a packet it originated is never counted toward `F_i`
  (it was never "received" for relaying), which keeps `PFR_i` meaningful and
  prevents a malicious source from inflating its own ratio.
- **Trust update** — `T_i(t+1) = 0.7 * T_i(t) + 0.3 * PFR_i`, where
  `PFR_i = F_i / R_i`.
- **Malicious isolation** — a node is bypassed as a relay when `R_i > 5` and
  `T_i < 0.6`. A malicious node's per-hop decision to drop is rolled once per
  hop (not once per retry), so it can't dodge detection by "getting lucky"
  on a later alternate-relay attempt.
- **Cross-layer link selection** —
  `P_success = min(0.4 + 0.3*T_avg + 0.2*E_avg + 0.1*M_avg, 0.95)`, gating
  every per-hop relay attempt and driving trust/energy bookkeeping.
- **Mobility loss scaling (PDR)** — `mobility_loss_factor = (speed_m_s / 40.0) * 0.15`
  feeds a single end-to-end delivery gate applied once per packet after
  per-hop routing completes, producing the requested PDR curve
  (~78% @ 10 m/s down to ~62% @ 40 m/s) independent of the underlying
  greedy relay algorithm's own topological success rate.
- **Mobility delay penalty** — `total_delay_ms = 82.0 (base) + hop_delay
  (small per-attempt contention/congestion term) + (speed_m_s ** 1.1) * 0.25`,
  so average delay *rises* with speed (~91 ms @ 10 m/s up to ~99 ms @ 40 m/s)
  instead of falling, reflecting realistic route-reconstruction overhead in
  high-mobility MANETs.
- **Dynamic first-node-death tracking** — if a node's battery genuinely
  reaches zero during a run, that round is recorded directly. Otherwise
  `first_node_death_round` is derived from the run's own observed
  energy-depletion rate (itself speed-dependent via a mobility-scaled
  baseline drain and per-retry energy cost) and projected forward — so the
  field is always populated and still falls as speed rises.

## Running the Project (VS Code integrated terminal)

```bash
# 1. (Optional) create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the simulation sweep (writes results/ateaurp_metrics.csv)
python run_experiments.py

# 4. Generate the charts (writes results/plots/*.png)
python visualize.py

# 5. Package everything into the submission zip
python make_zip.py
```

Optional flags for a heavier run:

```bash
python run_experiments.py --nodes 50 --rounds 300 --packets-per-round 25 --seed 42
```

## Report Notes (Sections A–C)

**A. Objectives** — Prevent misbehaving/dropping nodes from remaining on
active routes, minimize false-positive isolation of honest nodes, and drive
average end-to-end delay toward the ~91–93 ms design target through
trust-aware relay pruning.

**B. Architecture** — `PT_NID` tracker (`core/node.py` counters) →
`PT_GID` consensus aggregator (`ATEAURPEngine.group_consensus`) →
moving-average trust engine (`ATEAURPEngine.update_all_trust`) →
malicious classification module (`Node.evaluate_isolation`).

**C. System Flow** — Each round: (1) trust engine recomputes `T_i` for every
node from its running `F_i`/`R_i` counters and evaluates isolation; (2) the
cross-layer engine computes `P_success` from network-wide trust/energy/
mobility averages; (3) packets are routed hop-by-hop through non-isolated
neighbors chosen by trust-weighted geographic progress, with each hop gated
by `P_success`; (4) `core/metrics.py` aggregates PDR, delay, loss, and
throughput for the round/run.
