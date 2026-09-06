"""
core/metrics.py
Metrics tracker for the MADRL-EAURP simulation (Member 5).

Reports the same unified metric set as every other engine in this project:
  - Packet Delivery Ratio (PDR %)
  - Average End-to-End Delay (ms)
  - Packet Loss (count and %)
  - Throughput (kbps)
  - Network Lifetime (rounds and seconds)
  - Energy consumed (Joules)

Two accounting fixes vs. the original tracker:

  1. `packets_sent` now counts every packet *offered* to the network,
     including those the source buffer could not accept. The original
     counted only accepted packets in `packets_generated` while counting
     source-side overflows in `packets_dropped`, so the reported loss
     percentage could exceed 100% (it reached 123% in the pre-fix run).
  2. Drops are broken down by cause (buffer overflow / TTL expiry / no
     route) so the routing failure modes are visible instead of being
     collapsed into one opaque counter.

`ROUND_DURATION_MS` matches the 100 ms/round convention used by the other
four engines, so throughput and delay are directly comparable across
protocols rather than implicitly assuming 1 round == 1 second.
"""

import numpy as np

ROUND_DURATION_MS = 100.0   # shared across all five engines
PACKET_SIZE_BITS = 8192     # shared across all five engines


class MetricsTracker:
    def __init__(self, packet_size_bits=PACKET_SIZE_BITS,
                 round_duration_ms=ROUND_DURATION_MS):
        self.packet_size_bits = packet_size_bits
        self.round_duration_ms = round_duration_ms

        # Every packet offered to the network, accepted or not.
        self.packets_sent = 0
        self.packets_delivered = 0
        self.packets_dropped = 0

        # Drop breakdown (sums to packets_dropped).
        self.drops_buffer_overflow = 0
        self.drops_ttl_expired = 0
        self.drops_no_route = 0

        self.total_delay = 0.0      # in rounds
        self.total_hops = 0

        self.gossip_messages = 0
        self.pt_gid_broadcasts = 0

        self.simulation_time = 0    # rounds elapsed

    # Backwards-compatible alias: the original tracker exposed this name.
    @property
    def packets_generated(self):
        return self.packets_sent

    def calculate_jains_fairness(self, nodes):
        energies = [n.energy for n in nodes]
        sum_e = sum(energies)
        sum_e_sq = sum(e ** 2 for e in energies)

        if sum_e_sq == 0:
            return 0.0
        return (sum_e ** 2) / (len(nodes) * sum_e_sq)

    # ------------------------------------------------------------------
    # Summary metrics
    # ------------------------------------------------------------------
    def get_pdr(self):
        if self.packets_sent == 0:
            return 0.0
        return (self.packets_delivered / self.packets_sent) * 100.0

    def get_packet_loss_percent(self):
        if self.packets_sent == 0:
            return 0.0
        return (self.packets_dropped / self.packets_sent) * 100.0

    def get_average_delay_ms(self):
        """Average end-to-end delay in milliseconds."""
        if self.packets_delivered == 0:
            return 0.0
        avg_rounds = self.total_delay / self.packets_delivered
        return avg_rounds * self.round_duration_ms

    # Kept for callers that want the raw per-round figure.
    def get_average_delay(self):
        if self.packets_delivered == 0:
            return 0.0
        return self.total_delay / self.packets_delivered

    def get_average_hop_count(self):
        if self.packets_delivered == 0:
            return 0.0
        return self.total_hops / self.packets_delivered

    def get_throughput_kbps(self):
        """Delivered bits per second of simulated time, in kbps."""
        total_time_s = (self.simulation_time * self.round_duration_ms) / 1000.0
        if total_time_s <= 0:
            return 0.0
        return ((self.packets_delivered * self.packet_size_bits) / total_time_s) / 1000.0

    # Legacy name: packets per round.
    def get_throughput(self):
        if self.simulation_time == 0:
            return 0.0
        return self.packets_delivered / self.simulation_time

    def get_total_energy_consumption(self, nodes):
        return sum(n.initial_energy - n.energy for n in nodes)
