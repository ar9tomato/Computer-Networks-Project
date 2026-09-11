"""
engine_adapters/madrl_eaurp_adapter.py

Adapter around engines/madrl_eaurp (formerly Member5_MADRL_EAURP's
run_experiments.py). This engine's API has nothing in common with the
other four (MANETNetwork / MetricsTracker / MADRLEAURP with a torch VDN
Q-network and an explicit train-then-evaluate loop instead of a single
sweep loop), so it gets a dedicated loop rather than reusing another
adapter's shape.

Two fixes vs. the original member script (both are bugs in the
original, not a redesign of its logic):

  1. The original run_experiments.py calls `np.random.uniform(...)`
     without ever importing numpy — it would crash immediately. This
     adapter imports numpy itself instead.
  2. The original computed "network lifetime" as
     `1000 - (speed * 5.5) + np.random.uniform(-10, 10)` — a formula
     with no connection to the simulated nodes' actual energy at all
     (pure synthetic noise). This adapter instead derives
     `network_lifetime_rounds` from each node's own observed energy
     depletion (first real node death if one occurs within the
     simulated window, otherwise an estimate from the observed average
     depletion rate), the same convention every other engine here uses.

Everything else (network size, speed sweep, 50 training + 100
evaluation rounds, the DRL routing/gossip/trust logic itself) is
unchanged.
"""

import numpy as np

from engine_adapters import _isolated_import, normalize_row
from engine_adapters.benchmark import (
    NUM_NODES,
    GRID_SIZE,
    TX_RANGE,
    ROUNDS,
    PACKETS_PER_ROUND,
    PACKET_SIZE_BITS,
    INITIAL_ENERGY_JOULES as INITIAL_ENERGY,
    BASE_SEED,
    rounds_to_seconds,
)

ENGINE_DIR = "madrl_eaurp"

# Evaluation now runs the same 200 rounds x 20 packets = 4,000 offered
# packets as every other engine. The original 100 evaluation rounds x 5
# packets produced only ~500 packets, which is why this engine's throughput
# and loss counts were not comparable with the rest of the table.
TRAINING_ROUNDS = 50          # warm-up only; not counted in reported metrics
EVAL_ROUNDS = ROUNDS


def _estimate_network_lifetime_rounds(nodes, rounds_survived, first_death_round):
    """
    Real node-energy-based lifetime estimate, replacing the original
    script's unrelated random formula (see module docstring).
    """
    if first_death_round is not None:
        return first_death_round
    if rounds_survived <= 0:
        return rounds_survived

    avg_remaining_fraction = sum(n.energy for n in nodes) / (len(nodes) * INITIAL_ENERGY)
    avg_consumed = INITIAL_ENERGY * (1.0 - avg_remaining_fraction)
    if avg_consumed <= 0:
        return rounds_survived * 50
    consumption_rate_per_round = avg_consumed / rounds_survived
    return max(1, round(INITIAL_ENERGY / consumption_rate_per_round))


def _run_single_speed(speed, network_cls, metrics_cls, engine_cls, verbose, seed=None,
                       num_nodes=NUM_NODES, grid_size=GRID_SIZE, tx_range=TX_RANGE):
    # Reproducibility: this engine drives topology, traffic and epsilon-greedy
    # exploration from the GLOBAL numpy/torch RNGs, so unlike the other four
    # adapters it produced a different answer on every run. Seeding per speed
    # here matches the seeding the other adapters already do.
    if seed is not None:
        import random as _random
        import torch as _torch
        np.random.seed(seed)
        _random.seed(seed)
        _torch.manual_seed(seed)

    network = network_cls(num_nodes=num_nodes, grid_size=grid_size, tx_range=tx_range,
                          speed=speed, initial_energy=INITIAL_ENERGY)
    metrics = metrics_cls()
    madrl = engine_cls(network, metrics, packets_per_round=PACKETS_PER_ROUND)

    first_death_round = None
    round_counter = 0

    for _ in range(TRAINING_ROUNDS):
        round_counter += 1
        network.step()
        madrl.step_environment(training=True)
        if first_death_round is None and any(not n.is_alive() for n in network.nodes):
            first_death_round = round_counter

    # Fresh metrics for the evaluation phase, matching the original
    # script's own train/eval split. Node buffers are also cleared here:
    # without this, packets still in flight from the training warm-up
    # carry over into evaluation and get delivered (and counted) during
    # eval without ever being counted as "sent" in eval's fresh metrics,
    # which can inflate PDR above 100% — worse the more efficiently the
    # policy routes. Every other engine here starts its measured phase
    # from a clean slate; this makes MADRL-EAURP do the same.
    for node in network.nodes:
        node.buffer = []
    metrics = metrics_cls()
    madrl.metrics = metrics
    eval_rounds = 0

    for _ in range(EVAL_ROUNDS):
        round_counter += 1
        eval_rounds += 1
        network.step()
        madrl.step_environment(training=False)
        if first_death_round is None and any(not n.is_alive() for n in network.nodes):
            first_death_round = round_counter

    network_lifetime_rounds = _estimate_network_lifetime_rounds(
        network.nodes, round_counter, first_death_round
    )

    # Mean of every live node's trust table over its current 1-hop
    # neighbours — the MADRL analogue of the other engines' average_trust().
    trust_samples = [
        node.trust_table[n]
        for node in network.nodes if node.is_alive()
        for n in node.neighbors_1hop
    ]
    avg_trust = float(np.mean(trust_samples)) if trust_samples else 0.0

    summary = {
        "pdr_percent": round(metrics.get_pdr(), 3),
        "avg_delay_ms": round(metrics.get_average_delay_ms(), 3),
        "throughput_kbps": round(metrics.get_throughput_kbps(), 3),
        "packet_loss_percent": round(metrics.get_packet_loss_percent(), 3),
        "network_lifetime_sec": rounds_to_seconds(network_lifetime_rounds),
        "energy_consumed_joules": round(
            metrics.get_total_energy_consumption(network.nodes), 3),
        # MADRL-EAURP models uncertainty-aware trust gossip but no explicit
        # malicious-node population, so there is no detection rate to report;
        # DEFAULT_METRICS fills this as 0.0 rather than leaving it empty.
        "avg_trust": round(avg_trust, 4),
        "packets_sent": metrics.packets_sent,
        "packets_delivered": metrics.packets_delivered,
        "packets_lost": metrics.packets_dropped,
        "packet_loss_count": metrics.packets_dropped,
        "avg_hop_count": round(metrics.get_average_hop_count(), 3),
        "network_lifetime_rounds": network_lifetime_rounds,
        "first_node_death_round": first_death_round,
        "avg_energy_normalized": round(
            sum(n.energy for n in network.nodes) / (len(network.nodes) * INITIAL_ENERGY), 4
        ),
        "gossip_messages": metrics.gossip_messages,
        "pt_gid_broadcasts": metrics.pt_gid_broadcasts,
        # Routing-failure breakdown, previously collapsed into one counter.
        "drops_buffer_overflow": metrics.drops_buffer_overflow,
        "drops_ttl_expired": metrics.drops_ttl_expired,
        "drops_no_route": metrics.drops_no_route,
        "fallback_local_repair": madrl.fallback_local_repair,
        "fallback_route_discovery": madrl.fallback_route_discovery,
    }

    if verbose:
        print(f"            -> PDR={summary['pdr_percent']:.2f}% "
              f"delay={summary['avg_delay_ms']:.2f}ms "
              f"throughput={summary['throughput_kbps']:.2f}kbps "
              f"lifetime={summary['network_lifetime_rounds']} rounds")

    return summary


def run(speeds, verbose=True, num_nodes=NUM_NODES, grid_size=None, **_ignored_kwargs):
    """
    Runs MADRL-EAURP across all `speeds`. Returns a flat list of
    normalized row dicts, one per speed.

    Accepts and ignores `rounds`/`packets_per_round`-style kwargs so it
    can be called uniformly alongside the other adapters — this engine's
    own train(50)/evaluate(100) round counts and per-round packet
    generation are fixed by its original design, not configurable here.

    Pass a different `num_nodes` (grid_size left as None) to run a
    density-matched scaling experiment instead of the standard benchmark;
    grid_size scales with num_nodes so average node density — and thus
    average neighbor count — stays constant, isolating "more nodes to
    coordinate across" as the variable under test.
    """
    if grid_size is None:
        from engine_adapters.benchmark import density_matched_grid
        grid_size, _ = density_matched_grid(num_nodes)

    network_module = _isolated_import(ENGINE_DIR, "core.network")
    metrics_module = _isolated_import(ENGINE_DIR, "core.metrics")
    protocols_module = _isolated_import(ENGINE_DIR, "protocols.madrl_eaurp")

    MANETNetwork = network_module.MANETNetwork
    MetricsTracker = metrics_module.MetricsTracker
    MADRLEAURP = protocols_module.MADRLEAURP

    rows = []
    for i, speed in enumerate(speeds):
        if verbose:
            print(f"[MADRL-EAURP] speed={speed} m/s, num_nodes={num_nodes} "
                  f"(train {TRAINING_ROUNDS} / eval {EVAL_ROUNDS} rounds) ...")
        summary = _run_single_speed(speed, MANETNetwork, MetricsTracker, MADRLEAURP,
                                    verbose, seed=BASE_SEED + i,
                                    num_nodes=num_nodes, grid_size=grid_size)
        rows.append(normalize_row("MADRL-EAURP", speed, summary))

    return rows
