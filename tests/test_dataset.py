import torch

from eating_detection.dataset import (
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
