import numpy as np

class Node:
    def __init__(self, node_id, grid_size=1000, max_speed=10, num_nodes=50, group_id=1,
                 initial_energy=100.0):
        self.node_id = node_id
        self.group_id = group_id
        self.grid_size = grid_size
        
        # Initial position and velocity
        self.x = np.random.uniform(0, grid_size)
        self.y = np.random.uniform(0, grid_size)
        angle = np.random.uniform(0, 2 * np.pi)
        self.vx = np.cos(angle) * max_speed
        self.vy = np.sin(angle) * max_speed
        
        # Energy and Buffer
        self.initial_energy = initial_energy   # Joules (baseline: 100.0)
        self.energy = self.initial_energy
        self.buffer = []
        self.buffer_capacity = 20
        
        # Network & Trust
        self.neighbors_1hop = []
        self.neighbors_2hop = []
        self.trust_table = np.ones(num_nodes) * 0.5  # Neutral trust 0.5 initially
        
        # Statistics
        self.packets_sent = 0
        self.packets_forwarded = 0
        
    def update_position(self, dt=1.0):
        self.x += self.vx * dt
        self.y += self.vy * dt
        
        # Boundary reflection
        if self.x <= 0 or self.x >= self.grid_size:
            self.vx *= -1
            self.x = np.clip(self.x, 0, self.grid_size)
        if self.y <= 0 or self.y >= self.grid_size:
            self.vy *= -1
            self.y = np.clip(self.y, 0, self.grid_size)

    def consume_energy(self, amount):
        self.energy = max(0.0, self.energy - amount)
        
    def is_alive(self):
        return self.energy > 0

    def receive_packet(self, packet):
        if len(self.buffer) < self.buffer_capacity and self.is_alive():
            self.buffer.append(packet)
            self.consume_energy(0.05) # RX cost
            return True
        return False

    def get_local_state(self, num_nodes=50):
        # S_{t,i} = [buffer_occupancy, residual_energy, neighbor_trust_information]
        state = np.zeros(2 + num_nodes)
        state[0] = len(self.buffer) / self.buffer_capacity
        state[1] = self.energy / self.initial_energy
        for i in range(num_nodes):
            state[2 + i] = self.trust_table[i] if i in self.neighbors_1hop else -1.0
        return state
