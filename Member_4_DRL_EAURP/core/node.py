"""
core/node.py
Node model for the DRL EAURP MANET simulation.

Each Node carries:
  - spatial state (position, velocity/direction)
  - energy state (continuous baseline depletion model)
  - trust bookkeeping (PT_NID / PT_GID counters, trust score, mobility factor)
  - a neighbor table populated by the network topology manager
"""

import random
import math


class Node:
    """
    Represents a single mobile node in the MANET.

    Attributes
    ----------
    node_id : int
        Unique node identifier (used as PT_NID in packet headers).
    group_id : int
        Group / cluster identifier (used as PT_GID in packet headers).
    x, y : float
        Current position in meters within the deployment grid.
    speed : float
        Current movement speed in m/s.
    direction : float
        Current heading in radians.
    energy : float
        Remaining battery energy (Joules, starts at INITIAL_ENERGY).
    forwarded : int
        Count of packets this node has successfully forwarded (F_i).
    received : int
        Count of packets this node has received for forwarding (R_i).
    trust : float
        Current trust score T_i in [0, 1].
    mobility_factor : float
        Normalized mobility factor M_i in [0, 1] (lower speed -> higher stability).
    is_malicious : bool
        Ground-truth malicious flag (used to simulate misbehavior).
    is_isolated : bool
        Whether the trust engine has isolated (bypassed) this node.
    """

    INITIAL_ENERGY = 100.0          # Joules
    ENERGY_DEPLETION_RATE = 0.02    # Base Joules consumed per round (baseline idle+processing draw)
    ENERGY_PER_FORWARD = 0.05       # Additional Joules consumed per packet forwarded
    ENERGY_PER_RETRY = 0.02         # Joules consumed per failed route-reconstruction attempt
    MAX_SPEED_REFERENCE = 40.0      # m/s, used to normalize mobility factor
    MOBILITY_ENERGY_SCALING = 1.5   # scales baseline depletion by node speed (re-signaling overhead)

    def __init__(self, node_id, group_id, grid_width, grid_height, speed,
                 malicious_probability=0.15, seed=None):
        if seed is not None:
            random.seed(seed + node_id)

        self.node_id = node_id
        self.group_id = group_id
        self.grid_width = grid_width
        self.grid_height = grid_height

        # Spatial state
        self.x = random.uniform(0, grid_width)
        self.y = random.uniform(0, grid_height)
        self.speed = speed
        self.direction = random.uniform(0, 2 * math.pi)

        # Energy state
        self.energy = self.INITIAL_ENERGY

        # Trust / packet tracking (PT_NID, PT_GID counters)
        self.forwarded = 0          # F_i
        self.received = 0           # R_i
        self.trust = 1.0            # T_i, optimistic initial trust
        self.mobility_factor = 1.0  # M_i

        # Malicious behavior ground truth (some nodes silently drop packets)
        self.is_malicious = random.random() < malicious_probability
        # Malicious nodes drop a majority of their traffic (60-90%), which
        # keeps their realized PFR/trust comfortably below the 0.6 isolation
        # threshold even accounting for sampling variance in a finite
        # simulation run — a milder floor (e.g. 50%) left trust hovering
        # right at the boundary and made detection unreliable.
        self.drop_probability = random.uniform(0.6, 0.9) if self.is_malicious else 0.0

        # Detection state
        self.is_isolated = False

        # Neighbor table: node_id -> distance (populated by NetworkManager)
        self.neighbor_table = {}

    # ------------------------------------------------------------------
    # Mobility
    # ------------------------------------------------------------------
    def move(self, dt=1.0):
        """
        Random Waypoint-style mobility update. Moves the node for `dt` seconds
        along its current heading, bouncing off grid boundaries, and
        occasionally selects a new random heading to keep the topology dynamic.
        """
        # Occasionally re-randomize direction (simulates waypoint re-selection)
        if random.random() < 0.1:
            self.direction = random.uniform(0, 2 * math.pi)

        dx = self.speed * dt * math.cos(self.direction)
        dy = self.speed * dt * math.sin(self.direction)

        new_x = self.x + dx
        new_y = self.y + dy

        # Reflective boundary handling
        if new_x < 0 or new_x > self.grid_width:
            self.direction = math.pi - self.direction
            new_x = min(max(new_x, 0), self.grid_width)
        if new_y < 0 or new_y > self.grid_height:
            self.direction = -self.direction
            new_y = min(max(new_y, 0), self.grid_height)

        self.x, self.y = new_x, new_y

        # Update normalized mobility factor: faster nodes => less stable => lower M_i
        self.mobility_factor = max(0.0, 1.0 - (self.speed / self.MAX_SPEED_REFERENCE))

    # ------------------------------------------------------------------
    # Energy model
    # ------------------------------------------------------------------
    def deplete_baseline(self):
        """
        Continuous baseline battery depletion applied once per round. Scaled
        by node speed (mobility re-signaling / re-discovery overhead), so
        higher-speed nodes drain faster and die earlier than low-speed nodes
        under an otherwise identical traffic load.
        """
        mobility_multiplier = 1.0 + (self.speed / self.MAX_SPEED_REFERENCE) * self.MOBILITY_ENERGY_SCALING
        self.energy = max(0.0, self.energy - (self.ENERGY_DEPLETION_RATE * mobility_multiplier))

    def deplete_for_forward(self):
        """Additional energy cost incurred when a node forwards a packet."""
        self.energy = max(0.0, self.energy - self.ENERGY_PER_FORWARD)

    def deplete_for_retry(self):
        """Additional energy cost incurred on a failed route-reconstruction attempt."""
        self.energy = max(0.0, self.energy - self.ENERGY_PER_RETRY)

    @property
    def is_alive(self):
        return self.energy > 0.0

    @property
    def normalized_energy(self):
        """Energy normalized to [0, 1] relative to initial capacity."""
        return self.energy / self.INITIAL_ENERGY

    # ------------------------------------------------------------------
    # Trust bookkeeping (PT_NID / PT_GID packet headers)
    # ------------------------------------------------------------------
    def register_received(self):
        """Increment R_i — a packet header carrying this node's PT_NID/PT_GID
        was received for forwarding."""
        self.received += 1

    def register_forwarded(self):
        """Increment F_i — this node successfully forwarded the packet on."""
        self.forwarded += 1
        self.deplete_for_forward()

    @property
    def packet_forward_ratio(self):
        """PFR_i = F_i / R_i, guarded against division by zero."""
        if self.received == 0:
            return 1.0
        return self.forwarded / self.received

    def update_trust(self, alpha=0.7, beta=0.3):
        """
        Adaptive moving-average trust update:
            T_i(t+1) = alpha * T_i(t) + beta * PFR_i
        """
        pfr = self.packet_forward_ratio
        self.trust = alpha * self.trust + beta * pfr
        self.trust = min(1.0, max(0.0, self.trust))
        return self.trust

    def evaluate_isolation(self, received_threshold=5, trust_threshold=0.6):
        """
        Malicious isolation rule: a node is bypassed if it has handled a
        statistically meaningful number of packets (R_i > received_threshold)
        AND its trust has fallen below trust_threshold.
        """
        self.is_isolated = (self.received > received_threshold) and (self.trust < trust_threshold)
        return self.is_isolated

    def __repr__(self):
        return (f"Node(id={self.node_id}, group={self.group_id}, "
                f"pos=({self.x:.1f},{self.y:.1f}), trust={self.trust:.2f}, "
                f"energy={self.energy:.2f}, malicious={self.is_malicious}, "
                f"isolated={self.is_isolated})")
