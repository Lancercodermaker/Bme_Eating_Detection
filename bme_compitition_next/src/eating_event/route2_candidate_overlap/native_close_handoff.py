"""Bounded wire format for native close and independent Linux exit signatures.

This module has no key generation, approval creation, filesystem installation,
or generic receipt-signing API. Trust and invocation pins must be obtained by
the concrete installed bridges. Ed25519 is loaded lazily: an absent or unsupported
provider refuses instead of falling back to a MAC shared with a verifier.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import asdict, fields
import hashlib
import json
import importlib.util
from pathlib import PurePosixPath
import re
import stat
import sys

from .budget import BudgetLimits, STAGE_A_CAPACITY_UPPER_BOUND_V2, require_fixed_native_budget
from .contracts import STUDY_ID, StudyStatus
from .linux_supervisor import Route2Supervisor, TerminalCloseReceipt


MAX_TRUST_BYTES = 65536
MAX_NATIVE_BYTES = 24 << 20
MAX_EXIT_BYTES = 65536
MAX_LEDGER_BYTES = 16 << 20
MAX_TERMINAL_BYTES = 1 << 20
MAX_LEDGER_RECORDS = 65536
_HEX = re.compile(r"[0-9a-f]+\Z")
_SESSION_FIELDS = frozenset({
    "invocation_id", "unit_name", "systemd_invocation_id", "linux_boot_id",
    "main_pid", "main_start_ticks", "invocation_started_monotonic_ns",
    "host_nonce", "external_started_ticks", "qpc_frequency",
})
_TRUST_FIELDS = frozenset({
    "schema", "study_id", "full_ab_seal_sha256", "frozen_admission_sha256",
    "authorization_card_sha256", "owner_approval_id", "independent_review_id",
    "budget_policy_sha256", "limits", "ledger_path", "role_graph_sha256",
    "native_close_public_key", "linux_exit_public_key", "native_payload_cap_bytes",
    "exit_payload_cap_bytes", "attempt_payload_cap_bytes", "anchor_payload_cap_bytes",
})
_OBSERVATION_FIELDS = frozenset({
    "unit_name", "systemd_invocation_id", "unit_result", "exit_status", "active_state",
    "cgroup_path", "cgroup_empty", "terminal_reverified", "terminal_sha256",
    "ledger_sha256", "observed_monotonic_ns",
})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def _deny(message):
    raise PermissionError(message)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _deny("handoff JSON contains duplicate keys")
        result[key] = value
    return result


def _constant(value):
    _deny("handoff JSON contains a nonfinite number")


def _json_integer(value):
    # Python 3.10 has no universal decimal conversion cap. Bound BEFORE int().
    if len(value) > 20:
        _deny("handoff JSON integer exceeds its conversion bound")
    return int(value)


def _json_float(value):
    if len(value) > 64:
        _deny("handoff JSON float exceeds its conversion bound")
    return float(value)


def _depth(encoded):
    depth = 0
    items = 0
    quoted = escaped = False
    for byte in encoded:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            items += 1
            if depth > 32:
                _deny("handoff JSON exceeds its nesting bound")
        elif byte in (93, 125):
            depth -= 1
            if depth < 0:
                _deny("handoff JSON has an invalid nesting frame")
        elif byte in (44, 58):
            items += 1
        if items > 131072:
            _deny("handoff JSON exceeds its structural item bound")
    if depth or quoted:
        _deny("handoff JSON nesting/string frame is incomplete")


def parse(encoded, maximum):
    if type(encoded) is not bytes or not 0 < len(encoded) <= maximum:
        _deny("handoff frame is absent or exceeds its byte cap")
    try:
        _depth(encoded)
        value = json.loads(encoded, object_pairs_hook=_unique, parse_constant=_constant,
                           parse_int=_json_integer, parse_float=_json_float)
        if type(value) is not dict or canonical(value) != encoded:
            _deny("handoff JSON must be an exact canonical object")
        return value
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise PermissionError("handoff frame is not bounded canonical UTF-8 JSON") from exc


def _exact(value, names):
    if type(value) is not dict or set(value) != set(names):
        _deny("handoff object has missing or unknown fields")


def _hex(value, length):
    if type(value) is not str or len(value) != length or not _HEX.fullmatch(value):
        _deny("handoff digest/key/nonce is not canonical lowercase hex")
    return value


def _integer(value, *, minimum=1):
    if type(value) is not int or not minimum <= value < 1 << 63:
        _deny("handoff integer has an invalid type or range")
    return value


def _text(value):
    if (type(value) is not str or not 0 < len(value.encode("utf-8")) <= 256
            or any(ord(ch) < 33 or ord(ch) > 126 for ch in value)):
        _deny("handoff identity must be bounded printable ASCII without whitespace")
    return value


def validate_session(session):
    _exact(session, _SESSION_FIELDS)
    _text(session["invocation_id"])
    from .linux_cgroup_backend import _validate_unit_name
    _text(session["unit_name"])
    _validate_unit_name(session["unit_name"])
    _hex(session["systemd_invocation_id"], 32)
    _hex(session["host_nonce"], 64)
    if (type(session["linux_boot_id"]) is not str
            or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", session["linux_boot_id"])):
        _deny("handoff Linux boot ID is malformed")
    for name in ("main_pid", "main_start_ticks", "invocation_started_monotonic_ns",
                 "external_started_ticks", "qpc_frequency"):
        _integer(session[name])
    return session


def validate_trust(trust):
    _exact(trust, _TRUST_FIELDS)
    if trust["schema"] != "route2_native_close_trust_v1" or trust["study_id"] != STUDY_ID:
        _deny("handoff trust is for an unknown schema/study")
    for name in ("full_ab_seal_sha256", "frozen_admission_sha256", "authorization_card_sha256",
                 "budget_policy_sha256", "role_graph_sha256", "native_close_public_key", "linux_exit_public_key"):
        _hex(trust[name], 64)
    if trust["native_close_public_key"] == trust["linux_exit_public_key"]:
        _deny("native-close and independent-exit issuers must use separate keys")
    for name in ("owner_approval_id", "independent_review_id"):
        _text(trust[name])
        if trust[name] in {"NOT_ISSUED", "None", "PREPARED_UNREVIEWED"}:
            _deny("handoff trust has no issued review/approval identity")
    _exact(trust["limits"], {item.name for item in fields(BudgetLimits)})
    try:
        limits = BudgetLimits(**trust["limits"])
        require_fixed_native_budget(limits)
    except (TypeError, ValueError) as exc:
        raise PermissionError("handoff budget is invalid") from exc
    if (limits.stage_a_disk_accounting_mode != STAGE_A_CAPACITY_UPPER_BOUND_V2
            or limits.digest() != trust["budget_policy_sha256"]):
        _deny("handoff budget differs from its explicit V2 policy digest")
    path = trust["ledger_path"]
    if (type(path) is not str or not PurePosixPath(path).is_absolute()
            or PurePosixPath(path).as_posix() != path or ".." in PurePosixPath(path).parts):
        _deny("handoff ledger path is not canonical and absolute")
    for name, maximum in (("native_payload_cap_bytes", MAX_NATIVE_BYTES),
                          ("exit_payload_cap_bytes", MAX_EXIT_BYTES),
                          ("attempt_payload_cap_bytes", MAX_TRUST_BYTES),
                          ("anchor_payload_cap_bytes", MAX_TRUST_BYTES)):
        if _integer(trust[name]) > maximum:
            _deny("handoff policy cap exceeds the wire-format bound")
    return limits


def _provider():
    # Concrete bridges require identity in this actual process. Linux retains
    # an explicit refusal at its missing complete observer runtime producer;
    # a study bootstrap or readonly file snapshot cannot release that gate.
    # Never import a provider first and then accept an ambient installation.
    if sys.platform == "win32":
        from .windows_native_close_handoff import require_provider_origin
    else:
        from .linux_native_close_handoff import require_provider_origin
    runtime_root = require_provider_origin()
    spec = importlib.util.find_spec("cryptography")
    from pathlib import Path
    if (spec is None or not spec.origin or not Path(spec.origin).is_absolute()
            or not Path(spec.origin).resolve(strict=True).is_relative_to(runtime_root)):
        _deny("Ed25519 provider would resolve outside the authenticated immutable runtime")
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    except ImportError as exc:
        raise PermissionError("pinned Ed25519 provider is not installed in the immutable runtime") from exc
    for name, module in tuple(sys.modules.items()):
        if name == "cryptography" or name.startswith("cryptography.") or name in {"cffi", "_cffi_backend"} or name.startswith("cffi."):
            origin = getattr(module, "__file__", None)
            if (type(origin) is not str or not Path(origin).is_absolute()
                    or not Path(origin).resolve(strict=True).is_relative_to(runtime_root)):
                _deny("cryptography/transitive extension origin escaped the immutable runtime")
    if require_provider_origin() != runtime_root:
        _deny("immutable provider runtime changed during provider loading")
    return Ed25519PrivateKey, Ed25519PublicKey, serialization, InvalidSignature, UnsupportedAlgorithm


def _message(kind, body):
    return b"route2-native-close-handoff-v1\0" + kind.encode("ascii") + b"\0" + canonical(body)


def _sign(kind, body, private_bytes, public_hex, maximum):
    # Private callers are the two concrete root bridges; no public sign API.
    private_type, _, serialization, _, unsupported = _provider()
    if type(private_bytes) is not bytes or len(private_bytes) != 32:
        _deny("protected Ed25519 secret is not exactly 32 bytes")
    try:
        key = private_type.from_private_bytes(private_bytes)
        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if public.hex() != _hex(public_hex, 64):
            _deny("protected signing secret differs from the installed public trust")
        value = canonical({"schema": "route2_signed_handoff_v1", "kind": kind,
                           "key_id": digest(public), "body": body,
                           "signature": key.sign(_message(kind, body)).hex()})
    except (ValueError, unsupported) as exc:
        raise PermissionError("installed Ed25519 provider refuses this signing key") from exc
    if len(value) > maximum:
        _deny("signed handoff exceeds its explicitly installed payload cap")
    _provider()  # Recheck origins/actual runtime after any lazy provider work.
    return value


def verify(encoded, kind, public_hex, maximum):
    envelope = parse(encoded, maximum)
    _exact(envelope, {"schema", "kind", "key_id", "body", "signature"})
    public = bytes.fromhex(_hex(public_hex, 64))
    if (envelope["schema"] != "route2_signed_handoff_v1" or envelope["kind"] != kind
            or envelope["key_id"] != digest(public) or type(envelope["body"]) is not dict):
        _deny("signed handoff has the wrong domain or pinned issuer")
    signature = bytes.fromhex(_hex(envelope["signature"], 128))
    _, public_type, _, invalid, unsupported = _provider()
    try:
        public_type.from_public_bytes(public).verify(signature, _message(kind, envelope["body"]))
    except (invalid, unsupported, ValueError) as exc:
        raise PermissionError("handoff signature does not authenticate these exact bytes") from exc
    _provider()  # Verification can trigger lazy native/provider dependency loads.
    return envelope["body"]


def context(trust, session):
    validate_trust(trust)
    validate_session(session)
    return {"trust_sha256": digest(canonical(trust)), "session": session}


def _require_context(value, trust, session):
    if value != context(trust, session) or canonical(value) != canonical(context(trust, session)):
        _deny("signed handoff differs from the original full-seal/clock/session binding")


def _blob(value, maximum):
    if type(value) is not str or not 0 < len(value) <= 4 * ((maximum + 2) // 3):
        _deny("handoff binary field exceeds its bound")
    try:
        encoded = value.encode("ascii")
        decoded = base64.b64decode(encoded, validate=True)
    except (UnicodeError, binascii.Error, ValueError) as exc:
        raise PermissionError("handoff binary field is not canonical base64") from exc
    if not 0 < len(decoded) <= maximum or base64.b64encode(decoded) != encoded:
        _deny("handoff binary field is empty or noncanonical")
    return decoded


def terminal_wire(terminal):
    if type(terminal) is not TerminalCloseReceipt:
        _deny("handoff requires the exact native terminal receipt type")
    value = asdict(terminal)
    for name, maximum in (("ledger_bytes", MAX_LEDGER_BYTES), ("terminal_record_bytes", MAX_TERMINAL_BYTES)):
        data = value[name]
        if type(data) is not bytes or not 0 < len(data) <= maximum:
            _deny("native terminal bytes exceed the handoff bound")
        value[name] = base64.b64encode(data).decode("ascii")
    return value


def decode_terminal(value, trust, session):
    _exact(value, {item.name for item in fields(TerminalCloseReceipt)})
    value = dict(value)
    value["ledger_bytes"] = _blob(value["ledger_bytes"], MAX_LEDGER_BYTES)
    value["terminal_record_bytes"] = _blob(value["terminal_record_bytes"], MAX_TERMINAL_BYTES)
    for name in ("ledger_fsynced", "ledger_closed", "no_active_gt_view", "no_active_worker"):
        if value[name] is not True:
            _deny("signed terminal is not a closed/quiescent native handoff")
    for name in ("terminal_sha256", "terminal_binding_sha256"):
        _hex(value[name], 64)
    for name in ("invocation_started_monotonic_ns", "terminal_closed_monotonic_ns", "deadline_monotonic_ns"):
        _integer(value[name])
    limits = validate_trust(trust)
    if (value["invocation_id"] != session["invocation_id"] or value["unit_name"] != session["unit_name"]
            or type(value["status"]) is not str or value["status"] not in {item.value for item in StudyStatus}
            or value["invocation_started_monotonic_ns"] != session["invocation_started_monotonic_ns"]
            or value["deadline_monotonic_ns"] != session["invocation_started_monotonic_ns"] + limits.total_wall_ns
            or value["terminal_closed_monotonic_ns"] < session["invocation_started_monotonic_ns"]):
        _deny("signed terminal differs from the original invocation and full wall budget")
    terminal = TerminalCloseReceipt(**value)
    try:
        record = parse(terminal.terminal_record_bytes[:-1], MAX_TERMINAL_BYTES)
        evidence = record["entry"]["payload"]["evidence"]
        chain = evidence["route2_supervisor_chain"]
        expected = {}
        records = terminal.ledger_bytes.splitlines()
        if len(records) > MAX_LEDGER_RECORDS:
            _deny("signed terminal exceeds the bounded ledger record count")
        for raw in records:
            event = parse(raw, MAX_TERMINAL_BYTES)["entry"]
            if event["event"] in ("stage_a_finished", "stage_b_entry_passed", "stage_b_volume_expanded", "stage_b_complete"):
                if event["event"] in expected:
                    _deny("signed terminal has a duplicate phase")
                expected[event["event"]] = event["payload"]
        if digest(canonical(chain)) != terminal.terminal_binding_sha256 or record["sha256"] != terminal.terminal_sha256:
            _deny("signed terminal digest differs from its actual terminal/chain bytes")
        Route2Supervisor._verify_terminal_record(terminal, terminal.status, evidence,
            terminal.terminal_binding_sha256, expected, session["invocation_started_monotonic_ns"],
            session["invocation_started_monotonic_ns"] + limits.stage_a_wall_ns,
            terminal.deadline_monotonic_ns, trust["role_graph_sha256"])
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise PermissionError("signed terminal ledger is malformed") from exc
    return terminal


def decode_native(encoded, trust, session):
    body = verify(encoded, "native_close", trust["native_close_public_key"], trust["native_payload_cap_bytes"])
    return decode_native_body(body, trust, session)


def decode_native_body(body, trust, session):
    """Validate owner-channel bytes; only decode_native authenticates a signature."""
    _exact(body, {"context", "terminal", "ledger_identity", "ledger_sha256", "issued_monotonic_ns"})
    _require_context(body["context"], trust, session)
    identity = body["ledger_identity"]
    if type(identity) is not list or len(identity) != 5:
        _deny("signed ledger inode identity is incomplete")
    for item in identity:
        _integer(item, minimum=0)
    if not stat.S_ISREG(identity[2]) or identity[3:] != [1, 0] or identity[2] & 0o022:
        _deny("signed ledger identity is not the original protected root-owned inode")
    terminal = decode_terminal(body["terminal"], trust, session)
    if body["ledger_sha256"] != digest(terminal.ledger_bytes):
        _deny("signed native handoff ledger digest differs from its bytes")
    issued = _integer(body["issued_monotonic_ns"])
    if issued < terminal.terminal_closed_monotonic_ns or (terminal.status != "INCOMPLETE_RESOURCE" and issued > terminal.deadline_monotonic_ns):
        _deny("native signature issuance is outside the original wall frame")
    return terminal, tuple(identity), body


def require_observation(observation, terminal, session):
    _exact(observation, _OBSERVATION_FIELDS)
    observed = _integer(observation["observed_monotonic_ns"])
    if (observation["unit_name"] != terminal.unit_name or observation["systemd_invocation_id"] != session["systemd_invocation_id"]
            or observation["unit_result"] != "success" or type(observation["exit_status"]) is not int
            or observation["exit_status"] != 0 or observation["active_state"] != "inactive"
            or observation["cgroup_path"] != "/system.slice/" + terminal.unit_name
            or observation["cgroup_empty"] is not True or observation["terminal_reverified"] is not True
            or observation["terminal_sha256"] != terminal.terminal_sha256
            or observation["ledger_sha256"] != digest(terminal.ledger_bytes)
            or observed < terminal.terminal_closed_monotonic_ns
            or (terminal.status != "INCOMPLETE_RESOURCE" and observed > terminal.deadline_monotonic_ns)):
        _deny("signed outer Linux observation is not the original successful post-exit witness")


__all__ = ["MAX_NATIVE_BYTES", "MAX_EXIT_BYTES"]
