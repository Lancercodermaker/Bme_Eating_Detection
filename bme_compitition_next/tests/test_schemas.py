import numpy as np
import pytest

from eating_event.schemas import CandidateRow, ManifestRow, PredictionRow


def test_prediction_row_rejects_bounds_outside_session():
    with pytest.raises(ValueError, match="session"):
        PredictionRow(
            participant_id="p",
            session_id="s",
            start_ms=0,
            end_ms=1000,
            session_start_ms=100,
            session_end_ms=900,
        )


def test_prediction_row_uses_half_open_integer_millisecond_bounds():
    row = PredictionRow(
        participant_id="p",
        session_id="s",
        start_ms=100,
        end_ms=900,
        session_start_ms=100,
        session_end_ms=900,
    )
    assert row.start_ms == 100
    assert row.end_ms == 900


def test_candidate_row_normalizes_contract_dtypes():
    row = CandidateRow(
        participant_id="p",
        session_id="s",
        start_ms=0,
        end_ms=1000,
        features=np.ones(3, dtype=np.float64),
        label=-1,
        coverage=0.8,
        invalid_run_length=2,
    )
    assert row.features.dtype == np.float32
    assert row.label == np.int8(-1)
    assert row.coverage == pytest.approx(0.8)


def test_manifest_row_rejects_unknown_status():
    with pytest.raises(ValueError, match="status"):
        ManifestRow(
            participant_id="p",
            session_id="s",
            path_or_file_id="file",
            session_start_ms=0,
            session_end_ms=1000,
            status="unknown",
            reason=None,
            row_count=1,
            valid_timestamp_count=1,
            duplicate_count=0,
            dropped_timestamp_count=0,
        )
