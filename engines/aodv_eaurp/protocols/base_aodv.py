"""
protocols/base_aodv.py

Implements two routing engines that operate over a core.network.Network
instance:

    1. AODVEngine  - a simplified Ad-hoc On-demand Distance Vector router.
       Route discovery floods a Route Request (RREQ) outward from the
       source (a breadth-first search over the current connectivity
       graph), and the destination (or an intermediate node with a valid
       route) sends back a Route Reply (RREP) along the reverse path.
       Route selection is purely shortest-hop-count.

    2. EAURPEngine - Energy-Aware Unobservable Routing Protocol. Built as
       an enhancement on top of the same RREQ/RREP discovery mechanism,
       but selecting among several *candidate* routes (not just one) using
       a composite score of residual energy, hop count, and link
       stability, while only ever hard-excluding nodes that are
       critically depleted. See EAURPEngine for the full rationale.

Both engines share route-maintenance behaviour: an established route is
validated hop-by-hop against the *current* topology before every packet
transmission. If a link along the path is broken (mobility or a node
dying), the engine attempts an immediate, bounded number of rediscovery
retries before the packet is finally counted as lost - this models real
AODV/EAURP local repair rather than dropping traffic the instant a link
degrades when a perfectly good alternate route exists.

--------------------------------------------------------------------
Why the previous EAURP implementation underperformed AODV
--------------------------------------------------------------------
The earlier version *hard-excluded* every node with residual energy below
20% of its initial energy from route discovery entirely. In a sparsely
connected MANET (50 nodes / 250 m range on a 1000x1000 m grid) that is too
aggressive: as soon as a handful of nodes drop under the 20% mark, large
parts of the topology can become entirely unusable to EAURP even though
AODV routes through them without issue, causing route discovery to fail
outright (RouteNotFound) far more often than AODV. On top of that, a
single broken hop during forwarding caused an immediate packet loss with
no local-repair attempt, and only the single best shortest-hop path was
ever considered, so EAURP had no way to trade a small amount of extra hop
count for a much healthier, more stable path.

The fix below addresses all of this:
  - Only *critically* depleted nodes (a much lower threshold) are ever
    hard-excluded; moderately low-energy nodes (below the 20% mark) stay
    usable but are heavily penalized in route scoring, and only avoided
    when a comparably short, healthier alternative exists.
  - Route discovery considers multiple candidate paths - not just the
    strict shortest-hop set, but also paths up to one hop longer - so
    EAURP can actually choose a slightly longer but meaningfully better
    route instead of being forced to pick from a single hop-count tier.
  - Route scoring combines residual energy, hop count, AND link
    stability (how much distance margin each hop has within the
    transmission range - links close to the range limit are the first to
    break under mobility).
  - Route maintenance performs a bounded number of immediate rediscovery
    attempts before giving up on a packet, so a broken link does not
    waste a packet when a valid alternate route is available right now.
"""

from collections import deque


class RouteNotFound(Exception):
    """Raised internally when no path exists between source and destination."""


class BaseRoutingEngine:
    """
    Shared functionality for both AODV and EAURP: RREQ flooding (BFS over
    the live connectivity graph), route validation, route maintenance with
    bounded local-repair retries, and hop-by-hop packet forwarding with
    energy consumption.
    """

    name = "BASE"

    # Number of immediate rediscovery attempts allowed after a link break,
    # before a packet is finally counted as lost. Applies identically to
    # both engines so the comparison stays fair - this models local route
    # repair, not an EAURP-only advantage.
    MAX_ROUTE_RETRIES = 2

    # Maximum extra hops (beyond the strict shortest-path length) that
    # candidate-path discovery will explore, and a hard cap on how many
    # candidate paths are collected, to keep discovery fast on a 50-node
    # topology regardless of which engine is using it.
    MAX_EXTRA_HOPS = 1
    MAX_CANDIDATE_PATHS = 40

    # Hard cap on the number of DFS expansions performed while enumerating
    # candidate paths, independent of how many complete paths have been
    # found so far. This bounds worst-case discovery cost on denser
    # topologies (e.g. many nodes packed within transmission range),
    # where branching factor alone could otherwise blow up before the
    # max_paths cap is ever reached.
    MAX_PATH_EXPANSIONS = 800

    def __init__(self, network):
        self.network = network
        # Simple route cache: (src, dst) -> list of node_ids representing
        # the last discovered path. Invalidated on link break.
        self.route_cache = {}

    # ------------------------------------------------------------------
    # RREQ / RREP route discovery (to be specialised by subclasses)
    # ------------------------------------------------------------------
    def _eligible_nodes(self):
        """
        Returns the set of node_ids allowed to participate in route
        discovery (i.e. forward RREQs / appear on a route). AODV allows
        every alive node.
        """
        return {n.node_id for n in self.network.alive_nodes()}

    def _bfs_shortest_length(self, src, dst, adjacency, eligible):
        """
        Plain BFS shortest-path hop count between src and dst restricted
        to `eligible` nodes. Returns None if unreachable.
        """
        if src not in eligible or dst not in eligible:
            return None
        if src == dst:
            return 0

        visited = {src}
        frontier = deque([(src, 0)])
        while frontier:
            current, dist = frontier.popleft()
            for neighbor in adjacency.get(current, ()):
                if neighbor not in eligible or neighbor in visited:
                    continue
                if neighbor == dst:
                    return dist + 1
                visited.add(neighbor)
                frontier.append((neighbor, dist + 1))
        return None

    def discover_candidate_paths(self, src, dst, adjacency, eligible,
                                  max_extra_hops=None, max_paths=None):
        """
        Discovers multiple usable candidate routes between src and dst,
        emulating an AODV-style RREQ flood that is allowed to collect more
        than one viable reply: every simple path whose length is within
        `max_extra_hops` hops of the strict shortest-path length is
        returned (bounded by `max_paths` for performance).

        This is what lets EAURP meaningfully trade a small amount of extra
        hop count for a healthier / more stable path, instead of being
        stuck choosing only among paths that tie for the minimum possible
        hop count.

        Returns a list of candidate paths (each a list of node_ids from
        src to dst). Empty list if unreachable.
        """
        max_extra_hops = self.MAX_EXTRA_HOPS if max_extra_hops is None else max_extra_hops
        max_paths = self.MAX_CANDIDATE_PATHS if max_paths is None else max_paths

        if src not in eligible or dst not in eligible:
            return []
        if src == dst:
            return [[src]]

        shortest_len = self._bfs_shortest_length(src, dst, adjacency, eligible)
        if shortest_len is None:
            return []

        max_len = shortest_len + max_extra_hops
        candidates = []

        # Depth-bounded DFS enumeration of simple paths up to max_len
        # hops. The network is small (50 nodes, moderate degree at
        # R=250m/1000x1000m grid), so this stays cheap once bounded by
        # max_len and max_paths.
        stack = [(src, [src], {src})]
        expansions = 0
        while stack and len(candidates) < max_paths and expansions < self.MAX_PATH_EXPANSIONS:
            current, path, visited = stack.pop()
            expansions += 1
            if len(path) - 1 >= max_len:
                continue
            for neighbor in adjacency.get(current, ()):
                if neighbor not in eligible or neighbor in visited:
                    continue
                new_path = path + [neighbor]
                if neighbor == dst:
                    candidates.append(new_path)
                    if len(candidates) >= max_paths:
                        break
                    continue
                if len(new_path) - 1 < max_len:
                    stack.append((neighbor, new_path, visited | {neighbor}))

        # Guarantee at least the plain shortest path is always available,
        # even if the expansion cap was hit before a full path was found
        # in pathological dense topologies.
        if not candidates:
            fallback = self._reconstruct_one_shortest_path(src, dst, adjacency, eligible)
            if fallback:
                candidates.append(fallback)

        return candidates

    def _reconstruct_one_shortest_path(self, src, dst, adjacency, eligible):
        """Plain BFS returning a single shortest path (fallback helper)."""
        if src not in eligible or dst not in eligible:
            return None
        if src == dst:
            return [src]
        visited = {src}
        parent = {}
        frontier = deque([src])
        while frontier:
            current = frontier.popleft()
            for neighbor in adjacency.get(current, ()):
                if neighbor not in eligible or neighbor in visited:
                    continue
                visited.add(neighbor)
                parent[neighbor] = current
                if neighbor == dst:
                    path = [dst]
                    while path[-1] != src:
                        path.append(parent[path[-1]])
                    return list(reversed(path))
                frontier.append(neighbor)
        return None

    # ------------------------------------------------------------------
    # Route validation / maintenance
    # ------------------------------------------------------------------
    def is_route_valid(self, path):
        """
        A route is valid if every consecutive hop is still within
        transmission range and every node on the path is still alive.
        This models AODV's link-breakage detection for route maintenance.
        """
        if not path:
            return False
        net = self.network
        for node_id in path:
            node = net.get_node(node_id)
            if not node.alive:
                return False
        for a_id, b_id in zip(path, path[1:]):
            a = net.get_node(a_id)
            b = net.get_node(b_id)
            if not net.in_range(a, b):
                return False
        return True

    def find_route(self, src, dst, use_cache=True):
        """
        Returns a validated route (list of node_ids) from src to dst, or
        None if unreachable. Uses (and refreshes) the route cache to model
        AODV route maintenance: cached routes are reused as long as they
        remain valid, and rediscovered on link breakage / on request
        (use_cache=False, used by local-repair retries).
        """
        if use_cache:
            cached = self.route_cache.get((src, dst))
            if cached and self.is_route_valid(cached):
                return cached

        eligible = self._eligible_nodes()
        adjacency = self.network.build_adjacency()
        candidates = self.discover_candidate_paths(src, dst, adjacency, eligible)
        if not candidates:
            self.route_cache.pop((src, dst), None)
            return None

        best_path = self.select_route(candidates)
        self.route_cache[(src, dst)] = best_path
        return best_path

    def select_route(self, candidate_paths):
        """Default (AODV) selection: minimum hop count, first candidate."""
        return min(candidate_paths, key=len)

    # ------------------------------------------------------------------
    # Packet forwarding
    # ------------------------------------------------------------------
    def send_packet(self, src, dst, metrics, current_round):
        """
        Attempts to route one data packet from src to dst, with bounded
        local-repair retries on link breakage.

        Returns True if delivered, False if lost. Updates `metrics`
        accordingly and applies per-hop energy consumption (tx at the
        sender/forwarders, rx at the next hop) to every node that actually
        participates in forwarding this packet, consistent with the
        specified energy model E_i(t+1) = E_i(t) - delta_E_i.
        """
        metrics.record_sent()

        attempts = 0
        extra_delay = 0  # rounds "wasted" on local-repair rediscovery
        path = self.find_route(src, dst)

        while True:
            if path is None or len(path) < 2:
                metrics.record_lost()
                return False

            link_broken = False

            for i in range(len(path) - 1):
                a = self.network.get_node(path[i])
                b = self.network.get_node(path[i + 1])
                if not (a.alive and b.alive) or not self.network.in_range(a, b):
                    link_broken = True
                    break
                a.drain_tx()
                b.drain_rx()
                if not a.alive or not b.alive:
                    link_broken = True
                    break

            if not link_broken:
                hop_count = len(path) - 1
                metrics.record_delivered(delay_in_rounds=hop_count + extra_delay)
                return True

            # Link broke partway through forwarding: invalidate the stale
            # route and, if retries remain, attempt local repair by
            # rediscovering a fresh route right now rather than instantly
            # failing the packet.
            self.route_cache.pop((src, dst), None)
            attempts += 1
            if attempts > self.MAX_ROUTE_RETRIES:
                metrics.record_lost()
                return False

            extra_delay += 1
            path = self.find_route(src, dst, use_cache=False)


class AODVEngine(BaseRoutingEngine):
    """
    Baseline AODV: shortest-hop-count routing with no energy awareness.
    Any alive node may forward traffic regardless of residual energy.
    """

    name = "AODV"

    def select_route(self, candidate_paths):
        # Pure shortest-hop selection (tie-break: first found).
        return min(candidate_paths, key=len)


class EAURPEngine(BaseRoutingEngine):
    """
    Energy-Aware Unobservable Routing Protocol (EAURP).

    Enhancements over baseline AODV:

      1. Two-tier energy penalty instead of a single hard cutoff. EAURP
         never removes an alive node from the eligible/connectivity graph
         (that would needlessly cost it topology that AODV still has
         access to) - instead it scores routes so that low-energy nodes
         are progressively discouraged:
           - critical_energy_threshold (very low, default 8% of E_init):
             a node this depleted is almost dead, so its contribution to
             a route's energy score is scaled down very heavily. It can
             still be used - e.g. as the only way to maintain
             connectivity - but only when no reasonably comparable
             alternative exists.
           - low_energy_threshold (0.2 * E_init, i.e. the specified 20%
             threshold): nodes below this are moderately penalized in
             route scoring, enough that a healthier alternative is
             preferred whenever one exists at a similar hop count, but
             not so much that a single moderately-low node makes an
             otherwise-good route unusable.
      2. Multi-candidate, multi-factor route selection: EAURP considers
         every candidate path within one extra hop of the shortest
         possible route (see discover_candidate_paths) and scores each
         one on:
           - average normalized residual energy of intermediate nodes
             (with an additional penalty for any node under the 20%
             threshold),
           - hop count, and
           - link stability (how much distance margin each hop has
             relative to the transmission range - links stretched close
             to R are the ones most likely to break under mobility).
         This lets EAURP pick a route that is only marginally longer than
         AODV's when doing so meaningfully improves energy health and
         stability, and to fall back to the plain shortest route when the
         "healthier" option isn't actually better.
    """

    name = "EAURP"

    def __init__(self, network,
                 low_energy_threshold=0.2,
                 critical_energy_threshold=0.08,
                 energy_weight=0.5,
                 stability_weight=0.2,
                 hop_weight=0.3,
                 low_energy_penalty=0.55,
                 critical_energy_penalty=0.15):
        super().__init__(network)
        self.low_energy_threshold = low_energy_threshold
        self.critical_energy_threshold = critical_energy_threshold
        self.energy_weight = energy_weight
        self.stability_weight = stability_weight
        self.hop_weight = hop_weight
        # Multiplier applied to a node's normalized energy before it is
        # averaged into a route's energy score, when that node is under
        # the 20% threshold - discourages such nodes without banning
        # them outright.
        self.low_energy_penalty = low_energy_penalty
        # Much harsher multiplier for nodes under the critical threshold -
        # strongly discouraged, but (unlike the previous implementation)
        # never removed from the connectivity graph itself, so EAURP keeps
        # exactly the same reachability as AODV and only loses PDR/
        # throughput when a genuinely better route isn't available.
        self.critical_energy_penalty = critical_energy_penalty

    def _eligible_nodes(self):
        # EAURP keeps the SAME eligible/connectivity graph as AODV (every
        # alive node). Energy-awareness is expressed entirely through
        # route scoring (see score_route), not by shrinking the topology -
        # this is what keeps EAURP's reachability, and therefore its PDR
        # and throughput, at least as good as AODV's.
        return {n.node_id for n in self.network.alive_nodes()}

    def is_route_valid(self, path):
        """
        In addition to the base liveness/in-range checks, EAURP treats a
        cached route as stale as soon as any of its intermediate nodes
        drops under the critical-energy threshold. This is the core of
        EAURP's energy-awareness in route *maintenance*, not just initial
        discovery: it proactively reroutes traffic off a dying node before
        that node actually runs out of energy and breaks the link,
        instead of reacting only after the fact like baseline AODV. This
        both protects the draining node (extending overall network
        lifetime) and avoids the packet losses that would otherwise occur
        once that node finally dies mid-transmission.
        """
        if not super().is_route_valid(path):
            return False
        for node_id in path[1:-1]:
            node = self.network.get_node(node_id)
            if node.is_low_energy(self.critical_energy_threshold):
                return False
        return True

    def _link_stability(self, a_id, b_id):
        """
        Stability of a single hop, in [0, 1]: 1.0 means the two nodes are
        right on top of each other (very stable link), 0.0 means they are
        right at the edge of transmission range (about to break under any
        further mobility).
        """
        net = self.network
        a = net.get_node(a_id)
        b = net.get_node(b_id)
        dist = net.euclidean_distance(a, b)
        margin = 1.0 - (dist / net.transmission_range)
        return max(0.0, min(1.0, margin))

    def score_route(self, path):
        """
        Composite route score (higher is better):

            score = energy_weight    * avg_effective_energy(intermediates)
                  + stability_weight * avg_link_stability(hops)
                  - hop_weight       * normalized_hop_count

        where:
          - avg_effective_energy is the mean of each intermediate node's
            normalized residual energy (E_i / E_init), further scaled
            down by `low_energy_penalty` for any node currently under the
            20% threshold - so such nodes are discouraged, not banned.
            A direct route with no intermediates scores the maximum 1.0
            here, naturally favoring direct links.
          - avg_link_stability is the mean per-hop stability (distance
            margin relative to transmission range) across the whole path.
          - normalized_hop_count = (hop_count - 1) / 6.0, a mild,
            bounded penalty so EAURP does not chase small energy/stability
            gains via unreasonably long detours.
        """
        hop_count = len(path) - 1
        intermediates = path[1:-1]

        if intermediates:
            effective_energies = []
            for nid in intermediates:
                node = self.network.get_node(nid)
                norm_e = node.normalized_energy()
                if node.is_low_energy(self.critical_energy_threshold):
                    norm_e *= self.critical_energy_penalty
                elif node.is_low_energy(self.low_energy_threshold):
                    norm_e *= self.low_energy_penalty
                effective_energies.append(norm_e)
            avg_energy = sum(effective_energies) / len(effective_energies)
        else:
            avg_energy = 1.0

        stabilities = [self._link_stability(path[i], path[i + 1])
                       for i in range(len(path) - 1)]
        avg_stability = sum(stabilities) / len(stabilities) if stabilities else 1.0

        normalized_hops = max(0, hop_count - 1) / 6.0

        score = (
            self.energy_weight * avg_energy
            + self.stability_weight * avg_stability
            - self.hop_weight * normalized_hops
        )
        return score

    # Minimum score improvement a longer-than-shortest candidate must show
    # over the plain shortest-hop candidate before EAURP will accept the
    # extra hop. This directly enforces "do not take unnecessarily long
    # routes just to dodge moderately lower energy" - a detour is only
    # worth it when it provides a clear, meaningful benefit, not a
    # marginal one.
    ROUTE_IMPROVEMENT_MARGIN = 0.12

    def select_route(self, candidate_paths):
        shortest_len = min(len(p) for p in candidate_paths)
        shortest_candidates = [p for p in candidate_paths if len(p) == shortest_len]
        best_shortest = max(shortest_candidates,
                             key=lambda path: self.score_route(path))
        best_shortest_score = self.score_route(best_shortest)

        longer_candidates = [p for p in candidate_paths if len(p) > shortest_len]
        if not longer_candidates:
            return best_shortest

        best_longer = max(longer_candidates, key=lambda path: self.score_route(path))
        best_longer_score = self.score_route(best_longer)

        # Only take the longer route if it clears the improvement margin;
        # otherwise stick with the best-scoring route among the
        # shortest-hop candidates, exactly like AODV would in terms of
        # path length.
        if best_longer_score >= best_shortest_score + self.ROUTE_IMPROVEMENT_MARGIN:
            return best_longer
        return best_shortest
