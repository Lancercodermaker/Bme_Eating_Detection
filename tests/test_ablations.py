import pytest

import numpy as np

from eating_detection.preprocess import apply_feature_variant, apply_variant
from eating_detection.training import mirror_imu_axes


def test_p0_always_keeps_raw_imu_and_masks():
    out = apply_variant(
        "p0_raw_mask", raw_imu_channels=6, magnitude_channels=2, mask_channels=2
    )
    assert out["channels"] == 10
    assert out["keeps_raw"] is True


def test_unknown_preprocess_variant_is_rejected():
    with pytest.raises(ValueError, match="unknown preprocess variant"):
        apply_variant("unknown", raw_imu_channels=6, magnitude_channels=2, mask_channels=2)


def test_p1_adds_six_derived_channels_without_dropping_p0():
    base = np.ones((128, 8), dtype=np.float32)
    out = apply_feature_variant(
        base, sample_hz=25, name="p1_lowpass_dynamic", lowpass_cutoff_hz=1.0, median_kernel=5
    )
    assert out.shape == (128, 14)
    assert np.array_equal(out[:, :8], base)


def test_p2_mirrors_only_raw_x_axes():
    values = np.arange(20, dtype=np.float32).reshape(1, 10, 2)
    out = mirror_imu_axes(values)
    assert np.array_equal(out[:, 0], -values[:, 0])
    assert np.array_equal(out[:, 3], -values[:, 3])
    assert np.array_equal(out[:, 6:], values[:, 6:])
