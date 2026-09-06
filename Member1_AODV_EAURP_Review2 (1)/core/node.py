"""
core/node.py

Defines the Node class used across the MANET simulation. A Node models a
single mobile device with a position, velocity, and battery energy. Nodes
also maintain a live neighbor table, which is rebuilt every simulation
round by core.network.Network based on the transmission range.
"""

import math
import random


class Node:
    """
    Represents a single mobile ad-hoc network (MANET) node.

    Attributes:
        node_id (int): Unique identifier for the node.
        x, y (float): Current 2D position in meters.
        speed (float): Movement speed in m/s (constant per experiment run,
            drawn from the speed scenario being tested, e.g. 10/20/30/40).
        direction (float): Current heading in radians. Updated using a
            random-waypoint-style mobility model.
        energy_init (float): Initial (maximum) battery energy in Joules.
        energy (float): Residual (current) battery energy in Joules.
        alive (bool): False once energy has been fully depleted.
        neighbor_table (dict): Maps neighbor_id -> distance (meters) for all
            nodes currently within transmission range. Rebuilt each round.
    """

    # Energy cost constants (Joules). These are intentionally small so a
    # node can survive many simulation rounds, but will eventually deplete
    # under continuous baseline drain plus per-transmission/reception costs.
    IDLE_DRAIN_PER_ROUND = 0.03
    TX_COST = 0.35
    RX_COST = 0.25
    FORWARD_COST = TX_COST + RX_COST

    def __init__(self, node_id, x, y, speed, energy_init=100.0, rng=None):
        self.node_id = node_id
        self.x = x
        self.y = y
        self.speed = speed
        self.energy_init = energy_init
        self.energy = energy_init
        self.alive = True
        self.neighbor_table = {}

        rng = rng or random
        self.direction = rng.uniform(0, 2 * math.pi)

    # ------------------------------------------------------------------
    # Mobility
    # ------------------------------------------------------------------
    def move(self, grid_width, grid_height, rng, direction_change_prob=0.15):
        """
        Advance the node's position by one simulation round using a
        random-waypoint-style mobility model: the node mostly keeps moving
        in its current direction, occasionally picking a new random
        direction, and bounces off the boundaries of the deployment grid.
        """
        if not self.alive:
            return

        if rng.random() < direction_change_prob:
            self.direction = rng.uniform(0, 2 * math.pi)

        dx = self.speed * math.cos(self.direction)
        dy = self.speed * math.sin(self.direction)

        new_x = self.x + dx
        new_y = self.y + dy

        # Bounce off boundaries so nodes stay within the deployment grid.
        if new_x < 0:
            new_x = -new_x
            self.direction = math.pi - self.direction
        elif new_x > grid_width:
            new_x = 2 * grid_width - new_x
            self.direction = math.pi - self.direction

        if new_y < 0:
            new_y = -new_y
            self.direction = -self.direction
        elif new_y > grid_height:
            new_y = 2 * grid_height - new_y
            self.direction = -self.direction

        self.x = min(max(new_x, 0.0), grid_width)
        self.y = min(max(new_y, 0.0), grid_height)

    # ------------------------------------------------------------------
    # Energy model
    # ------------------------------------------------------------------
    def drain_idle(self):
        """Apply continuous baseline battery depletion for one round."""
        if not self.alive:
            return
        self._consume(self.IDLE_DRAIN_PER_ROUND)

    def drain_forwarding(self):
        """Apply the energy cost of forwarding (rx + tx) one packet."""
        if not self.alive:
            return
        self._consume(self.FORWARD_COST)

    def drain_tx(self):
        if not self.alive:
            return
        self._consume(self.TX_COST)

    def drain_rx(self):
        if not self.alive:
            return
        self._consume(self.RX_COST)

    def _consume(self, amount):
        self.energy -= amount
        if self.energy <= 0:
            self.energy = 0.0
            self.alive = False

    def normalized_energy(self):
        """Residual energy normalized to [0, 1] relative to initial energy."""
        if self.energy_init <= 0:
            return 0.0
        return max(0.0, self.energy / self.energy_init)

    def is_low_energy(self, threshold_fraction=0.2):
        """
        True if E_i < threshold_fraction * E_init (default 20%), used by
        EAURP to avoid routing through nearly-depleted intermediate nodes.
        """
        return self.energy < threshold_fraction * self.energy_init

    def __repr__(self):
        return (f"Node(id={self.node_id}, pos=({self.x:.1f},{self.y:.1f}), "
                f"E={self.energy:.2f}/{self.energy_init:.2f}, "
                f"alive={self.alive})")
