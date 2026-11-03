"""No-data WSL capability probes for the proposed Route 2 resource controller.

This module intentionally does not issue an ``EnforcementReceipt`` or invoke the
study.  A synthetic probe proves a host capability, not an approved A+B runtime.
The scratch namespace is disjoint from ``route2-candidate-overlap-v1-001``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import errno
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eating_event.route2_candidate_overlap.linux_enforcement import (
    StudyAccessPolicy,
    WORKER_SCOPE_ALIAS,
    capture_cgroup_v2_observation,
    prepare_worker_write_paths,
)


GIB = 1 << 30
STAGE_A_CAP_BYTES = 2 * GIB
TOTAL_CAP_BYTES = 4 * GIB
BACKING_FREE_FLOOR_BYTES = 8 * GIB
SCRATCH_BASE = Path("/var/lib/route2-scratch")
FORMAL_STUDY_ID = "route2-candidate-overlap-v1-001"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _run(argv: list[str], *, timeout: float = 60) -> str:
    try:
        completed = subprocess.run(argv, check=True, text=True, capture_output=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        diagnostic = (exc.stderr or exc.stdout or str(exc))[-2000:]
        raise RuntimeError(f"command failed ({exc.returncode}): {diagnostic}") from exc
    return completed.stdout.strip()


def _mount_point_unescape(value: str) -> str:
    for source, target in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
        value = value.replace(source, target)
    return value


@dataclass(frozen=True)
class MountEvidence:
    mount_id: int
    parent_id: int
    major_minor: str
    mount_point: str
    fs_type: str
    source: str
    st_dev: int
    capacity_bytes: int
    available_bytes: int
    allocated_bytes: int


def mount_evidence(path: Path) -> MountEvidence:
    """Read the covering mount ID and actual statfs capacity, without `df` parsing."""
    path = path.resolve(strict=True)
    chosen: tuple[int, list[str], list[str]] | None = None
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        fields = left.split()
        mount_point = _mount_point_unescape(fields[4])
        if path == Path(mount_point) or Path(mount_point) in path.parents:
            if chosen is None or len(mount_point) > chosen[0]:
                chosen = (len(mount_point), fields, right.split())
    if chosen is None:
        raise RuntimeError(f"mount information unavailable for {path}")
    _, fields, right = chosen
    stat = os.stat(path)
    fs = os.statvfs(path)
    capacity = fs.f_blocks * fs.f_frsize
    available = fs.f_bavail * fs.f_frsize
    return MountEvidence(
        mount_id=int(fields[0]),
        parent_id=int(fields[1]),
        major_minor=fields[2],
        mount_point=_mount_point_unescape(fields[4]),
        fs_type=right[0],
        source=_mount_point_unescape(right[1]),
        st_dev=stat.st_dev,
        capacity_bytes=capacity,
        available_bytes=available,
        allocated_bytes=(fs.f_blocks - fs.f_bfree) * fs.f_frsize,
    )


def guest_backing_preflight(image_parent: Path = SCRATCH_BASE) -> dict[str, object]:
    """Read only.  This is the WSL half of the two-layer startup check."""
    candidate = image_parent if image_parent.exists() else image_parent.parent
    if not candidate.exists():
        raise FileNotFoundError(candidate)
    mount = mount_evidence(candidate)
    if mount.fs_type != "ext4":
        raise RuntimeError("proposed image parent is not on WSL ext4")
    if mount.available_bytes < BACKING_FREE_FLOOR_BYTES:
        raise RuntimeError("WSL backing filesystem has less than 8 GiB free")
    return {
        "probe_kind": "guest_backing_preflight_only",
        "image_parent": str(image_parent),
        "checked_existing_path": str(candidate.resolve()),
        "backing_mount": asdict(mount),
        "free_floor_bytes": BACKING_FREE_FLOOR_BYTES,
        "guest_free_pass": True,
        "windows_physical_free_pass": None,
        "experiment_authorized": False,
    }


def live_vhdx_host_free(linux_vhdx: Path) -> dict[str, object]:
    """Sample the VHDX's Windows volume via WSL DrvFS/9p after Linux entry.

    The Windows volume GUID cannot be independently learned from Linux here;
    it must be bound to a preceding trusted Windows registry/Win32 attestation.
    The actual free-byte sample is fresh and made by the Linux supervisor.
    """
    if linux_vhdx.is_symlink() or not linux_vhdx.is_file():
        raise PermissionError("exact VHDX path must be a regular non-link file")
    resolved = linux_vhdx.resolve(strict=True)
    if len(resolved.parts) < 4 or resolved.parts[1] != "mnt" or len(resolved.parts[2]) != 1:
        raise PermissionError("VHDX must resolve under one WSL Windows-drive mount")
    mounted = mount_evidence(resolved)
    expected_source = resolved.parts[2].upper() + ":\\"
    if mounted.fs_type != "9p" or mounted.source != expected_source:
        raise PermissionError("VHDX path does not belong to the expected Windows drive mount")
    if mounted.available_bytes < BACKING_FREE_FLOOR_BYTES:
        raise RuntimeError("VHDX host physical volume is below the 8 GiB startup floor")
    return {
        "probe_kind": "linux_live_vhdx_9p_free_sample",
        "linux_vhdx_path": str(resolved),
        "vhdx_length_bytes": resolved.stat().st_size,
        "host_volume_mount": asdict(mounted),
        "host_physical_free_bytes": mounted.available_bytes,
        "free_floor_bytes": BACKING_FREE_FLOOR_BYTES,
        "windows_volume_guid_verified_in_linux": False,
        "experiment_authorized": False,
    }


def _refuse_formal_namespace(path: Path) -> None:
    for part in path.parts:
        if part == FORMAL_STUDY_ID or part.startswith(FORMAL_STUDY_ID + "-"):
            raise PermissionError("synthetic probe must never occupy the formal study namespace")


def _write_until_enospc(path: Path) -> dict[str, int | bool]:
    block = b"\xa5" * (4 << 20)
    written = 0
    exhausted = False
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        while written <= TOTAL_CAP_BYTES:
            try:
                count = os.write(fd, block)
                if count <= 0:
                    raise OSError("write returned no progress")
                written += count
            except OSError as exc:
                if exc.errno != errno.ENOSPC:
                    raise
                exhausted = True
                break
        try:
            os.fsync(fd)
        except OSError as exc:
            if exc.errno != errno.ENOSPC:
                raise
            exhausted = True
    finally:
        os.close(fd)
    st = path.stat()
    return {"write_bytes_before_rejection": written, "file_allocated_bytes": st.st_blocks * 512, "enospc": exhausted}


def _grow_until_enospc(path: Path) -> dict[str, int | bool]:
    block = b"\x5a" * (4 << 20)
    written = 0
    exhausted = False
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    try:
        while written <= TOTAL_CAP_BYTES:
            try:
                count = os.write(fd, block)
                if count <= 0:
                    raise OSError("write returned no progress")
                written += count
            except OSError as exc:
                if exc.errno != errno.ENOSPC:
                    raise
                exhausted = True
                break
        try:
            os.fsync(fd)
        except OSError as exc:
            if exc.errno != errno.ENOSPC:
                raise
            exhausted = True
    finally:
        os.close(fd)
    st = path.stat()
    return {"additional_write_bytes_before_rejection": written, "file_allocated_bytes": st.st_blocks * 512, "enospc": exhausted}


def probe_disk(scratch_base: Path = SCRATCH_BASE) -> dict[str, object]:
    """Create and destroy one independent 2->4 GiB ext4 loop scratch volume.

    This deliberately consumes up to 4 GiB of transient host disk.  It refuses
    pre-existing scratch paths, symlinks, non-ext4 backing, insufficient free
    space, and any formal-study name.  No result is an experiment receipt.
    """
    if os.geteuid() != 0:
        raise PermissionError("the synthetic loopback probe requires WSL root")
    _refuse_formal_namespace(scratch_base)
    if scratch_base.is_symlink():
        raise PermissionError("scratch base cannot be a symlink")
    scratch_base.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = mount_evidence(scratch_base)
    if parent.fs_type != "ext4" or parent.available_bytes < BACKING_FREE_FLOOR_BYTES:
        raise RuntimeError("scratch image parent needs ext4 and at least 8 GiB guest free")
    probe_id = "route2-os-probe-" + uuid.uuid4().hex
    scratch = Path(tempfile.mkdtemp(prefix=probe_id + "-", dir=scratch_base))
    _refuse_formal_namespace(scratch)
    if scratch.resolve().parent != scratch_base.resolve():
        raise PermissionError("scratch path escaped its base")
    image = scratch / "synthetic.ext4"
    mount_point = scratch / "volume"
    mount_point.mkdir(mode=0o700)
    loop_device: str | None = None
    mounted = False
    try:
        fd = os.open(image, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            os.ftruncate(fd, STAGE_A_CAP_BYTES)
            os.fsync(fd)
        finally:
            os.close(fd)
        _run(["mkfs.ext4", "-F", "-q", "-m", "0", str(image)], timeout=120)
        loop_device = _run(["losetup", "--find", "--show", str(image)])
        _run(["mount", "-t", "ext4", "-o", "nosuid,nodev,noexec", loop_device, str(mount_point)])
        mounted = True
        before = mount_evidence(mount_point)
        fs_uuid_before = _run(["blkid", "-s", "UUID", "-o", "value", loop_device])
        if before.capacity_bytes > STAGE_A_CAP_BYTES:
            raise RuntimeError("Stage A filesystem exceeds the 2 GiB hard cap")
        stage_a_write = _write_until_enospc(mount_point / "synthetic.bin")
        if not stage_a_write["enospc"]:
            raise RuntimeError("synthetic Stage A write was not rejected")
        # This probe models the stage gate without representing an authorized
        # scientific Stage A.  A real controller must bind the frozen ledger.
        synthetic_gate = {"all_references": True, "all_treatments": True, "projection": True, "fsynced": True}
        if not all(synthetic_gate.values()):
            raise RuntimeError("synthetic transition gate was denied")
        fd = os.open(image, os.O_WRONLY | os.O_NOFOLLOW)
        try:
            os.ftruncate(fd, TOTAL_CAP_BYTES)
            os.fsync(fd)
        finally:
            os.close(fd)
        _run(["losetup", "-c", loop_device])
        _run(["resize2fs", loop_device], timeout=120)
        after = mount_evidence(mount_point)
        fs_uuid_after = _run(["blkid", "-s", "UUID", "-o", "value", loop_device])
        same = (
            before.mount_id == after.mount_id
            and before.st_dev == after.st_dev
            and before.major_minor == after.major_minor
            and before.source == after.source == loop_device
            and fs_uuid_before == fs_uuid_after
        )
        if not same or after.capacity_bytes <= before.capacity_bytes or after.capacity_bytes > TOTAL_CAP_BYTES:
            raise RuntimeError("online growth changed identity or exceeded the 4 GiB cap")
        stage_b_write = _grow_until_enospc(mount_point / "synthetic.bin")
        if not stage_b_write["enospc"]:
            raise RuntimeError("synthetic post-growth write was not rejected")
        return {
            "probe_kind": "independent_synthetic_2_to_4_gib_ext4_loop",
            "probe_id": probe_id,
            "scratch_path": str(scratch),
            "image_path": str(image),
            "loop_device": loop_device,
            "guest_backing_before": asdict(parent),
            "stage_a_mount": asdict(before),
            "stage_a_write": stage_a_write,
            "synthetic_gate": synthetic_gate,
            "stage_b_mount": asdict(after),
            "stage_b_write": stage_b_write,
            "fs_uuid_before": fs_uuid_before,
            "fs_uuid_after": fs_uuid_after,
            "same_mount_device_filesystem": same,
            "image_allocated_bytes": image.stat().st_blocks * 512,
            "experiment_authorized": False,
        }
    finally:
        if mounted:
            subprocess.run(["umount", str(mount_point)], check=True, timeout=60)
        if loop_device is not None:
            subprocess.run(["losetup", "-d", loop_device], check=True, timeout=60)
        if scratch.exists() and scratch.resolve().parent == scratch_base.resolve() and scratch.name.startswith(probe_id + "-"):
            shutil.rmtree(scratch)


def _read_cgroup_value(name: str) -> str:
    entry = Path("/proc/self/cgroup").read_text().strip().split(":")
    if len(entry) != 3 or entry[0] != "0":
        raise RuntimeError("expected unified cgroup v2")
    return (Path("/sys/fs/cgroup") / entry[2].lstrip("/") / name).read_text().strip()


def _cgroup_child() -> dict[str, object]:
    """Execute only inside a transient synthetic systemd service."""
    if os.environ.get("ROUTE2_SYNTHETIC_CGROUP_CHILD") != "1":
        raise PermissionError("synthetic cgroup child must be launched by the probe")
    own_limits = resource.getrlimit(resource.RLIMIT_AS)
    first = subprocess.Popen(["/bin/sleep", "0.5"])
    third_refused = False
    observation: dict[str, object] | None = None
    try:
        try:
            extra = subprocess.Popen(["/bin/sleep", "0.01"])
        except OSError as exc:
            third_refused = exc.errno == errno.EAGAIN
            if not third_refused:
                raise
        else:
            extra.wait(timeout=2)
        allocation_refused = False
        try:
            mapping = mmap.mmap(-1, 256 << 20)
        except (OSError, MemoryError):
            allocation_refused = True
        else:
            mapping.close()
        observation = capture_cgroup_v2_observation()
    finally:
        first.wait(timeout=2)
    if observation is None:
        raise RuntimeError("synthetic cgroup observation was not captured")
    return {
        "probe_kind": "synthetic_cgroup_task_and_as_limit",
        "cgroup_observation": observation,
        "cgroup_path": Path("/proc/self/cgroup").read_text().strip(),
        "memory_max": _read_cgroup_value("memory.max"),
        "memory_swap_max": _read_cgroup_value("memory.swap.max"),
        "pids_max": _read_cgroup_value("pids.max"),
        "cpu_max": _read_cgroup_value("cpu.max"),
        "pids_events": _read_cgroup_value("pids.events"),
        "rlimit_as": own_limits,
        "third_task_refused": third_refused,
        "oversize_virtual_allocation_refused": allocation_refused,
        "experiment_authorized": False,
    }


def probe_cgroup() -> dict[str, object]:
    """Check actual cgroup properties and conservative task/AS rejection."""
    if os.geteuid() != 0:
        raise PermissionError("synthetic systemd probe requires WSL root")
    unit = "route2-synthetic-" + uuid.uuid4().hex[:16]
    env = "ROUTE2_SYNTHETIC_CGROUP_CHILD=1"
    output = _run([
        "systemd-run", "--pipe", "--wait", "--collect", "--unit", unit,
        "--property=Type=exec", "--property=MemoryMax=268435456",
        "--property=MemorySwapMax=0", "--property=TasksMax=2",
        "--property=CPUQuota=200%", "--property=LimitAS=134217728",
        "--property=NoNewPrivileges=yes", "--property=CapabilityBoundingSet=",
        "--setenv=" + env,
        sys.executable, str(Path(__file__).resolve()), "_cgroup_child",
    ], timeout=60)
    lines = [line for line in output.splitlines() if line.startswith("{")]
    if len(lines) != 1:
        raise RuntimeError(f"unexpected synthetic service response: {output[-400:]}")
    data = json.loads(lines[0])
    if (
        data["memory_max"] != "268435456"
        or data["memory_swap_max"] != "0"
        or data["pids_max"] != "2"
        or data["rlimit_as"] != [134217728, 134217728]
        or not data["third_task_refused"]
        or not data["oversize_virtual_allocation_refused"]
    ):
        raise RuntimeError("synthetic service failed an OS hard-limit check")
    data["unit"] = unit
    data["supervisor_and_dependency_import_proven"] = False
    data["hard_rss_or_worker_receipt_issued"] = False
    return data


def probe_readonly_file_bind(scratch_base: Path = SCRATCH_BASE) -> dict[str, object]:
    """Prove a systemd worker sees one exact file bind as RO and cannot write it."""

    if os.geteuid() != 0:
        raise PermissionError("synthetic read-only bind probe requires WSL root")
    _refuse_formal_namespace(scratch_base)
    scratch_base.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = scratch_base / ("route2-bind-probe-" + uuid.uuid4().hex + ".bin")
    payload = b"route2 synthetic bind; no project data\n"
    fd = os.open(source, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o444)
    try:
        if os.write(fd, payload) != len(payload):
            raise OSError("partial synthetic source write")
        os.fsync(fd)
    finally:
        os.close(fd)
    alias_root = Path("/run/route2-input")
    alias_root.mkdir(mode=0o755, parents=True, exist_ok=True)
    if alias_root.is_symlink() or alias_root.stat().st_uid != 0 or alias_root.stat().st_mode & 0o022:
        source.unlink(missing_ok=True)
        raise PermissionError("synthetic bind alias root is not controller-owned")
    if alias_root.stat().st_mode & 0o111 == 0:
        os.chmod(alias_root, 0o755)
    alias = alias_root / ("probe-" + uuid.uuid4().hex)
    unit = "route2-bind-synthetic-" + uuid.uuid4().hex[:16]
    script = (
        "import errno,hashlib,json,os,sys;"
        "path=sys.argv[1];"
        "raw=open(path,'rb').read();"
        "rows=[line for line in open('/proc/self/mountinfo',encoding='utf-8') if line.split(' - ',1)[0].split()[4].replace('\\\\040',' ')==path];"
        "len(rows)==1 or sys.exit(21);"
        "fields=rows[0].split(' - ',1)[0].split();"
        "ro='ro' in fields[5].split(',');"
        "denied=False;"
        "\ntry:\n fd=os.open(path,os.O_WRONLY|os.O_APPEND); os.close(fd)\nexcept OSError as e:\n denied=e.errno in (errno.EROFS,errno.EACCES)\n"
        "json.dump({'mount_id':int(fields[0]),'read_only':ro,'write_denied':denied,'payload_sha256':hashlib.sha256(raw).hexdigest()},sys.stdout);print()"
    )
    argv = [
        "systemd-run", "--system", "--unit", unit, "--wait", "--pipe",
        "--property=Type=exec",
        "--property=User=nobody",
        "--property=Group=nogroup",
        f"--property=BindReadOnlyPaths={source}:{alias}",
        f"--property=ReadOnlyPaths={alias}",
        "--property=ProtectSystem=strict",
        "--property=ProtectHome=yes",
        "--property=InaccessiblePaths=/mnt /home",
        "--property=PrivateTmp=yes",
        "--property=PrivateDevices=yes",
        "--property=PrivateNetwork=yes",
        "--property=NoNewPrivileges=yes",
        "--property=RestrictAddressFamilies=AF_UNIX",
        "--property=UMask=0077",
        "--", sys.executable, "-B", "-c", script, str(alias),
    ]
    try:
        output = _run(argv, timeout=30)
        lines = [line for line in output.splitlines() if line.startswith("{")]
        if len(lines) != 1:
            raise RuntimeError("synthetic read-only bind worker returned no unique receipt")
        receipt = json.loads(lines[0])
        if (
            type(receipt.get("mount_id")) is not int or receipt["mount_id"] <= 0
            or receipt.get("read_only") is not True
            or receipt.get("write_denied") is not True
            or receipt.get("payload_sha256") != hashlib.sha256(payload).hexdigest()
        ):
            raise PermissionError("synthetic file bind was writable or not mount-observed")
        unit_state = _run([
            "systemctl", "show", unit,
            "--property=ActiveState", "--property=Result", "--property=ExecMainStatus",
            "--no-pager",
        ])
        if "ActiveState=inactive" not in unit_state or "Result=success" not in unit_state or "ExecMainStatus=0" not in unit_state:
            raise RuntimeError("synthetic file bind service did not exit successfully")
        return {
            "probe_kind": "synthetic_systemd_exact_file_readonly_bind",
            "unit": unit,
            "source_path": str(source),
            "worker_alias": str(alias),
            "worker_receipt": receipt,
            "unit_state": unit_state,
            "project_data_used": False,
            "experiment_authorized": False,
        }
    finally:
        source.unlink(missing_ok=True)


def probe_worker_write_paths(scratch_base: Path = SCRATCH_BASE) -> dict[str, object]:
    """Exercise study-volume-backed tmp/cache/home/log writes on a scratch loop."""

    if os.geteuid() != 0:
        raise PermissionError("synthetic worker write-path probe requires WSL root")
    _refuse_formal_namespace(scratch_base)
    scratch_base.mkdir(mode=0o700, parents=True, exist_ok=True)
    probe_id = "route2-write-probe-" + uuid.uuid4().hex
    scratch = scratch_base / probe_id
    if scratch.exists() or scratch.is_symlink():
        raise FileExistsError("synthetic worker write-path namespace is occupied")
    scratch.mkdir(mode=0o700)
    image = scratch / "synthetic.ext4"
    mountpoint = scratch / "volume"
    study_root = mountpoint / "study"
    scope: Path | None = None
    temp_dir: Path | None = None
    home_dir: Path | None = None
    cache_dir: Path | None = None
    log_dir: Path | None = None
    output_path: Path | None = None
    loop_device = ""
    mounted = False
    unit = "route2-write-synthetic-" + uuid.uuid4().hex[:16]
    try:
        with image.open("xb") as stream:
            stream.truncate(64 * 1024 * 1024)
            stream.flush()
            os.fsync(stream.fileno())
        mountpoint.mkdir(mode=0o755)
        loop_device = _run(["losetup", "--find", "--show", str(image)])
        _run(["mkfs.ext4", "-F", "-q", loop_device])
        _run(["mount", loop_device, str(mountpoint)])
        mounted = True
        study_root.mkdir(mode=0o755)
        policy = StudyAccessPolicy(
            study_root=str(study_root),
            ledger_path=str(study_root.parent / "synthetic-ledger.jsonl"),
            lock_path=str(study_root.parent / "synthetic.lock"),
            source_snapshot_root="/opt/route2/synthetic-source",
            runtime_snapshot_root="/opt/route2/synthetic-runtime",
            read_only_view_paths=(),
            active_role_id="synthetic-role",
            active_phase="synthetic-phase",
        )
        worker_paths = prepare_worker_write_paths(policy, owner_uid=65534, owner_gid=65534)
        scope = Path(worker_paths.scratch_dir).parent
        temp_dir = Path(worker_paths.scratch_dir)
        home_dir = Path(worker_paths.home_dir)
        cache_dir = Path(worker_paths.cache_dir)
        log_dir = Path(worker_paths.stdout_log).parent
        output_path = scope / "result.json"
        volume_mount = mount_evidence(study_root)

        worker_script = (
            "import json,os,pathlib,sys;\n"
            "study_dev=int(sys.argv[1]); result=pathlib.Path(sys.argv[2]);\n"
            "home=pathlib.Path(os.environ['HOME']); cache=pathlib.Path(os.environ['XDG_CACHE_HOME']);\n"
            "probe_dirs=(result.parent,home,cache,pathlib.Path('/tmp'),pathlib.Path('/var/tmp'));\n"
            "for probe_path in probe_dirs:\n"
            " try:\n"
            "  probe_stat=probe_path.stat(); print('perm',probe_path.name,probe_stat.st_uid,probe_stat.st_gid,oct(probe_stat.st_mode&0o777),os.access(probe_path,os.X_OK),os.access(probe_path,os.W_OK),flush=True)\n"
            " except Exception as probe_error:\n"
            "  print('perm_error',probe_path.name,repr(probe_error),flush=True)\n"
            "paths={'tmp':pathlib.Path('/tmp/route2-write.tmp'),\n"
            "'var_tmp':pathlib.Path('/var/tmp/route2-write.var-tmp'),\n"
            "'home':home/'home.txt','cache':cache/'cache.txt'};\n"
            "[(path.parent.mkdir(parents=True,exist_ok=True),path.write_bytes(b'route2 synthetic worker write\\n')) for path in paths.values()];\n"
            "devs={name:os.stat(path).st_dev for name,path in paths.items()};\n"
            "mounts={};\n"
            "for name in ('/tmp','/var/tmp'):\n"
            " rows=[line for line in open('/proc/self/mountinfo',encoding='utf-8') if line.split(' - ',1)[0].split()[4]==name];\n"
            " len(rows)==1 or sys.exit(31); fields=rows[0].split(' - ',1)[0].split(); mounts[name]={'mount_id':int(fields[0]),'major_minor':fields[2],'options':fields[5]};\n"
            "result.write_text(json.dumps({'study_st_dev':study_dev,'write_st_dev_by_path':devs,'tmp_mounts':mounts,'home':str(home),'cache':str(cache),'project_data_used':False},sort_keys=True));\n"
            "print('route2 synthetic stdout marker'); print('route2 synthetic stderr marker',file=sys.stderr);\n"
            "set(devs.values())=={study_dev} or sys.exit(32);\n"
            "all('ro' not in item['options'].split(',') for item in mounts.values()) or sys.exit(33)\n"
        )
        # systemd-run stores argv in a transient unit. Keep the Python -c
        # argument to one harmless expression so source newlines and
        # semicolons cannot be parsed as unit-file syntax.
        worker_exec = "exec(bytes.fromhex('" + worker_script.encode("utf-8").hex() + "'))"
        argv = [
            "systemd-run", "--system", "--unit", unit, "--wait", "--quiet",
            "--property=Type=exec",
            "--property=User=nobody",
            "--property=Group=nogroup",
            "--property=RuntimeDirectory=route2-worker",
            "--property=RuntimeDirectoryMode=0755",
            f"--property=WorkingDirectory={WORKER_SCOPE_ALIAS}",
            f"--property=ReadWritePaths={scope}",
            f"--property=BindPaths={scope}:{WORKER_SCOPE_ALIAS} {temp_dir}:/tmp {temp_dir}:/var/tmp",
            "--property=ProtectSystem=strict",
            "--property=ProtectHome=yes",
            "--property=InaccessiblePaths=/mnt /home /dev/shm",
            "--property=PrivateTmp=no",
            "--property=PrivateDevices=yes",
            "--property=PrivateMounts=yes",
            "--property=PrivateNetwork=yes",
            "--property=NoNewPrivileges=yes",
            "--property=ProtectControlGroups=yes",
            "--property=LimitCORE=0",
            "--property=UMask=0077",
            f"--property=StandardOutput=append:{log_dir / 'stdout.log'}",
            f"--property=StandardError=append:{log_dir / 'stderr.log'}",
            f"--setenv=HOME={WORKER_SCOPE_ALIAS}/home",
            f"--setenv=XDG_CACHE_HOME={WORKER_SCOPE_ALIAS}/cache",
            f"--setenv=TMPDIR=/tmp",
            f"--setenv=TMP=/tmp",
            f"--setenv=TEMP=/tmp",
            f"--setenv=JOBLIB_TEMP_FOLDER=/tmp/joblib",
            "--", sys.executable, "-B", "-c", worker_exec,
            str(volume_mount.st_dev), f"{WORKER_SCOPE_ALIAS}/result.json",
        ]
        try:
            _run(argv, timeout=30)
        except RuntimeError as exc:
            assert log_dir is not None
            try:
                worker_stdout = (log_dir / "stdout.log").read_text(encoding="utf-8")
            except OSError as log_error:
                worker_stdout = repr(log_error)
            try:
                worker_stderr = (log_dir / "stderr.log").read_text(encoding="utf-8")
            except OSError as log_error:
                worker_stderr = repr(log_error)
            try:
                unit_state = _run([
                    "systemctl", "show", unit, "--property=LoadState", "--property=ActiveState",
                    "--property=Result", "--property=ExecMainStatus", "--no-pager",
                ])
            except RuntimeError as state_error:
                unit_state = repr(state_error)
            path_diagnostic = ",".join(
                line for line in worker_stdout.splitlines() if line.startswith(("perm ", "perm_error "))
            )
            raise RuntimeError(
                f"synthetic worker unit failed: {unit}; unit_state={unit_state}; "
                f"path_diagnostic={path_diagnostic}; worker_stderr={worker_stderr[-350:]}"
            ) from exc
        unit_state = _run([
            "systemctl", "show", unit, "--property=ActiveState", "--property=Result",
            "--property=ExecMainStatus", "--no-pager",
        ])
        if (
            "ActiveState=inactive" not in unit_state
            or "Result=success" not in unit_state
            or "ExecMainStatus=0" not in unit_state
        ):
            raise RuntimeError("synthetic write-path worker did not exit successfully")
        assert scope is not None and temp_dir is not None and home_dir is not None
        assert cache_dir is not None and log_dir is not None and output_path is not None
        result = json.loads(output_path.read_text(encoding="utf-8"))
        stdout = (log_dir / "stdout.log").read_text(encoding="utf-8")
        stderr = (log_dir / "stderr.log").read_text(encoding="utf-8")
        if (
            result.get("project_data_used") is not False
            or result.get("study_st_dev") != volume_mount.st_dev
            or set(result.get("write_st_dev_by_path", {}).values()) != {volume_mount.st_dev}
            or set(result.get("tmp_mounts", {})) != {"/tmp", "/var/tmp"}
            or any(item.get("major_minor") != volume_mount.major_minor for item in result["tmp_mounts"].values())
            or "route2 synthetic stdout marker" not in stdout
            or "route2 synthetic stderr marker" not in stderr
        ):
            raise PermissionError("a synthetic worker write escaped its study loop filesystem")
        used_bytes = volume_mount.capacity_bytes - os.statvfs(study_root).f_bfree * os.statvfs(study_root).f_frsize
        return {
            "probe_kind": "synthetic_worker_tmp_cache_home_and_logs_on_study_loop",
            "probe_id": probe_id,
            "unit": unit,
            "image_path": str(image),
            "image_bytes": image.stat().st_size,
            "mountpoint": str(mountpoint),
            "study_root": str(study_root),
            "volume_mount": asdict(volume_mount),
            "worker_result": result,
            "unit_state": unit_state,
            "stdout_log_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            "stderr_log_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
            "study_used_bytes_before_cleanup": used_bytes,
            "project_data_used": False,
            "experiment_authorized": False,
        }
    finally:
        try:
            if "ActiveState=active" in _run([
                "systemctl", "show", unit, "--property=ActiveState", "--no-pager",
            ]):
                _run(["systemctl", "stop", unit], timeout=30)
        except (RuntimeError, subprocess.CalledProcessError):
            pass
        if mounted:
            _run(["umount", str(mountpoint)], timeout=30)
        if loop_device:
            _run(["losetup", "--detach", loop_device], timeout=30)
        if scratch.exists():
            resolved_base = scratch_base.resolve(strict=True)
            resolved_scratch = scratch.resolve(strict=True)
            if (
                resolved_scratch.parent != resolved_base
                or not resolved_scratch.name.startswith("route2-write-probe-")
            ):
                raise RuntimeError("synthetic write-path cleanup target escaped its scratch namespace")
            shutil.rmtree(resolved_scratch)


def _wall_terminal_child(
    invocation_id: str, total_wall_ns: int, descriptor_path_text: str,
) -> dict[str, object]:
    """Write and close one fake terminal inside a short-lived systemd unit."""
    if os.environ.get("ROUTE2_SYNTHETIC_WALL_CHILD") != "1":
        raise PermissionError("synthetic terminal child must be launched by the wall probe")
    if not re.fullmatch(r"route2-wall-[a-f0-9]{16,32}", invocation_id):
        raise ValueError("synthetic wall invocation ID is malformed")
    if type(total_wall_ns) is not int or total_wall_ns <= 0:
        raise ValueError("synthetic total wall limit is invalid")
    start_ns = time.monotonic_ns()
    descriptor_path = Path(descriptor_path_text)
    if not descriptor_path.is_absolute() or descriptor_path.name != "descriptor.json":
        raise PermissionError("synthetic terminal descriptor must be an absolute fixed-name path")
    scratch = descriptor_path.parent
    if (
        scratch.is_symlink() or not scratch.is_dir()
        or scratch.resolve(strict=True).parent != SCRATCH_BASE.resolve(strict=True)
        or not scratch.name.startswith("route2-wall-terminal-")
    ):
        raise PermissionError("synthetic terminal worker scratch directory is not controller-owned")
    terminal_path = scratch / "terminal.json"
    encoded = _canonical({
        "schema": "route2_synthetic_terminal_v1",
        "invocation_id": invocation_id,
        "terminal_status": "synthetic_only",
        "project_data_used": False,
    }) + b"\n"
    fd = os.open(terminal_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        if os.write(fd, encoded) != len(encoded):
            raise OSError("partial synthetic terminal write")
        os.fsync(fd)
    finally:
        os.close(fd)
    directory_fd = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    closed_ns = time.monotonic_ns()
    result = {
        "probe_kind": "synthetic_terminal_close",
        "invocation_id": invocation_id,
        "terminal_path": str(terminal_path),
        "terminal_sha256": hashlib.sha256(encoded).hexdigest(),
        "invocation_started_ns": start_ns,
        "terminal_closed_ns": closed_ns,
        "deadline_ns": start_ns + total_wall_ns,
        "project_data_used": False,
    }
    descriptor = _canonical(result) + b"\n"
    descriptor_fd = os.open(
        descriptor_path,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
        0o600,
    )
    try:
        if os.write(descriptor_fd, descriptor) != len(descriptor):
            raise OSError("partial synthetic terminal descriptor write")
        os.fsync(descriptor_fd)
    finally:
        os.close(descriptor_fd)
    directory_fd = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return result


def _synthetic_unit_state(unit: str) -> dict[str, object]:
    if not re.fullmatch(r"route2-synthetic-wall-[a-f0-9]{16}\.service", unit):
        raise PermissionError("wall probe may inspect only its exact synthetic unit")
    def sample() -> dict[str, str]:
        output = _run([
            "systemctl", "show", unit,
            "--property=LoadState", "--property=ActiveState", "--property=SubState",
            "--property=Result", "--property=ExecMainStatus", "--property=MainPID",
            "--property=ControlGroup", "--no-pager",
        ])
        return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)

    before_stop = sample()
    cgroup = before_stop.get("ControlGroup", "")
    if cgroup:
        if not cgroup.startswith("/system.slice/"):
            raise PermissionError("synthetic terminal unit lacks its exact service cgroup")
        path = Path("/sys/fs/cgroup") / cgroup.lstrip("/")
        if not path.exists():
            raise PermissionError("synthetic terminal cgroup disappeared before its exit proof")
        if any(line for line in (path / "cgroup.procs").read_text().splitlines() if line):
            raise PermissionError("synthetic terminal unit still has a live cgroup process")
    if (
        before_stop.get("LoadState") != "loaded"
        or before_stop.get("ActiveState") != "active"
        or before_stop.get("SubState") != "exited"
        or before_stop.get("Result") != "success"
        or before_stop.get("ExecMainStatus") != "0"
        or before_stop.get("MainPID") != "0"
    ):
        raise PermissionError("synthetic terminal unit did not exit successfully before stop")
    _run(["systemctl", "stop", unit])
    inactive = sample()
    if (
        inactive.get("ActiveState") != "inactive"
        or inactive.get("SubState") != "dead"
        or inactive.get("Result") != "success"
        or inactive.get("ExecMainStatus") != "0"
        or inactive.get("MainPID") != "0"
    ):
        raise PermissionError("synthetic terminal unit did not become inactive after stop")
    inactive_summary = {
        "active_state": inactive.get("ActiveState"),
        "sub_state": inactive.get("SubState"),
        "unit_result": inactive.get("Result"),
        "exit_status": int(inactive["ExecMainStatus"]),
        "main_pid": int(inactive["MainPID"]),
        "load_state": inactive.get("LoadState"),
    }
    return {
        "unit_name": unit,
        "before_stop": before_stop,
        "inactive": inactive_summary,
        "cgroup_processes_empty": True,
        "observed_monotonic_ns": time.monotonic_ns(),
    }


def probe_wall_external_linux(
    invocation_id: str, unit: str, total_wall_ns: int,
) -> dict[str, object]:
    """Run a synthetic child, verify its close/exit, then return to Windows QPC."""
    if os.geteuid() != 0:
        raise PermissionError("external wall probe requires WSL root")
    if not re.fullmatch(r"route2-wall-[a-f0-9]{16}", invocation_id):
        raise ValueError("synthetic wall invocation identity is malformed")
    if not re.fullmatch(r"route2-synthetic-wall-[a-f0-9]{16}\.service", unit):
        raise ValueError("synthetic wall unit identity is malformed")
    if type(total_wall_ns) is not int or total_wall_ns <= 0:
        raise ValueError("synthetic wall duration is invalid")
    SCRATCH_BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="route2-wall-terminal-", dir=SCRATCH_BASE))
    descriptor_path = scratch / "descriptor.json"
    started_ns = time.monotonic_ns()
    try:
        _run([
            "systemd-run", "--system", "--no-block", "--unit", unit[:-8],
            "--property=Type=exec", "--property=RemainAfterExit=yes",
            "--property=Restart=no", "--property=KillMode=control-group",
            "--property=RuntimeMaxSec=5s", "--property=TimeoutStopSec=1s",
            "--property=StandardOutput=null", "--property=StandardError=null",
            "--setenv=ROUTE2_SYNTHETIC_WALL_CHILD=1",
            "--", sys.executable, "-B", str(Path(__file__).resolve()),
            "_wall-terminal", invocation_id, str(total_wall_ns), str(descriptor_path),
        ], timeout=10)
        supervisor_deadline = time.monotonic_ns() + 8_000_000_000
        while True:
            values_output = _run([
                "systemctl", "show", unit,
                "--property=LoadState", "--property=ActiveState", "--property=SubState",
                "--property=Result", "--property=ExecMainStatus", "--property=MainPID",
                "--property=ControlGroup", "--no-pager",
            ], timeout=3)
            values = dict(line.split("=", 1) for line in values_output.splitlines() if "=" in line)
            if values.get("LoadState") == "loaded" and values.get("SubState") == "exited":
                break
            if time.monotonic_ns() >= supervisor_deadline:
                raise TimeoutError("synthetic terminal service did not exit before the observer deadline")
            time.sleep(0.02)
        terminal = json.loads(descriptor_path.read_bytes())
        unit_state = _synthetic_unit_state(unit)
        terminal_check = _verify_synthetic_terminal(
            str(terminal["terminal_path"]), str(terminal["terminal_sha256"]),
        )
        return {
            "probe_kind": "synthetic_terminal_and_inactive_unit_observation",
            "linux_supervisor_started_ns": started_ns,
            "terminal": terminal,
            "unit_state": unit_state,
            "terminal_reverification": terminal_check,
            "project_data_used": False,
            "experiment_authorized": False,
        }
    finally:
        if scratch.exists() and scratch.resolve().parent == SCRATCH_BASE.resolve() and scratch.name.startswith("route2-wall-terminal-"):
            shutil.rmtree(scratch)
        terminal_path = Path(locals().get("terminal", {}).get("terminal_path", ""))
        if (
            terminal_path.name == "terminal.json"
            and terminal_path.parent.name.startswith("route2-wall-terminal-")
            and terminal_path.parent.resolve().parent == SCRATCH_BASE.resolve()
            and terminal_path.parent.resolve() != scratch.resolve()
        ):
            shutil.rmtree(terminal_path.parent)


def _verify_synthetic_terminal(path_text: str, expected_sha256: str) -> dict[str, object]:
    base = SCRATCH_BASE.resolve(strict=True)
    path = Path(path_text)
    if path.is_symlink() or not path.is_file():
        raise PermissionError("synthetic terminal path is absent or linked")
    resolved = path.resolve(strict=True)
    if base not in resolved.parents or resolved.name != "terminal.json":
        raise PermissionError("synthetic terminal path escaped its scratch namespace")
    raw = resolved.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256.lower():
        raise PermissionError("synthetic terminal bytes changed after the unit exited")
    value = json.loads(raw)
    if value.get("project_data_used") is not False:
        raise PermissionError("synthetic terminal unexpectedly contains project data")
    return {
        "terminal_sha256": expected_sha256.lower(),
        "terminal_bytes": len(raw),
        "terminal_reverified": True,
        "observed_monotonic_ns": time.monotonic_ns(),
    }
def _boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def write_post_terminal_wall_receipt(
    path: Path, *, invocation_id: str, terminal_sha256: str,
    start_monotonic_ns: int, terminal_closed_ns: int, deadline_ns: int,
) -> dict[str, object]:
    """Persist a terminal-bound receipt, then make a fail-closed live check.

    The returned post-close observation is intentionally not claimed to be
    durable.  An external verifier must bind its outcome to the service exit.
    """
    if not invocation_id or len(terminal_sha256) != 64 or any(c not in "0123456789abcdef" for c in terminal_sha256.lower()):
        raise ValueError("invocation ID and exact terminal SHA-256 are required")
    if not (0 < start_monotonic_ns <= terminal_closed_ns <= time.monotonic_ns()):
        raise ValueError("terminal timing order is invalid")
    if path.exists() or path.is_symlink():
        raise FileExistsError("wall receipt is one-time and nonrecoverable")
    payload = {
        "schema": "route2-wall-receipt-v1",
        "invocation_id": invocation_id,
        "terminal_sha256": terminal_sha256.lower(),
        "boot_id": _boot_id(),
        "start_monotonic_ns": start_monotonic_ns,
        "terminal_closed_ns": terminal_closed_ns,
        "deadline_ns": deadline_ns,
        "receipt_write_started_ns": time.monotonic_ns(),
    }
    encoded = _canonical(payload) + b"\n"
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        if os.write(fd, encoded) != len(encoded):
            raise OSError("partial wall receipt write")
        os.fsync(fd)
    finally:
        os.close(fd)
    dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    post_close_ns = time.monotonic_ns()
    return {
        "receipt_sha256": hashlib.sha256(encoded).hexdigest(),
        "post_close_monotonic_ns": post_close_ns,
        "terminal_closed_before_deadline": terminal_closed_ns <= deadline_ns,
        "post_close_before_deadline": post_close_ns <= deadline_ns,
        "post_close_result_durable": False,
    }


def verify_wall_receipt_live(
    path: Path, *, invocation_id: str, terminal_sha256: str,
) -> dict[str, object]:
    """External immediate post-close verifier; late, absent or stale fails."""
    try:
        raw = path.read_bytes()
        record = json.loads(raw)
    except (OSError, ValueError):
        return {"accepted_now": False, "reason": "receipt_absent_or_invalid"}
    now_ns = time.monotonic_ns()
    valid = (
        record.get("schema") == "route2-wall-receipt-v1"
        and record.get("invocation_id") == invocation_id
        and record.get("terminal_sha256") == terminal_sha256.lower()
        and record.get("boot_id") == _boot_id()
        and isinstance(record.get("deadline_ns"), int)
        and isinstance(record.get("start_monotonic_ns"), int)
        and isinstance(record.get("terminal_closed_ns"), int)
        and record["start_monotonic_ns"] <= record["terminal_closed_ns"] <= record["deadline_ns"]
        and now_ns <= record["deadline_ns"]
    )
    return {"accepted_now": valid, "observed_monotonic_ns": now_ns, "receipt_sha256": hashlib.sha256(raw).hexdigest()}


def probe_wall(scratch_base: Path = SCRATCH_BASE) -> dict[str, object]:
    """No-data terminal/receipt ordering and fail-closed negative checks."""
    scratch_base.mkdir(mode=0o700, parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="route2-wall-probe-", dir=scratch_base))
    _refuse_formal_namespace(scratch)
    try:
        start = time.monotonic_ns()
        terminal = scratch / "fake-terminal.json"
        terminal_bytes = b'{"synthetic":true}\n'
        with terminal.open("xb") as output:
            output.write(terminal_bytes)
            output.flush()
            os.fsync(output.fileno())
        terminal_closed = time.monotonic_ns()
        terminal_sha = hashlib.sha256(terminal_bytes).hexdigest()
        deadline = start + 5_000_000_000
        good_path = scratch / "wall-receipt.json"
        good_write = write_post_terminal_wall_receipt(
            good_path, invocation_id="synthetic-wall", terminal_sha256=terminal_sha,
            start_monotonic_ns=start, terminal_closed_ns=terminal_closed,
            deadline_ns=deadline,
        )
        good_verify = verify_wall_receipt_live(
            good_path, invocation_id="synthetic-wall", terminal_sha256=terminal_sha,
        )
        absent_verify = verify_wall_receipt_live(
            scratch / "absent.json", invocation_id="synthetic-wall", terminal_sha256=terminal_sha,
        )
        late_path = scratch / "late-receipt.json"
        late_write = write_post_terminal_wall_receipt(
            late_path, invocation_id="synthetic-wall-late", terminal_sha256=terminal_sha,
            start_monotonic_ns=start, terminal_closed_ns=terminal_closed,
            deadline_ns=terminal_closed - 1,
        )
        late_verify = verify_wall_receipt_live(
            late_path, invocation_id="synthetic-wall-late", terminal_sha256=terminal_sha,
        )
        if not (good_write["post_close_before_deadline"] and good_verify["accepted_now"]):
            raise RuntimeError("synthetic on-time receipt was not accepted")
        if absent_verify["accepted_now"] or late_verify["accepted_now"]:
            raise RuntimeError("missing or late synthetic receipt was accepted")
        return {
            "probe_kind": "synthetic_post_terminal_wall_receipt",
            "terminal_sha256": terminal_sha,
            "terminal_closed_monotonic_ns": terminal_closed,
            "on_time_write": good_write,
            "on_time_live_verify": good_verify,
            "absent_live_verify": absent_verify,
            "late_write": late_write,
            "late_live_verify": late_verify,
            "durable_external_completion_event_proven": False,
            "experiment_authorized": False,
        }
    finally:
        if scratch.exists() and scratch.resolve().parent == scratch_base.resolve() and scratch.name.startswith("route2-wall-probe-"):
            shutil.rmtree(scratch)


def _main() -> None:
    if sys.platform != "linux":
        raise SystemExit("WSL controller probes must execute under Linux")
    if len(sys.argv) not in (2, 3, 4, 5):
        raise SystemExit("usage: wsl_controller.py {preflight|preflight-host PATH|probe-disk|probe-cgroup|probe-bind|probe-write-paths|probe-wall|probe-wall-external ID UNIT NS|synthetic-unit-state UNIT|verify-synthetic-terminal PATH SHA|_wall-terminal ID NS DESCRIPTOR|_cgroup_child}")
    command = sys.argv[1]
    if command == "preflight":
        result = guest_backing_preflight()
    elif command == "preflight-host" and len(sys.argv) == 3:
        result = live_vhdx_host_free(Path(sys.argv[2]))
    elif command == "probe-disk":
        result = probe_disk()
    elif command == "probe-cgroup":
        result = probe_cgroup()
    elif command == "probe-bind":
        result = probe_readonly_file_bind()
    elif command == "probe-write-paths":
        result = probe_worker_write_paths()
    elif command == "synthetic-unit-state" and len(sys.argv) == 3:
        result = _synthetic_unit_state(sys.argv[2])
    elif command == "verify-synthetic-terminal" and len(sys.argv) == 4:
        result = _verify_synthetic_terminal(sys.argv[2], sys.argv[3])
    elif command == "probe-wall-external" and len(sys.argv) == 5:
        result = probe_wall_external_linux(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif command == "_wall-terminal" and len(sys.argv) == 5:
        result = _wall_terminal_child(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif command == "probe-wall":
        result = probe_wall()
    elif command == "_cgroup_child":
        result = _cgroup_child()
    else:
        raise SystemExit("unknown probe command")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    _main()
