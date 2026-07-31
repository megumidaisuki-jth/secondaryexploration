# Full Feasible Hypergraph Router Implementation Contract

**Date:** 2026-07-31

**Milestone:** Verified full feasible router (research design implementation
sequence item 3; Git policy milestone 4).

## Scope

This slice implements the paper-2 primary service router for one current
balance state and one payment request. It performs a complete global search of
the directed residual hypergraph. It does not use a precomputed candidate-path
set, mutate balances, advance a request clock, or define stopping events.

## Directed residual semantics

For request amount `a`, hyperedge `e` contributes a directed arc
`(u, e, v)` for every ordered pair of distinct members `u,v` exactly when
`x[e,u] >= a`. Traversing the arc costs one routing hop regardless of
hyperedge arity. The payee's pre-payment balance does not constrain receipt.

All hop costs are positive. Therefore every minimum-hop route is a simple
node path; repeating a hyperedge cannot be minimum-hop because the first
feasible entry could directly use that same hyperedge to reach the later exit.
The returned route is nevertheless checked by the existing `Route` contract.

## Ordered routing objective

Candidate routes are ordered lexicographically by three criteria:

1. minimize the number of traversed hyperedges;
2. among minimum-hop routes, maximize

   ```text
   min over route steps (
       (payer balance before payment - request amount)
       / total capital of that step's hyperedge
   )
   ```

3. among routes still tied, choose uniformly using an explicitly supplied
   `random.Random` instance.

Criterion 2 is the minimum post-payment normalized **paying** coordinate. It
uses exact `fractions.Fraction` arithmetic, not floating point. Normalization
by per-hyperedge total capital makes residual margins comparable across
heterogeneous channel sizes and reduces to the usual directional residual
fraction for a binary channel.

Random state is consumed only when at least two routes remain tied. No-path
and unique-optimum requests consume no random draw.

## Production algorithm

Create `secondaryexploration/routing/search.py` with:

```python
@dataclass(frozen=True, slots=True)
class RouteSearchResult:
    route: Route | None
    shortest_hops: int | None
    bottleneck: Fraction | None
    tied_route_count: int

def find_feasible_route(
    state: HypergraphState,
    request: PaymentRequest,
    rng: random.Random,
) -> RouteSearchResult: ...
```

The production search proceeds as follows:

1. deterministically construct all currently feasible directed residual arcs;
2. breadth-first search node distances from the request source;
3. retain the complete shortest-path directed acyclic multigraph, including
   parallel arcs produced by different hyperedges;
4. use layerwise dynamic programming to obtain the maximum bottleneck at the
   destination;
5. retain shortest-DAG arcs whose exact residual fraction is at least that
   bottleneck;
6. count all optimal routes with arbitrary-precision integers by reverse
   dynamic programming;
7. select one route uniformly by a single integer ticket weighted by suffix
   path counts.

This counts tied paths without materializing every route. Arc ordering is
canonical, so the same state, request, seed, and Python random stream produce
the same route.

`RouteSearchResult` enforces these public invariants:

- no path: all route metrics are `None` and tie count is zero;
- path found: route exists, hop count matches the route, bottleneck is in
  `[0,1]`, and tie count is positive.

## Independent reference oracle

Create `tests/exact/reference_full_search.py` as a deliberately separate small
implementation. It performs depth-first enumeration of all simple node/edge
routes, computes route scores directly, and returns the complete tuple of
optimal routes. It must not import or call production search helpers.

The oracle is only for tiny networks. The production search and oracle are
cross-checked on exhaustively varied small balance states and on hand-built
counterexamples.

## Test-first sequence

1. Write focused production-contract tests and observe the missing-module
   failure.
2. Lock directional feasibility, arity-independent hop cost, shortest-hop
   priority, exact normalized bottleneck priority, parallel-edge tie counts,
   deterministic unique selection, and explicit no-path behavior.
3. Lock random consumption: zero calls for no path or one optimum; exactly one
   bounded ticket draw for multiple tied paths.
4. Implement the breadth-first/dynamic-programming production router and make
   focused tests pass.
5. Write the independent DFS oracle without production helper reuse.
6. Cross-check route existence, shortest hops, exact bottleneck, optimal route
   count, and selected-route membership over small state families.
7. Add a regression in which a longer route has a better balance margin but
   must lose to the shorter route, and another in which normalized rather than
   raw residual balance changes the winner.
8. Run all tests on Python 3.10 and 3.12, compile source, check package
   discovery, run `git diff --check`, and scan implementation paths for
   placeholders.
9. Request an independent read-only audit of the production/oracle separation
   and semantic counterexamples before commit and push.

## Acceptance criteria

- Every returned route is structurally valid and feasible in the supplied
  pre-payment state.
- If any feasible route exists, the production search returns one; otherwise
  it returns the explicit no-path result.
- A longer path never beats a shorter path because of balance margin.
- Among equally short paths, the returned route has globally maximal exact
  normalized post-payment payer bottleneck.
- Every fully tied optimum has equal selection probability under the supplied
  ticket draw.
- Production metadata and selected routes agree with the independent oracle
  on the frozen small-network cross-check family.
- No topology-performance or stopping-time claim is made by this milestone.
