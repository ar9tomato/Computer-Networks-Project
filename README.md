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
| Member 1 | Baseline AODV & EAURP | [`Member1_AODV_EAURP/`](./Member1_AODV_EAURP/) | Energy-aware trust filtering (PFR-based) over standard AODV |
| Member 2 | ATEAURP | [`Member2_ATEAURP/`](./Member2_ATEAURP) | Adaptive moving-average trust: `T(t+1) = 0.7·T(t) + 0.3·PFR` |
| Member 3 | PSE-EAURP | [`Member3_PSEEAURP/`](./Member3_PSEEAURP) | Predictive trust forecasting + PT_CREV controlled revocation |
| Member 4 | DRL-EAURP | [`Member4_DRL_EAURP/`](./Member4_DRL_EAURP/) | Centralized Q-learning routing agent (exploit/explore) |
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

---

## Member 4: DRL-EAURP

Deep Reinforcement Learning-based Energy-Aware Unicast Routing Protocol.

DRL-EAURP extends the EAURP approach by introducing a centralized
Q-learning-based routing agent that learns routing decisions through
exploration and exploitation. The agent considers network trust, residual
energy, and mobility conditions to improve routing reliability and
energy efficiency in dynamic MANET environments.

### Features
- Centralized Q-learning-based routing agent for adaptive route selection.
- Exploitation of learned routing decisions and exploration of alternative
  routing choices.
- Trust-aware and energy-aware routing decisions.
- Network state representation using average trust, normalized residual
  energy, and node mobility.
- Reward-based learning from successful packet delivery and packet loss.
- Malicious-node detection and isolation during routing.
- Multi-hop MANET routing with packet forwarding and relay behavior.
- Automated node-speed sweep experiments from 10 to 40 m/s.
- Energy consumption and network lifetime tracking.
- Performance evaluation using PDR, packet loss, average delay,
  throughput, and network lifetime.
- Automatic CSV metric export and performance plot generation.

### DRL Routing Model

The centralized Q-learning agent observes the current network state using
trust, energy, and mobility information:

`State = <T_avg, E_avg, M_avg>`

where:

- `T_avg` = average trust of the network nodes
- `E_avg` = normalized average residual energy
- `M_avg` = mobility-related network condition

The agent selects between exploration and exploitation to adapt its routing
behaviour to changing network conditions. Successful packet delivery
provides a positive reward, while packet loss provides a negative reward,
allowing the Q-table to gradually learn better routing decisions.

### Results

The DRL-EAURP implementation was evaluated using the shared MANET
simulation baseline with **50 nodes**, a **1000 × 1000 m²** deployment
area, and **200 simulation rounds** for each node-speed configuration.

| Speed (m/s) | PDR | Packet Loss | Avg. Delay (ms) | Throughput (kbps) | Network Lifetime (rounds) |
|---:|---:|---:|---:|---:|---:|
| 10 | 97.975% | 81 | 80.097 | 160.522 | 200 |
| 20 | 97.800% | 88 | 81.157 | 160.236 | 200 |
| 30 | 96.200% | 152 | 80.266 | 157.614 | 200 |
| 40 | 92.275% | 309 | 81.186 | 151.183 | 200 |

The results show that DRL-EAURP maintains a high Packet Delivery Ratio
under increasing node mobility. PDR decreases from **97.975% at 10 m/s**
to **92.275% at 40 m/s**, while throughput decreases from **160.522 kbps**
to **151.183 kbps**. Average delay remains relatively stable at around
**80–81 ms** across the tested mobility range.

The network lifetime remains at **200 rounds** for all tested speeds,
indicating that the network remained operational throughout the configured
simulation period.

### Project Structure

```text
Member4_DRL_EAURP/
├── core/
│   ├── __init__.py
│   ├── node.py              # Node and mobility model
│   ├── network.py           # MANET topology and connectivity
│   └── metrics.py           # PDR, delay, loss, throughput and lifetime
├── protocols/
│   ├── __init__.py
│   └── drl_eaurp.py         # DRL-EAURP routing and Q-learning engine
├── results/                 # Exported CSV metrics and generated plots
├── run_experiments.py       # Simulation and speed-sweep entry point
├── visualize.py             # Performance plot generation
└── requirements.txt         # Project dependencies