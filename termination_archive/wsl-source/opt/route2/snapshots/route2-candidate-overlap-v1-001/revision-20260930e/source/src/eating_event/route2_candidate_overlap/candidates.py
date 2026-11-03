"""Candidate interval construction without labels or evaluation truths."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import groupby
from math import isfinite
import hashlib
import json
from typing import Literal

from .contracts import REFERENCE_GAP_MS


@dataclass(frozen=True, slots=True)
class SupportWindow:
    role_id: str
    participant_id: str
    record_id: str
    session_id: str
    component_id: str
    global_index: int
    row_index: int
    start_ms: int
    end_ms: int
    relative: float
    coverage: float

    def __post_init__(self) -> None:
        if self.end_ms <= self.start_ms:
            raise ValueError("window interval must be nonempty")
        if self.global_index < 0 or self.row_index < 0:
            raise ValueError("window indices must be nonnegative")
        if not isfinite(self.relative) or not isfinite(self.coverage):
            raise ValueError("window score and coverage must be finite")
        if not 0.8 <= self.coverage <= 1.0:
            raise ValueError("window fails the frozen A1 coverage rule")
        if not all((
            self.role_id,
            self.participant_id,
            self.record_id,
            self.session_id,
            self.component_id,
        )):
            raise ValueError("candidate grouping identity must be complete")

    @property
    def group_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.role_id,
            self.participant_id,
            self.record_id,
            self.session_id,
            self.component_id,
        )


@dataclass(frozen=True, slots=True)
class WindowGeometry:
    role_id: str
    participant_id: str
    record_id: str
    session_id: str
    global_index: int
    row_index: int
    start_ms: int
    end_ms: int
    coverage: float
    crosses_gap: bool


def build_support_component_ids(
    role_id: str,
    geometry: Iterable[WindowGeometry],
) -> dict[int, str]:
    """Reproduce the frozen observed-window component rule for one role."""

    groups: dict[tuple[str, str, str], list[WindowGeometry]] = {}
    seen: set[int] = set()
    for item in geometry:
        if item.role_id != role_id:
            raise ValueError("component input contains a different role")
        if item.global_index in seen:
            raise ValueError("duplicate global identity in component input")
        seen.add(item.global_index)
        if item.end_ms <= item.start_ms or not 0.8 <= item.coverage <= 1.0:
            raise ValueError("invalid window geometry for component construction")
        if item.crosses_gap:
            raise ValueError("hard-gap window cannot enter a support component")
        group_key = (item.participant_id, item.record_id, item.session_id)
        groups.setdefault(group_key, []).append(item)

    result: dict[int, str] = {}
    for identity_key in sorted(groups):
        items = sorted(
            groups[identity_key],
            key=lambda item: (item.start_ms, item.end_ms, item.row_index),
        )
        component_ordinal = -1
        current_end: int | None = None
        for item in items:
            if current_end is None or item.start_ms > current_end:
                component_ordinal += 1
                current_end = item.end_ms
            else:
                current_end = max(current_end, item.end_ms)
            result[item.global_index] = (
                f"{identity_key[0]}|{identity_key[1]}|{identity_key[2]}|"
                f"component-{component_ordinal}"
            )
    return result


@dataclass(frozen=True, slots=True)
class Candidate:
    role_id: str
    participant_id: str
    record_id: str
    session_id: str
    component_id: str
    start_ms: int
    end_ms: int
    support_indices: tuple[int, ...]
    source_16d: tuple[float, ...]
    boundary_kind: str = "observed_window_support_component_v1"
    source_segment_id: None = None

    def __post_init__(self) -> None:
        if self.end_ms <= self.start_ms:
            raise ValueError("candidate interval must be nonempty")
        if not self.support_indices or len(set(self.support_indices)) != len(self.support_indices):
            raise ValueError("candidate support must be nonempty and unique")
        if len(self.source_16d) != 16 or not all(map(isfinite, self.source_16d)):
            raise ValueError("candidate must have 16 finite, newly derived features")
        if self.boundary_kind != "observed_window_support_component_v1":
            raise ValueError("unknown support boundary kind")
        if self.source_segment_id is not None:
            raise ValueError("source_segment_id must remain null")

    @property
    def comparison_key(self) -> tuple[object, ...]:
        return (
            self.role_id,
            self.participant_id,
            self.record_id,
            self.session_id,
            self.component_id,
            self.start_ms,
            self.end_ms,
            self.support_indices,
            self.boundary_kind,
            self.source_segment_id,
        )

    @property
    def interval_key(self) -> tuple[object, ...]:
        return (
            self.role_id,
            self.participant_id,
            self.record_id,
            self.session_id,
            self.component_id,
            self.start_ms,
            self.end_ms,
        )


@dataclass(frozen=True, slots=True)
class ReferenceInterval:
    """Projected geometry/support only; has no label, 16D, or model score."""

    role_id: str
    participant_id: str
    record_id: str
    session_id: str
    component_id: str
    start_ms: int
    end_ms: int
    support_indices: tuple[int, ...]
    boundary_kind: str
    source_segment_id: None

    @property
    def comparison_key(self) -> tuple[object, ...]:
        return (
            self.role_id,
            self.participant_id,
            self.record_id,
            self.session_id,
            self.component_id,
            self.start_ms,
            self.end_ms,
            self.support_indices,
            self.boundary_kind,
            self.source_segment_id,
        )

    @property
    def interval_key(self) -> tuple[object, ...]:
        return self.comparison_key[:7]


@dataclass(frozen=True, slots=True)
class CandidateFileReceipt:
    """One fully persisted, label-free treatment role consumed by Stage B."""

    role_id: str
    path: str
    sha256: str
    row_count: int
    file_bytes: int
    interval_fingerprint: str

    def __post_init__(self) -> None:
        if (
            not self.role_id
            or not self.path
            or type(self.row_count) is not int
            or type(self.file_bytes) is not int
            or self.row_count < 0
            or self.file_bytes < 0
            or any(len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower())
                   for value in (self.sha256, self.interval_fingerprint))
        ):
            raise ValueError("candidate file receipt is incomplete")


def _positive_windows(
    windows: Iterable[SupportWindow],
) -> list[SupportWindow]:
    items: list[SupportWindow] = []
    seen: set[tuple[str, int]] = set()
    for item in windows:
        identity = (item.role_id, item.global_index)
        if identity in seen:
            raise ValueError("duplicate global window score within role")
        seen.add(identity)
        if item.relative < 0:
            continue
        items.append(item)
    items.sort(key=lambda item: (*item.group_key, item.start_ms, item.end_ms, item.row_index))
    return items


def build_candidates(
    windows: Iterable[SupportWindow],
    *,
    rule: Literal["reference_300s", "strict_overlap"],
) -> Iterator[Candidate]:
    """Build one rule's interval stream; no truth/label argument is accepted.

    Reference fusion uses the frozen inclusive 300-second rule. Treatment
    fusion requires positive-duration overlap, so endpoint touching does not
    join. Each candidate's 16D vector is recomputed from its own support.
    """

    if rule not in {"reference_300s", "strict_overlap"}:
        raise ValueError(f"unsupported fusion rule: {rule}")
    items = _positive_windows(windows)
    for group_key, group_iter in groupby(items, key=lambda item: item.group_key):
        group = iter(group_iter)
        support: list[SupportWindow] = []
        start_ms = end_ms = 0
        for item in group:
            if not support:
                support = [item]
                start_ms, end_ms = item.start_ms, item.end_ms
                continue
            joins = (
                item.start_ms <= end_ms + REFERENCE_GAP_MS
                if rule == "reference_300s"
                else item.start_ms < end_ms
            )
            if joins:
                support.append(item)
                end_ms = max(end_ms, item.end_ms)
            else:
                yield _make_candidate(group_key, start_ms, end_ms, support)
                support = [item]
                start_ms, end_ms = item.start_ms, item.end_ms
        if support:
            yield _make_candidate(group_key, start_ms, end_ms, support)


def _make_candidate(
    key: tuple[str, str, str, str, str],
    start_ms: int,
    end_ms: int,
    support: list[SupportWindow],
) -> Candidate:
    from .features import build_source_16d

    role_id, participant_id, record_id, session_id, component_id = key
    return Candidate(
        role_id=role_id,
        participant_id=participant_id,
        record_id=record_id,
        session_id=session_id,
        component_id=component_id,
        start_ms=start_ms,
        end_ms=end_ms,
        support_indices=tuple(item.global_index for item in support),
        source_16d=tuple(build_source_16d(support, start_ms=start_ms, end_ms=end_ms)),
    )


def compare_reference_and_fingerprint(
    expected: Iterable[ReferenceInterval],
    actual: Iterable[Candidate],
) -> tuple[bool, tuple[int, str]]:
    """Compare exact reference/support rows and retain an interval fingerprint."""

    left = iter(expected)
    right = iter(actual)
    previous_left: tuple[object, ...] | None = None
    previous_right: tuple[object, ...] | None = None
    digest = hashlib.sha256()
    count = 0
    sentinel = object()
    while True:
        a = next(left, sentinel)
        b = next(right, sentinel)
        if a is sentinel or b is sentinel:
            return a is sentinel and b is sentinel, (count, digest.hexdigest())
        assert isinstance(a, ReferenceInterval) and isinstance(b, Candidate)
        ka, kb = a.comparison_key, b.comparison_key
        if previous_left is not None and ka < previous_left:
            raise ValueError("reference projection is not canonically sorted")
        if previous_right is not None and kb < previous_right:
            raise ValueError("new candidates are not canonically sorted")
        previous_left, previous_right = ka, kb
        if ka != kb:
            return False, (count, digest.hexdigest())
        interval_key = b.interval_key
        digest.update(json.dumps(interval_key, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
        count += 1


def sorted_stream_fingerprint(items: Iterable[Candidate]) -> tuple[int, str]:
    """Fingerprint an already canonical stream without retaining candidates."""

    digest = hashlib.sha256()
    count = 0
    previous: tuple[object, ...] | None = None
    for item in items:
        key = item.interval_key
        if previous is not None and key < previous:
            raise ValueError("candidate interval stream is not canonically sorted")
        previous = key
        digest.update(json.dumps(key, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


def same_interval_fingerprint(
    expected: tuple[int, str],
    actual: Iterable[Candidate],
) -> bool:
    """Support-only changes cannot pass the geometry-mechanism gate."""

    return sorted_stream_fingerprint(actual) == expected
