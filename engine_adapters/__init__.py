"""
engine_adapters

Each member's protocol code (engines/<name>/core, engines/<name>/protocols)
was written independently, with its own Network/Node/MetricsCollector
classes, its own constructor signatures, and its own per-packet API
(Member1's AODV/EAURP engine mutates a shared MetricsCollector via
`send_packet(...)`; Member2's ATEAURP engine instead *returns*
(delivered, delay_ms, hop_count) from `route_packet(...)`). Renaming
classes to match would mean rewriting and re-validating each member's
simulation logic, which is out of scope for a consolidation refactor.

Instead, each engine keeps its own internal `core`/`protocols` packages
completely untouched, and gets ONE adapter module here that:
    1. loads that engine's own `core`/`protocols` in isolation
       (see `_isolated_import`), so the two engines' same-named
       `core.network`, `core.node`, etc. modules never collide in
       sys.modules,
    2. runs that engine's own experiment loop for a list of speeds,
    3. returns a list of plain dict rows in the COMMON schema defined
       below, ready to be concatenated across protocols.

This is the seam a real "unified pipeline" needs: run_all_experiments.py
and visualize_all.py only ever talk to this common schema, never to a
member's internal classes.
"""

import importlib
import os
import sys

# Columns every adapter is guaranteed to fill in, in this order. Any
# extra, protocol-specific columns (e.g. ATEAURP's detection_rate_percent)
# are preserved too, but only these are relied on by run_all_experiments.py
# and visualize_all.py.
# The nine unified metric keys every engine must report, plus identifiers.
# Ordered so the CSV opens with the comparison metrics.
COMMON_COLUMNS = [
    "protocol",
    "speed_mps",
    "pdr_percent",
    "avg_delay_ms",
    "throughput_kbps",
    "packet_loss_percent",
    "network_lifetime_sec",
    "energy_consumed_joules",
    "detection_rate_percent",
    "avg_trust",
    "avg_predicted_trust",
    "network_lifetime_rounds",
]

ENGINES_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engines")

# Modules that must be forced to reload between engines, since both
# Member1 and Member2 name their internal packages "core" / "protocols".
_ISOLATED_MODULE_PREFIXES = ("core", "protocols")


def _isolated_import(engine_dir_name, module_path):
    """
    Imports `module_path` (e.g. "core.network") from a single engine's
    directory (engines/<engine_dir_name>/), guaranteeing it does NOT pick
    up another engine's same-named "core" or "protocols" package left
    over in sys.modules from a previous adapter run.

    Returns the imported module.
    """
    engine_dir = os.path.join(ENGINES_ROOT, engine_dir_name)

    # Drop any previously-imported "core"/"protocols" (sub)modules so the
    # next import re-resolves them against THIS engine's directory.
    for name in list(sys.modules):
        if name.split(".")[0] in _ISOLATED_MODULE_PREFIXES:
            del sys.modules[name]

    # Make sure this engine's directory is first on sys.path, and that no
    # other engine's directory is still ahead of it.
    for other in os.listdir(ENGINES_ROOT):
        other_dir = os.path.join(ENGINES_ROOT, other)
        if other_dir in sys.path:
            sys.path.remove(other_dir)
    sys.path.insert(0, engine_dir)

    return importlib.import_module(module_path)


def normalize_row(protocol_name, speed, raw_summary):
    """
    Takes one engine's raw per-speed summary dict (whatever keys that
    engine's own MetricsCollector.summary() happens to produce) and returns
    a new dict guaranteed to contain every unified metric key, plus any
    extra keys the engine provided (kept as-is for reference).

    The row is merged OVER benchmark.DEFAULT_METRICS, so a protocol that
    does not natively produce a metric (e.g. AODV has no trust model) gets
    an explicit 0.0 instead of an empty CSV cell. This is what eliminates
    the ",," runs in results/combined_metrics.csv.
    """
    from engine_adapters.benchmark import apply_schema

    row = {"protocol": protocol_name, "speed_mps": speed}
    row.update(raw_summary)
    row = apply_schema(row)
    row["protocol"] = protocol_name
    row["speed_mps"] = speed

    for col in COMMON_COLUMNS:
        row.setdefault(col, 0.0)
    return row
