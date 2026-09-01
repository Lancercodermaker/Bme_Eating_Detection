import torch
from torch import nn


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, kernel_size=5, padding=2),
            nn.BatchNorm1d(out_channels),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )

    def forward(self, x):
        return self.net(x)


class IMUCNN(nn.Module):
    def __init__(self, in_channels: int = 10):
        super().__init__()
        if in_channels <= 0:
            raise ValueError("in_channels must be positive")
        self.in_channels = in_channels
        self.encoder = nn.Sequential(
            ConvBlock(in_channels, 32),
            ConvBlock(32, 64),
            ConvBlock(64, 96),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Linear(96, 1)

    def forward(self, x):
        if x.ndim != 3 or x.shape[1] != self.in_channels:
            raise ValueError(
                f"expected (batch, channels, time) with {self.in_channels} channels"
            )
        return self.head(self.encoder(x).squeeze(-1)).squeeze(-1)
