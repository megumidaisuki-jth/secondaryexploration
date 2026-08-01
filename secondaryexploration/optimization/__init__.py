"""Demand-aware topology and common capacity optimization contracts."""

from .constructor import (
    CANDIDATE_GENERATOR_VERSION,
    EXHAUSTIVE_CANDIDATE_NODE_LIMIT,
    TOPOLOGY_SEARCH_VERSION,
    ConnectedCandidate,
    ConnectedCandidatePool,
    DemandAwareSearchPlan,
    DemandAwareSearchStep,
    DemandAwareTopologyResult,
    generate_connected_candidate_pool,
    train_demand_aware_topology,
    validate_connected_candidate_pool,
    validate_demand_aware_topology_result,
)

from .demand import (
    DEMAND_OBJECTIVE_VERSION,
    DemandAwareObjectiveScore,
    DemandAwareObjectiveWeights,
    DemandAwareTrainingManifest,
    DirectedDemandMatrix,
    OptimizationError,
    score_demand_aware_topology,
    validate_demand_aware_score,
    validate_demand_aware_topology,
)


__all__ = [
    "CANDIDATE_GENERATOR_VERSION",
    "DEMAND_OBJECTIVE_VERSION",
    "EXHAUSTIVE_CANDIDATE_NODE_LIMIT",
    "TOPOLOGY_SEARCH_VERSION",
    "ConnectedCandidate",
    "ConnectedCandidatePool",
    "DemandAwareObjectiveScore",
    "DemandAwareObjectiveWeights",
    "DemandAwareSearchPlan",
    "DemandAwareSearchStep",
    "DemandAwareTopologyResult",
    "DemandAwareTrainingManifest",
    "DirectedDemandMatrix",
    "OptimizationError",
    "generate_connected_candidate_pool",
    "score_demand_aware_topology",
    "train_demand_aware_topology",
    "validate_connected_candidate_pool",
    "validate_demand_aware_score",
    "validate_demand_aware_topology",
    "validate_demand_aware_topology_result",
]
