"""Append-only budget accounting; execution requires a reviewed Linux enforcer.

Snapshots are observations, never a substitute for the independently reviewed
OS limits and the post-terminal wall receipt.  Without that controller the study
fails before output creation.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import TYPE_CHECKING, Callable, Iterator, Literal, Protocol, TypeVar
import uuid

from .contracts import ExperimentApproval, STUDY_ID, StudyStatus
from .candidates import CandidateFileReceipt

if TYPE_CHECKING:
    from .gt_provider import TruthReadScope

ZERO_HASH = "0" * 64
_BINARY = getattr(os, "O_BINARY", 0)
T = TypeVar("T")
CALL_CEILINGS = {
    "verifier_fit": 25,
    "verifier_predict": 25,
    "decoder": 65,
    "event_evaluator": 21,
}


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    stage_a_wall_ns: int = 1_200_000_000_000
    total_wall_ns: int = 3_600_000_000_000
    fit_wall_ns: int = 900_000_000_000
    rss_cap_bytes: int = 4_294_967_296
    stage_a_disk_bytes: int = 2_147_483_648
    total_disk_bytes: int = 4_294_967_296
    startup_free_disk_bytes: int = 8_589_934_592
    worker_limit: int = 2
    stage_b_disk_slack_bytes: int = 268_435_456
    stage_b_rss_slack_bytes: int = 536_870_912

    def __post_init__(self) -> None:
        values = tuple(asdict(self).values())
        if any(type(value) is not int for value in values):
            raise ValueError("every budget limit must be an exact integer")
        if any(value <= 0 for value in values):
            raise ValueError("every budget limit must be positive")
        if self.stage_a_wall_ns > self.total_wall_ns:
            raise ValueError("Stage A wall ceiling exceeds the study ceiling")
        if self.fit_wall_ns > self.total_wall_ns:
            raise ValueError("fit wall ceiling exceeds the study ceiling")
        if self.stage_a_disk_bytes > self.total_disk_bytes:
            raise ValueError("Stage A disk ceiling exceeds the study ceiling")

    def digest(self) -> str:
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    process_tree_rss_bytes: int
    study_disk_peak_bytes: int
    compute_workers: int
    available_ram_bytes: int
    study_disk_current_bytes: int
    guest_backing_free_bytes: int
    guest_backing_mount_id: str
    guest_backing_device: str
    windows_vhdx_path: str
    windows_volume_id: str
    windows_volume_free_bytes: int
    study_mount_id: str
    study_device: str
    study_fs_capacity_bytes: int
    study_fs_uuid: str
    study_loop_device: str
    study_image_path: str
    study_image_dev: int
    study_image_inode: int
    study_image_length_bytes: int
    study_image_allocated_bytes: int

    def __post_init__(self) -> None:
        values = (
            self.process_tree_rss_bytes,
            self.study_disk_peak_bytes,
            self.compute_workers,
            self.available_ram_bytes,
            self.study_disk_current_bytes,
            self.guest_backing_free_bytes,
            self.windows_volume_free_bytes,
            self.study_fs_capacity_bytes,
            self.study_image_dev,
            self.study_image_inode,
            self.study_image_length_bytes,
            self.study_image_allocated_bytes,
        )
        if any(type(value) is not int for value in values):
            raise ValueError("resource snapshot values must be exact integers")
        if min(values) < 0:
            raise ValueError("resource snapshot contains a negative observation")
        if self.study_disk_current_bytes > self.study_disk_peak_bytes:
            raise ValueError("current disk usage exceeds the stated peak")


def require_two_layer_startup_free(snapshot: ResourceSnapshot, limits: BudgetLimits) -> None:
    """The VHD's virtual `df` space cannot stand in for host physical free space."""

    if not all((
        snapshot.guest_backing_mount_id,
        snapshot.guest_backing_device,
        snapshot.windows_vhdx_path,
        snapshot.windows_volume_id,
    )):
        raise PermissionError("WSL backing and Windows VHDX volume identity is incomplete")
    if (
        snapshot.guest_backing_free_bytes < limits.startup_free_disk_bytes
        or snapshot.windows_volume_free_bytes < limits.startup_free_disk_bytes
    ):
        raise RuntimeError("two-layer startup free-disk hard line is not met")


def require_stage_filesystem(
    snapshot: ResourceSnapshot, expected: ResourceSnapshot, capacity_ceiling_bytes: int,
) -> None:
    """Check the same mounted filesystem still enforces the phase capacity."""

    frozen = (
        expected.study_mount_id,
        expected.study_device,
        expected.study_fs_uuid,
        expected.study_loop_device,
        expected.study_image_path,
        expected.study_image_dev,
        expected.study_image_inode,
    )
    observed = (
        snapshot.study_mount_id,
        snapshot.study_device,
        snapshot.study_fs_uuid,
        snapshot.study_loop_device,
        snapshot.study_image_path,
        snapshot.study_image_dev,
        snapshot.study_image_inode,
    )
    if not all(frozen):
        raise PermissionError("study mount identity was not frozen")
    if observed != frozen:
        raise PermissionError("study mount, loop, image or filesystem identity changed during the invocation")
    if snapshot.study_fs_capacity_bytes > capacity_ceiling_bytes:
        raise RuntimeError("study filesystem capacity exceeds the phase hard limit")
    if snapshot.study_image_length_bytes > capacity_ceiling_bytes:
        raise RuntimeError("study image length exceeds the phase hard limit")


def require_precreate_order(
    invocation_started_ns: int,
    free_checked_ns: int,
    image_created_ns: int,
    guest_free_bytes: int,
    host_free_bytes: int,
    required_free_bytes: int,
) -> None:
    """Reject a quota receipt sampled only after the formal image existed."""

    if any(type(value) is not int for value in (
        invocation_started_ns, free_checked_ns, image_created_ns,
        guest_free_bytes, host_free_bytes, required_free_bytes,
    )) or not (0 < invocation_started_ns <= free_checked_ns < image_created_ns):
        raise PermissionError("pre-create two-layer free sampling order is not proven")
    if min(guest_free_bytes, host_free_bytes) < required_free_bytes:
        raise RuntimeError("pre-create two-layer free-disk hard line is not met")


@dataclass(frozen=True, slots=True)
class EnforcementReceipt:
    """Evidence from a separately reviewed external hard-limit controller.

    An in-process assertion is insufficient: review must bind ``controller_id``
    to the installed OS controller, its implementation hash, covered volumes,
    and the exact approved study invocation before use.
    """

    controller_id: str
    controller_sha256: str
    study_root: str
    ledger_path: str
    lock_path: str
    covered_write_volumes: tuple[str, ...]
    hard_rss: bool
    hard_worker_threads: bool
    hard_disk_peak: bool
    hard_wall: bool
    evidence_sha256: str
    parent_cgroup_path: str
    memory_max_bytes: int
    memory_swap_max_bytes: int
    pids_max: int
    rlimit_as_per_process_bytes: int
    stage_a_capacity_bytes: int
    total_capacity_bytes: int
    guest_backing_mount_id: str
    windows_volume_id: str
    invocation_started_monotonic_ns: int
    precreate_free_checked_monotonic_ns: int
    image_created_monotonic_ns: int
    precreate_guest_free_bytes: int
    precreate_windows_volume_free_bytes: int
    study_fs_uuid: str
    study_loop_device: str
    study_image_path: str
    study_image_dev: int
    study_image_inode: int
    study_image_length_bytes: int

    def require_complete(self) -> None:
        if (
            not self.controller_id
            or len(self.controller_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in self.controller_sha256.lower())
            or not self.covered_write_volumes
            or not all((self.hard_rss, self.hard_worker_threads, self.hard_disk_peak, self.hard_wall))
            or len(self.evidence_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in self.evidence_sha256.lower())
            or not self.parent_cgroup_path
            or not self.guest_backing_mount_id
            or not self.windows_volume_id
            or not self.study_fs_uuid
            or not self.study_loop_device
            or not self.study_image_path
            or any(
                type(value) is not int or value < 0
                for value in (
                    self.memory_max_bytes,
                    self.memory_swap_max_bytes,
                    self.pids_max,
                    self.rlimit_as_per_process_bytes,
                    self.stage_a_capacity_bytes,
                    self.total_capacity_bytes,
                    self.invocation_started_monotonic_ns,
                    self.precreate_free_checked_monotonic_ns,
                    self.image_created_monotonic_ns,
                    self.precreate_guest_free_bytes,
                    self.precreate_windows_volume_free_bytes,
                    self.study_image_dev,
                    self.study_image_inode,
                    self.study_image_length_bytes,
                )
            )
        ):
            raise PermissionError("audited OS hard-limit coverage is incomplete")


class ResourceEnforcer(Protocol):
    """External platform controller; sampled monitoring alone is inadequate."""

    def prepare_volume(
        self,
        study_root: Path,
        ledger_path: Path,
        lock_path: Path,
        limits: BudgetLimits,
        invocation_started_monotonic_ns: int,
    ) -> tuple[EnforcementReceipt, ResourceSnapshot]: ...
    def current_snapshot(self, study_root: Path) -> ResourceSnapshot: ...
    def enforce_during_activity(
        self,
        study_root: Path,
        limits: BudgetLimits,
        activity: str,
        *,
        remaining_total_wall_ns: int,
        remaining_stage_a_wall_ns: int | None,
        remaining_fit_wall_ns: int | None,
        frozen_rss_ceiling_bytes: int,
    ) -> object: ...
    def stop_activity(self, handle: object) -> ResourceSnapshot: ...
    def expand_after_stage_b_entry(
        self, study_root: Path, limits: BudgetLimits, entry_event_sha256: str,
    ) -> ResourceSnapshot: ...


class UnavailableResourceEnforcer:
    """Safe default while no independently reviewed OS controller exists."""

    def prepare_volume(self, *args: object, **kwargs: object) -> tuple[EnforcementReceipt, ResourceSnapshot]:
        raise PermissionError("no independently reviewed OS hard-limit controller is installed")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class PredictionFreezeReceipt:
    phase: Literal["inner", "outer"]
    role_id: str
    outer_id: str
    threshold: str
    prediction_path: str
    prediction_sha256: str
    predict_attempt: int
    decoder_attempt: int
    ledger_event_sha256: str


@dataclass(frozen=True, slots=True)
class DurableEventReceipt:
    event_sha256: str
    fsynced_monotonic_ns: int


class AppendOnlyLedger:
    """A hash-chained journal that is created once and never resumed."""

    def __init__(self, path: Path, lock_path: Path, study_root: Path):
        self.path = path
        self.lock_path = lock_path
        self.study_root = study_root
        self._fd: int | None = None
        self._seq = 0
        self._tail = ZERO_HASH
        self._guard = threading.RLock()
        self._poisoned = False
        self._terminal = False
        self._owner_thread_id: int | None = None
        self._reference_roles: set[str] = set()
        self._reference_passed: set[str] = set()
        self._treatment_roles: set[str] = set()
        self._treatment_finished: dict[str, CandidateFileReceipt] = {}
        self._different_treatment_roles: set[str] = set()
        self._call_counts = dict.fromkeys(CALL_CEILINGS, 0)
        self._call_state: dict[tuple[str, int], tuple[str, str]] = {}
        self._frozen_predictions: dict[tuple[str, str, str, str], PredictionFreezeReceipt] = {}
        self._stage_b_entry_passed = False
        self._stage_b_entry_event_hash: str | None = None
        self._stage_b_volume_expanded = False
        self._active_gt_release: str | None = None
        self._terminal_sha256: str | None = None
        self._closed_at_monotonic_ns: int | None = None
        self._invocation_id: str | None = None
        self._invocation_started_monotonic_ns: int | None = None
        self._stage_a_finished = False
        self._stage_b_complete = False

    def _require_exact_paths(self) -> None:
        expected_root = self.study_root.parent / STUDY_ID
        expected_ledger = self.study_root.parent / f"{STUDY_ID}-budget.jsonl"
        expected_lock = self.study_root.parent / f"{STUDY_ID}.lock"
        if not all(path.is_absolute() for path in (self.study_root, self.path, self.lock_path)):
            raise ValueError("study paths must be absolute")
        if (self.study_root, self.path, self.lock_path) != (expected_root, expected_ledger, expected_lock):
            raise ValueError("study output, ledger, and lock must be exact approved sibling paths")
        if any(path.parent.is_symlink() for path in (self.study_root, self.path, self.lock_path)):
            raise PermissionError("study parent must not be a symlink")

    def create(self, approval: ExperimentApproval, limits: BudgetLimits) -> None:
        approval.require_full_ab()
        self._require_exact_paths()
        if (
            str(self.study_root) != approval.study_root_path
            or str(self.path) != approval.budget_ledger_path
            or str(self.lock_path) != approval.lock_path
        ):
            raise PermissionError("ledger paths differ from the frozen A+B approval")
        if approval.study_id != STUDY_ID or approval.budget_policy_sha256 != limits.digest():
            raise PermissionError("authorization does not bind this study and budget policy")
        if self._fd is not None:
            raise RuntimeError("ledger is already open")
        if not self.study_root.parent.is_dir():
            raise FileNotFoundError("approved study parent directory is missing")
        if self.path.exists() or self.lock_path.exists() or self.study_root.exists():
            raise FileExistsError("study output, ledger, or lock is already occupied")
        self._owner_thread_id = threading.get_ident()
        # Exclusive creation is intentionally nonrecoverable.  If a crash occurs
        # after any one object is created, a second invocation may not reuse it.
        self.study_root.mkdir()
        lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _BINARY, 0o600)
        try:
            payload = _canonical({"study_id": STUDY_ID, "lock_id": str(uuid.uuid4())})
            if os.write(lock_fd, payload) != len(payload):
                raise OSError("partial lock-file write")
            os.fsync(lock_fd)
        finally:
            os.close(lock_fd)
        self._fd = os.open(
            self.path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND | _BINARY,
            0o600,
        )
        self.append(
            "study_created",
            {
                "study_id": STUDY_ID,
                "approval_record": approval.approval_record,
                "input_registry_sha256": approval.input_registry_sha256,
                "budget_policy_sha256": limits.digest(),
                "limits": asdict(limits),
                "created_wall_ns": time.time_ns(),
            },
        )

    def append(self, event: str, payload: dict[str, object]) -> str:
        if self._fd is None:
            raise RuntimeError("ledger has not been created under an A+B approval")
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("budget ledger has a single owner thread; concurrent mutation is forbidden")
        with self._guard:
            if self._poisoned or self._terminal:
                raise RuntimeError("ledger is poisoned or already terminal; no continuation is allowed")
            if self._stage_b_complete and event != "terminal":
                raise RuntimeError("ledger cannot continue after the durable Stage B completion event")
            if event == "invocation_started":
                invocation_id = payload.get("invocation_id")
                started_ns = payload.get("monotonic_ns")
                if (
                    self._invocation_id is not None
                    or not isinstance(invocation_id, str)
                    or not invocation_id
                    or type(started_ns) is not int
                    or started_ns <= 0
                ):
                    raise PermissionError("invocation start must be bound exactly once to a valid id and monotonic time")
            elif self._invocation_id is not None and payload.get("invocation_id") not in (None, self._invocation_id):
                raise PermissionError("ledger event invocation identity differs from its frozen start")
            body = {
                "seq": self._seq,
                "event": event,
                "payload": payload,
                "previous_sha256": self._tail,
            }
            encoded_body = _canonical(body)
            digest = hashlib.sha256(encoded_body).hexdigest()
            line = _canonical({"entry": body, "sha256": digest}) + b"\n"
            try:
                written = os.write(self._fd, line)
                if written != len(line):
                    raise OSError("partial ledger append")
                os.fsync(self._fd)
            except BaseException:
                self._poisoned = True
                raise
            self._tail = digest
            self._seq += 1
            if event == "invocation_started":
                self._invocation_id = invocation_id
                self._invocation_started_monotonic_ns = started_ns
            return digest

    def _append_durable(self, event: str, payload: dict[str, object]) -> DurableEventReceipt:
        digest = self.append(event, payload)
        return DurableEventReceipt(digest, time.monotonic_ns())

    def _require_invocation(self, invocation_id: str) -> None:
        if (
            not isinstance(invocation_id, str)
            or not invocation_id
            or self._invocation_id is None
            or invocation_id != self._invocation_id
        ):
            raise PermissionError("stage event is not bound to the started ledger invocation")

    def mark_stage_a_finished(self, payload: dict[str, object]) -> DurableEventReceipt:
        expected = {
            "invocation_id", "reference_roles", "treatment_roles",
            "different_treatment_roles", "stage_a_disk_bytes", "finished_monotonic_ns",
        }
        if self._stage_a_finished or set(payload) != expected:
            raise RuntimeError("Stage A boundary event is incomplete or already recorded")
        self._require_invocation(payload["invocation_id"])
        if (
            type(payload["reference_roles"]) is not int
            or payload["reference_roles"] != 105
            or type(payload["treatment_roles"]) is not int
            or payload["treatment_roles"] != 105
            or type(payload["different_treatment_roles"]) is not int
            or not 0 <= payload["different_treatment_roles"] <= 105
            or type(payload["stage_a_disk_bytes"]) is not int
            or payload["stage_a_disk_bytes"] < 0
            or type(payload["finished_monotonic_ns"]) is not int
            or payload["finished_monotonic_ns"] <= (self._invocation_started_monotonic_ns or 0)
        ):
            raise PermissionError("Stage A boundary event does not meet the frozen role and time contract")
        receipt = self._append_durable("stage_a_finished", payload)
        self._stage_a_finished = True
        return receipt

    def reserve_candidate_reconstruction(self, stage: str, role_id: str) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("candidate reservations must use the ledger owner thread")
        if stage == "reference":
            if self._treatment_roles:
                raise RuntimeError("all reference roles must precede every treatment role")
            if role_id in self._reference_roles or len(self._reference_roles) >= 105:
                raise RuntimeError("candidate reference role reservation is duplicated/exhausted")
        elif stage == "treatment":
            if len(self._reference_passed) != 105:
                raise RuntimeError("treatment is blocked until all 105 references pass")
            if role_id not in self._reference_roles or role_id in self._treatment_roles:
                raise RuntimeError("treatment role is unregistered or already reserved")
            if len(self._treatment_roles) >= 105:
                raise RuntimeError("candidate treatment role reservation is exhausted")
        else:
            raise ValueError("candidate reconstruction stage must be reference or treatment")
        attempt = 1 + (len(self._reference_roles) if stage == "reference" else len(self._treatment_roles))
        self.append(
            "candidate_reconstruction_reserved",
            {"stage": stage, "role_id": role_id, "attempt": attempt},
        )
        (self._reference_roles if stage == "reference" else self._treatment_roles).add(role_id)

    def mark_reference_passed(self, role_id: str, *, candidate_count: int, fingerprint: str) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("reference result must use the ledger owner thread")
        if role_id not in self._reference_roles or role_id in self._reference_passed:
            raise RuntimeError("reference pass has no unique prior reservation")
        if candidate_count < 0 or len(fingerprint) != 64:
            raise ValueError("reference pass evidence is incomplete")
        self.append(
            "reference_role_passed",
            {"role_id": role_id, "candidate_count": candidate_count, "interval_fingerprint": fingerprint},
        )
        self._reference_passed.add(role_id)

    def mark_treatment_finished(
        self,
        receipt: CandidateFileReceipt,
        *,
        interval_set_same: bool,
    ) -> None:
        """Persist one completed treatment and its exact Stage B input file."""

        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("treatment result must use the ledger owner thread")
        if type(receipt) is not CandidateFileReceipt or type(interval_set_same) is not bool:
            raise TypeError("treatment completion requires an exact candidate receipt and comparison")
        if receipt.role_id not in self._treatment_roles or receipt.role_id in self._treatment_finished:
            raise RuntimeError("treatment completion has no unique prior reservation")
        file_path = self._study_output(Path(receipt.path))
        if (
            file_path.stat().st_size != receipt.file_bytes
            or self._hash_file(file_path) != receipt.sha256.lower()
        ):
            raise ValueError("persisted treatment candidate file differs from its receipt")
        self.append(
            "treatment_role_finished",
            {**asdict(receipt), "interval_set_same": interval_set_same},
        )
        self._treatment_finished[receipt.role_id] = receipt
        if not interval_set_same:
            self._different_treatment_roles.add(receipt.role_id)

    def require_frozen_candidate(self, receipt: CandidateFileReceipt) -> None:
        """Bind Stage B to the live treatment ledger and detect mutation."""

        if type(receipt) is not CandidateFileReceipt or self._treatment_finished.get(receipt.role_id) != receipt:
            raise PermissionError("candidate receipt is absent from the live treatment ledger")
        file_path = self._study_output(Path(receipt.path))
        if (
            file_path.stat().st_size != receipt.file_bytes
            or self._hash_file(file_path) != receipt.sha256.lower()
        ):
            raise PermissionError("treatment candidate file changed after freezing")

    def reserve_call(self, kind: str, role_id: str) -> int:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("call reservations must use the ledger owner thread")
        if kind not in CALL_CEILINGS:
            if kind in {"candidate_fit", "candidate_predict"}:
                raise PermissionError("candidate models are forbidden in this study")
            raise ValueError(f"unknown budgeted call: {kind}")
        if not role_id:
            raise ValueError("call must be bound to a nonempty role")
        with self._guard:
            count = self._call_counts[kind]
            if count >= CALL_CEILINGS[kind]:
                raise RuntimeError(f"{kind} call ceiling is exhausted")
            self.append(
                "call_reserved",
                {"kind": kind, "role_id": role_id, "attempt": count + 1, "ceiling": CALL_CEILINGS[kind]},
            )
            self._call_counts[kind] = count + 1
            self._call_state[(kind, count + 1)] = (role_id, "reserved")
            return count + 1

    def start_call(self, kind: str, role_id: str, attempt: int) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("call start must use the ledger owner thread")
        if self._call_state.get((kind, attempt)) != (role_id, "reserved"):
            raise RuntimeError("call start has no unique, matching reservation")
        self.append("call_started", {"kind": kind, "role_id": role_id, "attempt": attempt})
        self._call_state[(kind, attempt)] = (role_id, "started")

    def finish_call(self, kind: str, role_id: str, attempt: int, *, succeeded: bool) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("call finish must use the ledger owner thread")
        if self._call_state.get((kind, attempt)) != (role_id, "started"):
            raise RuntimeError("call finish has no matching started attempt")
        outcome = "succeeded" if succeeded else "failed"
        self.append("call_finished", {"kind": kind, "role_id": role_id, "attempt": attempt, "outcome": outcome})
        self._call_state[(kind, attempt)] = (role_id, outcome)

    def _study_output(self, path: Path) -> Path:
        if not path.is_absolute() or path.is_symlink():
            raise PermissionError("prediction output must be an absolute, non-symlink study file")
        root = self.study_root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        if root not in resolved.parents or not resolved.is_file():
            raise PermissionError("prediction output is outside the exact study root")
        return resolved

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                digest.update(block)
        return digest.hexdigest()

    def freeze_prediction(
        self,
        *,
        phase: Literal["inner", "outer"],
        role_id: str,
        outer_id: str,
        threshold: str,
        prediction_path: Path,
        predict_attempt: int,
        decoder_attempt: int,
    ) -> PredictionFreezeReceipt:
        """Hash a persisted prediction and bind it to a successful predict call."""

        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("prediction freeze must use the ledger owner thread")
        if phase not in {"inner", "outer"} or threshold not in {"0.10", "0.25", "0.50"}:
            raise ValueError("prediction phase or frozen threshold is invalid")
        if not role_id or not outer_id:
            raise ValueError("prediction role and outer id are required")
        if self._call_state.get(("verifier_predict", predict_attempt)) != (role_id, "succeeded"):
            raise PermissionError("prediction has no completed verifier predict batch")
        if self._call_state.get(("decoder", decoder_attempt)) != (role_id, "succeeded"):
            raise PermissionError("prediction has no completed decoder call")
        key = (phase, role_id, outer_id, threshold)
        if key in self._frozen_predictions:
            raise RuntimeError("prediction receipt is already frozen")
        exact_path = self._study_output(prediction_path)
        file_hash = self._hash_file(exact_path)
        payload: dict[str, object] = {
            "phase": phase,
            "role_id": role_id,
            "outer_id": outer_id,
            "threshold": threshold,
            "prediction_path": str(exact_path),
            "prediction_sha256": file_hash,
            "predict_attempt": predict_attempt,
            "decoder_attempt": decoder_attempt,
        }
        event_hash = self.append("prediction_frozen", payload)
        receipt = PredictionFreezeReceipt(
            phase=phase,
            role_id=role_id,
            outer_id=outer_id,
            threshold=threshold,
            prediction_path=str(exact_path),
            prediction_sha256=file_hash,
            predict_attempt=predict_attempt,
            decoder_attempt=decoder_attempt,
            ledger_event_sha256=event_hash,
        )
        self._frozen_predictions[key] = receipt
        return receipt

    def require_frozen_prediction(
        self,
        receipt: PredictionFreezeReceipt,
        *,
        phase: Literal["inner", "outer"],
        role_id: str,
        outer_id: str,
        threshold: str,
    ) -> None:
        """Check the live ledger binding and detect output mutation before GT opens."""

        key = (phase, role_id, outer_id, threshold)
        if self._frozen_predictions.get(key) != receipt:
            raise PermissionError("prediction receipt does not match the live append-only ledger")
        if receipt.ledger_event_sha256 == ZERO_HASH or not receipt.ledger_event_sha256:
            raise PermissionError("prediction receipt has no persisted ledger event")
        exact_path = self._study_output(Path(receipt.prediction_path))
        if self._hash_file(exact_path) != receipt.prediction_sha256:
            raise PermissionError("frozen prediction output changed before evaluation GT opened")

    def mark_stage_b_entry(
        self, projection: dict[str, int], *, invocation_id: str,
    ) -> DurableEventReceipt:
        if not self._stage_a_finished or self._stage_b_entry_passed:
            raise RuntimeError("Stage B entry can only be recorded once")
        self._require_invocation(invocation_id)
        receipt = self._append_durable("stage_b_entry_passed", {
            "invocation_id": invocation_id,
            "projection": projection,
        })
        self._stage_b_entry_passed = True
        self._stage_b_entry_event_hash = receipt.event_sha256
        return receipt

    def mark_stage_b_volume_expanded(
        self,
        entry_event_sha256: str,
        volume: dict[str, object],
        *,
        invocation_id: str,
    ) -> DurableEventReceipt:
        if (
            not self._stage_b_entry_passed
            or self._stage_b_entry_event_hash != entry_event_sha256
            or self._stage_b_volume_expanded
            or self._active_gt_release is not None
        ):
            raise PermissionError("Stage B volume expansion lacks its unique entry gate")
        self._require_invocation(invocation_id)
        receipt = self._append_durable("stage_b_volume_expanded", {
            "invocation_id": invocation_id,
            "entry_event_sha256": entry_event_sha256,
            "volume": volume,
        })
        self._stage_b_volume_expanded = True
        return receipt

    def mark_stage_b_complete(self, payload: dict[str, object]) -> DurableEventReceipt:
        expected = {
            "invocation_id", "inner_roles_completed", "outer_roles_completed",
            "verifier_fit_calls", "verifier_predict_calls", "decoder_calls",
            "evaluator_calls", "pooled_aggregation_completed", "pooled_gt_reads",
            "finished_monotonic_ns", "result_sha256",
        }
        if not self._stage_b_volume_expanded or self._stage_b_complete or self._active_gt_release is not None:
            raise PermissionError("Stage B completion requires the expanded volume and no active GT view")
        if set(payload) != expected:
            raise ValueError("Stage B completion event schema is incomplete or unknown")
        self._require_invocation(payload["invocation_id"])
        quota_fields = (
            "inner_roles_completed", "outer_roles_completed", "verifier_fit_calls",
            "verifier_predict_calls", "decoder_calls", "evaluator_calls", "pooled_gt_reads",
        )
        if (
            any(type(payload[name]) is not int for name in quota_fields)
            or (payload["inner_roles_completed"], payload["outer_roles_completed"],
                payload["verifier_fit_calls"], payload["verifier_predict_calls"],
                payload["decoder_calls"], payload["evaluator_calls"], payload["pooled_gt_reads"])
            != (20, 5, 25, 25, 65, 21, 0)
            or payload["pooled_aggregation_completed"] is not True
            or type(payload["finished_monotonic_ns"]) is not int
            or payload["finished_monotonic_ns"] <= (self._invocation_started_monotonic_ns or 0)
            or not isinstance(payload["result_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", payload["result_sha256"])
        ):
            raise PermissionError("Stage B completion does not meet the fixed quota and pooled no-GT contract")
        receipt = self._append_durable("stage_b_complete", payload)
        self._stage_b_complete = True
        return receipt

    @staticmethod
    def _truth_scope_digest(scope: "TruthReadScope") -> str:
        from .gt_provider import TruthReadScope

        if type(scope) is not TruthReadScope:
            raise PermissionError("GT release requires the exact reviewed truth scope")
        return hashlib.sha256(_canonical(asdict(scope))).hexdigest()

    def record_gt_release(self, scope: "TruthReadScope") -> str:
        """Persist a one-view release after the exact prediction freeze barrier."""

        from .contracts import StudyStage

        if not self._stage_b_volume_expanded or self._active_gt_release is not None:
            raise PermissionError("GT release requires Stage B expansion and no prior active view")
        scope_digest = self._truth_scope_digest(scope)
        prediction_hashes: list[str] = []
        if scope.stage == StudyStage.TRAIN_LABELS:
            if scope.prediction_receipt is not None or len(scope.role_ids) != 1:
                raise PermissionError("training GT release is not role scoped")
        elif scope.stage in (StudyStage.INNER_EVALUATION, StudyStage.OUTER_EVALUATION):
            prediction = scope.prediction_receipt
            if prediction is None:
                raise PermissionError("evaluation GT release lacks frozen predictions")
            expected = 12 if scope.stage == StudyStage.INNER_EVALUATION else 1
            if len(prediction.predictions) != expected:
                raise PermissionError("evaluation GT release lacks the full prediction barrier")
            phase = "inner" if expected == 12 else "outer"
            for item in prediction.predictions:
                self.require_frozen_prediction(
                    item, phase=phase, role_id=item.role_id,
                    outer_id=scope.outer_id, threshold=item.threshold,
                )
                prediction_hashes.append(item.ledger_event_sha256)
        else:
            raise PermissionError("Stage A has no GT release")
        digest = self.append("gt_phase_released", {
            "scope_sha256": scope_digest,
            "stage": scope.stage.value,
            "outer_id": scope.outer_id,
            "role_ids": list(scope.role_ids),
            "prediction_event_sha256": prediction_hashes,
        })
        self._active_gt_release = digest
        return digest

    def record_gt_revoke(
        self, scope: "TruthReadScope", release_event_sha256: str, os_revoke_receipt_sha256: str,
    ) -> str:
        """Record OS-observed teardown; the controller must attest it independently."""

        if self._active_gt_release != release_event_sha256:
            raise PermissionError("GT revoke differs from the sole active view")
        if len(os_revoke_receipt_sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in os_revoke_receipt_sha256.lower()
        ):
            raise PermissionError("OS GT mount teardown receipt is missing")
        digest = self.append("gt_phase_view_revoked", {
            "scope_sha256": self._truth_scope_digest(scope),
            "release_event_sha256": release_event_sha256,
            "os_revoke_receipt_sha256": os_revoke_receipt_sha256.lower(),
        })
        self._active_gt_release = None
        return digest

    def require_gt_release(self, scope: "TruthReadScope", release_event_sha256: str) -> None:
        """Rebuild the durable ledger chain, including in a fresh phase child."""

        expected_scope = self._truth_scope_digest(scope)
        if len(release_event_sha256) != 64:
            raise PermissionError("GT release hash is missing")
        previous = ZERO_HASH
        entry_passed = False
        entry_event_sha256: str | None = None
        volume_expanded = False
        prediction_events: dict[str, dict[str, object]] = {}
        completed_calls: set[tuple[str, str, int]] = set()
        release_found = False
        release_revoked = False
        with self.path.open("rb") as source:
            for line in source:
                record = json.loads(line)
                body = record["entry"]
                digest = record["sha256"]
                if body["previous_sha256"] != previous or hashlib.sha256(_canonical(body)).hexdigest() != digest:
                    raise PermissionError("GT release ledger chain is invalid")
                previous = digest
                event = body["event"]
                payload = body["payload"]
                if event == "stage_b_entry_passed":
                    entry_passed = True
                    entry_event_sha256 = digest
                elif event == "stage_b_volume_expanded":
                    if not entry_passed or payload.get("entry_event_sha256") != entry_event_sha256:
                        raise PermissionError("GT release lacks its Stage B volume transition")
                    volume_expanded = True
                elif event == "call_finished" and payload.get("outcome") == "succeeded":
                    completed_calls.add((payload["kind"], payload["role_id"], payload["attempt"]))
                elif event == "prediction_frozen":
                    if (
                        ("verifier_predict", payload["role_id"], payload["predict_attempt"]) not in completed_calls
                        or ("decoder", payload["role_id"], payload["decoder_attempt"]) not in completed_calls
                    ):
                        raise PermissionError("frozen prediction lacks completed predict/decoder calls")
                    prediction_events[digest] = payload
                elif event == "gt_phase_released" and digest == release_event_sha256:
                    expected_predictions = (
                        set() if scope.prediction_receipt is None
                        else {item.ledger_event_sha256 for item in scope.prediction_receipt.predictions}
                    )
                    if (
                        not entry_passed
                        or not volume_expanded
                        or payload["scope_sha256"] != expected_scope
                        or payload["stage"] != scope.stage.value
                        or payload["outer_id"] != scope.outer_id
                        or payload["role_ids"] != list(scope.role_ids)
                        or set(payload["prediction_event_sha256"]) != expected_predictions
                        or len(payload["prediction_event_sha256"]) != len(expected_predictions)
                        or not expected_predictions <= prediction_events.keys()
                    ):
                        raise PermissionError("GT release lacks the frozen phase barrier")
                    release_found = True
                elif event == "gt_phase_view_revoked" and payload.get("release_event_sha256") == release_event_sha256:
                    release_revoked = True
        if not release_found or release_revoked:
            raise PermissionError("GT release is absent or already revoked")
        if scope.prediction_receipt is not None:
            for item in scope.prediction_receipt.predictions:
                expected_payload = asdict(item)
                expected_payload.pop("ledger_event_sha256")
                if prediction_events.get(item.ledger_event_sha256) != expected_payload:
                    raise PermissionError("frozen prediction receipt differs from the durable ledger")
                exact_path = self._study_output(Path(item.prediction_path))
                if self._hash_file(exact_path) != item.prediction_sha256.lower():
                    raise PermissionError("frozen prediction changed after GT release")

    def terminal(
        self,
        status: str,
        *,
        evidence: dict[str, object],
        invocation_started_monotonic_ns: int,
    ) -> str:
        """Persist one terminal event; any missing event after a crash is incomplete."""

        if status not in {item.value for item in StudyStatus}:
            raise ValueError("unknown Route 2 terminal status")
        if self._active_gt_release is not None:
            raise RuntimeError("active GT view must have an OS-confirmed revoke before terminal")
        if any(state in {"reserved", "started"} for _, state in self._call_state.values()):
            if status != "INCOMPLETE_RESOURCE":
                raise RuntimeError("unfinished call attempts require INCOMPLETE_RESOURCE")
        if status == StudyStatus.COMPLETE.value:
            if (
                not self._stage_a_finished
                or not self._stage_b_complete
                or len(self._reference_passed) != 105
                or len(self._treatment_roles) != 105
                or any(self._call_counts[kind] != ceiling for kind, ceiling in CALL_CEILINGS.items())
                or any(state != "succeeded" for _, state in self._call_state.values())
            ):
                raise RuntimeError("COMPLETE requires all paired roles and frozen call ceilings")
        if type(invocation_started_monotonic_ns) is not int or invocation_started_monotonic_ns <= 0:
            raise ValueError("terminal event requires the frozen invocation monotonic start")
        terminal_monotonic_ns = time.monotonic_ns()
        if terminal_monotonic_ns < invocation_started_monotonic_ns:
            raise RuntimeError("terminal monotonic time precedes invocation start")
        digest = self.append(
            "terminal",
            {
                "status": status,
                "evidence": evidence,
                "wall_ns": terminal_monotonic_ns - invocation_started_monotonic_ns,
                "monotonic_ns": terminal_monotonic_ns,
                "epoch_ns": time.time_ns(),
            },
        )
        self._terminal = True
        self._terminal_sha256 = digest
        return digest

    def close(self) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise RuntimeError("ledger close must use the owner thread")
        if self._fd is not None:
            os.fsync(self._fd)
            os.close(self._fd)
            self._fd = None
            self._closed_at_monotonic_ns = time.monotonic_ns()

    @property
    def terminal_sha256(self) -> str:
        if self._fd is not None or not self._terminal_sha256:
            raise RuntimeError("terminal hash is unavailable before ledger close")
        return self._terminal_sha256

    @property
    def closed_at_monotonic_ns(self) -> int:
        if self._fd is not None or self._closed_at_monotonic_ns is None:
            raise RuntimeError("terminal close time is unavailable before ledger close")
        return self._closed_at_monotonic_ns


class BudgetGuard:
    def __init__(
        self,
        limits: BudgetLimits,
        ledger: AppendOnlyLedger,
        enforcer: ResourceEnforcer,
        study_root: Path,
        *,
        approved_controller_sha256: str,
        approved_write_volumes: tuple[str, ...],
        invocation_started_monotonic_ns: int,
        invocation_id: str,
    ):
        if enforcer is None:
            raise RuntimeError("no independent OS-level resource enforcer is installed")
        if ledger.study_root != study_root:
            raise ValueError("resource guard and budget ledger must bind the same exact study root")
        if (
            len(approved_controller_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in approved_controller_sha256.lower())
            or len(approved_write_volumes) != 1
            or not isinstance(invocation_id, str)
            or not invocation_id
        ):
            raise PermissionError("the reviewed controller and covered volumes must be frozen")
        self.limits = limits
        self.ledger = ledger
        self.enforcer = enforcer
        self.study_root = study_root
        self.approved_controller_sha256 = approved_controller_sha256.lower()
        self.approved_write_volumes = tuple(approved_write_volumes)
        self.invocation_id = invocation_id
        # Conservatively count all preflight work after guard construction.
        if (
            type(invocation_started_monotonic_ns) is not int
            or invocation_started_monotonic_ns <= 0
            or invocation_started_monotonic_ns > time.monotonic_ns()
        ):
            raise ValueError("outer invocation clock must start before guard construction")
        self._invocation_started_ns: int | None = invocation_started_monotonic_ns
        self._start_entered = False
        self._stage_a_finished_ns: int | None = None
        self._fit_wall_ns = 0
        self._rss_ceiling_bytes: int | None = None
        self._started = False
        self._activity_open = False
        self._finished = False
        self._stage_a_snapshot: ResourceSnapshot | None = None
        self._stage_b_admitted = False
        self._volume_identity_snapshot: ResourceSnapshot | None = None
        self._stage_a_event_receipt: DurableEventReceipt | None = None
        self._stage_b_entry_event_receipt: DurableEventReceipt | None = None
        self._stage_b_expansion_event_receipt: DurableEventReceipt | None = None
        self._stage_b_completion_event_receipt: DurableEventReceipt | None = None
        self._stage_b_result_evidence: dict[str, object] | None = None
        self._boundary_failure: str | None = None

    def start(self, approval: ExperimentApproval) -> None:
        """Count from entry, verify the OS controller, then create the study once."""

        if self._start_entered:
            raise RuntimeError("startup measurement may occur only once")
        self._start_entered = True
        approval.require_full_ab()
        if (
            approval.resource_controller_sha256.lower() != self.approved_controller_sha256
            or tuple(approval.approved_write_volumes) != self.approved_write_volumes
        ):
            raise PermissionError("controller and write-volume coverage differ from the frozen A+B approval")
        self.ledger._require_exact_paths()
        if (
            str(self.study_root) != approval.study_root_path
            or str(self.ledger.path) != approval.budget_ledger_path
            or str(self.ledger.lock_path) != approval.lock_path
        ):
            raise PermissionError("resource guard paths differ from the frozen A+B approval")
        receipt, snapshot = self.enforcer.prepare_volume(
            self.study_root, self.ledger.path, self.ledger.lock_path, self.limits,
            self._invocation_started_ns or 0,
        )
        receipt.require_complete()
        require_precreate_order(
            self._invocation_started_ns or 0,
            receipt.precreate_free_checked_monotonic_ns,
            receipt.image_created_monotonic_ns,
            receipt.precreate_guest_free_bytes,
            receipt.precreate_windows_volume_free_bytes,
            self.limits.startup_free_disk_bytes,
        )
        if receipt.controller_sha256.lower() != self.approved_controller_sha256:
            raise PermissionError("OS controller implementation differs from the approved digest")
        if receipt.invocation_started_monotonic_ns != self._invocation_started_ns:
            raise PermissionError("OS controller receipt differs from the outer invocation clock")
        if (
            receipt.study_root != str(self.study_root)
            or receipt.study_image_path != approval.study_image_path
            or receipt.ledger_path != str(self.ledger.path)
            or receipt.lock_path != str(self.ledger.lock_path)
            or tuple(receipt.covered_write_volumes) != self.approved_write_volumes
        ):
            raise PermissionError("OS controller receipt does not cover the exact approved paths/volumes")
        study_volume = str(self.study_root.parent.resolve(strict=True))
        if study_volume not in self.approved_write_volumes:
            raise PermissionError("study output volume is absent from OS controller coverage")
        # The receipt is a capability claim, not independent proof.  Its provider
        # must be reviewed and bound to the separate human approval record.
        require_two_layer_startup_free(snapshot, self.limits)
        if (
            snapshot.guest_backing_mount_id != receipt.guest_backing_mount_id
            or snapshot.windows_volume_id != receipt.windows_volume_id
            or snapshot.study_fs_capacity_bytes > self.limits.stage_a_disk_bytes
            or receipt.stage_a_capacity_bytes > self.limits.stage_a_disk_bytes
            or receipt.total_capacity_bytes > self.limits.total_disk_bytes
            or not snapshot.study_mount_id
            or not snapshot.study_device
            or snapshot.study_fs_uuid != receipt.study_fs_uuid
            or snapshot.study_loop_device != receipt.study_loop_device
            or snapshot.study_image_path != receipt.study_image_path
            or snapshot.study_image_dev != receipt.study_image_dev
            or snapshot.study_image_inode != receipt.study_image_inode
            or snapshot.study_image_length_bytes != receipt.study_image_length_bytes
        ):
            raise PermissionError("backing identity or Stage A filesystem hard limit differs from approval")
        require_stage_filesystem(snapshot, snapshot, self.limits.stage_a_disk_bytes)
        self._volume_identity_snapshot = snapshot
        if snapshot.available_ram_bytes <= 0:
            raise RuntimeError("startup available-RAM sample is invalid")
        self._rss_ceiling_bytes = min(
            self.limits.rss_cap_bytes,
            (3 * snapshot.available_ram_bytes) // 5,
        )
        if (
            receipt.pids_max > self.limits.worker_limit
            or receipt.pids_max < 1
            or receipt.rlimit_as_per_process_bytes < 1
            or receipt.rlimit_as_per_process_bytes * receipt.pids_max > self._rss_ceiling_bytes
            or receipt.memory_max_bytes > self._rss_ceiling_bytes
            or receipt.memory_swap_max_bytes != 0
        ):
            raise PermissionError("reviewed RSS/task hard limits do not imply the frozen study ceiling")
        if snapshot.process_tree_rss_bytes > self._rss_ceiling_bytes:
            raise RuntimeError("startup process-tree RSS already exceeds the frozen ceiling")
        if snapshot.compute_workers > self.limits.worker_limit:
            raise RuntimeError("worker ceiling is already exceeded")
        if snapshot.study_disk_peak_bytes > self.limits.stage_a_disk_bytes:
            raise RuntimeError("Stage A disk ceiling is already exceeded at startup")
        self.ledger.create(approval, self.limits)
        self.ledger.append(
            "invocation_started",
            {
                "invocation_id": self.invocation_id,
                "monotonic_ns": self._invocation_started_ns,
                "controller_receipt": asdict(receipt),
                "startup_snapshot": asdict(snapshot),
                "frozen_rss_ceiling_bytes": self._rss_ceiling_bytes,
            },
        )
        self._started = True
        self._check(self.enforcer.current_snapshot(self.study_root))

    def _elapsed_ns(self) -> int:
        if self._invocation_started_ns is None:
            raise RuntimeError("study invocation has not started")
        return time.monotonic_ns() - self._invocation_started_ns

    def _remaining(self, ceiling: int, spent: int, kind: str) -> int:
        remaining = ceiling - spent
        if remaining <= 0:
            raise RuntimeError(f"{kind} hard line is exhausted")
        return remaining

    @contextmanager
    def activity(self, name: str, *, stage_a: bool = False, fit: bool = False) -> Iterator[None]:
        if not self._started or self._finished:
            raise RuntimeError("budget guard must be started before activity")
        if self._boundary_failure is not None:
            raise PermissionError("activity is forbidden after a durable stage boundary failure")
        if self._stage_b_completion_event_receipt is not None:
            raise PermissionError("activity is forbidden after the Stage B completion receipt")
        if self._activity_open:
            raise RuntimeError("nested activities can hide fit or stage wall consumption")
        if stage_a != (self._stage_a_finished_ns is None):
            raise RuntimeError("activity stage does not match the persisted Stage A boundary")
        if self._rss_ceiling_bytes is None:
            raise RuntimeError("RSS ceiling is not frozen")
        elapsed = self._elapsed_ns()
        remaining_total = self._remaining(self.limits.total_wall_ns, elapsed, "total wall")
        remaining_stage = (
            self._remaining(self.limits.stage_a_wall_ns, elapsed, "Stage A wall")
            if stage_a else None
        )
        remaining_fit = (
            self._remaining(self.limits.fit_wall_ns, self._fit_wall_ns, "fit wall")
            if fit else None
        )
        handle = self.enforcer.enforce_during_activity(
            self.study_root,
            self.limits,
            name,
            remaining_total_wall_ns=remaining_total,
            remaining_stage_a_wall_ns=remaining_stage,
            remaining_fit_wall_ns=remaining_fit,
            frozen_rss_ceiling_bytes=self._rss_ceiling_bytes,
        )
        self._activity_open = True
        started_ns = time.monotonic_ns()
        try:
            self.ledger.append("activity_started", {"name": name, "monotonic_ns": started_ns, "fit": fit, "stage_a": stage_a})
        except BaseException:
            self._activity_open = False
            self.enforcer.stop_activity(handle)
            raise
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            ended_ns = time.monotonic_ns()
            try:
                snapshot = self.enforcer.stop_activity(handle)
            finally:
                self._activity_open = False
            if fit:
                self._fit_wall_ns += time.monotonic_ns() - started_ns
            self.ledger.append(
                "activity_finished",
                {
                    "name": name,
                    "monotonic_ns": ended_ns,
                    "elapsed_ns": time.monotonic_ns() - started_ns,
                    "invocation_wall_ns": self._elapsed_ns(),
                    "fit_wall_ns": self._fit_wall_ns,
                    "failed": failed,
                    "snapshot": asdict(snapshot),
                },
            )
            self._check(snapshot)

    def invoke_call(self, kind: str, role_id: str, operation: Callable[[], T]) -> tuple[int, T]:
        """Reserve, invoke exactly once, and persist the actual call outcome."""

        if self._boundary_failure is not None:
            raise PermissionError("calls are forbidden after a durable stage boundary failure")
        if self._stage_b_completion_event_receipt is not None:
            raise PermissionError("calls are forbidden after the Stage B completion receipt")
        if not self._stage_b_admitted:
            raise PermissionError("no verifier, decoder, or evaluator call before Stage B admission")
        attempt = self.ledger.reserve_call(kind, role_id)
        self.ledger.start_call(kind, role_id, attempt)
        try:
            with self.activity(
                f"{kind}:{role_id}:{attempt}",
                stage_a=False,
                fit=(kind == "verifier_fit"),
            ):
                result = operation()
        except BaseException:
            self.ledger.finish_call(kind, role_id, attempt, succeeded=False)
            raise
        self.ledger.finish_call(kind, role_id, attempt, succeeded=True)
        return attempt, result

    def finish_stage_a(self) -> ResourceSnapshot:
        if not self._started or self._stage_a_finished_ns is not None or self._activity_open:
            raise RuntimeError("Stage A may finish only once with no open activity")
        if (
            len(self.ledger._reference_passed) != 105
            or len(self.ledger._treatment_roles) != 105
            or set(self.ledger._treatment_finished) != self.ledger._treatment_roles
        ):
            raise RuntimeError("Stage A boundary requires 105 passed references and 105 frozen treatments")
        snapshot = self.enforcer.current_snapshot(self.study_root)
        self._check(snapshot)
        final_snapshot = self.enforcer.current_snapshot(self.study_root)
        self._check(final_snapshot)
        finished_ns = time.monotonic_ns()
        if not self.ledger._different_treatment_roles.issubset(self.ledger._treatment_roles):
            raise PermissionError("Stage A difference count is not bound to treatment roles")
        self._stage_a_event_receipt = self.ledger.mark_stage_a_finished({
            "invocation_id": self.invocation_id,
            "reference_roles": len(self.ledger._reference_passed),
            "treatment_roles": len(self.ledger._treatment_finished),
            "different_treatment_roles": len(self.ledger._different_treatment_roles),
            "stage_a_disk_bytes": final_snapshot.study_disk_current_bytes,
            "finished_monotonic_ns": finished_ns,
        })
        self._stage_a_finished_ns = self._stage_a_event_receipt.fsynced_monotonic_ns
        self._stage_a_snapshot = final_snapshot
        if (
            self._invocation_started_ns is None
            or finished_ns > self._invocation_started_ns + self.limits.stage_a_wall_ns
            or self._stage_a_event_receipt.fsynced_monotonic_ns
            > self._invocation_started_ns + self.limits.stage_a_wall_ns
        ):
            self._boundary_failure = "Stage A boundary append/fsync exceeded the Stage A wall deadline"
            raise RuntimeError(self._boundary_failure)
        return final_snapshot

    def require_stage_b_entry(
        self,
        projection: StageBProjection,
    ) -> None:
        require_exact_stage_b_projection(projection)
        if self._boundary_failure is not None:
            raise PermissionError("Stage B entry is forbidden after a durable stage boundary failure")
        if self._stage_b_completion_event_receipt is not None:
            raise PermissionError("Stage B entry is forbidden after the Stage B completion receipt")
        if not self._started or self._stage_a_snapshot is None or self._finished or self._stage_b_admitted:
            raise RuntimeError("Stage B projection requires persisted, complete Stage A")
        if projection.stage_a_disk_bytes_d_a != self._stage_a_snapshot.study_disk_current_bytes:
            raise RuntimeError("D_A differs from the frozen Stage A current disk observation")
        if (
            self._stage_a_event_receipt is None
            or self._invocation_started_ns is None
            or self._stage_a_event_receipt.fsynced_monotonic_ns
            > self._invocation_started_ns + self.limits.stage_a_wall_ns
        ):
            raise RuntimeError("Stage B entry requires an on-time durable Stage A boundary")
        self._check(self.enforcer.current_snapshot(self.study_root))
        require_stage_b_entry(
            projection,
            limits=self.limits,
            frozen_rss_ceiling_bytes=self.frozen_rss_ceiling_bytes,
            stage_a_hard_lines_met=True,
        )
        self._stage_b_entry_event_receipt = self.ledger.mark_stage_b_entry(
            asdict(projection), invocation_id=self.invocation_id,
        )
        stage_a_deadline = self._invocation_started_ns + self.limits.stage_a_wall_ns
        if (
            self._stage_b_entry_event_receipt.fsynced_monotonic_ns
            < self._stage_a_event_receipt.fsynced_monotonic_ns
            or self._stage_b_entry_event_receipt.fsynced_monotonic_ns > stage_a_deadline
        ):
            self._boundary_failure = "Stage B entry append/fsync exceeded the Stage A wall deadline"
            raise RuntimeError(self._boundary_failure)
        entry_hash = self._stage_b_entry_event_receipt.event_sha256
        expanded = self.enforcer.expand_after_stage_b_entry(
            self.study_root, self.limits, entry_hash,
        )
        if self._volume_identity_snapshot is None:
            raise RuntimeError("study volume identity was not frozen before expansion")
        require_stage_filesystem(
            expanded, self._volume_identity_snapshot,
            self.limits.total_disk_bytes,
        )
        if expanded.study_fs_capacity_bytes <= self.limits.stage_a_disk_bytes:
            raise RuntimeError("Stage B filesystem did not expand after its entry gate")
        volume = {
            "invocation_id": self.invocation_id,
            "study_id": STUDY_ID,
            "study_root_path": str(self.study_root),
            "ledger_path": str(self.ledger.path),
            "lock_path": str(self.ledger.lock_path),
            "image_path": expanded.study_image_path,
            "created_monotonic_ns": time.monotonic_ns(),
            "image_device": expanded.study_image_dev,
            "image_inode": expanded.study_image_inode,
            "loop_device": expanded.study_loop_device,
            "filesystem_uuid": expanded.study_fs_uuid,
            "mount_id": expanded.study_mount_id,
            "filesystem_device": expanded.study_device,
            "filesystem_capacity_bytes": expanded.study_fs_capacity_bytes,
            "image_length_bytes": expanded.study_image_length_bytes,
        }
        self._stage_b_expansion_event_receipt = self.ledger.mark_stage_b_volume_expanded(
            entry_hash, volume, invocation_id=self.invocation_id,
        )
        created_ns = volume["created_monotonic_ns"]
        entry_fsynced_ns = self._stage_b_entry_event_receipt.fsynced_monotonic_ns
        expansion_fsynced_ns = self._stage_b_expansion_event_receipt.fsynced_monotonic_ns
        total_deadline = self._invocation_started_ns + self.limits.total_wall_ns
        if (
            type(created_ns) is not int
            or type(entry_fsynced_ns) is not int
            or type(expansion_fsynced_ns) is not int
            or created_ns < entry_fsynced_ns
            or expansion_fsynced_ns < created_ns
            or expansion_fsynced_ns > total_deadline
        ):
            self._boundary_failure = "Stage B expansion append/fsync is outside its durable wall boundary"
            raise RuntimeError(self._boundary_failure)
        self._stage_b_admitted = True
        self._check(expanded)

    def finish_stage_b(self, result: object) -> None:
        """Persist the unique COMPLETE payload after the fixed Stage B protocol succeeds."""

        from .stage_b import StageBResult

        if (
            not self._started or not self._stage_b_admitted or self._finished
            or self._activity_open or self._stage_b_completion_event_receipt is not None
        ):
            raise RuntimeError("Stage B completion requires one admitted, inactive invocation")
        if self._boundary_failure is not None:
            raise PermissionError("Stage B completion is forbidden after a durable stage boundary failure")
        if type(result) is not StageBResult or result.status is not StudyStatus.COMPLETE:
            raise ValueError("Stage B completion requires the exact successful result type")
        snapshot = self.enforcer.current_snapshot(self.study_root)
        self._check(snapshot)
        integer_fields = (
            result.pooled_gt_count,
            result.verifier_fit_attempts,
            result.verifier_prediction_batches,
            result.decoder_calls,
            result.evaluator_calls,
            result.pooled_gt_reads,
        )
        if (
            len(result.selected_thresholds) != 5
            or len(result.fold_metrics) != 5
            or len(result.outer_candidate_counts) != 5
            or len(result.outer_candidate_covered_gt) != 5
            or any(type(value) is not int for value in integer_fields)
            or result.pooled_gt_count != 234
            or result.verifier_fit_attempts != 25
            or result.verifier_prediction_batches != 25
            or result.decoder_calls != 65
            or result.evaluator_calls != 21
            or result.pooled_aggregation_completed is not True
            or result.pooled_gt_reads != 0
        ):
            raise PermissionError("Stage B result differs from the fixed role, call, or pooled no-GT protocol")
        result_sha256 = hashlib.sha256(_canonical(asdict(result))).hexdigest()
        finished_ns = time.monotonic_ns()
        if (
            self._invocation_started_ns is None
            or finished_ns > self._invocation_started_ns + self.limits.total_wall_ns
        ):
            raise RuntimeError("Stage B computation exceeded the total active-wall deadline")
        payload = {
            "invocation_id": self.invocation_id,
            # Five outer decisions each complete four nested inner roles.
            # selected_thresholds has one item per outer fold, not one per
            # inner held-out role.
            "inner_roles_completed": 20,
            "outer_roles_completed": len(result.fold_metrics),
            "verifier_fit_calls": result.verifier_fit_attempts,
            "verifier_predict_calls": result.verifier_prediction_batches,
            "decoder_calls": result.decoder_calls,
            "evaluator_calls": result.evaluator_calls,
            "pooled_aggregation_completed": result.pooled_aggregation_completed,
            "pooled_gt_reads": result.pooled_gt_reads,
            "finished_monotonic_ns": finished_ns,
            "result_sha256": result_sha256,
        }
        self._stage_b_result_evidence = asdict(result)
        self._stage_b_completion_event_receipt = self.ledger.mark_stage_b_complete(payload)
        if (
            self._stage_b_completion_event_receipt.fsynced_monotonic_ns < finished_ns
            or self._stage_b_completion_event_receipt.fsynced_monotonic_ns
            > self._invocation_started_ns + self.limits.total_wall_ns
        ):
            self._boundary_failure = "Stage B completion append/fsync exceeded the total active-wall deadline"
            raise RuntimeError(self._boundary_failure)

    def _check(self, snapshot: ResourceSnapshot) -> None:
        if self._rss_ceiling_bytes is None:
            raise RuntimeError("RSS ceiling was not frozen at startup")
        if self._volume_identity_snapshot is None:
            raise RuntimeError("study volume identity was not frozen at startup")
        require_stage_filesystem(
            snapshot, self._volume_identity_snapshot,
            self.limits.total_disk_bytes if self._stage_b_admitted else self.limits.stage_a_disk_bytes,
        )
        if snapshot.process_tree_rss_bytes > self._rss_ceiling_bytes:
            raise RuntimeError("process-tree RSS hard line exceeded")
        if snapshot.study_disk_peak_bytes > self.limits.total_disk_bytes:
            raise RuntimeError("study disk hard line exceeded")
        if self._stage_a_finished_ns is None and snapshot.study_disk_peak_bytes > self.limits.stage_a_disk_bytes:
            raise RuntimeError("Stage A disk hard line exceeded")
        if snapshot.compute_workers > self.limits.worker_limit:
            raise RuntimeError("compute worker hard line exceeded")
        if self._elapsed_ns() > self.limits.total_wall_ns:
            raise RuntimeError("total active-wall hard line exceeded")
        if self._stage_a_finished_ns is None and self._elapsed_ns() > self.limits.stage_a_wall_ns:
            raise RuntimeError("Stage A active-wall hard line exceeded")
        if self._fit_wall_ns > self.limits.fit_wall_ns:
            raise RuntimeError("fit active-wall hard line exceeded")

    def finalize(self, status: str, *, evidence: dict[str, object]) -> str:
        """Persist one terminal.  Missing/partial finalization is an incomplete run."""

        if not self._started or self._finished or self._activity_open:
            raise RuntimeError("study may finalize once after all activities close")
        snapshot = self.enforcer.current_snapshot(self.study_root)
        try:
            self._check(snapshot)
        except BaseException as error:
            status = "INCOMPLETE_RESOURCE"
            evidence = {**evidence, "resource_error": repr(error)}
        if self._boundary_failure is not None:
            status = "INCOMPLETE_RESOURCE"
            evidence = {**evidence, "boundary_failure": self._boundary_failure}
        if self._stage_b_completion_event_receipt is not None:
            if self._stage_b_result_evidence is None:
                raise RuntimeError("durable Stage B completion lacks its result evidence")
            existing_result = evidence.get("stage_b_result")
            if existing_result is not None and existing_result != self._stage_b_result_evidence:
                raise PermissionError("terminal Stage B result differs from the durable completion result")
            evidence = {**evidence, "stage_b_result": self._stage_b_result_evidence}
        started = self._invocation_started_ns
        if started is None:
            raise RuntimeError("invocation monotonic start is absent at terminal close")
        self.ledger.terminal(
            status,
            evidence={
                **evidence,
                "snapshot": asdict(snapshot),
                "invocation_wall_ns": self._elapsed_ns(),
                "fit_wall_ns": self._fit_wall_ns,
                "stage_a_wall_ns": (
                    self._stage_a_finished_ns - self._invocation_started_ns
                    if self._stage_a_finished_ns is not None and self._invocation_started_ns is not None
                    else self._elapsed_ns()
                ),
            },
            invocation_started_monotonic_ns=started,
        )
        self._finished = True
        self.ledger.close()
        return status

    @property
    def frozen_rss_ceiling_bytes(self) -> int:
        if self._rss_ceiling_bytes is None:
            raise RuntimeError("RSS ceiling is not frozen before startup")
        return self._rss_ceiling_bytes


@dataclass(frozen=True, slots=True)
class StageBProjection:
    candidate_rows_n: int
    maximum_fit_rows_m: int
    prediction_rows_s: int
    candidate_file_bytes_b: int
    stage_a_disk_bytes_d_a: int

    def __post_init__(self) -> None:
        values = (
            self.candidate_rows_n,
            self.maximum_fit_rows_m,
            self.prediction_rows_s,
            self.candidate_file_bytes_b,
            self.stage_a_disk_bytes_d_a,
        )
        if any(type(value) is not int for value in values):
            raise ValueError("Stage B projection values must be exact integers")
        if any(value < 0 for value in values):
            raise ValueError("Stage B projection values must be nonnegative")


def require_stage_b_entry(
    projection: StageBProjection,
    *,
    limits: BudgetLimits,
    frozen_rss_ceiling_bytes: int,
    stage_a_hard_lines_met: bool,
) -> None:
    """Apply the predeclared Stage B formula without loading GT or fitting."""

    require_exact_stage_b_projection(projection)
    if type(frozen_rss_ceiling_bytes) is not int or frozen_rss_ceiling_bytes <= 0:
        raise ValueError("frozen RSS ceiling must be a positive exact integer")
    if type(stage_a_hard_lines_met) is not bool:
        raise ValueError("Stage A hard-line result must be an exact boolean")
    disk_projection = (
        projection.stage_a_disk_bytes_d_a
        + 3 * (
            projection.candidate_file_bytes_b
            + 232 * projection.candidate_rows_n
            + 8 * projection.prediction_rows_s
        )
        + limits.stage_b_disk_slack_bytes
    )
    rss_projection = (
        limits.stage_b_rss_slack_bytes
        + 6 * 232 * projection.maximum_fit_rows_m
    )
    if not stage_a_hard_lines_met:
        raise RuntimeError("Stage A hard-line evidence is missing")
    if disk_projection > limits.total_disk_bytes:
        raise RuntimeError("Stage B disk entry formula fails")
    if rss_projection > frozen_rss_ceiling_bytes:
        raise RuntimeError("Stage B RSS entry formula fails")


def require_exact_stage_b_projection(projection: StageBProjection) -> None:
    """Reject subclasses and mutated field values at every public admission boundary."""

    if type(projection) is not StageBProjection:
        raise ValueError("Stage B projection must use the exact reviewed type")
    values = (
        projection.candidate_rows_n,
        projection.maximum_fit_rows_m,
        projection.prediction_rows_s,
        projection.candidate_file_bytes_b,
        projection.stage_a_disk_bytes_d_a,
    )
    if any(type(value) is not int for value in values):
        raise ValueError("Stage B projection values must be exact integers")
    if any(value < 0 for value in values):
        raise ValueError("Stage B projection values must be nonnegative")
