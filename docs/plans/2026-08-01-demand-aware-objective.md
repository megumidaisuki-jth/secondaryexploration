# Demand-Aware HPN: Training Objective and Feasibility Contract

**Date:** 2026-08-01
**Status:** Implemented and independently audited

## Purpose and claim boundary

This slice turns the four-term demand-aware design into an exact, replayable
training objective. It does not claim improved reliability. Reliability is
measured only after a topology has been trained once and evaluated on untouched
in-distribution and shifted test traces.

The training demand matrix is amount weighted:

`D[u,v] = sum(request.amount for training requests u -> v)`.

Every ordered pair of distinct declared nodes is represented, including zero
cells. A structurally framed SHA-256 fingerprint binds the node order and all
ordered-pair values. Requests with undeclared endpoints fail closed.

## Feasible topology set

For one connected parent graph, a candidate topology is feasible only if:

1. it preserves the exact parent node set;
2. its total incidence count equals the registered budget;
3. every hyperedge has arity at most the registered maximum;
4. every hyperedge's members induce a connected parent subgraph;
5. every parent edge is co-contained in at least one hyperedge;
6. no two hyperedges have identical member sets; and
7. the resulting incidence hypergraph is connected.

These rules prevent the optimizer from inventing disconnected multi-party
channels, discarding inconvenient parent relationships, hiding duplicate
channels under different identifiers, or changing the comparison budget.

## Exact four-term objective

For unordered pair `{u,v}`, let `m[u,v]` be the number of hyperedges containing
both nodes. A pair is captured when `m[u,v] > 0`.

1. **Bidirectional capture reward**
   `R = sum_captured min(D[u,v], D[v,u])`.
2. **Directional-imbalance penalty**
   `I = sum_captured abs(D[u,v] - D[v,u])`.
3. **Participation penalty**
   `P = sum_u choose(deg_H(u), 2)`.
4. **Coordination/overlap penalty**
   `O = sum_e choose(|e|, 2) + sum_{u<v} choose(m[u,v], 2)`.

The first part of `O` counts pairwise coordination exposure inside channels;
the second counts redundant pair exposure across overlapping channels. `P`
separately captures the operational burden of one node participating in many
channels.

All four terms are normalized with exact `Fraction` arithmetic before applying
registered non-negative rational coefficients. Demand terms use the total
available bidirectional volume and total directional imbalance as denominators.
Participation and coordination use declared budget/arity upper bounds, so the
same coefficient scale is meaningful across graph sizes. A zero denominator
maps to exact zero rather than an arbitrary epsilon.

The maximized score is:

`w_R R_norm - w_I I_norm - w_P P_norm - w_O O_norm`.

Every coefficient, parent fingerprint, demand fingerprint, incidence budget,
maximum arity, and objective version is frozen in a training manifest. No
coefficient may be selected using held-out service outcomes.

## Next bounded slices

1. deterministic connected-subset candidate generation and exact-budget
   construction;
2. small-graph exhaustive objective oracle;
3. common load/risk initialization and projected stochastic capacity optimizer;
4. train-once evaluation under same-distribution, hotspot relocation,
   direction reversal, and increased cross-community demand.
