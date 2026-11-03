"""Conservative observed-window support components."""

from __future__ import annotations

from dataclasses import dataclass

from eating_event.a1.inputs import A1Window


@dataclass(frozen=True)
class SupportComponent:
    component_id: str
    participant_id: str
    record_id: str
    session_id: str
    start_ms: int
    end_ms: int
    window_indices: tuple[int, ...]
    source_segment_id: None = None
    boundary_kind: str = "observed_window_support_component_v1"


def build_support_components(windows: list[A1Window] | tuple[A1Window, ...]) -> list[SupportComponent]:
    if not windows:
        return []
    ordered = sorted(windows, key=lambda item: (item.start_ms, item.end_ms, item.identity.row_index))
    first_key = (
        ordered[0].identity.participant_id,
        ordered[0].identity.record_id,
        ordered[0].identity.session_id,
    )
    for window in ordered:
        key = (window.identity.participant_id, window.identity.record_id, window.identity.session_id)
        if key != first_key:
            raise ValueError("support components require the same record/session")
        if window.crosses_hard_gap:
            raise ValueError("window crosses hard gap")
        if window.boundary_kind == "index_bounds" and (window.start_ms < window.session_start_ms or window.end_ms > window.session_end_ms):
            raise ValueError("window violates session bounds")
    components: list[SupportComponent] = []
    current_indices: list[int] = []
    current_start = 0
    current_end = 0

    def flush() -> None:
        if not current_indices:
            return
        ordinal = len(components)
        components.append(
            SupportComponent(
                component_id=f"{first_key[0]}|{first_key[1]}|{first_key[2]}|component-{ordinal}",
                participant_id=first_key[0],
                record_id=first_key[1],
                session_id=first_key[2],
                start_ms=current_start,
                end_ms=current_end,
                window_indices=tuple(current_indices),
            )
        )

    for window in ordered:
        row_index = window.identity.row_index
        if not current_indices:
            current_indices = [row_index]
            current_start, current_end = window.start_ms, window.end_ms
            continue
        if window.start_ms <= current_end:
            current_indices.append(row_index)
            current_end = max(current_end, window.end_ms)
        else:
            flush()
            current_indices = [row_index]
            current_start, current_end = window.start_ms, window.end_ms
    flush()
    return components
