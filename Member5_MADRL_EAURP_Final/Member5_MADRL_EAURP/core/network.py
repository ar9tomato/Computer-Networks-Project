import numpy as np
from .node import Node

class MANETNetwork:
    def __init__(self, num_nodes=50, grid_size=1000, tx_range=250, speed=10):
        self.num_nodes = num_nodes
        self.grid_size = grid_size
        self.tx_range = tx_range
        self.speed = speed
        
        self.nodes = [Node(i, grid_size, speed, num_nodes, group_id=(i%2)+1) for i in range(num_nodes)]
        self.update_topology()

    def step(self):
        # Move nodes
        for node in self.nodes:
            node.update_position()
            # Baseline continuous energy depletion
            node.consume_energy(0.01)
            
        self.update_topology()

    def update_topology(self):
        # Calculate Euclidean distances
        positions = np.array([[n.x, n.y] for n in self.nodes])
        diff = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]
        distances = np.sqrt(np.sum(diff ** 2, axis=-1))
        
        for i, node in enumerate(self.nodes):
            if not node.is_alive():
                node.neighbors_1hop = []
                node.neighbors_2hop = []
                continue
                
            # 1-hop neighbors
            neighbors = np.where(distances[i] <= self.tx_range)[0]
            node.neighbors_1hop = [int(n) for n in neighbors if n != i and self.nodes[n].is_alive()]
            
            # 2-hop neighbors
            hop2 = set()
            for n1 in node.neighbors_1hop:
                n1_neighbors = np.where(distances[n1] <= self.tx_range)[0]
                for n2 in n1_neighbors:
                    if n2 != i and n2 not in node.neighbors_1hop and self.nodes[n2].is_alive():
                        hop2.add(int(n2))
            node.neighbors_2hop = list(hop2)
