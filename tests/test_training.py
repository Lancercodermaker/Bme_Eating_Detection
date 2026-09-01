import torch

from eating_detection.models import IMUCNN
from eating_detection.training import compute_pos_weight, train_one_batch


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
