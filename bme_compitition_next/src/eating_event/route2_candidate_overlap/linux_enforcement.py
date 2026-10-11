"""Linux/systemd enforcement contracts for the WSL Route 2 supervisor.

This module contains no experiment entry point.  The helpers describe and
validate operating-system limits; a study still requires the separately
frozen admission and explicit A+B approval in ``contracts.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
from pathlib import PureWindowsPath
import re
import stat
from typing import Mapping, Sequence

from .budget import BudgetLimits
from .contracts import (
    OUTER_CONTROL_CANDIDATES_PHASE, OUTER_CONTROL_FINAL_MATCHES_PHASE, STUDY_ID, StudyStatus,
)


GIB = 1 << 30
DEFAULT_STOP_MARGIN_NS = 60_000_000_000
EXPECTED_PIDS_MAX = 2
EXPECTED_CPU_QUOTA_PERCENT = 200


@dataclass(frozen=True, slots=True)
class ResourceEnvelope:
    """The enforceable systemd/cgroup projection of one approved budget."""

    rss_cap_bytes: int
    memory_max_bytes: int
    memory_swap_max_bytes: int
    pids_max: int
    rlimit_as_per_process_bytes: int
    cpu_quota_percent: int
    total_wall_ns: int
    stage_a_wall_ns: int
    fit_wall_ns: int
    stop_margin_ns: int
    runtime_max_ns: int
    stage_a_stop_ns: int
    fit_stop_ns: int


def derive_resource_envelope(
    limits: BudgetLimits,
    *,
    available_ram_bytes: int,
    stop_margin_ns: int = DEFAULT_STOP_MARGIN_NS,
) -> ResourceEnvelope:
    """Turn the proposed RSS and wall budgets into kernel-enforced ceilings.

    ``TasksMax=2`` counts processes and threads.  With the main controller
    occupying one task, at most one child/compute task can run concurrently.
    Inherited ``RLIMIT_AS <= floor(C/2)`` gives a conservative sum-RSS bound
    of ``C`` for at most two live tasks, while cgroup ``memory.max`` is the
    independent hard backstop.
    """

    if type(limits) is not BudgetLimits:
        raise TypeError("resource envelope requires the fixed BudgetLimits type")
    if type(available_ram_bytes) is not int or available_ram_bytes <= 0:
        raise ValueError("startup available RAM must be a positive exact integer")
    if type(stop_margin_ns) is not int or stop_margin_ns < 0:
        raise ValueError("stop margin must be a nonnegative exact integer")
    if any(
        budget <= stop_margin_ns
        for budget in (limits.total_wall_ns, limits.stage_a_wall_ns, limits.fit_wall_ns)
    ):
        raise ValueError("every wall budget must leave a positive hard-stop interval")
    if limits.worker_limit != EXPECTED_PIDS_MAX:
        raise PermissionError("this controller is reviewed only for the frozen two-task limit")

    rss_cap = min(limits.rss_cap_bytes, (3 * available_ram_bytes) // 5)
    if rss_cap < 2:
        raise ValueError("available RAM cannot support a positive per-process address-space cap")
    address_space = rss_cap // 2
    if address_space <= 0:
        raise ValueError("derived per-process RLIMIT_AS is not enforceable")

    return ResourceEnvelope(
        rss_cap_bytes=rss_cap,
        memory_max_bytes=rss_cap,
        memory_swap_max_bytes=0,
        pids_max=EXPECTED_PIDS_MAX,
        rlimit_as_per_process_bytes=address_space,
        cpu_quota_percent=EXPECTED_CPU_QUOTA_PERCENT,
        total_wall_ns=limits.total_wall_ns,
        stage_a_wall_ns=limits.stage_a_wall_ns,
        fit_wall_ns=limits.fit_wall_ns,
        stop_margin_ns=stop_margin_ns,
        runtime_max_ns=limits.total_wall_ns - stop_margin_ns,
        stage_a_stop_ns=limits.stage_a_wall_ns - stop_margin_ns,
        fit_stop_ns=limits.fit_wall_ns - stop_margin_ns,
    )


def systemd_unit_properties(envelope: ResourceEnvelope) -> tuple[tuple[str, str], ...]:
    """Exact transient-service properties for the study parent unit.

    The study launcher adds its frozen ``ReadWritePaths`` and ``ExecStopPost``
    values after admission.  This base policy deliberately has no automatic
    restart and kills the complete service cgroup on timeout or failure.
    """

    if type(envelope) is not ResourceEnvelope:
        raise TypeError("systemd properties require a derived ResourceEnvelope")
    if envelope.runtime_max_ns % 1_000_000_000:
        raise ValueError("systemd runtime ceiling must be an exact whole second")
    if envelope.stop_margin_ns % 1_000_000_000:
        raise ValueError("systemd stop timeout must be an exact whole second")
    return (
        ("Type", "exec"),
        ("RemainAfterExit", "no"),
        ("Restart", "no"),
        ("KillMode", "control-group"),
        ("SendSIGKILL", "yes"),
        ("RuntimeMaxSec", f"{envelope.runtime_max_ns // 1_000_000_000}s"),
        ("TimeoutStopSec", f"{envelope.stop_margin_ns // 1_000_000_000}s"),
        ("MemoryAccounting", "yes"),
        ("MemoryMax", str(envelope.memory_max_bytes)),
        ("MemorySwapMax", str(envelope.memory_swap_max_bytes)),
        ("TasksAccounting", "yes"),
        ("TasksMax", str(envelope.pids_max)),
        ("CPUQuota", f"{envelope.cpu_quota_percent}%"),
        ("LimitAS", str(envelope.rlimit_as_per_process_bytes)),
        ("LimitCORE", "0"),
        ("NoNewPrivileges", "yes"),
        ("ProtectSystem", "strict"),
        ("ProtectHome", "yes"),
        ("ProtectKernelTunables", "yes"),
        ("ProtectKernelModules", "yes"),
        ("ProtectControlGroups", "yes"),
        ("PrivateMounts", "yes"),
        ("PrivateIPC", "yes"),
        ("LockPersonality", "yes"),
        ("ProtectHostname", "yes"),
        ("RestrictSUIDSGID", "yes"),
        ("SystemCallArchitectures", "native"),
        ("ProtectProc", "invisible"),
        # The trusted root controller needs boot_id and global kernel/resource
        # metadata. Worker services narrow this property again below.
        ("ProcSubset", "all"),
        ("PrivateTmp", "no"),
        ("PrivateDevices", "yes"),
        ("PrivateNetwork", "yes"),
        # The original parent reads targeted kernel UNIX peer diagnostics.
        # Worker properties below still narrow this family set to AF_UNIX.
        ("RestrictAddressFamilies", "AF_UNIX AF_NETLINK"),
        ("UMask", "0077"),
    )


_ACTIVE_INPUT_PHASES = frozenset({
    "preflight_metadata", "stage_a_input", "stage_a_reference",
    OUTER_CONTROL_CANDIDATES_PHASE, OUTER_CONTROL_FINAL_MATCHES_PHASE,
    "train_labels", "inner_evaluation", "outer_evaluation",
})
_GT_PHASES = frozenset({"train_labels", "inner_evaluation", "outer_evaluation"})
WORKER_SCOPE_ALIAS = "/run/route2-worker"


def _canonical_service_path(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise PermissionError(f"{what} must be an absolute Linux path")
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or path.as_posix() != value
        or ".." in path.parts
        or any(char.isspace() or ord(char) < 32 for char in value)
    ):
        raise PermissionError(f"{what} is not a canonical systemd path")
    return value


@dataclass(frozen=True, slots=True)
class StudyAccessPolicy:
    study_root: str
    ledger_path: str
    lock_path: str
    source_snapshot_root: str
    runtime_snapshot_root: str
    read_only_view_paths: tuple[str, ...]
    active_role_id: str | None
    active_phase: str | None


@dataclass(frozen=True, slots=True)
class WorkerWritePaths:
    """Deterministic, role-scoped writable paths on the study filesystem."""

    scope_sha256: str
    scope_dir: str
    scratch_dir: str
    home_dir: str
    cache_dir: str
    stdout_log: str
    stderr_log: str


def worker_write_paths(policy: StudyAccessPolicy) -> WorkerWritePaths:
    """Derive one isolated worker scratch/log namespace inside the study root.

    The privileged controller must materialize and clean these paths on the
    study volume before and after each service. No user or library temporary
    directory is allowed to fall back to the host's /tmp or /var/tmp.
    """

    if type(policy) is not StudyAccessPolicy:
        raise TypeError("worker write paths require the fixed study access policy")
    identity = {
        "study_root": policy.study_root,
        "role_id": policy.active_role_id or "__study__",
        "phase": policy.active_phase or "study",
        "read_only_views": list(policy.read_only_view_paths),
    }
    encoded = json.dumps(
        identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    scope = hashlib.sha256(encoded).hexdigest()
    root = PurePosixPath(policy.study_root) / ".worker" / scope
    values = {
        "scratch_dir": root / "tmp",
        "home_dir": root / "home",
        "cache_dir": root / "cache",
        "stdout_log": root / "logs" / "stdout.log",
        "stderr_log": root / "logs" / "stderr.log",
    }
    return WorkerWritePaths(
        scope_sha256=scope,
        scope_dir=root.as_posix(),
        **{name: path.as_posix() for name, path in values.items()},
    )


def prepare_worker_write_paths(
    policy: StudyAccessPolicy, *, owner_uid: int, owner_gid: int,
) -> WorkerWritePaths:
    """Create fresh study-volume paths owned by the unprivileged worker.

    Existing role/phase scratch is refused to avoid carrying a prior worker's
    temporary or cache data into a later release.
    """

    if os.name != "posix" or type(owner_uid) is not int or type(owner_gid) is not int:
        raise PermissionError("worker write roots require exact Linux uid/gid values")
    paths = worker_write_paths(policy)
    study_root = Path(policy.study_root)
    if study_root.is_symlink() or not study_root.is_dir():
        raise PermissionError("study root must be a real mounted directory")
    root_device = study_root.stat().st_dev
    worker_root = study_root / ".worker"
    if worker_root.exists() or worker_root.is_symlink():
        info = worker_root.lstat()
        if (
            not stat.S_ISDIR(info.st_mode) or info.st_dev != root_device
            or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o711
        ):
            raise PermissionError("worker namespace root is not a controller-owned study-volume directory")
    else:
        worker_root.mkdir(mode=0o700)
        os.chown(worker_root, 0, 0)
        os.chmod(worker_root, 0o711, follow_symlinks=False)
    info = worker_root.lstat()
    if (
        not stat.S_ISDIR(info.st_mode) or info.st_dev != root_device
        or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o711
    ):
        raise PermissionError("worker namespace root must be root-owned and traversable-only")

    scope_root = worker_root / paths.scope_sha256
    if scope_root.exists() or scope_root.is_symlink():
        raise FileExistsError("role/phase worker write namespace is already occupied")
    scope_root.mkdir(mode=0o700)
    os.chown(scope_root, owner_uid, owner_gid)
    for relative in ("tmp", "home", "cache", "logs"):
        directory = scope_root / relative
        directory.mkdir(mode=0o700)
        os.chown(directory, owner_uid, owner_gid)
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode) or info.st_dev != root_device
            or info.st_uid != owner_uid or info.st_gid != owner_gid
            or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise PermissionError("worker writable path escaped the study filesystem or has unsafe ownership")
    return paths


def cleanup_worker_write_paths(policy: StudyAccessPolicy, paths: WorkerWritePaths) -> None:
    """Remove one inactive worker namespace without traversing links or mounts."""

    expected = worker_write_paths(policy)
    if type(paths) is not WorkerWritePaths or paths != expected:
        raise PermissionError("worker cleanup paths differ from the active role/phase identity")
    study_root = Path(policy.study_root)
    root_device = study_root.stat().st_dev
    scope_root = study_root / ".worker" / paths.scope_sha256
    if scope_root.is_symlink() or not scope_root.is_dir():
        raise PermissionError("worker cleanup root is absent or linked")
    if scope_root.resolve(strict=True).parent != (study_root / ".worker").resolve(strict=True):
        raise PermissionError("worker cleanup root escaped the controller namespace")
    for directory, subdirs, filenames in os.walk(scope_root, topdown=False, followlinks=False):
        current = Path(directory)
        if current.stat().st_dev != root_device:
            raise PermissionError("worker cleanup encountered a different filesystem")
        for name in (*subdirs, *filenames):
            child = current / name
            info = child.lstat()
            if stat.S_ISDIR(info.st_mode):
                if info.st_dev != root_device:
                    raise PermissionError("worker cleanup encountered a mounted subdirectory")
                child.rmdir()
            elif stat.S_ISREG(info.st_mode):
                child.unlink()
            else:
                raise PermissionError("worker cleanup refuses links and special files")
    scope_root.rmdir()


@dataclass(frozen=True, slots=True)
class ReadonlyFileBind:
    """One exact Windows registered file translated to one WSL file alias."""

    role_id: str
    phase: str
    source_path: str
    alias_path: str


def registered_file_binds(mappings: Sequence[object]) -> tuple[ReadonlyFileBind, ...]:
    """Translate exact path-map rows into shell-free systemd bind pairs."""

    binds: list[ReadonlyFileBind] = []
    aliases: set[str] = set()
    keys: set[tuple[str, str, str, str]] = set()
    for item in mappings:
        try:
            logical_path = item.logical_path
            role_id = item.role_id
            phase = item.phase
            alias = item.bind_path
            digest = item.sha256
        except AttributeError as exc:
            raise PermissionError("read-only bind requires an exact registered file mapping") from exc
        windows = PureWindowsPath(logical_path)
        if (
            not windows.is_absolute() or len(windows.drive) != 2
            or windows.drive[1] != ":" or ".." in windows.parts
            or str(windows) != logical_path
            or logical_path.count(":") != 1
            or any(char.isspace() or ord(char) < 32 for char in logical_path)
        ):
            raise PermissionError("registered input path cannot be safely translated to WSL")
        if (
            not isinstance(role_id, str) or not role_id
            or not isinstance(phase, str) or phase not in _ACTIVE_INPUT_PHASES
            or not isinstance(alias, str)
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
        ):
            raise PermissionError("registered input mapping identity is incomplete")
        target = PurePosixPath(alias)
        if (
            not target.is_absolute() or target.as_posix() != alias
            or target.parent != PurePosixPath("/run/route2-input")
            or alias in aliases
        ):
            raise PermissionError("registered input alias is not one unique controller path")
        key = (logical_path, digest.lower(), role_id, phase)
        if key in keys:
            raise PermissionError("registered input mapping identity repeats")
        keys.add(key)
        aliases.add(alias)
        source = "/mnt/" + windows.drive[0].lower() + "/" + "/".join(windows.parts[1:])
        binds.append(ReadonlyFileBind(role_id, phase, source, alias))
    if not binds:
        raise PermissionError("controller bind set cannot be empty")
    if len({item.role_id for item in binds if item.role_id != "__study__"}) > 1:
        raise PermissionError("controller bind set exposes multiple roles")
    gt_phases = {item.phase for item in binds if item.phase in _GT_PHASES}
    if len(gt_phases) > 1 or (gt_phases and any(
        item.phase not in _GT_PHASES for item in binds
    )):
        raise PermissionError("controller bind set mixes GT and non-GT role views")
    return tuple(sorted(binds, key=lambda item: (item.role_id, item.phase, item.alias_path)))


def build_study_access_policy(
    *,
    study_root: str,
    ledger_path: str,
    lock_path: str,
    source_snapshot_root: str,
    runtime_snapshot_root: str,
    active_mounts: Sequence[tuple[str, str, str]],
) -> StudyAccessPolicy:
    """Bind service write exceptions and one active role/view mount set."""

    root = PurePosixPath(_canonical_service_path(study_root, "study root"))
    ledger = PurePosixPath(_canonical_service_path(ledger_path, "budget ledger"))
    lock = PurePosixPath(_canonical_service_path(lock_path, "study lock"))
    source_root = _canonical_service_path(source_snapshot_root, "source snapshot")
    runtime_root = _canonical_service_path(runtime_snapshot_root, "runtime snapshot")
    expected_volume = PurePosixPath("/var/lib/route2/studies") / f"{STUDY_ID}-volume"
    snapshot_parent = PurePosixPath("/opt/route2/snapshots") / STUDY_ID

    def pinned_snapshot_root(value: str, leaf: str) -> bool:
        path = PurePosixPath(value)
        if path.name != leaf:
            return False
        if path.parent == snapshot_parent:
            return True
        revision = path.parent
        return (
            revision.parent == snapshot_parent
            and re.fullmatch(r"revision-[0-9]{8}[a-z0-9]{1,8}", revision.name) is not None
        )

    if (
        root.name != STUDY_ID
        or root.parent != expected_volume
        or ledger != expected_volume / f"{STUDY_ID}-budget.jsonl"
        or lock != expected_volume / f"{STUDY_ID}.lock"
        or not pinned_snapshot_root(source_root, "source")
        or not pinned_snapshot_root(runtime_root, "venv")
    ):
        raise PermissionError("study writable or immutable snapshot paths differ from the frozen namespace")
    if root == PurePosixPath(source_root) or root in PurePosixPath(runtime_root).parents:
        raise PermissionError("study outputs overlap an immutable code or dependency snapshot")

    views: list[str] = []
    roles: set[str] = set()
    phases: set[str] = set()
    for item in active_mounts:
        if not isinstance(item, tuple) or len(item) != 3:
            raise PermissionError("active input mount identity must be a role, phase and alias")
        role_id, phase, alias = item
        if (
            not isinstance(role_id, str) or not role_id
            or phase not in _ACTIVE_INPUT_PHASES
        ):
            raise PermissionError("active input mount role or phase is malformed")
        path = PurePosixPath(_canonical_service_path(alias, "input alias"))
        if path.parent != PurePosixPath("/run/route2-input"):
            raise PermissionError("input view must use one exact controller alias under /run")
        roles.add(role_id)
        phases.add(phase)
        views.append(str(path))
    if len(views) != len(set(views)) or len([role for role in roles if role != "__study__"]) > 1:
        raise PermissionError("active input mounts expose duplicate aliases or more than one role")
    if "__study__" in roles and any(role != "__study__" for role in roles):
        raise PermissionError("metadata and role views cannot claim the same active role set")
    if len(phases & _GT_PHASES) > 0:
        if len(phases & _GT_PHASES) != 1 or phases - _GT_PHASES - {"preflight_metadata"}:
            raise PermissionError("a GT phase cannot coexist with Stage A role mounts")
        gt_aliases = [phase for _, phase, _ in active_mounts if phase in _GT_PHASES]
        if len(gt_aliases) != 1:
            raise PermissionError("a GT child can receive exactly one physical view")
    if any(phase != "preflight_metadata" for phase in phases) and not views:
        raise PermissionError("role-scoped input mount set is empty")
    return StudyAccessPolicy(
        study_root=str(root),
        ledger_path=str(ledger),
        lock_path=str(lock),
        source_snapshot_root=source_root,
        runtime_snapshot_root=runtime_root,
        read_only_view_paths=tuple(sorted(views)),
        active_role_id=next((role for role in roles if role != "__study__"), None),
        active_phase=next(iter(phases)) if len(phases) == 1 else None,
    )


def study_service_properties(
    envelope: ResourceEnvelope,
    policy: StudyAccessPolicy,
    *,
    input_binds: Sequence[ReadonlyFileBind] = (),
) -> tuple[tuple[str, str], ...]:
    """Add exact writable/read-only mounts and the dedicated worker identity."""

    if type(policy) is not StudyAccessPolicy:
        raise TypeError("study access restrictions require the fixed reviewed policy")
    if any(type(item) is not ReadonlyFileBind for item in input_binds):
        raise PermissionError("systemd worker binds require exact controller file-bind records")
    bind_aliases = tuple(sorted(item.alias_path for item in input_binds))
    if bind_aliases != policy.read_only_view_paths:
        raise PermissionError("controller bind aliases differ from the reviewed active view set")
    binds = tuple(f"{item.source_path}:{item.alias_path}" for item in input_binds)
    if any(any(char.isspace() for char in value) for value in binds):
        raise PermissionError("systemd bind paths may not contain unescaped whitespace")
    worker_paths = worker_write_paths(policy)
    # Replace the parent proc policy instead of appending a duplicate whose
    # interpretation could depend on property order.
    parent_properties = tuple((name, "pid" if name == "ProcSubset" else
                               "AF_UNIX" if name == "RestrictAddressFamilies" else value)
                              for name, value in systemd_unit_properties(envelope))
    properties = parent_properties + (
        ("User", "route2study"),
        ("Group", "route2study"),
        ("RuntimeDirectory", "route2-worker"),
        ("RuntimeDirectoryMode", "0755"),
        ("WorkingDirectory", WORKER_SCOPE_ALIAS),
        ("ReadWritePaths", worker_paths.scope_dir),
        ("BindPaths", " ".join((
            f"{worker_paths.scope_dir}:{WORKER_SCOPE_ALIAS}",
            f"{worker_paths.scratch_dir}:/tmp",
            f"{worker_paths.scratch_dir}:/var/tmp",
        ))),
        ("ReadOnlyPaths", " ".join((
            policy.source_snapshot_root,
            policy.runtime_snapshot_root,
            *policy.read_only_view_paths,
        ))),
        ("InaccessiblePaths", "/mnt /home /dev/shm"),
        ("StandardOutput", "append:" + worker_paths.stdout_log),
        ("StandardError", "append:" + worker_paths.stderr_log),
    )
    if binds:
        properties += (("BindReadOnlyPaths", " ".join(binds)),)
    return properties


def systemd_run_argv(
    invocation_unit_id: str,
    envelope: ResourceEnvelope,
    policy: StudyAccessPolicy,
    command: Sequence[str],
    *,
    input_binds: Sequence[ReadonlyFileBind] = (),
) -> tuple[str, ...]:
    """Create a shell-free transient unit with study-volume-backed writes."""

    if (
        not isinstance(invocation_unit_id, str)
        or not re.fullmatch(r"route2-[a-z0-9][a-z0-9-]{7,63}", invocation_unit_id)
        or not command
        or any(not isinstance(item, str) or not item or "\x00" in item for item in command)
    ):
        raise ValueError("systemd invocation identity or command is malformed")
    executable = PurePosixPath(command[0])
    runtime_root = PurePosixPath(policy.runtime_snapshot_root)
    if runtime_root not in executable.parents or executable.name != "python":
        raise PermissionError("study service executable is outside its frozen Python runtime")
    if len(command) < 3 or command[1] != "-B" or command[2] not in {"-m", "-c"}:
        raise PermissionError("study service must disable bytecode writes in the immutable runtime")
    unit_name = invocation_unit_id + ".service"
    argv = ["systemd-run", "--system", "--unit", unit_name, "--wait", "--quiet"]
    for name, value in study_service_properties(envelope, policy, input_binds=input_binds):
        argv.append(f"--property={name}={value}")
    worker_paths = worker_write_paths(policy)
    for name, value in (
        ("PYTHONDONTWRITEBYTECODE", "1"),
        ("OMP_NUM_THREADS", "1"),
        ("OPENBLAS_NUM_THREADS", "1"),
        ("MKL_NUM_THREADS", "1"),
        ("NUMEXPR_NUM_THREADS", "1"),
        ("VECLIB_MAXIMUM_THREADS", "1"),
        ("BLIS_NUM_THREADS", "1"),
        ("HOME", WORKER_SCOPE_ALIAS + "/home"),
        ("TMPDIR", "/tmp"),
        ("TMP", "/tmp"),
        ("TEMP", "/tmp"),
        ("JOBLIB_TEMP_FOLDER", "/tmp/joblib"),
        ("MPLCONFIGDIR", "/tmp/matplotlib"),
        ("NUMBA_CACHE_DIR", "/tmp/numba"),
        ("PYTHONPATH", policy.source_snapshot_root + "/src"),
        ("XDG_CACHE_HOME", WORKER_SCOPE_ALIAS + "/cache"),
    ):
        argv.append(f"--setenv={name}={value}")
    argv.extend(("--", *command))
    return tuple(argv)


@dataclass(frozen=True, slots=True)
class CgroupEnforcementProof:
    cgroup_path: str
    memory_max_bytes: int
    memory_current_bytes: int
    memory_peak_bytes: int
    memory_swap_max_bytes: int
    pids_max: int
    pids_current: int
    pids_events_max: int
    cpu_quota_percent: int
    process_count: int
    task_count: int
    process_tree_rss_bytes: int
    maximum_process_address_space_bytes: int
    hard_rss: bool
    hard_worker_threads: bool


def _exact_int(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise PermissionError(f"{name} must be a nonnegative exact integer")
    return value


def _parse_uint(value: object, name: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise PermissionError(f"{name} is not an exact cgroup integer")
    return int(value)


def _parse_key_values(raw: str, *, name: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r"[a-z_]+", parts[0]):
            raise PermissionError(f"{name} contains a malformed counter")
        if parts[0] in values:
            raise PermissionError(f"{name} repeats a counter")
        values[parts[0]] = _parse_uint(parts[1], name)
    if not values:
        raise PermissionError(f"{name} has no counters")
    return values


def _proc_limit_as_bytes(proc_status: Path) -> int:
    lines = (proc_status.parent / "limits").read_text(encoding="ascii").splitlines()
    matches = [line for line in lines if line.startswith("Max address space")]
    if len(matches) != 1:
        raise PermissionError("a live study process lacks one RLIMIT_AS observation")
    parts = matches[0][len("Max address space"):].split()
    if len(parts) != 3 or parts[2] != "bytes" or parts[0] == "unlimited" or parts[1] == "unlimited":
        raise PermissionError("a live study process has no finite inherited RLIMIT_AS")
    soft, hard = int(parts[0]), int(parts[1])
    if soft <= 0 or hard <= 0 or soft != hard:
        raise PermissionError("a live study process has an inconsistent RLIMIT_AS")
    return min(soft, hard)


def capture_cgroup_v2_observation(
    *,
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
) -> dict[str, object]:
    """Collect complete live v2 limits and per-process RSS/thread/address data.

    Parameters exist for synthetic fixture testing. The default paths inspect
    the caller's real WSL namespace; missing, hidden or partial evidence fails
    closed instead of falling back to sampled host-wide metrics.
    """

    memberships = (proc_root / "self" / "cgroup").read_text(encoding="ascii").splitlines()
    unified = [line for line in memberships if line.startswith("0::")]
    if len(unified) != 1:
        raise PermissionError("the study process is not in one unified cgroup v2 hierarchy")
    cgroup_path = unified[0][3:]
    if (
        not cgroup_path.startswith("/system.slice/route2-")
        or ".." in PurePosixPath(cgroup_path).parts
        or PurePosixPath(cgroup_path).as_posix() != cgroup_path
    ):
        raise PermissionError("the study process is outside its unique Route 2 systemd cgroup")
    root = cgroup_root.resolve(strict=True)
    group = (root / cgroup_path.lstrip("/")).resolve(strict=True)
    if group != root and root not in group.parents:
        raise PermissionError("the study cgroup resolves outside the unified hierarchy")

    groups = [group]
    descendants = tuple(group.rglob("*"))
    if any(item.is_symlink() for item in descendants):
        raise PermissionError("study cgroup hierarchy contains a symbolic link")
    groups.extend(sorted(
        (item for item in descendants if item.is_dir() and (item / "cgroup.procs").is_file()),
        key=lambda item: len(item.parts),
    ))
    pids: set[str] = set()
    for current in groups:
        for line in (current / "cgroup.procs").read_text(encoding="ascii").splitlines():
            if not line.isascii() or not line.isdecimal() or line == "0":
                raise PermissionError("cgroup.procs contains an invalid process ID")
            pids.add(line)
    if not pids:
        raise PermissionError("the study cgroup has no live process evidence")

    limits: dict[str, int] = {}
    rss: dict[str, int] = {}
    threads: dict[str, int] = {}
    for pid in sorted(pids, key=int):
        status_path = proc_root / pid / "status"
        fields: dict[str, str] = {}
        for line in status_path.read_text(encoding="ascii").splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields[key] = value.strip()
        vmrss = fields.get("VmRSS", "").split()
        task_count = fields.get("Threads", "")
        if (
            len(vmrss) != 2 or vmrss[1] != "kB"
            or not vmrss[0].isdecimal()
            or not task_count.isdecimal() or int(task_count) <= 0
        ):
            raise PermissionError("a live study process lacks exact RSS or task evidence")
        limits[pid] = _proc_limit_as_bytes(status_path)
        rss[pid] = int(vmrss[0]) * 1024
        threads[pid] = int(task_count)

    def read(name: str) -> str:
        return (group / name).read_text(encoding="ascii").strip()

    memory_events = _parse_key_values(read("memory.events"), name="memory.events")
    pids_events = _parse_key_values(read("pids.events"), name="pids.events")
    if "max" not in pids_events or not {"max", "oom", "oom_kill"}.issubset(memory_events):
        raise PermissionError("cgroup event evidence omits a hard-limit counter")
    return {
        "version": 2,
        "cgroup_path": cgroup_path,
        "memory.max": read("memory.max"),
        "memory.current": read("memory.current"),
        "memory.peak": read("memory.peak"),
        "memory.swap.max": read("memory.swap.max"),
        "memory.events": memory_events,
        "pids.max": read("pids.max"),
        "pids.current": read("pids.current"),
        "pids.events.max": str(pids_events["max"]),
        "cpu.max": read("cpu.max"),
        "rlimit_as_bytes_by_pid": limits,
        "rss_bytes_by_pid": rss,
        "thread_count_by_pid": threads,
    }


def validate_cgroup_enforcement(
    observation: Mapping[str, object],
    envelope: ResourceEnvelope,
) -> CgroupEnforcementProof:
    """Fail closed unless the live cgroup and every live task prove the bound."""

    if type(envelope) is not ResourceEnvelope or not isinstance(observation, Mapping):
        raise TypeError("cgroup validation requires the fixed envelope and a mapping")
    if observation.get("version") != 2:
        raise PermissionError("the active study service is not on unified cgroup v2")
    cgroup = observation.get("cgroup_path")
    if (
        not isinstance(cgroup, str)
        or not cgroup.startswith("/system.slice/route2-")
        or not cgroup.endswith(".service")
        or ".." in cgroup.split("/")
    ):
        raise PermissionError("the supervisor is outside its unique system.slice service cgroup")

    memory_max = _parse_uint(observation.get("memory.max"), "memory.max")
    memory_current = _parse_uint(observation.get("memory.current"), "memory.current")
    memory_peak = _parse_uint(observation.get("memory.peak"), "memory.peak")
    swap_max = _parse_uint(observation.get("memory.swap.max"), "memory.swap.max")
    pids_max = _parse_uint(observation.get("pids.max"), "pids.max")
    pids_current = _parse_uint(observation.get("pids.current"), "pids.current")
    pids_events_max = _parse_uint(observation.get("pids.events.max"), "pids.events.max")
    memory_events = observation.get("memory.events")
    if not isinstance(memory_events, Mapping):
        raise PermissionError("cgroup memory event counters are missing")
    memory_event_counts = {
        name: _exact_int(memory_events.get(name), f"memory.events {name}")
        for name in ("max", "oom", "oom_kill")
    }
    cpu_max = observation.get("cpu.max")
    if not isinstance(cpu_max, str) or len(cpu_max.split()) != 2:
        raise PermissionError("cpu.max is malformed")
    quota_text, period_text = cpu_max.split()
    quota = _parse_uint(quota_text, "cpu.max quota")
    period = _parse_uint(period_text, "cpu.max period")
    if period <= 0 or quota * 100 > envelope.cpu_quota_percent * period:
        raise PermissionError("cpu.max permits more than the frozen CPU quota")

    raw_rlimits = observation.get("rlimit_as_bytes_by_pid")
    raw_rss = observation.get("rss_bytes_by_pid")
    raw_threads = observation.get("thread_count_by_pid")
    if (
        not isinstance(raw_rlimits, Mapping) or not raw_rlimits
        or not isinstance(raw_rss, Mapping)
        or not isinstance(raw_threads, Mapping)
        or set(raw_rlimits) != set(raw_rss)
        or set(raw_rlimits) != set(raw_threads)
    ):
        raise PermissionError("complete per-process RSS, task and RLIMIT_AS evidence is missing")
    limits_by_pid: dict[str, int] = {}
    rss_by_pid: dict[str, int] = {}
    threads_by_pid: dict[str, int] = {}
    for pid, raw_limit in raw_rlimits.items():
        if not isinstance(pid, str) or not pid.isdecimal():
            raise PermissionError("RLIMIT_AS evidence contains an invalid PID")
        limit = _exact_int(raw_limit, "RLIMIT_AS")
        rss = _exact_int(raw_rss[pid], "process RSS")
        thread_count = raw_threads[pid]
        if type(thread_count) is not int or thread_count < 1:
            raise PermissionError("live process task count is missing or invalid")
        if limit > envelope.rlimit_as_per_process_bytes:
            raise PermissionError("a live task escaped the inherited RLIMIT_AS ceiling")
        if limit == 0 or rss > limit:
            raise PermissionError("a process RSS measurement exceeds its inherited address-space limit")
        limits_by_pid[pid] = limit
        rss_by_pid[pid] = rss
        threads_by_pid[pid] = thread_count

    if (
        memory_max != envelope.memory_max_bytes
        or memory_current > memory_max
        or memory_peak > memory_max
        or memory_current > memory_peak
        or swap_max != envelope.memory_swap_max_bytes
        or pids_max != envelope.pids_max
        or pids_current <= 0
        or pids_current > pids_max
        or pids_events_max != 0
        or any(memory_event_counts.values())
        or len(limits_by_pid) > pids_max
        or sum(threads_by_pid.values()) != pids_current
        or sum(rss_by_pid.values()) > envelope.rss_cap_bytes
    ):
        raise PermissionError("full-study cgroup, RSS or task values differ from the frozen hard-limit envelope")
    if max(limits_by_pid.values()) * pids_max > envelope.rss_cap_bytes:
        raise PermissionError("the task-count and RLIMIT_AS product exceeds the RSS ceiling")

    return CgroupEnforcementProof(
        cgroup_path=cgroup,
        memory_max_bytes=memory_max,
        memory_current_bytes=memory_current,
        memory_peak_bytes=memory_peak,
        memory_swap_max_bytes=swap_max,
        pids_max=pids_max,
        pids_current=pids_current,
        pids_events_max=pids_events_max,
        cpu_quota_percent=(quota * 100) // period,
        process_count=len(limits_by_pid),
        task_count=pids_current,
        process_tree_rss_bytes=sum(rss_by_pid.values()),
        maximum_process_address_space_bytes=max(limits_by_pid.values()),
        hard_rss=True,
        hard_worker_threads=True,
    )


_POST_EXIT_FIELDS = frozenset({
    "schema", "invocation_id", "unit_name", "terminal_sha256", "unit_result",
    "exit_status", "active_state", "durable_external_event",
    "invocation_started_ns", "terminal_closed_ns", "deadline_ns",
    "external_clock", "qpc_frequency", "external_started_ticks",
    "external_terminal_detected_ticks", "external_unit_inactive_ticks",
    "external_receipt_fsynced_ticks", "external_deadline_ticks",
})


def verify_post_exit_receipt(
    receipt: Mapping[str, object],
    *,
    invocation_id: str,
    unit_name: str,
    terminal_sha256: str,
    observed_monotonic_ns: int,
    observed_external_ticks: int,
    total_wall_ns: int,
    terminal_status: str = StudyStatus.COMPLETE.value,
    expected_qpc_frequency: int,
    expected_external_started_ticks: int,
) -> bool:
    """Verify a closed terminal witnessed after service exit by the host clock.

    The Linux monotonic interval covers the ledger lifecycle.  Windows QPC is
    the independent outer clock and covers launch through durable receipt and
    unit inactivity, so closing a terminal inside a surviving shell cannot
    masquerade as completed work. Only INCOMPLETE_RESOURCE may document a
    measured overrun; all successful and scientific stop statuses remain
    inside the frozen wall deadline.
    """

    if not isinstance(receipt, Mapping) or set(receipt) != _POST_EXIT_FIELDS:
        raise PermissionError("post-exit receipt has an unknown or missing field")
    if not isinstance(terminal_status, str) or terminal_status not in {item.value for item in StudyStatus}:
        raise PermissionError("post-exit receipt has an unknown terminal status")
    allow_wall_overrun = terminal_status == StudyStatus.INCOMPLETE_RESOURCE.value
    if (
        receipt.get("schema") != "route2_post_exit_receipt_v1"
        or receipt.get("invocation_id") != invocation_id
        or receipt.get("unit_name") != unit_name
        or receipt.get("terminal_sha256") != terminal_sha256.lower()
        or receipt.get("unit_result") != "success"
        or type(receipt.get("exit_status")) is not int
        or receipt.get("exit_status") != 0
        or receipt.get("active_state") != "inactive"
        or receipt.get("durable_external_event") is not True
    ):
        raise PermissionError("post-exit receipt does not bind a successful completed service")
    linux_times = tuple(receipt.get(name) for name in (
        "invocation_started_ns", "terminal_closed_ns", "deadline_ns",
    ))
    if any(type(value) is not int or value <= 0 for value in linux_times):
        raise PermissionError("post-exit receipt contains an invalid monotonic timestamp")
    started, terminal_closed, deadline = linux_times
    if (
        type(total_wall_ns) is not int or total_wall_ns <= 0
        or deadline != started + total_wall_ns
        or terminal_closed < started
        or (not allow_wall_overrun and terminal_closed > deadline)
        or type(observed_monotonic_ns) is not int
        or observed_monotonic_ns < terminal_closed
        or (not allow_wall_overrun and observed_monotonic_ns > deadline)
    ):
        raise PermissionError("Linux terminal close or full-study wall interval is invalid")
    if (
        receipt.get("external_clock") != "windows_qpc"
        or type(receipt.get("qpc_frequency")) is not int
        or receipt.get("qpc_frequency") != expected_qpc_frequency
        or type(expected_qpc_frequency) is not int or expected_qpc_frequency <= 0
        or type(expected_external_started_ticks) is not int or expected_external_started_ticks <= 0
    ):
        raise PermissionError("external host clock identity differs from the frozen invocation")
    external_times = tuple(receipt.get(name) for name in (
        "external_started_ticks", "external_terminal_detected_ticks",
        "external_unit_inactive_ticks", "external_receipt_fsynced_ticks",
        "external_deadline_ticks",
    ))
    if any(type(value) is not int or value <= 0 for value in external_times):
        raise PermissionError("external host receipt contains an invalid QPC timestamp")
    host_started, terminal_seen, unit_inactive, receipt_fsynced, host_deadline = external_times
    expected_host_deadline = host_started + (
        total_wall_ns * expected_qpc_frequency + 999_999_999
    ) // 1_000_000_000
    if (
        host_started != expected_external_started_ticks
        or not host_started <= terminal_seen <= unit_inactive <= receipt_fsynced
        or host_deadline != expected_host_deadline
        or type(observed_external_ticks) is not int
        or observed_external_ticks < receipt_fsynced
        or (not allow_wall_overrun and (receipt_fsynced > host_deadline or observed_external_ticks > host_deadline))
    ):
        raise PermissionError("durable external wall receipt is missing, late, or out of order")
    if (
        len(terminal_sha256) != 64
        or any(char not in "0123456789abcdef" for char in terminal_sha256.lower())
    ):
        raise PermissionError("post-exit receipt terminal digest is malformed")
    return True


def canonical_receipt_bytes(value: Mapping[str, object]) -> bytes:
    """Encode a controller receipt for hashing and durable persistence."""

    if not isinstance(value, Mapping):
        raise TypeError("receipt body must be a mapping")
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def receipt_sha256(value: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_receipt_bytes(value)).hexdigest()
