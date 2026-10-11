"""Pure capacity/accounting validation; never provisions or issues admission.

Native evidence is supplied by a separately installed, independently reviewed
verifier. This module cannot turn a caller-populated dataclass into a physical
cap, a live volume sample, an authorization or a measured peak.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
from typing import Protocol

from .capacity_plan import (
    Allocation, BASELINE_ITEMS, ConfirmedMethods, DeploymentPlan, EvidenceRef, ProposedCeiling,
    FreeSample, GIB, GUEST_CONTROL_ROOT, LAYERS, STUDY_ID, WRITE_REQUIREMENTS, proposed_fixed_carrier_plan,
    confirmed_preimage_floor_bytes,
)


class EvidenceVerifier(Protocol):
    def authenticated_bytes(self, reference: EvidenceRef) -> bytes:
        """Authenticate authority, review and native provenance before return.

        Implementations must reject synthetic receipts, caller assertions,
        unreviewed installations and stale native identities. No permissive
        verifier is supplied here. Reading arbitrary matching JSON is inadequate.
        """


@dataclass(frozen=True)
class Problem:
    code: str
    subject: str
    detail: str


@dataclass(frozen=True)
class LayerBalance:
    layer: str
    baseline_allocated_bytes: int | None
    peak_increment_bytes: int | None
    cleanup_reserve_bytes: int | None
    minimum_usable_capacity_bytes: int | None
    hard_cap_bytes: int | None
    remaining_after_baseline_bytes: int | None
    remaining_after_peak_and_cleanup_bytes: int | None
    unresolved_allocations: tuple[str, ...]
    live_free_bytes: int | None


@dataclass(frozen=True)
class CapacityReport:
    plan_sha256: str
    scope: str
    balances: tuple[LayerBalance, ...]
    problems: tuple[Problem, ...]
    status: str
    proposed_balances: tuple[dict, ...] = ()
    deployed: bool = False
    experiment_authorized: bool = False

    def review_content(self) -> dict:
        return asdict(self)


def _integer(value, minimum=0) -> bool:
    return type(value) is int and value >= minimum


def _valid_ceiling(item):
    return (type(item) is ProposedCeiling and type(item.layer) is str and item.layer in LAYERS
            and all(_integer(value, 1) for value in (
        item.minimum_formatted_usable_bytes, item.proposed_allocation_cap_bytes,
        item.baseline_ceiling_bytes, item.future_peak_increment_ceiling_bytes, item.cleanup_reserve_bytes)))


def _sha(value) -> bool:
    return (type(value) is str and len(value) == 64 and value != "0" * 64
            and all(character in "0123456789abcdef" for character in value))


def _id(value) -> bool:
    return type(value) is str and bool(value.strip()) and value not in {"NOT_ISSUED", "UNKNOWN", "TBD"}


def _absolute(value, layer) -> bool:
    if not _id(value) or "\x00" in value:
        return False
    path = PurePosixPath(value) if layer == "guest_fs" else PureWindowsPath(value)
    return path.is_absolute() and ".." not in path.parts


def _same_confirmed_methods(actual) -> bool:
    if type(actual) is not ConfirmedMethods:
        return False
    expected = ConfirmedMethods()
    return all(type(getattr(actual, name)) is type(getattr(expected, name))
               and getattr(actual, name) == getattr(expected, name)
               for name in ConfirmedMethods.__dataclass_fields__)


class _Checks:
    def __init__(self, plan, verifier):
        self.plan_hash = plan.sha256
        self.verifier = verifier
        self.problems = []

    def reject(self, code, subject, detail):
        self.problems.append(Problem(code, subject, detail))

    def evidence(self, reference, kind, subject, claims, *, origin="native"):
        if (not isinstance(reference, EvidenceRef) or reference.kind != kind
                or reference.subject != subject or not _sha(reference.sha256)
                or not _id(reference.review_id) or self.verifier is None):
            self.reject("EVIDENCE_MISSING", subject, f"Authenticated reviewed {kind} evidence required")
            return False
        try:
            raw = self.verifier.authenticated_bytes(reference)
            if type(raw) is not bytes or not 0 < len(raw) <= 8 << 20:
                raise ValueError("bounded raw authenticated receipt required")
            if hashlib.sha256(raw).hexdigest() != reference.sha256:
                raise ValueError("receipt digest mismatch")
            # Duplicate keys are ambiguous even if an external verifier misses them.
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate receipt key")
                    result[key] = value
                return result
            payload = json.loads(raw, object_pairs_hook=unique,
                                 parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if type(payload) is not dict:
                raise ValueError("receipt must be a plain JSON object")
            binding = {"kind": kind, "subject": subject, "plan_sha256": self.plan_hash,
                       "review_id": reference.review_id, "review_status": "PASS", "origin": origin}
            # Type-aware JSON comparison prevents true/1 and false/0 equivalence.
            for key, value in {**binding, **claims}.items():
                if key not in payload or json.dumps(payload[key], sort_keys=True, allow_nan=False) != json.dumps(value, sort_keys=True, allow_nan=False):
                    raise ValueError(f"receipt does not bind {key}")
            return True
        except Exception as exc:
            self.reject("EVIDENCE_INVALID", subject, f"{kind} receipt rejected: {type(exc).__name__}")
            return False

    def amount(self, amount, subject, phase):
        if not isinstance(amount, Allocation) or not _integer(amount.bytes):
            self.reject("ALLOCATION_UNKNOWN", subject, f"{phase} allocated bytes must be explicit, including zero")
            return None
        permitted = {"native_allocated"} if phase == "baseline" else {"conservative_upper_bound"}
        if amount.basis not in permitted:
            self.reject("ALLOCATION_BASIS", subject, f"{phase} requires {sorted(permitted)}")
        self.evidence(amount.evidence, f"allocation_{phase}", subject,
                      {"allocated_bytes": amount.bytes, "basis": amount.basis},
                      origin="native" if phase == "baseline" else "reviewed_bound")
        return amount.bytes


def validate_capacity_plan(
    plan: DeploymentPlan, *, verifier: EvidenceVerifier | None = None,
    preimage_samples: tuple[FreeSample, ...] = (), invocation_id: str | None = None,
    require_live_preimage: bool = False,
) -> CapacityReport:
    """Return reviewable deficits and balances, never an execution capability.

    DEPLOYMENT_ACCOUNTING_EVIDENCE_COMPLETE requires native proof and reviewed
    storage budgets, unlike the separate static proposal check. Neither it nor
    PREIMAGE_EVIDENCE_COMPLETE replaces full A+B implementation/admission review.
    """
    checks = _Checks(plan, verifier)
    if plan.current_host.external_admin_deployment_capability is None:
        checks.reject("EXTERNAL_ADMIN_REQUIRED", "installation", "Current process is not elevated and VHD cmdlets unavailable; diskpart existence cannot establish native deployment capability")
    if plan.current_host.deployed is not True:
        checks.reject("NOT_DEPLOYED", "installation", "Proposed storage objects have not been installed; static plan validity cannot mint native evidence")
    if (plan.schema != "route2_dedicated_capacity_plan_v1" or plan.study_id != STUDY_ID
            or not _same_confirmed_methods(plan.methods)):
        checks.reject("METHOD_CHANGED", "confirmed_methods", "Owner-confirmed methods must enter the final frozen policy unchanged")
    if plan.guest_control_root != GUEST_CONTROL_ROOT:
        checks.reject("CONTROL_ROOT_CHANGED", "guest_control", "Canonical controller mount is /var/lib/route2-controller")
    topology = plan.topology
    if (topology.mode != "fixed_preallocated_carrier" or topology.dedicated_unused_partition_available is not False
            or topology.actual_volume_guid != "dbd01263-98ac-43a9-a44c-5dcc3d2e02d1"
            or topology.disk_number != 1 or topology.partition_number != 2 or topology.filesystem != "NTFS"):
        checks.reject("TOPOLOGY_CHANGED", "E:", "This proposal is bound to the reported E: Disk1/partition2 fallback")
    if (not _absolute(topology.carrier_path, "windows_physical")
            or not _absolute(topology.guest_vhdx_path, "carrier_fs")
            or not _integer(topology.carrier_size_bytes, 1)
            or not all(_id(value) for value in
                       (topology.carrier_volume_guid, topology.carrier_file_id,
                        topology.distro_registration_guid, topology.guest_vhdx_path,
                        topology.guest_vhdx_file_id, topology.guest_fs_identity))):
        checks.reject("TOPOLOGY_INCOMPLETE", "carrier", "Exact fixed carrier Q, GUID/file IDs and dedicated distro/VHDX mapping required")
    if topology.physical_cap_scope != "all_attributable_allocated_bytes_including_outer_metadata":
        checks.reject("PHYSICAL_SCOPE", "windows_physical", "Cap must include carrier extents, outer metadata and all attributable host writes")
    checks.evidence(topology.native_topology_evidence, "native_three_layer_topology", "carrier",
                    {"actual_volume_guid": topology.actual_volume_guid, "disk_number": 1, "partition_number": 2,
                     "carrier_path": topology.carrier_path, "carrier_volume_guid": topology.carrier_volume_guid,
                     "carrier_file_id": topology.carrier_file_id, "distro_registration_guid": topology.distro_registration_guid,
                     "guest_vhdx_path": topology.guest_vhdx_path, "guest_vhdx_file_id": topology.guest_vhdx_file_id,
                     "guest_fs_identity": topology.guest_fs_identity, "dedicated_workload": True,
                     "guest_virtual_capacity_bytes": topology.guest_disk_size_bytes,
                     "guest_vhdx_logical_file_bytes": topology.guest_vhdx_logical_file_bytes,
                     "guest_vhdx_allocated_file_bytes": topology.guest_vhdx_allocated_file_bytes,
                     "guest_vhd_type": "fixed", "vhd_header_bat_metadata_and_extents_verified": True})
    checks.evidence(topology.fixed_allocation_evidence, "native_fixed_carrier_allocation", "carrier",
                    {"virtual_capacity_bytes": topology.carrier_size_bytes, "file_id": topology.carrier_file_id,
                     "logical_file_bytes": topology.carrier_logical_file_bytes,
                     "allocated_file_bytes": topology.carrier_allocated_file_bytes,
                     "vhd_header_bat_metadata_and_extents_verified": True, "vhd_type": "fixed",
                     "fully_preallocated": True, "sparse": False, "compressed": False,
                     "extension_prevented": True, "differencing_or_snapshot_growth_prevented": True})
    for subject, virtual, logical, allocated in (
            ("carrier", topology.carrier_size_bytes, topology.carrier_logical_file_bytes, topology.carrier_allocated_file_bytes),
            ("guest_vhdx", topology.guest_disk_size_bytes, topology.guest_vhdx_logical_file_bytes, topology.guest_vhdx_allocated_file_bytes)):
        if not all(_integer(value, 1) for value in (virtual, logical, allocated)) or logical < virtual or allocated < logical:
            checks.reject("VHD_NATIVE_ALLOCATION_UNKNOWN", subject, "Verify virtual size, complete VHD metadata/file length and actual preallocated extents independently")
    layer_map = {item.layer: item for item in plan.layers}
    if len(layer_map) != len(plan.layers) or set(layer_map) != set(LAYERS):
        checks.reject("LAYER_SET", "capacity", "Exactly guest FS, carrier FS and actual Windows physical layers required")
    cost_map = {item.item_id: item for item in plan.costs}
    if len(cost_map) != len(plan.costs) or not {item[0] for item in BASELINE_ITEMS} <= set(cost_map):
        checks.reject("COST_SET", "accounting", "All baseline/container/control/system items required once")
    # Mandatory containment is part of the protocol, not a caller waiver.
    expected = proposed_fixed_carrier_plan()
    for item in expected.costs:
        actual = cost_map.get(item.item_id)
        if actual is None:
            continue
        actual_edges = {(fp.layer, fp.included_in) for fp in actual.footprints}
        if actual_edges != {(fp.layer, fp.included_in) for fp in item.footprints}:
            checks.reject("ACCOUNTING_CONTAINMENT", item.item_id, "Required three-layer representation changed")
    footprints = {}
    for item in plan.costs:
        if not item.footprints:
            checks.reject("UNACCOUNTED_ITEM", item.item_id, "A cost item needs at least one layer footprint")
        for fp in item.footprints:
            key = (item.item_id, fp.layer)
            if fp.layer not in LAYERS or key in footprints:
                checks.reject("FOOTPRINT_DUPLICATE", item.item_id, "Unknown or repeated layer footprint")
            footprints[key] = fp
    for (item_id, layer), fp in footprints.items():
        if fp.included_in is None:
            continue
        seen, parent = {item_id}, fp.included_in
        while parent is not None:
            if parent in seen or (parent, layer) not in footprints:
                checks.reject("CONTAINMENT_CYCLE", f"{item_id}:{layer}", "Container must exist in the same layer and be acyclic")
                break
            seen.add(parent)
            parent = footprints[(parent, layer)].included_in
        if any(value != Allocation() for value in (fp.baseline, fp.peak_increment, fp.cleanup_reserve)):
            checks.reject("DOUBLE_CHARGE", f"{item_id}:{layer}", "Contained cost must use parent envelope instead of another additive charge")
    required_writes = {entry[0]: entry for entry in WRITE_REQUIREMENTS}
    actual_writes = {item.category: item for item in plan.writes}
    if len(actual_writes) != len(plan.writes) or not set(required_writes) <= set(actual_writes):
        checks.reject("WRITE_CLASSES_MISSING", "all_writers", "Complete write inventory includes control, OS, bridge and failure paths")
    caps_by_item = {}
    for route in plan.writes:
        subject = route.category
        required = required_writes.get(subject)
        if required is not None and (route.writer, route.cost_item, route.layer) != required[1:]:
            checks.reject("WRITE_ROUTE_CHANGED", subject, "Required writer, accounting object and layer changed")
        if not _absolute(route.absolute_path, route.layer) or not _integer(route.hard_cap_bytes):
            checks.reject("WRITE_ROUTE_UNRESOLVED", subject, "Exact absolute path and actual allocated-byte cap required; zero means native-denied writes")
        if route.cost_item == "guest_control" and (not _absolute(route.absolute_path, "guest_fs")
                or not PurePosixPath(route.absolute_path).is_relative_to(PurePosixPath(GUEST_CONTROL_ROOT))):
            checks.reject("CONTROL_PATH_OUTSIDE_ROOT", subject, "Guest control writes must resolve beneath the canonical /var/lib/route2-controller mount")
        if route.cost_item == "study_image" and route.hard_cap_bytes != 4 * GIB:
            checks.reject("STUDY_CAP_CHANGED", subject, "Study image/inner filesystem share the confirmed 4GiB whole-study envelope")
        fp = footprints.get((route.cost_item, route.layer))
        if fp is None or fp.included_in is not None:
            checks.reject("WRITE_ACCOUNTING", subject, "Write must belong to a direct cost envelope in its layer")
        elif all(_integer(value.bytes) for value in (fp.baseline, fp.peak_increment, fp.cleanup_reserve)):
            envelope = fp.baseline.bytes + fp.peak_increment.bytes + fp.cleanup_reserve.bytes
            if _integer(route.hard_cap_bytes) and route.hard_cap_bytes > envelope:
                checks.reject("WRITE_CAP_EXCEEDS_RESERVATION", subject, "Native write cap exceeds its reserved allocation envelope")
        key = (route.cost_item, route.layer)
        if key in caps_by_item and caps_by_item[key] != route.hard_cap_bytes:
            checks.reject("SHARED_CAP_CHANGED", subject, "Write classes sharing a cost object must share one allocation cap")
        caps_by_item[key] = route.hard_cap_bytes
        checks.evidence(route.native_confinement_evidence, "native_write_confinement", subject,
                        {"path": route.absolute_path, "writer": route.writer, "layer": route.layer,
                         "allocation_cap_bytes": route.hard_cap_bytes, "cost_item": route.cost_item,
                         "reparse_or_mount_escape_prevented": True, "descendants_covered": True,
                         "temporary_and_failure_writes_covered": True,
                         **({"initial_study_capacity_bytes": 2 * GIB, "total_study_capacity_bytes": 4 * GIB,
                             "same_image_identity": True, "expansion_only_after_durable_stage_b_entry": True}
                            if route.cost_item == "study_image" else {})})
    checks.evidence(plan.write_inventory_evidence, "native_complete_write_inventory", "all_writers",
                    {"categories": sorted(actual_writes), "undeclared_writes_denied": True,
                     "outside_system_effects_accounted": True})
    if not _integer(plan.max_free_sample_age_ns, 1) or not _integer(plan.attempt_payload_cap_bytes, 1):
        checks.reject("SAMPLING_POLICY_UNFROZEN", "control", "Freshness and marker payload need explicit reviewed amounts, not method defaults")
    sample_map = {sample.layer: sample for sample in preimage_samples}
    if len(sample_map) != len(preimage_samples) or set(sample_map) - set(LAYERS):
        checks.reject("FREE_SAMPLE_SET", "preimage", "No duplicate or unknown sample layers")
    balances = []
    ceilings = {item.layer: item for item in plan.proposed_ceilings
                if type(item) is ProposedCeiling and type(item.layer) is str}
    if len(ceilings) != len(plan.proposed_ceilings) or set(ceilings) != set(LAYERS):
        checks.reject("PROPOSED_CEILING_SET", "proposal", "Each layer needs its own explicit baseline/growth/cleanup ceilings")
    for item in plan.proposed_ceilings:
        if not _valid_ceiling(item):
            checks.reject("PROPOSED_CEILING_INVALID", item.layer if type(item) is ProposedCeiling else "proposal",
                          "Proposed ceilings require the exact ProposedCeiling type and positive exact byte values")
        elif (item.baseline_ceiling_bytes + item.future_peak_increment_ceiling_bytes + item.cleanup_reserve_bytes
              > item.proposed_allocation_cap_bytes or item.baseline_ceiling_bytes + max(
                  confirmed_preimage_floor_bytes(item.layer),
                  item.future_peak_increment_ceiling_bytes + item.cleanup_reserve_bytes)
              > item.minimum_formatted_usable_bytes):
            checks.reject("PROPOSED_CEILING_DEFICIT", item.layer, "Proposed envelope fails baseline/floor or peak/cleanup capacity relation")
    for layer in LAYERS:
        capacity = layer_map.get(layer)
        totals, unknown = [0, 0, 0], []
        for (item_id, fp_layer), fp in footprints.items():
            if fp_layer != layer or fp.included_in is not None:
                continue
            for index, (phase, amount) in enumerate(zip(
                    ("baseline", "peak_increment", "cleanup_reserve"),
                    (fp.baseline, fp.peak_increment, fp.cleanup_reserve))):
                value = checks.amount(amount, f"{item_id}:{layer}", phase)
                if value is None:
                    unknown.append(f"{item_id}:{phase}")
                else:
                    totals[index] += value
        baseline, increment, cleanup = (totals if not unknown else (None, None, None))
        ceiling = ceilings.get(layer)
        minimum = None if unknown else baseline + max(confirmed_preimage_floor_bytes(layer), increment + cleanup)
        hard_cap = capacity.hard_cap_bytes if capacity is not None else None
        if capacity is None or not _id(capacity.identity) or not _integer(capacity.usable_capacity_bytes, 1) or not _integer(hard_cap, 1):
            checks.reject("CAPACITY_UNRESOLVED", layer, "Exact layer identity, formatted usable capacity and separate hard cap required")
        else:
            expected_identity = (topology.actual_volume_guid if layer == "windows_physical" else
                                 topology.carrier_volume_guid if layer == "carrier_fs" else topology.guest_fs_identity)
            if capacity.identity != expected_identity:
                checks.reject("LAYER_IDENTITY_CHANGED", layer, "Capacity and cap identity must equal the held topology identity")
            if _valid_ceiling(ceiling):
                if capacity.usable_capacity_bytes < ceiling.minimum_formatted_usable_bytes or hard_cap > ceiling.proposed_allocation_cap_bytes:
                    checks.reject("PROPOSED_CAPACITY_EXCEEDED", layer, "Installation must meet proposed formatted minimum and stay within proposed cap; no silent budget increase")
                if baseline is not None and (baseline > ceiling.baseline_ceiling_bytes
                        or increment > ceiling.future_peak_increment_ceiling_bytes or cleanup > ceiling.cleanup_reserve_bytes):
                    checks.reject("INSTALLATION_CEILING_EXCEEDED", layer, "Refuse installation baseline/growth/cleanup above frozen proposed ceiling; resize requires another reviewed proposal")
            if minimum is not None and capacity.usable_capacity_bytes < minimum:
                checks.reject("USABLE_CAPACITY_DEFICIT", layer,
                              "Need baseline + max(confirmed layer floor, peak increment + cleanup); carrier has no third 8GiB floor")
            if baseline is not None and baseline + increment + cleanup > hard_cap:
                checks.reject("CAP_BUDGET_DEFICIT", layer, "Baseline, worst retained peak and cleanup exceed hard cap")
            # An allocated-byte envelope includes filesystem metadata, while
            # formatted usable bytes exclude it. Do not conflate these units.
            backing_limit = (topology.guest_disk_size_bytes if layer == "guest_fs" else
                             topology.carrier_size_bytes if layer == "carrier_fs" else capacity.usable_capacity_bytes)
            if not _integer(backing_limit, 1) or hard_cap > backing_limit:
                checks.reject("CAP_EXCEEDS_BACKING", layer, "Allocated-byte cap cannot exceed the independently verified backing envelope")
            checks.evidence(capacity.capacity_evidence, "native_layer_capacity", layer,
                            {"identity": capacity.identity, "usable_capacity_bytes": capacity.usable_capacity_bytes})
            checks.evidence(capacity.cap_evidence, "native_allocated_byte_cap", layer,
                            {"identity": capacity.identity, "hard_cap_bytes": hard_cap,
                             "includes_metadata": True, "all_writers_covered": True,
                             "overflow_and_failure_reviewed": True,
                             "sid_quota_or_free_space_only": False})
        free = None
        sample = sample_map.get(layer)
        if require_live_preimage:
            expected_identity = (topology.actual_volume_guid if layer == "windows_physical" else
                                 topology.carrier_volume_guid if layer == "carrier_fs" else topology.guest_fs_identity)
            if (not isinstance(sample, FreeSample) or not _id(invocation_id)
                    or sample.invocation_id != invocation_id or sample.identity != expected_identity
                    or not _id(sample.boot_id) or not _id(sample.clock)
                    or not all(_integer(value) for value in (sample.free_bytes, sample.observed_ns, sample.checked_ns))
                    or sample.checked_ns < sample.observed_ns or not _integer(plan.max_free_sample_age_ns, 1)
                    or sample.checked_ns - sample.observed_ns > plan.max_free_sample_age_ns):
                checks.reject("PREIMAGE_SAMPLE_INVALID", layer, "Same-invocation, same-clock fresh native sample of actual layer identity required")
            else:
                free = sample.free_bytes
                # Guest and actual physical floor is owner-confirmed. Carrier
                # receives a separate balance check; no third owner-approved
                # 8GiB floor is inferred from the two confirmed floors.
                required_free = max(confirmed_preimage_floor_bytes(layer),
                                    increment + cleanup if increment is not None else 0)
                if free < required_free:
                    checks.reject("PREIMAGE_FREE_DEFICIT", layer, "Live free bytes fail independent floor or reserved future expenditure")
                checks.evidence(sample.evidence, "native_preimage_free", layer,
                                {"identity": sample.identity, "free_bytes": free, "invocation_id": invocation_id,
                                 "boot_id": sample.boot_id, "clock": sample.clock,
                                 "observed_ns": sample.observed_ns, "checked_ns": sample.checked_ns,
                                 "before_formal_image_creation": True,
                                 "actual_physical_volume_query": layer == "windows_physical"})
        balances.append(LayerBalance(
            layer, baseline, increment, cleanup, minimum, hard_cap,
            hard_cap - baseline if _integer(hard_cap) and baseline is not None else None,
            hard_cap - baseline - increment - cleanup if _integer(hard_cap) and baseline is not None else None,
            tuple(unknown), free))
    # Outer physical accounting charges the complete preallocated carrier once.
    carrier = footprints.get(("fixed_carrier", "windows_physical"))
    if carrier is not None and _integer(topology.carrier_size_bytes, 1) and _integer(carrier.baseline.bytes):
        if (carrier.baseline.bytes != topology.carrier_allocated_file_bytes
                or carrier.baseline.bytes < topology.carrier_size_bytes or carrier.peak_increment.bytes != 0):
            checks.reject("FIXED_CARRIER_CHARGE", "windows_physical", "Full Q belongs to preparation baseline; carrier extension is forbidden")
    guest_vhdx = footprints.get(("guest_vhdx", "carrier_fs"))
    if guest_vhdx is not None and _integer(guest_vhdx.baseline.bytes):
        if guest_vhdx.baseline.bytes != topology.guest_vhdx_allocated_file_bytes or guest_vhdx.peak_increment.bytes != 0:
            checks.reject("FIXED_GUEST_VHDX_CHARGE", "carrier_fs", "Reserve the complete actual fixed guest VHDX allocation once; no dynamic growth beyond it")
    if ("carrier_fs" in layer_map and _integer(topology.carrier_size_bytes, 1)
            and _integer(layer_map["carrier_fs"].usable_capacity_bytes)
            and layer_map["carrier_fs"].usable_capacity_bytes > topology.carrier_size_bytes):
        checks.reject("CARRIER_CAPACITY_FICTION", "carrier_fs", "Formatted carrier usable capacity cannot exceed fixed carrier Q")
    physical_cap = layer_map.get("windows_physical")
    checks.evidence(topology.physical_cap_evidence, "native_physical_boundary", "windows_physical",
                    {"actual_volume_guid": topology.actual_volume_guid, "disk_number": 1, "partition_number": 2,
                     "hard_cap_bytes": physical_cap.hard_cap_bytes if physical_cap else None,
                     "scope": topology.physical_cap_scope, "fixed_carrier_and_outer_metadata_covered": True,
                     "host_system_writes_covered": True, "native_enforcement": True,
                     "sid_quota_or_file_length_or_free_size_only": False})
    preparation = {item.category: item for item in plan.preparation}
    if len(preparation) != len(plan.preparation) or set(preparation) != {item.category for item in expected.preparation}:
        checks.reject("PREPARATION_SET", "preparation", "Historic and future installation/acceptance costs must be separate and complete")
    for item in plan.preparation:
        if type(item.scope) is not str or not item.scope.strip():
            checks.reject("PREPARATION_SCOPE_UNKNOWN", item.category, "Preparation budget requires an explicit nonempty scope")
        if not all(_integer(value) for value in (item.already_incurred_bytes, item.future_peak_bytes, item.byte_cap,
                                                 item.wall_cap_ns, item.ram_cap_bytes, item.task_cap, item.cpu_percent_cap)):
            checks.reject("PREPARATION_UNKNOWN", item.category, "Unknown previous expenditure is not zero; explicit future byte/wall/RAM/task/CPU budget required")
        elif item.future_peak_bytes > item.byte_cap:
            checks.reject("PREPARATION_DEFICIT", item.category, "Future one-time expenditure exceeds separate preparation cap")
        checks.evidence(item.approval, "preparation_budget", item.category,
                        {"already_incurred_bytes": item.already_incurred_bytes, "future_peak_bytes": item.future_peak_bytes,
                         "byte_cap": item.byte_cap, "wall_cap_ns": item.wall_cap_ns,
                         "ram_cap_bytes": item.ram_cap_bytes, "task_cap": item.task_cap,
                         "cpu_percent_cap": item.cpu_percent_cap, "scope": item.scope}, origin="owner_decision")
    outside = {item.owner: item for item in plan.outside_resources}
    if len(outside) != len(plan.outside_resources) or set(outside) != {item.owner for item in expected.outside_resources}:
        checks.reject("OUTSIDE_RESOURCE_SET", "observers", "Both external observers/launchers and every helper require budgets")
    for item in plan.outside_resources:
        values = (item.memory_cap_bytes, item.task_cap, item.cpu_percent_cap, item.wall_cap_ns)
        if not all(_integer(value, 1) for value in values):
            checks.reject("OUTSIDE_RESOURCES_UNKNOWN", item.owner, "Resources outside TasksMax=2 are not free; all caps required")
        checks.evidence(item.native_cap_evidence, "native_outside_resource_caps", item.owner,
                        {"memory_cap_bytes": item.memory_cap_bytes, "task_cap": item.task_cap,
                         "cpu_percent_cap": item.cpu_percent_cap, "wall_cap_ns": item.wall_cap_ns,
                         "all_helpers_covered": True})
    checks.evidence(plan.storage_budget_approval, "storage_and_control_budget", STUDY_ID,
                    {"three_layers_accounted": True, "max_free_sample_age_ns": plan.max_free_sample_age_ns,
                     "attempt_payload_cap_bytes": plan.attempt_payload_cap_bytes}, origin="owner_decision")
    checks.evidence(plan.installation_review, "independent_installation_review", STUDY_ID,
                    {"complete_write_inventory": True, "native_physical_cap": True,
                     "failure_retention_and_cleanup": True, "readonly_execution_closures": True})
    problems = tuple(checks.problems)
    return CapacityReport(checks.plan_hash, "three-layer deployment accounting only", tuple(balances), problems,
                          "BLOCKED" if problems else "PREIMAGE_EVIDENCE_COMPLETE" if require_live_preimage else "DEPLOYMENT_ACCOUNTING_EVIDENCE_COMPLETE",
                          tuple(item.balances() for item in plan.proposed_ceilings if _valid_ceiling(item)),
                          deployed=not problems and plan.current_host.deployed is True)


def validate_proposed_capacity(plan: DeploymentPlan) -> dict:
    """Static arithmetic and topology checks, separate from native deployment.

    Serializes proposed remaining budgets even though actual baseline/live free
    are unknown. This check grants no installation or execution authorization.
    """
    problems = []
    if plan.schema != "route2_dedicated_capacity_plan_v1" or plan.study_id != STUDY_ID or not _same_confirmed_methods(plan.methods):
        problems.append("Schema/study identity or owner-confirmed methods changed")
    if plan.guest_control_root != GUEST_CONTROL_ROOT:
        problems.append("Canonical guest controller root must be /var/lib/route2-controller")
    ceilings = {item.layer: item for item in plan.proposed_ceilings
                if type(item) is ProposedCeiling and type(item.layer) is str}
    if len(ceilings) != len(plan.proposed_ceilings) or set(ceilings) != set(LAYERS):
        problems.append("Exactly three proposed layer envelopes required")
    for item in plan.proposed_ceilings:
        if not _valid_ceiling(item):
            subject = item.layer if type(item) is ProposedCeiling else "proposal"
            problems.append(f"{subject}: exact ProposedCeiling type and explicit positive ceilings required")
        elif (item.baseline_ceiling_bytes + max(confirmed_preimage_floor_bytes(item.layer), item.future_peak_increment_ceiling_bytes + item.cleanup_reserve_bytes)
              > item.minimum_formatted_usable_bytes or item.baseline_ceiling_bytes
              + item.future_peak_increment_ceiling_bytes + item.cleanup_reserve_bytes > item.proposed_allocation_cap_bytes):
            problems.append(f"{item.layer}: proposed baseline/floor/peak/cleanup arithmetic fails")
    topology = plan.topology
    if (topology.mode != "fixed_preallocated_carrier" or topology.carrier_size_bytes != 32 * GIB
            or topology.guest_disk_size_bytes != 20 * GIB or topology.actual_volume_guid != "dbd01263-98ac-43a9-a44c-5dcc3d2e02d1"
            or topology.disk_number != 1 or topology.partition_number != 2 or topology.filesystem != "NTFS"
            or topology.dedicated_unused_partition_available is not False
            or not _absolute(topology.carrier_path, "windows_physical")):
        problems.append("This concrete proposal requires fixed carrier32GiB/guest20GiB on the reported shared E: topology")
    if ("guest_fs" in ceilings and _valid_ceiling(ceilings["guest_fs"])
            and _integer(topology.guest_disk_size_bytes, 1)
            and ceilings["guest_fs"].minimum_formatted_usable_bytes > topology.guest_disk_size_bytes):
        problems.append("Guest formatted minimum exceeds nominal guest disk size")
    if ("carrier_fs" in ceilings and _valid_ceiling(ceilings["carrier_fs"])
            and _integer(topology.carrier_size_bytes, 1)
            and ceilings["carrier_fs"].minimum_formatted_usable_bytes > topology.carrier_size_bytes):
        problems.append("Carrier formatted minimum exceeds nominal carrier size")
    return {"status": "PROPOSAL_STATICALLY_CONSISTENT" if not problems else "PROPOSAL_INVALID",
            "plan_sha256": plan.sha256, "problems": problems,
            "proposed_balances": [item.balances() for item in plan.proposed_ceilings if _valid_ceiling(item)],
            "actual_allocated_baseline_bytes": None, "actual_live_free_bytes": None,
            "deployed": False, "native_physical_cap_verified": False,
            "proposed_budgets_owner_approved": False, "experiment_authorized": False,
            "external_admin_required": True,
            "strict_installation_refusal": "Refuse any measured baseline above its ceiling, formatted capacity below its minimum, unbounded metadata/system writes, or missing reviewed native enforcement"}


@dataclass(frozen=True)
class StageBProjection:
    N: int
    M: int
    S: int
    B: int
    first_available_ram_bytes: int


def project_stage_b(values: StageBProjection) -> dict:
    """Frozen V2 projection, not a durable entry gate or proof of completion.

    N=treatment candidates; B=complete UTF-8 candidate/support/16D bytes;
    S=sum of held-out rows in all 25 cycles; M=max cycle's four OOF training
    roles plus its held-out rows. Their source/freeze must be reviewed elsewhere.
    """
    if not all(_integer(value) for value in (values.N, values.M, values.S, values.B)) or not _integer(values.first_available_ram_bytes, 1):
        raise ValueError("Projection counts/bytes must be nonnegative exact integers and first available RAM positive")
    ceiling = min(4 * GIB, 3 * values.first_available_ram_bytes // 5)
    disk = 2 * GIB + 3 * (values.B + 232 * values.N + 8 * values.S) + 268_435_456
    memory = 536_870_912 + 6 * 232 * values.M
    return {"D_A_bytes": 2 * GIB, "D_A_basis": "stage_a_capacity_upper_bound_v2",
            "D_A_is_measured_peak": False, "disk_projection_bytes": disk,
            "disk_remaining_bytes": 4 * GIB - disk, "memory_projection_bytes": memory,
            "memory_ceiling_bytes": ceiling, "limit_as_per_task_bytes": ceiling // 2,
            "memory_remaining_bytes": ceiling - memory, "passes_projection": disk <= 4 * GIB and memory <= ceiling,
            "tasks_max_including_controller": 2, "ordinary_compute_worker_slots": 1,
            "experiment_authorized": False}


def remaining_wall_budget(*, stage_a_elapsed_ns: int, total_elapsed_ns: int, cumulative_fit_ns: int) -> dict:
    """Elapsed durations must already include setup, failures and persistence.

    Each duration is measured within its own continuous clock/boot/invocation;
    callers must never subtract Linux monotonic and Windows QPC epochs. Cleanup
    is inside the 1200/3600s ceilings; fit is a subset of total elapsed time.
    """
    if (not all(_integer(value) for value in (stage_a_elapsed_ns, total_elapsed_ns, cumulative_fit_ns))
            or stage_a_elapsed_ns > total_elapsed_ns or cumulative_fit_ns > total_elapsed_ns):
        raise ValueError("Invalid continuous-clock wall accounting")
    methods = ConfirmedMethods()
    return {"stage_a_remaining_ns": methods.stage_a_wall_ns - stage_a_elapsed_ns,
            "total_remaining_ns": methods.total_wall_ns - total_elapsed_ns,
            "fit_remaining_ns": methods.cumulative_fit_wall_ns - cumulative_fit_ns,
            "stage_a_work_remaining_before_cleanup_ns": methods.stage_a_wall_ns - methods.cleanup_margin_ns - stage_a_elapsed_ns,
            "total_work_remaining_before_cleanup_ns": methods.total_wall_ns - methods.cleanup_margin_ns - total_elapsed_ns,
            "cleanup_margin_is_additional_time": False,
            "over_limit": stage_a_elapsed_ns > methods.stage_a_wall_ns or total_elapsed_ns > methods.total_wall_ns
            or cumulative_fit_ns > methods.cumulative_fit_wall_ns,
            "experiment_authorized": False}
