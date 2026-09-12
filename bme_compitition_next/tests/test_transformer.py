import pytest


torch = pytest.importorskip("torch")

from eating_event.models.transformer import TransformerConfig, TemporalTransformer


def test_transformer_scores_each_window_and_masks_invalid_positions() -> None:
    model = TemporalTransformer(
        input_features=6,
        config=TransformerConfig(d_model=16, nhead=4, num_layers=2, dim_feedforward=32, max_sequence_length=32),
    )
    values = torch.randn(2, 11, 6)
    valid_mask = torch.ones(2, 11, dtype=torch.bool)
    valid_mask[:, -2:] = False

    logits = model(values, valid_mask=valid_mask)

    assert logits.shape == (2, 11)
    assert torch.isfinite(logits).all()
    assert torch.equal(logits[:, -2:], torch.zeros(2, 2))


def test_transformer_rejects_sequence_longer_than_configured_limit() -> None:
    model = TemporalTransformer(
        input_features=3,
        config=TransformerConfig(d_model=8, nhead=2, num_layers=1, dim_feedforward=16, max_sequence_length=4),
    )

    with pytest.raises(ValueError, match="max_sequence_length"):
        model(torch.randn(1, 5, 3))


def test_transformer_is_bounded_in_parameter_count() -> None:
    model = TemporalTransformer(
        input_features=111,
        config=TransformerConfig(d_model=32, nhead=4, num_layers=2, dim_feedforward=64, max_sequence_length=128),
    )

    parameter_count = sum(parameter.numel() for parameter in model.parameters())

    assert parameter_count < 100_000
