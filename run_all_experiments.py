#!/usr/bin/env python3
"""
run_all_experiments.py

Single root-level entry point that runs ALL FIVE protocol experiments
(AODV, EAURP, ATEAURP, PSE-EAURP, DRL-EAURP, MADRL-EAURP) across the
same speed sweep and writes one consolidated results/combined_metrics.csv,
replacing the old per-member `run_experiments.py` scripts.

Each protocol still runs through its OWN engine and its OWN core
(engines/aodv_eaurp, engines/ateaurp, engines/pse_eaurp,
engines/drl_eaurp, engines/madrl_eaurp) via a thin adapter in
engine_adapters/ — see that package's docstring for why a single
merged Network/Node/Engine class isn't used. This script only ever
talks to the adapters' common row schema.

Usage (from the project root):
    python run_all_experiments.py
    python run_all_experiments.py --speeds 10 20 30 40 --aodv-eaurp-rounds 400
    python run_all_experiments.py --skip madrl_eaurp   # e.g. to skip the torch-based engine
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
    TOTAL_PACKETS,
    INITIAL_ENERGY_JOULES,
    SPEEDS_MPS as DEFAULT_SPEEDS,
)

# name -> (adapter module, kwargs specific to that adapter's run() signature)
ADAPTERS = {
    "aodv_eaurp": aodv_eaurp_adapter,     # AODV + EAURP
    "ateaurp": ateaurp_adapter,           # ATEAURP
    "pse_eaurp": pse_eaurp_adapter,       # PSE-EAURP
    "drl_eaurp": drl_eaurp_adapter,       # DRL-EAURP
    "madrl_eaurp": madrl_eaurp_adapter,   # MADRL-EAURP (torch-based; fixed round counts)
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run AODV, EAURP, and ATEAURP experiments across the same speed sweep "
                    "and write one consolidated results/combined_metrics.csv."
    )
    parser.add_argument("--speeds", type=float, nargs="+", default=DEFAULT_SPEEDS,
                         help=f"Node speeds (m/s) to sweep (default: {DEFAULT_SPEEDS}).")
    parser.add_argument("--rounds", type=int, default=ROUNDS,
                         help=f"Simulation rounds per speed, for every engine (default: {ROUNDS}).")
    parser.add_argument("--packets-per-round", type=int, default=PACKETS_PER_ROUND,
                         help=f"Packets offered per round, for every engine "
                              f"(default: {PACKETS_PER_ROUND}, i.e. {TOTAL_PACKETS} total).")
    parser.add_argument("--delivery-mode", type=str, default="tuned",
                         choices=["tuned", "simulated"],
                         help="How ATEAURP / PSE-EAURP / DRL-EAURP decide whether a packet "
                              "was delivered. 'tuned' (default) keeps the legacy hand-set "
                              "delivery-probability constants. 'simulated' reports delivery "
                              "only when the packet actually reached its destination in the "
                              "hop-by-hop simulation, making PDR comparable with AODV, EAURP "
                              "and MADRL-EAURP, which already work that way.")
    parser.add_argument("--skip", type=str, nargs="*", default=[],
                         choices=list(ADAPTERS.keys()),
                         help="Engine names to skip entirely, e.g. --skip madrl_eaurp "
                              "(useful if torch isn't installed).")
    parser.add_argument("--output", type=str, default="results/combined_metrics.csv",
                         help="Path to the consolidated output CSV.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-run progress output.")
    return parser.parse_args()


def main():
    args = parse_args()
    verbose = not args.quiet
    speeds = [int(s) if float(s).is_integer() else s for s in args.speeds]

    all_rows = []

    def run_engine(name, label, **kwargs):
        if name in args.skip:
            print(f"(skipping {label} — engines/{name})")
            return
        print("=" * 70)
        print(f"Running {label} (engines/{name})")
        print("=" * 70)
        all_rows.extend(ADAPTERS[name].run(speeds, verbose=verbose, **kwargs))

    # Every engine now receives the SAME rounds / packets-per-round, so the
    # protocols are compared on an identical traffic load. Previously
    # AODV/EAURP ran 400x4 = 1,600 packets against everyone else's 4,000.
    common = dict(rounds=args.rounds, packets_per_round=args.packets_per_round)
    # AODV/EAURP and MADRL-EAURP always derive delivery from their own
    # simulation, so they take no delivery_mode; only the three engines that
    # shipped with a hand-tuned delivery gate accept it.
    gated = dict(common, delivery_mode=args.delivery_mode)

    print(f"Baseline: {args.rounds * args.packets_per_round} packets, "
          f"{INITIAL_ENERGY_JOULES:.0f} J/node, speeds {speeds} m/s, "
          f"delivery-mode={args.delivery_mode}")

    run_engine("aodv_eaurp", "AODV + EAURP", **common)
    run_engine("ateaurp", "ATEAURP", **gated)
    run_engine("pse_eaurp", "PSE-EAURP", **gated)
    run_engine("drl_eaurp", "DRL-EAURP", **gated)
    run_engine("madrl_eaurp", "MADRL-EAURP", **common)

    if not all_rows:
        print("No engines were run (everything skipped) — nothing to write.")
        return

    # Union of every column any protocol produced, common columns first so
    # the CSV stays easy to read regardless of each engine's extra fields
    # (e.g. ATEAURP's trust/detection columns).
    # Final guard: merge every row over DEFAULT_METRICS one more time at the
    # writing stage. The adapters already do this, but doing it here too means
    # a future engine that forgets a key still produces an explicit 0.0
    # instead of an empty cell in the CSV.
    all_rows = [{**DEFAULT_METRICS, **{k: v for k, v in row.items() if v is not None}}
                for row in all_rows]

    df = pd.DataFrame(all_rows)
    ordered_cols = COMMON_COLUMNS + [c for c in df.columns if c not in COMMON_COLUMNS]
    df = df[ordered_cols].sort_values(["protocol", "speed_mps"]).reset_index(drop=True)

    # Any remaining engine-specific extras (columns only some protocols emit)
    # are filled with 0.0 for numeric columns so no cell is ever blank.
    for col in df.columns:
        if col == "protocol":
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    df.to_csv(args.output, index=False)

    # Companion file recording which zeros mean "this protocol has no such
    # mechanism" rather than "this measured zero". Without it, AODV's 0.0
    # detection rate is indistinguishable from a detector that caught nothing.
    applicability_path = os.path.join(
        os.path.dirname(args.output) or ".", "metric_applicability.csv")
    app_rows = []
    for protocol in sorted(df["protocol"].unique()):
        for metric in DEFAULT_METRICS:
            app_rows.append({
                "protocol": protocol,
                "metric": metric,
                "applicable": metric not in NOT_APPLICABLE.get(protocol, []),
            })
    pd.DataFrame(app_rows).to_csv(applicability_path, index=False)

    missing = int(df.isna().sum().sum())
    print(f"Empty cells in {args.output}: {missing}")
    print(f"Metric applicability map written to: {applicability_path}")

    print("=" * 70)
    print(f"Done. Consolidated metrics for {df['protocol'].nunique()} protocols "
          f"across {len(speeds)} speeds written to: {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
