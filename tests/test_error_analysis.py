import numpy as np

from eating_detection.error_analysis import calibration_summary, quality_stratification


def test_calibration_summary_reports_brier_ece_and_bins():
    result = calibration_summary(np.array([0.1, 0.9]), np.array([0.0, 1.0]), bins=2)

    assert result["brier"] == 0.01
    assert result["ece"] == 0.1
    assert [item["count"] for item in result["bins"]] == [1, 1]


def test_quality_stratification_reports_window_rate_and_error():
    result = quality_stratification(
        probabilities=np.array([0.1, 0.8, 0.2, 0.7]),
        labels=np.array([0.0, 1.0, 0.0, 1.0]),
        quality_fraction=np.array([0.1, 0.1, 0.9, 0.9]),
        threshold=0.5,
        bins=(0.0, 0.5, 1.0),
    )

    assert [item["count"] for item in result] == [2, 2]
    assert result[0]["positive_rate"] == 0.5
    assert result[0]["predicted_positive_rate"] == 0.5
    assert result[1]["false_positive_rate"] == 0.0
