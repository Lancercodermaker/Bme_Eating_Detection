from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterator

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SensorChunk:
    timestamp_ms: np.ndarray
    acc: np.ndarray
    gyro: np.ndarray
    ppg: np.ndarray
    acc_valid: np.ndarray
    gyro_valid: np.ndarray
    ppg_valid: np.ndarray


def canonical_participant_id(raw: str) -> str:
    return re.sub(r"\s+", "", str(raw).strip().casefold())


def discover_participant_aliases(train_dir: Path) -> dict[str, str]:
    root = Path(train_dir)
    organized = root / "organized"
    if organized.is_dir():
        root = organized
    if not root.is_dir():
        raise FileNotFoundError(f"sensor directory does not exist: {root}")
    aliases = {}
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name.casefold() != "_unmapped_":
            aliases[child.name] = canonical_participant_id(child.name)
    return aliases


def read_meal_participant_aliases(index_dir: Path) -> dict[str, str]:
    candidates = sorted(Path(index_dir).glob("*mealinfo*.csv"))
    if not candidates:
        raise FileNotFoundError(f"meal metadata CSV not found in {index_dir}")
    frame = pd.read_csv(candidates[0], usecols=["externalid"], dtype={"externalid": "string"})
    aliases = {}
    for raw in frame["externalid"].dropna().astype(str):
        aliases[raw] = canonical_participant_id(raw)
    return aliases


def read_meal_intervals(
    index_dir: Path,
) -> tuple[dict[str, list[tuple[int, int]]], dict[str, int]]:
    from .labels import clean_interval

    candidates = sorted(Path(index_dir).glob("*mealinfo*.csv"))
    if not candidates:
        raise FileNotFoundError(f"meal metadata CSV not found in {index_dir}")
    frame = pd.read_csv(
        candidates[0],
        usecols=["externalid", "beforeTime", "afterTime"],
        dtype={"externalid": "string", "beforeTime": "Int64", "afterTime": "Int64"},
    )
    intervals: dict[str, list[tuple[int, int]]] = {}
    report = {
        "ok": 0,
        "missing_endpoint": 0,
        "reversed_swapped": 0,
        "zero_duration_excluded": 0,
        "outside_sensor_coverage": 0,
        "clipped_to_coverage": 0,
    }
    for row in frame.itertuples(index=False):
        participant = canonical_participant_id(row.externalid)
        start = None if pd.isna(row.beforeTime) else int(row.beforeTime)
        end = None if pd.isna(row.afterTime) else int(row.afterTime)
        interval, reason = clean_interval(start, end, (0, 10**18))
        report[reason] += 1
        if interval is not None:
            intervals.setdefault(participant, []).append(interval)
    return intervals, report


def iter_sensor_chunks(path: Path, chunksize: int = 50_000) -> Iterator[SensorChunk]:
    ppg_cols = [f"PPG{i}" for i in range(1, 45)]
    usecols = [
        "ACC_TIME",
        "PPG_TIME",
        "GYRO_TIME",
        *ppg_cols,
        "ACC_X",
        "ACC_Y",
        "ACC_Z",
        "GYRO_X",
        "GYRO_Y",
        "GYRO_Z",
    ]
    numeric = {col: "float32" for col in usecols if not col.endswith("_TIME")}
    numeric.update({"ACC_TIME": "Int64", "PPG_TIME": "Int64", "GYRO_TIME": "Int64"})
    for frame in pd.read_csv(
        path,
        sep="\t",
        usecols=usecols,
        dtype=numeric,
        chunksize=chunksize,
    ):
        acc_time = frame["ACC_TIME"].fillna(0).to_numpy(np.int64)
        ppg_time = frame["PPG_TIME"].fillna(0).to_numpy(np.int64)
        gyro_time = frame["GYRO_TIME"].fillna(0).to_numpy(np.int64)
        acc = frame[["ACC_X", "ACC_Y", "ACC_Z"]].to_numpy(np.float32)
        gyro = frame[["GYRO_X", "GYRO_Y", "GYRO_Z"]].to_numpy(np.float32)
        ppg = frame[ppg_cols].to_numpy(np.float32)
        acc_valid = (acc_time > 0) & np.isfinite(acc).all(axis=1)
        gyro_valid = (gyro_time > 0) & np.isfinite(gyro).all(axis=1)
        ppg_valid = (
            (ppg_time > 0)
            & np.isfinite(ppg).all(axis=1)
            & (np.abs(ppg).sum(axis=1) > 0)
        )
        yield SensorChunk(
            timestamp_ms=np.column_stack([acc_time, ppg_time, gyro_time]),
            acc=acc,
            gyro=gyro,
            ppg=ppg,
            acc_valid=acc_valid,
            gyro_valid=gyro_valid,
            ppg_valid=ppg_valid,
        )
