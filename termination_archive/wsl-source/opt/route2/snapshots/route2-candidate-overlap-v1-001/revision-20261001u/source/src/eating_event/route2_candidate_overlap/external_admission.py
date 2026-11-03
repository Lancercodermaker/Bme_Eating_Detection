"""Validate a controller-sealed A+B admission kept outside the source tree.

This module only verifies bytes supplied by the trusted controller. It does not
create an approval, establish that a reviewer is independent, or prove that the
running source/runtime trees are immutable. Those identities must be checked by
the external supervisor before it invokes this loader.
"""

from __future__ import annotations

from dataclasses import fields
import hashlib
import hmac
import json
from typing import Any

from .contracts import FrozenAdmission, STUDY_ID


_BODY_FIELDS = frozenset({
    "schema", "study_id", "independent_review_id", "review_result",
    "owner_approval_id", "owner_approved", "approval_scope",
    "authorization_card_sha256", "source_snapshot_sha256",
    "runtime_snapshot_sha256", "frozen_admission",
})
_ENVELOPE_FIELDS = frozenset({"body", "controller_hmac_sha256"})
_SCHEMA = "route2_controller_sealed_admission_v1"
MAX_CONTROLLER_SEAL_BYTES = 1 << 20


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64
        and all(char in "0123456789abcdef" for char in value.lower())
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _frozen_admission(value: object) -> FrozenAdmission:
    if not isinstance(value, dict):
        raise PermissionError("sealed admission has no frozen identity object")
    expected = {item.name for item in fields(FrozenAdmission)}
    if set(value) != expected:
        raise PermissionError("sealed admission has an unknown or missing frozen identity field")
    normalized = dict(value)
    volumes = normalized.get("approved_write_volumes")
    if not isinstance(volumes, list) or any(not isinstance(item, str) for item in volumes):
        raise PermissionError("sealed admission write-volume list is malformed")
    normalized["approved_write_volumes"] = tuple(volumes)
    try:
        return FrozenAdmission(**normalized)
    except (TypeError, ValueError) as exc:
        raise PermissionError("sealed frozen admission fails its path or digest contract") from exc


def load_controller_sealed_admission(
    artifact_bytes: bytes,
    *,
    controller_key: bytes,
    expected_source_snapshot_sha256: str,
    expected_runtime_snapshot_sha256: str,
    expected_review_id: str,
    expected_owner_approval_id: str,
    expected_authorization_card_sha256: str,
) -> FrozenAdmission:
    """Verify canonical, one-card A+B bytes and return their frozen pins.

    ``controller_key`` and the expected identities must come from a trusted
    supervisor configuration outside the source snapshot. This pure function
    intentionally performs no file or project-data reads, so it can be tested
    with synthetic records before any admission exists.
    """

    if type(artifact_bytes) is not bytes or not artifact_bytes:
        raise PermissionError("controller admission artifact must be nonempty bytes")
    if len(artifact_bytes) > MAX_CONTROLLER_SEAL_BYTES:
        raise PermissionError("controller admission artifact exceeds the fixed size bound")
    if type(controller_key) is not bytes or len(controller_key) < 32:
        raise PermissionError("controller seal key must contain at least 256 bits")
    if (
        not _is_sha256(expected_source_snapshot_sha256)
        or not _is_sha256(expected_runtime_snapshot_sha256)
        or not _is_sha256(expected_authorization_card_sha256)
        or not expected_review_id or not expected_owner_approval_id
    ):
        raise PermissionError("external review, approval, card or snapshot identity is incomplete")
    try:
        envelope: Any = json.loads(artifact_bytes, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PermissionError("controller admission artifact is not valid UTF-8 JSON") from exc
    try:
        canonical_envelope = _canonical(envelope)
    except (UnicodeError, TypeError, ValueError, RecursionError) as exc:
        raise PermissionError("controller admission JSON cannot be canonically encoded") from exc
    if (
        not isinstance(envelope, dict)
        or set(envelope) != _ENVELOPE_FIELDS
        or canonical_envelope != artifact_bytes
    ):
        raise PermissionError("controller admission envelope is noncanonical or has unknown fields")
    body = envelope.get("body")
    signature = envelope.get("controller_hmac_sha256")
    if not isinstance(body, dict) or set(body) != _BODY_FIELDS:
        raise PermissionError("controller admission body is incomplete or has unknown fields")
    if not _is_sha256(signature):
        raise PermissionError("controller admission HMAC is malformed")
    expected_signature = hmac.new(controller_key, _canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.lower(), expected_signature):
        raise PermissionError("controller admission seal does not authenticate these bytes")
    if (
        body.get("schema") != _SCHEMA
        or body.get("study_id") != STUDY_ID
        or body.get("independent_review_id") != expected_review_id
        or body.get("review_result") != "PASS"
        or body.get("owner_approval_id") != expected_owner_approval_id
        or body.get("owner_approved") is not True
        or body.get("approval_scope") != "A+B"
        or body.get("authorization_card_sha256") != expected_authorization_card_sha256.lower()
        or body.get("source_snapshot_sha256") != expected_source_snapshot_sha256.lower()
        or body.get("runtime_snapshot_sha256") != expected_runtime_snapshot_sha256.lower()
    ):
        raise PermissionError("controller seal is for a different review, approval, card or snapshot")
    frozen = _frozen_admission(body.get("frozen_admission"))
    if (
        frozen.source_snapshot_sha256.lower() != expected_source_snapshot_sha256.lower()
        or frozen.runtime_snapshot_sha256.lower() != expected_runtime_snapshot_sha256.lower()
        or frozen.approval_record != expected_owner_approval_id
    ):
        raise PermissionError("frozen admission pins differ from the externally sealed decision")
    return frozen
