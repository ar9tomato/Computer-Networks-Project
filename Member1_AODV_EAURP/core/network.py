"""
core/network.py

Defines the Network class, which owns the collection of Node objects,
drives the mobility model each round, computes Euclidean distances, and
rebuilds the neighbor table / connectivity graph based on the
transmission range R.
"""

import math
import random

from core.node import Node


class Network:
    """
    Represents the full MANET topology: a set of nodes deployed on a
    grid_width x grid_height meter grid, all moving with a shared speed
    scenario, connected whenever they are within transmission_range meters
    of one another (Euclidean distance check).
    """

    def __init__(self, num_nodes, grid_width, grid_height, transmission_range,
                 speed, energy_init=100.0, seed=None):
        self.num_nodes = num_nodes
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.transmission_range = transmission_range
        self.speed = speed
        self.energy_init = energy_init

        # A dedicated RNG instance keeps this network's randomness fully
        # independent from any other Network instance (e.g. the AODV vs
        # EAURP run for the same speed), which is required for a fair,
        # reproducible side-by-side comparison.
        self.rng = random.Random(seed)

        self.nodes = self._deploy_nodes()
        self.rebuild_topology()

    # ------------------------------------------------------------------
    # Deployment
    # ------------------------------------------------------------------
    def _deploy_nodes(self):
        nodes = []
        for node_id in range(self.num_nodes):
            x = self.rng.uniform(0, self.grid_width)
            y = self.rng.uniform(0, self.grid_height)
            node = Node(node_id, x, y, self.speed,
                        energy_init=self.energy_init, rng=self.rng)
            nodes.append(node)
        return nodes

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    @staticmethod
    def euclidean_distance(node_a, node_b):
        return math.hypot(node_a.x - node_b.x, node_a.y - node_b.y)

    def in_range(self, node_a, node_b):
        if not (node_a.alive and node_b.alive):
            return False
        return self.euclidean_distance(node_a, node_b) <= self.transmission_range

    # ------------------------------------------------------------------
    # Mobility + topology maintenance
    # ------------------------------------------------------------------
    def step_mobility(self):
        """Advance every alive node by one round of movement."""
        for node in self.nodes:
            node.move(self.grid_width, self.grid_height, self.rng)

    def rebuild_topology(self):
        """
        Rebuild every node's neighbor_table based on current positions and
        alive status. This is the single source of truth for connectivity
        used by the routing protocols for RREQ flooding / link-break
        detection.
        """
        alive_nodes = [n for n in self.nodes if n.alive]
        for node in self.nodes:
            node.neighbor_table = {}

        for i in range(len(alive_nodes)):
            for j in range(i + 1, len(alive_nodes)):
                a = alive_nodes[i]
                b = alive_nodes[j]
                dist = self.euclidean_distance(a, b)
                if dist <= self.transmission_range:
                    a.neighbor_table[b.node_id] = dist
                    b.neighbor_table[a.node_id] = dist

    def apply_idle_drain(self):
        """Apply the continuous baseline battery depletion for one round."""
        for node in self.nodes:
            node.drain_idle()

    def get_node(self, node_id):
        return self.nodes[node_id]

    def alive_nodes(self):
        return [n for n in self.nodes if n.alive]

    def alive_fraction(self):
        if not self.nodes:
            return 0.0
        return len(self.alive_nodes()) / len(self.nodes)

    def build_adjacency(self):
        """
        Returns dict: node_id -> set of neighbor node_ids, for currently
        alive nodes only. Used by the routing engines for RREQ flooding.
        """
        adjacency = {n.node_id: set(n.neighbor_table.keys())
                     for n in self.nodes if n.alive}
        return adjacency
