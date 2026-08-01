"""Reproducible fixed-edge synthetic parent-graph ensembles."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from math import comb
import random

from secondaryexploration.randomness import SeedError, derive_seed

from .parent import ParentGraph
from .structure import TopologyError


_MAX_UNSIGNED_64 = 2**64 - 1
_MAX_RESAMPLING_ATTEMPTS = 10_000


class TopologyGenerationError(TopologyError):
    """Raised when a valid random topology is not drawn within its budget."""


class ParentGraphModel(str, Enum):
    """Frozen synthetic parent-graph family labels."""

    ER_GNM = "er_gnm"
    BARABASI_ALBERT = "barabasi_albert"
    SBM_FIXED_COUNT = "sbm_fixed_count"


_ATTEMPT_NAMESPACES = {
    ParentGraphModel.ER_GNM: "parent.er_gnm.attempt",
    ParentGraphModel.BARABASI_ALBERT: "parent.barabasi_albert.attempt",
    ParentGraphModel.SBM_FIXED_COUNT: "parent.sbm_fixed_count.attempt",
}


@dataclass(frozen=True, slots=True)
class ParentGraphDraw:
    """One accepted connected graph plus replayable resampling metadata."""

    model: ParentGraphModel
    graph: ParentGraph
    root_seed: int
    accepted_attempt: int
    blocks: tuple[tuple[str, ...], ...] = ()
    attachment_count: int | None = None
    within_edge_count: int | None = None

    def __post_init__(self) -> None:
        if type(self.model) is not ParentGraphModel:
            raise TopologyError("model must be a ParentGraphModel")
        if not isinstance(self.graph, ParentGraph):
            raise TopologyError("graph must be a ParentGraph")
        if not self.graph.is_connected:
            raise TopologyError("an accepted parent graph draw must be connected")
        _validate_root_seed(self.root_seed)
        if (
            type(self.accepted_attempt) is not int
            or not 0 <= self.accepted_attempt < _MAX_RESAMPLING_ATTEMPTS
        ):
            raise TopologyError(
                "accepted_attempt must be an integer in [0, 10000)"
            )
        expected_nodes = _canonical_nodes(len(self.graph.nodes))
        if len(expected_nodes) < 2 or self.graph.nodes != expected_nodes:
            raise TopologyError(
                "random parent graphs must use at least two canonical node identifiers"
            )

        if type(self.blocks) is not tuple or any(
            type(block) is not tuple for block in self.blocks
        ):
            raise TopologyError("blocks must be a canonical tuple of tuples")
        if self.model is ParentGraphModel.SBM_FIXED_COUNT:
            _validate_block_partition(self.blocks, self.graph.nodes)
        elif self.blocks:
            raise TopologyError("only fixed-count SBM draws may carry blocks")

        if self.model is ParentGraphModel.ER_GNM:
            if self.attachment_count is not None or self.within_edge_count is not None:
                raise TopologyError("ER draws cannot carry BA or SBM parameters")
            reproduced = _gnm_graph_for_seed(
                self.graph.nodes,
                self.graph.edge_count,
                self.draw_seed,
            )
        elif self.model is ParentGraphModel.BARABASI_ALBERT:
            if self.accepted_attempt != 0:
                raise TopologyError("BA draws must use accepted_attempt zero")
            _validate_attachment_count(
                self.attachment_count,
                len(self.graph.nodes),
            )
            if self.within_edge_count is not None:
                raise TopologyError("BA draws cannot carry an SBM within-edge count")
            reproduced = _ba_graph_for_seed(
                self.graph.nodes,
                self.attachment_count,
                self.draw_seed,
            )
        else:
            if self.attachment_count is not None:
                raise TopologyError("SBM draws cannot carry a BA attachment count")
            _validate_sbm_budget(
                self.blocks,
                self.graph.edge_count,
                self.within_edge_count,
            )
            reproduced = _sbm_graph_for_seed(
                self.graph.nodes,
                self.blocks,
                self.graph.edge_count,
                self.within_edge_count,
                self.draw_seed,
            )
        if reproduced != self.graph:
            raise TopologyError(
                "graph does not match its declared model parameters and draw seed"
            )
        if self.model is not ParentGraphModel.BARABASI_ALBERT:
            for prior_attempt in range(self.accepted_attempt):
                prior_seed = derive_seed(
                    self.root_seed,
                    _ATTEMPT_NAMESPACES[self.model],
                    prior_attempt,
                )
                if self.model is ParentGraphModel.ER_GNM:
                    prior_graph = _gnm_graph_for_seed(
                        self.graph.nodes,
                        self.graph.edge_count,
                        prior_seed,
                    )
                else:
                    prior_graph = _sbm_graph_for_seed(
                        self.graph.nodes,
                        self.blocks,
                        self.graph.edge_count,
                        self.within_edge_count,
                        prior_seed,
                    )
                if prior_graph.is_connected:
                    raise TopologyError(
                        "accepted_attempt must be the first connected draw"
                    )

    @property
    def draw_seed(self) -> int:
        """Return the exact seed used for the accepted attempt."""

        return derive_seed(
            self.root_seed,
            _ATTEMPT_NAMESPACES[self.model],
            self.accepted_attempt,
        )

    @property
    def rejected_attempt_count(self) -> int:
        return self.accepted_attempt


@dataclass(frozen=True, slots=True)
class MatchedParentEnsemble:
    """ER, BA, and SBM draws with identical nodes and edge resources."""

    base_seed: int
    replicate_index: int
    er: ParentGraphDraw
    ba: ParentGraphDraw
    sbm: ParentGraphDraw

    def __post_init__(self) -> None:
        if not all(
            isinstance(draw, ParentGraphDraw) for draw in (self.er, self.ba, self.sbm)
        ):
            raise TopologyError("matched draws must be ParentGraphDraw objects")
        _validate_root_seed(self.base_seed)
        if (
            type(self.replicate_index) is not int
            or not 0 <= self.replicate_index <= _MAX_UNSIGNED_64
        ):
            raise TopologyError(
                "replicate_index must be an integer in [0, 2**64 - 1]"
            )
        expected_models = (
            ParentGraphModel.ER_GNM,
            ParentGraphModel.BARABASI_ALBERT,
            ParentGraphModel.SBM_FIXED_COUNT,
        )
        if tuple(draw.model for draw in self.draws) != expected_models:
            raise TopologyError("matched draws must be ordered as ER, BA, and SBM")
        expected_roots = (
            derive_seed(self.base_seed, "parent.er", self.replicate_index),
            derive_seed(self.base_seed, "parent.ba", self.replicate_index),
            derive_seed(self.base_seed, "parent.sbm", self.replicate_index),
        )
        if tuple(draw.root_seed for draw in self.draws) != expected_roots:
            raise TopologyError(
                "matched draw roots must use the declared base seed and namespaces"
            )

        graphs = tuple(draw.graph for draw in self.draws)
        if len({graph.nodes for graph in graphs}) != 1:
            raise TopologyError("matched parent graphs must use the same node mapping")
        if len({graph.edge_count for graph in graphs}) != 1:
            raise TopologyError("matched parent graphs must have the same edge count")
        if len({graph.mean_degree for graph in graphs}) != 1:
            raise TopologyError("matched parent graphs must have the same mean degree")

    @property
    def draws(self) -> tuple[ParentGraphDraw, ParentGraphDraw, ParentGraphDraw]:
        return (self.er, self.ba, self.sbm)

    @property
    def blocks(self) -> tuple[tuple[str, ...], ...]:
        return self.sbm.blocks

    @property
    def target_edge_count(self) -> int:
        return self.ba.graph.edge_count


def connected_gnm_parent_graph(
    node_count: int,
    edge_count: int,
    *,
    root_seed: int,
    max_attempts: int = 1_000,
) -> ParentGraphDraw:
    """Draw a connected graph from the exact-edge ER `G(n,m)` ensemble."""

    _validate_connected_graph_size(node_count, edge_count)
    _validate_root_seed(root_seed)
    _validate_max_attempts(max_attempts)
    nodes = _canonical_nodes(node_count)

    for attempt in range(max_attempts):
        draw_seed = derive_seed(
            root_seed,
            _ATTEMPT_NAMESPACES[ParentGraphModel.ER_GNM],
            attempt,
        )
        graph = _gnm_graph_for_seed(nodes, edge_count, draw_seed)
        if graph.is_connected:
            return ParentGraphDraw(
                model=ParentGraphModel.ER_GNM,
                graph=graph,
                root_seed=root_seed,
                accepted_attempt=attempt,
            )

    raise TopologyGenerationError(
        f"no connected ER G(n,m) graph found in {max_attempts} attempts"
    )


def barabasi_albert_parent_graph(
    node_count: int,
    attachment_count: int,
    *,
    root_seed: int,
) -> ParentGraphDraw:
    """Generate the frozen star-initialized preferential-attachment graph."""

    _validate_node_count(node_count)
    _validate_attachment_count(attachment_count, node_count)
    _validate_root_seed(root_seed)

    draw_seed = derive_seed(
        root_seed,
        _ATTEMPT_NAMESPACES[ParentGraphModel.BARABASI_ALBERT],
        0,
    )
    nodes = _canonical_nodes(node_count)
    graph = _ba_graph_for_seed(nodes, attachment_count, draw_seed)
    expected_edges = attachment_count * (node_count - attachment_count)
    if graph.edge_count != expected_edges or not graph.is_connected:
        raise AssertionError("internal BA construction violated its exact contract")
    return ParentGraphDraw(
        model=ParentGraphModel.BARABASI_ALBERT,
        graph=graph,
        root_seed=root_seed,
        accepted_attempt=0,
        attachment_count=attachment_count,
    )


def connected_sbm_parent_graph(
    block_sizes: Iterable[int],
    edge_count: int,
    within_edge_count: int,
    *,
    root_seed: int,
    max_attempts: int = 1_000,
) -> ParentGraphDraw:
    """Draw a connected fixed within/between-count stochastic block graph."""

    canonical_sizes = _validate_block_sizes(block_sizes)
    node_count = sum(canonical_sizes)
    _validate_connected_graph_size(node_count, edge_count)
    _validate_root_seed(root_seed)
    _validate_max_attempts(max_attempts)

    nodes = _canonical_nodes(node_count)
    blocks = _blocks_from_sizes(nodes, canonical_sizes)
    _validate_sbm_budget(blocks, edge_count, within_edge_count)

    for attempt in range(max_attempts):
        draw_seed = derive_seed(
            root_seed,
            _ATTEMPT_NAMESPACES[ParentGraphModel.SBM_FIXED_COUNT],
            attempt,
        )
        graph = _sbm_graph_for_seed(
            nodes,
            blocks,
            edge_count,
            within_edge_count,
            draw_seed,
        )
        if graph.is_connected:
            return ParentGraphDraw(
                model=ParentGraphModel.SBM_FIXED_COUNT,
                graph=graph,
                root_seed=root_seed,
                accepted_attempt=attempt,
                blocks=blocks,
                within_edge_count=within_edge_count,
            )

    raise TopologyGenerationError(
        f"no connected fixed-count SBM graph found in {max_attempts} attempts"
    )


def matched_synthetic_parent_graphs(
    *,
    node_count: int,
    attachment_count: int,
    block_count: int,
    sbm_within_edge_count: int,
    base_seed: int,
    replicate_index: int,
    max_attempts: int = 1_000,
) -> MatchedParentEnsemble:
    """Generate an exactly node/edge/mean-degree matched ER/BA/SBM block."""

    _validate_node_count(node_count)
    if type(block_count) is not int or not 2 <= block_count <= node_count:
        raise TopologyError("block_count must be an integer in [2, node_count]")
    _validate_root_seed(base_seed)
    if (
        type(replicate_index) is not int
        or not 0 <= replicate_index <= _MAX_UNSIGNED_64
    ):
        raise TopologyError(
            "replicate_index must be an integer in [0, 2**64 - 1]"
        )
    _validate_max_attempts(max_attempts)

    ba_root = derive_seed(base_seed, "parent.ba", replicate_index)
    er_root = derive_seed(base_seed, "parent.er", replicate_index)
    sbm_root = derive_seed(base_seed, "parent.sbm", replicate_index)
    ba = barabasi_albert_parent_graph(
        node_count,
        attachment_count,
        root_seed=ba_root,
    )
    edge_count = ba.graph.edge_count
    block_sizes = _balanced_block_sizes(node_count, block_count)
    er = connected_gnm_parent_graph(
        node_count,
        edge_count,
        root_seed=er_root,
        max_attempts=max_attempts,
    )
    sbm = connected_sbm_parent_graph(
        block_sizes,
        edge_count,
        sbm_within_edge_count,
        root_seed=sbm_root,
        max_attempts=max_attempts,
    )
    return MatchedParentEnsemble(
        base_seed=base_seed,
        replicate_index=replicate_index,
        er=er,
        ba=ba,
        sbm=sbm,
    )


def _canonical_nodes(node_count: int) -> tuple[str, ...]:
    return tuple(f"v{index:08d}" for index in range(node_count))


def _balanced_block_sizes(node_count: int, block_count: int) -> tuple[int, ...]:
    base_size, remainder = divmod(node_count, block_count)
    return tuple(
        base_size + (index < remainder) for index in range(block_count)
    )


def _blocks_from_sizes(
    nodes: tuple[str, ...],
    block_sizes: tuple[int, ...],
) -> tuple[tuple[str, ...], ...]:
    blocks: list[tuple[str, ...]] = []
    start = 0
    for size in block_sizes:
        stop = start + size
        blocks.append(nodes[start:stop])
        start = stop
    return tuple(blocks)


def _sample_without_replacement(
    population: tuple[tuple[str, str], ...],
    sample_size: int,
    rng: random.Random,
) -> tuple[tuple[str, str], ...]:
    if not 0 <= sample_size <= len(population):
        raise TopologyError("sample_size exceeds the candidate-pair population")
    working = list(population)
    for left_index in range(sample_size):
        right_index = left_index + _randbelow(rng, len(working) - left_index)
        working[left_index], working[right_index] = (
            working[right_index],
            working[left_index],
        )
    return tuple(sorted(working[:sample_size]))


def _gnm_graph_for_seed(
    nodes: tuple[str, ...],
    edge_count: int,
    draw_seed: int,
) -> ParentGraph:
    candidates = tuple(combinations(nodes, 2))
    sampled_edges = _sample_without_replacement(
        candidates,
        edge_count,
        random.Random(draw_seed),
    )
    return ParentGraph.from_edges(nodes, sampled_edges)


def _ba_graph_for_seed(
    nodes: tuple[str, ...],
    attachment_count: int,
    draw_seed: int,
) -> ParentGraph:
    rng = random.Random(draw_seed)
    center = nodes[0]
    initial_leaves = nodes[1 : attachment_count + 1]
    edges: list[tuple[str, str]] = [(center, leaf) for leaf in initial_leaves]

    repeated_nodes: list[str] = [center] * attachment_count
    repeated_nodes.extend(initial_leaves)
    for source in nodes[attachment_count + 1 :]:
        targets: set[str] = set()
        while len(targets) < attachment_count:
            targets.add(repeated_nodes[_randbelow(rng, len(repeated_nodes))])
        ordered_targets = tuple(sorted(targets))
        edges.extend((target, source) for target in ordered_targets)
        repeated_nodes.extend(ordered_targets)
        repeated_nodes.extend([source] * attachment_count)
    return ParentGraph.from_edges(nodes, edges)


def _sbm_graph_for_seed(
    nodes: tuple[str, ...],
    blocks: tuple[tuple[str, ...], ...],
    edge_count: int,
    within_edge_count: int,
    draw_seed: int,
) -> ParentGraph:
    block_index = {
        node: index for index, block in enumerate(blocks) for node in block
    }
    all_pairs = tuple(combinations(nodes, 2))
    within_candidates = tuple(
        pair for pair in all_pairs if block_index[pair[0]] == block_index[pair[1]]
    )
    between_candidates = tuple(
        pair for pair in all_pairs if block_index[pair[0]] != block_index[pair[1]]
    )
    rng = random.Random(draw_seed)
    sampled_within = _sample_without_replacement(
        within_candidates,
        within_edge_count,
        rng,
    )
    sampled_between = _sample_without_replacement(
        between_candidates,
        edge_count - within_edge_count,
        rng,
    )
    return ParentGraph.from_edges(nodes, sampled_within + sampled_between)


def _randbelow(rng: random.Random, stop: int) -> int:
    if type(stop) is not int or stop <= 0:
        raise TopologyError("random stop must be a positive integer")
    bit_count = stop.bit_length()
    while True:
        candidate = rng.getrandbits(bit_count)
        if candidate < stop:
            return candidate


def _validate_node_count(node_count: object) -> None:
    if type(node_count) is not int or node_count < 2:
        raise TopologyError("node_count must be an integer at least two")


def _validate_attachment_count(
    attachment_count: object,
    node_count: int,
) -> None:
    if (
        type(attachment_count) is not int
        or not 1 <= attachment_count < node_count
    ):
        raise TopologyError(
            "attachment_count must be an integer in [1, node_count)"
        )


def _validate_connected_graph_size(node_count: object, edge_count: object) -> None:
    _validate_node_count(node_count)
    if (
        type(edge_count) is not int
        or not node_count - 1 <= edge_count <= comb(node_count, 2)
    ):
        raise TopologyError(
            "edge_count must be an integer in [node_count - 1, choose(node_count, 2)]"
        )


def _validate_root_seed(root_seed: object) -> None:
    if type(root_seed) is not int or not 0 <= root_seed <= _MAX_UNSIGNED_64:
        raise TopologyError("root_seed must be an integer in [0, 2**64 - 1]")
    try:
        derive_seed(root_seed, "parent.seed.validation", 0)
    except SeedError as exc:  # defensive synchronization with the seed module
        raise TopologyError(str(exc)) from exc


def _validate_max_attempts(max_attempts: object) -> None:
    if (
        type(max_attempts) is not int
        or not 1 <= max_attempts <= _MAX_RESAMPLING_ATTEMPTS
    ):
        raise TopologyError("max_attempts must be an integer in [1, 10000]")


def _validate_block_sizes(block_sizes: Iterable[int]) -> tuple[int, ...]:
    if isinstance(block_sizes, (str, bytes)):
        raise TopologyError("block_sizes must be an iterable of positive integers")
    try:
        sizes = tuple(block_sizes)
    except TypeError as exc:
        raise TopologyError(
            "block_sizes must be an iterable of positive integers"
        ) from exc
    if len(sizes) < 2:
        raise TopologyError("fixed-count SBM requires at least two blocks")
    if any(type(size) is not int or size < 1 for size in sizes):
        raise TopologyError("every block size must be a positive integer")
    if sum(sizes) < 2:
        raise TopologyError("block sizes must contain at least two nodes")
    return sizes


def _validate_block_partition(
    blocks: tuple[tuple[str, ...], ...],
    nodes: tuple[str, ...],
) -> None:
    if len(blocks) < 2 or any(not block for block in blocks):
        raise TopologyError("SBM blocks must contain at least two non-empty blocks")
    flattened = tuple(node for block in blocks for node in block)
    if flattened != nodes:
        raise TopologyError(
            "SBM blocks must be the canonical contiguous partition of graph nodes"
        )
    if tuple(sorted(blocks, key=lambda block: block[0])) != blocks:
        raise TopologyError("SBM blocks must be in canonical order")


def _validate_sbm_budget(
    blocks: tuple[tuple[str, ...], ...],
    edge_count: int,
    within_edge_count: object,
) -> None:
    if type(within_edge_count) is not int or not 0 <= within_edge_count <= edge_count:
        raise TopologyError("within_edge_count must be an integer in [0, edge_count]")
    within_capacity = sum(comb(len(block), 2) for block in blocks)
    total_capacity = comb(sum(len(block) for block in blocks), 2)
    between_capacity = total_capacity - within_capacity
    between_edge_count = edge_count - within_edge_count
    if within_edge_count > within_capacity:
        raise TopologyError("within_edge_count exceeds within-block pair capacity")
    if between_edge_count > between_capacity:
        raise TopologyError("between-edge count exceeds between-block pair capacity")
    if len(blocks) > 1 and between_edge_count < len(blocks) - 1:
        raise TopologyError(
            "a connected SBM needs at least block_count - 1 between-block edges"
        )


__all__ = [
    "MatchedParentEnsemble",
    "ParentGraphDraw",
    "ParentGraphModel",
    "TopologyGenerationError",
    "barabasi_albert_parent_graph",
    "connected_gnm_parent_graph",
    "connected_sbm_parent_graph",
    "matched_synthetic_parent_graphs",
]
