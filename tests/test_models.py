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


def test_m0_supports_average_and_max_temporal_pooling():
    model = IMUCNN(in_channels=10, pooling="avgmax")

    logits = model(torch.randn(3, 10, 125))

    assert logits.shape == (3,)
    assert model.head.in_features == 192


def test_m0_avgmax_supports_deterministic_cuda_backward():
    if not torch.cuda.is_available():
        pytest.skip("CUDA is not available")
    previous = torch.are_deterministic_algorithms_enabled()
    torch.use_deterministic_algorithms(True)
    try:
        model = IMUCNN(in_channels=10, pooling="avgmax").cuda()
        model(torch.randn(2, 10, 125, device="cuda")).sum().backward()
    finally:
        torch.use_deterministic_algorithms(previous)


def test_m0_supports_four_bin_temporal_average_pooling():
    model = IMUCNN(in_channels=10, pooling="avg4")

    logits = model(torch.randn(3, 10, 125))

    assert logits.shape == (3,)
    assert model.head.in_features == 384
