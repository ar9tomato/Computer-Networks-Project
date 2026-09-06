"""
protocols/drl_eaurp.py
DRL-EAURP (Deep-RL-assisted EAURP) routing engine — Member 4.

Tabular Q-learning over a coarse (trust, energy, mobility) state, choosing
between an EXPLOIT and an EXPLORE relay-selection strategy.

delivery_mode
-------------
"tuned" (default) reproduces the original behaviour: no packet is ever
actually routed. `route_packet` draws hop count from `randint(3, 10)`, delay
from `uniform(20, 50)`, and decides delivery from

    p = 0.45 + 0.25*trust + 0.20*energy + 0.10*mobility (+0.08 exploit)
    p = clamp(p, 0.40, 0.98)

so the reported PDR is a property of those literals, not of the topology.

"simulated" routes the packet hop by hop across the real topology using the
same NetworkManager/Node API as ATEAURP and PSE-EAURP, and reports delivery
only if the packet actually arrived. The Q-learning agent is retained and now
has something real to control: its action selects the relay strategy at every
hop (EXPLOIT = greedy best next hop by trust/energy/geographic progress,
EXPLORE = sample among the viable candidates), and its reward becomes the
true delivery outcome instead of a coin flip it already knew the odds of.
"""

from collections import defaultdict
import math
import random

MAX_HOPS = 25
MAX_RELAY_RETRIES = 5
BASE_DELAY_MS = 74.0
HOP_DELAY_MS = 0.32
CONTENTION_DELAY_MS = 0.45


class DRLEAURPEngine:
    EXPLOIT = 0
    EXPLORE = 1

    # Reward weights. Delivery dominates, with smaller costs for a long path
    # and for energy spent, so the agent prefers short, cheap, successful
    # routes rather than merely successful ones.
    REWARD_DELIVERY = 15.0
    PENALTY_FAILURE = 5.0
    PENALTY_PER_HOP = 0.4
    PENALTY_ENERGY = 2.0

    def __init__(self, network, alpha=0.1, gamma=0.9, epsilon=0.1,
                 eval_epsilon=0.02, seed=42, q_table=None, delivery_mode="tuned"):
        if delivery_mode not in ("tuned", "simulated"):
            raise ValueError(f"unknown delivery_mode: {delivery_mode!r}")
        self.delivery_mode = delivery_mode
        self.network = network
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.rng = random.Random(seed)
        # Exploration schedule. The engine previously used a single epsilon
        # (0.1) for the whole run with no train/evaluate split, so 10% of
        # every reported routing decision was a deliberately random choice —
        # exploration noise was being measured as protocol performance.
        # MADRL-EAURP already separates a training phase from an evaluation
        # phase; this brings DRL-EAURP in line with that convention.
        self.train_epsilon = epsilon
        self.eval_epsilon = eval_epsilon
        self.evaluating = False
        self.q_table = q_table if q_table is not None else defaultdict(
            lambda: [0.0, 0.0]
        )
        self.last_state = None
        self.last_action = None
        self.last_reward = None

    def get_state(self):
        return (
            round(self.network.average_trust(), 1),
            round(self.network.average_energy(), 1),
            round(self.network.average_mobility(), 1),
        )

    def set_evaluation_mode(self, evaluating=True):
        """Switch between the training and evaluation exploration rates."""
        self.evaluating = evaluating
        self.epsilon = self.eval_epsilon if evaluating else self.train_epsilon

    def choose_action(self, state):
        if self.rng.random() < self.epsilon:
            return self.rng.randint(0, 1)

        q = self.q_table[state]
        return 0 if q[0] >= q[1] else 1

    def update_q(self, state, action, reward, next_state):
        best_next = max(self.q_table[next_state])
        old = self.q_table[state][action]
        self.q_table[state][action] = old + self.alpha * (
            reward + self.gamma * best_next - old
        )

    def base_success_probability(self):
        t = self.network.average_trust()
        e = self.network.average_energy()
        m = self.network.average_mobility()
        return 0.45 + 0.25 * t + 0.20 * e + 0.10 * m

    def success_probability(self, action):
        p = self.base_success_probability()
        p += 0.08 if action == self.EXPLOIT else 0.02
        return min(max(p, 0.40), 0.98)

    @staticmethod
    def adaptive_trust_update(node):
        if node.received == 0:
            return

        pfr = node.forwarded / node.received
        node.trust = 0.7 * node.trust + 0.3 * pfr
        node.trust = min(1.0, max(0.0, node.trust))

        if node.received > 5 and node.trust < 0.6:
            if hasattr(node, "is_isolated"):
                node.is_isolated = True

    def update_endpoint_trust(self, source_node, destination_node):
        source_node.forwarded += 1
        destination_node.received += 1
        self.adaptive_trust_update(source_node)
        self.adaptive_trust_update(destination_node)

    # ------------------------------------------------------------------
    # Simulated hop-by-hop routing
    # ------------------------------------------------------------------
    def _candidate_score(self, current_node, candidate, dest_node):
        """Trust-weighted, energy-aware geographic progress. Higher is better."""
        here = math.dist((current_node.x, current_node.y), (dest_node.x, dest_node.y))
        there = math.dist((candidate.x, candidate.y), (dest_node.x, dest_node.y))
        progress = (here - there) / max(self.network.tx_range, 1.0)
        return (2.0 * progress) + (0.8 * candidate.trust) + (0.6 * candidate.normalized_energy)

    def _select_next_hop(self, current_node, dest_node, visited, tried_ids, action):
        """
        Pick the next relay. The Q-learning action chooses the strategy:
        EXPLOIT takes the highest-scoring viable neighbour, EXPLORE samples
        among them so the agent can discover routes greedy selection misses.
        """
        candidates = [
            n for n in self.network.neighbors_of(current_node)
            if n.is_alive
            and n.node_id not in visited
            and n.node_id not in tried_ids
            and not getattr(n, "is_isolated", False)
        ]
        if not candidates:
            return None
        if dest_node in candidates:
            return dest_node
        if action == self.EXPLORE:
            weights = [max(self._candidate_score(current_node, c, dest_node), 0.01)
                       for c in candidates]
            return self.rng.choices(candidates, weights=weights, k=1)[0]
        return max(candidates, key=lambda c: self._candidate_score(current_node, c, dest_node))

    def _route_simulated(self, source_node, dest_node, action):
        """Route one packet across the real topology. Returns (delivered, delay_ms, hops)."""
        current_node = source_node
        visited = {source_node.node_id}
        hops = 0
        accumulated_delay = 0.0

        while hops < MAX_HOPS:
            if current_node.node_id == dest_node.node_id:
                return True, BASE_DELAY_MS + accumulated_delay, hops

            tried_ids = set()
            hop_delivered = False

            # A malicious forwarder's decision to withhold is a property of
            # that node, so roll it once per hop position rather than per
            # retry (matching ATEAURP's treatment).
            dropped_by_malice = current_node.is_malicious and (
                self.rng.random() < current_node.drop_probability
            )

            for _ in range(MAX_RELAY_RETRIES + 1):
                next_hop = self._select_next_hop(
                    current_node, dest_node, visited, tried_ids, action)
                if next_hop is None:
                    break
                tried_ids.add(next_hop.node_id)

                congestion = len(self.network.neighbors_of(current_node))
                accumulated_delay += (
                    HOP_DELAY_MS
                    + self.rng.uniform(0, CONTENTION_DELAY_MS)
                    + 0.007 * congestion
                )

                link_ok = self.rng.random() < self.base_success_probability()

                if link_ok and not dropped_by_malice:
                    if hops > 0:
                        current_node.register_forwarded()
                    # R_i counts packets received *for forwarding*. The
                    # DESTINATION of a packet has no forwarding duty — the
                    # route ends there — so crediting it with a receipt it can
                    # never discharge drives PFR_i = F_i / R_i toward zero for
                    # every well-behaved node in the network.
                    #
                    # This was the dominant trust bug: with random src/dst over
                    # 50 nodes and 4,000 packets, each node is the destination
                    # ~80 times, so benign nodes ended a run at received=86,
                    # forwarded=1 (PFR 0.012) — statistically indistinguishable
                    # from a black-hole node at PFR 0.000. That is why 26-36%
                    # of BENIGN nodes were being permanently blacklisted.
                    if next_hop.node_id != dest_node.node_id:
                        next_hop.register_received()
                    current_node.deplete_for_forward()
                    visited.add(next_hop.node_id)
                    current_node = next_hop
                    hops += 1
                    hop_delivered = True
                    break

                current_node.deplete_for_retry()
                if dropped_by_malice:
                    break

            if not hop_delivered:
                return False, BASE_DELAY_MS + accumulated_delay, hops

        return False, BASE_DELAY_MS + accumulated_delay, hops

    def route_packet(self, source_node, dest_node, current_round):
        if not source_node.is_alive or not dest_node.is_alive:
            return False, 0.0, 0

        state = self.get_state()
        action = self.choose_action(state)

        if self.delivery_mode == "simulated":
            energy_before = self.network.average_energy()
            success, delay, hops = self._route_simulated(source_node, dest_node, action)
            energy_after = self.network.average_energy()

            if success:
                reward = (self.REWARD_DELIVERY
                          - self.PENALTY_PER_HOP * hops
                          - self.PENALTY_ENERGY * max(energy_before - energy_after, 0.0))
            else:
                reward = -(self.PENALTY_FAILURE + self.PENALTY_PER_HOP * hops)
                delay = 0.0

            self.update_endpoint_trust(source_node, dest_node)
            next_state = self.get_state()
            self.update_q(state, action, reward, next_state)

            self.last_state = state
            self.last_action = action
            self.last_reward = reward
            _ = current_round
            return success, delay, hops

        # ---- legacy "tuned" path: no packet is actually routed ----
        # Same packet/hop ranges as the supplied notebook.
        packet_size = self.rng.randint(512, 1024)
        hops = self.rng.randint(3, 10)

        success = self.rng.random() < self.success_probability(action)

        if success:
            delay = self.rng.uniform(20.0, 50.0) + (
                hops * self.rng.uniform(4.0, 10.0)
            )
            reward = 1
        else:
            delay = 0.0
            reward = -1

        self.update_endpoint_trust(source_node, dest_node)

        next_state = self.get_state()
        self.update_q(state, action, reward, next_state)

        self.last_state = state
        self.last_action = action
        self.last_reward = reward

        _ = packet_size
        _ = current_round
        return success, delay, hops

    def action_name(self, action):
        return "EXPLOITATION" if action == 0 else "EXPLORATION"

    def q_values(self, state=None):
        if state is None:
            state = self.get_state()
        return tuple(self.q_table[state])

    def learned_state_count(self):
        return len(self.q_table)
