"""Immutable manifests and paired experiment execution."""

from .paired import (
    ExperimentError,
    PairedRunManifest,
    PairedRunResult,
    RouteChoiceRandom,
    TopologyVariant,
    VariantRunResult,
    route_choice_rng,
    route_choice_ticket,
    run_paired_experiment,
)
from .prior_paper import (
    PriorPaperDataset,
    PriorPaperError,
    PriorPaperInputManifest,
    PriorPaperTopologyDescriptor,
    componentwise_closed_neighborhood_nch,
    componentwise_fixed_hyperedge_size,
    describe_prior_paper_topology,
    load_prior_paper_dataset,
    prior_paper_binary_state,
    prior_paper_transformed_state,
    published_order_closed_neighborhood_nch,
)
from .prior_paper_replay import (
    PriorPaperReplayManifest,
    PriorPaperReplayOutcome,
    PriorPaperReplayResult,
    run_prior_paper_replay,
    state_balance_fingerprint,
    validate_prior_paper_replay,
)


__all__ = [
    "ExperimentError",
    "PairedRunManifest",
    "PairedRunResult",
    "RouteChoiceRandom",
    "TopologyVariant",
    "VariantRunResult",
    "PriorPaperDataset",
    "PriorPaperError",
    "PriorPaperInputManifest",
    "PriorPaperTopologyDescriptor",
    "PriorPaperReplayManifest",
    "PriorPaperReplayOutcome",
    "PriorPaperReplayResult",
    "componentwise_closed_neighborhood_nch",
    "componentwise_fixed_hyperedge_size",
    "describe_prior_paper_topology",
    "load_prior_paper_dataset",
    "prior_paper_binary_state",
    "prior_paper_transformed_state",
    "published_order_closed_neighborhood_nch",
    "run_prior_paper_replay",
    "state_balance_fingerprint",
    "validate_prior_paper_replay",
    "route_choice_rng",
    "route_choice_ticket",
    "run_paired_experiment",
]
