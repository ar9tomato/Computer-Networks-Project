from collections import defaultdict
import random


class DRLEAURPEngine:
    EXPLOIT = 0
    EXPLORE = 1

    def __init__(self, network, alpha=0.1, gamma=0.9, epsilon=0.1,
                 seed=42, q_table=None):
        self.network = network
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.rng = random.Random(seed)
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

    def route_packet(self, source_node, dest_node, current_round):
        if not source_node.is_alive or not dest_node.is_alive:
            return False, 0.0, 0

        state = self.get_state()
        action = self.choose_action(state)

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
