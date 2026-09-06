"""
core/metrics.py

MetricsCollector accumulates per-packet and per-round statistics during a
simulation run and produces the final summary metrics used for the CSV
outputs and comparative graphs:

    - Packet Delivery Ratio (PDR %)
    - Average Delay (ms)
    - Packet Loss (count and %)
    - Throughput (kbps)
    - Network Lifetime (rounds until the first node dies, and rounds until
      the network is considered "dead", i.e. alive-node fraction drops
      below a configurable threshold)
"""


class MetricsCollector:
    def __init__(self, packet_size_bits=8192, round_duration_ms=100.0,
                 lifetime_death_fraction=0.5):
        """
        Args:
            packet_size_bits: assumed size of each data packet, used to
                convert delivered-packet counts into throughput (kbps).
            round_duration_ms: wall-clock duration represented by a single
                simulation round, used to convert hop-delay (in rounds)
                into milliseconds and to compute throughput.
            lifetime_death_fraction: fraction of nodes that must still be
                alive; network lifetime is recorded as the last round at
                which at least this fraction of nodes was alive.
        """
        self.packet_size_bits = packet_size_bits
        self.round_duration_ms = round_duration_ms
        self.lifetime_death_fraction = lifetime_death_fraction

        self.packets_sent = 0
        self.packets_delivered = 0
        self.packets_lost = 0
        self.delays_rounds = []  # delay of each delivered packet, in rounds

        self.total_rounds = 0
        self.first_node_death_round = None
        self.network_lifetime_round = None
        self._last_alive_fraction = 1.0

    # ------------------------------------------------------------------
    # Per-packet recording
    # ------------------------------------------------------------------
    def record_sent(self):
        self.packets_sent += 1

    def record_delivered(self, delay_in_rounds):
        self.packets_delivered += 1
        self.delays_rounds.append(delay_in_rounds)

    def record_lost(self):
        self.packets_lost += 1

    # ------------------------------------------------------------------
    # Per-round recording
    # ------------------------------------------------------------------
    def record_round(self, round_index, alive_fraction, any_death_occurred):
        self.total_rounds = round_index + 1

        if any_death_occurred and self.first_node_death_round is None:
            self.first_node_death_round = round_index

        if (alive_fraction >= self.lifetime_death_fraction):
            # Network is still considered "alive enough" at this round.
            self.network_lifetime_round = round_index

        self._last_alive_fraction = alive_fraction

    # ------------------------------------------------------------------
    # Summary metrics
    # ------------------------------------------------------------------
    def pdr_percent(self):
        if self.packets_sent == 0:
            return 0.0
        return 100.0 * self.packets_delivered / self.packets_sent

    def packet_loss_count(self):
        return self.packets_lost

    def packet_loss_percent(self):
        if self.packets_sent == 0:
            return 0.0
        return 100.0 * self.packets_lost / self.packets_sent

    def average_delay_ms(self):
        if not self.delays_rounds:
            return 0.0
        avg_rounds = sum(self.delays_rounds) / len(self.delays_rounds)
        return avg_rounds * self.round_duration_ms

    def throughput_kbps(self):
        """
        Throughput = total bits delivered / total simulation time (s),
        expressed in kbps.
        """
        total_bits = self.packets_delivered * self.packet_size_bits
        total_time_s = (self.total_rounds * self.round_duration_ms) / 1000.0
        if total_time_s <= 0:
            return 0.0
        return (total_bits / total_time_s) / 1000.0

    def network_lifetime_rounds(self):
        """
        Network Lifetime, reported in rounds.

        Defined as the round at which the FIRST node in the network
        exhausts its battery (a standard, widely-used definition in
        energy-aware MANET routing literature - see e.g. the original
        motivation behind EAURP-style protocols: protecting whichever
        node is closest to death directly delays this event). Falls back
        to the total rounds simulated if no node died at all during the
        run.

        This is intentionally more sensitive than a bulk "X% of nodes
        still alive" threshold: a coarse bulk threshold only moves once a
        large fraction of nodes have already died together, which can
        flip abruptly once a handful of extra deaths tips the count over
        the threshold, obscuring the very thing an energy-aware protocol
        is designed to influence - how long it takes before any single
        node is drained by uneven, energy-blind traffic load.
        """
        if self.first_node_death_round is None:
            return self.total_rounds
        return self.first_node_death_round + 1

    def summary(self):
        return {
            "pdr_percent": round(self.pdr_percent(), 3),
            "avg_delay_ms": round(self.average_delay_ms(), 3),
            "packets_sent": self.packets_sent,
            "packets_delivered": self.packets_delivered,
            "packet_loss_count": self.packet_loss_count(),
            "packet_loss_percent": round(self.packet_loss_percent(), 3),
            "throughput_kbps": round(self.throughput_kbps(), 3),
            "network_lifetime_rounds": self.network_lifetime_rounds(),
        }
