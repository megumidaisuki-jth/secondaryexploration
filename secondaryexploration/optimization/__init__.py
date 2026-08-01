"""Demand-aware topology and common capacity optimization contracts."""

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
    "DEMAND_OBJECTIVE_VERSION",
    "DemandAwareObjectiveScore",
    "DemandAwareObjectiveWeights",
    "DemandAwareTrainingManifest",
    "DirectedDemandMatrix",
    "OptimizationError",
    "score_demand_aware_topology",
    "validate_demand_aware_score",
    "validate_demand_aware_topology",
]
