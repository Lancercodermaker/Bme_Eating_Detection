"""Data-only Route2 deployment proposal; constructing it performs no I/O.

Read with the integrated 2026-10-03 revision of the original Route2 design,
execution plan and review. Owner decisions are methods, not installation or
experiment approval. Unknown allocation, capacity and evidence stay None.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Literal

GIB = 1 << 30
MIB = 1 << 20
STUDY_ID = "route2-candidate-overlap-v1-001"
GUEST_CONTROL_ROOT = "/var/lib/route2-controller"
LAYERS = ("guest_fs", "carrier_fs", "windows_physical")
Layer = Literal["guest_fs", "carrier_fs", "windows_physical"]


def confirmed_preimage_floor_bytes(layer):
    """Only guest and actual physical storage have the confirmed 8 GiB floor."""
    if type(layer) is not str or layer not in LAYERS:
        raise ValueError("confirmed free floor requires an exact known storage layer")
    return 0 if layer == "carrier_fs" else 8 * GIB


def content_sha256(value: object) -> str:
    """Hash JSON-compatible review content, with no filesystem access."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class EvidenceRef:
    """Reference only. A separate installed verifier must authenticate bytes.

    A hash, review ID or caller assertion alone is not native evidence. Payloads
    must bind the exact plan hash, subjects and claimed native measurements.
    """

    kind: str
    subject: str
    sha256: str
    review_id: str


@dataclass(frozen=True)
class Allocation:
    bytes: int | None = None
    basis: Literal["unknown", "native_allocated", "conservative_upper_bound"] = "unknown"
    evidence: EvidenceRef | None = None


@dataclass(frozen=True)
class Footprint:
    layer: Layer
    baseline: Allocation = Allocation()
    # Increment includes simultaneous copies and failure retention; deletion
    # never refunds an earlier peak. Cleanup headroom is a separate reservation.
    peak_increment: Allocation = Allocation()
    cleanup_reserve: Allocation = Allocation()
    included_in: str | None = None


@dataclass(frozen=True)
class CostItem:
    item_id: str
    description: str
    footprints: tuple[Footprint, ...]


@dataclass(frozen=True)
class LayerCapacity:
    layer: Layer
    identity: str | None = None
    usable_capacity_bytes: int | None = None
    hard_cap_bytes: int | None = None
    # None is distinct from a reviewed explicit zero reserve.
    capacity_evidence: EvidenceRef | None = None
    cap_evidence: EvidenceRef | None = None


@dataclass(frozen=True)
class ProposedCeiling:
    """Proposed planning envelope; every value still needs owner review.

    Formatted usable capacity is a minimum acceptance condition, not a claim
    that a nominal VHD size is usable or physically allocated storage.
    """

    layer: Layer
    minimum_formatted_usable_bytes: int
    proposed_allocation_cap_bytes: int
    baseline_ceiling_bytes: int
    future_peak_increment_ceiling_bytes: int
    cleanup_reserve_bytes: int

    def balances(self) -> dict:
        return {**asdict(self),
                "minimum_capacity_from_baseline_bytes": self.baseline_ceiling_bytes + max(
                    confirmed_preimage_floor_bytes(self.layer),
                    self.future_peak_increment_ceiling_bytes + self.cleanup_reserve_bytes),
                "remaining_after_baseline_bytes": self.proposed_allocation_cap_bytes - self.baseline_ceiling_bytes,
                "remaining_after_peak_and_cleanup_bytes": self.proposed_allocation_cap_bytes - self.baseline_ceiling_bytes
                - self.future_peak_increment_ceiling_bytes - self.cleanup_reserve_bytes,
                "remaining_basis": "nominal allocated-byte cap budget; not measured or guaranteed formatted free space",
                "minimum_usable_planning_remaining_after_baseline_bytes": self.minimum_formatted_usable_bytes - self.baseline_ceiling_bytes,
                "minimum_usable_planning_remaining_after_peak_and_cleanup_bytes": self.minimum_formatted_usable_bytes
                - self.baseline_ceiling_bytes - self.future_peak_increment_ceiling_bytes - self.cleanup_reserve_bytes,
                "minimum_usable_planning_basis": "conditional arithmetic if formatted minimum and baseline/growth/cleanup ceilings are verified; overhead still unknown",
                "actual_allocated_baseline_bytes": None, "actual_formatted_free_bytes": None,
                "basis": "proposed ceilings; no deployment or measurement", "owner_approved": False}


PROPOSED_CEILINGS = (
    # Guest baseline includes OS/runtime/views/control setup and FS metadata.
    # 6GiB future envelope covers 4GiB study image, candidate 64MiB control,
    # journal/cache/temporary copies and any measured overhead. No quota waiver.
    ProposedCeiling("guest_fs", 19 * GIB, 20 * GIB, 8 * GIB, 6 * GIB, GIB),
    # A fixed 20GiB guest VHDX is reserved in the carrier baseline, alongside
    # <=2GiB Windows closure and <=1GiB host/control/metadata combined overhead.
    ProposedCeiling("carrier_fs", 31 * GIB, 32 * GIB, 23 * GIB, GIB, GIB),
    # Entire carrier32 plus <=1GiB initial physical metadata/system writes.
    # Another 768MiB growth + 256MiB cleanup reaches the proposed 34GiB cap.
    # E: must retain an independent actual 8GiB preimage balance; 41GiB is the
    # attributable baseline+free planning minimum, not a proposed partition.
    ProposedCeiling("windows_physical", 41 * GIB, 34 * GIB, 33 * GIB, 768 * MIB, 256 * MIB),
)


@dataclass(frozen=True)
class WriteRoute:
    category: str
    writer: str
    cost_item: str
    layer: Layer
    absolute_path: str | None = None
    hard_cap_bytes: int | None = None
    native_confinement_evidence: EvidenceRef | None = None


@dataclass(frozen=True)
class PreparationCost:
    category: str
    already_incurred_bytes: int | None = None
    future_peak_bytes: int | None = None
    byte_cap: int | None = None
    wall_cap_ns: int | None = None
    ram_cap_bytes: int | None = None
    task_cap: int | None = None
    scope: str = "separate one-time preparation; no study namespace or GT"
    approval: EvidenceRef | None = None
    cpu_percent_cap: int | None = None


@dataclass(frozen=True)
class OutsideResources:
    owner: str
    memory_cap_bytes: int | None = None
    task_cap: int | None = None
    cpu_percent_cap: int | None = None
    wall_cap_ns: int | None = None
    native_cap_evidence: EvidenceRef | None = None


@dataclass(frozen=True)
class HostCapabilities:
    """Latest owner-supplied actual metadata; no native probe performed here."""

    source: str = "owner_supplied_actual_metadata"
    elevated_administrator: bool = False
    new_vhd_available: bool = False
    get_vhd_available: bool = False
    diskpart_exe_exists: bool = True
    external_admin_deployment_capability: str | None = None
    deployed: bool = False


@dataclass(frozen=True)
class FreeSample:
    layer: Layer
    identity: str
    free_bytes: int
    invocation_id: str
    boot_id: str
    clock: str
    observed_ns: int
    checked_ns: int
    evidence: EvidenceRef


@dataclass(frozen=True)
class Topology:
    mode: str = "fixed_preallocated_carrier"
    actual_volume_guid: str = "dbd01263-98ac-43a9-a44c-5dcc3d2e02d1"
    disk_number: int = 1
    partition_number: int = 2
    filesystem: str = "NTFS"
    # E: is a shared backing volume, never a dedicated study boundary.
    dedicated_unused_partition_available: bool = False
    carrier_path: str = "E:/Route2Dedicated/route2-fixed-carrier.vhdx"
    carrier_volume_guid: str | None = None
    carrier_size_bytes: int | None = 32 * GIB
    carrier_file_id: str | None = None
    carrier_logical_file_bytes: int | None = None
    carrier_allocated_file_bytes: int | None = None
    distro_registration_guid: str | None = None
    guest_vhdx_path: str | None = None
    guest_vhdx_file_id: str | None = None
    guest_disk_size_bytes: int = 20 * GIB
    guest_vhdx_logical_file_bytes: int | None = None
    guest_vhdx_allocated_file_bytes: int | None = None
    guest_fs_identity: str | None = None
    native_topology_evidence: EvidenceRef | None = None
    fixed_allocation_evidence: EvidenceRef | None = None
    physical_cap_evidence: EvidenceRef | None = None
    # Explicit proposed scope includes outer NTFS metadata and escaped system
    # writes. A fixed VHDX size alone cannot establish this physical byte cap.
    physical_cap_scope: str = "all_attributable_allocated_bytes_including_outer_metadata"


@dataclass(frozen=True)
class ConfirmedMethods:
    host_owner_trusted: bool = True
    preimage_free_floor_bytes: int = 8 * GIB
    stage_a_wall_ns: int = 1200 * 10**9
    total_wall_ns: int = 3600 * 10**9
    cumulative_fit_wall_ns: int = 900 * 10**9
    cleanup_margin_ns: int = 60 * 10**9
    memory_ceiling_bytes: int = 4 * GIB
    ram_numerator: int = 3
    ram_denominator: int = 5
    tasks_max_including_controller: int = 2
    swap_max_bytes: int = 0
    cpu_quota_percent: int = 200
    stage_a_disk_bytes: int = 2 * GIB
    total_study_disk_bytes: int = 4 * GIB
    stage_a_disk_accounting_mode: str = "stage_a_capacity_upper_bound_v2"
    gt_evaluator_calls: int = 20
    pooled_reduction_calls: int = 1
    pooled_gt_reads: int = 0


# Each entry needs a fixed path and actual allocation confinement. These are
# write *classes*, not just final artifact payloads; stdout, temporary copies,
# service logs and host-side system effects cannot escape the inventory.
WRITE_REQUIREMENTS = (
    ("study_image", "root volume controller", "study_image", "guest_fs"),
    ("study_files_and_fs_metadata", "phase workers and ledger writer", "study_image", "guest_fs"),
    ("initial_attempt_and_lock", "root bootstrap", "guest_control", "guest_fs"),
    ("expansion_attempt_and_lock", "root volume controller", "guest_control", "guest_fs"),
    ("failure_abort_ledger", "root supervisor", "guest_control", "guest_fs"),
    ("quarantine_metadata", "root supervisor", "guest_control", "guest_fs"),
    ("role_phase_mount_revoke_receipts", "root role broker", "guest_control", "guest_fs"),
    ("terminal_and_native_close_receipts", "root supervisor and Linux observer", "guest_control", "guest_fs"),
    ("systemd_journald", "systemd and journald", "guest_system_writes", "guest_fs"),
    ("mkfs_resize_stdout_stderr", "volume helpers", "guest_system_writes", "guest_fs"),
    ("runtime_tmp_cache_home", "all guest writers", "guest_system_writes", "guest_fs"),
    ("swap_core_crash", "guest kernel and crash handlers", "guest_system_writes", "guest_fs"),
    ("guest_boot_service_metadata", "dedicated distro OS", "guest_system_writes", "guest_fs"),
    ("guest_vhdx_growth_and_metadata", "WSL host", "guest_vhdx", "carrier_fs"),
    ("carrier_fs_metadata", "carrier filesystem", "carrier_metadata", "carrier_fs"),
    ("host_qpc_core_seal_anchor", "Windows outer observer", "host_control", "carrier_fs"),
    ("host_temp_readback_copies", "Windows outer observer", "host_control", "carrier_fs"),
    ("host_startup_once_quarantine", "Windows outer launcher", "host_control", "carrier_fs"),
    ("host_launcher_bridge_logs", "Windows launcher and WSL bridge", "host_control", "carrier_fs"),
    ("fixed_carrier_allocation", "Windows storage stack", "fixed_carrier", "windows_physical"),
    ("outer_ntfs_extent_inode_journal", "Windows NTFS", "outer_metadata", "windows_physical"),
    ("host_os_wsl_registry_eventlog_temp", "Windows OS and WSL registration", "host_system_writes", "windows_physical"),
)

BASELINE_ITEMS = (
    ("distro_os", "Dedicated distro OS and native libraries"),
    ("linux_runtime", "Python and all 13 wheels, installed extents/inodes"),
    ("source_runtime_snapshot", "Complete current immutable Linux execution closure"),
    ("input_view_copies", "Every approved input/view copy; no GT opened by this module"),
    ("install_cache_copies", "Installer/wheel/cache copies and temporary staging peaks"),
    ("guest_control", "Guest control filesystem including all metadata and failure headroom"),
    ("guest_system_writes", "Guest journal, runtime, HOME, temporary and kernel writes"),
    ("guest_fs_metadata", "Guest filesystem reserved blocks, directory/inode metadata"),
    ("study_image", "Same fixed 2 to 4 GiB study image, including inner FS metadata"),
    ("guest_vhdx", "Dedicated ext4.vhdx actual allocated extent/metadata envelope"),
    ("windows_execution_snapshot", "Complete readonly Windows Python/source/native bridge closure"),
    ("host_control", "Host control FS with core/seal/anchor/copies and failed attempt retention"),
    ("carrier_metadata", "Carrier filesystem overhead, reserved blocks and failure headroom"),
    ("fixed_carrier", "Entire fixed carrier allocation charged once before formal preimage gate"),
    ("outer_metadata", "Outer physical NTFS allocation metadata and system journal"),
    ("host_system_writes", "Attributable Windows/WSL system writes outside carrier"),
)


@dataclass(frozen=True)
class DeploymentPlan:
    schema: str
    study_id: str
    topology: Topology
    methods: ConfirmedMethods
    layers: tuple[LayerCapacity, ...]
    costs: tuple[CostItem, ...]
    writes: tuple[WriteRoute, ...]
    preparation: tuple[PreparationCost, ...]
    outside_resources: tuple[OutsideResources, ...]
    proposed_ceilings: tuple[ProposedCeiling, ...] = PROPOSED_CEILINGS
    current_host: HostCapabilities = HostCapabilities()
    guest_control_root: str = GUEST_CONTROL_ROOT
    # 5s / 64 KiB / guest64 MiB / host16 MiB remain candidates, not approvals.
    max_free_sample_age_ns: int | None = None
    attempt_payload_cap_bytes: int | None = None
    storage_budget_approval: EvidenceRef | None = None
    installation_review: EvidenceRef | None = None
    write_inventory_evidence: EvidenceRef | None = None

    @property
    def sha256(self) -> str:
        # References are excluded from the semantic hash to permit receipts to
        # bind this hash without a self-referential receipt-hash cycle.
        def semantic(value):
            if isinstance(value, dict):
                return {key: semantic(item) for key, item in value.items()
                        if key not in {"evidence", "approval", "storage_budget_approval", "installation_review"}
                        and not key.endswith("_evidence")}
            if isinstance(value, (tuple, list)):
                return [semantic(item) for item in value]
            return value
        return content_sha256(semantic(asdict(self)))

    def review_content(self) -> dict:
        return {"plan": asdict(self), "plan_sha256": self.sha256,
                "owner_selected_build_baseline": {
                    "distribution": "Ubuntu 22.04", "glibc": "2.35", "machine": "x86_64 LP64",
                    "native_mount_interface": "independently reviewed and frozen native helper",
                    "actual_target_identity": None, "actual_helper_artifact": None,
                    "compilation_and_abi_preparation_cost": "separate; UNKNOWN_NOT_ZERO",
                    "experiment_authorized": False},
                "inventory_source": "owner report; approximate, not live admission evidence",
                "inventory": {"drive": "E:", "filesystem": "NTFS", "disk": 1, "partition": 2,
                              "volume_guid": self.topology.actual_volume_guid,
                              "total_approx_tb": "1.898", "free_approx_tb": "1.018"},
                "unapproved_candidates": {"guest_control_bytes": 64 * MIB,
                                           "host_control_bytes": 16 * MIB,
                                           "freshness_ns": 5 * 10**9,
                                           "marker_payload_bytes": 64 * 1024},
                "proposed_capacity_balances": [item.balances() for item in self.proposed_ceilings],
                "deployment_objects": {
                    "carrier": {"path": self.topology.carrier_path, "fixed_preallocated_bytes": 32 * GIB,
                                "created": False, "native_physical_cap_verified": False},
                    "distro": {"proposed_name": "Route2Dedicated", "registered": False,
                               "guest_disk_bytes": 20 * GIB, "guest_disk_kind": "fixed; independently verify native VHD allocation"},
                    "guest_control": {"proposed_path": self.guest_control_root, "candidate_cap_bytes": 64 * MIB},
                    "host_control": {"proposed_path": "<held-carrier-volume-GUID>/route2-host-control", "candidate_cap_bytes": 16 * MIB},
                    "path_status": "proposed objects; GUIDs and per-write paths must be frozen after reviewed installation"},
                "deployment_steps": DEPLOYMENT_STEPS,
                "current_deployment": {"deployed": False, "native_proof_verified": False,
                                       "requires_external_admin": True,
                                       "reason": "current process non-elevated; New-VHD/Get-VHD unavailable; diskpart existence is not deployment capability"},
                "experiment_authorized": False}


DEPLOYMENT_STEPS = (
    "Review proposed E:/Route2Dedicated/route2-fixed-carrier.vhdx 32GiB and Route2Dedicated guest20GiB; native physical cap34GiB remains unproved.",
    "Freeze exact carrier/distro/VHDX/volume identities and Q; review physical enforcement including metadata.",
    "Trace historic scratch/dependency/snapshot costs; approve one-time installation and evidence budgets.",
    "Separately bind native helper compiler/helper/linker/header closure, temporary/failure outputs and byte/wall/RAM/task/CPU preparation budgets; never charge an existing toolchain as zero by default.",
    "After separate installation approval, preallocate the entire fixed carrier; charge all physical extents.",
    "Install dedicated distro, readonly closures and actually capped guest/host controls; measure baseline.",
    "Verify complete write confinement and native physical cap/overflow/crash/quarantine behavior.",
    "Recompute all three layer balances and reserve failure cleanup without refunding earlier peaks.",
    "Before formal image creation, same invocation live-query guest FS, carrier FS and actual E: physical GUID.",
    "Re-freeze budget, D_A V2, source/runtime/roles and numeric policy; obtain independent review IDs.",
    "Separate full A+B owner authorization and protected admission are required before any study execution.",
)


def proposed_fixed_carrier_plan() -> DeploymentPlan:
    """Concrete inventory/checklist with intentionally unmeasured byte fields.

    Proposed Q32GiB/guest20GiB and baseline ceilings are reviewable suggestions,
    not prior approvals or allocations inferred from approximate free space.
    Parent representation prevents adding inner data to its backing container
    again in the same layer. Layer totals must never be summed together.
    """
    guest = {item[0] for item in BASELINE_ITEMS[:9]}
    costs = []
    for item_id, description in BASELINE_ITEMS:
        footprints = []
        if item_id in guest:
            footprints.append(Footprint("guest_fs"))
            footprints.append(Footprint("carrier_fs", included_in="guest_vhdx"))
        elif item_id in {"guest_vhdx", "windows_execution_snapshot", "host_control", "carrier_metadata"}:
            footprints.append(Footprint("carrier_fs"))
        if item_id not in {"outer_metadata", "host_system_writes", "fixed_carrier"}:
            footprints.append(Footprint("windows_physical", included_in="fixed_carrier"))
        else:
            footprints.append(Footprint("windows_physical"))
        costs.append(CostItem(item_id, description, tuple(footprints)))
    return DeploymentPlan(
        "route2_dedicated_capacity_plan_v1", STUDY_ID, Topology(), ConfirmedMethods(),
        tuple(LayerCapacity(layer) for layer in LAYERS), tuple(costs),
        tuple(WriteRoute(*entry) for entry in WRITE_REQUIREMENTS),
        tuple(PreparationCost(category) for category in
              ("historic_scratch_probes", "historic_dependencies", "historic_source_snapshots",
               "dedicated_storage_installation", "readonly_execution_closures",
               "native_mount_helper_build_and_abi_freeze", "native_capacity_and_failure_acceptance", "final_identity_freeze")),
        tuple(OutsideResources(owner) for owner in
              ("Linux post-exit observer and helpers", "Windows launcher/QPC observer and WSL bridge")),
    )
