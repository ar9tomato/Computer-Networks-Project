#!/usr/bin/env python3
"""
run_experiments.py

CLI entry point for the centralized DRL-EAURP MANET simulation.

Runs the simulation across the standard team speed sweep:
10, 20, 30 and 40 m/s

Outputs:
    results/drl_eaurp_metrics.csv

Usage
-----
    python run_experiments.py

    python run_experiments.py --nodes 50 --rounds 200 --packets-per-round 20

    python run_experiments.py --speeds 10 20 30 40

    python run_experiments.py --output results/drl_eaurp_metrics.csv
"""

import argparse
import random
import time

from core.network import NetworkManager
from core.node import Node
from core.metrics import (
    MetricsCollector,
    write_results_csv,
    estimate_first_node_death_round,
)

from protocols.drl_eaurp import DRLEAURPEngine


def run_single_speed(
    speed,
    num_nodes,
    grid_width,
    grid_height,
    tx_range,
    rounds,
    packets_per_round,
    seed,
    verbose=True,
):
    """
    Run one complete DRL-EAURP simulation for a particular
    node speed and return one metrics summary row.
    """

    rng = random.Random(seed)

    # ---------------------------------------------------------
    # Create MANET network
    # ---------------------------------------------------------
    network = NetworkManager(
        num_nodes=num_nodes,
        grid_width=grid_width,
        grid_height=grid_height,
        tx_range=tx_range,
        speed=speed,
        num_groups=max(2, num_nodes // 10),
        malicious_probability=0.15,
        seed=seed,
    )

    # ---------------------------------------------------------
    # Create centralized DRL-EAURP routing engine
    # ---------------------------------------------------------
    engine = DRLEAURPEngine(
        network,
        seed=seed,
    )

    # ---------------------------------------------------------
    # Metrics collector
    # ---------------------------------------------------------
    metrics = MetricsCollector()

    # ---------------------------------------------------------
    # Simulation
    # ---------------------------------------------------------
    for round_number in range(1, rounds + 1):

        alive = network.alive_nodes()

        # Need at least two nodes to send a packet
        if len(alive) < 2:
            break

        # -----------------------------------------------------
        # Generate packets during this round
        # -----------------------------------------------------
        for _ in range(packets_per_round):

            alive = network.alive_nodes()

            if len(alive) < 2:
                break

            # Random source and destination
            source, destination = rng.sample(alive, 2)

            # Record packet transmission
            metrics.record_packet_sent()

            # -------------------------------------------------
            # DRL-EAURP routing
            # -------------------------------------------------
            delivered, delay_ms, hop_count = engine.route_packet(
                source,
                destination,
                round_number,
            )

            # -------------------------------------------------
            # Record result
            # -------------------------------------------------
            if delivered:
                metrics.record_packet_delivered(
                    delay_ms,
                    hop_count,
                )
            else:
                metrics.record_packet_lost()

        # -----------------------------------------------------
        # Record round-level metrics
        # -----------------------------------------------------
        metrics.record_round(
            round_number,
            network,
        )

        # -----------------------------------------------------
        # Move nodes and deplete energy
        # -----------------------------------------------------
        network.advance_round(dt=1.0)

        # -----------------------------------------------------
        # Stop if the network has exhausted its lifetime
        # -----------------------------------------------------
        if network.network_lifetime_exhausted():
            break

    # ---------------------------------------------------------
    # Simulation duration
    # ---------------------------------------------------------
    metrics.set_duration(round_number)

    # ---------------------------------------------------------
    # First node death
    # ---------------------------------------------------------
    if metrics.first_node_death_round is None:

        metrics.first_node_death_round = (
            estimate_first_node_death_round(
                network,
                network.round_number,
                Node.INITIAL_ENERGY,
            )
        )

    # ---------------------------------------------------------
    # Additional network information
    # ---------------------------------------------------------
    malicious_count = sum(
        1
        for node in network.nodes
        if node.is_malicious
    )

    isolated_malicious_count = sum(
        1
        for node in network.nodes
        if node.is_malicious and node.is_isolated
    )

    if malicious_count > 0:
        detection_rate = (
            isolated_malicious_count
            / malicious_count
            * 100.0
        )
    else:
        detection_rate = 0.0

    # ---------------------------------------------------------
    # Extra values stored in CSV
    # ---------------------------------------------------------
    extra = {
        "malicious_nodes": malicious_count,

        "isolated_nodes": isolated_malicious_count,

        "detection_rate_percent": round(
            detection_rate,
            3,
        ),

        "avg_trust": round(
            network.average_trust(),
            4,
        ),

        "avg_energy_normalized": round(
            network.average_energy(),
            4,
        ),
    }

    # ---------------------------------------------------------
    # Generate final summary row
    # ---------------------------------------------------------
    row = metrics.summary(
        speed,
        extra=extra,
    )

    # ---------------------------------------------------------
    # Console output
    # ---------------------------------------------------------
    if verbose:

        print(
            f"  speed={speed:>4} m/s | "
            f"PDR={row['pdr_percent']:>6.2f}% | "
            f"avg_delay={row['avg_delay_ms']:>7.2f} ms | "
            f"throughput={row['throughput_kbps']:>8.2f} kbps | "
            f"lifetime={row['network_lifetime_rounds']:>4} rounds | "
            f"isolated="
            f"{isolated_malicious_count}/"
            f"{malicious_count} malicious"
        )

    return row


def main():

    # =========================================================
    # Command-line arguments
    # =========================================================

    parser = argparse.ArgumentParser(
        description=(
            "Run centralized DRL-EAURP MANET "
            "simulation experiments across a speed sweep."
        )
    )

    parser.add_argument(
        "--nodes",
        type=int,
        default=50,
        help="Number of nodes (default: 50)",
    )

    parser.add_argument(
        "--width",
        type=float,
        default=1000,
        help="Grid width in meters (default: 1000)",
    )

    parser.add_argument(
        "--height",
        type=float,
        default=1000,
        help="Grid height in meters (default: 1000)",
    )

    parser.add_argument(
        "--range",
        dest="tx_range",
        type=float,
        default=250,
        help="Transmission range in meters (default: 250)",
    )

    parser.add_argument(
        "--speeds",
        type=float,
        nargs="+",
        default=[10, 20, 30, 40],
        help=(
            "Node speeds to test in m/s "
            "(default: 10 20 30 40)"
        ),
    )

    parser.add_argument(
        "--rounds",
        type=int,
        default=200,
        help="Simulation rounds per speed (default: 200)",
    )

    parser.add_argument(
        "--packets-per-round",
        type=int,
        default=20,
        help=(
            "Packets generated per round "
            "(default: 20)"
        ),
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed (default: 42)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="results/drl_eaurp_metrics.csv",
        help=(
            "Output CSV path "
            "(default: results/drl_eaurp_metrics.csv)"
        ),
    )

    args = parser.parse_args()

    # =========================================================
    # Header
    # =========================================================

    print("=" * 70)

    print(
        "DRL-EAURP "
        "(Deep Reinforcement Learning based EAURP) "
        "— Member 4 Simulation"
    )

    print("=" * 70)

    print(
        f"Grid: {args.width}x{args.height} m² | "
        f"Nodes: {args.nodes} | "
        f"Range: {args.tx_range} m | "
        f"Rounds: {args.rounds}"
    )

    print(
        f"Speeds sweep: {args.speeds}"
    )

    print("-" * 70)

    # =========================================================
    # Run experiments
    # =========================================================

    start = time.time()

    rows = []

    for i, speed in enumerate(args.speeds):

        row = run_single_speed(
            speed=speed,

            num_nodes=args.nodes,

            grid_width=args.width,

            grid_height=args.height,

            tx_range=args.tx_range,

            rounds=args.rounds,

            packets_per_round=args.packets_per_round,

            seed=args.seed + i,

        )

        rows.append(row)

    # =========================================================
    # Write CSV
    # =========================================================

    write_results_csv(
        rows,
        args.output,
    )

    elapsed = time.time() - start

    # =========================================================
    # Completion message
    # =========================================================

    print("-" * 70)

    print(
        f"Done in {elapsed:.2f}s."
    )

    print(
        f"Results written to: {args.output}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()