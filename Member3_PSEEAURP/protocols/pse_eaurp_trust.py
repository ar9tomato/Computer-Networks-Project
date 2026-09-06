# protocols/pse_eaurp.py
# Member 3 - PSE-EAURP (Predictive Secure EAURP)
#
# This file adds "predictive trust" on top of the basic trust idea.
# Instead of just reacting to a node's last behavior, we look at its
# last 3 trust scores and guess where it's heading -- catching bad
# nodes earlier.

# ---------------------------------------------------------------
# STEP 1: Trust history per node
# ---------------------------------------------------------------
# Every node in the network needs its own memory of the last 3 trust
# values. We store these in a plain dictionary keyed by node ID.

def init_trust_history(node_ids):
    """
    Call this ONCE at the start of the simulation.
    Gives every node a neutral starting history: [1.0, 1.0, 1.0]
    meaning 'fully trusted, no history yet'.
    """
    trust_history = {}
    for node_id in node_ids:
        trust_history[node_id] = [1.0, 1.0, 1.0]  # [T(t-2), T(t-1), T(t)]
    return trust_history


# ---------------------------------------------------------------
# STEP 2: Predictive trust formula
# ---------------------------------------------------------------
def predict_trust(history_for_node):
    """
    history_for_node = [T(t-2), T(t-1), T(t)]
    Returns the predicted next trust value, weighting recent
    behavior most heavily (0.5), then less recent (0.3), then
    oldest (0.2).
    """
    t_minus2, t_minus1, t_now = history_for_node
    t_pred = 0.5 * t_now + 0.3 * t_minus1 + 0.2 * t_minus2
    return t_pred


# ---------------------------------------------------------------
# STEP 3: Compute this round's raw trust (PFR) for a node
# ---------------------------------------------------------------
def compute_pfr(packets_forwarded, packets_received):
    """
    Packet Forwarding Ratio: how much of what a node RECEIVED did it
    actually FORWARD onward? Close to 1 = trustworthy.
    Guard against divide-by-zero if the node received nothing yet.
    """
    if packets_received == 0:
        return 1.0  # no data yet -> assume trustworthy
    return packets_forwarded / packets_received


# ---------------------------------------------------------------
# STEP 4: Slide the window forward after each round
# ---------------------------------------------------------------
def update_trust_history(trust_history, node_id, new_trust_value):
    """
    Drops the oldest trust reading and appends the newest one.
    This keeps the history always exactly 3 values long.
    """
    old = trust_history[node_id]
    # old = [t-2, t-1, t] -> new = [t-1, t, new]
    trust_history[node_id] = [old[1], old[2], new_trust_value]


# ---------------------------------------------------------------
# STEP 5: Route success probability
# ---------------------------------------------------------------
def route_success_probability(avg_trust_pred, avg_energy, avg_mobility):
    """
    Combines predicted trust, average energy, and average mobility
    stability into a single 'how likely is this route to work' score.
    Capped at 0.97 (never claim near-perfect certainty).
    """
    score = 0.4 + 0.35 * avg_trust_pred + 0.15 * avg_energy + 0.1 * avg_mobility
    return min(score, 0.97)


# ---------------------------------------------------------------
# STEP 6: Revocation logic (PT_CREV)
# ---------------------------------------------------------------
# We track how many CONSECUTIVE rounds a node has stayed below the
# trust threshold. Only revoke after it's been bad for a while --
# this avoids punishing a node for one bad round (e.g. a temporary
# battery dip).

TRUST_THRESHOLD = 0.6
ROUNDS_BEFORE_REVOKE = 3

def check_and_revoke(node_id, predicted_trust, bad_streak_tracker, revocation_list):
    """
    bad_streak_tracker: dict {node_id: consecutive_bad_rounds}
    revocation_list: a python set() of node_ids that are blacklisted

    Returns True if this node was JUST revoked this round (so you know
    to broadcast a PT_CREV packet to the rest of the network).
    """
    if node_id in revocation_list:
        return False  # already revoked, nothing new to broadcast

    if predicted_trust < TRUST_THRESHOLD:
        bad_streak_tracker[node_id] = bad_streak_tracker.get(node_id, 0) + 1
    else:
        bad_streak_tracker[node_id] = 0  # reset if it recovered

    if bad_streak_tracker[node_id] >= ROUNDS_BEFORE_REVOKE:
        revocation_list.add(node_id)
        return True  # just got revoked -> broadcast PT_CREV now

    return False


def broadcast_pt_crev(node_id, all_nodes_revocation_lists):
    """
    Simulates telling every other node in the network: 'block this
    node_id from now on.' In your real simulation loop, call this
    right after check_and_revoke() returns True.
    """
    for node_list in all_nodes_revocation_lists.values():
        node_list.add(node_id)


# ---------------------------------------------------------------
# STEP 7: Route reassessment -- avoid revoked nodes
# ---------------------------------------------------------------
def is_route_safe(route_node_ids, revocation_list):
    """
    route_node_ids: list of node IDs along a candidate path
    Returns False if ANY node on the path has been revoked --
    meaning: drop this route, go find another one.
    """
    for node_id in route_node_ids:
        if node_id in revocation_list:
            return False
    return True