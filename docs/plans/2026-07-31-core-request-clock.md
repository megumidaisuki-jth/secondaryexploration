# Core Request Clock and Service-Event Implementation Contract

**Date:** 2026-07-31

**Milestone:** Verified core request-clock engine (research design
implementation sequence item 4, first bounded slice).

## Scope

This slice composes the verified full feasible router with the verified atomic
state engine over a finite, ordered request trace. It records the first
depletion, first no-path request, first final rejection, continuation after
failure, recovery, failure streaks, and cumulative accepted payments.

It does not yet implement topology generation, traffic generation, fees,
reserves, retry attempts, rebalancing, statistical estimators, or formal
experiment manifests.

## Clock and event conventions

- Request indices are one-based: the first attempted request has index `1`.
- Every attempted request advances the clock, whether accepted or rejected.
- The finite trace length is the observation horizon `T`.
- If an event is not observed by `T`, it is right-censored at `T`; an explicit
  `observed` flag distinguishes an event at `T` from censoring at `T`.
- To preserve the paper-1 stopping-time boundary convention, `tau_dep=0` when
  any initial directional balance is already zero. Otherwise `tau_dep` is the
  first request index at which an accepted atomic payment newly reduces at
  least one payer coordinate to exactly zero.
- `tau_nopath` is the first request for which complete residual search returns
  no route.
- In this core layer, no non-liquidity failures or retries exist, so
  `tau_rej=tau_nopath`. They remain distinct result fields so later protocol
  sensitivities can separate them without renaming the estimands.
- An accepted exact-boundary payment can set `tau_dep` but never sets
  `tau_nopath` or `tau_rej` on the same request.
- Simulation always continues to `T` after the first failure.

## Recovery and service summaries

- Recovery after first rejection means the first later request of any
  source-destination pair that is accepted. It is a network-service recovery,
  not necessarily recovery of the same failed pair.
- If no later request succeeds, recovery is right-censored at `T` and its
  elapsed time is `T - tau_rej`.
- Consecutive rejected requests form a `FailureEpisode`. An episode ending in
  an accepted request is observed as ended; an episode still active at `T` is
  marked censored.
- Cumulative success at request `i` is the number of accepted requests among
  indices `1..i`. The final success rate is stored or exposed as an exact
  `Fraction`, not a rounded float.

## Public interfaces

Create `secondaryexploration/simulation/core.py`:

```python
@dataclass(frozen=True, slots=True)
class EventObservation:
    observed: bool
    request_index: int

@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    origin_request: int
    observed: bool
    request_index: int

    @property
    def elapsed_requests(self) -> int: ...

@dataclass(frozen=True, slots=True)
class FailureEpisode:
    start_request: int
    length: int
    ended_by_success: bool

@dataclass(frozen=True, slots=True)
class CoreRequestOutcome:
    request_index: int
    request: PaymentRequest
    search_result: RouteSearchResult
    depleted_coordinates: tuple[BalanceCoordinate, ...]

    @property
    def accepted(self) -> bool: ...
    @property
    def no_path(self) -> bool: ...
    @property
    def final_rejected(self) -> bool: ...

@dataclass(frozen=True, slots=True)
class CoreSimulationResult:
    initial_state: HypergraphState
    final_state: HypergraphState
    outcomes: tuple[CoreRequestOutcome, ...]
    tau_dep: EventObservation
    tau_nopath: EventObservation
    tau_rej: EventObservation

    @property
    def horizon(self) -> int: ...
    @property
    def cumulative_successes(self) -> tuple[int, ...]: ...
    @property
    def success_rate(self) -> Fraction | None: ...
    @property
    def failure_episodes(self) -> tuple[FailureEpisode, ...]: ...
    @property
    def recovery_after_first_rejection(self) -> RecoveryObservation | None: ...

def run_core_trace(
    initial_state: HypergraphState,
    requests: Iterable[PaymentRequest],
    rng: random.Random,
) -> CoreSimulationResult: ...
```

`CoreSimulationResult` recomputes the complete feasible search and replays every
recorded selected route during validation. It rejects false no-path records,
nonoptimal route metadata, routes that do not attain the global bottleneck, and
inconsistent final states, depletion records, event times, or request indices.
Alternative routes within the same exact optimal tie set remain valid. This
makes serialized or manually constructed result objects fail closed rather
than relying only on the runner.

## Test-first sequence

1. Lock `EventObservation`, recovery, episode, and outcome invariants; observe
   the missing simulation module.
2. Lock an empty trace and initial-boundary `tau_dep=0`.
3. Lock an exact accepted boundary hit at request 1.
4. Construct a three-request trace with `tau_nopath=1 < tau_dep=3`: an amount
   too large for the forward direction fails while all balances remain
   positive, a reverse payment restores margin, and a later forward payment
   succeeds and depletes.
5. Construct the reverse ordering `tau_dep < tau_nopath` with an intervening
   reverse recovery, proving there is no fixed event ordering.
6. Lock two initial failures, one accepted recovery, and a final censored
   failure episode; assert cumulative successes, recovery delay, exact success
   rate, and continuation to the horizon.
7. Lock deterministic replay on a topology with tied routes using a seed from
   the versioned RNG layer.
8. Add a separately written tiny reference trace runner or exhaustive sequence
   check that does not call `run_core_trace`, and compare final state and first
   events over short request sequences.
9. Run all tests on Python 3.10 and 3.12, compile source, check package
   discovery, scan placeholders, and request an independent read-only audit.
10. Commit and push only after the audit and full suite pass.

## Acceptance criteria

- Every attempted request receives exactly one monotonically increasing clock
  index.
- No-path requests leave balances unchanged and do not stop the trace.
- Returned routes settle atomically and every recorded depletion is exact.
- `tau_dep`, `tau_nopath`, and `tau_rej` have exact first-event indexing and
  explicit censoring.
- The core equality `tau_nopath=tau_rej` is enforced without conflating their
  later protocol meanings.
- Recovery and consecutive-failure summaries agree with the full outcome
  sequence.
- Same initial state, request trace, and seed reproduce the complete result.
- No service-reliability or topology-ranking claim is made by this software
  milestone alone.
