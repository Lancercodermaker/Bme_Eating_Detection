from __future__ import annotations

import numpy as np
import pytest

from eating_event.a2.features import ContextWindow, build_a2_features
from eating_event.metrics import EventInterval


def window(index: int, start: int, end: int, score: float, *, role: str = "candidate/r0/inner", component: str = "p|r|s|component-0") -> ContextWindow:
    return ContextWindow(
        role_id=role,
        global_window_index=index,
        stable_id=f"p|r|s|{index}",
        component_id=component,
        start_ms=start,
        end_ms=end,
        relative=score,
    )


def make_features(windows: list[ContextWindow]) -> np.ndarray:
    return build_a2_features(
        source_16d=tuple(range(16)),
        interval=EventInterval(100, 300),
        role_id="candidate/r0/inner",
        component_id="p|r|s|component-0",
        context_windows=windows,
    )


def test_midpoint_equal_to_start_is_inside_and_equal_to_end_is_post() -> None:
    values = make_features(
        [
            window(0, 90, 110, 2.0),  # midpoint == s
            window(1, 290, 310, -2.0),  # midpoint == e
        ]
    )

    assert values.shape == (26,)
    assert values[16] == 2.0
    assert values[17] == 2.0
    assert values[18] == 1.0
    assert values[23] == -2.0


def test_positive_run_uses_positive_length_half_open_intersection() -> None:
    values = make_features(
        [
            window(0, 100, 180, 1.0),
            window(1, 179, 240, 1.0),  # overlaps by one millisecond
            window(2, 240, 280, 1.0),  # endpoint touch breaks the run
        ]
    )

    assert values[18] == 1.0
    assert values[19] == pytest.approx(2 / 3)


def test_negative_relative_score_breaks_positive_run() -> None:
    values = make_features(
        [
            window(0, 100, 170, 1.0),
            window(1, 160, 210, -0.001),
            window(2, 200, 290, 1.0),
        ]
    )

    assert values[18] == pytest.approx(2 / 3)
    assert values[19] == pytest.approx(1 / 3)


def test_empty_pre_and_post_regions_are_three_zeros_each() -> None:
    values = make_features([window(0, 120, 220, 0.25)])

    assert tuple(values[20:23]) == (0.0, 0.0, 0.0)
    assert tuple(values[23:26]) == (0.0, 0.0, 0.0)


def test_empty_inside_region_is_invalid() -> None:
    with pytest.raises(ValueError, match="inside region"):
        make_features([window(0, -100, -50, 1.0)])


@pytest.mark.parametrize(
    "bad_window",
    [
        window(0, 100, 200, 1.0, role="candidate/other/inner"),
        window(0, 100, 200, 1.0, component="p|r|s|component-1"),
    ],
)
def test_other_role_or_component_context_is_rejected(bad_window: ContextWindow) -> None:
    with pytest.raises(ValueError, match="role|component"):
        make_features([window(1, 120, 220, 1.0), bad_window])


def test_midpoint_regions_can_include_boundary_overlapping_windows() -> None:
    # Midpoint allocation may place boundary-overlapping windows in pre/post.
    values = make_features([window(0, 40, 140, 4.0), window(1, 150, 200, 0.0), window(2, 260, 360, 2.0)])

    assert values[20] == 4.0
    assert values[23] == 2.0
