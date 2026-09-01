import pytest
import torch

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
