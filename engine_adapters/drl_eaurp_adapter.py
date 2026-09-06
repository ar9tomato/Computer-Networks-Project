"""
engine_adapters/drl_eaurp_adapter.py

Adapter around engines/drl_eaurp (formerly Member_4_DRL_EAURP's
run_experiments.py). Same NetworkManager/Node/MetricsCollector core
family as ateaurp/pse_eaurp, but DRLEAURPEngine has no per-round
update_all_trust() call — its trust/Q-learning bookkeeping happens
entirely inside route_packet() — and reports isolated_nodes via
node.is_isolated rather than an engine-side revocation list.
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

ENGINE_DIR = "drl_eaurp"

# Baseline parameters imported from engine_adapters.benchmark so all five
# engines share one definition (4,000 packets, 100 J, speeds 10-40 m/s).

# Warm-up rounds before measurement begins. Not counted in reported metrics,
# matching MADRL-EAURP's train(50)/eval convention.
TRAINING_ROUNDS = 50


def _run_single_speed(speed, network_manager_cls, node_cls, metrics_cls,
                       estimate_death_fn, engine_cls, rng_module,
                       rounds, packets_per_round, seed, delivery_mode):
    rng = rng_module.Random(seed)

    network = network_manager_cls(
        num_nodes=NUM_NODES,
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
        tx_range=TX_RANGE,
        speed=speed,
        num_groups=max(2, NUM_NODES // 10),
        malicious_probability=MALICIOUS_PROBABILITY,
        seed=seed,
    )
    engine = engine_cls(network, seed=seed, delivery_mode=delivery_mode)
    metrics = metrics_cls()

    # Warm-up training phase, then evaluate with a near-greedy policy. The
    # engine previously had no train/evaluate split at all: every reported
    # packet was routed with epsilon=0.1, so a tenth of the measured
    # decisions were random by construction. MADRL-EAURP already uses this
    # train-then-evaluate structure; DRL-EAURP now matches it.
    engine.set_evaluation_mode(False)
    warmup_metrics = metrics_cls()
    for warmup_round in range(1, TRAINING_ROUNDS + 1):
        alive = network.alive_nodes()
        if len(alive) < 2:
            break
        for _ in range(packets_per_round):
            alive = network.alive_nodes()
            if len(alive) < 2:
                break
            source, dest = rng.sample(alive, 2)
            warmup_metrics.record_packet_sent()
            engine.route_packet(source, dest, warmup_round)
        network.advance_round(dt=1.0)
    engine.set_evaluation_mode(True)

    round_number = 0
    for round_number in range(1, rounds + 1):
        alive = network.alive_nodes()
        if len(alive) < 2:
            break

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
    metrics.set_duration(rounds_to_seconds(round_number))

    if metrics.first_node_death_round is None:
        metrics.first_node_death_round = estimate_death_fn(
            network, network.round_number, node_cls.INITIAL_ENERGY
        )

    malicious_count = sum(1 for n in network.nodes if n.is_malicious)
    isolated_malicious_count = sum(1 for n in network.nodes if n.is_malicious and n.is_isolated)
    detection_rate = (isolated_malicious_count / malicious_count * 100.0) if malicious_count else 0.0

    extra = {
        "malicious_nodes": malicious_count,
        "isolated_nodes": isolated_malicious_count,
        "detection_rate_percent": round(detection_rate, 3),
        "avg_trust": round(network.average_trust(), 4),
        "avg_energy_normalized": round(network.average_energy(), 4),
    }

    extra["network_lifetime_sec"] = rounds_to_seconds(
        metrics.network_lifetime_rounds)
    extra["energy_consumed_joules"] = round(
        sum(INITIAL_ENERGY_JOULES - n.energy for n in network.nodes), 3)

    return metrics.summary(speed, extra=extra)


def run(speeds, rounds=ROUNDS, packets_per_round=PACKETS_PER_ROUND, verbose=True,
        delivery_mode="tuned"):
    """
    Runs DRL-EAURP across all `speeds`. Returns a flat list of normalized
    row dicts, one per speed.
    """
    import random as rng_module

    network_module = _isolated_import(ENGINE_DIR, "core.network")
    node_module = _isolated_import(ENGINE_DIR, "core.node")
    metrics_module = _isolated_import(ENGINE_DIR, "core.metrics")
    protocols_module = _isolated_import(ENGINE_DIR, "protocols.drl_eaurp")

    NetworkManager = network_module.NetworkManager
    Node = node_module.Node
    MetricsCollector = metrics_module.MetricsCollector
    estimate_first_node_death_round = metrics_module.estimate_first_node_death_round
    DRLEAURPEngine = protocols_module.DRLEAURPEngine

    rows = []
    for i, speed in enumerate(speeds):
        seed = BASE_SEED + i
        if verbose:
            print(f"[DRL-EAURP] speed={speed} m/s ...")
        summary = _run_single_speed(
            speed, NetworkManager, Node, MetricsCollector,
            estimate_first_node_death_round, DRLEAURPEngine, rng_module,
            rounds, packets_per_round, seed, delivery_mode,
        )
        if verbose:
            print(f"            -> PDR={summary['pdr_percent']:.2f}% "
                  f"delay={summary['avg_delay_ms']:.2f}ms "
                  f"throughput={summary['throughput_kbps']:.2f}kbps "
                  f"lifetime={summary['network_lifetime_rounds']} rounds")
        rows.append(normalize_row("DRL-EAURP", speed, summary))

    return rows
