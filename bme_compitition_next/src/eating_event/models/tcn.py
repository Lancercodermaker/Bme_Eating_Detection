"""Small dilated temporal convolutional scorer for dense candidate windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor, nn


@dataclass(frozen=True)
class TCNConfig:
    hidden_channels: int = 64
    kernel_size: int = 3
    dilations: tuple[int, ...] = (1, 2, 4, 8, 16)
    dropout: float = 0.1

    def __post_init__(self) -> None:
        if self.hidden_channels <= 0:
            raise ValueError("hidden_channels must be positive")
        if self.kernel_size < 2 or self.kernel_size % 2 == 0:
            raise ValueError("kernel_size must be odd and at least 3")
        if not self.dilations or any(dilation <= 0 for dilation in self.dilations):
            raise ValueError("dilations must contain positive values")
        if not 0 <= self.dropout < 1:
            raise ValueError("dropout must be in [0, 1)")


def receptive_field(*, kernel_size: int, dilations: Sequence[int], convolutions_per_block: int = 2) -> int:
    """Return the number of sequence positions visible to one output."""

    if kernel_size < 2 or convolutions_per_block <= 0 or any(dilation <= 0 for dilation in dilations):
        raise ValueError("kernel_size, convolutions_per_block, and dilations must be positive")
    return 1 + convolutions_per_block * (kernel_size - 1) * sum(dilations)


class _ResidualBlock(nn.Module):
    def __init__(self, channels: int, *, kernel_size: int, dilation: int, dropout: float) -> None:
        super().__init__()
        padding = dilation * (kernel_size - 1) // 2
        self.net = nn.Sequential(
            nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=dilation),
            nn.GroupNorm(1, channels),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Conv1d(channels, channels, kernel_size, padding=padding, dilation=dilation),
            nn.GroupNorm(1, channels),
            nn.GELU(),
            nn.Dropout(dropout),
        )

    def forward(self, values: Tensor) -> Tensor:
        return values + self.net(values)


class TemporalConvNet(nn.Module):
    """Non-causal residual TCN that scores one logit per dense window."""

    def __init__(self, input_channels: int, config: TCNConfig = TCNConfig()) -> None:
        super().__init__()
        if input_channels <= 0:
            raise ValueError("input_channels must be positive")
        self.config = config
        self.input_projection = nn.Conv1d(input_channels, config.hidden_channels, kernel_size=1)
        self.blocks = nn.Sequential(
            *(
                _ResidualBlock(
                    config.hidden_channels,
                    kernel_size=config.kernel_size,
                    dilation=dilation,
                    dropout=config.dropout,
                )
                for dilation in config.dilations
            )
        )
        self.output_projection = nn.Conv1d(config.hidden_channels, 1, kernel_size=1)

    def forward(self, values: Tensor, *, valid_mask: Tensor | None = None) -> Tensor:
        if values.ndim != 3:
            raise ValueError("values must have shape [batch, channels, windows]")
        projected = self.input_projection(values)
        logits = self.output_projection(self.blocks(projected)).squeeze(1)
        if valid_mask is not None:
            if valid_mask.shape != logits.shape:
                raise ValueError("valid_mask must have shape [batch, windows]")
            logits = logits.masked_fill(~valid_mask.to(dtype=torch.bool), 0.0)
        return logits

