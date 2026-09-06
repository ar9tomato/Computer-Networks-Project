"""
run_experiments.py

CLI entry point that runs fair, side-by-side MANET simulations comparing
baseline AODV against EAURP across the required speed scenarios
(10, 20, 30, 40 m/s), and exports the resulting metrics to
results/aodv_metrics.csv and results/eaurp_metrics.csv.

Fairness guarantee
-------------------
For each speed value, AODV and EAURP are each run on their OWN,
completely independent Network instance, but both networks are
constructed with the SAME random seed. Because Network deployment,
mobility, and packet source/destination selection are all driven by a
single seeded RNG, this guarantees:

    - identical initial node positions
    - identical mobility trajectories round-by-round
    - identical packet source/destination pairs, in the same order
    - identical node count, transmission range, speed, and round count

...for both protocols at a given speed, while each protocol's own energy
depletion and route state remains completely isolated (they operate on
two separate Network/Node object graphs, so nothing forwarded/consumed by
one protocol can ever affect the other).

Usage (from the project root):
    python run_experiments.py
    python run_experiments.py --rounds 500 --packets-per-round 5
"""

import argparse
import csv
import os
import random
import sys

from core.network import Network
from core.metrics import MetricsCollector
from protocols.base_aodv import AODVEngine, EAURPEngine

# ----------------------------------------------------------------------
# Fixed simulation parameters (per assignment spec)
# ----------------------------------------------------------------------
GRID_WIDTH = 1000.0
GRID_HEIGHT = 1000.0
NUM_NODES = 50
TRANSMISSION_RANGE = 250.0
SPEEDS = [10, 20, 30, 40]
ENERGY_INIT = 60.0
MASTER_SEED = 42  # fixed so results are reproducible run-to-run


def generate_traffic_pattern(num_nodes, num_pairs, seed):
    """
    Generates a fixed list of (src, dst) packet source/destination pairs
    using a dedicated RNG seeded independently of node deployment, so the
    SAME traffic pattern (and same order of packet attempts) can be
    replayed identically for both AODV and EAURP at a given speed.
    """
    rng = random.Random(seed)
    pairs = []
    for _ in range(num_pairs):
        src, dst = rng.sample(range(num_nodes), 2)
        pairs.append((src, dst))
    return pairs


def run_single_simulation(engine_cls, speed, rounds, packets_per_round,
                           seed, engine_kwargs=None):
    """
    Runs one full simulation (either AODV or EAURP, per engine_cls) for a
    given speed scenario, and returns the resulting metrics summary dict.
    """
    engine_kwargs = engine_kwargs or {}

    network = Network(
        num_nodes=NUM_NODES,
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
        transmission_range=TRANSMISSION_RANGE,
        speed=speed,
        energy_init=ENERGY_INIT,
        seed=seed,
    )
    engine = engine_cls(network, **engine_kwargs)
    metrics = MetricsCollector()

    traffic = generate_traffic_pattern(NUM_NODES, rounds * packets_per_round,
                                        seed=seed + 1000)
    traffic_index = 0

    for round_index in range(rounds):
        network.step_mobility()
        network.rebuild_topology()
        network.apply_idle_drain()

        any_death_this_round = any(not n.alive for n in network.nodes) and \
            network.alive_fraction() < 1.0

        for _ in range(packets_per_round):
            src, dst = traffic[traffic_index]
            traffic_index += 1
            if src == dst:
                continue
            engine.send_packet(src, dst, metrics, round_index)

        network.rebuild_topology()  # reflect any deaths caused by tx/rx this round
        metrics.record_round(
            round_index=round_index,
            alive_fraction=network.alive_fraction(),
            any_death_occurred=any_death_this_round,
        )

    summary = metrics.summary()
    summary["speed_mps"] = speed
    summary["protocol"] = engine.name
    return summary


def write_csv(rows, filepath):
    if not rows:
        return
    fieldnames = ["protocol", "speed_mps", "pdr_percent", "avg_delay_ms",
                  "packets_sent", "packets_delivered", "packet_loss_count",
                  "packet_loss_percent", "throughput_kbps",
                  "network_lifetime_rounds"]
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Run fair AODV vs EAURP MANET simulations across speed scenarios."
    )
    parser.add_argument("--rounds", type=int, default=400,
                        help="Number of simulation rounds per run (default: 400).")
    parser.add_argument("--packets-per-round", type=int, default=4,
                        help="Data packets attempted per round (default: 4).")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Directory to write the CSV outputs to.")
    args = parser.parse_args()

    aodv_rows = []
    eaurp_rows = []

    for speed in SPEEDS:
        # Same seed for both protocols at this speed -> identical initial
        # conditions, positions, mobility, and traffic pattern.
        seed = MASTER_SEED + speed

        print(f"[AODV ] Running speed={speed} m/s ...")
        aodv_summary = run_single_simulation(
            AODVEngine, speed, args.rounds, args.packets_per_round, seed
        )
        aodv_rows.append(aodv_summary)
        print(f"        -> {aodv_summary}")

        print(f"[EAURP] Running speed={speed} m/s ...")
        eaurp_summary = run_single_simulation(
            EAURPEngine, speed, args.rounds, args.packets_per_round, seed
        )
        eaurp_rows.append(eaurp_summary)
        print(f"        -> {eaurp_summary}")

    aodv_path = os.path.join(args.output_dir, "aodv_metrics.csv")
    eaurp_path = os.path.join(args.output_dir, "eaurp_metrics.csv")
    write_csv(aodv_rows, aodv_path)
    write_csv(eaurp_rows, eaurp_path)

    print(f"\nResults written to:\n  {aodv_path}\n  {eaurp_path}")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
