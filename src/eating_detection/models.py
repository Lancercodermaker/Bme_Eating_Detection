import torch
from torch import nn


def _equal_bin_mean(x: torch.Tensor, bins: int) -> torch.Tensor:
    if x.shape[-1] < bins:
        raise ValueError("temporal dimension must contain at least one sample per bin")
    return torch.cat(
        [part.mean(dim=-1, keepdim=True) for part in torch.tensor_split(x, bins, dim=-1)],
        dim=-1,
    )


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, normalization: str = "batch"):
        super().__init__()
        if normalization == "batch":
            norm = nn.BatchNorm1d(out_channels)
        elif normalization == "group":
            norm = nn.GroupNorm(num_groups=8, num_channels=out_channels)
        else:
            raise ValueError("normalization must be batch or group")
        self.net = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, kernel_size=5, padding=2),
            norm,
            nn.ReLU(),
            nn.MaxPool1d(2),
        )

    def forward(self, x):
        return self.net(x)


class IMUCNN(nn.Module):
    def __init__(
        self,
        in_channels: int = 10,
        normalization: str = "batch",
        pooling: str = "avg",
    ):
        super().__init__()
        if in_channels <= 0:
            raise ValueError("in_channels must be positive")
        if normalization not in {"batch", "group"}:
            raise ValueError("normalization must be batch or group")
        if pooling not in {"avg", "avgmax", "avg4"}:
            raise ValueError("pooling must be avg, avgmax, or avg4")
        self.in_channels = in_channels
        self.normalization = normalization
        self.pooling = pooling
        blocks = [
            ConvBlock(in_channels, 32, normalization),
            ConvBlock(32, 64, normalization),
            ConvBlock(64, 96, normalization),
        ]
        if pooling == "avg":
            # Keep the original module layout for checkpoint compatibility.
            self.encoder = nn.Sequential(*blocks, nn.AdaptiveAvgPool1d(1))
            self.head = nn.Linear(96, 1)
        elif pooling == "avgmax":
            self.encoder = nn.Sequential(*blocks)
            self.head = nn.Linear(192, 1)
        else:
            self.encoder = nn.Sequential(*blocks)
            self.head = nn.Linear(384, 1)

    def forward(self, x):
        if x.ndim != 3 or x.shape[1] != self.in_channels:
            raise ValueError(
                f"expected (batch, channels, time) with {self.in_channels} channels"
            )
        encoded = self.encoder(x)
        if self.pooling == "avg":
            pooled = encoded.squeeze(-1)
        elif self.pooling == "avgmax":
            pooled = torch.cat(
                [
                    encoded.mean(dim=-1),
                    encoded.amax(dim=-1),
                ],
                dim=1,
            )
        else:
            pooled = _equal_bin_mean(encoded, 4).flatten(start_dim=1)
        return self.head(pooled).squeeze(-1)
