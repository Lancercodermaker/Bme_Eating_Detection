import pytest

from eating_event.a1.boundaries import build_support_components
from eating_event.a1.inputs import A1Window
from eating_event.a1.contracts import WindowIdentity


def window(participant, record, session, row, start, end, *, crossed=False):
    return A1Window(
        identity=WindowIdentity(participant, record, session, row),
        start_ms=start,
        end_ms=end,
        coverage=1.0,
        crosses_hard_gap=crossed,
        features=(0.0,) * 111,
        label=0,
        session_start_ms=0,
        session_end_ms=100000,
    )


def test_overlapping_or_adjacent_windows_form_support_components():
    components = build_support_components(
        [
            window("p", "r", "s", 0, 0, 15000),
            window("p", "r", "s", 1, 7500, 22500),
            window("p", "r", "s", 2, 30000, 45000),
        ]
    )
    assert [(c.start_ms, c.end_ms, c.window_indices) for c in components] == [
        (0, 22500, (0, 1)),
        (30000, 45000, (2,)),
    ]
    assert all(c.source_segment_id is None for c in components)
    assert all(c.boundary_kind == "observed_window_support_component_v1" for c in components)


def test_different_sessions_cannot_be_combined():
    with pytest.raises(ValueError, match="same record/session"):
        build_support_components(
            [window("p", "r", "s1", 0, 0, 15000), window("p", "r", "s2", 1, 15000, 30000)]
        )


def test_gap_or_out_of_bounds_window_is_invalid():
    with pytest.raises(ValueError, match="hard gap"):
        build_support_components([window("p", "r", "s", 0, 0, 15000, crossed=True)])
    with pytest.raises(ValueError, match="session bounds"):
        build_support_components([window("p", "r", "s", 0, -1, 15000)])
