"""Deterministic fixed-resource search for the demand-aware HPN topology."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
from itertools import combinations

from secondaryexploration.topology import HypergraphTopology, ParentGraph

from .demand import (
    DemandAwareObjectiveScore,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    OptimizationError,
    score_demand_aware_topology,
    validate_demand_aware_topology,
)


CANDIDATE_GENERATOR_VERSION = "connected-demand-candidates.v1"
TOPOLOGY_SEARCH_VERSION = "fixed-incidence-local-search.v1"
EXHAUSTIVE_CANDIDATE_NODE_LIMIT = 10
_MAX_UNSIGNED_64 = 2**64 - 1


@dataclass(frozen=True, slots=True)
class ConnectedCandidate:
    """One parent-connected membership and its exact proposal priority."""

    members: tuple[str, ...]
    priority: Fraction

    def __post_init__(self) -> None:
        if type(self.members) is not tuple or len(self.members) < 2:
            raise OptimizationError("candidate members must be a tuple of arity two+")
        if tuple(sorted(self.members)) != self.members or len(set(self.members)) != len(
            self.members
        ):
            raise OptimizationError("candidate members must be canonical and unique")
        if not isinstance(self.priority, Fraction):
            raise OptimizationError("candidate priority must be an exact Fraction")


@dataclass(frozen=True, slots=True)
class ConnectedCandidatePool:
    """Replayable connected-subset pool ordered by exact proposal priority."""

    manifest_fingerprint: str
    candidates: tuple[ConnectedCandidate, ...]
    generator_version: str = CANDIDATE_GENERATOR_VERSION

    def __post_init__(self) -> None:
        _validate_digest(self.manifest_fingerprint, "manifest_fingerprint")
        if self.generator_version != CANDIDATE_GENERATOR_VERSION:
            raise OptimizationError("unsupported candidate generator version")
        if type(self.candidates) is not tuple or not self.candidates:
            raise OptimizationError("candidate pool must be a nonempty tuple")
        if any(not isinstance(item, ConnectedCandidate) for item in self.candidates):
            raise OptimizationError("candidate pool contains a malformed candidate")
        memberships = tuple(item.members for item in self.candidates)
        if len(set(memberships)) != len(memberships):
            raise OptimizationError("candidate pool contains duplicate memberships")
        if tuple(sorted(self.candidates, key=_candidate_order_key)) != self.candidates:
            raise OptimizationError("candidate pool is not in canonical priority order")

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.connected-candidate-pool.v1\x00")
        _hash_field(digest, self.manifest_fingerprint)
        _hash_field(digest, self.generator_version)
        _hash_count(digest, len(self.candidates))
        for candidate in self.candidates:
            _hash_count(digest, len(candidate.members))
            for member in candidate.members:
                _hash_field(digest, member)
            _hash_integer(digest, candidate.priority.numerator)
            _hash_count(digest, candidate.priority.denominator)
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class DemandAwareSearchPlan:
    """Common deterministic compute budget for topology training."""

    proposal_budget: int
    maximum_rounds: int
    maximum_move_edges: int = 3
    candidate_generator_version: str = CANDIDATE_GENERATOR_VERSION
    search_version: str = TOPOLOGY_SEARCH_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("proposal_budget", self.proposal_budget),
            ("maximum_rounds", self.maximum_rounds),
        ):
            if type(value) is not int or not 1 <= value <= _MAX_UNSIGNED_64:
                raise OptimizationError(f"{name} must be a positive unsigned-64 integer")
        if (
            type(self.maximum_move_edges) is not int
            or not 1 <= self.maximum_move_edges <= 3
        ):
            raise OptimizationError("maximum_move_edges must be in [1, 3]")
        if self.candidate_generator_version != CANDIDATE_GENERATOR_VERSION:
            raise OptimizationError("unsupported candidate generator version")
        if self.search_version != TOPOLOGY_SEARCH_VERSION:
            raise OptimizationError("unsupported topology search version")

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.demand-search-plan.v1\x00")
        _hash_count(digest, self.proposal_budget)
        _hash_count(digest, self.maximum_rounds)
        _hash_count(digest, self.maximum_move_edges)
        _hash_field(digest, self.candidate_generator_version)
        _hash_field(digest, self.search_version)
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class DemandAwareSearchStep:
    """One accepted best-improvement round with exact accounting."""

    round_index: int
    proposal_start: int
    proposal_stop: int
    feasible_evaluations: int
    before_objective: Fraction
    after_objective: Fraction
    accepted_topology_fingerprint: str

    def __post_init__(self) -> None:
        if type(self.round_index) is not int or self.round_index < 1:
            raise OptimizationError("round_index must be positive")
        if (
            type(self.proposal_start) is not int
            or type(self.proposal_stop) is not int
            or not 0 <= self.proposal_start < self.proposal_stop
        ):
            raise OptimizationError("search-step proposal bounds are inconsistent")
        if (
            type(self.feasible_evaluations) is not int
            or not 1 <= self.feasible_evaluations <= self.proposal_stop - self.proposal_start
        ):
            raise OptimizationError("search-step feasible evaluation count is invalid")
        if not isinstance(self.before_objective, Fraction) or not isinstance(
            self.after_objective, Fraction
        ):
            raise OptimizationError("search-step objectives must be Fractions")
        if self.after_objective <= self.before_objective:
            raise OptimizationError("an accepted search step must strictly improve")
        _validate_digest(
            self.accepted_topology_fingerprint,
            "accepted_topology_fingerprint",
        )


@dataclass(frozen=True, slots=True)
class DemandAwareTopologyResult:
    """Input-bound result of complete deterministic topology training."""

    manifest_fingerprint: str
    seed_topology_fingerprint: str
    candidate_pool_fingerprint: str
    search_plan: DemandAwareSearchPlan
    proposal_fingerprints: tuple[str, ...]
    feasible_evaluations: int
    steps: tuple[DemandAwareSearchStep, ...]
    topology: HypergraphTopology
    score: DemandAwareObjectiveScore

    def __post_init__(self) -> None:
        _validate_digest(self.manifest_fingerprint, "manifest_fingerprint")
        _validate_digest(self.seed_topology_fingerprint, "seed_topology_fingerprint")
        _validate_digest(self.candidate_pool_fingerprint, "candidate_pool_fingerprint")
        if not isinstance(self.search_plan, DemandAwareSearchPlan):
            raise OptimizationError("search_plan must be a DemandAwareSearchPlan")
        if type(self.proposal_fingerprints) is not tuple or any(
            not _is_digest(value) for value in self.proposal_fingerprints
        ):
            raise OptimizationError("proposal_fingerprints must be SHA-256 values")
        if len(self.proposal_fingerprints) > self.search_plan.proposal_budget:
            raise OptimizationError("proposal record exceeds the search budget")
        if (
            type(self.feasible_evaluations) is not int
            or not 0 <= self.feasible_evaluations <= len(self.proposal_fingerprints)
        ):
            raise OptimizationError("feasible_evaluations is inconsistent")
        if type(self.steps) is not tuple or any(
            not isinstance(step, DemandAwareSearchStep) for step in self.steps
        ):
            raise OptimizationError("steps must be a search-step tuple")
        if len(self.steps) > self.search_plan.maximum_rounds:
            raise OptimizationError("accepted steps exceed maximum_rounds")
        if tuple(step.round_index for step in self.steps) != tuple(
            range(1, len(self.steps) + 1)
        ):
            raise OptimizationError("search-step indices must be consecutive")
        if not isinstance(self.topology, HypergraphTopology):
            raise OptimizationError("topology must be a HypergraphTopology")
        if not isinstance(self.score, DemandAwareObjectiveScore):
            raise OptimizationError("score must be a DemandAwareObjectiveScore")
        if self.score.manifest_fingerprint != self.manifest_fingerprint:
            raise OptimizationError("final score is not bound to the result manifest")

    @property
    def proposals_considered(self) -> int:
        return len(self.proposal_fingerprints)


def generate_connected_candidate_pool(
    parent: ParentGraph,
    demand: DirectedDemandMatrix,
    manifest: DemandAwareTrainingManifest,
) -> ConnectedCandidatePool:
    """Generate the exact registered connected-subset proposal pool."""

    _validate_manifest_inputs(parent, demand, manifest)
    maximum_arity = manifest.maximum_arity
    memberships: set[tuple[str, ...]] = set()
    if len(parent.nodes) <= EXHAUSTIVE_CANDIDATE_NODE_LIMIT:
        for arity in range(2, maximum_arity + 1):
            for members in combinations(parent.nodes, arity):
                if _members_connected(parent, members):
                    memberships.add(members)
    else:
        for edge in parent.edges:
            memberships.add(edge.endpoints)
        for node_id in parent.nodes:
            for mode in ("canonical", "demand"):
                memberships.update(
                    _connected_expansion(
                        parent,
                        demand,
                        manifest,
                        (node_id,),
                        maximum_arity,
                        mode,
                    )
                )
        for edge in parent.edges:
            for mode in ("canonical", "demand"):
                memberships.update(
                    _connected_expansion(
                        parent,
                        demand,
                        manifest,
                        edge.endpoints,
                        maximum_arity,
                        mode,
                    )
                )
    candidates = tuple(
        sorted(
            (
                ConnectedCandidate(
                    members,
                    _candidate_priority(demand, members, manifest),
                )
                for members in memberships
            ),
            key=_candidate_order_key,
        )
    )
    return ConnectedCandidatePool(manifest.fingerprint, candidates)


def validate_connected_candidate_pool(
    pool: ConnectedCandidatePool,
    parent: ParentGraph,
    demand: DirectedDemandMatrix,
    manifest: DemandAwareTrainingManifest,
) -> None:
    """Regenerate the candidate pool and reject any altered record."""

    if not isinstance(pool, ConnectedCandidatePool):
        raise OptimizationError("pool must be a ConnectedCandidatePool")
    exact = generate_connected_candidate_pool(parent, demand, manifest)
    if pool != exact:
        raise OptimizationError("candidate pool does not match complete regeneration")


def train_demand_aware_topology(
    parent: ParentGraph,
    demand: DirectedDemandMatrix,
    seed_topology: HypergraphTopology,
    manifest: DemandAwareTrainingManifest,
    search_plan: DemandAwareSearchPlan,
) -> DemandAwareTopologyResult:
    """Train a fixed-resource topology with deterministic best-improvement search."""

    _validate_manifest_inputs(parent, demand, manifest)
    if not isinstance(search_plan, DemandAwareSearchPlan):
        raise OptimizationError("search_plan must be a DemandAwareSearchPlan")
    validate_demand_aware_topology(parent, seed_topology, manifest)
    current_topology = seed_topology
    current_score = score_demand_aware_topology(
        parent,
        demand,
        current_topology,
        manifest,
    )
    seed_fingerprint = current_score.topology_fingerprint
    pool = generate_connected_candidate_pool(parent, demand, manifest)
    proposal_fingerprints: list[str] = []
    total_feasible = 0
    steps: list[DemandAwareSearchStep] = []

    for round_index in range(1, search_plan.maximum_rounds + 1):
        if len(proposal_fingerprints) >= search_plan.proposal_budget:
            break
        proposal_start = len(proposal_fingerprints)
        round_feasible = 0
        best_topology: HypergraphTopology | None = None
        best_score: DemandAwareObjectiveScore | None = None
        current_memberships = tuple(
            edge.members for edge in current_topology.hyperedges
        )
        for proposed_memberships in _proposal_membership_stream(
            current_memberships,
            pool,
            search_plan.maximum_move_edges,
        ):
            if len(proposal_fingerprints) >= search_plan.proposal_budget:
                break
            proposal_fingerprints.append(
                _membership_collection_fingerprint(proposed_memberships)
            )
            if len(set(proposed_memberships)) != len(proposed_memberships):
                continue
            proposed = _topology_from_memberships(parent.nodes, proposed_memberships)
            try:
                validate_demand_aware_topology(parent, proposed, manifest)
            except OptimizationError:
                continue
            proposed_score = score_demand_aware_topology(
                parent,
                demand,
                proposed,
                manifest,
            )
            round_feasible += 1
            total_feasible += 1
            if proposed_score.objective_value <= current_score.objective_value:
                continue
            if best_score is None or (
                proposed_score.objective_value > best_score.objective_value
                or (
                    proposed_score.objective_value == best_score.objective_value
                    and proposed_score.topology_fingerprint
                    < best_score.topology_fingerprint
                )
            ):
                best_topology = proposed
                best_score = proposed_score
        if best_topology is None or best_score is None:
            break
        steps.append(
            DemandAwareSearchStep(
                round_index=round_index,
                proposal_start=proposal_start,
                proposal_stop=len(proposal_fingerprints),
                feasible_evaluations=round_feasible,
                before_objective=current_score.objective_value,
                after_objective=best_score.objective_value,
                accepted_topology_fingerprint=best_score.topology_fingerprint,
            )
        )
        current_topology = best_topology
        current_score = best_score

    return DemandAwareTopologyResult(
        manifest_fingerprint=manifest.fingerprint,
        seed_topology_fingerprint=seed_fingerprint,
        candidate_pool_fingerprint=pool.fingerprint,
        search_plan=search_plan,
        proposal_fingerprints=tuple(proposal_fingerprints),
        feasible_evaluations=total_feasible,
        steps=tuple(steps),
        topology=current_topology,
        score=current_score,
    )


def validate_demand_aware_topology_result(
    result: DemandAwareTopologyResult,
    parent: ParentGraph,
    demand: DirectedDemandMatrix,
    seed_topology: HypergraphTopology,
    manifest: DemandAwareTrainingManifest,
    search_plan: DemandAwareSearchPlan,
) -> None:
    """Rerun candidate generation and search, rejecting any altered result."""

    if not isinstance(result, DemandAwareTopologyResult):
        raise OptimizationError("result must be a DemandAwareTopologyResult")
    if not isinstance(search_plan, DemandAwareSearchPlan):
        raise OptimizationError("search_plan must be a DemandAwareSearchPlan")
    if result.search_plan != search_plan:
        raise OptimizationError("result is not bound to the expected search plan")
    exact = train_demand_aware_topology(
        parent,
        demand,
        seed_topology,
        manifest,
        search_plan,
    )
    if result != exact:
        raise OptimizationError("topology result does not match complete training replay")


def _proposal_membership_stream(
    current_memberships: tuple[tuple[str, ...], ...],
    pool: ConnectedCandidatePool,
    maximum_move_edges: int,
):
    classes = tuple(
        (removed_count, added_count)
        for removed_count in range(1, maximum_move_edges + 1)
        for added_count in range(1, maximum_move_edges + 1)
    )
    iterators = [
        iter(
            _proposal_class(
                current_memberships,
                pool.candidates,
                removed_count,
                added_count,
            )
        )
        for removed_count, added_count in classes
    ]
    active = list(iterators)
    emitted = {tuple(sorted(current_memberships))}
    while active:
        next_active = []
        for iterator in active:
            try:
                proposal = next(iterator)
            except StopIteration:
                continue
            next_active.append(iterator)
            if proposal in emitted:
                continue
            emitted.add(proposal)
            yield proposal
        active = next_active


def _proposal_class(
    current_memberships: tuple[tuple[str, ...], ...],
    candidates: tuple[ConnectedCandidate, ...],
    removed_count: int,
    added_count: int,
):
    possible_added_incidence = _possible_arity_sums(
        tuple(len(candidate.members) for candidate in candidates),
        added_count,
    )
    possible_removed_incidence = _possible_arity_sums(
        tuple(len(members) for members in current_memberships),
        removed_count,
    )
    if possible_added_incidence.isdisjoint(possible_removed_incidence):
        return
    for removed_indices in combinations(range(len(current_memberships)), removed_count):
        removed_set = set(removed_indices)
        retained = tuple(
            members
            for index, members in enumerate(current_memberships)
            if index not in removed_set
        )
        target_incidence = sum(
            len(current_memberships[index]) for index in removed_indices
        )
        if target_incidence not in possible_added_incidence:
            continue
        for additions in _candidate_combinations(
            candidates,
            added_count,
            target_incidence,
        ):
            yield tuple(sorted(retained + additions))


def _candidate_combinations(
    candidates: tuple[ConnectedCandidate, ...],
    count: int,
    target_incidence: int,
):
    def visit(start: int, remaining_count: int, remaining_incidence: int, chosen):
        if remaining_count == 0:
            if remaining_incidence == 0:
                yield tuple(chosen)
            return
        if remaining_incidence < 2 * remaining_count:
            return
        for index in range(start, len(candidates)):
            members = candidates[index].members
            arity = len(members)
            if arity > remaining_incidence - 2 * (remaining_count - 1):
                continue
            chosen.append(members)
            yield from visit(
                index + 1,
                remaining_count - 1,
                remaining_incidence - arity,
                chosen,
            )
            chosen.pop()

    yield from visit(0, count, target_incidence, [])


def _possible_arity_sums(arities: tuple[int, ...], count: int) -> set[int]:
    reachable = [set() for _ in range(count + 1)]
    reachable[0].add(0)
    for arity in arities:
        for selected_count in range(count, 0, -1):
            reachable[selected_count].update(
                subtotal + arity
                for subtotal in reachable[selected_count - 1]
            )
    return reachable[count]


def _connected_expansion(
    parent: ParentGraph,
    demand: DirectedDemandMatrix,
    manifest: DemandAwareTrainingManifest,
    seed: tuple[str, ...],
    maximum_arity: int,
    mode: str,
) -> tuple[tuple[str, ...], ...]:
    selected = set(seed)
    outputs: list[tuple[str, ...]] = []
    if len(selected) >= 2:
        outputs.append(tuple(sorted(selected)))
    while len(selected) < maximum_arity:
        frontier = {
            neighbor
            for member in selected
            for neighbor in parent.neighbors(member)
            if neighbor not in selected
        }
        if not frontier:
            break
        if mode == "canonical":
            chosen = min(frontier)
        elif mode == "demand":
            chosen = min(
                frontier,
                key=lambda candidate: (
                    -_frontier_priority(demand, selected, candidate, manifest),
                    candidate,
                ),
            )
        else:
            raise RuntimeError("unknown connected-expansion mode")
        selected.add(chosen)
        outputs.append(tuple(sorted(selected)))
    return tuple(outputs)


def _frontier_priority(
    demand: DirectedDemandMatrix,
    selected: set[str],
    candidate: str,
    manifest: DemandAwareTrainingManifest,
) -> Fraction:
    return sum(
        _pair_priority(demand, candidate, member, manifest)
        for member in selected
    )


def _candidate_priority(
    demand: DirectedDemandMatrix,
    members: tuple[str, ...],
    manifest: DemandAwareTrainingManifest,
) -> Fraction:
    pair_score = sum(
        _pair_priority(demand, left, right, manifest)
        for left, right in combinations(members, 2)
    )
    coordination_upper = _coordination_upper(manifest)
    coordination = (
        Fraction(len(members) * (len(members) - 1) // 2, coordination_upper)
        if coordination_upper
        else Fraction(0, 1)
    )
    return pair_score - manifest.weights.coordination_overlap * coordination


def _pair_priority(
    demand: DirectedDemandMatrix,
    left: str,
    right: str,
    manifest: DemandAwareTrainingManifest,
) -> Fraction:
    capture_total = demand.total_bidirectional_volume
    imbalance_total = demand.total_directional_imbalance
    capture = min(demand.amount(left, right), demand.amount(right, left))
    imbalance = abs(demand.amount(left, right) - demand.amount(right, left))
    capture_term = Fraction(capture, capture_total) if capture_total else Fraction(0, 1)
    imbalance_term = (
        Fraction(imbalance, imbalance_total)
        if imbalance_total
        else Fraction(0, 1)
    )
    return (
        manifest.weights.bidirectional_capture * capture_term
        - manifest.weights.directional_imbalance * imbalance_term
    )


def _coordination_upper(manifest: DemandAwareTrainingManifest) -> int:
    incidence_budget = manifest.incidence_budget
    maximum_arity = manifest.maximum_arity
    return (
        incidence_budget * (maximum_arity - 1) // 2
        + (incidence_budget // 2) * (incidence_budget // 2 - 1) // 2
        * (maximum_arity * (maximum_arity - 1) // 2)
    )


def _members_connected(parent: ParentGraph, members: tuple[str, ...]) -> bool:
    allowed = set(members)
    visited = {members[0]}
    frontier = [members[0]]
    while frontier:
        current = frontier.pop()
        for neighbor in parent.neighbors(current):
            if neighbor in allowed and neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return len(visited) == len(members)


def _validate_manifest_inputs(
    parent: object,
    demand: object,
    manifest: object,
) -> None:
    if not isinstance(parent, ParentGraph):
        raise OptimizationError("parent must be a ParentGraph")
    if not parent.is_connected:
        raise OptimizationError("candidate generation requires a connected parent")
    if not isinstance(demand, DirectedDemandMatrix):
        raise OptimizationError("demand must be a DirectedDemandMatrix")
    if not isinstance(manifest, DemandAwareTrainingManifest):
        raise OptimizationError("manifest must be a DemandAwareTrainingManifest")
    expected = DemandAwareTrainingManifest.create(
        parent,
        demand,
        manifest.incidence_budget,
        manifest.maximum_arity,
        manifest.weights,
    )
    if manifest != expected:
        raise OptimizationError("manifest does not bind candidate-generation inputs")


def _topology_from_memberships(
    nodes: tuple[str, ...],
    memberships: tuple[tuple[str, ...], ...],
) -> HypergraphTopology:
    canonical = tuple(sorted(memberships))
    return HypergraphTopology.from_edges(
        nodes,
        {
            f"demand-edge-{index:08d}": members
            for index, members in enumerate(canonical)
        },
    )


def _membership_collection_fingerprint(
    memberships: tuple[tuple[str, ...], ...],
) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.demand-proposal-memberships.v1\x00")
    canonical = tuple(sorted(memberships))
    _hash_count(digest, len(canonical))
    for members in canonical:
        _hash_count(digest, len(members))
        for member in members:
            _hash_field(digest, member)
    return digest.hexdigest()


def _candidate_order_key(candidate: ConnectedCandidate):
    return (-candidate.priority, len(candidate.members), candidate.members)


def _validate_digest(value: object, field: str) -> None:
    if not _is_digest(value):
        raise OptimizationError(f"{field} must be lowercase SHA-256 hexadecimal")


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _hash_field(digest, value: str) -> None:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise OptimizationError("fingerprinted text must be valid UTF-8") from exc
    _hash_count(digest, len(encoded))
    digest.update(encoded)


def _hash_count(digest, value: int) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise OptimizationError("fingerprint count must be an unsigned 64-bit integer")
    digest.update(value.to_bytes(8, "big"))


def _hash_integer(digest, value: int) -> None:
    sign = b"-" if value < 0 else b"+"
    magnitude = str(abs(value)).encode("ascii")
    digest.update(sign)
    _hash_count(digest, len(magnitude))
    digest.update(magnitude)


__all__ = [
    "CANDIDATE_GENERATOR_VERSION",
    "EXHAUSTIVE_CANDIDATE_NODE_LIMIT",
    "TOPOLOGY_SEARCH_VERSION",
    "ConnectedCandidate",
    "ConnectedCandidatePool",
    "DemandAwareSearchPlan",
    "DemandAwareSearchStep",
    "DemandAwareTopologyResult",
    "generate_connected_candidate_pool",
    "train_demand_aware_topology",
    "validate_connected_candidate_pool",
    "validate_demand_aware_topology_result",
]
