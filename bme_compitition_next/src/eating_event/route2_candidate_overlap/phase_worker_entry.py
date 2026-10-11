"""Fixed private JSON codec/child entry; no grant, receipt or sandbox authority.

The native launcher has already chrooted, dropped privileges, filtered syscalls
and closed every outside FD before this interpreter starts. Only FD 3 survives.
The deployed root/closure, original deadlines and broker publication are still
production dependencies. A failure capsule carries bounded numeric summaries;
raw child exceptions cannot survive child death through this JSON transport.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import select
import stat
import struct
import sys
import time

if __name__ == "__main__":
    # -I -S -B: no cwd/user-site/PYTHONPATH/.pth loading. This is the one fixed
    # reviewed project root inside the native chroot, not a supplied import path.
    sys.path.insert(0, "/source/src")

from eating_event.a1.metrics import AggregateMetrics, ParticipantMetrics, PredictionRecord
from eating_event.metrics import EventInterval
from eating_event.route2_candidate_overlap.budget import PredictionFreezeReceipt
from eating_event.route2_candidate_overlap.contracts import RegisteredFile, StudyStage
from eating_event.route2_candidate_overlap.gt_provider import FrozenPredictionReceipt, TruthReadScope
from eating_event.route2_candidate_overlap.native_failure_capture import NativeFailureCapture
from eating_event.route2_candidate_overlap.phase_worker import (
    EvaluationPhaseResult, InnerSelectionPhaseResult, LabelCandidate,
    TrainingPhaseResult, execute_phase_operation,
)

_MAX_BYTES, _MAX_ROWS, _MAX_NODES, _MAX_DEPTH = 16 << 20, 1 << 16, 1 << 20, 16
_OPERATIONS = ("training_labels", "inner_evaluator", "outer_evaluator")
_TEXT, _HASH, _COUNT, _TIME = "text", "hash", "count", "time"
_RATIO, _NUMBER = "ratio", "number"
def _seq(rule): return ("seq", rule)
def _opt(rule): return ("opt", rule)

_RULES = {
    EventInterval: (("start_ms", _TIME), ("end_ms", _TIME)),
    LabelCandidate: (("candidate_id", _TEXT), ("participant_id", _TEXT), ("start_ms", _TIME), ("end_ms", _TIME)),
    PredictionRecord: (("prediction_id", _TEXT), ("participant_id", _TEXT), ("record_id", _TEXT),
        ("session_id", _TEXT), ("source_segment_id", _opt(_TEXT)), ("interval", EventInterval)),
    RegisteredFile: (("path", _TEXT), ("sha256", _HASH), ("fields", _seq(_TEXT)),
        ("role_id", _TEXT), ("projection_attestation", _TEXT), ("scope_sha256", _HASH)),
    PredictionFreezeReceipt: (("phase", ("enum", ("inner", "outer"))), ("role_id", _TEXT), ("outer_id", _TEXT),
        ("threshold", ("enum", ("0.10", "0.25", "0.50"))), ("prediction_path", _TEXT),
        ("prediction_sha256", _HASH), ("predict_attempt", _COUNT), ("decoder_attempt", _COUNT), ("ledger_event_sha256", _HASH)),
    FrozenPredictionReceipt: (("outer_id", _TEXT), ("role_ids", _seq(_TEXT)), ("thresholds", _seq(_RATIO)),
        ("predictions", _seq(PredictionFreezeReceipt))),
    TruthReadScope: (("stage", StudyStage), ("outer_id", _TEXT), ("role_ids", _seq(_TEXT)), ("participants", _seq(_TEXT)),
        ("eligibility_field", ("enum", ("training_eligibility", "evaluation_eligibility"))),
        ("consumer", ("enum", ("candidate_labeler", "threshold_selector", "outer_evaluator"))),
        ("prediction_receipt", _opt(FrozenPredictionReceipt)), ("role_graph_sha256", _HASH), ("participant_scope_attestation", _HASH)),
    TrainingPhaseResult: (("labels", _seq("label")), ("positive_gt_commitments", _seq(_HASH))),
    InnerSelectionPhaseResult: (("f1", _opt(_RATIO)), ("fp", _COUNT), ("eligible_gt_count", _COUNT), ("prediction_count", _COUNT)),
    ParticipantMetrics: (("participant_id", _TEXT), ("tp", _COUNT), ("fp", _COUNT), ("fn", _COUNT),
        ("precision", _RATIO), ("recall", _opt(_RATIO)), ("f1", _opt(_RATIO)),
        ("start_mae_ms", _opt(_NUMBER)), ("end_mae_ms", _opt(_NUMBER)),
        ("matched_pairs", _seq(("row", (_TEXT, _HASH, _RATIO)))), ("unmatched_prediction_ids", _seq(_TEXT)),
        ("unmatched_truth_ids", _seq(_HASH)), ("long_fp_count", _COUNT), ("long_fp_fraction", _RATIO),
        ("fp_per_hour", _opt(_NUMBER)), ("fp_per_hour_reason", _opt(_TEXT))),
    AggregateMetrics: (("tp", _COUNT), ("fp", _COUNT), ("fn", _COUNT), ("precision", _RATIO), ("recall", _RATIO),
        ("f1", _opt(_RATIO)), ("start_mae_ms", _opt(_NUMBER)), ("end_mae_ms", _opt(_NUMBER)), ("matched_count", _COUNT),
        ("participants", _seq(ParticipantMetrics)), ("long_fp_count", _COUNT), ("long_fp_fraction", _RATIO)),
    EvaluationPhaseResult: (("metric", AggregateMetrics), ("eligible_gt_count", _COUNT), ("candidate_covered_gt", _opt(_COUNT)),
        ("reference_candidate_covered_gt", _opt(_COUNT)), ("candidate_added_gt_commitments", _seq(_HASH)),
        ("candidate_lost_gt_commitments", _seq(_HASH)), ("control_matched_gt_commitments", _opt(_seq(_HASH))),
        ("matched_gt_added_commitments", _seq(_HASH)), ("matched_gt_lost_commitments", _seq(_HASH))),
}
_REQUEST = (("scope", TruthReadScope), ("operation", ("enum", _OPERATIONS)), ("expected_view_sha256", _HASH),
    ("gt_commitment_key", "key"), ("candidates", _seq(LabelCandidate)), ("reference_candidates", _opt(_seq(LabelCandidate))),
    ("control_final_matches", _opt(RegisteredFile)), ("control_metrics_sha256", _opt(_HASH)),
    ("predictions", _seq(PredictionRecord)), ("participant_ids", _seq(_TEXT)))
_RESULTS = dict(zip(_OPERATIONS, (TrainingPhaseResult, InnerSelectionPhaseResult, EvaluationPhaseResult)))

def _check(deadline):
    if type(deadline) is not int or not 0 < deadline < 1 << 63 or time.monotonic_ns() >= deadline:
        raise TimeoutError("original phase deadline exhausted")

def _mapping(value, fields):
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != {name for name, _ in fields}:
        raise ValueError("phase object has missing or unknown fields")

def _walk(rule, value, encode, deadline, budget, depth=0):
    _check(deadline)
    budget[0] += 1
    if budget[0] > _MAX_NODES or depth > _MAX_DEPTH:
        raise ValueError("phase value exceeds its node/depth bound")
    if type(rule) is tuple:
        kind, item = rule
        if kind == "opt": return None if value is None else _walk(item, value, encode, deadline, budget, depth + 1)
        if kind == "enum":
            if type(value) is not str or value not in item: raise ValueError("phase enumeration differs")
            return value
        if type(value) is not (tuple if encode else list) or len(value) > _MAX_ROWS:
            raise ValueError("phase rows exceed their exact container/count bound")
        if kind == "row" and len(value) != len(item): raise ValueError("phase row shape differs")
        values = [_walk(item[i] if kind == "row" else item, child, encode, deadline, budget, depth + 1)
                  for i, child in enumerate(value)]
        return values if encode else tuple(values)
    if rule is StudyStage:
        if encode:
            if type(value) is not StudyStage: raise ValueError("phase stage type differs")
            return value.value
        if type(value) is not str: raise ValueError("phase stage type differs")
        return StudyStage(value)
    if rule in _RULES:
        fields = _RULES[rule]
        if encode:
            if type(value) is not rule: raise ValueError("phase scientific type differs")
            return {name: _walk(child, getattr(value, name), True, deadline, budget, depth + 1) for name, child in fields}
        _mapping(value, fields)
        return rule(**{name: _walk(child, value[name], False, deadline, budget, depth + 1) for name, child in fields})
    if rule == "key":
        if encode:
            if type(value) is not bytes or not 32 <= len(value) <= 64: raise ValueError("phase commitment key bound differs")
            return value.hex()
        if type(value) is not str or not 64 <= len(value) <= 128 or len(value) % 2 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("phase commitment key encoding differs")
        return bytes.fromhex(value)
    if rule in (_TEXT, _HASH):
        if type(value) is not str or not 0 < len(value) <= 4096 or "\0" in value:
            raise ValueError("phase text bound differs")
        if rule == _HASH and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError("phase digest/commitment differs")
        return value
    if rule in (_COUNT, _TIME, "label"):
        lo, hi = ((0, 1) if rule == "label" else (0, (1 << 63) - 1) if rule == _COUNT else (-(1 << 63), (1 << 63) - 1))
        if type(value) is not int or not lo <= value <= hi: raise ValueError("phase integer type/bound differs")
        return value
    if type(value) is not float or not math.isfinite(value) or not 0 <= value <= (1 if rule == _RATIO else 1e20):
        raise ValueError("phase float type/bound differs")
    return value

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("duplicate phase JSON key")
        result[key] = value
    return result

def _integer(text):
    if len(text) > 20: raise ValueError("phase JSON integer exceeds its bound")
    value = int(text)
    if not -(1 << 63) <= value < 1 << 63: raise ValueError("phase JSON integer exceeds its bound")
    return value

def _real(text):
    if len(text) > 32: raise ValueError("phase JSON float exceeds its bound")
    value = float(text)
    if not math.isfinite(value): raise ValueError("nonfinite phase JSON")
    return value

def _constant(_): raise ValueError("nonstandard phase JSON constant")

def _loads(frame, deadline):
    # Scan bytes BEFORE JSON's object/list/string allocations. Every array has
    # at most MAX_ROWS elements; depth, scalar size and total tokens are bounded.
    if type(frame) not in (bytes, bytearray) or not 0 < len(frame) <= _MAX_BYTES:
        raise ValueError("phase JSON byte bound differs")
    stack, counts = [0] * _MAX_DEPTH, [0] * _MAX_DEPTH
    depth = nodes = string_size = 0
    quoted = escaped = token = False
    for index, char in enumerate(frame):
        if not index % 4096: _check(deadline)
        if quoted:
            string_size += 1
            if string_size > 24576: raise ValueError("phase JSON string bound exceeded")
            if escaped: escaped = False
            elif char == 92: escaped = True
            elif char == 34: quoted = False
            continue
        if char in (9, 10, 13, 32): token = False; continue
        if char in (93, 125):
            if not depth or stack[depth - 1] != (91 if char == 93 else 123): raise ValueError("phase JSON nesting differs")
            depth -= 1; token = False; continue
        if char == 44:
            if depth and stack[depth - 1] == 91:
                counts[depth - 1] += 1
                if counts[depth - 1] > _MAX_ROWS: raise ValueError("phase JSON row bound exceeded")
            token = False; continue
        if char == 58: token = False; continue
        if depth and stack[depth - 1] == 91 and not counts[depth - 1]: counts[depth - 1] = 1
        if char == 34:
            quoted = True; string_size = 0; nodes += 1; token = False
        elif char in (91, 123):
            if depth == _MAX_DEPTH: raise ValueError("phase JSON depth bound exceeded")
            stack[depth], counts[depth] = char, 0; depth += 1; nodes += 1; token = False
        elif not token: nodes += 1; token = True
        if nodes > _MAX_NODES: raise ValueError("phase JSON token bound exceeded")
    if depth or quoted: raise ValueError("incomplete phase JSON")
    _check(deadline)
    value = json.loads(frame, object_pairs_hook=_unique, parse_int=_integer, parse_float=_real, parse_constant=_constant)
    _check(deadline)
    return value

def _dumps(value, deadline):
    body = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    for chunk in encoder.iterencode(value):
        _check(deadline)
        encoded = chunk.encode("ascii")
        if len(body) + len(encoded) > _MAX_BYTES: raise ValueError("phase encoded byte bound exceeded")
        body.extend(encoded)
    return body

def _poll(fd, writing, deadline):
    _check(deadline)
    poller = select.poll(); poller.register(fd, select.POLLOUT if writing else select.POLLIN)
    while True:
        _check(deadline)
        left = deadline - time.monotonic_ns()
        events = poller.poll(min(50, max(1, (left + 999999) // 1000000)))
        _check(deadline)
        if not events: continue
        if any(actual != fd or flags & (select.POLLERR | select.POLLNVAL) for actual, flags in events):
            raise OSError("private phase IPC poll failed")
        return

def _read(fd, count, deadline):
    _check(deadline)
    if not 0 <= count <= _MAX_BYTES: raise ValueError("phase read bound differs")
    body = bytearray(count); position = 0
    while position < count:
        _poll(fd, False, deadline)
        try: part = os.read(fd, min(65536, count - position))
        except BlockingIOError: continue
        if not part: raise EOFError("incomplete private phase frame")
        body[position:position + len(part)] = part; position += len(part)
    return body

def _write(fd, body, deadline):
    _check(deadline)
    if type(body) not in (bytes, bytearray) or len(body) > _MAX_BYTES: raise ValueError("phase write bound differs")
    view = memoryview(body); position = 0
    while position < len(view):
        _poll(fd, True, deadline)
        try: sent = os.write(fd, view[position:position + 65536])
        except BlockingIOError: continue
        if not sent: raise OSError("private phase IPC write made no progress")
        position += sent

def _receive(fd, deadline):
    length, = struct.unpack("!I", _read(fd, 4, deadline))
    if not 0 < length <= _MAX_BYTES: raise ValueError("private phase frame exceeds its byte bound")
    return _loads(_read(fd, length, deadline), deadline)

def _send(fd, value, deadline):
    body = _dumps(value, deadline)
    _write(fd, struct.pack("!I", len(body)), deadline); _write(fd, body, deadline)

def _eof(fd, deadline):
    while True:
        _poll(fd, False, deadline)
        try: extra = os.read(fd, 1)
        except BlockingIOError: continue
        if extra: raise ValueError("unexpected trailing private phase frame")
        return

def _request(value, encode, deadline):
    if not encode:
        _mapping(value, (("schema", None), ("payload", None)))
        if type(value["schema"]) is not str or value["schema"] != "route2_phase_request_v1": raise ValueError("phase request schema differs")
        value = value["payload"]
    _mapping(value, _REQUEST); budget = [0]
    payload = {name: _walk(rule, value[name], encode, deadline, budget) for name, rule in _REQUEST}
    return {"schema": "route2_phase_request_v1", "payload": payload} if encode else payload

def _result(value, operation, encode, deadline):
    if encode: return {"schema": "route2_phase_result_v1", "operation": operation,
        "result": _walk(_RESULTS[operation], value, True, deadline, [0])}
    _mapping(value, (("schema", None), ("operation", None), ("result", None)))
    if type(value["schema"]) is not str or value["schema"] != "route2_phase_result_v1" or type(value["operation"]) is not str or value["operation"] != operation:
        raise ValueError("phase response schema/operation differs")
    return _walk(_RESULTS[operation], value["result"], False, deadline, [0])

def _safe_error(error):
    kinds = {json.JSONDecodeError: 1, UnicodeDecodeError: 2, ValueError: 3, PermissionError: 4,
             TimeoutError: 5, OSError: 6, MemoryError: 7}
    kind = kinds.get(type(error), 8)
    number = error.errno if type(error) in (OSError, PermissionError, TimeoutError) else 0
    position = error.pos if type(error) is json.JSONDecodeError else -1
    return {"kind": kind, "errno": number if type(number) is int and 0 <= number <= 4095 else 0,
            "json_position": position if type(position) is int and -1 <= position <= _MAX_BYTES else -1}

def _failure(error):
    primary, secondary, seen = error, [], set()
    capture = getattr(error, "failure_capture", None) if type(error) is PermissionError else None
    if type(capture) is NativeFailureCapture:
        primary = capture.failure.primary_error or error
        secondary.extend(slot.error for slot in capture._slots if slot.error is not None and slot.error is not primary)
    current = error
    while current is not None and id(current) not in seen and len(secondary) <= 16:
        seen.add(id(current))
        if current is not primary and all(current is not item for item in secondary): secondary.append(current)
        current = current.__context__
    return {"schema": "route2_phase_failure_v1", "primary": _safe_error(primary),
            "secondary": [_safe_error(item) for item in secondary[:16]],
            "truncated": len(secondary) > 16 or current is not None}

def _main():
    # No arbitrary entry, operation import, FD or path can be supplied in argv.
    if (len(sys.argv) != 2 or not sys.argv[1].isascii() or not sys.argv[1].isdecimal()
            or len(sys.argv[1]) > 19 or os.getresuid() != (65534,) * 3
            or os.getresgid() != (65534,) * 3 or os.getgroups()
            or not stat.S_ISSOCK(os.fstat(3).st_mode)):
        os._exit(126)
    deadline = int(sys.argv[1]); primary = secondary = None
    try:
        request = _request(_receive(3, deadline), False, deadline)
        _eof(3, deadline)
        operation = request.pop("operation")
        control = request["control_final_matches"]
        result = execute_phase_operation(**request, operation=operation, view_path=Path("/inputs/gt-view.jsonl"),
            control_final_matches_path=Path("/inputs/control-final-matches.jsonl") if control is not None else None)
        _check(deadline); _send(3, _result(result, operation, True, deadline), deadline)
    except BaseException as error:
        primary = error  # retain raw objects locally; never pickle or print them
        try: _send(3, _failure(error), deadline)
        except BaseException as reporting_error: secondary = reporting_error
    # The sole inherited channel is released by process exit, avoiding a retry
    # or an unreportable explicit last-FD close. Native exit is still consumed
    # by the parent; a capsule alone is never successful phase/GT preservation.
    os._exit(126 if primary is not None or secondary is not None else 0)

if __name__ == "__main__": _main()
__all__ = []
