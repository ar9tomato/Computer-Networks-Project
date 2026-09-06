import numpy as np

class MetricsTracker:
    def __init__(self):
        self.packets_generated = 0
        self.packets_delivered = 0
        self.packets_dropped = 0
        self.total_delay = 0.0
        self.delivered_delays = []
        
        self.gossip_messages = 0
        self.pt_gid_broadcasts = 0
        
        self.simulation_time = 0

    def calculate_jains_fairness(self, nodes):
        energies = [n.energy for n in nodes]
        sum_e = sum(energies)
        sum_e_sq = sum(e**2 for e in energies)
        
        if sum_e_sq == 0:
            return 0
        return (sum_e ** 2) / (len(nodes) * sum_e_sq)

    def get_pdr(self):
        if self.packets_generated == 0: return 0.0
        return (self.packets_delivered / self.packets_generated) * 100.0

    def get_average_delay(self):
        if self.packets_delivered == 0: return 0.0
        return self.total_delay / self.packets_delivered

    def get_throughput(self):
        if self.simulation_time == 0: return 0.0
        return self.packets_delivered / self.simulation_time

    def get_total_energy_consumption(self, nodes):
        total_initial = len(nodes) * 100.0
        total_current = sum(n.energy for n in nodes)
        return total_initial - total_current
