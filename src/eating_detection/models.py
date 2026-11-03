import torch
from torch import nn
import torch.nn.functional as F
from typing import Mapping


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


class TemporalEncoder(nn.Module):
    """Independent fixed-length temporal encoder for a single sensor modality."""

    def __init__(
        self,
        in_channels: int,
        embedding_dim: int = 64,
        normalization: str = "group",
        pooling: str = "avg",
    ):
        super().__init__()
        if in_channels <= 0 or embedding_dim <= 0:
            raise ValueError("encoder channel counts must be positive")
        if pooling not in {"avg", "avgmax", "avg4"}:
            raise ValueError("pooling must be avg, avgmax, or avg4")
        self.in_channels = in_channels
        self.pooling = pooling
        blocks = [
            ConvBlock(in_channels, 32, normalization),
            ConvBlock(32, 64, normalization),
            ConvBlock(64, 96, normalization),
        ]
        if pooling == "avg":
            blocks.append(nn.AdaptiveAvgPool1d(1))
            projection_channels = 96
        elif pooling == "avgmax":
            projection_channels = 192
        else:
            projection_channels = 96 * 4
        self.blocks = nn.Sequential(
            *blocks,
        )
        self.projection = nn.Linear(projection_channels, embedding_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 3 or x.shape[1] != self.in_channels:
            raise ValueError(
                f"expected (batch, channels, time) with {self.in_channels} channels"
            )
        encoded = self.blocks(x)
        if self.pooling == "avg":
            pooled = encoded.squeeze(-1)
        elif self.pooling == "avgmax":
            pooled = torch.cat(
                [encoded.mean(dim=-1), encoded.amax(dim=-1)], dim=1
            )
        else:
            pooled = _equal_bin_mean(encoded, 4).flatten(start_dim=1)
        return self.projection(pooled)


class IMUPPGFusion(nn.Module):
    """Feature-level M1 fusion with explicit availability and safe dropout.

    PPG's 45th channel is its pointwise quality signal. ``modality_mask`` is
    deliberately separate: it specifies whether IMU/PPG is observable for
    each window, so a missing modality is never represented only by zeros.
    """

    def __init__(
        self,
        imu_channels: int = 10,
        ppg_channels: int = 45,
        embedding_dim: int = 64,
        modality_dropout: float = 0.25,
        normalization: str = "group",
        pooling: str = "avg",
        fusion_mode: str = "concat",
    ):
        super().__init__()
        if not 0.0 <= modality_dropout <= 1.0:
            raise ValueError("modality_dropout must be in [0, 1]")
        if fusion_mode not in {
            "concat", "shared_mean", "normalized_mean", "logit_mean", "logit_min"
        }:
            raise ValueError(
                "fusion_mode must be concat, shared_mean, normalized_mean, logit_mean, or logit_min"
            )
        self.imu_encoder = TemporalEncoder(
            imu_channels, embedding_dim, normalization, pooling=pooling
        )
        self.ppg_encoder = TemporalEncoder(
            ppg_channels, embedding_dim, normalization, pooling=pooling
        )
        self.modality_dropout = float(modality_dropout)
        self.fusion_mode = fusion_mode
        if fusion_mode == "concat":
            self.gate = nn.Sequential(
                nn.Linear(embedding_dim * 2 + 2, embedding_dim),
                nn.ReLU(),
                nn.Linear(embedding_dim, 2),
                nn.Sigmoid(),
            )
            self.head = nn.Linear(embedding_dim * 2 + 2, 1)
        elif fusion_mode in {"logit_mean", "logit_min"}:
            self.imu_head = nn.Linear(embedding_dim, 1)
            self.ppg_head = nn.Linear(embedding_dim, 1)
            self.missing_logit = nn.Parameter(torch.zeros(1))
        else:
            self.head = nn.Linear(embedding_dim, 1)

    @staticmethod
    def _validate_inputs(
        imu: torch.Tensor,
        ppg: torch.Tensor,
        modality_mask: torch.Tensor,
    ) -> None:
        if imu.ndim != 3 or ppg.ndim != 3:
            raise ValueError("IMU and PPG inputs must have shape (batch, channels, time)")
        if imu.shape[0] != ppg.shape[0] or imu.shape[2] != ppg.shape[2]:
            raise ValueError("IMU and PPG must have matching batch and temporal dimensions")
        if modality_mask.shape != (imu.shape[0], 2):
            raise ValueError("modality_mask must have shape (batch, 2)")
        if imu.device != ppg.device or imu.device != modality_mask.device:
            raise ValueError("IMU, PPG, and modality_mask must share a device")
        if not torch.isfinite(imu).all() or not torch.isfinite(ppg).all():
            raise ValueError("IMU and PPG inputs must be finite")
        if not torch.all((modality_mask == 0) | (modality_mask == 1)):
            raise ValueError("modality_mask entries must be binary")

    def apply_modality_dropout(
        self,
        imu: torch.Tensor,
        ppg: torch.Tensor,
        modality_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Drop at most one available modality per training example."""
        self._validate_inputs(imu, ppg, modality_mask)
        available = modality_mask.to(dtype=torch.bool)
        if not self.training or self.modality_dropout == 0.0:
            return imu, ppg, available.to(dtype=imu.dtype)

        drop_rows = (available.sum(dim=1) == 2) & (
            torch.rand(imu.shape[0], device=imu.device) < self.modality_dropout
        )
        dropped = available.clone()
        if drop_rows.any():
            selected = torch.rand(int(drop_rows.sum()), device=imu.device) < 0.5
            row_indices = torch.nonzero(drop_rows, as_tuple=False).squeeze(1)
            dropped[row_indices[selected], 0] = False
            dropped[row_indices[~selected], 1] = False
        active = dropped.to(dtype=imu.dtype)
        return (
            imu * active[:, 0].view(-1, 1, 1),
            ppg * active[:, 1].view(-1, 1, 1),
            active,
        )

    def forward(
        self,
        imu: torch.Tensor,
        ppg: torch.Tensor,
        modality_mask: torch.Tensor,
    ) -> torch.Tensor:
        imu, ppg, active = self.apply_modality_dropout(imu, ppg, modality_mask)
        imu_embedding = self.imu_encoder(imu) * active[:, :1]
        ppg_embedding = self.ppg_encoder(ppg) * active[:, 1:]
        if self.fusion_mode in {"logit_mean", "logit_min"}:
            imu_logits = self.imu_head(imu_embedding).squeeze(-1)
            ppg_logits = self.ppg_head(ppg_embedding).squeeze(-1)
            available_count = active.sum(dim=1)
            if self.fusion_mode == "logit_mean":
                modality_logits = (
                    imu_logits * active[:, 0] + ppg_logits * active[:, 1]
                ) / available_count.clamp_min(1.0)
            else:
                both = (active[:, 0] == 1) & (active[:, 1] == 1)
                imu_only = (active[:, 0] == 1) & (active[:, 1] == 0)
                ppg_only = (active[:, 0] == 0) & (active[:, 1] == 1)
                modality_logits = torch.where(
                    both,
                    torch.minimum(imu_logits, ppg_logits),
                    torch.where(
                        imu_only,
                        imu_logits,
                        torch.where(ppg_only, ppg_logits, self.missing_logit),
                    ),
                )
            return torch.where(
                available_count > 0.0,
                modality_logits,
                self.missing_logit.expand(imu.shape[0]),
            )
        if self.fusion_mode in {"shared_mean", "normalized_mean"}:
            available_count = active.sum(dim=1, keepdim=True).clamp_min(1.0)
            if self.fusion_mode == "normalized_mean":
                imu_embedding = F.normalize(imu_embedding, p=2, dim=1) * active[:, :1]
                ppg_embedding = F.normalize(ppg_embedding, p=2, dim=1) * active[:, 1:]
            fused = (imu_embedding + ppg_embedding) / available_count
            return self.head(fused).squeeze(-1)
        gates = self.gate(torch.cat((imu_embedding, ppg_embedding, active), dim=1))
        fused = torch.cat(
            (
                imu_embedding * gates[:, :1] * active[:, :1],
                ppg_embedding * gates[:, 1:] * active[:, 1:],
                active,
            ),
            dim=1,
        )
        return self.head(fused).squeeze(-1)


def load_compatible_imu_encoder_from_m0(
    model: IMUPPGFusion, m0_state_dict: Mapping[str, torch.Tensor]
) -> None:
    """Load only a completely compatible IMU encoder; otherwise fail closed."""
    expected = model.imu_encoder.state_dict()
    supplied = {
        key.removeprefix("imu_encoder."): value
        for key, value in m0_state_dict.items()
        if key.startswith("imu_encoder.")
    }
    compatible = set(supplied) == set(expected) and all(
        supplied[key].shape == expected[key].shape for key in expected
    )
    if not compatible:
        raise ValueError("M0 IMU encoder is not structurally compatible with M1")
    model.imu_encoder.load_state_dict(supplied, strict=True)
