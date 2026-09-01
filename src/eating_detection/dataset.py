from dataclasses import dataclass

import torch
from torch.utils.data import Dataset, Sampler


@dataclass(frozen=True)
class WindowRecord:
    participant: str
    start_ms: int
    end_ms: int
    features: torch.Tensor
    label: float
    loss_mask: bool = True


class WindowDataset(Dataset):
    def __init__(self, records):
        self.records = list(records)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]
        return (
            record.features,
            torch.tensor(record.label, dtype=torch.float32),
            record.participant,
        )


class ParticipantBatchSampler(Sampler[list[int]]):
    def __init__(self, dataset: WindowDataset, batch_size: int):
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.groups: dict[str, list[int]] = {}
        for index, record in enumerate(dataset.records):
            self.groups.setdefault(record.participant, []).append(index)
        self.batch_size = batch_size

    def __iter__(self):
        for participant in sorted(self.groups):
            indices = self.groups[participant]
            for start in range(0, len(indices), self.batch_size):
                yield indices[start : start + self.batch_size]

    def __len__(self):
        return sum(
            (len(indices) + self.batch_size - 1) // self.batch_size
            for indices in self.groups.values()
        )
