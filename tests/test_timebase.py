import numpy as np
import time

from eating_detection.timebase import canonicalize_stream, infer_rate_hz, interpolate_uniform


def test_zero_timestamps_removed_and_duplicates_averaged():
    t = np.array([0, 1000, 1000, 2000], dtype=np.int64)
    x = np.array([[99.0], [1.0], [3.0], [5.0]], dtype=np.float32)
    out = canonicalize_stream(t, x)
    assert out.timestamps_ms.tolist() == [1000, 2000]
    assert np.allclose(out.values[:, 0], [2.0, 5.0])
    assert out.duplicate_rows == 1


def test_rate_uses_positive_unique_deltas():
    assert infer_rate_hz(np.array([1000, 1020, 1040, 1060])) == 50.0


def test_duplicate_aggregation_scales_for_large_packetized_stream():
    timestamps = np.repeat(np.arange(1, 10_001, dtype=np.int64) * 100, 10)
    values = np.arange(len(timestamps), dtype=np.float32)[:, None]

    started = time.perf_counter()
    out = canonicalize_stream(timestamps, values)
    elapsed = time.perf_counter() - started

    assert out.duplicate_rows == 90_000
    assert out.timestamps_ms.shape == (10_000,)
    assert np.allclose(out.values[[0, -1], 0], [4.5, 99_994.5])
    assert elapsed < 0.75


def test_interpolation_masks_large_gaps_and_out_of_range():
    stream = canonicalize_stream(
        np.array([1000, 2000, 5000]),
        np.array([[1.0], [2.0], [5.0]], dtype=np.float32),
    )
    grid, values, valid = interpolate_uniform(stream, 1, 500, 5500, max_gap_ms=1500)
    assert grid[0] == 500
    assert not valid[0]
    assert valid.tolist() == [False, True, False, False, False, False]
    assert not valid[-1]
    assert values.dtype == np.float32
