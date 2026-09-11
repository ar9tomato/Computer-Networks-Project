# Computer Networks Project - Unified Experiment Pipeline

Run it:

```bash
python run_all_experiments.py                           # tuned mode (default)
python run_all_experiments.py --delivery-mode simulated  # PDR derived from routing
python visualize_all.py --output-dir plots/tuned
python visualize_all.py --input results/combined_metrics_simulated.csv \
                        --output-dir plots/simulated

# node-count scaling sweep, fixed speed, density-matched grid
python node_scaling_experiment.py --delivery-mode simulated
```

Baseline for every protocol: 4,000 packets, 100 J/node, speeds [10, 20, 30, 40]
m/s, 100 ms/round. Both delivery modes reproduce byte-identically across runs.

Read the "what I did not tune" section of `PARAMETER_FIXES.md` before using
these numbers in a write-up. Several columns are modelled rather than
measured, and they aren't all comparable across engines.

Consolidated MANET routing-protocol comparison across all five members'
protocols: AODV, EAURP, ATEAURP, PSE-EAURP, DRL-EAURP, and MADRL-EAURP. Each
member folder used to have its own duplicated `run_experiments.py` +
`visualize.py`. This refactor replaces all of them with one root-level
runner and one root-level visualizer that produce a single consolidated
results file and one set of comparative charts covering every protocol.

## Folder structure

```
Computer-Networks-Project/
├── engines/                      # protocol implementations, one per member
│   ├── aodv_eaurp/                # Member1_AODV_EAURP_Review2 -> AODVEngine, EAURPEngine
│   ├── ateaurp/                   # Member2_ATEAURP           -> ATEAURPEngine
│   ├── pse_eaurp/                 # Member3_PSEEAURP          -> PSEEAURPEngine
│   ├── drl_eaurp/                 # Member_4_DRL_EAURP        -> DRLEAURPEngine
│   └── madrl_eaurp/               # Member5_MADRL_EAURP       -> MADRLEAURP (torch-based)
│       each with its own core/ (Network, Node, MetricsCollector)
│       and protocols/ (the routing engine itself)
├── engine_adapters/               # the glue that makes one pipeline possible
│   ├── __init__.py                # isolated import helper + common row schema
│   ├── benchmark.py               # shared baseline params + unified metric schema
│   ├── aodv_eaurp_adapter.py       # runs AODV + EAURP
│   ├── ateaurp_adapter.py          # runs ATEAURP
│   ├── pse_eaurp_adapter.py        # runs PSE-EAURP
│   ├── drl_eaurp_adapter.py        # runs DRL-EAURP
│   └── madrl_eaurp_adapter.py      # runs MADRL-EAURP
├── run_all_experiments.py         # root runner, speed sweep, all 6 protocols
├── node_scaling_experiment.py     # root runner, node-count sweep, all 6 protocols
├── visualize_all.py                # root visualizer (all 6 on one chart)
├── results/
│   ├── combined_metrics.csv            # generated - tuned mode, speed sweep
│   ├── combined_metrics_simulated.csv  # generated - simulated mode, speed sweep
│   ├── node_scaling_metrics.csv        # generated - node-count sweep
│   └── metric_applicability.csv        # which 0.0 values are structural
├── plots/
│   ├── tuned/           *.png          # generated (5 charts)
│   ├── simulated/       *.png          # generated (5 charts)
│   └── node_scaling/    *.png          # generated (PDR/delay vs. node count)
├── REFACTOR_NOTES.md
├── PARAMETER_FIXES.md
└── requirements.txt
```

Every member's `run_experiments.py` and `visualize.py` are removed. Their
logic now lives in `engine_adapters/` and the two root scripts.

## Why there's an `engine_adapters/` layer instead of one merged `core/`

The five members' protocol code was written independently and isn't
API-compatible across the board:

| Engine family | Network class | Node "alive" check | Per-packet call |
|---|---|---|---|
| `aodv_eaurp` (M1) | `Network` | `node.alive` | `engine.send_packet(src, dst, metrics, round)`, mutates a shared `MetricsCollector` |
| `ateaurp` / `pse_eaurp` / `drl_eaurp` (M2/M3/M4) | `NetworkManager` | `node.is_alive` (property) | `engine.route_packet(src, dst, round)` -> `(delivered, delay_ms, hop_count)` |
| `madrl_eaurp` (M5) | `MANETNetwork` | `node.is_alive()` (method) | `engine.step_environment(training=...)`, a full train/eval RL loop, no single-packet call at all |

M2/M3/M4 actually share an identical `core/` (byte-for-byte for
`node.py`/`metrics.py`; only `network.py`'s docstring differs). Only their
engine classes (`ATEAURPEngine`, `PSEEAURPEngine`, `DRLEAURPEngine`) differ,
each with a different constructor and per-round trust-update contract. M5
shares nothing with the other four: it's a torch-based multi-agent DRL
router with its own network/metrics classes and an explicit
train-then-evaluate loop instead of a speed-sweep loop.

Merging all of this into one `Network`/`Node`/`Engine` class would mean
rewriting and re-validating five different simulation cores, which is out
of scope for a structural refactor and risky to correctness. Instead:

- Each engine's `core/` and `protocols/` package stays intact under
  `engines/<name>/` (aside from the documented fixes below), not silently
  rewritten to match the others.
- Several engines' packages are still named `core` and `protocols`
  internally (their own files still do `from core.network import Network`,
  etc.), so `engine_adapters/__init__.py`'s `_isolated_import()` helper
  loads each engine's `core`/`protocols` from its own directory and clears
  `sys.modules` between engines, so same-named packages never collide.
- Each adapter (`aodv_eaurp_adapter.py`, `ateaurp_adapter.py`,
  `pse_eaurp_adapter.py`, `drl_eaurp_adapter.py`, `madrl_eaurp_adapter.py`)
  reproduces that member's original experiment loop, then converts its
  output into one common row schema (`protocol`, `speed_mps`,
  `pdr_percent`, `avg_delay_ms`, `packet_loss_percent`, `throughput_kbps`,
  `network_lifetime_rounds`, plus whatever protocol-specific extra columns
  it has, e.g. `detection_rate_percent`, `avg_trust`,
  `total_pt_crev_broadcasts`, `gossip_messages`).

`run_all_experiments.py`, `node_scaling_experiment.py`, and
`visualize_all.py` only ever talk to that common schema. They don't know
or care that `AODVEngine` and `MADRLEAURP` work completely differently
internally.

### Two bugs fixed in Member5's original script (not a redesign)

`madrl_eaurp_adapter.py`'s docstring documents this in full, but in short,
Member5's original `run_experiments.py`:

1. Called `np.random.uniform(...)` without ever importing `numpy`, which
   would crash immediately. The adapter imports it itself.
2. Computed "lifetime" as `1000 - (speed * 5.5) + noise`, a formula with no
   connection to the simulated nodes' actual energy at all. The adapter
   instead derives `network_lifetime_rounds` from each node's real
   observed energy depletion (first real death within the run, or an
   estimate from the observed depletion rate), the same convention
   `ateaurp`/`pse_eaurp`/`drl_eaurp`'s own `estimate_first_node_death_round`
   already uses.

## `engines/madrl_eaurp` fixes: routing correctness, then scalability

The original MADRL-EAURP reported 3-5% PDR. That wasn't slow convergence,
it was three routing bugs that made delivery almost impossible regardless
of what the network learned (an action space limited to 1-hop neighbours
compared with `action == dst` directly, no TTL or loop detection, and
invalid actions counted as drops with no fallback). `protocols/madrl_eaurp.py`
documents the fixes: graceful fallback through local repair and route
discovery, a hop budget with loop-free packet state, and delivery credited
whenever a packet actually arrives.

A second, separate pass fixed how MADRL-EAURP scales with network size:

- **State/action space was O(num_nodes).** The Q-network indexed directly
  into every global node ID (`state_dim = 2 + N`, `action_dim = N`), so at
  400 nodes it had to learn a 402-dimensional, mostly-padding state mapped
  to a 1-of-400 decision from the same 50 warm-up rounds used at 50 nodes.
  It now ranks each node's 1-hop neighbours into a fixed top-8 candidate
  shortlist and reasons over "prefer my best-ranked candidate / defer to
  the fallback heuristic" instead, a state/action space of fixed size
  regardless of `num_nodes`.
- **TTL wasn't derived from the topology.** The packet hop budget was a
  flat `MAX_HOPS = 12`, about half of what ATEAURP/PSE-EAURP/DRL-EAURP use
  (`25`), with no connection to grid size. It's now computed from the
  network's own diagonal and transmission range, using the same safety
  margin the other three engines' fixed `25` implies at their baseline
  1000m grid, so it scales sensibly as the grid does.
- **Train/eval buffer leak.** Packets still in flight at the end of the
  training warm-up were carrying over into evaluation and getting counted
  as delivered without a matching "sent" in eval's metrics, which could
  push PDR above 100% once routing got efficient enough to surface it.
  Node buffers are now cleared at the train/eval boundary, the same
  clean-slate convention every other engine already follows.

None of this touches the reward function, the gossip/trust mechanics, or
the fallback routing logic; it only changes what the Q-network's inputs
and outputs represent.

## `node_scaling_experiment.py`

`run_all_experiments.py` sweeps speed at a fixed 50 nodes.
`node_scaling_experiment.py` instead sweeps node count (default 50 / 100 /
200 / 400) at a fixed speed, so you can see how each protocol holds up as
the network grows. To make that a fair comparison, the deployment grid is
scaled with node count so average node density (and average neighbour
count) stays constant across the sweep; otherwise more nodes on a fixed
grid just means a denser network, which flatters every protocol for a
reason that has nothing to do with how well it coordinates a larger
population. See `density_matched_grid()` in `engine_adapters/benchmark.py`.

```bash
python node_scaling_experiment.py                                  # default sweep, tuned mode
python node_scaling_experiment.py --delivery-mode simulated        # PDR derived from routing
python node_scaling_experiment.py --node-counts 50 100 200 400 800
python node_scaling_experiment.py --skip madrl_eaurp                # torch not installed
```

Writes `results/node_scaling_metrics.csv`, one row per `(protocol,
num_nodes)` pair.

## `__init__.py` / import notes

- No changes were needed inside any `engines/<name>/` package. Their
  `core/__init__.py` and `protocols/__init__.py` are untouched, and their
  internal files keep using `from core.network import ...` /
  `from protocols.<x> import ...` exactly as before.
- The only new import machinery is `engine_adapters/__init__.py`'s
  `_isolated_import(engine_dir_name, module_path)`, which:
  1. removes any previously loaded `core.*` / `protocols.*` modules from
     `sys.modules`,
  2. puts `engines/<engine_dir_name>/` at the front of `sys.path` (and
     removes every other engine's directory from `sys.path`),
  3. imports and returns the requested module fresh from that directory.
- To add a sixth engine later: drop it under `engines/<name>/` with its own
  `core/`/`protocols/` packages, write one adapter module that calls
  `_isolated_import("<name>", "...")` and returns `normalize_row(...)`
  rows, add it to the `ADAPTERS` dict in `run_all_experiments.py` (and
  `node_scaling_experiment.py` if it should be part of the scaling sweep
  too), and optionally give it a style entry in `visualize_all.py`'s
  `PROTOCOL_STYLES`.

## Usage

```bash
pip install -r requirements.txt

# Run all six protocols across the standard speed sweep (10/20/30/40 m/s)
python run_all_experiments.py

# Optional: customize the sweep or round counts per engine
python run_all_experiments.py --speeds 10 20 30 40 \
    --aodv-eaurp-rounds 400 --aodv-eaurp-packets-per-round 4 \
    --ateaurp-rounds 200 --ateaurp-packets-per-round 20 \
    --pse-eaurp-rounds 200 --pse-eaurp-packets-per-round 20 \
    --drl-eaurp-rounds 200 --drl-eaurp-packets-per-round 20

# Skip an engine (e.g. if torch isn't installed for MADRL-EAURP)
python run_all_experiments.py --skip madrl_eaurp

# Node-count scaling sweep instead of the speed sweep
python node_scaling_experiment.py --delivery-mode simulated

# Plot every protocol present in the results on the same comparative charts
python visualize_all.py
```

`run_all_experiments.py` writes `results/combined_metrics.csv` with one row
per `(protocol, speed)` pair across all engines that ran.
`node_scaling_experiment.py` writes `results/node_scaling_metrics.csv` with
one row per `(protocol, num_nodes)` pair instead. `visualize_all.py` reads
the speed-sweep file and writes one PNG per metric under `plots/`, with
every protocol present plotted together using a fixed, distinct
color/marker/line-style per protocol and a legend.

## Metrics compared

- Packet Delivery Ratio (%)
- Average Delay (ms)
- Packet Loss (%)
- Throughput (kbps)
- Network Lifetime (rounds)

Each protocol may also report extra columns in `combined_metrics.csv` (e.g.
ATEAURP/PSE-EAURP/DRL-EAURP's `avg_trust`, `detection_rate_percent`;
PSE-EAURP's `total_pt_crev_broadcasts`; MADRL-EAURP's `gossip_messages`)
that aren't part of the shared comparison charts but remain available for
protocol-specific analysis.

## Note on `madrl_eaurp`'s dependency

`engines/madrl_eaurp` uses `torch` for its DQN (the other four engines only
need `pandas`/`matplotlib`, already in `requirements.txt`). Install it with
`pip install torch`, or run everything else via
`python run_all_experiments.py --skip madrl_eaurp` if you don't need it.