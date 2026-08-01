"""Replay-attested iid payment-request traces."""

from __future__ import annotations

from dataclasses import dataclass
import random

from secondaryexploration.model import PaymentRequest
from secondaryexploration.randomness import derive_seed

from .kernels import AmountDistribution, DemandKernel, TrafficError


_MAX_UNSIGNED_64 = 2**64 - 1


@dataclass(frozen=True, slots=True)
class RequestTrace:
    """One exact iid request tuple and the complete information to replay it."""

    kernel: DemandKernel
    amount_distribution: AmountDistribution
    length: int
    root_seed: int
    requests: tuple[PaymentRequest, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kernel, DemandKernel):
            raise TrafficError("kernel must be a DemandKernel")
        if not isinstance(self.amount_distribution, AmountDistribution):
            raise TrafficError("amount_distribution must be an AmountDistribution")
        _validate_length(self.length)
        _validate_root_seed(self.root_seed)
        if type(self.requests) is not tuple or any(
            not isinstance(request, PaymentRequest) for request in self.requests
        ):
            raise TrafficError("requests must be a PaymentRequest tuple")
        if len(self.requests) != self.length:
            raise TrafficError("request tuple length does not match declared length")
        expected = _generate_requests(
            self.kernel,
            self.amount_distribution,
            self.length,
            self.root_seed,
        )
        if self.requests != expected:
            raise TrafficError(
                "requests do not match the declared kernel, amount table, and seed"
            )

    @property
    def pair_seed(self) -> int:
        return derive_seed(self.root_seed, "traffic.pairs", 0)

    @property
    def amount_seed(self) -> int:
        return derive_seed(self.root_seed, "traffic.amounts", 0)


def generate_request_trace(
    kernel: DemandKernel,
    amount_distribution: AmountDistribution,
    length: int,
    *,
    root_seed: int,
) -> RequestTrace:
    """Generate a deterministic iid request trace from separated streams."""

    if not isinstance(kernel, DemandKernel):
        raise TrafficError("kernel must be a DemandKernel")
    if not isinstance(amount_distribution, AmountDistribution):
        raise TrafficError("amount_distribution must be an AmountDistribution")
    _validate_length(length)
    _validate_root_seed(root_seed)
    requests = _generate_requests(kernel, amount_distribution, length, root_seed)
    return RequestTrace(
        kernel=kernel,
        amount_distribution=amount_distribution,
        length=length,
        root_seed=root_seed,
        requests=requests,
    )


def _generate_requests(
    kernel: DemandKernel,
    amount_distribution: AmountDistribution,
    length: int,
    root_seed: int,
) -> tuple[PaymentRequest, ...]:
    pair_rng = random.Random(derive_seed(root_seed, "traffic.pairs", 0))
    amount_rng = random.Random(derive_seed(root_seed, "traffic.amounts", 0))
    requests: list[PaymentRequest] = []
    for _ in range(length):
        source, destination = kernel.pair_for_ticket(
            _randbelow(pair_rng, kernel.total_weight)
        )
        amount = amount_distribution.amount_for_ticket(
            _randbelow(amount_rng, amount_distribution.total_weight)
        )
        requests.append(PaymentRequest(source, destination, amount))
    return tuple(requests)


def _randbelow(rng: random.Random, stop: int) -> int:
    bit_count = stop.bit_length()
    while True:
        candidate = rng.getrandbits(bit_count)
        if candidate < stop:
            return candidate


def _validate_length(length: object) -> None:
    if type(length) is not int or length < 0:
        raise TrafficError("length must be a non-negative integer")


def _validate_root_seed(root_seed: object) -> None:
    if type(root_seed) is not int or not 0 <= root_seed <= _MAX_UNSIGNED_64:
        raise TrafficError("root_seed must be an integer in [0, 2**64 - 1]")


__all__ = ["RequestTrace", "generate_request_trace"]
