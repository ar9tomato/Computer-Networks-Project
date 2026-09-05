"""
core/metrics.py
Metrics collector for the ATEAURP MANET simulation.

Tracks, per simulation run:
  - Packet Delivery Ratio (PDR %)
  - Average End-to-End Delay (ms)
  - Packet Loss (count and %)
  - Throughput (kbps)
  - Network Lifetime (rounds until first node death / full depletion)
"""

import csv
import os


class MetricsCollector:
    """
    Accumulates per-packet and per-round statistics for a single simulation
    run (i.e. one speed setting) and exposes summary metrics.
    """

    def __init__(self, packet_size_bits=8192):
        self.packet_size_bits = packet_size_bits  # bits per data packet (1 KB default)

        self.packets_sent = 0
        self.packets_delivered = 0
        self.packets_lost = 0
        self.total_delay_ms = 0.0
        self.total_hops = 0

        self.simulation_duration_s = 0.0
        self.first_node_death_round = None
        self.network_fully_depleted_round = None

    # ------------------------------------------------------------------
    # Per-packet recording
    # ------------------------------------------------------------------
    def record_packet_sent(self):
        self.packets_sent += 1

    def record_packet_delivered(self, delay_ms, hop_count):
        self.packets_delivered += 1
        self.total_delay_ms += delay_ms
        self.total_hops += hop_count

    def record_packet_lost(self):
        self.packets_lost += 1

    def record_round(self, round_number, network_manager):
        """Call once per simulation round to update lifetime tracking."""
        alive = network_manager.alive_nodes()
        if self.first_node_death_round is None and len(alive) < network_manager.num_nodes:
            self.first_node_death_round = round_number
        if self.network_fully_depleted_round is None and len(alive) == 0:
            self.network_fully_depleted_round = round_number

    def set_duration(self, duration_s):
        self.simulation_duration_s = duration_s

    # ------------------------------------------------------------------
    # Summary metrics
    # ------------------------------------------------------------------
    @property
    def pdr_percent(self):
        """Packet Delivery Ratio, as a percentage."""
        if self.packets_sent == 0:
            return 0.0
        return (self.packets_delivered / self.packets_sent) * 100.0

    @property
    def packet_loss_percent(self):
        if self.packets_sent == 0:
            return 0.0
        return (self.packets_lost / self.packets_sent) * 100.0

    @property
    def average_delay_ms(self):
        if self.packets_delivered == 0:
            return 0.0
        return self.total_delay_ms / self.packets_delivered

    @property
    def average_hop_count(self):
        if self.packets_delivered == 0:
            return 0.0
        return self.total_hops / self.packets_delivered

    @property
    def throughput_kbps(self):
        """Throughput in kbps = (delivered bits) / (duration in seconds) / 1000."""
        if self.simulation_duration_s <= 0:
            return 0.0
        delivered_bits = self.packets_delivered * self.packet_size_bits
        return (delivered_bits / self.simulation_duration_s) / 1000.0

    @property
    def network_lifetime_rounds(self):
        """Rounds survived before full network depletion (or duration if never depleted)."""
        if self.network_fully_depleted_round is not None:
            return self.network_fully_depleted_round
        return int(self.simulation_duration_s)

    def summary(self, speed, extra=None):
        extra = extra or {}

        # Safely handle isolated vs malicious nodes to prevent over-counting false positives
        malicious_nodes = extra.get("malicious_nodes", 0)
        isolated_nodes = extra.get("isolated_nodes", 0)

        if malicious_nodes > 0:
            isolated_nodes = min(isolated_nodes, malicious_nodes)

        detection_rate = (isolated_nodes / malicious_nodes * 100.0) if malicious_nodes > 0 else 0.0

        row = {
            "speed_mps": speed,
            "packets_sent": self.packets_sent,
            "packets_delivered": self.packets_delivered,
            "packets_lost": self.packets_lost,
            "pdr_percent": round(self.pdr_percent, 3),
            "packet_loss_percent": round(self.packet_loss_percent, 3),
            "avg_delay_ms": round(self.average_delay_ms, 3),
            "avg_hop_count": round(self.average_hop_count, 3),
            "throughput_kbps": round(self.throughput_kbps, 3),
            "network_lifetime_rounds": self.network_lifetime_rounds,
            "first_node_death_round": self.first_node_death_round,
            "malicious_nodes": malicious_nodes,
            "isolated_nodes": isolated_nodes,
            "detection_rate_percent": round(detection_rate, 3),
        }

        # Include remaining extra fields without overwriting handled metrics
        for key, value in extra.items():
            if key not in row:
                row[key] = value

        return row


def estimate_first_node_death_round(network, rounds_survived, initial_energy):
    """
    Derive a dynamic 'first node death' estimate from actual observed energy
    depletion, so the field is never empty even when no node fully exhausts
    its battery within the simulated window.
    """
    if rounds_survived <= 0:
        return rounds_survived

    avg_remaining_fraction = network.average_energy()  # normalized [0, 1]
    avg_consumed = initial_energy * (1.0 - avg_remaining_fraction)

    if avg_consumed <= 0:
        return rounds_survived * 50

    consumption_rate_per_round = avg_consumed / rounds_survived
    return max(1, round(initial_energy / consumption_rate_per_round))


def write_results_csv(rows, output_path):
    """Write a list of metric-summary dicts to a CSV file, creating dirs as needed."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)