# Computer Networks Project — Unified Experiment Pipeline

> **Start here:** `REFACTOR_NOTES.md` (routing fix, standardized baseline,
> metrics schema, delivery modes) and `PARAMETER_FIXES.md` (trust
> false-positive bug, DRL exploration, what was deliberately not tuned).
>
> **Run it:**
> ```bash
> python run_all_experiments.py                           # tuned mode (default)
> python run_all_experiments.py --delivery-mode simulated  # PDR derived from routing
> python visualize_all.py --output-dir plots/tuned
> python visualize_all.py --input results/combined_metrics_simulated.csv \
>                         --output-dir plots/simulated
> ```
>
> Baseline for every protocol: **4,000 packets, 100 J/node, speeds
> [10, 20, 30, 40] m/s, 100 ms/round.** Both modes reproduce byte-identically
> across runs.
>
> Read the "what I did not tune" section of `PARAMETER_FIXES.md` before using
> these numbers in a write-up — several columns are modelled rather than
> measured, and they are not all comparable across engines.

Consolidated MANET routing-protocol comparison across **all five members'
protocols**: **AODV**, **EAURP**, **ATEAURP**, **PSE-EAURP**, **DRL-EAURP**,
and **MADRL-EAURP**. Each member folder used to have its own duplicated
`run_experiments.py` + `visualize.py`. This refactor replaces all of them
with one root-level runner and one root-level visualizer producing a
single consolidated results file and one set of comparative charts
covering every protocol.

## Folder structure

```
Computer-Networks-Project/
├── engines/                      # protocol implementations, one per member
│   ├── aodv_eaurp/                # Member1_AODV_EAURP_Review2 → AODVEngine, EAURPEngine
│   ├── ateaurp/                   # Member2_ATEAURP           → ATEAURPEngine
│   ├── pse_eaurp/                 # Member3_PSEEAURP          → PSEEAURPEngine
│   ├── drl_eaurp/                 # Member_4_DRL_EAURP        → DRLEAURPEngine
│   └── madrl_eaurp/               # Member5_MADRL_EAURP       → MADRLEAURP (torch-based)
│       each with its own untouched core/ (Network, Node, MetricsCollector)
│       and protocols/ (the routing engine itself)
├── engine_adapters/               # the "glue" that makes one pipeline possible
│   ├── __init__.py                # isolated import helper + common row schema
│   ├── benchmark.py               # shared baseline params + unified metric schema
│   ├── aodv_eaurp_adapter.py       # runs AODV + EAURP
│   ├── ateaurp_adapter.py          # runs ATEAURP
│   ├── pse_eaurp_adapter.py        # runs PSE-EAURP
│   ├── drl_eaurp_adapter.py        # runs DRL-EAURP
│   └── madrl_eaurp_adapter.py      # runs MADRL-EAURP
├── run_all_experiments.py         # single root runner (all 6 protocols)
├── visualize_all.py                # single root visualizer (all 6 on one chart)
├── results/
│   ├── combined_metrics.csv            # generated — tuned mode
│   ├── combined_metrics_simulated.csv  # generated — simulated mode
│   └── metric_applicability.csv        # which 0.0 values are structural
├── plots/
│   ├── tuned/       *.png              # generated (5 charts)
│   └── simulated/   *.png              # generated (5 charts)
├── REFACTOR_NOTES.md
├── PARAMETER_FIXES.md
└── requirements.txt
```

Every member's `run_experiments.py` and `visualize.py` are removed —
their logic now lives in `engine_adapters/` and the two root scripts.

## Why there's an `engine_adapters/` layer instead of one merged `core/`

The five members' protocol code was written independently and is
**not API-compatible** across the board:

| Engine family | Network class | Node "alive" check | Per-packet call |
|---|---|---|---|
| `aodv_eaurp` (M1) | `Network` | `node.alive` | `engine.send_packet(src, dst, metrics, round)` — mutates a shared `MetricsCollector` |
| `ateaurp` / `pse_eaurp` / `drl_eaurp` (M2/M3/M4) | `NetworkManager` | `node.is_alive` (property) | `engine.route_packet(src, dst, round)` → `(delivered, delay_ms, hop_count)` |
| `madrl_eaurp` (M5) | `MANETNetwork` | `node.is_alive()` (method) | `engine.step_environment(training=...)` — a full train/eval RL loop, no single-packet call at all |

M2/M3/M4 actually share an *identical* `core/` (byte-for-byte for
`node.py`/`metrics.py`; only `network.py`'s docstring differs) — only
their engine classes (`ATEAURPEngine`, `PSEEAURPEngine`,
`DRLEAURPEngine`) differ, each with a different constructor and
per-round trust-update contract. M5 shares nothing with the other four:
it's a torch-based multi-agent DRL router with its own network/metrics
classes and an explicit train-then-evaluate loop instead of a
speed-sweep loop.

Silently merging all of this into one `Network`/`Node`/`Engine` class
would mean rewriting and re-validating five different simulation
cores — out of scope for a structural refactor, and risky to
correctness. Instead:

- Each engine's `core/` and `protocols/` package is kept **completely
  unmodified** (aside from two fixes documented below), just moved
  under `engines/<name>/`.
- Multiple engines' packages are still named `core` and `protocols`
  internally (their own files still do `from core.network import
  Network`, etc.), so `engine_adapters/__init__.py`'s
  `_isolated_import()` helper loads each engine's `core`/`protocols`
  from its own directory and clears `sys.modules` between engines, so
  same-named packages never collide.
- Each adapter (`aodv_eaurp_adapter.py`, `ateaurp_adapter.py`,
  `pse_eaurp_adapter.py`, `drl_eaurp_adapter.py`,
  `madrl_eaurp_adapter.py`) reproduces that member's original
  experiment loop, then converts its output into one **common row
  schema** (`protocol`, `speed_mps`, `pdr_percent`, `avg_delay_ms`,
  `packet_loss_percent`, `throughput_kbps`,
  `network_lifetime_rounds`, plus whatever protocol-specific extra
  columns it has — e.g. `detection_rate_percent`, `avg_trust`,
  `total_pt_crev_broadcasts`, `gossip_messages`).

`run_all_experiments.py` and `visualize_all.py` only ever talk to that
common schema — they don't know or care that `AODVEngine` and
`MADRLEAURP` work completely differently internally.

### Two bugs fixed in Member5's original script (not a redesign)

`madrl_eaurp_adapter.py`'s docstring documents this in full, but in
short: Member5's original `run_experiments.py`

1. called `np.random.uniform(...)` without ever importing `numpy` — it
   would crash immediately. The adapter imports it itself.
2. computed `"lifetime"` as `1000 - (speed * 5.5) + noise` — a formula
   with no connection to the simulated nodes' actual energy at all.
   The adapter instead derives `network_lifetime_rounds` from each
   node's real observed energy depletion (first real death within the
   run, or an estimate from the observed depletion rate), the same
   convention `ateaurp`/`pse_eaurp`/`drl_eaurp`'s own
   `estimate_first_node_death_round` already uses.

Everything else about MADRL-EAURP (network size, speed sweep, the
50-round training + 100-round evaluation split, the DRL routing/gossip
logic itself) is unchanged. Its very low PDR in quick test runs is the
DQN needing more training, not a plumbing bug — it's inherited as-is
from the original engine.

## `__init__.py` / import notes

- No changes were needed inside any `engines/<name>/` package — their
  `core/__init__.py` and `protocols/__init__.py` are untouched, and
  their internal files keep using `from core.network import ...` /
  `from protocols.<x> import ...` exactly as before.
- The only new import machinery is `engine_adapters/__init__.py`'s
  `_isolated_import(engine_dir_name, module_path)`, which:
  1. removes any previously-loaded `core.*` / `protocols.*` modules
     from `sys.modules`,
  2. puts `engines/<engine_dir_name>/` at the front of `sys.path` (and
     removes every other engine's directory from `sys.path`),
  3. imports and returns the requested module fresh from that
     directory.
- To add a sixth engine later: drop it under `engines/<name>/` with its
  own `core/`/`protocols/` packages, write one adapter module that
  calls `_isolated_import("<name>", "...")` and returns
  `normalize_row(...)` rows, add it to the `ADAPTERS` dict in
  `run_all_experiments.py`, and (optionally) give it a style entry in
  `visualize_all.py`'s `PROTOCOL_STYLES`.

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

# Plot every protocol present in the results on the same comparative charts
python visualize_all.py
```

`run_all_experiments.py` writes `results/combined_metrics.csv` with one
row per `(protocol, speed)` pair across all engines that ran.
`visualize_all.py` reads that file and writes one PNG per metric under
`plots/`, with every protocol present plotted together using a fixed,
distinct color/marker/line-style per protocol and a legend.

## Metrics compared

- Packet Delivery Ratio (%)
- Average Delay (ms)
- Packet Loss (%)
- Throughput (kbps)
- Network Lifetime (rounds)

Each protocol may also report extra columns in `combined_metrics.csv`
(e.g. ATEAURP/PSE-EAURP/DRL-EAURP's `avg_trust`,
`detection_rate_percent`; PSE-EAURP's `total_pt_crev_broadcasts`;
MADRL-EAURP's `gossip_messages`) that aren't part of the shared
comparison charts but remain available for protocol-specific analysis.

## Note on `madrl_eaurp`'s dependency

`engines/madrl_eaurp` uses `torch` for its DQN (the other four engines
only need `pandas`/`matplotlib`, already in `requirements.txt`). Install
it with `pip install torch`, or run everything else via
`python run_all_experiments.py --skip madrl_eaurp` if you don't need it.
