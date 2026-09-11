"""
engine_adapters/pse_eaurp_adapter.py

Adapter around engines/pse_eaurp (formerly Member3_PSEEAURP's
run_experiments.py). Same NetworkManager/Node/MetricsCollector core as
ateaurp (identical files), but a different engine: PSEEAURPEngine, whose
update_all_trust() takes a current_round kwarg (predictive trust +
PT_CREV revocation), and whose per-run extras include a revocation log
instead of ATEAURP's isolation counters.
"""

from engine_adapters import _isolated_import, normalize_row
from engine_adapters.benchmark import (
    NUM_NODES,
    GRID_WIDTH,
    GRID_HEIGHT,
    TX_RANGE,
    ROUNDS,
    PACKETS_PER_ROUND,
    INITIAL_ENERGY_JOULES,
    MALICIOUS_PROBABILITY,
    BASE_SEED,
    rounds_to_seconds,
)

ENGINE_DIR = "pse_eaurp"

# Baseline parameters imported from engine_adapters.benchmark so all five
# engines share one definition (4,000 packets, 100 J, speeds 10-40 m/s).


def _run_single_speed(speed, network_manager_cls, node_cls, metrics_cls,
                       estimate_death_fn, engine_cls, rng_module,
                       rounds, packets_per_round, seed, delivery_mode,
                       num_nodes=NUM_NODES, grid_width=GRID_WIDTH, grid_height=GRID_HEIGHT,
                       tx_range=TX_RANGE):
    rng = rng_module.Random(seed)

    network = network_manager_cls(
        num_nodes=num_nodes,
        grid_width=grid_width,
        grid_height=grid_height,
        tx_range=tx_range,
        speed=speed,
        num_groups=max(2, num_nodes // 10),
        malicious_probability=MALICIOUS_PROBABILITY,
        seed=seed,
    )
    engine = engine_cls(network, seed=seed, delivery_mode=delivery_mode)
    metrics = metrics_cls()

    for round_number in range(1, rounds + 1):
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

    # Throughput unit fix: MetricsCollector.throughput_kbps divides delivered
    # bits by `simulation_duration_s`, but this was previously handed a count
    # of ROUNDS, implicitly declaring 1 round == 1 second. AODV/EAURP already
    # used 100 ms per round, so the two families' throughput columns were a
    # factor of 10 apart. All five engines now use ROUND_DURATION_MS = 100.
    metrics.set_duration(rounds_to_seconds(rounds))

    if metrics.first_node_death_round is None:
        metrics.first_node_death_round = estimate_death_fn(
            network, network.round_number, node_cls.INITIAL_ENERGY
        )

    revoked_malicious_count = sum(
        1 for n in network.nodes if n.is_malicious and n.node_id in engine.revocation_list
    )
    malicious_count = sum(1 for n in network.nodes if n.is_malicious)
    detection_rate = (revoked_malicious_count / malicious_count * 100.0) if malicious_count else 0.0

    extra = {
        "malicious_nodes": malicious_count,
        "isolated_nodes": revoked_malicious_count,
        "detection_rate_percent": round(detection_rate, 3),
        "avg_trust": round(network.average_trust(), 4),
        "avg_predicted_trust": round(engine.average_predicted_trust(), 4),
        "avg_energy_normalized": round(network.average_energy(), 4),
        "link_success_probability": round(engine.link_success_probability(), 4),
        "total_pt_crev_broadcasts": len(engine._pt_crev_log),
    }

    extra["network_lifetime_sec"] = rounds_to_seconds(
        metrics.network_lifetime_rounds)
    extra["energy_consumed_joules"] = round(
        sum(INITIAL_ENERGY_JOULES - n.energy for n in network.nodes), 3)

    return metrics.summary(speed, extra=extra)


def run(speeds, rounds=ROUNDS, packets_per_round=PACKETS_PER_ROUND, verbose=True,
        delivery_mode="tuned", num_nodes=NUM_NODES, grid_width=None, grid_height=None):
    """
    Runs PSE-EAURP across all `speeds`. Returns a flat list of normalized
    row dicts, one per speed.

    Pass a different `num_nodes` (grid_width/height left as None) to run a
    density-matched scaling experiment instead of the standard benchmark.
    """
    if grid_width is None or grid_height is None:
        from engine_adapters.benchmark import density_matched_grid
        grid_width, grid_height = density_matched_grid(num_nodes)

    import random as rng_module

    network_module = _isolated_import(ENGINE_DIR, "core.network")
    node_module = _isolated_import(ENGINE_DIR, "core.node")
    metrics_module = _isolated_import(ENGINE_DIR, "core.metrics")
    protocols_module = _isolated_import(ENGINE_DIR, "protocols.pse_eaurp_engine")

    NetworkManager = network_module.NetworkManager
    Node = node_module.Node
    MetricsCollector = metrics_module.MetricsCollector
    estimate_first_node_death_round = metrics_module.estimate_first_node_death_round
    PSEEAURPEngine = protocols_module.PSEEAURPEngine

    rows = []
    for i, speed in enumerate(speeds):
        seed = BASE_SEED + i
        if verbose:
            print(f"[PSE-EAURP] speed={speed} m/s, num_nodes={num_nodes} ...")
        summary = _run_single_speed(
            speed, NetworkManager, Node, MetricsCollector,
            estimate_first_node_death_round, PSEEAURPEngine, rng_module,
            rounds, packets_per_round, seed, delivery_mode,
            num_nodes=num_nodes, grid_width=grid_width, grid_height=grid_height,
        )
        if verbose:
            print(f"            -> PDR={summary['pdr_percent']:.2f}% "
                  f"delay={summary['avg_delay_ms']:.2f}ms "
                  f"throughput={summary['throughput_kbps']:.2f}kbps "
                  f"lifetime={summary['network_lifetime_rounds']} rounds")
        rows.append(normalize_row("PSE-EAURP", speed, summary))

    return rows
