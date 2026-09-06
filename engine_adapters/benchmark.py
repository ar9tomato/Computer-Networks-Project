"""
engine_adapters/benchmark.py

Single source of truth for the baseline simulation parameters and the
unified metrics schema shared by all five protocol engines.

Before this module existed, each adapter carried its own copies of these
constants and they had drifted apart, so the protocols were not actually
being benchmarked against one another:

  * AODV / EAURP ran 400 rounds x 4 packets = 1,600 offered packets, while
    ATEAURP / PSE-EAURP / DRL-EAURP ran 200 x 20 = 4,000 and MADRL-EAURP
    generated only ~500. PDR is a ratio so it survives that, but throughput,
    packet-loss counts and lifetime do not.
  * AODV / EAURP nodes started with 60 J while every other engine started
    with 100 J, which directly biased the energy and lifetime columns.
  * MADRL-EAURP implicitly treated one round as one second while the other
    four treated it as 100 ms, making its throughput column an order of
    magnitude off.

Everything below is now imported by the adapters rather than redeclared.
"""

# ---------------------------------------------------------------------
# Baseline simulation parameters — identical for every protocol
# ---------------------------------------------------------------------
TOTAL_PACKETS = 4000            # total packets offered per run
ROUNDS = 200                    # simulation rounds per speed
PACKETS_PER_ROUND = TOTAL_PACKETS // ROUNDS   # == 20
INITIAL_ENERGY_JOULES = 100.0   # per-node starting battery
SPEEDS_MPS = [10, 20, 30, 40]   # node speed sweep

NUM_NODES = 50
GRID_WIDTH = 1000.0
GRID_HEIGHT = 1000.0
GRID_SIZE = 1000
TX_RANGE = 250.0
PACKET_SIZE_BITS = 8192
ROUND_DURATION_MS = 100.0       # one simulation round == 100 ms
MALICIOUS_PROBABILITY = 0.15
BASE_SEED = 42

# Seconds of simulated wall-clock time represented by a full run.
SIMULATION_SECONDS = (ROUNDS * ROUND_DURATION_MS) / 1000.0


# ---------------------------------------------------------------------
# Unified metrics schema
# ---------------------------------------------------------------------
# Every adapter row is merged over this dictionary, so a metric that a
# given protocol does not natively produce is explicitly 0.0 rather than an
# empty CSV cell. Baseline protocols (AODV, EAURP) have no trust or
# intrusion-detection mechanism at all, so their detection/trust columns are
# legitimately zero — that is a real property of those protocols, not a
# missing measurement, and NOT_APPLICABLE below records the distinction.
DEFAULT_METRICS = {
    "pdr_percent": 0.0,
    "avg_delay_ms": 0.0,
    "throughput_kbps": 0.0,
    "packet_loss_percent": 0.0,
    "network_lifetime_sec": 0.0,
    "energy_consumed_joules": 0.0,
    "detection_rate_percent": 0.0,
    "avg_trust": 0.0,
    "avg_predicted_trust": 0.0,
}

# Metrics that are structurally absent for a protocol, as opposed to
# measured-as-zero. Written to the companion *_applicability.csv so a reader
# can tell "this protocol has no trust model" apart from "trust measured 0".
NOT_APPLICABLE = {
    "AODV": ["detection_rate_percent", "avg_trust", "avg_predicted_trust"],
    "EAURP": ["detection_rate_percent", "avg_trust", "avg_predicted_trust"],
    "ATEAURP": ["avg_predicted_trust"],
    "PSE-EAURP": [],
    "DRL-EAURP": ["avg_predicted_trust"],
    "MADRL-EAURP": ["avg_predicted_trust"],
}


def rounds_to_seconds(rounds):
    """Convert a lifetime expressed in rounds into simulated seconds."""
    if rounds is None:
        return 0.0
    return round((float(rounds) * ROUND_DURATION_MS) / 1000.0, 3)


def apply_schema(row):
    """
    Merge one adapter row over DEFAULT_METRICS so every unified key is
    present and numeric. Keys the engine supplied always win; keys it did
    not supply fall back to the 0.0 default instead of an empty cell.
    """
    merged = {**DEFAULT_METRICS, **{k: v for k, v in row.items() if v is not None}}
    for key in DEFAULT_METRICS:
        if merged.get(key) is None:
            merged[key] = DEFAULT_METRICS[key]
    return merged
