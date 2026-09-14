"""Formal high-recall candidate coverage gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from eating_event.metrics import EventInterval, interval_iou


G1_CANDIDATE_QUANTILE_GRID = (0.70, 0.80, 0.90)
G1_CANDIDATE_FUSE_GAP_MS = 300_000
G1_COVERAGE_THRESHOLD = 0.90


@dataclass(frozen=True)
class CoverageRunConfig:
    formal: bool = False
    max_files_per_participant: int | None = None
    outer_folds: int = 5
    selection_seed: int = 20260910

    def __post_init__(self) -> None:
        if self.formal and self.max_files_per_participant is not None:
            raise ValueError("formal coverage cannot use max-files-per-participant")
        if self.outer_folds < 2:
            raise ValueError("outer_folds must be at least 2")


@dataclass(frozen=True)
class QuantileResult:
    quantile: float
    pooled_recall: float
    worst_participant_recall: float
    candidate_count: int


def select_candidate_quantile(results: Sequence[QuantileResult]) -> QuantileResult:
    if not results:
        raise ValueError("candidate quantile selection needs results")
    if any(result.quantile not in G1_CANDIDATE_QUANTILE_GRID for result in results):
        raise ValueError("candidate quantile is outside the frozen G1 grid")
    return max(
        results,
        key=lambda result: (
            result.pooled_recall,
            result.worst_participant_recall,
            -result.candidate_count,
            result.quantile,
        ),
    )


@dataclass(frozen=True)
class FoldCoverageResult:
    fold_id: str
    pooled_recall: float
    participant_recall: Mapping[str, float]
    selected_quantile: float | None = None
    candidate_count: int = 0


@dataclass(frozen=True)
class CandidateCoverageReport:
    gate_id: str
    fold_results: tuple[FoldCoverageResult, ...]
    result: str = "pass"
    failure_class: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "result": self.result,
            "failure_class": self.failure_class,
            "fold_results": [asdict(result) for result in self.fold_results],
        }


def _truth_covered(predictions: Sequence[EventInterval], truths: Sequence[EventInterval]) -> tuple[int, int]:
    covered = sum(1 for truth in truths if any(interval_iou(prediction, truth) > 0.25 for prediction in predictions))
    return covered, len(truths)


def evaluate_candidate_coverage(
    predictions_by_participant: Mapping[str, Sequence[EventInterval]],
    truths_by_participant: Mapping[str, Sequence[EventInterval]],
) -> tuple[float, dict[str, float]]:
    participant_recall: dict[str, float] = {}
    total_covered = 0
    total_truths = 0
    for participant in sorted(truths_by_participant):
        covered, truth_count = _truth_covered(
            predictions_by_participant.get(participant, ()),
            truths_by_participant[participant],
        )
        participant_recall[participant] = covered / truth_count if truth_count else 1.0
        total_covered += covered
        total_truths += truth_count
    pooled = total_covered / total_truths if total_truths else 1.0
    return pooled, participant_recall


def write_coverage_reports(
    report: CandidateCoverageReport,
    *,
    output: str | Path,
    by_fold: str | Path,
    by_participant: str | Path,
) -> None:
    payload = report.to_dict()
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    Path(by_fold).expanduser().resolve().write_text(
        json.dumps(payload["fold_results"], indent=2), encoding="utf-8"
    )
    participant_rows = []
    for fold in report.fold_results:
        for participant, recall in fold.participant_recall.items():
            participant_rows.append({"fold_id": fold.fold_id, "participant_id": participant, "recall": recall})
    Path(by_participant).expanduser().resolve().write_text(
        json.dumps(participant_rows, indent=2), encoding="utf-8"
    )
