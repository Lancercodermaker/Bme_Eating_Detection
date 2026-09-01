import torch

from eating_detection.dataset import ParticipantBatchSampler, WindowDataset, WindowRecord


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
