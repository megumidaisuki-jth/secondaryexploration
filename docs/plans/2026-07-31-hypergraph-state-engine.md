# Hypergraph State and Atomic Transition Implementation Contract

**Date:** 2026-07-31

**Milestone:** Verified balance/state engine (research design implementation
sequence item 2; Git policy milestone 3).

## Scope

This slice implements only the immutable payment-network state, simple atomic
routes, feasibility of a declared route, and an all-or-nothing balance update.
It does not search for routes, advance a request clock, define stopping times,
or produce topology-comparison results.

The transfer semantics are inherited from paper 1's frozen model contract:
for every alternating route step `(payer, hyperedge, payee)`, the payer's
hyperedge-local balance decreases by the payment amount and the payee's
balance in that same hyperedge increases by the same amount. A simple route
uses a hyperedge at most once, and every traversed hyperedge settles as one
atomic network transition.

## Locked representation choices

- Node and hyperedge identifiers are non-empty strings without outer
  whitespace or NUL.
- Balances and payment amounts use exact integer units. Balances are
  non-negative; request amounts are positive. Python booleans are rejected as
  integers.
- `HyperedgeState` stores a canonical sorted tuple of `(node, balance)` pairs,
  has at least two members, and has positive conserved total capital.
- `HypergraphState` stores the complete canonical node set separately from its
  hyperedges, so isolated nodes are representable. Every hyperedge member must
  belong to the node set.
- State objects are frozen and hashable. Successful transitions return a new
  state; an insufficient-balance rejection returns the exact original state
  object.
- `Route` is a non-empty tuple of continuous `TransferStep` objects. Nodes and
  hyperedges may not repeat, so the route is a simple alternating path.
- All structural checks and all payer-balance checks use the pre-payment
  state. Only after every step passes are all edge updates constructed.
- A coordinate is reported as newly depleted when an accepted payment reduces
  that payer coordinate exactly to zero. Pre-existing zero coordinates do not
  create a new depletion event.
- A missing edge, endpoint mismatch, or membership error is a malformed model
  object and raises `ModelError`. A structurally valid route with inadequate
  payer balance is a modeled rejection with reason
  `INSUFFICIENT_BALANCE`.
- Absence of any route is owned by the routing/simulation layers and is not
  represented as an atomic-transition rejection in this slice.

## Public interfaces

Create `secondaryexploration/model/entities.py`:

```python
class ModelError(ValueError): ...

@dataclass(frozen=True, order=True, slots=True)
class BalanceCoordinate:
    hyperedge_id: str
    node_id: str

@dataclass(frozen=True, slots=True)
class HyperedgeState:
    hyperedge_id: str
    balances: tuple[tuple[str, int], ...]

    @classmethod
    def from_balances(...): ...
    def balance_of(...): ...
    @property
    def members(...): ...
    @property
    def total_balance(...): ...

@dataclass(frozen=True, slots=True)
class HypergraphState:
    nodes: tuple[str, ...]
    hyperedges: tuple[HyperedgeState, ...]

    @classmethod
    def from_balances(...): ...
    def edge(...): ...
    @property
    def total_balance(...): ...

@dataclass(frozen=True, slots=True)
class PaymentRequest:
    source: str
    destination: str
    amount: int

@dataclass(frozen=True, slots=True)
class TransferStep:
    hyperedge_id: str
    payer: str
    payee: str

@dataclass(frozen=True, slots=True)
class Route:
    steps: tuple[TransferStep, ...]

    @property
    def source(...): ...
    @property
    def destination(...): ...
    @property
    def hop_count(...): ...
```

Create `secondaryexploration/model/transition.py`:

```python
class RejectionReason(str, Enum):
    INSUFFICIENT_BALANCE = "insufficient_balance"

@dataclass(frozen=True, slots=True)
class PaymentTransition:
    state: HypergraphState
    accepted: bool
    rejection_reason: RejectionReason | None
    depleted_coordinates: tuple[BalanceCoordinate, ...]

def is_route_feasible(
    state: HypergraphState,
    request: PaymentRequest,
    route: Route,
) -> bool: ...

def apply_atomic_payment(
    state: HypergraphState,
    request: PaymentRequest,
    route: Route,
) -> PaymentTransition: ...
```

The package-level `secondaryexploration.model` namespace exports the tested
public symbols. The project root namespace remains limited to cross-cutting
configuration and randomness APIs.

## Test-first sequence

1. Write entity tests for canonicalization, validation, hashability, isolated
   nodes, request validation, route continuity, and simple-path constraints;
   observe an import failure.
2. Implement entities and make only the entity tests pass.
3. Write transition tests for per-edge conservation, exact deltas, newly
   depleted coordinates, full preflight feasibility, rejection identity, and
   malformed-route errors; observe an import failure.
4. Implement route feasibility and atomic transitions; make the focused tests
   pass.
5. Add a paper-1 bridge fixture for the route
   `(0,e1,2,e2,3)` and assert that a unit payment gives one `-1/+1` pair in
   each edge, matching the inherited model definition.
6. Run all tests on Python 3.10 and 3.12, compile all source files, run
   `git diff --check`, and scan implementation paths for placeholders.
7. Commit and push only after all checks pass. This milestone establishes
   process correctness for the state engine but makes no router or service
   reliability claim.

## Acceptance criteria

- Every accepted transition conserves each hyperedge's capital independently.
- No balance can become negative.
- A valid route is updated completely or not at all.
- A rejected payment leaves the original immutable state unchanged.
- Exact boundary hits are recorded only after accepted payments.
- Canonical states are hashable for later finite-state enumeration.
- Paper 1's unit-route increment is reproduced by an explicit bridge test.
