"""
core/network.py
Network topology manager for the ATEAURP MANET simulation.

Responsible for:
  - Instantiating the node population on the deployment grid
  - Advancing the mobility model each round
  - Recomputing Euclidean-distance-based neighbor tables (transmission range check)
  - Providing network-wide averages (trust, energy, mobility) used by the
    cross-layer link-selection formula in protocols/ateaurp.py
"""

import math
from core.node import Node


class NetworkManager:
    """
    Owns the full set of nodes and the topology derived from their positions.

    Parameters
    ----------
    num_nodes : int
        Number of nodes to deploy (default 50, per Member 2 spec).
    grid_width, grid_height : float
        Deployment area dimensions in meters (default 1000 x 1000).
    tx_range : float
        Transmission range R in meters used for the Euclidean neighbor check.
    speed : float
        Node speed in m/s for this simulation run.
    num_groups : int
        Number of PT_GID groups nodes are partitioned into.
    seed : int
        RNG seed for reproducibility.
    """

    def __init__(self, num_nodes=50, grid_width=1000, grid_height=1000,
                 tx_range=250, speed=10, num_groups=5, malicious_probability=0.15,
                 seed=42):
        self.num_nodes = num_nodes
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.tx_range = tx_range
        self.speed = speed
        self.seed = seed

        self.nodes = [
            Node(
                node_id=i,
                group_id=i % num_groups,
                grid_width=grid_width,
                grid_height=grid_height,
                speed=speed,
                malicious_probability=malicious_probability,
                seed=seed,
            )
            for i in range(num_nodes)
        ]

        self.round_number = 0
        self.rebuild_topology()

    # ------------------------------------------------------------------
    # Distance / topology
    # ------------------------------------------------------------------
    @staticmethod
    def euclidean_distance(node_a, node_b):
        return math.hypot(node_a.x - node_b.x, node_a.y - node_b.y)

    def rebuild_topology(self):
        """
        Recomputes each node's neighbor table using the Euclidean distance
        threshold d_ij <= R (transmission range check).
        """
        for node in self.nodes:
            node.neighbor_table = {}

        for i, node_a in enumerate(self.nodes):
            for node_b in self.nodes[i + 1:]:
                dist = self.euclidean_distance(node_a, node_b)
                if dist <= self.tx_range:
                    node_a.neighbor_table[node_b.node_id] = dist
                    node_b.neighbor_table[node_a.node_id] = dist

    def advance_round(self, dt=1.0):
        """Move every alive node and rebuild the topology for this round."""
        self.round_number += 1
        for node in self.nodes:
            if node.is_alive:
                node.move(dt=dt)
            node.deplete_baseline()
        self.rebuild_topology()

    # ------------------------------------------------------------------
    # Network-wide aggregates (feed the cross-layer P_success formula)
    # ------------------------------------------------------------------
    def alive_nodes(self):
        return [n for n in self.nodes if n.is_alive]

    def average_trust(self):
        alive = self.alive_nodes()
        if not alive:
            return 0.0
        return sum(n.trust for n in alive) / len(alive)

    def average_energy(self):
        alive = self.alive_nodes()
        if not alive:
            return 0.0
        return sum(n.normalized_energy for n in alive) / len(alive)

    def average_mobility(self):
        alive = self.alive_nodes()
        if not alive:
            return 0.0
        return sum(n.mobility_factor for n in alive) / len(alive)

    def network_lifetime_exhausted(self):
        """Network lifetime ends when no alive nodes remain."""
        return len(self.alive_nodes()) == 0

    def get_node(self, node_id):
        return self.nodes[node_id]

    def neighbors_of(self, node):
        """Return list of live neighbor Node objects within transmission range."""
        return [self.nodes[nid] for nid in node.neighbor_table if self.nodes[nid].is_alive]
