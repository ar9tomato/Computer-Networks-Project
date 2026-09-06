# Member 1 — Baseline AODV & EAURP (Energy-Aware Unobservable Routing Protocol)

MANET (Mobile Ad-hoc Network) simulation comparing a simplified baseline
AODV routing protocol against EAURP, an energy-aware enhancement, across
four node-speed scenarios. Built to be merged into a shared repository
alongside Members 2–5's protocol implementations.

## Project Structure

```
manet_sim/
├── core/
│   ├── node.py          # Node: position, speed, energy, alive state, neighbor table
│   ├── network.py       # Deployment grid, mobility model, distance calc, topology
│   └── metrics.py       # PDR, delay, packet loss, throughput, network lifetime
├── protocols/
│   └── base_aodv.py     # AODVEngine (shortest-hop) + EAURPEngine (energy-aware)
├── run_experiments.py   # Runs both protocols across speeds 10/20/30/40 m/s
├── visualize.py         # Generates comparative line charts from the CSV results
├── make_zip.py          # Packages the project into the deliverable .zip
├── results/
│   ├── aodv_metrics.csv
│   └── eaurp_metrics.csv
├── graphs/               # Generated PNG charts (created by visualize.py)
├── requirements.txt
└── README.md
```

## Simulation Parameters

| Parameter            | Value                          |
|-----------------------|--------------------------------|
| Deployment grid       | 1000 × 1000 m²                 |
| Node count            | 50                              |
| Transmission range R  | 250 m (Euclidean distance)     |
| Speed scenarios       | 10, 20, 30, 40 m/s              |
| Energy model          | Continuous baseline depletion   |
| Low-energy threshold  | 20% of initial energy (EAURP)   |

## Protocol Summary

**Baseline AODV** — simplified Route Request (RREQ) / Route Reply (RREP)
discovery implemented as a breadth-first search over the live
connectivity graph. Routes are selected purely by minimum hop count.
Route maintenance re-validates every hop before each transmission and
triggers rediscovery on link breakage (mobility or node death).

**EAURP** — built on the same RREQ/RREP discovery mechanism, with two
enhancements:
1. Any node with residual energy `E_i < 0.2 * E_init` is excluded from
   route discovery entirely (cannot forward RREQs or appear as a hop).
2. Among the discovered shortest-hop candidate routes, the final route is
   chosen using a composite score:
   `score = 0.7 * avg_normalized_residual_energy − 0.3 * normalized_hop_count`
   favoring paths with healthier intermediate nodes.

Energy depletes every round via a continuous baseline idle drain, plus a
per-transmission/reception cost applied to every node that actually
forwards a packet: `E_i(t+1) = E_i(t) − ΔE_i`.

## Fair Comparison Guarantee

For each speed scenario, AODV and EAURP each run on their own, fully
independent `Network`/`Node` object graph, but both are constructed from
the **same random seed**, guaranteeing identical initial node positions,
mobility trajectories, packet source/destination pairs, node count,
transmission range, speed, and round count. Because the two protocol runs
never share objects, one protocol's energy depletion or route state can
never leak into or affect the other's results.

## Metrics Collected

- Packet Delivery Ratio (PDR %)
- Average Delay (ms)
- Packet Loss (count and %)
- Throughput (kbps)
- Network Lifetime (rounds sustaining ≥50% of nodes alive)

## Running the Project (VS Code integrated terminal)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the simulations (AODV + EAURP, all four speeds)
python run_experiments.py

# Optional: customize round count / traffic load
python run_experiments.py --rounds 500 --packets-per-round 6

# 3. Generate comparative charts
python visualize.py

# 4. Package everything into the deliverable zip
python make_zip.py
```

After step 2, `results/aodv_metrics.csv` and `results/eaurp_metrics.csv`
contain the per-speed metric summaries. After step 3, `graphs/` contains
five PNG charts (PDR, delay, packet loss, throughput, lifetime — each
plotted vs. speed for both protocols). After step 4,
`Member1_AODV_EAURP_Review2.zip` contains the full project, ready to
submit or merge into the shared MANET simulation repository.

## Notes for Merging with Members 2–5

- `core/` is written to be protocol-agnostic (`Node`, `Network`,
  `MetricsCollector` have no AODV/EAURP-specific logic) so other members'
  protocol engines can reuse it directly — just implement a new engine in
  `protocols/` exposing the same `send_packet(src, dst, metrics,
  current_round)` interface used by `BaseRoutingEngine`.
- All simulation parameters (grid size, node count, transmission range,
  speeds) are defined as constants at the top of `run_experiments.py` for
  easy central configuration across the merged repository.
