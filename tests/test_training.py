import torch

from eating_detection.models import IMUCNN
from eating_detection.dataset import WindowRecord
from eating_detection.training import (
    compute_pos_weight,
    evaluate_predictions,
    standardize_window_records,
    train_one_batch,
)


def test_pos_weight_uses_only_train_labels():
    assert compute_pos_weight([0.0, 0.0, 1.0, 1.0, 1.0]) == 2 / 3


def test_train_one_batch_updates_model_with_logits_loss():
    torch.manual_seed(7)
    model = IMUCNN(in_channels=10)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    before = [parameter.detach().clone() for parameter in model.parameters()]
    loss = train_one_batch(
        model,
        optimizer,
        torch.randn(4, 10, 32),
        torch.tensor([0.0, 1.0, 0.0, 1.0]),
        pos_weight=1.0,
    )
    assert loss >= 0.0
    assert any(
        not torch.equal(old, new.detach())
        for old, new in zip(before, model.parameters())
    )


def test_standardize_window_records_uses_train_participants_only():
    train = WindowRecord("p1", 0, 2, torch.tensor([[1.0, 3.0]] * 8 + [[1.0, 1.0], [1.0, 1.0]]), 1.0)
    validation = WindowRecord("p2", 0, 2, torch.tensor([[101.0, 103.0]] * 8 + [[1.0, 1.0], [1.0, 1.0]]), 0.0)
    standardized, stats = standardize_window_records([train, validation], {"p1"})
    assert torch.allclose(standardized[0].features[0], torch.tensor([-1.0, 1.0]))
    assert torch.allclose(standardized[1].features[0], torch.tensor([99.0, 101.0]))
    assert stats.mean[0] == 2.0


def test_evaluate_predictions_only_scores_supplied_split_truth():
    aggregate, _, _ = evaluate_predictions(
        predictions={"val": [(0, 10, 0.9)]},
        truth={"train": [(0, 10)], "val": [(0, 10)]},
        decoder={"threshold": 0.5, "merge_gap_ms": 0, "min_duration_ms": 0},
        iou_threshold=0.25,
        participants={"val"},
    )
    assert aggregate.tp == 1
    assert aggregate.fn == 0
