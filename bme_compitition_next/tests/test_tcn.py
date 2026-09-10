import pytest


torch = pytest.importorskip("torch")

from eating_event.models.tcn import TCNConfig, TemporalConvNet, receptive_field


def test_tcn_preserves_window_axis_and_masks_invalid_positions() -> None:
    model = TemporalConvNet(input_channels=4, config=TCNConfig(hidden_channels=8, dilations=(1, 2, 4)))
    values = torch.randn(2, 4, 17)
    valid_mask = torch.ones(2, 17, dtype=torch.bool)
    valid_mask[:, -2:] = False

    logits = model(values, valid_mask=valid_mask)

    assert logits.shape == (2, 17)
    assert torch.isfinite(logits).all()
    assert torch.equal(logits[:, -2:], torch.zeros(2, 2))


def test_tcn_receptive_field_accounts_for_two_convolutions_per_block() -> None:
    assert receptive_field(kernel_size=3, dilations=(1, 2, 4)) == 29
