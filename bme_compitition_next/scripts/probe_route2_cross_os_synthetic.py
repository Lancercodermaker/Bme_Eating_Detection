"""No-project-data numerical parity probe for the Route 2 A2 runtime.

Run this file with the pinned Windows and WSL CPython environments.  It
constructs every row in memory, fits only a deterministic synthetic HGB model,
and emits hashes of feature, score, decode, and metric results.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import platform
import sys
import sysconfig
from pathlib import Path

import numpy as np
import scipy
import sklearn

from eating_event.a1.events import A1Candidate, decode_candidates
from eating_event.a1.metrics import (
    PredictionRecord,
    TruthRecord,
    evaluate_participants,
)
from eating_event.a1.scoring import fit_verifier_estimator, predict_scores
from eating_event.metrics import EventInterval
from eating_event.route2_candidate_overlap.candidates import Candidate, SupportWindow
from eating_event.route2_candidate_overlap.features import (
    ContextWindow,
    build_26d,
    build_source_16d,
)
from eating_event.route2_candidate_overlap.stage_b import StageBAdapter


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _synthetic_features() -> tuple[bytes, bytes]:
    role = "candidate/o1/outer"
    participant = "synthetic-p0"
    record = "record-0"
    session = "session-0"
    component = "component-0"
    start_ms, end_ms = 3_600_000, 4_200_000
    support = tuple(
        SupportWindow(
            role_id=role,
            participant_id=participant,
            record_id=record,
            session_id=session,
            component_id=component,
            global_index=index,
            row_index=index,
            start_ms=start_ms + index * 60_000,
            end_ms=start_ms + (index + 1) * 60_000,
            relative=value,
            coverage=coverage,
        )
        for index, (value, coverage) in enumerate(
            ((-0.25, 0.8), (0.5, 0.9), (1.25, 1.0))
        )
    )
    source_16d = build_source_16d(support, start_ms=start_ms, end_ms=end_ms)
    candidate = Candidate(
        role_id=role,
        participant_id=participant,
        record_id=record,
        session_id=session,
        component_id=component,
        start_ms=start_ms,
        end_ms=end_ms,
        support_indices=(0, 1, 2),
        source_16d=tuple(map(float, source_16d)),
    )
    context = tuple(
        ContextWindow(
            role_id=role,
            component_id=component,
            global_index=index + 10,
            start_ms=midpoint - 30_000,
            end_ms=midpoint + 30_000,
            relative=value,
        )
        for index, (midpoint, value) in enumerate(
            (
                (3_300_000, -0.5),
                (3_600_000, 0.25),
                (3_660_000, 0.75),
                (4_200_000, -0.25),
                (4_500_000, 0.125),
            )
        )
    )
    full_26d = build_26d(candidate, context)
    return source_16d.astype("<f8", copy=False).tobytes(), full_26d.astype("<f4", copy=False).tobytes()


def _synthetic_model() -> tuple[bytes, tuple[float, ...], int]:
    features = np.asarray(
        [
            [(((row * 19 + column * 11 + row * column * 3) % 97) - 48) / 16]
            for row in range(200)
            for column in range(26)
        ],
        dtype=np.float32,
    ).reshape(200, 26)
    labels = np.asarray([int((row * 7) % 13 < 6) for row in range(200)], dtype=np.int8)
    participants = tuple(f"synthetic-p{row // 20:02d}" for row in range(200))
    estimator = fit_verifier_estimator(
        features,
        labels,
        participants,
        positive_weight=3.0,
        random_state=20260910,
        max_iter=100,
    )
    scores = predict_scores(estimator, features)
    return (
        scores.astype("<f8", copy=False).tobytes(),
        tuple(map(float, scores)),
        int(estimator.max_iter),
    )


def _synthetic_decode_and_metrics(scores: tuple[float, ...]) -> tuple[str, str, int]:
    candidates = tuple(
        A1Candidate(
            candidate_id=f"synthetic-candidate-{index:03d}",
            participant_id=f"synthetic-p{index // 4:02d}",
            record_id="record-0",
            session_id="session-0",
            component_id=f"component-{index:03d}",
            interval=EventInterval(index * 1_000_000, index * 1_000_000 + 600_000),
            features=np.asarray([((index + column * 3) % 17) / 16 for column in range(16)]),
            support_indices=(),
        )
        for index in range(40)
    )
    decoded = decode_candidates(
        candidates,
        scores[:40],
        threshold=0.5,
        min_duration_ms=180_000,
        decode_fuse_gap_ms=600_000,
    )
    predictions = tuple(
        PredictionRecord(
            prediction_id=item.identity.stable_id,
            participant_id=item.identity.participant_id,
            record_id=item.identity.record_id,
            session_id=item.identity.session_id,
            source_segment_id=None,
            interval=item.interval,
        )
        for item in decoded
    )
    truths = tuple(
        TruthRecord(
            event_id=f"synthetic-p{participant:02d}:event-{event}",
            participant_id=f"synthetic-p{participant:02d}",
            interval=EventInterval(participant * 4_000_000 + event * 1_000_000,
                                  participant * 4_000_000 + event * 1_000_000 + 500_000),
        )
        for participant in range(10)
        for event in range(2)
    )
    metric = evaluate_participants(
        predictions,
        truths,
        participant_ids=tuple(f"synthetic-p{index:02d}" for index in range(10)),
    )
    decoded_payload = [
        {
            "identity": asdict(item.identity),
            "interval": asdict(item.interval),
            "source_candidate_ids": item.source_candidate_ids,
        }
        for item in decoded
    ]
    return _digest(_canonical(decoded_payload)), _digest(_canonical(asdict(metric))), len(decoded)


def _synthetic_pooled_reduction() -> str:
    participant_ids = tuple(f"pooled-p{index:02d}" for index in range(41))
    predictions: list[PredictionRecord] = []
    truths: list[TruthRecord] = []
    for participant_index, participant in enumerate(participant_ids):
        for index in range(participant_index % 4):
            start = participant_index * 100_000 + index * 2_000
            predictions.append(PredictionRecord(
                f"{participant}:{index}", participant, "r", "s", None,
                EventInterval(start, start + 1_000 + (index * 250)),
            ))
        for index in range((participant_index * 3) % 4):
            start = participant_index * 100_000 + index * 2_000 + (index % 2) * 100
            truths.append(TruthRecord(
                f"{participant}:truth-{index}", participant,
                EventInterval(start, start + 1_000 + (index * 250)),
            ))
    folds = tuple(
        evaluate_participants(
            tuple(item for item in predictions if item.participant_id in group),
            tuple(item for item in truths if item.participant_id in group),
            participant_ids=group,
        )
        for group in (
            participant_ids[0:8], participant_ids[8:16], participant_ids[16:24],
            participant_ids[24:32], participant_ids[32:41],
        )
    )
    expected = evaluate_participants(predictions, truths, participant_ids=participant_ids)
    actual = StageBAdapter._pooled_from_disjoint_folds(folds, participant_ids)
    if actual != expected:
        raise AssertionError("synthetic pooled fold reduction differs from the direct A1 evaluator")
    return _digest(_canonical(asdict(actual)))


def build_payload() -> dict[str, object]:
    source_16d, full_26d = _synthetic_features()
    score_bytes, scores, fit_max_iter = _synthetic_model()
    decoded_sha, metric_sha, decoded_count = _synthetic_decode_and_metrics(scores)
    return {
        "probe": "route2-cross-os-synthetic-v1",
        "project_data_used": False,
        "runtime": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "soabi": sysconfig.get_config_var("SOABI"),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "fit_parameters": {
            "positive_weight": 3.0,
            "random_state": 20260910,
            "max_iter": fit_max_iter,
        },
        "stage_b_sha256": _digest(
            Path(sys.modules[StageBAdapter.__module__].__file__).read_bytes()
        ),
        "numeric": {
            "source_16d_sha256": _digest(source_16d),
            "feature_26d_sha256": _digest(full_26d),
            "verifier_probability_f64le_sha256": _digest(score_bytes),
            "verifier_probability_f64_hex": [value.hex() for value in scores],
            "decoded_predictions_sha256": decoded_sha,
            "event_metric_sha256": metric_sha,
            "decoded_count": decoded_count,
            "pooled_fold_reduction_sha256": _synthetic_pooled_reduction(),
        },
    }


def main() -> None:
    payload = build_payload()
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    main()
