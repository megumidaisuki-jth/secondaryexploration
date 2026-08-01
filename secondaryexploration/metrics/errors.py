"""Shared metric validation error."""


class MetricError(ValueError):
    """Raised when a metric input or derived record is inconsistent."""


__all__ = ["MetricError"]
