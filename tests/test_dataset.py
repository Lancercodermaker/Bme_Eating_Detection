import torch
import numpy as np

from eating_detection.dataset import (
    CachedWindowDataset,
    build_records_from_sensor_file,
    ParticipantBatchSampler,
    WindowDataset,
    WindowRecord,
    make_window_records,
)


def test_window_dataset_shape_and_batch_groups():
    records = [
        WindowRecord("p1", 0, 4, torch.zeros(10, 8), 1.0),
        WindowRecord("p1", 4, 8, torch.ones(10, 8), 0.0, loss_mask=False),
    ]
    dataset = WindowDataset(records)
    x, y, participant = dataset[0]
    assert x.shape == (10, 8)
    assert y.item() == 1.0
    assert participant == "p1"
    assert dataset.records[1].loss_mask is False
    batches = list(ParticipantBatchSampler(dataset, batch_size=2))
    assert batches == [[0, 1]]


def test_participant_batch_sampler_can_shuffle_deterministically_within_groups():
    records = [
        WindowRecord(participant, index, index + 1, torch.zeros(10, 8), 0.0)
        for participant in ("p1", "p2")
        for index in range(4)
    ]
    dataset = WindowDataset(records)
    first = ParticipantBatchSampler(dataset, batch_size=2, shuffle=True, seed=7)
    second = ParticipantBatchSampler(dataset, batch_size=2, shuffle=True, seed=7)

    first_batches = list(first)
    second_batches = list(second)

    assert first_batches == second_batches
    assert first_batches != [[0, 1], [2, 3], [4, 5], [6, 7]]
    assert all(
        len({dataset.participant_for_index(index) for index in batch}) == 1
        for batch in first_batches
    )


def test_make_window_records_preserves_soft_labels_and_ignore_mask():
    features = torch.zeros(10, 30)
    records = make_window_records(
        participant="p1",
        start_ms=0,
        sample_hz=10,
        features=features,
        intervals=[(500, 1500)],
        window_sec=1,
        step_sec=1,
        positive_overlap=0.75,
        boundary_mode="soft",
    )
    assert [(record.start_ms, record.end_ms) for record in records[:2]] == [
        (0, 1000),
        (1000, 2000),
    ]
    assert records[0].label == 0.5
    assert records[0].loss_mask is True


def test_build_records_p1_adds_derived_channels(monkeypatch, tmp_path):
    timestamps = np.arange(128, dtype=np.int64) * 1000
    acc = np.column_stack([np.sin(timestamps / 1000), np.ones(128), np.zeros(128)]).astype(np.float32)
    gyro = np.column_stack([np.cos(timestamps / 1000), np.zeros(128), np.ones(128)]).astype(np.float32)
    monkeypatch.setattr(
        "eating_detection.dataset._read_sensor_file",
        lambda *args, **kwargs: (
            timestamps,
            timestamps,
            timestamps,
            acc,
            gyro,
            np.ones(128, dtype=bool),
            np.ones(128, dtype=bool),
        ),
    )
    records = build_records_from_sensor_file(
        tmp_path / "organized" / "p1" / "sample.txt",
        intervals=[],
        resample_hz=25,
        window_sec=1,
        step_sec=1,
        positive_overlap=0.25,
        boundary_mode="soft",
        preprocess_variant="p1_lowpass_dynamic",
    )
    assert records
    assert records[0].features.shape[0] == 16
