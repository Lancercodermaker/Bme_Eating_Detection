import torch
import json

from eating_detection.models import IMUCNN
from eating_detection.dataset import WindowRecord
from eating_detection.training import (
    compute_pos_weight,
    evaluate_predictions,
    fit_m0,
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


def test_fit_m0_writes_participant_and_window_summary(tmp_path):
    torch.manual_seed(7)
    records = []
    for participant, labels in (("p1", (0.0, 1.0)), ("p2", (0.0, 1.0))):
        for index, label in enumerate(labels):
            features = torch.randn(10, 32)
            features[8:] = 1.0
            records.append(WindowRecord(participant, index * 32000, (index + 1) * 32000, features, label))
    fit_m0(
        records=records,
        train_participants={"p1"},
        val_participants={"p2"},
        truth={"p2": [(0, 64000)]},
        output_dir=tmp_path,
        config_payload={"event_iou_threshold": 0.25},
        split_manifest={"train": ["p1"], "val": ["p2"]},
        epochs=1,
        batch_size=2,
        seed=7,
        iou_threshold=0.25,
        device_name="cpu",
    )
    report = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert {"participant_f1_mean", "participant_f1_std", "participant_f1_worst", "window_count", "window_samples", "training_time_sec"} <= set(report)


def test_standardize_window_records_keeps_p1_derived_channels():
    features = torch.zeros(16, 4)
    features[:14] = torch.arange(14, dtype=torch.float32).unsqueeze(1)
    features[-2:] = 1.0
    records, stats = standardize_window_records(
        [WindowRecord("p1", 0, 4, features, 1.0)], {"p1"}
    )
    assert records[0].features.shape == (16, 4)
    assert stats.mean.shape == (14,)
