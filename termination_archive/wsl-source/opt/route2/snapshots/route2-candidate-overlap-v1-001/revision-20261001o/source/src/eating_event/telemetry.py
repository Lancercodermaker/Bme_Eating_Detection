"""Validation and construction of bounded run telemetry events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Mapping, TypedDict
from uuid import uuid4


EventType = Literal["run_start", "gate_result", "escalation", "run_end"]


class TelemetryEvent(TypedDict):
    schema_version: Literal["telemetry_v1"]
    event_id: str
    event_type: EventType
    timestamp: str
    run_id: str
    project_id: str
    workflow_path: str
    execution_mode: str
    execution_backend: str
    capability_tags: list[str]
    loaded_profiles: list[str]
    payload: dict[str, object]


_EVENT_TYPES = {"run_start", "gate_result", "escalation", "run_end"}
_FORBIDDEN_KEY_PARTS = (
    "secret",
    "password",
    "token",
    "prompt",
    "test_truth",
    "raw_data",
    "source_data",
    "command_output",
)


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _FORBIDDEN_KEY_PARTS):
                return True
            if _contains_forbidden_key(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def validate_telemetry_payload(event_type: str, payload: Mapping[str, object]) -> None:
    if event_type not in _EVENT_TYPES:
        raise ValueError(f"unknown telemetry event type: {event_type}")
    if not isinstance(payload, Mapping):
        raise TypeError("telemetry payload must be a mapping")
    if _contains_forbidden_key(payload):
        raise ValueError("forbidden telemetry payload field")
    required: dict[str, tuple[str, ...]] = {
        "run_start": ("workflow_path",),
        "gate_result": ("gate_id", "result", "failure_class"),
        "escalation": ("reason", "hypothesis_count", "circuit_breaker_fired"),
        "run_end": ("final_status",),
    }
    missing = [key for key in required[event_type] if key not in payload]
    if missing:
        raise ValueError(f"telemetry payload missing {', '.join(missing)}")
    if event_type == "escalation" and payload["circuit_breaker_fired"] is not True:
        raise ValueError("escalation requires circuit_breaker_fired=true")
    if event_type == "run_start" and payload["workflow_path"] != "RESEARCH":
        raise ValueError("run_start workflow_path must be RESEARCH")


def build_telemetry_event(
    event_type: EventType,
    payload: Mapping[str, object],
    *,
    run_context: Mapping[str, object],
) -> TelemetryEvent:
    validate_telemetry_payload(event_type, payload)
    return {
        "schema_version": "telemetry_v1",
        "event_id": uuid4().hex,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": str(run_context["run_id"]),
        "project_id": str(run_context["project_id"]),
        "workflow_path": str(run_context["workflow_path"]),
        "execution_mode": str(run_context["execution_mode"]),
        "execution_backend": str(run_context["execution_backend"]),
        "capability_tags": list(run_context["capability_tags"]),
        "loaded_profiles": list(run_context["loaded_profiles"]),
        "payload": dict(payload),
    }
