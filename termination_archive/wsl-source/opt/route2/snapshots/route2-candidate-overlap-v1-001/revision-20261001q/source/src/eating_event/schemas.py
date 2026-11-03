"""Typed, serializable contracts shared by the event pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


MANIFEST_STATUSES = frozenset(
    {
        "processed",
        "skipped_malformed",
        "skipped_missing_index",
        "skipped_invalid_session",
        "skipped_no_valid_timestamp",
        "skipped_missing_required_imu",
        "skipped_cache_missing",
    }
)


def _validate_interval(start_ms: int, end_ms: int, *, message: str = "interval") -> None:
    if not isinstance(start_ms, (int, np.integer)) or not isinstance(end_ms, (int, np.integer)):
        raise TypeError(f"{message} bounds must be integers")
    if end_ms <= start_ms:
        raise ValueError(f"{message} end_ms must be greater than start_ms")


@dataclass(frozen=True)
class ManifestRow:
    participant_id: str
    session_id: str
    path_or_file_id: str
    session_start_ms: int
    session_end_ms: int
    status: str
    reason: str | None
    row_count: int | None
    valid_timestamp_count: int
    duplicate_count: int
    dropped_timestamp_count: int

    def __post_init__(self) -> None:
        _validate_interval(self.session_start_ms, self.session_end_ms, message="session")
        if self.status not in MANIFEST_STATUSES:
            raise ValueError(f"unknown manifest status: {self.status}")
        for name in ("valid_timestamp_count", "duplicate_count", "dropped_timestamp_count"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.row_count is not None and self.row_count < 0:
            raise ValueError("row_count must be non-negative")


@dataclass(frozen=True)
class GapSummary:
    session_id: str
    gap_start_ms: int
    gap_end_ms: int
    segment_before: int | None = None
    segment_after: int | None = None

    def __post_init__(self) -> None:
        _validate_interval(self.gap_start_ms, self.gap_end_ms, message="gap")


@dataclass(frozen=True)
class CandidateRow:
    participant_id: str
    session_id: str
    start_ms: int
    end_ms: int
    features: np.ndarray
    label: int
    coverage: float
    invalid_run_length: int
    segment_id: int = 0

    def __post_init__(self) -> None:
        _validate_interval(self.start_ms, self.end_ms)
        if self.label not in (-1, 0, 1):
            raise ValueError("candidate label must be one of -1, 0 or 1")
        if not 0.0 <= float(self.coverage) <= 1.0:
            raise ValueError("candidate coverage must be in [0, 1]")
        if self.invalid_run_length < 0:
            raise ValueError("invalid_run_length must be non-negative")
        values = np.asarray(self.features, dtype=np.float32)
        if values.ndim != 1 or not np.isfinite(values).all():
            raise ValueError("candidate features must be a finite one-dimensional array")
        object.__setattr__(self, "features", values)
        object.__setattr__(self, "label", np.int8(self.label))
        object.__setattr__(self, "coverage", float(self.coverage))


@dataclass(frozen=True)
class EventCandidateRow:
    participant_id: str
    session_id: str
    segment_id: int
    start_ms: int
    end_ms: int
    features: np.ndarray
    label: int
    candidate_status: Literal["positive", "negative", "ignore"] = "negative"
    quality_status: str = "audited"
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_interval(self.start_ms, self.end_ms)
        if self.label not in (-1, 0, 1):
            raise ValueError("event candidate label must be one of -1, 0 or 1")
        if self.candidate_status not in {"positive", "negative", "ignore"}:
            raise ValueError("invalid event candidate status")
        values = np.asarray(self.features, dtype=np.float64)
        if values.ndim != 1 or not np.isfinite(values).all():
            raise ValueError("event candidate features must be finite and one-dimensional")
        object.__setattr__(self, "features", values)
        object.__setattr__(self, "label", np.int8(self.label))
        object.__setattr__(self, "quality_flags", tuple(self.quality_flags))


@dataclass(frozen=True)
class PredictionRow:
    participant_id: str
    session_id: str
    start_ms: int
    end_ms: int
    session_start_ms: int
    session_end_ms: int
    score: float | None = None

    def __post_init__(self) -> None:
        _validate_interval(self.start_ms, self.end_ms, message="prediction")
        _validate_interval(self.session_start_ms, self.session_end_ms, message="session")
        if not self.session_start_ms <= self.start_ms < self.end_ms <= self.session_end_ms:
            raise ValueError("prediction bounds must lie inside session")
        if self.score is not None and not np.isfinite(self.score):
            raise ValueError("prediction score must be finite")
