"""Small window-sequence Transformer for a bounded candidate-scoring spike."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn


@dataclass(frozen=True)
class TransformerConfig:
    d_model: int = 64
    nhead: int = 4
    num_layers: int = 2
    dim_feedforward: int = 128
    dropout: float = 0.1
    max_sequence_length: int = 512

    def __post_init__(self) -> None:
        if self.d_model <= 0 or self.nhead <= 0 or self.num_layers <= 0 or self.dim_feedforward <= 0:
            raise ValueError("Transformer dimensions must be positive")
        if self.d_model % self.nhead != 0:
            raise ValueError("d_model must be divisible by nhead")
        if not 0 <= self.dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        if self.max_sequence_length <= 0:
            raise ValueError("max_sequence_length must be positive")


def _sinusoidal_positions(length: int, width: int) -> Tensor:
    positions = torch.arange(length, dtype=torch.float32).unsqueeze(1)
    frequencies = torch.exp(
        torch.arange(0, width, 2, dtype=torch.float32) * (-torch.log(torch.tensor(10_000.0)) / width)
    )
    encoding = torch.zeros(length, width, dtype=torch.float32)
    encoding[:, 0::2] = torch.sin(positions * frequencies)
    encoding[:, 1::2] = torch.cos(positions * frequencies[: encoding[:, 1::2].shape[1]])
    return encoding.unsqueeze(0)


class TemporalTransformer(nn.Module):
    """Non-causal Transformer that emits one eventness logit per candidate window."""

    def __init__(self, input_features: int, config: TransformerConfig = TransformerConfig()) -> None:
        super().__init__()
        if input_features <= 0:
            raise ValueError("input_features must be positive")
        self.config = config
        self.input_projection = nn.Linear(input_features, config.d_model)
        self.register_buffer(
            "position_encoding",
            _sinusoidal_positions(config.max_sequence_length, config.d_model),
            persistent=False,
        )
        layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.dim_feedforward,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=config.num_layers)
        self.output_projection = nn.Linear(config.d_model, 1)

    def forward(self, values: Tensor, *, valid_mask: Tensor | None = None) -> Tensor:
        if values.ndim != 3:
            raise ValueError("values must have shape [batch, windows, features]")
        batch_size, sequence_length, _ = values.shape
        if sequence_length > self.config.max_sequence_length:
            raise ValueError("sequence length exceeds max_sequence_length")
        if valid_mask is None:
            mask = torch.ones(batch_size, sequence_length, dtype=torch.bool, device=values.device)
        else:
            if valid_mask.shape != (batch_size, sequence_length):
                raise ValueError("valid_mask must have shape [batch, windows]")
            mask = valid_mask.to(dtype=torch.bool, device=values.device)

        padding_mask = ~mask
        all_padding = padding_mask.all(dim=1)
        if bool(all_padding.any()):
            padding_mask = padding_mask.clone()
            padding_mask[all_padding, 0] = False
        encoded = self.input_projection(values) + self.position_encoding[:, :sequence_length].to(values.dtype)
        key_padding_mask = None if bool(mask.all()) else padding_mask
        encoded = self.encoder(encoded, src_key_padding_mask=key_padding_mask)
        logits = self.output_projection(encoded).squeeze(-1)
        return logits.masked_fill(~mask, 0.0)
