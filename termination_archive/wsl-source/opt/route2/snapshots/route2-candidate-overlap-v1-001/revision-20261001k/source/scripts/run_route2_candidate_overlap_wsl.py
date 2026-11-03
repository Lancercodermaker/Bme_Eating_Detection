"""Windows entry for read-only WSL preflight and no-data OS capability probes.

There is deliberately no Stage A, Stage B, candidate, fit, or evaluation command.
An approved experiment runner still requires a separately reviewed implementation
and a distinct, frozen A+B authorization.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import winreg


FLOOR_BYTES = 8 * (1 << 30)
DEFAULT_DISTRO = "Ubuntu-22.04"
LINUX_PROBE_PATH = Path(__file__).resolve().parents[1] / "src" / "eating_event" / "route2_candidate_overlap" / "wsl_controller.py"


def _distribution_base_path(name: str) -> Path:
    registry_path = r"Software\Microsoft\Windows\CurrentVersion\Lxss"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path) as distributions:
        for index in range(winreg.QueryInfoKey(distributions)[0]):
            key_name = winreg.EnumKey(distributions, index)
            with winreg.OpenKey(distributions, key_name) as entry:
                try:
                    distribution_name = winreg.QueryValueEx(entry, "DistributionName")[0]
                    base_path = winreg.QueryValueEx(entry, "BasePath")[0]
                except FileNotFoundError:
                    continue
                if distribution_name == name:
                    base = Path(os.path.expandvars(base_path)).resolve(strict=True)
                    if not base.is_dir() or base.drive == "" or str(base).startswith("\\\\"):
                        raise RuntimeError("WSL distribution base must be a local Windows directory")
                    return base
    raise FileNotFoundError(f"WSL distribution {name!r} is not registered for this Windows user")


def _win32_volume(path: Path) -> dict[str, object]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_mount = kernel.GetVolumePathNameW
    get_mount.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    get_mount.restype = ctypes.c_int
    get_name = kernel.GetVolumeNameForVolumeMountPointW
    get_name.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    get_name.restype = ctypes.c_int
    get_free = kernel.GetDiskFreeSpaceExW
    get_free.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
    ]
    get_free.restype = ctypes.c_int
    mount = ctypes.create_unicode_buffer(32768)
    if not get_mount(str(path), mount, len(mount)):
        raise ctypes.WinError(ctypes.get_last_error())
    volume_name = ctypes.create_unicode_buffer(32768)
    if not get_name(mount.value, volume_name, len(volume_name)):
        raise ctypes.WinError(ctypes.get_last_error())
    available = ctypes.c_uint64()
    total = ctypes.c_uint64()
    total_free = ctypes.c_uint64()
    if not get_free(mount.value, ctypes.byref(available), ctypes.byref(total), ctypes.byref(total_free)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {
        "mount_point": mount.value,
        "volume_id": volume_name.value,
        "available_to_user_bytes": available.value,
        "total_free_bytes": total_free.value,
        "total_bytes": total.value,
    }


def windows_vhdx_preflight(distro: str) -> dict[str, object]:
    base = _distribution_base_path(distro)
    vhdx = (base / "ext4.vhdx").resolve(strict=True)
    if vhdx.parent != base or not vhdx.is_file() or vhdx.is_symlink():
        raise RuntimeError("registered WSL VHDX is missing, linked or outside its BasePath")
    volume = _win32_volume(vhdx)
    if volume["available_to_user_bytes"] < FLOOR_BYTES or volume["total_free_bytes"] < FLOOR_BYTES:
        raise RuntimeError("VHDX Windows physical volume has less than 8 GiB free")
    return {
        "probe_kind": "windows_vhdx_physical_preflight_only",
        "distribution": distro,
        "registered_base_path": str(base),
        "vhdx_path": str(vhdx),
        "vhdx_current_length_bytes": vhdx.stat().st_size,
        "volume": volume,
        "free_floor_bytes": FLOOR_BYTES,
        "windows_physical_free_pass": True,
        "experiment_authorized": False,
    }


def _to_wsl_path(path: Path) -> str:
    absolute = path.resolve(strict=True)
    drive, tail = os.path.splitdrive(str(absolute))
    if len(drive) != 2 or drive[1] != ":":
        raise RuntimeError("probe source must be on a locally mounted drive")
    return "/mnt/" + drive[0].lower() + tail.replace("\\", "/")


def _run_wsl(distro: str, command: str, *, root: bool = False, extra: tuple[str, ...] = ()) -> dict[str, object]:
    argv = ["wsl.exe", "--distribution", distro]
    if root:
        argv += ["--user", "root"]
    argv += ["--", "python3", _to_wsl_path(LINUX_PROBE_PATH), command, *extra]
    # wsl.exe can emit UTF-16 diagnostic text on stderr while the Linux child
    # emits UTF-8 JSON on stdout.  Decode the streams independently.
    completed = subprocess.run(argv, capture_output=True, timeout=600)
    if completed.returncode != 0:
        diagnostic = completed.stderr.decode("utf-8", errors="replace")[-1000:]
        raise RuntimeError(f"WSL {command} failed ({completed.returncode}): {diagnostic}")
    lines = [line for line in completed.stdout.decode("utf-8", errors="strict").splitlines() if line.startswith("{")]
    if len(lines) != 1:
        raise RuntimeError(f"WSL {command} did not produce one JSON receipt")
    return json.loads(lines[0])


def _run_wsl_argv(distro: str, linux_argv: tuple[str, ...], *, timeout: float = 60) -> str:
    argv = ["wsl.exe", "--distribution", distro, "--user", "root", "--", *linux_argv]
    completed = subprocess.run(argv, capture_output=True, timeout=timeout)
    if completed.returncode != 0:
        diagnostic = completed.stderr.decode("utf-8", errors="replace")[-1500:]
        raise RuntimeError(f"WSL controller command failed ({completed.returncode}): {diagnostic}")
    return completed.stdout.decode("utf-8", errors="strict")


def _qpc() -> tuple[int, int]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
    kernel.QueryPerformanceFrequency.restype = ctypes.c_int
    kernel.QueryPerformanceCounter.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
    kernel.QueryPerformanceCounter.restype = ctypes.c_int
    counter = ctypes.c_longlong()
    frequency = ctypes.c_longlong()
    if not kernel.QueryPerformanceFrequency(ctypes.byref(frequency)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.QueryPerformanceCounter(ctypes.byref(counter)):
        raise ctypes.WinError(ctypes.get_last_error())
    if frequency.value <= 0 or counter.value <= 0:
        raise RuntimeError("Windows QPC returned an invalid clock sample")
    return counter.value, frequency.value


def _durable_create(path: Path, encoded: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"one-shot external wall artifact is already occupied: {path}")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        offset = 0
        while offset < len(view):
            offset += os.write(descriptor, view[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if path.read_bytes() != encoded:
        raise OSError("persisted external wall bytes differ from the durable write")
    return hashlib.sha256(encoded).hexdigest()


def external_wall_probe(distro: str) -> dict[str, object]:
    """Observe a terminal only after its WSL unit exits, then persist a QPC seal."""

    total_wall_ns = 10_000_000_000
    invocation_id = "route2-wall-" + uuid.uuid4().hex[:16]
    unit = "route2-synthetic-wall-" + uuid.uuid4().hex[:16] + ".service"
    external_started_ticks, qpc_frequency = _qpc()
    output = _run_wsl_argv(
        distro,
        (
            "python3", _to_wsl_path(LINUX_PROBE_PATH), "probe-wall-external",
            invocation_id, unit, str(total_wall_ns),
        ),
        timeout=20,
    )
    lines = [line for line in output.splitlines() if line.startswith("{")]
    if len(lines) != 1:
        raise RuntimeError("synthetic WSL controller did not return one exit receipt")
    linux_receipt = json.loads(lines[0])
    terminal = linux_receipt.get("terminal")
    unit_state = linux_receipt.get("unit_state")
    terminal_check = linux_receipt.get("terminal_reverification")
    if not isinstance(terminal, dict) or not isinstance(unit_state, dict) or not isinstance(terminal_check, dict):
        raise PermissionError("synthetic WSL controller receipt omits terminal, exit or rehash proof")
    inactive_state = unit_state.get("inactive")
    if (
        linux_receipt.get("probe_kind") != "synthetic_terminal_and_inactive_unit_observation"
        or terminal.get("probe_kind") != "synthetic_terminal_close"
        or terminal.get("invocation_id") != invocation_id
        or terminal.get("project_data_used") is not False
        or not isinstance(inactive_state, dict)
        or inactive_state.get("active_state") != "inactive"
        or unit_state.get("cgroup_processes_empty") is not True
    ):
        raise PermissionError(
            "synthetic terminal, service exit or no-data proof differs: "
            + json.dumps(linux_receipt, sort_keys=True, separators=(",", ":"))[:2000]
        )
    terminal_detected_ticks, _ = _qpc()
    unit_inactive_ticks, _ = _qpc()
    observed_monotonic_ns = terminal_check.get("observed_monotonic_ns")
    # The terminal file is fully rehashed after the unit is inactive.
    if terminal_check.get("terminal_reverified") is not True:
        raise PermissionError("external observer could not reverify closed terminal bytes")

    external_deadline_ticks = external_started_ticks + (
        total_wall_ns * qpc_frequency + 999_999_999
    ) // 1_000_000_000
    core = {
        "schema": "route2_post_exit_receipt_v1",
        "invocation_id": invocation_id,
        "unit_name": unit,
        "terminal_sha256": terminal["terminal_sha256"],
        "unit_result": inactive_state["unit_result"],
        "exit_status": inactive_state["exit_status"],
        "active_state": inactive_state["active_state"],
        "invocation_started_ns": terminal["invocation_started_ns"],
        "terminal_closed_ns": terminal["terminal_closed_ns"],
        "deadline_ns": terminal["deadline_ns"],
        "external_clock": "windows_qpc",
        "qpc_frequency": qpc_frequency,
        "external_started_ticks": external_started_ticks,
        "external_terminal_detected_ticks": terminal_detected_ticks,
        "external_unit_inactive_ticks": unit_inactive_ticks,
        "external_deadline_ticks": external_deadline_ticks,
    }
    core_bytes = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    distribution_base = _distribution_base_path(distro)
    receipt_dir = distribution_base / "route2-controller" / "synthetic-wall-probes"
    receipt_id = invocation_id.removeprefix("route2-wall-")
    core_path = receipt_dir / f"{receipt_id}.core.json"
    seal_path = receipt_dir / f"{receipt_id}.seal.json"
    core_sha256 = _durable_create(core_path, core_bytes)
    external_receipt_fsynced_ticks, _ = _qpc()
    seal = {
        "schema": "route2_windows_qpc_wall_seal_v1",
        "invocation_id": invocation_id,
        "core_path": str(core_path),
        "core_sha256": core_sha256,
        "external_receipt_fsynced_ticks": external_receipt_fsynced_ticks,
        "durable_external_event": True,
        "unit_inactive_observed": True,
    }
    seal_bytes = json.dumps(seal, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    seal_sha256 = _durable_create(seal_path, seal_bytes)
    observed_external_ticks, _ = _qpc()
    receipt = {
        **core,
        "durable_external_event": True,
        "external_receipt_fsynced_ticks": external_receipt_fsynced_ticks,
    }
    sys.path.insert(0, str(LINUX_PROBE_PATH.resolve().parents[2]))
    from eating_event.route2_candidate_overlap.linux_enforcement import verify_post_exit_receipt

    accepted = verify_post_exit_receipt(
        receipt,
        invocation_id=invocation_id,
        unit_name=unit,
        terminal_sha256=str(terminal["terminal_sha256"]),
        observed_monotonic_ns=int(observed_monotonic_ns),
        observed_external_ticks=observed_external_ticks,
        total_wall_ns=total_wall_ns,
        expected_qpc_frequency=qpc_frequency,
        expected_external_started_ticks=external_started_ticks,
    )
    evidence = {
        "probe_kind": "windows_qpc_post_terminal_persisted_wall_receipt",
        "project_data_used": False,
        "experiment_authorized": False,
        "terminal": terminal,
        "unit_state": unit_state,
        "terminal_reverification": terminal_check,
        "windows_qpc_frequency": qpc_frequency,
        "receipt_core_path": str(core_path),
        "receipt_core_sha256": core_sha256,
        "receipt_seal_path": str(seal_path),
        "receipt_seal_sha256": seal_sha256,
        "receipt": receipt,
        "observed_monotonic_ns": observed_monotonic_ns,
        "observed_external_ticks": observed_external_ticks,
        "receipt_accepted": accepted,
    }
    evidence_volume = _win32_volume(seal_path)
    if evidence_volume["volume_id"] != _win32_volume(distribution_base / "ext4.vhdx")["volume_id"]:
        raise PermissionError("external wall seal is not on the WSL VHDX physical volume")
    evidence["receipt_volume"] = evidence_volume
    return evidence


def combined_preflight(distro: str) -> dict[str, object]:
    windows = windows_vhdx_preflight(distro)
    guest = _run_wsl(distro, "preflight")
    linux_host = _run_wsl(distro, "preflight-host", extra=(_to_wsl_path(Path(windows["vhdx_path"])),))
    if guest["backing_mount"]["available_bytes"] < FLOOR_BYTES:
        raise RuntimeError("WSL guest backing layer is below the 8 GiB floor")
    if linux_host["host_volume_mount"]["capacity_bytes"] != windows["volume"]["total_bytes"]:
        raise RuntimeError("Linux 9p mount capacity differs from the registered Windows volume")
    if linux_host["vhdx_length_bytes"] != windows["vhdx_current_length_bytes"]:
        raise RuntimeError("VHDX length changed across the two-layer preflight")
    return {
        "probe_kind": "two_layer_preflight_only",
        "windows": windows,
        "guest": guest,
        "linux_live_host": linux_host,
        "both_free_at_least_8_gib": True,
        "experiment_authorized": False,
    }


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("run this wrapper from Windows; Linux probe code is in wsl_controller.py")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "probe-disk", "probe-cgroup", "probe-bind", "probe-write-paths", "probe-wall"))
    parser.add_argument("--distro", default=DEFAULT_DISTRO)
    args = parser.parse_args()
    before = combined_preflight(args.distro)
    if args.command == "preflight":
        result: dict[str, object] = before
    else:
        probe = (
            external_wall_probe(args.distro)
            if args.command == "probe-wall"
            else _run_wsl(args.distro, args.command, root=True)
        )
        after = combined_preflight(args.distro)
        if before["windows"]["volume"]["volume_id"] != after["windows"]["volume"]["volume_id"]:
            raise RuntimeError("Windows backing volume changed during the synthetic probe")
        if before["guest"]["backing_mount"]["mount_id"] != after["guest"]["backing_mount"]["mount_id"]:
            raise RuntimeError("WSL backing mount changed during the synthetic probe")
        result = {"probe_kind": args.command, "before": before, "probe": probe, "after": after, "experiment_authorized": False}
        if args.command in ("probe-wall", "probe-write-paths"):
            if args.command == "probe-wall":
                invocation = str(probe["receipt"]["invocation_id"])
                evidence_name = (
                    "2026-09-29-route2-windows-qpc-wall-probe-"
                    f"{invocation.removeprefix('route2-wall-')}.json"
                )
            else:
                evidence_name = (
                    "2026-09-29-route2-wsl-worker-write-path-probe-"
                    f"{probe['probe_id']}.json"
                )
            evidence_path = (
                Path(__file__).resolve().parents[1]
                / "docs" / "evidence"
                / evidence_name
            )
            encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
            result["evidence_file"] = str(evidence_path)
            result["evidence_sha256"] = _durable_create(evidence_path, encoded)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
