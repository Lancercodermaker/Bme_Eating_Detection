"""Explicit proposed Route2 numeric contract and pure transcript comparison.

The tolerances below are a NEW proposal, not an earlier owner decision and not
inferred from revision-g errors. Even bitwise matches remain unaccepted until
this exact policy is frozen by owner decision and independent protocol review.
No model, candidate reconstruction, decoder, evaluator or GT reader runs here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import struct
from typing import Mapping

from .capacity_plan import EvidenceRef, content_sha256
from .capacity_validation import EvidenceVerifier

_CATEGORIES = {
    "source16d": ("float64", 16, "feature"),
    "features26d": ("float32", 26, "feature"),
    "probabilities": ("float64", 1, "probability"),
    "metric_rates": ("float64", 4, "precision,recall,F1,long_FP_fraction"),
    "metric_mae_ms": ("float64", 2, "start_ms,end_ms"),
}

EXACT_FIELDS = (
    "positive_window_masks", "window_and_component_order", "candidate_intervals_and_support",
    "candidate_labels_and_eligibility_commitments", "nested_role_order_and_participants",
    "decoder_threshold_masks", "decoded_prediction_order_intervals_and_sources",
    "matcher_priority_order_and_pairs", "inner_threshold_rank_and_selected_thresholds",
    "participant_fold_pooled_counts_and_error_sums", "quality_gate_decisions",
    "null_masks", "call_counts", "stage_a_gt_reads", "pooled_gt_reads",
)

# These rules follow the original source predicates/order, without epsilon,
# rounding, threshold snapping or a replacement tie key. Decisions and full
# order transcripts must be identical even when continuous values are close.
EXACT_RULES = (
    "Positive relative >= 0; finite values only; no tolerance at zero.",
    "Window/component order uses frozen identity groups then (start_ms,end_ms,original_index).",
    "Reference joins next.start_ms <= current_end_ms+300000; treatment joins next.start_ms < current_end_ms.",
    "Half-open integer-ms intervals, role-qualified support IDs, labels and nulls match exactly.",
    "Candidate label/matcher IoU > 0.25; threshold admission uses its original strict comparison.",
    "Decoder score >= threshold; thresholds exactly binary64 0.10/0.25/0.50; duration >=180000ms before fusion.",
    "Decoder order is (participant_id,component_id,start_ms,original_index); same identity fusion start<=end+600000ms.",
    "Matcher predictions/truths sort by prediction_id/event_id; edges sort (-IoU,p_index,t_index); greedy pairs/order exact.",
    "Inner selection maximizes (F1 or -1 for null,-FP,threshold); higher threshold wins exact final ties.",
    "Pooled reduction sorts disjoint participants by ID, sums TP/FP/FN and matched-error sums/count; no fold averaging.",
    "G3: >=20 positive candidates, >=5 positive participants and both classes; admission decision exact.",
    "Numeric F1 gates >=0.66/>=0.80; stage >=3/5 folds F1>=0.66, each long-FP<=0.25 and both MAE<=900000ms; nulls preserved.",
    "All branch predicates, ranking comparisons and tie outcomes must match exactly; epsilon is never used by production decisions.",
    "Aggregate contract v2 requires a full 5x4 role/metric layout and recomputes quality gates, selection tuples/ranking and every block's null mask from actual metric/score records.",
)

AGGREGATE_CONTRACT = "route2_numeric_aggregate_contract_v2"
_COUNT_FIELDS = (
    "tp", "fp", "fn", "matched_count", "long_fp_count", "eligible_gt_count",
    "prediction_count", "start_abs_error_sum_ms", "end_abs_error_sum_ms",
)


@dataclass(frozen=True)
class Tolerance:
    category: str
    absolute: float = 1e-12
    relative: float = 1e-10


@dataclass(frozen=True)
class NumericPolicy:
    schema: str = "route2_numeric_equivalence_proposal_v1"
    status: str = "PROPOSED_NOT_OWNER_APPROVED"
    rule: str = "abs(left-right) <= absolute + relative * max(abs(left),abs(right))"
    tolerances: tuple[Tolerance, ...] = tuple(Tolerance(category) for category in _CATEGORIES)
    exact_rules: tuple[str, ...] = EXACT_RULES
    exact_fields: tuple[str, ...] = EXACT_FIELDS
    rounding_before_comparison: bool = False
    nonfinite_allowed: bool = False
    null_masks_exact: bool = True
    aggregate_contract: str = AGGREGATE_CONTRACT

    @property
    def sha256(self) -> str:
        return content_sha256(asdict(self))

    def review_content(self) -> dict:
        return {"policy": asdict(self), "policy_sha256": self.sha256,
                "units": {category: spec[2] for category, spec in _CATEGORIES.items()},
                "threshold_hex": tuple(float(value).hex() for value in (0.1, 0.25, 0.5)),
                "on_decision_disagreement": "FAIL even if every continuous error meets tolerance",
                "on_missing_freeze_or_full_coverage": "FAIL_CLOSED",
                "aggregate_schemas": {
                    "layout": "five SelectionScope records: outer role, four inner roles, three ordered threshold/metric pairs, outer metric; one pooled metric",
                    "counts": {"aggregate": _COUNT_FIELDS, "participant_order": "sorted participant IDs",
                               "participant_counts": "one complete count/error record per participant"},
                    "ranking": {"selection_tuples": "three metric_id/negative_fp/threshold_hex records; F1 comes from metric_rates column 2",
                                "ranked_thresholds_hex": "descending exact (F1 or -1,-FP,threshold) order",
                                "selected_threshold_hex": "maximum selection tuple's threshold"},
                    "quality": "five outer-role records and pooled study record with recomputed typed predicates",
                    "null_masks": "one complete category/role/shape/row_ids/null_mask record for every continuous block",
                },
                "experiment_authorized": False}


@dataclass(frozen=True)
class ContinuousBlock:
    category: str
    role_or_metric_id: str
    dtype: str
    unit: str
    shape: tuple[int, int]
    row_ids: tuple[str, ...]
    # Flattened in row-major order; None is legal only for metrics and must
    # agree exactly at every index. No NaN stands in for an absent metric.
    values: tuple[float | None, ...]


@dataclass(frozen=True)
class SelectionScope:
    outer_role_id: str
    inner_verifier_role_ids: tuple[str, ...]
    threshold_metric_ids: tuple[tuple[str, str], ...]
    outer_metric_id: str


@dataclass(frozen=True)
class AggregateLayout:
    """Explicit frozen coverage; metric names/order alone cannot infer roles."""

    outer_scopes: tuple[SelectionScope, ...]
    pooled_metric_id: str


@dataclass(frozen=True)
class EquivalenceTranscript:
    scope: str
    platform: str
    source_sha256: str
    protocol_sha256: str
    input_manifest_sha256: str
    runtime_manifest_sha256: str
    candidate_role_ids: tuple[str, ...]
    verifier_role_ids: tuple[str, ...]
    metric_ids: tuple[str, ...]
    exact: Mapping[str, object]
    continuous: tuple[ContinuousBlock, ...]
    aggregate_layout: AggregateLayout | None = None

    @property
    def sha256(self) -> str:
        return content_sha256(asdict(self))


@dataclass(frozen=True)
class FrozenPolicyReview:
    policy_sha256: str
    source_sha256: str
    protocol_sha256: str
    input_manifest_sha256: str
    windows_runtime_manifest_sha256: str
    linux_runtime_manifest_sha256: str
    owner_decision: EvidenceRef
    independent_review: EvidenceRef


@dataclass(frozen=True)
class NumericIssue:
    code: str
    subject: str
    detail: str


@dataclass(frozen=True)
class BlockComparison:
    category: str
    role_or_metric_id: str
    finite_pairs: int
    bitwise_equal_pairs: int
    null_pairs: int
    max_absolute_error: float | None
    max_relative_error: float | None
    rms_error: float | None
    out_of_tolerance: int
    first_bad_indices: tuple[int, ...]


@dataclass(frozen=True)
class EquivalenceReport:
    policy_sha256: str
    status: str
    accepted: bool
    proposed_comparison_matches: bool
    blocks: tuple[BlockComparison, ...]
    issues: tuple[NumericIssue, ...]
    experiment_authorized: bool = False


def _sha(value):
    return (type(value) is str and len(value) == 64 and value != "0" * 64
            and all(character in "0123456789abcdef" for character in value))


def _exact_bytes(value):
    def validate(item):
        if item is None or type(item) in {str, bool, int}:
            return
        if type(item) in {list, tuple}:
            for child in item:
                validate(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                validate(child)
            return
        raise ValueError("Exact transcript permits only typed discrete JSON; float thresholds use exact hex strings")
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _unique_ids(values, count):
    return (type(values) is tuple and len(values) == count
            and all(type(value) is str and bool(value) for value in values)
            and len(set(values)) == count)


def _scope_records(transcript, field, expected_ids):
    """Require every named scope in frozen order, with no generic aggregate."""
    record = transcript.exact[field]
    if (type(record) is not dict or set(record) != {"complete", "scope_ids", "records"}
            or record["complete"] is not True or type(record["records"]) is not dict
            or type(record["scope_ids"]) not in {tuple, list}
            or tuple(record["scope_ids"]) != tuple(expected_ids)
            or set(record["records"]) != set(expected_ids)):
        raise ValueError(f"{field}: complete records for each required scope in frozen order are mandatory")
    return record["records"]


def _aggregate_layout(transcript):
    layout = transcript.aggregate_layout
    if (not isinstance(layout, AggregateLayout) or type(layout.outer_scopes) is not tuple
            or len(layout.outer_scopes) != 5 or type(layout.pooled_metric_id) is not str
            or not layout.pooled_metric_id):
        raise ValueError("aggregate_layout: five explicit outer scopes and one pooled metric required")
    outer_roles, inner_roles, metric_ids = [], [], [layout.pooled_metric_id]
    allowed = tuple(value.hex() for value in (0.1, 0.25, 0.5))
    for scope in layout.outer_scopes:
        if (not isinstance(scope, SelectionScope) or type(scope.outer_role_id) is not str or not scope.outer_role_id
                or not _unique_ids(scope.inner_verifier_role_ids, 4)
                or type(scope.outer_metric_id) is not str or not scope.outer_metric_id
                or type(scope.threshold_metric_ids) is not tuple or len(scope.threshold_metric_ids) != 3
                or any(type(pair) is not tuple or len(pair) != 2
                       or any(type(value) is not str or not value for value in pair)
                       for pair in scope.threshold_metric_ids)
                or tuple(pair[0] for pair in scope.threshold_metric_ids) != allowed):
            raise ValueError("aggregate_layout: each outer needs four inner roles, three ordered threshold metrics and its outer metric")
        outer_roles.append(scope.outer_role_id)
        inner_roles.extend(scope.inner_verifier_role_ids)
        metric_ids.extend(metric for _, metric in scope.threshold_metric_ids)
        metric_ids.append(scope.outer_metric_id)
    if (not _unique_ids(tuple(outer_roles), 5) or not _unique_ids(tuple(inner_roles), 20)
            or set(outer_roles) & set(inner_roles)
            or set(outer_roles + inner_roles) != set(transcript.verifier_role_ids)
            or not _unique_ids(tuple(metric_ids), 21) or set(metric_ids) != set(transcript.metric_ids)):
        raise ValueError("aggregate_layout: full disjoint 5x4 verifier coverage and exactly 15 inner + five outer + one pooled metrics required")
    return layout


def _count_values(record, subject):
    if (type(record) is not dict or set(record) != set(_COUNT_FIELDS)
            or any(type(value) is not int or value < 0 for value in record.values())):
        raise ValueError(f"{subject}: all count and integer-ms error-sum fields required, with exact integer types")
    if (record["matched_count"] != record["tp"] or record["long_fp_count"] > record["fp"]
            or record["eligible_gt_count"] != record["tp"] + record["fn"]
            or record["prediction_count"] != record["tp"] + record["fp"]
            or record["matched_count"] == 0 and (record["start_abs_error_sum_ms"] != 0 or record["end_abs_error_sum_ms"] != 0)):
        raise ValueError(f"{subject}: inconsistent TP/FP/FN, matched/GT/prediction counts or error sums")
    return record


def _full_count_record(record, subject):
    if (type(record) is not dict or set(record) != {"aggregate", "participant_order", "participant_counts"}
            or type(record["participant_counts"]) is not dict
            or type(record["participant_order"]) not in {tuple, list}
            or not record["participant_order"]
            or any(type(value) is not str or not value for value in record["participant_order"])
            or len(set(record["participant_order"])) != len(record["participant_order"])
            or tuple(record["participant_order"]) != tuple(sorted(record["participant_order"]))
            or set(record["participant_counts"]) != set(record["participant_order"])):
        raise ValueError(f"{subject}: aggregate and complete sorted per-participant count/error records required")
    aggregate = _count_values(record["aggregate"], subject)
    participants = {pid: _count_values(record["participant_counts"][pid], f"{subject}:{pid}")
                    for pid in record["participant_order"]}
    for field in _COUNT_FIELDS:
        if aggregate[field] != sum(item[field] for item in participants.values()):
            raise ValueError(f"{subject}: aggregate {field} differs from complete participant reduction")
    return aggregate, participants


def _validate_aggregate_records(transcript, block_map):
    """Derive decision inputs and predicates; caller assertions are compared.

    Continuous tolerances never enter these computations. If metric identity,
    count, layout or record schemas are missing, computation refuses the input.
    """
    layout = _aggregate_layout(transcript)
    outer_ids = tuple(scope.outer_role_id for scope in layout.outer_scopes)
    counts = _scope_records(transcript, "participant_fold_pooled_counts_and_error_sums", transcript.metric_ids)
    aggregate_counts, participant_counts = {}, {}
    for metric_id in transcript.metric_ids:
        aggregate_counts[metric_id], participant_counts[metric_id] = _full_count_record(counts[metric_id], metric_id)
        rates = block_map[("metric_rates", metric_id)].values
        errors = block_map[("metric_mae_ms", metric_id)].values
        summary = aggregate_counts[metric_id]
        # Aggregate precision/recall/long-FP use 0.0 for zero denominators.
        # F1 and MAE have their original distinct nullable semantics.
        if (any(rates[index] is None for index in (0, 1, 3))
                or (rates[2] is None) != (2 * summary["tp"] + summary["fp"] + summary["fn"] == 0)
                or any((value is None) != (summary["matched_count"] == 0) for value in errors)):
            raise ValueError(f"{metric_id}: metric nulls disagree with original aggregate count semantics")
        tp, fp, fn, matches = (summary[name] for name in ("tp", "fp", "fn", "matched_count"))
        expected_rates = (tp / (tp + fp) if tp + fp else 0.0,
                          tp / (tp + fn) if tp + fn else 0.0,
                          2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
                          summary["long_fp_count"] / fp if fp else 0.0)
        # Match A1's sorted participant-weighted arithmetic, including its
        # intermediate divisions. No epsilon may change decision inputs.
        expected_errors = tuple(
            sum((item[field] / item["matched_count"] if item["matched_count"] else 0.0)
                * item["matched_count"] for item in participant_counts[metric_id].values()) / matches
            if matches else None
            for field in ("start_abs_error_sum_ms", "end_abs_error_sum_ms"))
        if tuple(rates) != expected_rates or tuple(errors) != expected_errors:
            raise ValueError(f"{metric_id}: supplied metrics contradict exact counts or original weighted error sums")
    pooled_participants = participant_counts[layout.pooled_metric_id]
    if len(pooled_participants) != 41 or aggregate_counts[layout.pooled_metric_id]["eligible_gt_count"] != 234:
        raise ValueError("pooled: complete 41-participant/234-GT denominator required")
    folded_participants = {}
    for scope in layout.outer_scopes:
        fold = participant_counts[scope.outer_metric_id]
        if set(folded_participants) & set(fold):
            raise ValueError("outer folds: participant overlap is forbidden")
        folded_participants.update(fold)
        for _, metric_id in scope.threshold_metric_ids:
            if set(participant_counts[metric_id]) != set(pooled_participants) - set(fold):
                raise ValueError(f"{metric_id}: inner threshold metric must cover exactly this outer's training participants")
    if _exact_bytes(folded_participants) != _exact_bytes(pooled_participants):
        raise ValueError("pooled: per-participant counts/errors must be the exact disjoint outer-fold reduction")

    ranking = _scope_records(transcript, "inner_threshold_rank_and_selected_thresholds", outer_ids)
    masks = transcript.exact["decoder_threshold_masks"]["records"]
    allowed = tuple(value.hex() for value in (0.1, 0.25, 0.5))
    for scope in layout.outer_scopes:
        selection_inputs, selection_values = [], []
        for threshold_hex, metric_id in scope.threshold_metric_ids:
            f1 = block_map[("metric_rates", metric_id)].values[2]
            negative_fp = -aggregate_counts[metric_id]["fp"]
            selection_inputs.append({"metric_id": metric_id, "negative_fp": negative_fp, "threshold_hex": threshold_hex})
            # Match original max((F1 if non-null else -1.0, -FP, threshold)).
            selection_values.append((f1 if f1 is not None else -1.0, negative_fp, float.fromhex(threshold_hex)))
        ranked = tuple(item[2].hex() for item in sorted(selection_values, reverse=True))
        selected = max(selection_values)[2].hex()
        expected = {"selection_tuples": selection_inputs, "ranked_thresholds_hex": ranked,
                    "selected_threshold_hex": selected}
        if _exact_bytes(ranking[scope.outer_role_id]) != _exact_bytes(expected):
            raise ValueError(f"{scope.outer_role_id}: required selection input tuples, full exact ranking or selected threshold disagree with actual metric values")
        for inner_role in scope.inner_verifier_role_ids:
            if tuple(masks[inner_role]["thresholds_hex"]) != allowed:
                raise ValueError(f"{inner_role}: inner decoder coverage must use all three frozen thresholds")
        if tuple(masks[scope.outer_role_id]["thresholds_hex"]) != (selected,):
            raise ValueError(f"{scope.outer_role_id}: outer decoder threshold differs from recomputed inner selection")

    gates = _scope_records(transcript, "quality_gate_decisions", (*outer_ids, layout.pooled_metric_id))
    fold_predicates = []
    for scope in layout.outer_scopes:
        rates = block_map[("metric_rates", scope.outer_metric_id)].values
        start, end = block_map[("metric_mae_ms", scope.outer_metric_id)].values
        f1, long_fp = rates[2], rates[3]
        expected = {"metric_id": scope.outer_metric_id, "f1_present": f1 is not None,
                    "f1_minimum": f1 is not None and f1 >= 0.66,
                    "long_fp_within_limit": long_fp <= 0.25,
                    "start_mae_present": start is not None, "end_mae_present": end is not None,
                    "start_mae_within_limit": start is not None and start <= 900_000,
                    "end_mae_within_limit": end is not None and end <= 900_000}
        expected["quality_per_fold"] = bool(expected["long_fp_within_limit"]
            and expected["start_mae_within_limit"] and expected["end_mae_within_limit"])
        if _exact_bytes(gates[scope.outer_role_id]) != _exact_bytes(expected):
            raise ValueError(f"{scope.outer_role_id}: full typed fold gate record must equal the exact predicates from its actual metric values")
        fold_predicates.append(expected)
    pooled_f1 = block_map[("metric_rates", layout.pooled_metric_id)].values[2]
    present_count = sum(item["f1_present"] for item in fold_predicates)
    minimum_count = sum(item["f1_minimum"] for item in fold_predicates)
    majority = present_count == 5 and minimum_count >= 3
    quality = all(item["quality_per_fold"] for item in fold_predicates)
    minimum = pooled_f1 is not None and pooled_f1 >= 0.66
    ideal = pooled_f1 is not None and pooled_f1 >= 0.80
    expected = {"metric_id": layout.pooled_metric_id, "pooled_f1_present": pooled_f1 is not None,
                "complete_folds": 5, "fold_f1_present_count": present_count, "fold_minimum_count": minimum_count,
                "numeric_minimum": minimum, "numeric_ideal": ideal, "majority_folds": majority,
                "quality_per_fold": quality, "stage_minimum": bool(minimum and majority and quality),
                "stage_ideal": bool(ideal and majority and quality)}
    if _exact_bytes(gates[layout.pooled_metric_id]) != _exact_bytes(expected):
        raise ValueError("pooled: full typed study gate record must equal exact F1/majority/quality/stage predicates from actual metrics")

    null_scope_ids = tuple(sorted(f"{category}/{scope_id}" for category, scope_id in block_map))
    null_records = _scope_records(transcript, "null_masks", null_scope_ids)
    for (category, scope_id), block in block_map.items():
        expected = {"category": category, "role_or_metric_id": scope_id, "shape": block.shape,
                    "row_ids": block.row_ids, "null_mask": [value is None for value in block.values]}
        if _exact_bytes(null_records[f"{category}/{scope_id}"]) != _exact_bytes(expected):
            raise ValueError(f"{category}/{scope_id}: exact null-mask schema/content must match the complete actual block")


def _validate_transcript(transcript, issues):
    initial_issue_count = len(issues)
    subject = transcript.platform
    if (transcript.scope != "full_5x4_ab" or transcript.platform not in {"windows", "linux"}
            or not all(_sha(value) for value in (transcript.source_sha256, transcript.protocol_sha256,
                                                transcript.input_manifest_sha256, transcript.runtime_manifest_sha256))):
        issues.append(NumericIssue("TRANSCRIPT_IDENTITY", subject, "Full A+B scope and complete source/protocol/input/runtime hashes required; partial probe cannot qualify"))
    if (not _unique_ids(transcript.candidate_role_ids, 105) or not _unique_ids(transcript.verifier_role_ids, 25)
            or not _unique_ids(transcript.metric_ids, 21)):
        issues.append(NumericIssue("FULL_COVERAGE_MISSING", subject, "Need all 105 candidate, 25 verifier and 20+1 metric identities in frozen order"))
    try:
        if type(transcript.exact) is not dict or set(transcript.exact) != set(EXACT_FIELDS):
            raise ValueError("every exact field required once; unknown fields refused")
        _exact_bytes(transcript.exact)
        if any(transcript.exact[field] in (None, {}, [], ()) for field in EXACT_FIELDS
               if field not in {"stage_a_gt_reads", "pooled_gt_reads"}):
            raise ValueError("missing decision/order/count content")
        required_calls = {"reference_reconstructions": 105, "treatment_reconstructions": 105,
                          "candidate_fit": 0, "candidate_predict": 0, "verifier_fit": 25,
                          "verifier_predict": 25, "decoder": 65, "gt_evaluator": 20,
                          "pooled_reduction": 1}
        if _exact_bytes(transcript.exact["call_counts"]) != _exact_bytes(required_calls):
            raise ValueError("full COMPLETE call counts must equal frozen 105/105/25/25/65/20+1")
        if any(type(transcript.exact[field]) is not int or transcript.exact[field] != 0
               for field in ("stage_a_gt_reads", "pooled_gt_reads")):
            raise ValueError("Stage A and pooled GT reads must be exact integer zero")
        for field in EXACT_FIELDS:
            if field in {"call_counts", "stage_a_gt_reads", "pooled_gt_reads"}:
                continue
            record = transcript.exact[field]
            if (type(record) is not dict or set(record) != {"complete", "scope_ids", "records"}
                    or record["complete"] is not True or type(record["records"]) is not dict
                    or type(record["scope_ids"]) not in {tuple, list}
                    or set(record["scope_ids"]) != set(record["records"])):
                raise ValueError(f"{field} needs complete per-scope decision/order records")
            if len(record["scope_ids"]) != len(set(record["scope_ids"])):
                raise ValueError(f"{field} repeats a scope")
            # Every scope record may legitimately be empty (e.g. no positive
            # windows); the set of scopes itself must be exhaustive.
            if field in {"positive_window_masks", "window_and_component_order", "candidate_intervals_and_support",
                         "candidate_labels_and_eligibility_commitments"}:
                expected = set(transcript.candidate_role_ids)
            elif field in {"nested_role_order_and_participants", "decoder_threshold_masks",
                           "decoded_prediction_order_intervals_and_sources"}:
                expected = set(transcript.verifier_role_ids)
            elif field in {"matcher_priority_order_and_pairs", "participant_fold_pooled_counts_and_error_sums"}:
                expected = set(transcript.metric_ids)
            else:
                expected = None  # aggregate quality/null masks/threshold ranking
            if expected is not None and set(record["scope_ids"]) != expected:
                raise ValueError(f"{field} does not cover the full frozen role/metric set")
            if expected is None and not record["scope_ids"]:
                raise ValueError(f"{field} has no aggregate scopes")
    except (ValueError, TypeError) as exc:
        issues.append(NumericIssue("EXACT_CONTRACT_INVALID", subject, str(exc)))
    block_map = {}
    for block in transcript.continuous:
        if (type(block) is not ContinuousBlock
                or any(type(getattr(block, name)) is not str or not getattr(block, name)
                       for name in ("category", "role_or_metric_id", "dtype", "unit"))):
            issues.append(NumericIssue("BLOCK_SCHEMA", subject, "Exact continuous block type and string identities required"))
            continue
        key = (block.category, block.role_or_metric_id)
        spec = _CATEGORIES.get(block.category)
        if key in block_map:
            issues.append(NumericIssue("BLOCK_DUPLICATE", str(key), "A continuous block may occur only once"))
        block_map[key] = block
        valid = (spec is not None and block.dtype == spec[0] and block.unit == spec[2]
                  and type(block.shape) is tuple and len(block.shape) == 2
                  and all(type(value) is int and value >= 0 for value in block.shape)
                  and type(block.row_ids) is tuple and type(block.values) is tuple
                 and block.shape[1] == spec[1] and len(block.row_ids) == block.shape[0]
                  and all(type(value) is str and bool(value) for value in block.row_ids)
                  and len(set(block.row_ids)) == len(block.row_ids)
                 and len(block.values) == block.shape[0] * block.shape[1])
        if not valid:
            issues.append(NumericIssue("BLOCK_SCHEMA", str(key), "Exact category, dtype, units, row IDs and row-major dimensions required"))
            continue
        if block.category.startswith("metric_") and (block.shape[0] != 1 or block.row_ids != (block.role_or_metric_id,)):
            issues.append(NumericIssue("METRIC_ROW_MISSING", str(key), "Every metric identity requires exactly one non-vacuous summary row"))
        for value in block.values:
            if value is None:
                if not block.category.startswith("metric_"):
                    issues.append(NumericIssue("NULL_NOT_ALLOWED", str(key), "Only nullable metrics may contain None"))
                continue
            if type(value) is not float or not math.isfinite(value):
                issues.append(NumericIssue("NONFINITE_OR_TYPE", str(key), "Every non-null value must be a finite float"))
                break
            if block.dtype == "float32":
                try:
                    if struct.unpack("<f", struct.pack("<f", value))[0] != value:
                        raise ValueError("not an exact float32 value")
                except (OverflowError, ValueError):
                    issues.append(NumericIssue("DTYPE_VALUE", str(key), "Float32 transcript must preserve the actual float32 values, without decimal rounding"))
                    break
            if block.category == "probabilities" and not 0.0 <= value <= 1.0:
                issues.append(NumericIssue("PROBABILITY_RANGE", str(key), "Probabilities must lie in [0,1]"))
            if block.category == "metric_rates" and not 0.0 <= value <= 1.0:
                issues.append(NumericIssue("METRIC_RATE_RANGE", str(key), "Precision/recall/F1/long-FP must lie in [0,1]"))
            if block.category == "metric_mae_ms" and value < 0.0:
                issues.append(NumericIssue("METRIC_MAE_RANGE", str(key), "Boundary errors must be nonnegative milliseconds"))
    expected_keys = {(category, role) for category in ("source16d", "features26d") for role in transcript.candidate_role_ids}
    expected_keys |= {("probabilities", role) for role in transcript.verifier_role_ids}
    expected_keys |= {(category, metric) for category in ("metric_rates", "metric_mae_ms") for metric in transcript.metric_ids}
    if set(block_map) != expected_keys:
        issues.append(NumericIssue("CONTINUOUS_COVERAGE", subject, "Every candidate feature, prediction role and 20+1 metric block must be present; no unknown block allowed"))
    # Recompute all 65 score-threshold predicates directly from the supplied
    # probabilities. A caller cannot conceal a threshold crossing behind an
    # identical asserted mask. Duration/order/matcher traces remain exact data.
    try:
        masks = transcript.exact["decoder_threshold_masks"]["records"]
        counts = {1: 0, 3: 0}
        allowed = tuple(value.hex() for value in (0.1, 0.25, 0.5))
        for role in transcript.verifier_role_ids:
            record = masks[role]
            if type(record) is not dict or set(record) != {"thresholds_hex", "score_ge_threshold_masks"}:
                raise ValueError("each decoder role needs threshold hex values and score masks")
            thresholds = tuple(record["thresholds_hex"])
            if len(thresholds) not in counts or len(set(thresholds)) != len(thresholds):
                raise ValueError("inner roles use three thresholds; outer roles use one")
            if any(value not in allowed for value in thresholds) or (len(thresholds) == 3 and thresholds != allowed):
                raise ValueError("thresholds must match the frozen exact ordered set")
            counts[len(thresholds)] += 1
            probabilities = block_map[("probabilities", role)].values
            supplied = record["score_ge_threshold_masks"]
            expected = {value: [score >= float.fromhex(value) for score in probabilities] for value in thresholds}
            if _exact_bytes(supplied) != _exact_bytes(expected):
                raise ValueError("asserted threshold masks disagree with exact score comparisons")
        if counts != {1: 5, 3: 20}:
            raise ValueError("need 20 inner triple-threshold and five outer selected-threshold roles")
    except (KeyError, ValueError, TypeError) as exc:
        issues.append(NumericIssue("THRESHOLD_TRACE_INVALID", subject, str(exc)))
    if len(issues) == initial_issue_count:
        try:
            _validate_aggregate_records(transcript, block_map)
        except (KeyError, ValueError, TypeError, IndexError, OverflowError) as exc:
            issues.append(NumericIssue("AGGREGATE_CONTRACT_INVALID", subject, str(exc)))
    return block_map


def _reviewed_freeze(policy, frozen, verifier, left, right, issues):
    if frozen is None or verifier is None:
        issues.append(NumericIssue("POLICY_NOT_FROZEN", "numeric_policy", "Explicit owner decision and independent review of this exact policy/closure required"))
        return False
    binding = {"policy_sha256": policy.sha256, "source_sha256": left.source_sha256,
               "protocol_sha256": left.protocol_sha256, "input_manifest_sha256": left.input_manifest_sha256,
               "windows_runtime_manifest_sha256": left.runtime_manifest_sha256,
               "linux_runtime_manifest_sha256": right.runtime_manifest_sha256}
    if any(getattr(frozen, key) != value for key, value in binding.items()):
        issues.append(NumericIssue("FREEZE_BINDING", "numeric_policy", "Frozen policy/closure differs from these full-scope transcripts"))
        return False
    for reference, kind, origin in ((frozen.owner_decision, "numeric_policy_owner_decision", "owner_decision"),
                                    (frozen.independent_review, "numeric_policy_independent_review", "independent_review")):
        try:
            if (not isinstance(reference, EvidenceRef) or reference.kind != kind or reference.subject != policy.sha256
                    or not _sha(reference.sha256) or not reference.review_id or reference.review_id == "NOT_ISSUED"):
                raise ValueError("missing authentic numeric policy decision/review")
            raw = verifier.authenticated_bytes(reference)
            if type(raw) is not bytes or not 0 < len(raw) <= 8 << 20 or hashlib.sha256(raw).hexdigest() != reference.sha256:
                raise ValueError("authenticated receipt hash/size mismatch")
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate review key")
                    result[key] = value
                return result
            payload = json.loads(raw, object_pairs_hook=unique)
            claims = {**binding, "kind": kind, "subject": policy.sha256, "origin": origin,
                      "review_id": reference.review_id, "review_status": "PASS",
                      "policy_frozen_before_comparison": True, "full_scope": "full_5x4_ab",
                      "discrete_decisions_exact": True, "tolerances_explicitly_approved": True}
            if any(_exact_bytes(payload.get(key)) != _exact_bytes(value) for key, value in claims.items()):
                raise ValueError("numeric policy decision/review does not bind every required claim")
        except Exception as exc:
            issues.append(NumericIssue("FREEZE_EVIDENCE_INVALID", kind, f"Authenticated frozen review rejected: {type(exc).__name__}"))
            return False
    return True


def compare_transcripts(
    left: EquivalenceTranscript, right: EquivalenceTranscript, *,
    policy: NumericPolicy = NumericPolicy(), frozen: FrozenPolicyReview | None = None,
    verifier: EvidenceVerifier | None = None,
) -> EquivalenceReport:
    """Compare supplied transcripts, preserving strict policy acceptance gates.

    A successful calculation describes these bound transcripts only; authentic
    full-run provenance and full scientific protocol review remain separate.
    It never promotes revision-g PARTIAL_MATCH_ONLY to a complete result.
    """
    issues = []
    tolerance_map = {item.category: item for item in policy.tolerances}
    if (policy.schema != "route2_numeric_equivalence_proposal_v1" or policy.exact_rules != EXACT_RULES
            or policy.exact_fields != EXACT_FIELDS or policy.rounding_before_comparison is not False
            or policy.nonfinite_allowed is not False or policy.null_masks_exact is not True
            or policy.aggregate_contract != AGGREGATE_CONTRACT
            or policy.rule != NumericPolicy().rule or len(tolerance_map) != len(policy.tolerances)
            or set(tolerance_map) != set(_CATEGORIES)
            or any(type(value) is not float or not math.isfinite(value) or value < 0
                   for item in policy.tolerances for value in (item.absolute, item.relative))):
        return EquivalenceReport("UNAVAILABLE_INVALID_POLICY", "FAIL_CLOSED", False, False, (),
                                 (NumericIssue("POLICY_INVALID", "numeric_policy", "Complete finite tolerances and exact decision rules required"),))
    left_blocks = _validate_transcript(left, issues)
    right_blocks = _validate_transcript(right, issues)
    if left.platform != "windows" or right.platform != "linux":
        issues.append(NumericIssue("PLATFORM_PAIR", "transcripts", "Expected Windows then Linux with separately frozen runtime identities"))
    for field in ("source_sha256", "protocol_sha256", "input_manifest_sha256", "candidate_role_ids", "verifier_role_ids", "metric_ids", "aggregate_layout"):
        if getattr(left, field) != getattr(right, field):
            issues.append(NumericIssue("IDENTITY_OR_ORDER_CHANGED", field, "Identity/role order must match exactly"))
    try:
        if _exact_bytes(dict(left.exact)) != _exact_bytes(dict(right.exact)):
            issues.append(NumericIssue("DISCRETE_DECISION_CHANGED", "exact", "One or more masks, thresholds, rankings, intervals, matches, counts, gates or nulls differ"))
    except (ValueError, TypeError):
        pass  # Schema validation already supplies the actionable error.
    comparisons = []
    if not issues:
        for key in sorted(left_blocks):
            a, b = left_blocks[key], right_blocks[key]
            if (a.dtype, a.unit, a.shape, a.row_ids) != (b.dtype, b.unit, b.shape, b.row_ids):
                issues.append(NumericIssue("CONTINUOUS_ALIGNMENT", str(key), "Dimensions, dtype, units and row IDs must match without broadcasting or truncation"))
                continue
            tolerance = tolerance_map[a.category]
            finite = equal = nulls = bad = 0
            absolute_errors, relative_errors, indices = [], [], []
            pack = "<f" if a.dtype == "float32" else "<d"
            for index, (x, y) in enumerate(zip(a.values, b.values)):
                if x is None or y is None:
                    if x is y:
                        nulls += 1
                    else:
                        bad += 1
                        if len(indices) < 16:
                            indices.append(index)
                    continue
                finite += 1
                equal += struct.pack(pack, x) == struct.pack(pack, y)
                error = abs(x - y)
                scale = max(abs(x), abs(y))
                relative = error / scale if scale else 0.0
                absolute_errors.append(error)
                relative_errors.append(relative)
                if not math.isfinite(error) or error > tolerance.absolute + tolerance.relative * scale:
                    bad += 1
                    if len(indices) < 16:
                        indices.append(index)
            maximum = max(absolute_errors, default=0.0)
            # Scaled RMS avoids overflow squaring large finite feature values.
            rms = (maximum * math.sqrt(math.fsum((error / maximum)**2 for error in absolute_errors) / finite)
                   if finite and maximum and math.isfinite(maximum) else 0.0 if maximum == 0 else None)
            relative_maximum = max(relative_errors, default=0.0)
            comparisons.append(BlockComparison(a.category, a.role_or_metric_id, finite, equal, nulls,
                                               maximum if math.isfinite(maximum) else None,
                                               relative_maximum if math.isfinite(relative_maximum) else None,
                                               rms, bad, tuple(indices)))
            if bad:
                issues.append(NumericIssue("CONTINUOUS_TOLERANCE_FAILED", str(key), "Continuous tolerance or exact null-mask check failed"))
    matches = not issues
    frozen_ok = _reviewed_freeze(policy, frozen, verifier, left, right, issues)
    accepted = matches and frozen_ok and not issues
    return EquivalenceReport(policy.sha256, "TRANSCRIPTS_EQUIVALENT_UNDER_FROZEN_POLICY" if accepted else "FAIL_CLOSED",
                             accepted, matches, tuple(comparisons), tuple(issues))
