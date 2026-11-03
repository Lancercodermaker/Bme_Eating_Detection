from eating_event.diagnostic_bounded_proposal import (
    Proposal,
    WindowEvidence,
    build_contiguous_segments,
    build_extra_proposals,
    union_proposals,
)


def test_segments_do_not_bridge_gap_or_hard_gap():
    windows = (
        WindowEvidence(0, 0, 15_000, 0.8, False),
        WindowEvidence(1, 7_500, 22_500, 0.7, False),
        WindowEvidence(2, 40_000, 55_000, 0.9, False),
        WindowEvidence(3, 47_500, 62_500, 0.9, True),
        WindowEvidence(4, 55_000, 70_000, 0.9, False),
    )

    segments = build_contiguous_segments(windows)

    assert segments == ((0, (0, 1)), (1, (2,)), (2, (3,)), (3, (4,)))


def test_extra_variants_are_deterministic_and_capped():
    windows = tuple(
        WindowEvidence(
            index,
            index * 7_500,
            index * 7_500 + 15_000,
            0.30 if index == 3 else 0.60 + index / 100,
            False,
        )
        for index in range(8)
    )

    first = build_extra_proposals(
        "record-a",
        windows,
        support_threshold=0.60,
        max_per_recording=4,
        max_per_hour=1_000,
    )
    second = build_extra_proposals(
        "record-a",
        windows,
        support_threshold=0.60,
        max_per_recording=4,
        max_per_hour=1_000,
    )

    assert first == second
    assert len(first) == 4
    assert all(proposal.source == "extra" for proposal in first)
    assert all(proposal.boundary_variants for proposal in first)


def test_union_preserves_baseline_and_only_deduplicates_exact_intervals():
    baseline = (
        Proposal("record-a", 0, 15_000, "A", ("baseline",), (0,), 0.8, 0.8),
        Proposal("record-a", 30_000, 45_000, "A", ("baseline",), (4,), 0.7, 0.7),
    )
    extra = (
        Proposal("record-a", 0, 15_000, "extra", ("support_core",), (0, 1), 0.8, 0.75),
        Proposal("record-a", 15_000, 30_000, "extra", ("peak_window",), (1, 2), 0.75, 0.7),
    )

    union = union_proposals(baseline, extra)

    assert {(item.record_path, item.start_ms, item.end_ms) for item in union} == {
        ("record-a", 0, 15_000),
        ("record-a", 15_000, 30_000),
        ("record-a", 30_000, 45_000),
    }
    preserved = next(item for item in union if item.start_ms == 0)
    assert preserved.source == "A+extra"
    assert preserved.source_indices == (0,)
    assert next(item for item in union if item.start_ms == 15_000).source == "extra"
