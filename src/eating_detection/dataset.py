from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset, Sampler

from .io import iter_sensor_chunks
from .labels import label_window
from .preprocess import imu_features, resample_uniform
from .timebase import canonicalize_stream, infer_rate_hz, interpolate_uniform


@dataclass(frozen=True)
class WindowRecord:
    participant: str
    start_ms: int
    end_ms: int
    features: torch.Tensor
    label: float
    loss_mask: bool = True


def make_window_records(
    participant: str,
    start_ms: int,
    sample_hz: float,
    features: torch.Tensor,
    intervals: list[tuple[int, int]],
    window_sec: float,
    step_sec: float,
    positive_overlap: float,
    boundary_mode: str,
) -> list[WindowRecord]:
    if sample_hz <= 0 or window_sec <= 0 or step_sec <= 0:
        raise ValueError("sample_hz, window_sec, and step_sec must be positive")
    if step_sec > window_sec:
        raise ValueError("step_sec must not exceed window_sec")
    if features.ndim != 2:
        raise ValueError("features must have shape (channels, time)")
    window_samples = max(1, int(round(window_sec * sample_hz)))
    step_samples = max(1, int(round(step_sec * sample_hz)))
    records = []
    for offset in range(0, features.shape[1] - window_samples + 1, step_samples):
        window_start = int(round(start_ms + offset * 1000.0 / sample_hz))
        window_end = int(round(window_start + window_samples * 1000.0 / sample_hz))
        label = label_window(
            (window_start, window_end), intervals, positive_overlap, boundary_mode
        )
        records.append(
            WindowRecord(
                participant=participant,
                start_ms=window_start,
                end_ms=window_end,
                features=features[:, offset : offset + window_samples].clone(),
                label=0.0 if label is None else float(label),
                loss_mask=label is not None,
            )
        )
    return records


def participant_from_sensor_path(path: Path) -> str:
    parts = list(Path(path).parts)
    lowered = [part.casefold() for part in parts]
    if "organized" in lowered:
        index = lowered.index("organized")
        if index + 1 < len(parts):
            return parts[index + 1].replace(" ", "").casefold()
    return Path(path).parent.name.replace(" ", "").casefold()


def _read_sensor_file(
    path: Path, max_rows: int | None, chunksize: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    timestamps = []
    acc = []
    gyro = []
    acc_valid = []
    gyro_valid = []
    for chunk in iter_sensor_chunks(path, chunksize=chunksize):
        take = len(chunk.acc) if max_rows is None else min(len(chunk.acc), max_rows - sum(map(len, acc)))
        if take <= 0:
            break
        timestamps.append(chunk.timestamp_ms[:take])
        acc.append(chunk.acc[:take])
        gyro.append(chunk.gyro[:take])
        acc_valid.append(chunk.acc_valid[:take])
        gyro_valid.append(chunk.gyro_valid[:take])
        if max_rows is not None and sum(map(len, acc)) >= max_rows:
            break
    if not acc:
        raise ValueError("sensor file has no rows in the requested limit")
    timestamp_array = np.concatenate(timestamps, axis=0)
    return (
        timestamp_array[:, 0],
        timestamp_array[:, 1],
        timestamp_array[:, 2],
        np.concatenate(acc, axis=0),
        np.concatenate(gyro, axis=0),
        np.concatenate(acc_valid, axis=0),
        np.concatenate(gyro_valid, axis=0),
    )


def build_records_from_sensor_file(
    path: Path,
    intervals: list[tuple[int, int]],
    resample_hz: int,
    window_sec: float,
    step_sec: float,
    positive_overlap: float,
    boundary_mode: str,
    max_rows: int | None = None,
    chunksize: int = 50_000,
    max_gap_ms: int = 2_000,
) -> list[WindowRecord]:
    acc_time, _, gyro_time, acc, gyro, _, _ = _read_sensor_file(
        path, max_rows=max_rows, chunksize=chunksize
    )
    acc_stream = canonicalize_stream(acc_time, acc)
    gyro_stream = canonicalize_stream(gyro_time, gyro)
    acc_hz = infer_rate_hz(acc_stream.timestamps_ms)
    gyro_hz = infer_rate_hz(gyro_stream.timestamps_ms)
    source_hz = max(acc_hz, gyro_hz)
    start_ms = max(acc_stream.timestamps_ms[0], gyro_stream.timestamps_ms[0])
    end_ms = min(acc_stream.timestamps_ms[-1], gyro_stream.timestamps_ms[-1])
    if end_ms <= start_ms:
        raise ValueError("ACC and GYRO streams have no overlapping time range")

    grid, acc_uniform, acc_mask = interpolate_uniform(
        acc_stream, source_hz, start_ms, end_ms, max_gap_ms
    )
    gyro_grid, gyro_uniform, gyro_mask = interpolate_uniform(
        gyro_stream, source_hz, start_ms, end_ms, max_gap_ms
    )
    if not np.array_equal(grid, gyro_grid):
        raise ValueError("aligned streams produced different time grids")
    features, mask = imu_features(acc_uniform, gyro_uniform, acc_mask, gyro_mask)
    resampled_features = resample_uniform(features, source_hz, resample_hz)
    resampled_mask = resample_uniform(mask.astype(np.float32), source_hz, resample_hz) > 0.5
    length = min(len(resampled_features), len(resampled_mask))
    feature_tensor = torch.from_numpy(
        np.vstack(
            [resampled_features[:length].T, resampled_mask[:length].astype(np.float32).T]
        ).astype(np.float32)
    )
    return make_window_records(
        participant=participant_from_sensor_path(path),
        start_ms=int(start_ms),
        sample_hz=resample_hz,
        features=feature_tensor,
        intervals=intervals,
        window_sec=window_sec,
        step_sec=step_sec,
        positive_overlap=positive_overlap,
        boundary_mode=boundary_mode,
    )


def build_records_from_sensor_files(
    paths: list[Path],
    meal_intervals: dict[str, list[tuple[int, int]]],
    resample_hz: int,
    window_sec: float,
    step_sec: float,
    positive_overlap: float,
    boundary_mode: str,
    max_rows: int | None = None,
    chunksize: int = 50_000,
) -> tuple[list[WindowRecord], list[dict[str, str]]]:
    records: list[WindowRecord] = []
    issues: list[dict[str, str]] = []
    for path in paths:
        participant = participant_from_sensor_path(path)
        try:
            records.extend(
                build_records_from_sensor_file(
                    path,
                    intervals=meal_intervals.get(participant, []),
                    resample_hz=resample_hz,
                    window_sec=window_sec,
                    step_sec=step_sec,
                    positive_overlap=positive_overlap,
                    boundary_mode=boundary_mode,
                    max_rows=max_rows,
                    chunksize=chunksize,
                )
            )
        except (OSError, ValueError) as exc:
            issues.append({"path": str(path), "reason": str(exc)})
    return records, issues


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
