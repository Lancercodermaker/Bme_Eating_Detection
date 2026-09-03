import pytest
import torch
from torch import nn

from eating_detection.models import IMUCNN


def test_m0_accepts_batch_channel_time_and_returns_logits():
    model = IMUCNN(in_channels=10)
    logits = model(torch.randn(3, 10, 125))
    assert logits.shape == (3,)
    assert torch.isfinite(logits).all()


def test_m0_rejects_wrong_channel_count():
    model = IMUCNN(in_channels=10)
    with pytest.raises(ValueError, match="channels"):
        model(torch.randn(2, 9, 125))


def test_m0_supports_group_normalization_without_running_statistics():
    model = IMUCNN(in_channels=10, normalization="group")

    assert any(isinstance(module, nn.GroupNorm) for module in model.modules())
    assert not any(isinstance(module, nn.BatchNorm1d) for module in model.modules())
