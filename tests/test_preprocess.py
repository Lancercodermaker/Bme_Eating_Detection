import numpy as np

from eating_detection.preprocess import fit_standardizer, imu_features, resample_uniform


def test_imu_features_keep_raw_magnitudes_and_two_masks():
    acc = np.array([[3, 0, 0], [0, 4, 0]], dtype=np.float32)
    gyro = np.array([[0, 0, 2], [0, 0, 0]], dtype=np.float32)
    acc_ok = np.array([True, False])
    gyro_ok = np.array([True, True])
    features, mask = imu_features(acc, gyro, acc_ok, gyro_ok)
    assert features.shape == (2, 8)
    assert np.allclose(features[:, 6], [3, 4])
    assert mask.tolist() == [[True, True], [False, True]]


def test_standardizer_uses_train_values_only():
    stats = fit_standardizer(np.array([[1.0, 10.0], [3.0, 14.0]]), np.ones((2, 2), bool))
    assert np.allclose(stats.mean, [2.0, 12.0])
    assert np.allclose(stats.std, [1.0, 2.0])


def test_resample_uniform_returns_expected_length_and_dtype():
    values = np.sin(np.linspace(0, 2 * np.pi, 100, endpoint=False)).astype(np.float32)
    out = resample_uniform(values[:, None], source_hz=10.0, target_hz=20)
    assert out.shape == (200, 1)
    assert out.dtype == np.float32
