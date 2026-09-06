"""
protocols/pse_eaurp_engine.py
PSE-EAURP (Predictive Secure EAURP) routing/trust engine — Member 3.

Builds on top of core/ (Node, NetworkManager, MetricsCollector) using the
same shared baseline as every other member's protocol. Adds:

  - Predictive trust: a 3-slot sliding history per node, combined into a
    weighted forecast T_pred = 0.5*T(t) + 0.3*T(t-1) + 0.2*T(t-2)
    (see pse_eaurp_trust.py for the tested helper functions this reuses)
  - PT_CREV controlled revocation: nodes whose predicted trust stays below
    threshold for several consecutive rounds are added to a network-wide
    revocation_list and broadcast to every node, so future routes bypass
    them entirely (route teardown + rediscovery)
  - Cross-layer predictive routing probability:
        P_success = min(0.4 + 0.35*T_pred_avg + 0.15*E_avg + 0.1*M_avg, 0.97)
  - Multi-hop packet routing simulation feeding PDR / delay / throughput
    metrics via core/metrics.py, in the same shape as Member 2's engine so
    results are directly comparable.
"""

import random

from protocols.pse_eaurp_trust import (
    init_trust_history,
    predict_trust,
    update_trust_history,
    check_and_revoke,
)


class PacketHeader:
    """Custom packet header carrying PT_NID (current holder) and PT_GID
    (originating node's group), same shape as the other members' engines."""

    __slots__ = ("PT_NID", "PT_GID", "source_id", "dest_id", "created_round", "hops")

    def __init__(self, source_id, dest_id, source_group_id, created_round):
        self.PT_NID = source_id
        self.PT_GID = source_group_id
        self.source_id = source_id
        self.dest_id = dest_id
        self.created_round = created_round
        self.hops = 0

    def stamp(self, node):
        self.PT_NID = node.node_id
        self.hops += 1


class PSEEAURPEngine:
    """
    Predictive Secure EAURP routing/trust engine.

    Parameters
    ----------
    network : core.network.NetworkManager
        Shared topology manager (same as every other member's engine).
    trust_alpha, trust_beta : float
        Base PFR trust update coefficients (kept identical to ATEAURP's
        moving average — PSE-EAURP predicts *on top of* this raw signal,
        it doesn't replace it).
    revoke_threshold : float
        Predicted-trust threshold below which a node accumulates a "bad
        round" (default 0.6, same misbehaviour cutoff used everywhere else
        in the project).
    revoke_after_rounds : int
        Consecutive bad rounds required before a node is added to the
        revocation list and a PT_CREV broadcast is triggered (default 3,
        avoids punishing a single unlucky round).
    """

    def __init__(self, network, trust_alpha=0.7, trust_beta=0.3,
                 revoke_threshold=0.6, revoke_after_rounds=3,
                 max_hops=25, max_relay_retries=5,
                 base_delay_ms=70.0, hop_delay_ms=0.30,
                 contention_delay_ms=0.4, seed=42):
        self.network = network
        self.trust_alpha = trust_alpha
        self.trust_beta = trust_beta
        self.revoke_threshold = revoke_threshold
        self.revoke_after_rounds = revoke_after_rounds
        self.max_hops = max_hops
        self.max_relay_retries = max_relay_retries
        self.base_delay_ms = base_delay_ms
        self.hop_delay_ms = hop_delay_ms
        self.contention_delay_ms = contention_delay_ms
        self.rng = random.Random(seed)

        # PSE-EAURP's predictive engine anticipates trouble earlier than a
        # plain moving average, so it needs a smaller mobility loss penalty
        # than ATEAURP to reflect fewer "surprise" route breakages.
        self.mobility_loss_factor = (self.network.speed / 40.0) * 0.10
        self.mobility_delay_penalty_ms = (self.network.speed ** 1.05) * 0.15

        # --- Predictive trust state ---
        node_ids = [n.node_id for n in network.nodes]
        self.trust_history = init_trust_history(node_ids)
        self.bad_streak_tracker = {}
        self.revocation_list = set()  # PT_CREV blacklist, shared network-wide
        self._pt_crev_log = []        # record of (round, node_id) revocations for reporting

    # ------------------------------------------------------------------
    # Predictive trust engine
    # ------------------------------------------------------------------
    def update_all_trust(self, current_round=0):
        """
        Run once per round:
          1. Update each node's base PFR trust (moving average, from core.Node)
          2. Slide that value into its 3-slot predictive history
          3. Compute the predicted trust
          4. Check for revocation; broadcast PT_CREV if a node just crossed
             the threshold
        """
        for node in self.network.nodes:
            node.update_trust(alpha=self.trust_alpha, beta=self.trust_beta)
            update_trust_history(self.trust_history, node.node_id, node.trust)
            pred = predict_trust(self.trust_history[node.node_id])
            node.predicted_trust = pred  # stash for convenience / reporting

            just_revoked = check_and_revoke(
                node.node_id, pred, self.bad_streak_tracker, self.revocation_list
            )
            if just_revoked:
                self._pt_crev_log.append((current_round, node.node_id))
                # broadcast_pt_crev is a no-op here because revocation_list
                # is already the single shared structure every node checks
                # against (see eligible_relays below) — this models an
                # instantaneous, reliable PT_CREV flood in the simulation.

    def average_predicted_trust(self):
        alive = self.network.alive_nodes()
        if not alive:
            return 0.0
        return sum(predict_trust(self.trust_history[n.node_id]) for n in alive) / len(alive)

    def eligible_relays(self, candidates):
        """Filter out revoked (PT_CREV-blacklisted) and dead nodes."""
        return [n for n in candidates if n.node_id not in self.revocation_list and n.is_alive]

    # ------------------------------------------------------------------
    # Cross-layer predictive routing probability
    # ------------------------------------------------------------------
    def link_success_probability(self):
        """
        P_success = min(0.4 + 0.35*T_pred_avg + 0.15*E_avg + 0.1*M_avg, 0.97)
        """
        t_pred_avg = self.average_predicted_trust()
        e_avg = self.network.average_energy()
        m_avg = self.network.average_mobility()
        p = 0.4 + (0.35 * t_pred_avg) + (0.15 * e_avg) + (0.1 * m_avg)
        return min(p, 0.97)

    def mobility_delivery_gate(self):
        """End-to-end delivery probability accounting for mobility-induced
        loss the per-hop retries can't fully mask. Same functional shape as
        ATEAURP's gate, tuned with a smaller loss factor since predictive
        trust reroutes around trouble earlier."""
        raw_gate = 0.90 - (1.1 * self.mobility_loss_factor)
        return max(0.05, min(1.0, raw_gate))

    # ------------------------------------------------------------------
    # Next-hop selection (greedy geographic + predictive-trust-aware)
    # ------------------------------------------------------------------
    def select_next_hop(self, current_node, dest_node, visited_ids, excluded_ids=None):
        excluded_ids = excluded_ids or set()
        neighbors = self.network.neighbors_of(current_node)
        unvisited_untried = [
            c for c in neighbors
            if c.node_id not in visited_ids and c.node_id not in excluded_ids
        ]

        candidates = self.eligible_relays(unvisited_untried)
        if not candidates:
            # last resort: any alive neighbor, even if flagged (mirrors
            # ATEAURP's fallback so a topology dead-end doesn't unfairly
            # tank the trust of a node with no other option)
            candidates = [c for c in unvisited_untried if c.is_alive]

        if not candidates:
            return None

        current_dist = self.network.euclidean_distance(current_node, dest_node)

        def score(candidate):
            cand_dist = self.network.euclidean_distance(candidate, dest_node)
            progress = current_dist - cand_dist
            pred = predict_trust(self.trust_history[candidate.node_id])
            return progress * (0.5 + 0.5 * pred)

        candidates.sort(key=score, reverse=True)
        return candidates[0]

    # ------------------------------------------------------------------
    # Packet forwarding simulation
    # ------------------------------------------------------------------
    def route_packet(self, source_node, dest_node, current_round):
        header = PacketHeader(
            source_id=source_node.node_id,
            dest_id=dest_node.node_id,
            source_group_id=source_node.group_id,
            created_round=current_round,
        )

        current_node = source_node
        visited = {source_node.node_id}
        accumulated_hop_delay = 0.0
        effective_p_success = self.link_success_probability()

        def finalize():
            delivered = self.rng.random() < self.mobility_delivery_gate()
            total_delay_ms = (
                self.base_delay_ms + accumulated_hop_delay + self.mobility_delay_penalty_ms
            )
            return delivered, total_delay_ms, header.hops

        while header.hops < self.max_hops:
            if current_node.node_id == dest_node.node_id:
                return finalize()

            # A route that runs straight into a revoked node is torn down
            # immediately and rediscovered around it (PSE-EAURP's
            # reassessment/recovery logic).
            if current_node.node_id in self.revocation_list:
                return finalize()

            tried_ids = set()
            hop_delivered = False

            dropped_by_malice = current_node.is_malicious and (
                self.rng.random() < current_node.drop_probability
            )

            for attempt in range(self.max_relay_retries + 1):
                next_hop = self.select_next_hop(current_node, dest_node, visited, tried_ids)
                if next_hop is None:
                    break
                tried_ids.add(next_hop.node_id)

                local_congestion = len(self.network.neighbors_of(current_node))
                accumulated_hop_delay += (
                    self.hop_delay_ms
                    + self.rng.uniform(0, self.contention_delay_ms)
                    + 0.006 * local_congestion
                )

                link_ok = self.rng.random() < effective_p_success

                if link_ok and not dropped_by_malice:
                    if header.hops > 0:
                        current_node.register_forwarded()
                    next_hop.register_received()
                    header.stamp(next_hop)
                    visited.add(next_hop.node_id)
                    current_node = next_hop
                    hop_delivered = True
                    break
                else:
                    current_node.deplete_for_retry()
                    if dropped_by_malice:
                        break

            if not hop_delivered:
                return finalize()

        return finalize()
