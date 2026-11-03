import numpy as np

from eating_event.diagnostic_temporal import (
    TEMPORAL_PROBE_FEATURE_COUNT,
    extract_temporal_probe_features,
    extract_temporal_probe_matrix,
    make_diagnostic_estimator,
)


def test_temporal_probe_has_frozen_width_and_finite_deterministic_values():
    values = np.zeros((150, 6), dtype=np.float64)
    values[:, 0] = np.linspace(0.0, 1.0, 150)
    values[:, 1] = np.sin(np.linspace(0.0, 8.0 * np.pi, 150))
    values[:, 3] = np.cos(np.linspace(0.0, 4.0 * np.pi, 150))
    valid_mask = np.ones(150, dtype=bool)

    first = extract_temporal_probe_features(values, valid_mask, grid_hz=10)
    second = extract_temporal_probe_features(values, valid_mask, grid_hz=10)

    assert TEMPORAL_PROBE_FEATURE_COUNT == 72
    assert first.values.shape == (TEMPORAL_PROBE_FEATURE_COUNT,)
    assert len(first.names) == TEMPORAL_PROBE_FEATURE_COUNT
    assert np.isfinite(first.values).all()
    np.testing.assert_array_equal(first.values, second.values)
    assert first.names == second.names


def test_temporal_probe_respects_invalid_samples_without_nan_output():
    values = np.ones((150, 6), dtype=np.float64)
    values[45:55, :] = np.nan
    valid_mask = np.ones(150, dtype=bool)
    valid_mask[45:55] = False

    result = extract_temporal_probe_features(values, valid_mask, grid_hz=10)

    assert result.values.shape == (72,)
    assert np.isfinite(result.values).all()
    assert result.values.dtype == np.float32


def test_temporal_probe_matrix_matches_scalar_extraction():
    values = np.zeros((3, 150, 6), dtype=np.float64)
    values[0, :, 0] = np.linspace(0.0, 1.0, 150)
    values[1, :, 1] = np.sin(np.linspace(0.0, 8.0 * np.pi, 150))
    values[2, :, 3] = np.cos(np.linspace(0.0, 4.0 * np.pi, 150))
    valid_mask = np.ones((3, 150), dtype=bool)
    valid_mask[1, 40:50] = False
    values[1, 40:50] = np.nan

    matrix = extract_temporal_probe_matrix(values, valid_mask, grid_hz=10)
    scalar = np.vstack(
        [extract_temporal_probe_features(row, mask, grid_hz=10).values for row, mask in zip(values, valid_mask)]
    )

    np.testing.assert_allclose(matrix.values, scalar, rtol=1e-6, atol=1e-6)


def test_diagnostic_estimators_are_fixed_and_distinct():
    linear = make_diagnostic_estimator("L")
    nonlinear = make_diagnostic_estimator("N")

    assert linear.steps[0][0] == "scaler"
    assert linear.steps[1][0] == "classifier"
    assert linear.steps[1][1].C == 1.0
    assert linear.steps[1][1].class_weight == "balanced"
    assert nonlinear.max_iter == 100
    assert nonlinear.max_leaf_nodes == 7
    assert nonlinear.min_samples_leaf == 20
    assert nonlinear.learning_rate == 0.05
    assert nonlinear.l2_regularization == 1e-3
    assert nonlinear.random_state == 20260910
