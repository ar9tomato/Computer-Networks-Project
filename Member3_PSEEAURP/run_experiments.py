#!/usr/bin/env python3
"""
run_experiments.py
CLI entry point that runs the PSE-EAURP MANET simulation across the
standard team speed sweep and exports summary metrics to
results/pseaurp_metrics.csv.

Usage
-----
    python run_experiments.py
    python run_experiments.py --nodes 50 --rounds 200 --packets-per-round 20
    python run_experiments.py --speeds 10 20 30 40 --output results/pseaurp_metrics.csv
"""

import argparse
import random
import time

from core.network import NetworkManager
from core.node import Node
from core.metrics import MetricsCollector, write_results_csv, estimate_first_node_death_round
from protocols.pse_eaurp_engine import PSEEAURPEngine


def run_single_speed(speed, num_nodes, grid_width, grid_height, tx_range,
                      rounds, packets_per_round, seed, verbose=True):
    """Run one full simulation for a given node speed and return a metrics summary row."""
    rng = random.Random(seed)

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
    engine = PSEEAURPEngine(network, seed=seed)
    metrics = MetricsCollector()

    for round_number in range(1, rounds + 1):
        # Predictive trust engine runs once per round using the previous
        # round's F_i/R_i state, then checks for PT_CREV revocations.
        engine.update_all_trust(current_round=round_number)

        for _ in range(packets_per_round):
            alive = network.alive_nodes()
            if len(alive) < 2:
                break
            source, dest = rng.sample(alive, 2)

            metrics.record_packet_sent()
            delivered, delay_ms, hop_count = engine.route_packet(source, dest, round_number)

            if delivered:
                metrics.record_packet_delivered(delay_ms, hop_count)
            else:
                metrics.record_packet_lost()

        metrics.record_round(round_number, network)
        network.advance_round(dt=1.0)

        if network.network_lifetime_exhausted():
            break

    metrics.set_duration(rounds)

    if metrics.first_node_death_round is None:
        metrics.first_node_death_round = estimate_first_node_death_round(
            network, network.round_number, Node.INITIAL_ENERGY
        )

    # Detection accuracy: how many of the truly malicious nodes did PT_CREV
    # actually revoke (rather than just isolated-but-not-malicious ones)?
    revoked_malicious_count = sum(
        1 for n in network.nodes if n.is_malicious and n.node_id in engine.revocation_list
    )
    malicious_count = sum(1 for n in network.nodes if n.is_malicious)
    detection_rate = (revoked_malicious_count / malicious_count * 100.0) if malicious_count else 0.0

    extra = {
        "malicious_nodes": malicious_count,
        "isolated_nodes": revoked_malicious_count,
        "detection_rate_percent": round(detection_rate, 3),
        "avg_predicted_trust": round(engine.average_predicted_trust(), 4),
        "avg_energy_normalized": round(network.average_energy(), 4),
        "link_success_probability": round(engine.link_success_probability(), 4),
        "total_pt_crev_broadcasts": len(engine._pt_crev_log),
    }

    row = metrics.summary(speed, extra=extra)

    if verbose:
        print(f"  speed={speed:>4} m/s | PDR={row['pdr_percent']:>6.2f}% | "
              f"avg_delay={row['avg_delay_ms']:>7.2f} ms | "
              f"throughput={row['throughput_kbps']:>8.2f} kbps | "
              f"lifetime={row['network_lifetime_rounds']:>4} rounds | "
              f"PT_CREV revocations={row['total_pt_crev_broadcasts']} "
              f"({revoked_malicious_count}/{malicious_count} malicious caught)")

    return row


def main():
    parser = argparse.ArgumentParser(
        description="Run PSE-EAURP MANET simulation experiments across a speed sweep."
    )
    parser.add_argument("--nodes", type=int, default=50, help="Number of nodes (default: 50)")
    parser.add_argument("--width", type=float, default=1000, help="Grid width in meters")
    parser.add_argument("--height", type=float, default=1000, help="Grid height in meters")
    parser.add_argument("--range", dest="tx_range", type=float, default=250,
                         help="Transmission range R in meters")
    parser.add_argument("--speeds", type=float, nargs="+", default=[10, 20, 30, 40],
                         help="List of node speeds in m/s to sweep")
    parser.add_argument("--rounds", type=int, default=200,
                         help="Number of simulation rounds per speed")
    parser.add_argument("--packets-per-round", type=int, default=20,
                         help="Number of packets injected into the network per round")
    parser.add_argument("--seed", type=int, default=42, help="Base RNG seed")
    parser.add_argument("--output", type=str, default="results/pseaurp_metrics.csv",
                         help="Output CSV path")
    args = parser.parse_args()

    print("=" * 70)
    print("PSE-EAURP (Predictive Secure EAURP) — Member 3 Simulation")
    print("=" * 70)
    print(f"Grid: {args.width}x{args.height} m^2 | Nodes: {args.nodes} | "
          f"Range: {args.tx_range} m | Rounds: {args.rounds}")
    print(f"Speeds sweep: {args.speeds}")
    print("-" * 70)

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

    write_results_csv(rows, args.output)
    elapsed = time.time() - start

    print("-" * 70)
    print(f"Done in {elapsed:.2f}s. Results written to: {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
