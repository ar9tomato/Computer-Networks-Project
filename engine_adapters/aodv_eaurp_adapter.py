"""
engine_adapters/aodv_eaurp_adapter.py

Adapter around engines/aodv_eaurp (formerly Member1_AODV_EAURP_Review2's
run_experiments.py). Reproduces that script's own simulation loop exactly
(same fixed grid/node/seed parameters, same per-speed fairness guarantee:
AODV and EAURP replay identical mobility + traffic for a given speed) but
returns rows instead of writing its own CSV.
"""

import random

from engine_adapters import _isolated_import, normalize_row
from engine_adapters.benchmark import (
    GRID_WIDTH,
    GRID_HEIGHT,
    NUM_NODES,
    TX_RANGE as TRANSMISSION_RANGE,
    INITIAL_ENERGY_JOULES as ENERGY_INIT,
    BASE_SEED as MASTER_SEED,
    ROUNDS,
    PACKETS_PER_ROUND,
    rounds_to_seconds,
)

ENGINE_DIR = "aodv_eaurp"

# Simulation parameters now come from engine_adapters.benchmark so this
# engine is measured on the same baseline as the other four. Two values
# changed as a result, and both were genuine comparability bugs:
#   * ENERGY_INIT was 60.0 J here while every other engine used 100.0 J.
#   * rounds/packets_per_round defaulted to 400x4 = 1,600 offered packets
#     against the others' 200x20 = 4,000.


def _generate_traffic_pattern(num_nodes, num_pairs, seed):
    rng = random.Random(seed)
    return [tuple(rng.sample(range(num_nodes), 2)) for _ in range(num_pairs)]


def _run_single(engine_cls, network_cls, metrics_cls, speed, rounds, packets_per_round, seed,
                 num_nodes=NUM_NODES, grid_width=GRID_WIDTH, grid_height=GRID_HEIGHT,
                 transmission_range=TRANSMISSION_RANGE):
    network = network_cls(
        num_nodes=num_nodes,
        grid_width=grid_width,
        grid_height=grid_height,
        transmission_range=transmission_range,
        speed=speed,
        energy_init=ENERGY_INIT,
        seed=seed,
    )
    engine = engine_cls(network)
    metrics = metrics_cls()

    traffic = _generate_traffic_pattern(num_nodes, rounds * packets_per_round, seed=seed + 1000)
    traffic_index = 0

    for round_index in range(rounds):
        network.step_mobility()
        network.rebuild_topology()
        network.apply_idle_drain()

        any_death_this_round = (
            any(not n.alive for n in network.nodes) and network.alive_fraction() < 1.0
        )

        for _ in range(packets_per_round):
            src, dst = traffic[traffic_index]
            traffic_index += 1
            if src == dst:
                continue
            engine.send_packet(src, dst, metrics, round_index)

        network.rebuild_topology()
        metrics.record_round(
            round_index=round_index,
            alive_fraction=network.alive_fraction(),
            any_death_occurred=any_death_this_round,
        )

    summary = metrics.summary()
    summary["speed_mps"] = speed
    summary["protocol"] = engine.name

    # Unified schema fields. AODV and EAURP are baseline protocols with no
    # trust model and no intrusion detection, so those columns are filled by
    # DEFAULT_METRICS (0.0) rather than left empty — see benchmark.py.
    summary["network_lifetime_sec"] = rounds_to_seconds(
        summary.get("network_lifetime_rounds"))
    summary["energy_consumed_joules"] = round(
        sum(n.energy_init - n.energy for n in network.nodes), 3)
    summary["packets_lost"] = summary.get("packet_loss_count", 0)
    return summary


def run(speeds, rounds=ROUNDS, packets_per_round=PACKETS_PER_ROUND, verbose=True,
        num_nodes=NUM_NODES, grid_width=None, grid_height=None):
    """
    Runs AODV and EAURP across all `speeds`. Returns a flat list of
    normalized row dicts (both protocols interleaved per speed, same
    order as the original run_experiments.py).

    `num_nodes` / `grid_width` / `grid_height` default to the standard
    benchmark values; pass a different `num_nodes` (with grid_width/height
    left as None) to run a density-matched scaling experiment instead.
    """
    network_module = _isolated_import(ENGINE_DIR, "core.network")
    metrics_module = _isolated_import(ENGINE_DIR, "core.metrics")
    protocols_module = _isolated_import(ENGINE_DIR, "protocols.base_aodv")

    Network = network_module.Network
    MetricsCollector = metrics_module.MetricsCollector
    AODVEngine = protocols_module.AODVEngine
    EAURPEngine = protocols_module.EAURPEngine

    if grid_width is None or grid_height is None:
        from engine_adapters.benchmark import density_matched_grid
        grid_width, grid_height = density_matched_grid(num_nodes)

    rows = []
    for speed in speeds:
        seed = MASTER_SEED + speed

        if verbose:
            print(f"[AODV ] speed={speed} m/s, num_nodes={num_nodes} ...")
        aodv_summary = _run_single(AODVEngine, Network, MetricsCollector, speed, rounds, packets_per_round, seed,
                                    num_nodes=num_nodes, grid_width=grid_width, grid_height=grid_height)
        rows.append(normalize_row("AODV", speed, aodv_summary))
        if verbose:
            print(f"        -> {aodv_summary}")

        if verbose:
            print(f"[EAURP] speed={speed} m/s, num_nodes={num_nodes} ...")
        eaurp_summary = _run_single(EAURPEngine, Network, MetricsCollector, speed, rounds, packets_per_round, seed,
                                     num_nodes=num_nodes, grid_width=grid_width, grid_height=grid_height)
        rows.append(normalize_row("EAURP", speed, eaurp_summary))
        if verbose:
            print(f"        -> {eaurp_summary}")

    return rows
