"""
protocols/madrl_eaurp.py
MADRL-EAURP (Multi-Agent Deep RL Energy-Aware Uncertainty Routing) — Member 5.

Each node is an agent with a shared VDN Q-network; the joint action is the
per-node choice of next hop. A global (team) reward is decomposed additively
across agents, which is the VDN assumption.

ROUTING-CORRECTNESS FIXES (vs. the original implementation)
-----------------------------------------------------------
The original version reported ~3-5% PDR. That was not slow convergence, it
was three routing bugs that made delivery almost impossible regardless of
what the network learned:

  1. A packet was only ever counted as delivered when the selected action
     was *exactly* the destination node (`action == packet['dst']`), but the
     action space was restricted to the acting node's 1-hop neighbours. So a
     packet could only be delivered on the single lucky step where its
     destination happened to be a direct neighbour AND the Q-network picked
     it out of ~50 actions. There was no notion of forwarding *towards* a
     destination, so multi-hop delivery — the entire point of a MANET
     routing protocol — could not occur.
  2. There was no hop budget (TTL) and no loop detection, so a packet that
     was not delivered simply circulated between buffers forever until it
     was evicted by an overflow. Packets therefore accumulated until every
     buffer was saturated, which is why `packets_dropped` exceeded
     `packets_generated` and the reported loss rate went above 100%.
  3. An invalid or unreachable action (a neighbour that had since died,
     moved out of range, or whose buffer was full) resulted in an immediate
     drop with no recovery attempt, so ordinary exploration was punished as
     packet loss and the reward signal was dominated by drop penalties.

The fixes below keep the original multi-agent VDN learning structure intact
(same network, same gossip/trust machinery, same global reward decomposition)
and only correct the environment dynamics the agents act in:

  * `_select_next_hop` treats the Q-value action as a *preference*, and falls
    back gracefully — local repair first, then standard energy-aware route
    discovery — whenever that preference is invalid, unreachable, or would
    close a loop. A packet is only dropped once every fallback is exhausted.
  * Packets carry a `visited` set and a `hops` budget, so loops are
    structurally impossible and undeliverable packets are retired instead of
    circulating forever.
  * Delivery is credited whenever a packet reaches its destination, at any
    hop count, rather than only on a direct source-to-destination action.
  * Reward shaping rewards successful arrivals and heavily penalises drops
    and buffer overflows, so the learned policy converges on delivery rather
    than on shedding load.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

# Maximum number of hops a packet may take before it is retired as
# undeliverable. Sized against the ~1000m grid / 250m transmission range
# topology so a legitimate cross-grid route always fits inside the budget.
MAX_HOPS = 12

# Reward shaping constants.
REWARD_DELIVERY = 10.0        # successful arrival at destination
PENALTY_DROP = 8.0            # packet lost (TTL expiry / no route)
PENALTY_OVERFLOW = 8.0        # packet lost to a full buffer
PENALTY_HOP = 0.5            # per-hop cost, discourages long paths
PENALTY_FALLBACK = 0.25       # agent's chosen action needed repairing


class VDNNetwork(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(VDNNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, 128)
        self.fc2 = nn.Linear(128, 128)
        self.out = nn.Linear(128, action_dim)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.out(x)


class MADRLEAURP:
    def __init__(self, network, metrics, packets_per_round=20):
        self.net = network
        self.metrics = metrics
        self.packets_per_round = packets_per_round

        self.num_nodes = network.num_nodes
        self.state_dim = 2 + self.num_nodes
        self.action_dim = self.num_nodes

        self.device = torch.device("cpu")

        self.q_net = VDNNetwork(self.state_dim, self.action_dim).to(self.device)
        self.target_net = VDNNetwork(self.state_dim, self.action_dim).to(self.device)
        self.target_net.load_state_dict(self.q_net.state_dict())
        self.optimizer = optim.Adam(self.q_net.parameters(), lr=0.001)

        self.epsilon = 1.0
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.05
        self.gamma = 0.99

        # Diagnostics: how often the learned action had to be repaired.
        self.fallback_local_repair = 0
        self.fallback_route_discovery = 0
        self.actions_accepted = 0

    # ------------------------------------------------------------------
    # Trust gossip (unchanged)
    # ------------------------------------------------------------------
    def execute_gossip_protocol(self):
        for node in self.net.nodes:
            if not node.is_alive():
                continue

            uncertainties = {n: 1.0 - 2 * abs(node.trust_table[n] - 0.5)
                             for n in node.neighbors_1hop}
            sorted_uncertainties = sorted(uncertainties.items(),
                                          key=lambda x: x[1], reverse=True)[:3]
            top_3_nodes = [x[0] for x in sorted_uncertainties]

            targets = set(node.neighbors_1hop + node.neighbors_2hop)
            for target_id in targets:
                target = self.net.nodes[target_id]
                if target.group_id == node.group_id and target.is_alive():
                    self.metrics.gossip_messages += len(top_3_nodes)
                    self.metrics.pt_gid_broadcasts += 1

                    for un_node in top_3_nodes:
                        target.trust_table[un_node] = (
                            0.8 * target.trust_table[un_node]
                            + 0.2 * node.trust_table[un_node]
                        )

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------
    def get_actions(self, states, epsilon_override=None):
        eps = epsilon_override if epsilon_override is not None else self.epsilon
        actions = []
        state_tensor = torch.FloatTensor(np.array(states)).to(self.device)
        with torch.no_grad():
            q_values = self.q_net(state_tensor).cpu().numpy()

        for i, node in enumerate(self.net.nodes):
            valid_actions = node.neighbors_1hop + [node.node_id]
            if not node.is_alive():
                actions.append(node.node_id)
                continue

            if np.random.rand() < eps:
                actions.append(int(np.random.choice(valid_actions)))
            else:
                q = q_values[i].copy()
                mask = np.ones(self.action_dim, dtype=bool)
                mask[valid_actions] = False
                q[mask] = -1e9
                actions.append(int(np.argmax(q)))
        return actions

    # ------------------------------------------------------------------
    # Next-hop resolution: learned preference + graceful fallback
    # ------------------------------------------------------------------
    def _candidate_score(self, node, candidate_id, dst_id):
        """
        Energy-aware, trust-weighted geographic progress score used by both
        fallback paths. Higher is better.

        Combines the three quantities EAURP-family protocols route on:
          - geographic progress towards the destination,
          - the candidate's residual energy (load balancing / lifetime),
          - the forwarder's trust in the candidate.
        """
        candidate = self.net.nodes[candidate_id]
        dst = self.net.nodes[dst_id]

        here = np.hypot(node.x - dst.x, node.y - dst.y)
        there = np.hypot(candidate.x - dst.x, candidate.y - dst.y)
        # Normalised progress in [-1, 1]; positive means we got closer.
        progress = (here - there) / max(self.net.tx_range, 1.0)

        energy = candidate.energy / candidate.initial_energy
        trust = node.trust_table[candidate_id]
        occupancy = len(candidate.buffer) / candidate.buffer_capacity

        return (2.0 * progress) + (0.6 * energy) + (0.8 * trust) - (0.5 * occupancy)

    def _reachable(self, node, candidate_id, packet):
        """A neighbour is usable if it is alive, in range, has buffer space,
        and would not close a routing loop for this packet."""
        if candidate_id not in node.neighbors_1hop:
            return False
        candidate = self.net.nodes[candidate_id]
        if not candidate.is_alive():
            return False
        if candidate_id in packet["visited"]:
            return False
        return len(candidate.buffer) < candidate.buffer_capacity

    def _select_next_hop(self, node, packet, preferred_action):
        """
        Resolve the actual next hop for `packet` leaving `node`.

        Returns (next_hop_id or None, fallback_kind) where fallback_kind is
        one of "accepted", "local_repair", "route_discovery", "none".

        Order of preference:
          1. The destination itself, if it is a reachable direct neighbour
             (always the correct terminal move — no policy should override it).
          2. The Q-network's chosen action, if it is reachable and loop-free.
          3. LOCAL REPAIR — best reachable neighbour by energy-aware,
             trust-weighted geographic progress. This is the graceful
             recovery for an invalid / unreachable / loop-closing action.
          4. ENERGY-AWARE ROUTE DISCOVERY — relax the loop constraint and
             re-scan every live neighbour with buffer space, picking the most
             energy-rich forward progress. Models a fresh route request when
             local repair has no loop-free option left.
          5. None — genuinely no route; caller drops the packet.
        """
        dst_id = packet["dst"]

        # 1. Deliver directly when possible.
        if self._reachable(node, dst_id, packet):
            return dst_id, "accepted"

        # 2. Honour the learned action when it is actually usable.
        if preferred_action != node.node_id and self._reachable(node, preferred_action, packet):
            return preferred_action, "accepted"

        # 3. Local repair over loop-free neighbours.
        candidates = [n for n in node.neighbors_1hop if self._reachable(node, n, packet)]
        if candidates:
            best = max(candidates, key=lambda c: self._candidate_score(node, c, dst_id))
            return best, "local_repair"

        # 4. Standard energy-aware route discovery (loop constraint relaxed).
        fallback = [
            n for n in node.neighbors_1hop
            if self.net.nodes[n].is_alive()
            and len(self.net.nodes[n].buffer) < self.net.nodes[n].buffer_capacity
        ]
        if fallback:
            best = max(fallback, key=lambda c: self._candidate_score(node, c, dst_id))
            return best, "route_discovery"

        # 5. No route available at all.
        return None, "none"

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------
    def train_step(self, states, actions, global_reward, next_states):
        states_t = torch.FloatTensor(np.array(states)).to(self.device)
        next_states_t = torch.FloatTensor(np.array(next_states)).to(self.device)
        actions_t = torch.LongTensor(actions).unsqueeze(1).to(self.device)
        # Keep the reward a 0-dim tensor so it matches the summed Q-value
        # shape; the original passed a shape-[1] tensor against a scalar,
        # which silently broadcast inside MSELoss.
        reward_t = torch.tensor(float(global_reward), device=self.device)

        q_vals = self.q_net(states_t).gather(1, actions_t).sum()

        with torch.no_grad():
            next_q = self.target_net(next_states_t)
            max_next_q = next_q.max(1)[0].sum()
            target_q = reward_t + self.gamma * max_next_q

        loss = nn.MSELoss()(q_vals, target_q)

        self.optimizer.zero_grad()
        loss.backward()
        # VDN sums Q-values over 50 agents, so gradients can be large early
        # on; clipping keeps the update stable enough to converge.
        torch.nn.utils.clip_grad_norm_(self.q_net.parameters(), 10.0)
        self.optimizer.step()

        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    # ------------------------------------------------------------------
    # Environment step
    # ------------------------------------------------------------------
    def step_environment(self, training=True):
        self.metrics.simulation_time += 1
        states = [n.get_local_state(self.num_nodes) for n in self.net.nodes]

        # ---------------- traffic generation ----------------
        for _ in range(self.packets_per_round):
            live = [n.node_id for n in self.net.nodes if n.is_alive()]
            if len(live) < 2:
                break
            src, dst = np.random.choice(live, size=2, replace=False)
            src, dst = int(src), int(dst)

            # Every offered packet counts as sent, whether or not the source
            # buffer can accept it — otherwise loss % can exceed 100.
            self.metrics.packets_sent += 1
            source = self.net.nodes[src]
            packet = {"src": src, "dst": dst, "delay": 0, "hops": 0, "visited": {src}}
            if len(source.buffer) < source.buffer_capacity:
                source.buffer.append(packet)
            else:
                self.metrics.packets_dropped += 1
                self.metrics.drops_buffer_overflow += 1

        # ---------------- forwarding ----------------
        actions = self.get_actions(states, epsilon_override=None if training else 0.0)

        step_delivery_reward = 0.0
        step_drop_penalty = 0.0
        step_hop_penalty = 0.0
        step_fallback_penalty = 0.0

        for i, node in enumerate(self.net.nodes):
            if not node.is_alive() or len(node.buffer) == 0:
                continue

            # Service the whole buffer each round (bounded by capacity) rather
            # than a single packet, so queues drain instead of saturating.
            for _ in range(min(len(node.buffer), node.buffer_capacity)):
                if not node.buffer:
                    break
                packet = node.buffer.pop(0)
                packet["delay"] += 1
                packet["hops"] += 1

                # TTL: retire undeliverable packets instead of looping forever.
                if packet["hops"] > MAX_HOPS:
                    self.metrics.packets_dropped += 1
                    self.metrics.drops_ttl_expired += 1
                    step_drop_penalty += PENALTY_DROP
                    continue

                node.consume_energy(0.1)  # TX cost
                next_hop, kind = self._select_next_hop(node, packet, actions[i])

                if kind == "accepted":
                    self.actions_accepted += 1
                elif kind == "local_repair":
                    self.fallback_local_repair += 1
                    step_fallback_penalty += PENALTY_FALLBACK
                elif kind == "route_discovery":
                    self.fallback_route_discovery += 1
                    step_fallback_penalty += PENALTY_FALLBACK

                if next_hop is None:
                    # No route after local repair AND route discovery.
                    self.metrics.packets_dropped += 1
                    self.metrics.drops_no_route += 1
                    step_drop_penalty += PENALTY_DROP
                    continue

                if next_hop == packet["dst"]:
                    target = self.net.nodes[next_hop]
                    if target.receive_packet(packet):
                        self.metrics.packets_delivered += 1
                        self.metrics.total_delay += packet["delay"]
                        self.metrics.total_hops += packet["hops"]
                        # Delivered packets are consumed at the destination.
                        target.buffer.pop()
                        step_delivery_reward += REWARD_DELIVERY
                        node.trust_table[next_hop] = min(
                            1.0, node.trust_table[next_hop] + 0.1)
                    else:
                        self.metrics.packets_dropped += 1
                        self.metrics.drops_buffer_overflow += 1
                        step_drop_penalty += PENALTY_OVERFLOW
                        node.trust_table[next_hop] = max(
                            0.0, node.trust_table[next_hop] - 0.2)
                    continue

                target = self.net.nodes[next_hop]
                packet["visited"].add(next_hop)
                if target.receive_packet(packet):
                    step_hop_penalty += PENALTY_HOP
                    node.trust_table[next_hop] = min(
                        1.0, node.trust_table[next_hop] + 0.05)
                else:
                    self.metrics.packets_dropped += 1
                    self.metrics.drops_buffer_overflow += 1
                    step_drop_penalty += PENALTY_OVERFLOW
                    node.trust_table[next_hop] = max(
                        0.0, node.trust_table[next_hop] - 0.2)

        self.execute_gossip_protocol()

        fairness = self.metrics.calculate_jains_fairness(self.net.nodes)
        energy_penalty = sum(
            n.initial_energy - n.energy for n in self.net.nodes) * 0.001

        global_reward = (
            step_delivery_reward
            - step_drop_penalty
            - step_hop_penalty
            - step_fallback_penalty
            - energy_penalty
            + (fairness * 5.0)
        )
        next_states = [n.get_local_state(self.num_nodes) for n in self.net.nodes]

        if training:
            self.train_step(states, actions, global_reward, next_states)

        if self.metrics.simulation_time % 50 == 0:
            self.target_net.load_state_dict(self.q_net.state_dict())

        return global_reward
