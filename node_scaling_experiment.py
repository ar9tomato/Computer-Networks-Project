#!/usr/bin/env python3
"""
node_scaling_experiment.py

Runs all five protocols (AODV, EAURP, ATEAURP, PSE-EAURP, DRL-EAURP,
MADRL-EAURP) across a sweep of NODE COUNTS at a single fixed speed, instead
of run_all_experiments.py's speed sweep at a fixed node count.

For each num_nodes in the sweep, the deployment grid is scaled so average
node density (and therefore average neighbor count) stays constant — see
engine_adapters.benchmark.density_matched_grid. That isolates "how well does
this protocol coordinate a larger population of nodes" as the variable under
test, rather than conflating it with "the network got denser".

No protocol logic is touched. Every engine still runs its own untouched
core/network.py, core/node.py, protocols/*.py — this script only varies the
num_nodes/grid_size arguments already threaded through each adapter's run().

Usage:
    python node_scaling_experiment.py
    python node_scaling_experiment.py --node-counts 50 100 200 400 800
    python node_scaling_experiment.py --skip madrl_eaurp
"""

import argparse
import os

import pandas as pd

from engine_adapters import (
    COMMON_COLUMNS,
    aodv_eaurp_adapter,
    ateaurp_adapter,
    pse_eaurp_adapter,
    drl_eaurp_adapter,
    madrl_eaurp_adapter,
)
from engine_adapters.benchmark import (
    DEFAULT_METRICS,
    NOT_APPLICABLE,
    ROUNDS,
    PACKETS_PER_ROUND,
    NODE_COUNTS_SWEEP,
    SCALING_SPEED_MPS,
)

ADAPTERS = {
    "aodv_eaurp": aodv_eaurp_adapter,
    "ateaurp": ateaurp_adapter,
    "pse_eaurp": pse_eaurp_adapter,
    "drl_eaurp": drl_eaurp_adapter,
    "madrl_eaurp": madrl_eaurp_adapter,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sweep num_nodes (density-matched grid) across all five engines "
                    "at a fixed speed and write results/node_scaling_metrics.csv."
    )
    parser.add_argument("--node-counts", type=int, nargs="+", default=NODE_COUNTS_SWEEP,
                         help=f"Node counts to sweep (default: {NODE_COUNTS_SWEEP}).")
    parser.add_argument("--speed", type=float, default=SCALING_SPEED_MPS,
                         help=f"Fixed node speed in m/s for every run (default: {SCALING_SPEED_MPS}).")
    parser.add_argument("--rounds", type=int, default=ROUNDS)
    parser.add_argument("--packets-per-round", type=int, default=PACKETS_PER_ROUND)
    parser.add_argument("--delivery-mode", type=str, default="tuned",
                         choices=["tuned", "simulated"])
    parser.add_argument("--skip", type=str, nargs="*", default=[],
                         choices=list(ADAPTERS.keys()))
    parser.add_argument("--output", type=str, default="results/node_scaling_metrics.csv")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    verbose = not args.quiet
    speeds = [args.speed]

    all_rows = []

    def run_engine(name, label, **kwargs):
        if name in args.skip:
            print(f"(skipping {label} — engines/{name})")
            return
        for num_nodes in args.node_counts:
            print("=" * 70)
            print(f"Running {label} (engines/{name}) at num_nodes={num_nodes}")
            print("=" * 70)
            rows = ADAPTERS[name].run(speeds, verbose=verbose, num_nodes=num_nodes, **kwargs)
            for row in rows:
                row["num_nodes"] = num_nodes
            all_rows.extend(rows)

    common = dict(rounds=args.rounds, packets_per_round=args.packets_per_round)
    gated = dict(common, delivery_mode=args.delivery_mode)

    print(f"Node-count sweep: {args.node_counts}, fixed speed={args.speed} m/s, "
          f"density-matched grid, delivery-mode={args.delivery_mode}")

    run_engine("aodv_eaurp", "AODV + EAURP", **common)
    run_engine("ateaurp", "ATEAURP", **gated)
    run_engine("pse_eaurp", "PSE-EAURP", **gated)
    run_engine("drl_eaurp", "DRL-EAURP", **gated)
    run_engine("madrl_eaurp", "MADRL-EAURP", **common)

    if not all_rows:
        print("No engines were run (everything skipped) — nothing to write.")
        return

    all_rows = [{**DEFAULT_METRICS, **{k: v for k, v in row.items() if v is not None}}
                for row in all_rows]

    df = pd.DataFrame(all_rows)
    ordered_cols = ["num_nodes"] + COMMON_COLUMNS + [
        c for c in df.columns if c not in COMMON_COLUMNS and c != "num_nodes"]
    df = df[ordered_cols].sort_values(["protocol", "num_nodes"]).reset_index(drop=True)

    for col in df.columns:
        if col == "protocol":
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    df.to_csv(args.output, index=False)

    print("=" * 70)
    print(f"Done. Wrote {len(df)} rows across {df['protocol'].nunique()} protocols "
          f"and {len(args.node_counts)} node counts to: {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
