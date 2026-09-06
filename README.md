# MANET Routing Protocols — Comparative Simulation Project

A comparative implementation and performance analysis of five progressively
enhanced routing protocols for Mobile Ad-hoc Networks (MANETs), tracing the
evolution:

**AODV (baseline) → EAURP → ATEAURP → PSE-EAURP → DRL-EAURP → MADRL-EAURP**

Each member independently implements, simulates, and documents one protocol
in the chain, using a shared node/network/metrics baseline so results are
directly comparable across all five.

## Team & Protocols

| Member | Protocol | Folder | Core idea |
|---|---|---|---|
| Member 1 | Baseline AODV & EAURP | `Member1_*` | Energy-aware trust filtering (PFR-based) over standard AODV |
| Member 2 | ATEAURP | [`Member2_ATEAURP/`](./Member2_ATEAURP) | Adaptive moving-average trust: `T(t+1) = 0.7·T(t) + 0.3·PFR` |
| Member 3 | PSE-EAURP | [`Member3_PSEEAURP/`](./Member3_PSEEAURP) | Predictive trust forecasting + PT_CREV controlled revocation |
| Member 4 | DRL-EAURP | `Member4_*` | Centralized Q-learning routing agent (exploit/explore) |
| Member 5 | MADRL-EAURP | [`Member5_MADRL_EAURP/`](./Member5_MADRL_EAURP_Final.zip) | Multi-agent CTDE (QMIX/VDN) with 2-hop gossip |

## Shared Simulation Baseline

Every member's `core/` implements the same agreed environment so results
are comparable:

- **Deployment area:** 1000 × 1000 m²
- **Node count:** 50 (default), scalable up to 500
- **Speed sweep:** 10–40 m/s
- **Connectivity:** Euclidean distance threshold, `d_ij ≤ R`
- **Metrics:** Packet Delivery Ratio (PDR), Average Delay (ms), Packet Loss, Throughput (kbps), Network Lifetime (rounds)

Each member's folder is self-contained (`core/`, `protocols/`,
`run_experiments.py`, `visualize.py`, `results/`) so it can be run
independently:
```bash
cd Member<N>_<PROTOCOL>/
pip install -r requirements.txt
python run_experiments.py
python visualize.py
```

---

## Member 2: ATEAURP

Adaptive Trust-Enhanced Energy-Aware Unicast Routing Protocol.

### Features
- Dynamic trust-based routing engine with malicious node isolation.
- Energy consumption & network lifetime tracking.
- Automated node speed sweep experiments (10 to 40 m/s).
- Metric visualization generation (PDR, Delay, Throughput, Lifetime).

### Project Structure
```text
Member2_ATEAURP/
├── core/               # Network, node, and metrics modules
├── protocols/          # ATEAURP routing and trust engine implementation
├── results/            # Exported metrics (CSV) and plots (PNG)
├── run_experiments.py  # Simulation CLI entry point
├── visualize.py        # Plot generation script
└── requirements.txt    # Project dependencies
```

---

## Member 3: PSE-EAURP

Predictive Secure Energy-Aware Unicast Routing Protocol — extends
ATEAURP's reactive trust with a **predictive** trust layer, so misbehaving
nodes are flagged and routed around *before* their trust fully collapses.

### Features
- 3-slot sliding trust history per node, combined into a weighted forecast:
  `T_pred = 0.5·T(t) + 0.3·T(t-1) + 0.2·T(t-2)`
- Cross-layer predictive routing probability:
  `P_success = min(0.4 + 0.35·T_pred_avg + 0.15·E_avg + 0.1·M_avg, 0.97)`
- `PT_CREV` controlled revocation: nodes with sustained low predicted trust
  are blacklisted and broadcast network-wide; routes through revoked nodes
  are torn down and rediscovered automatically.
- Full multi-hop routing simulation (relay retries, malicious drop
  modeling) driving PDR / delay / throughput / lifetime metrics.

### Results (50 nodes, 200 rounds, 10–40 m/s sweep)

| Speed (m/s) | PDR | Avg. Delay | Throughput |
|---|---|---|---|
| 10 | 87.5% | 74.4 ms | 143.3 kbps |
| 20 | 84.2% | 75.8 ms | 137.9 kbps |
| 30 | 81.2% | 78.3 ms | 133.0 kbps |
| 40 | 79.4% | 79.9 ms | 130.1 kbps |

Outperforms ATEAURP (Member 2) on both PDR and delay at every speed
tested, consistent with the predictive-trust layer catching misbehaving
nodes earlier than a plain moving average.

A separate comparison against the senior's original PSE-EAURP notebook
implementation is included in the project report — see the shared
findings document for the full write-up (throughput scale differs between
the two codebases due to differing packet-size/measurement-window
assumptions, flagged and explained there).

### Project Structure
```text
Member3_PSEEAURP/
├── core/                        # Shared network, node, and metrics modules
├── protocols/
│   ├── pse_eaurp_trust.py       # Predictive trust math (history buffer, forecast, revocation)
│   └── pse_eaurp_engine.py      # Full routing/simulation engine
├── results/                     # Exported metrics (CSV) and plots (PNG)
├── run_experiments.py           # Simulation CLI entry point
├── visualize.py                 # Plot generation script
└── requirements.txt             # Project dependencies
```