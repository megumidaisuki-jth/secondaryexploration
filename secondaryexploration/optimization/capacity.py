"""Common fixed-node-capital optimization across structural topologies."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import hashlib

from secondaryexploration.experiments.paired import route_choice_rng
from secondaryexploration.model import HypergraphState
from secondaryexploration.randomness import derive_seed
from secondaryexploration.simulation import run_core_trace_with_request_rngs
from secondaryexploration.topology import (
    HypergraphTopology,
    node_budget_capital_state,
    node_capital_totals,
)
from secondaryexploration.traffic import RequestTrace

from .demand import DirectedDemandMatrix, OptimizationError


CAPACITY_INITIALIZER_VERSION = "load-risk-hamilton.v1"
CAPACITY_OBJECTIVE_VERSION = "regime-lower-quantile-maximin.v1"
CAPACITY_SEARCH_VERSION = "projected-ticket-coordinate.v1"
_MAX_UNSIGNED_64 = 2**64 - 1


@dataclass(frozen=True, slots=True)
class CapacityTrainingScenario:
    """One registered training trace and its route-choice ticket family."""

    scenario_id: str
    regime_id: str
    trace: RequestTrace
    routing_root_seed: int
    _fingerprint: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _validate_identifier(self.scenario_id, "scenario_id")
        _validate_identifier(self.regime_id, "regime_id")
        if not isinstance(self.trace, RequestTrace):
            raise OptimizationError("trace must be a RequestTrace")
        if self.trace.length < 1:
            raise OptimizationError("capacity-training traces must be nonempty")
        _validate_unsigned_64(self.routing_root_seed, "routing_root_seed")
        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.capacity-scenario.v1\x00")
        _hash_field(digest, self.scenario_id)
        _hash_field(digest, self.regime_id)
        _hash_count(digest, self.routing_root_seed)
        _hash_count(digest, self.trace.length)
        _hash_count(digest, self.trace.root_seed)
        _hash_field(digest, self.trace.kernel.fingerprint)
        _hash_field(digest, self.trace.amount_distribution.fingerprint)
        _hash_count(digest, len(self.trace.requests))
        for request in self.trace.requests:
            _hash_field(digest, request.source)
            _hash_field(digest, request.destination)
            _hash_integer(digest, request.amount)
        object.__setattr__(self, "_fingerprint", digest.hexdigest())

    @property
    def fingerprint(self) -> str:
        return self._fingerprint


@dataclass(frozen=True, slots=True)
class CapacityOptimizationManifest:
    """Topology-independent frozen inputs for common capacity training."""

    nodes: tuple[str, ...]
    demand_fingerprint: str
    per_node_capital: int
    load_weight: Fraction
    risk_weight: Fraction
    lower_quantile: Fraction
    scenarios: tuple[CapacityTrainingScenario, ...]
    initializer_version: str = CAPACITY_INITIALIZER_VERSION
    objective_version: str = CAPACITY_OBJECTIVE_VERSION
    _fingerprint: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.nodes) is not tuple or len(self.nodes) < 2:
            raise OptimizationError("nodes must be a canonical tuple of at least two")
        for node_id in self.nodes:
            _validate_identifier(node_id, "node")
        if len(set(self.nodes)) != len(self.nodes) or tuple(sorted(self.nodes)) != self.nodes:
            raise OptimizationError("nodes must be unique and canonical")
        _validate_digest(self.demand_fingerprint, "demand_fingerprint")
        if (
            type(self.per_node_capital) is not int
            or not 1 <= self.per_node_capital <= _MAX_UNSIGNED_64
        ):
            raise OptimizationError("per_node_capital must be a positive unsigned-64 integer")
        for name, weight in (
            ("load_weight", self.load_weight),
            ("risk_weight", self.risk_weight),
        ):
            if not isinstance(weight, Fraction) or weight < 0:
                raise OptimizationError(f"{name} must be a nonnegative Fraction")
        if not isinstance(self.lower_quantile, Fraction) or not (
            0 < self.lower_quantile <= 1
        ):
            raise OptimizationError("lower_quantile must be a Fraction in (0, 1]")
        if type(self.scenarios) is not tuple or not self.scenarios:
            raise OptimizationError("scenarios must be a nonempty tuple")
        if any(not isinstance(item, CapacityTrainingScenario) for item in self.scenarios):
            raise OptimizationError("scenarios contain a malformed entry")
        scenario_ids = tuple(item.scenario_id for item in self.scenarios)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise OptimizationError("scenario identifiers must be unique")
        if tuple(sorted(self.scenarios, key=_scenario_order_key)) != self.scenarios:
            raise OptimizationError("scenarios must be in canonical regime/scenario order")
        horizons = {item.trace.length for item in self.scenarios}
        if len(horizons) != 1:
            raise OptimizationError("all capacity-training traces must share one horizon")
        if any(item.trace.kernel.nodes != self.nodes for item in self.scenarios):
            raise OptimizationError("scenario nodes do not match the manifest nodes")
        if self.initializer_version != CAPACITY_INITIALIZER_VERSION:
            raise OptimizationError("unsupported capacity initializer version")
        if self.objective_version != CAPACITY_OBJECTIVE_VERSION:
            raise OptimizationError("unsupported capacity objective version")

        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.capacity-manifest.v1\x00")
        _hash_count(digest, len(self.nodes))
        for node_id in self.nodes:
            _hash_field(digest, node_id)
        _hash_field(digest, self.demand_fingerprint)
        _hash_count(digest, self.per_node_capital)
        for value in (self.load_weight, self.risk_weight, self.lower_quantile):
            _hash_integer(digest, value.numerator)
            _hash_count(digest, value.denominator)
        _hash_count(digest, len(self.scenarios))
        for scenario in self.scenarios:
            _hash_field(digest, scenario.fingerprint)
        _hash_field(digest, self.initializer_version)
        _hash_field(digest, self.objective_version)
        object.__setattr__(self, "_fingerprint", digest.hexdigest())

    @classmethod
    def create(
        cls,
        demand: DirectedDemandMatrix,
        per_node_capital: int,
        load_weight: Fraction,
        risk_weight: Fraction,
        lower_quantile: Fraction,
        scenarios: tuple[CapacityTrainingScenario, ...],
    ) -> "CapacityOptimizationManifest":
        if not isinstance(demand, DirectedDemandMatrix):
            raise OptimizationError("demand must be a DirectedDemandMatrix")
        manifest = cls(
            nodes=demand.nodes,
            demand_fingerprint=demand.fingerprint,
            per_node_capital=per_node_capital,
            load_weight=load_weight,
            risk_weight=risk_weight,
            lower_quantile=lower_quantile,
            scenarios=scenarios,
        )
        _validate_registered_demand(demand, manifest)
        return manifest

    @property
    def fingerprint(self) -> str:
        return self._fingerprint


@dataclass(frozen=True, slots=True)
class CapacityOptimizationPlan:
    """Common full-objective evaluation budget and proposal schedule."""

    evaluation_budget: int
    proposal_root_seed: int
    proposals_per_step_level: int
    search_version: str = CAPACITY_SEARCH_VERSION

    def __post_init__(self) -> None:
        if (
            type(self.evaluation_budget) is not int
            or not 2 <= self.evaluation_budget <= _MAX_UNSIGNED_64
        ):
            raise OptimizationError("evaluation_budget must be an integer in [2, 2**64 - 1]")
        _validate_unsigned_64(self.proposal_root_seed, "proposal_root_seed")
        if (
            type(self.proposals_per_step_level) is not int
            or not 1 <= self.proposals_per_step_level <= _MAX_UNSIGNED_64
        ):
            raise OptimizationError("proposals_per_step_level must be positive")
        if self.search_version != CAPACITY_SEARCH_VERSION:
            raise OptimizationError("unsupported capacity search version")

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.capacity-search-plan.v1\x00")
        _hash_count(digest, self.evaluation_budget)
        _hash_count(digest, self.proposal_root_seed)
        _hash_count(digest, self.proposals_per_step_level)
        _hash_field(digest, self.search_version)
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class CapacityScenarioOutcome:
    """Restricted service outcome for one training scenario."""

    scenario_id: str
    regime_id: str
    horizon: int
    tau_nopath: int
    observed: bool
    accepted_requests: int

    def __post_init__(self) -> None:
        _validate_identifier(self.scenario_id, "scenario_id")
        _validate_identifier(self.regime_id, "regime_id")
        if type(self.horizon) is not int or self.horizon < 1:
            raise OptimizationError("scenario horizon must be positive")
        if type(self.tau_nopath) is not int or not 1 <= self.tau_nopath <= self.horizon:
            raise OptimizationError("tau_nopath must lie on the restricted request clock")
        if type(self.observed) is not bool:
            raise OptimizationError("observed must be boolean")
        if (
            type(self.accepted_requests) is not int
            or not 0 <= self.accepted_requests <= self.horizon
        ):
            raise OptimizationError("accepted_requests is outside the scenario horizon")


@dataclass(frozen=True, slots=True)
class CapacityObjectiveScore:
    """Exact robust objective and its complete scenario witness."""

    manifest_fingerprint: str
    state_fingerprint: str
    outcomes: tuple[CapacityScenarioOutcome, ...]
    regime_quantiles: tuple[tuple[str, int], ...]
    robust_lower_quantile: int
    regime_quantile_sum: int
    total_restricted_tau: int
    total_accepted_requests: int

    def __post_init__(self) -> None:
        _validate_digest(self.manifest_fingerprint, "manifest_fingerprint")
        _validate_digest(self.state_fingerprint, "state_fingerprint")
        if type(self.outcomes) is not tuple or not self.outcomes:
            raise OptimizationError("outcomes must be a nonempty tuple")
        if any(not isinstance(item, CapacityScenarioOutcome) for item in self.outcomes):
            raise OptimizationError("outcomes contain a malformed entry")
        scenario_ids = tuple(item.scenario_id for item in self.outcomes)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise OptimizationError("outcome scenario identifiers must be unique")
        if tuple(sorted(self.outcomes, key=lambda item: (item.regime_id, item.scenario_id))) != self.outcomes:
            raise OptimizationError("outcomes must be in canonical regime/scenario order")
        if type(self.regime_quantiles) is not tuple or not self.regime_quantiles:
            raise OptimizationError("regime_quantiles must be a nonempty tuple")
        if any(
            type(item) is not tuple
            or len(item) != 2
            or not isinstance(item[0], str)
            or type(item[1]) is not int
            for item in self.regime_quantiles
        ):
            raise OptimizationError("regime_quantiles contain a malformed entry")
        regime_ids = tuple(item[0] for item in self.regime_quantiles)
        for regime_id in regime_ids:
            _validate_identifier(regime_id, "regime quantile identifier")
        if tuple(sorted(regime_ids)) != regime_ids or len(set(regime_ids)) != len(regime_ids):
            raise OptimizationError("regime quantiles must be canonical and unique")
        if any(type(value) is not int or value < 1 for _, value in self.regime_quantiles):
            raise OptimizationError("regime quantiles must be positive integers")
        if set(regime_ids) != {item.regime_id for item in self.outcomes}:
            raise OptimizationError("regime quantiles do not cover the outcome regimes")
        for name, value in (
            ("robust_lower_quantile", self.robust_lower_quantile),
            ("regime_quantile_sum", self.regime_quantile_sum),
            ("total_restricted_tau", self.total_restricted_tau),
            ("total_accepted_requests", self.total_accepted_requests),
        ):
            if type(value) is not int or value < 0:
                raise OptimizationError(f"{name} must be a nonnegative integer")
        expected = (
            min(value for _, value in self.regime_quantiles),
            sum(value for _, value in self.regime_quantiles),
            sum(item.tau_nopath for item in self.outcomes),
            sum(item.accepted_requests for item in self.outcomes),
        )
        observed = (
            self.robust_lower_quantile,
            self.regime_quantile_sum,
            self.total_restricted_tau,
            self.total_accepted_requests,
        )
        if observed != expected:
            raise OptimizationError("capacity objective aggregates do not match outcomes")

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update(b"secondaryexploration.capacity-score.v1\x00")
        _hash_field(digest, self.manifest_fingerprint)
        _hash_field(digest, self.state_fingerprint)
        _hash_count(digest, len(self.outcomes))
        for item in self.outcomes:
            _hash_field(digest, item.scenario_id)
            _hash_field(digest, item.regime_id)
            _hash_count(digest, item.horizon)
            _hash_count(digest, item.tau_nopath)
            _hash_count(digest, int(item.observed))
            _hash_count(digest, item.accepted_requests)
        _hash_count(digest, len(self.regime_quantiles))
        for regime_id, value in self.regime_quantiles:
            _hash_field(digest, regime_id)
            _hash_count(digest, value)
        for value in _scientific_score_key(self):
            _hash_count(digest, value)
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class CapacityProposalEvaluation:
    """One budget-consuming projected proposal and its full score."""

    evaluation_index: int
    node_id: str
    donor_edge_id: str | None
    recipient_edge_id: str | None
    requested_transfer: int
    actual_transfer: int
    state_fingerprint: str
    score: CapacityObjectiveScore

    def __post_init__(self) -> None:
        if type(self.evaluation_index) is not int or self.evaluation_index < 3:
            raise OptimizationError("proposal evaluation_index must be at least three")
        _validate_identifier(self.node_id, "proposal node_id")
        if (self.donor_edge_id is None) != (self.recipient_edge_id is None):
            raise OptimizationError("proposal edge identifiers must both be present or absent")
        if self.donor_edge_id is not None:
            _validate_identifier(self.donor_edge_id, "donor_edge_id")
            _validate_identifier(self.recipient_edge_id, "recipient_edge_id")
            if self.donor_edge_id == self.recipient_edge_id:
                raise OptimizationError("proposal donor and recipient must differ")
        if type(self.requested_transfer) is not int or self.requested_transfer < 1:
            raise OptimizationError("requested_transfer must be positive")
        if (
            type(self.actual_transfer) is not int
            or not 0 <= self.actual_transfer <= self.requested_transfer
        ):
            raise OptimizationError("actual_transfer is inconsistent")
        if self.donor_edge_id is None and self.actual_transfer != 0:
            raise OptimizationError("a degree-one proposal cannot transfer capital")
        _validate_digest(self.state_fingerprint, "state_fingerprint")
        if not isinstance(self.score, CapacityObjectiveScore):
            raise OptimizationError("proposal score is malformed")
        if self.score.state_fingerprint != self.state_fingerprint:
            raise OptimizationError("proposal score is not bound to its state")


@dataclass(frozen=True, slots=True)
class CapacityOptimizationStep:
    """One strictly accepted refinement evaluation."""

    evaluation_index: int
    before_state_fingerprint: str
    after_state_fingerprint: str
    before_score_fingerprint: str
    after_score_fingerprint: str

    def __post_init__(self) -> None:
        if type(self.evaluation_index) is not int or self.evaluation_index < 3:
            raise OptimizationError("accepted evaluation_index must be at least three")
        for name, value in (
            ("before_state_fingerprint", self.before_state_fingerprint),
            ("after_state_fingerprint", self.after_state_fingerprint),
            ("before_score_fingerprint", self.before_score_fingerprint),
            ("after_score_fingerprint", self.after_score_fingerprint),
        ):
            _validate_digest(value, name)
        if self.before_state_fingerprint == self.after_state_fingerprint:
            raise OptimizationError("an accepted step must change the state")


@dataclass(frozen=True, slots=True)
class CapacityOptimizationResult:
    """Replay-complete common capacity optimization result."""

    manifest_fingerprint: str
    topology_fingerprint: str
    plan: CapacityOptimizationPlan
    uniform_state: HypergraphState
    uniform_score: CapacityObjectiveScore
    load_risk_state: HypergraphState
    load_risk_score: CapacityObjectiveScore
    starting_source: str
    proposals: tuple[CapacityProposalEvaluation, ...]
    steps: tuple[CapacityOptimizationStep, ...]
    state: HypergraphState
    score: CapacityObjectiveScore

    def __post_init__(self) -> None:
        _validate_digest(self.manifest_fingerprint, "manifest_fingerprint")
        _validate_digest(self.topology_fingerprint, "topology_fingerprint")
        if not isinstance(self.plan, CapacityOptimizationPlan):
            raise OptimizationError("plan must be a CapacityOptimizationPlan")
        for name, state in (
            ("uniform_state", self.uniform_state),
            ("load_risk_state", self.load_risk_state),
            ("state", self.state),
        ):
            if not isinstance(state, HypergraphState):
                raise OptimizationError(f"{name} must be a HypergraphState")
        for name, score in (
            ("uniform_score", self.uniform_score),
            ("load_risk_score", self.load_risk_score),
            ("score", self.score),
        ):
            if not isinstance(score, CapacityObjectiveScore):
                raise OptimizationError(f"{name} is malformed")
            if score.manifest_fingerprint != self.manifest_fingerprint:
                raise OptimizationError(f"{name} is not bound to the manifest")
        if self.starting_source not in {"uniform", "load-risk"}:
            raise OptimizationError("starting_source is unsupported")
        if type(self.proposals) is not tuple or any(
            not isinstance(item, CapacityProposalEvaluation) for item in self.proposals
        ):
            raise OptimizationError("proposals must be a proposal tuple")
        if len(self.proposals) != self.plan.evaluation_budget - 2:
            raise OptimizationError("proposal count does not exhaust the common budget")
        if tuple(item.evaluation_index for item in self.proposals) != tuple(
            range(3, self.plan.evaluation_budget + 1)
        ):
            raise OptimizationError("proposal evaluation indices must be consecutive")
        if type(self.steps) is not tuple or any(
            not isinstance(item, CapacityOptimizationStep) for item in self.steps
        ):
            raise OptimizationError("steps must be an accepted-step tuple")
        if tuple(item.evaluation_index for item in self.steps) != tuple(
            sorted(item.evaluation_index for item in self.steps)
        ):
            raise OptimizationError("accepted steps must be in evaluation order")
        if len({item.evaluation_index for item in self.steps}) != len(self.steps):
            raise OptimizationError("accepted-step evaluation indices must be unique")
        if any(item.evaluation_index > self.plan.evaluation_budget for item in self.steps):
            raise OptimizationError("an accepted step exceeds the evaluation budget")
        if self.uniform_score.state_fingerprint != _state_fingerprint(self.uniform_state):
            raise OptimizationError("uniform score does not match uniform_state")
        if self.load_risk_score.state_fingerprint != _state_fingerprint(self.load_risk_state):
            raise OptimizationError("load/risk score does not match load_risk_state")
        if self.score.state_fingerprint != _state_fingerprint(self.state):
            raise OptimizationError("final score does not match final state")

    @property
    def evaluation_count(self) -> int:
        return 2 + len(self.proposals)


def initialize_load_risk_state(
    topology: HypergraphTopology,
    demand: DirectedDemandMatrix,
    manifest: CapacityOptimizationManifest,
) -> HypergraphState:
    """Allocate each node budget by exact load/risk Hamilton apportionment."""

    _validate_capacity_inputs(topology, demand, manifest)
    incident = _incident_edge_ids(topology)
    allocations: dict[str, dict[str, int]] = {
        edge.hyperedge_id: {} for edge in topology.hyperedges
    }
    edge_lookup = {edge.hyperedge_id: edge for edge in topology.hyperedges}
    for node_id in topology.nodes:
        edge_ids = incident[node_id]
        scores = tuple(
            (
                edge_id,
                _incidence_load_risk_score(
                    node_id,
                    edge_lookup[edge_id].members,
                    demand,
                    manifest,
                ),
            )
            for edge_id in edge_ids
        )
        apportioned = _positive_hamilton_apportionment(
            manifest.per_node_capital,
            scores,
        )
        for edge_id, amount in apportioned:
            allocations[edge_id][node_id] = amount
    state = HypergraphState.from_balances(topology.nodes, allocations)
    validate_capacity_state(topology, state, manifest)
    return state


def score_capacity_state(
    topology: HypergraphTopology,
    state: HypergraphState,
    demand: DirectedDemandMatrix,
    manifest: CapacityOptimizationManifest,
) -> CapacityObjectiveScore:
    """Evaluate one fixed allocation on every registered training scenario."""

    _validate_capacity_inputs(topology, demand, manifest)
    validate_capacity_state(topology, state, manifest)
    return _score_valid_state(state, manifest)


def optimize_common_capacity(
    topology: HypergraphTopology,
    demand: DirectedDemandMatrix,
    manifest: CapacityOptimizationManifest,
    plan: CapacityOptimizationPlan,
) -> CapacityOptimizationResult:
    """Run the common exact-budget projected stochastic allocation search."""

    _validate_capacity_inputs(topology, demand, manifest)
    if not isinstance(plan, CapacityOptimizationPlan):
        raise OptimizationError("plan must be a CapacityOptimizationPlan")

    budgets = {node_id: manifest.per_node_capital for node_id in topology.nodes}
    uniform_state = node_budget_capital_state(topology, budgets)
    validate_capacity_state(topology, uniform_state, manifest)
    uniform_score = _score_valid_state(uniform_state, manifest)
    load_risk_state = initialize_load_risk_state(topology, demand, manifest)
    load_risk_score = _score_valid_state(load_risk_state, manifest)

    if _score_is_better(load_risk_score, uniform_score):
        current_state = load_risk_state
        current_score = load_risk_score
        starting_source = "load-risk"
    else:
        current_state = uniform_state
        current_score = uniform_score
        starting_source = "uniform"

    proposals: list[CapacityProposalEvaluation] = []
    steps: list[CapacityOptimizationStep] = []
    for evaluation_index in range(3, plan.evaluation_budget + 1):
        proposal_index = evaluation_index - 2
        proposed_state, proposal_metadata = _projected_proposal(
            topology,
            current_state,
            manifest,
            plan,
            proposal_index,
        )
        proposed_score = _score_valid_state(proposed_state, manifest)
        state_fingerprint = _state_fingerprint(proposed_state)
        proposals.append(
            CapacityProposalEvaluation(
                evaluation_index=evaluation_index,
                node_id=proposal_metadata[0],
                donor_edge_id=proposal_metadata[1],
                recipient_edge_id=proposal_metadata[2],
                requested_transfer=proposal_metadata[3],
                actual_transfer=proposal_metadata[4],
                state_fingerprint=state_fingerprint,
                score=proposed_score,
            )
        )
        if _score_is_better(proposed_score, current_score):
            steps.append(
                CapacityOptimizationStep(
                    evaluation_index=evaluation_index,
                    before_state_fingerprint=_state_fingerprint(current_state),
                    after_state_fingerprint=state_fingerprint,
                    before_score_fingerprint=current_score.fingerprint,
                    after_score_fingerprint=proposed_score.fingerprint,
                )
            )
            current_state = proposed_state
            current_score = proposed_score

    return CapacityOptimizationResult(
        manifest_fingerprint=manifest.fingerprint,
        topology_fingerprint=_topology_fingerprint(topology),
        plan=plan,
        uniform_state=uniform_state,
        uniform_score=uniform_score,
        load_risk_state=load_risk_state,
        load_risk_score=load_risk_score,
        starting_source=starting_source,
        proposals=tuple(proposals),
        steps=tuple(steps),
        state=current_state,
        score=current_score,
    )


def validate_common_capacity_result(
    result: CapacityOptimizationResult,
    topology: HypergraphTopology,
    demand: DirectedDemandMatrix,
    manifest: CapacityOptimizationManifest,
    plan: CapacityOptimizationPlan,
) -> None:
    """Rerun the full optimization under independently supplied frozen inputs."""

    if not isinstance(result, CapacityOptimizationResult):
        raise OptimizationError("result must be a CapacityOptimizationResult")
    if not isinstance(plan, CapacityOptimizationPlan):
        raise OptimizationError("plan must be a CapacityOptimizationPlan")
    if result.plan != plan:
        raise OptimizationError("result is not bound to the expected capacity plan")
    exact = optimize_common_capacity(topology, demand, manifest, plan)
    if result != exact:
        raise OptimizationError("capacity result does not match complete optimization replay")


def validate_capacity_state(
    topology: HypergraphTopology,
    state: HypergraphState,
    manifest: CapacityOptimizationManifest,
) -> None:
    """Enforce unchanged topology, equal node budgets, and positive incidences."""

    if not isinstance(topology, HypergraphTopology):
        raise OptimizationError("topology must be a HypergraphTopology")
    if not isinstance(state, HypergraphState):
        raise OptimizationError("state must be a HypergraphState")
    if not isinstance(manifest, CapacityOptimizationManifest):
        raise OptimizationError("manifest must be a CapacityOptimizationManifest")
    if topology.nodes != manifest.nodes or state.nodes != topology.nodes:
        raise OptimizationError("capacity state nodes do not match the frozen node set")
    topology_structure = tuple(
        (edge.hyperedge_id, edge.members) for edge in topology.hyperedges
    )
    state_structure = tuple(
        (edge.hyperedge_id, edge.members) for edge in state.hyperedges
    )
    if state_structure != topology_structure:
        raise OptimizationError("capacity state changes the registered topology")
    if any(amount < 1 for edge in state.hyperedges for _, amount in edge.balances):
        raise OptimizationError("every optimized incidence balance must be positive")
    expected_totals = tuple(
        (node_id, manifest.per_node_capital) for node_id in topology.nodes
    )
    if node_capital_totals(state) != expected_totals:
        raise OptimizationError("capacity state violates the equal per-node budget")


def _validate_capacity_inputs(
    topology: HypergraphTopology,
    demand: DirectedDemandMatrix,
    manifest: CapacityOptimizationManifest,
) -> None:
    if not isinstance(topology, HypergraphTopology):
        raise OptimizationError("topology must be a HypergraphTopology")
    if not topology.is_connected:
        raise OptimizationError("capacity optimization requires a connected topology")
    if not isinstance(demand, DirectedDemandMatrix):
        raise OptimizationError("demand must be a DirectedDemandMatrix")
    if not isinstance(manifest, CapacityOptimizationManifest):
        raise OptimizationError("manifest must be a CapacityOptimizationManifest")
    if topology.nodes != manifest.nodes or demand.nodes != manifest.nodes:
        raise OptimizationError("capacity inputs do not share the manifest node set")
    if demand.fingerprint != manifest.demand_fingerprint:
        raise OptimizationError("training demand does not match the manifest")
    degrees = dict(topology.node_incidence_degrees)
    if any(degree < 1 for degree in degrees.values()):
        raise OptimizationError("capacity optimization does not permit isolated nodes")
    if any(manifest.per_node_capital < degree for degree in degrees.values()):
        raise OptimizationError(
            "per_node_capital must cover one positive unit per node incidence"
        )
    _validate_registered_demand(demand, manifest)


def _validate_registered_demand(
    demand: DirectedDemandMatrix,
    manifest: CapacityOptimizationManifest,
) -> None:
    combined = DirectedDemandMatrix.from_requests(
        manifest.nodes,
        tuple(
            request
            for scenario in manifest.scenarios
            for request in scenario.trace.requests
        ),
    )
    if combined != demand:
        raise OptimizationError(
            "training demand must equal the aggregate registered scenario requests"
        )


def _score_valid_state(
    state: HypergraphState,
    manifest: CapacityOptimizationManifest,
) -> CapacityObjectiveScore:
    outcomes: list[CapacityScenarioOutcome] = []
    for scenario in manifest.scenarios:
        simulation = run_core_trace_with_request_rngs(
            state,
            scenario.trace.requests,
            (
                route_choice_rng(scenario.routing_root_seed, request_index)
                for request_index in range(1, scenario.trace.length + 1)
            ),
        )
        outcomes.append(
            CapacityScenarioOutcome(
                scenario_id=scenario.scenario_id,
                regime_id=scenario.regime_id,
                horizon=scenario.trace.length,
                tau_nopath=simulation.tau_nopath.request_index,
                observed=simulation.tau_nopath.observed,
                accepted_requests=sum(item.accepted for item in simulation.outcomes),
            )
        )
    outcome_tuple = tuple(outcomes)
    regime_ids = tuple(sorted({item.regime_id for item in outcome_tuple}))
    regime_quantiles = tuple(
        (
            regime_id,
            _empirical_lower_quantile(
                tuple(
                    item.tau_nopath
                    for item in outcome_tuple
                    if item.regime_id == regime_id
                ),
                manifest.lower_quantile,
            ),
        )
        for regime_id in regime_ids
    )
    return CapacityObjectiveScore(
        manifest_fingerprint=manifest.fingerprint,
        state_fingerprint=_state_fingerprint(state),
        outcomes=outcome_tuple,
        regime_quantiles=regime_quantiles,
        robust_lower_quantile=min(value for _, value in regime_quantiles),
        regime_quantile_sum=sum(value for _, value in regime_quantiles),
        total_restricted_tau=sum(item.tau_nopath for item in outcome_tuple),
        total_accepted_requests=sum(item.accepted_requests for item in outcome_tuple),
    )


def _projected_proposal(
    topology: HypergraphTopology,
    state: HypergraphState,
    manifest: CapacityOptimizationManifest,
    plan: CapacityOptimizationPlan,
    proposal_index: int,
) -> tuple[HypergraphState, tuple[str, str | None, str | None, int, int]]:
    node_index = _unbiased_choice_index(
        plan.proposal_root_seed,
        "capacity.proposal.node",
        proposal_index,
        len(topology.nodes),
    )
    node_id = topology.nodes[node_index]
    edge_ids = _incident_edge_ids(topology)[node_id]
    step_level = (proposal_index - 1) // plan.proposals_per_step_level
    shift = min(step_level, manifest.per_node_capital.bit_length() - 1)
    requested_transfer = max(1, manifest.per_node_capital >> shift)
    if len(edge_ids) < 2:
        return state, (node_id, None, None, requested_transfer, 0)

    pair_index = _unbiased_choice_index(
        plan.proposal_root_seed,
        "capacity.proposal.ordered-incidence-pair",
        proposal_index,
        len(edge_ids) * (len(edge_ids) - 1),
    )
    donor_index, recipient_rank = divmod(pair_index, len(edge_ids) - 1)
    recipient_index = (
        recipient_rank if recipient_rank < donor_index else recipient_rank + 1
    )
    donor_edge_id = edge_ids[donor_index]
    recipient_edge_id = edge_ids[recipient_index]
    donor_balance = state.edge(donor_edge_id).balance_of(node_id)
    actual_transfer = min(requested_transfer, donor_balance - 1)
    if actual_transfer == 0:
        return state, (
            node_id,
            donor_edge_id,
            recipient_edge_id,
            requested_transfer,
            0,
        )

    balances = {
        edge.hyperedge_id: dict(edge.balances) for edge in state.hyperedges
    }
    balances[donor_edge_id][node_id] -= actual_transfer
    balances[recipient_edge_id][node_id] += actual_transfer
    proposed = HypergraphState.from_balances(topology.nodes, balances)
    validate_capacity_state(topology, proposed, manifest)
    return proposed, (
        node_id,
        donor_edge_id,
        recipient_edge_id,
        requested_transfer,
        actual_transfer,
    )


def _positive_hamilton_apportionment(
    budget: int,
    scores: tuple[tuple[str, Fraction], ...],
) -> tuple[tuple[str, int], ...]:
    if not scores or budget < len(scores):
        raise OptimizationError("positive apportionment budget is infeasible")
    if any(score <= 0 for _, score in scores):
        raise OptimizationError("Hamilton apportionment scores must be positive")
    remaining = budget - len(scores)
    total_score = sum((score for _, score in scores), Fraction(0))
    floors: dict[str, int] = {}
    remainders: list[tuple[Fraction, str]] = []
    for edge_id, score in scores:
        quota = Fraction(remaining) * score / total_score
        floor_value = quota.numerator // quota.denominator
        floors[edge_id] = 1 + floor_value
        remainders.append((quota - floor_value, edge_id))
    leftover = budget - sum(floors.values())
    for _, edge_id in sorted(remainders, key=lambda item: (-item[0], item[1]))[:leftover]:
        floors[edge_id] += 1
    return tuple((edge_id, floors[edge_id]) for edge_id, _ in scores)


def _incidence_load_risk_score(
    node_id: str,
    members: tuple[str, ...],
    demand: DirectedDemandMatrix,
    manifest: CapacityOptimizationManifest,
) -> Fraction:
    others = tuple(member for member in members if member != node_id)
    load = sum(
        demand.amount(node_id, other) + demand.amount(other, node_id)
        for other in others
    )
    risk = sum(
        abs(demand.amount(node_id, other) - demand.amount(other, node_id))
        for other in others
    )
    return (
        Fraction(1)
        + manifest.load_weight * load
        + manifest.risk_weight * risk
    )


def _incident_edge_ids(
    topology: HypergraphTopology,
) -> dict[str, tuple[str, ...]]:
    incident: dict[str, list[str]] = {node_id: [] for node_id in topology.nodes}
    for edge in topology.hyperedges:
        for member in edge.members:
            incident[member].append(edge.hyperedge_id)
    return {
        node_id: tuple(sorted(edge_ids)) for node_id, edge_ids in incident.items()
    }


def _empirical_lower_quantile(values: tuple[int, ...], quantile: Fraction) -> int:
    if not values:
        raise OptimizationError("an empirical regime must contain at least one value")
    ordered = tuple(sorted(values))
    numerator = quantile.numerator * len(ordered)
    rank = (numerator + quantile.denominator - 1) // quantile.denominator
    return ordered[max(1, rank) - 1]


def _scientific_score_key(score: CapacityObjectiveScore) -> tuple[int, int, int, int]:
    return (
        score.robust_lower_quantile,
        score.regime_quantile_sum,
        score.total_restricted_tau,
        score.total_accepted_requests,
    )


def _score_is_better(
    candidate: CapacityObjectiveScore,
    incumbent: CapacityObjectiveScore,
) -> bool:
    candidate_key = _scientific_score_key(candidate)
    incumbent_key = _scientific_score_key(incumbent)
    if candidate_key != incumbent_key:
        return candidate_key > incumbent_key
    return candidate.state_fingerprint < incumbent.state_fingerprint


def _scenario_order_key(
    scenario: CapacityTrainingScenario,
) -> tuple[str, str]:
    return (scenario.regime_id, scenario.scenario_id)


def _unbiased_choice_index(
    root_seed: int,
    namespace: str,
    proposal_index: int,
    count: int,
) -> int:
    if type(count) is not int or not 1 <= count <= 2**64:
        raise OptimizationError("proposal choice count must be in [1, 2**64]")
    ticket = derive_seed(root_seed, namespace, proposal_index)
    rejection_limit = 2**64 - (2**64 % count)
    retry_index = 0
    while ticket >= rejection_limit:
        ticket = derive_seed(
            ticket,
            "capacity.choice.rejection-retry",
            retry_index,
        )
        retry_index += 1
    return ticket % count


def _topology_fingerprint(topology: HypergraphTopology) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.capacity-topology.v1\x00")
    _hash_count(digest, len(topology.nodes))
    for node_id in topology.nodes:
        _hash_field(digest, node_id)
    _hash_count(digest, len(topology.hyperedges))
    for edge in topology.hyperedges:
        _hash_field(digest, edge.hyperedge_id)
        _hash_count(digest, len(edge.members))
        for member in edge.members:
            _hash_field(digest, member)
    return digest.hexdigest()


def _state_fingerprint(state: HypergraphState) -> str:
    digest = hashlib.sha256()
    digest.update(b"secondaryexploration.capacity-state.v1\x00")
    _hash_count(digest, len(state.nodes))
    for node_id in state.nodes:
        _hash_field(digest, node_id)
    _hash_count(digest, len(state.hyperedges))
    for edge in state.hyperedges:
        _hash_field(digest, edge.hyperedge_id)
        _hash_count(digest, len(edge.balances))
        for node_id, amount in edge.balances:
            _hash_field(digest, node_id)
            _hash_count(digest, amount)
    return digest.hexdigest()


def _validate_identifier(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise OptimizationError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise OptimizationError(
            f"{field_name} must be nonempty and have no outer whitespace"
        )
    if "\x00" in value:
        raise OptimizationError(f"{field_name} must not contain NUL")


def _validate_unsigned_64(value: object, field_name: str) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise OptimizationError(f"{field_name} must be unsigned 64-bit")


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_digest(value: object, field_name: str) -> None:
    if not _is_digest(value):
        raise OptimizationError(f"{field_name} must be a lowercase SHA-256 digest")


def _hash_field(digest: "hashlib._Hash", value: str) -> None:
    encoded = value.encode("utf-8")
    _hash_count(digest, len(encoded))
    digest.update(encoded)


def _hash_count(digest: "hashlib._Hash", value: int) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_UNSIGNED_64:
        raise OptimizationError("hash count is outside unsigned-64 range")
    digest.update(value.to_bytes(8, "big", signed=False))


def _hash_integer(digest: "hashlib._Hash", value: int) -> None:
    if type(value) is not int:
        raise OptimizationError("hash integer must be exact")
    sign = b"\x01" if value < 0 else b"\x00"
    magnitude = abs(value)
    width = max(1, (magnitude.bit_length() + 7) // 8)
    _hash_count(digest, width)
    digest.update(sign)
    digest.update(magnitude.to_bytes(width, "big", signed=False))


__all__ = [
    "CAPACITY_INITIALIZER_VERSION",
    "CAPACITY_OBJECTIVE_VERSION",
    "CAPACITY_SEARCH_VERSION",
    "CapacityObjectiveScore",
    "CapacityOptimizationManifest",
    "CapacityOptimizationPlan",
    "CapacityOptimizationResult",
    "CapacityOptimizationStep",
    "CapacityProposalEvaluation",
    "CapacityScenarioOutcome",
    "CapacityTrainingScenario",
    "initialize_load_risk_state",
    "optimize_common_capacity",
    "score_capacity_state",
    "validate_capacity_state",
    "validate_common_capacity_result",
]
