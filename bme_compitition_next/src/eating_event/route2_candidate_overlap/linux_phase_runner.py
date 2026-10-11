"""Fixed original native phase transactions, without deployment authority.

Assembly binds the live bootstrap and unstarted original controller only. It
does not start the guard, install a GT broker, load a helper or grant a view.
Execution later requires the actually installed original broker/publisher,
the unchanged installation gate and the already armed current activity clock.
The complete native installation, early start/QPC transport and data producers
are still separate missing production requirements. Private source identities
and descriptive receipts cannot manufacture those OS facts or authorize work.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import threading

from . import admission_bootstrap as bootstrap
from . import contracts
from . import linux_child_launch as children
from . import linux_gt_history as gt
from . import linux_phase_publication as publication
from . import phase_worker_entry as wire
from .budget import AppendOnlyLedger, BudgetGuard, _canonical
from .contracts import (
    CONTROL_FINAL_MATCH_FIELDS, OUTER_CONTROL_FINAL_MATCHES_PHASE, RegisteredFile,
    StudyStage, projection_scope_sha256,
)
from .gt_provider import TruthReadScope, stage_gt_fields
from .linux_production_controller import (
    LinuxProductionController, LinuxProductionOSPorts, _ASSEMBLIES,
)
from .native_failure_capture import NativeFailureCapture
from .source_snapshot import verify_snapshot_module, require_controller_owned_readonly_tree
from .startup_ownership import require_startup_binding
from .stage_b import PhaseRunReceipt

_RELATIVE = "src/eating_event/route2_candidate_overlap/linux_phase_runner.py"
_MAX_TRANSACTIONS = 512
# Strong issuances survive lost caller handles, failed operations and retirement.
_EXECUTORS = {}
_GUARD_EXECUTORS = {}
_TRANSACTIONS = {}
_GRANT = gt.LinuxNativeGTBroker.grant
_REVOKE = gt.LinuxNativeGTBroker.revoke
_PUBLISH = publication._OriginalPhaseInputPublisher.publish
_CLOSE = publication._OriginalPhaseInputPublisher.close
_LAUNCH = children._run_private_phase
_CONSUME = children._consume_private_phase_outcome
_INSTALL_GATE = LinuxProductionOSPorts.require_installation_and_write_boundary
_APPEND = AppendOnlyLedger.append
_RECEIPT = PhaseRunReceipt


class _OriginalNativePhaseRunner:
    __slots__ = ()

    def __init__(self):
        gt._deny("native phase runner requires its original private bootstrap assembly")

    def implementation_sha256(self):
        state = _EXECUTORS.get(self)
        if state is None:
            gt._deny("native phase runner has no original registered source identity")
        return _require_original_executor(self, state.guard, state.ledger).source_sha256


class _TransactionHandle:
    __slots__ = ()


@dataclass(slots=True)
class _Executor:
    handle: object
    proof: object
    issued: object
    guard: BudgetGuard
    controller: object
    assembly: object
    ledger: AppendOnlyLedger
    pid: int
    thread: object
    source_manifest: object | None = None
    source_bytes: object | None = None
    source_proof: object | None = None
    source_sha256: str = ""
    current_source_bytes: object | None = None
    owner: object | None = None
    active: object | None = None
    transactions: tuple = ()
    installed: bool = False
    failed: bool = False
    errors: NativeFailureCapture = field(default_factory=lambda: NativeFailureCapture(1024))


@dataclass(slots=True)
class _Transaction:
    executor: _Executor
    handle: object
    scope: object
    registered_view: object
    operation: object
    candidates: object
    reference_candidates: object
    control_final_matches: object
    control_metrics_sha256: object
    predictions: object
    participant_ids: object
    # All attempt, raw-return, origin and reporting slots precede grant().
    errors: NativeFailureCapture = field(default_factory=lambda: NativeFailureCapture(4096))
    buffers: tuple = ()
    origins: tuple = ()
    reports: list = field(default_factory=lambda: [None] * 16)
    report_count: int = 0
    wrapper_cycle_error: BaseException = field(default_factory=lambda: PermissionError(
        "native phase failure report has no nonrecursive original error"))
    primary_error: object | None = None
    primary_report: object | None = None
    secondary_report: object | None = None
    report_entry_report: object | None = None
    report_entry_preservation_report: object | None = None
    report_origin: object | None = None
    owner: object | None = None
    publisher: object | None = None
    broker: object | None = None
    binding: object | None = None
    current_executor: object | None = None
    view: object | None = None
    initial_ledger: tuple = ()
    retained_history: tuple = ()
    retained_ledger: tuple = ()
    retained_active: object | None = None
    policy_result: object | None = None
    budget_result: object | None = None
    journal: object | None = None
    current_budget_result: object | None = None
    current_clock: tuple = ()
    stop_ns: object | None = None
    cleanup_ns: object | None = None
    clock: tuple = ()
    scope_bytes: object | None = None
    scope_sha256: str = ""
    payload: object | None = None
    payload_sha256: str = ""
    grant_attempted: bool = False
    grant_receipt: object | None = None
    grant: object | None = None
    release: object | None = None
    release_fact: object | None = None
    grant_fact: object | None = None
    publish_attempted: bool = False
    publication_result: object | None = None
    batch: object | None = None
    published_fact: object | None = None
    historical_source: object | None = None
    commitment_key: object | None = None
    launch_attempted: bool = False
    outcome_handle: object | None = None
    child: object | None = None
    child_outcome: object | None = None
    consume_attempted: bool = False
    outcome: object | None = None
    result: object | None = None
    close_attempted: bool = False
    close_result: object | None = None
    close_returned: bool = False
    unpublished_fact: object | None = None
    revoke_attempted: bool = False
    revoke_result: object | None = None
    revoke_confirmed_fact: object | None = None
    revoke_fact: object | None = None
    revoke_event: object | None = None
    result_sha256: str = ""
    receipt: object | None = None
    complete: bool = False
    take_attempted: bool = False
    take_result: object | None = None
    retrieved: bool = False
    accept_attempted: bool = False
    acceptance_body: object | None = None
    acceptance_result: object | None = None
    acceptance_tail_result: object | None = None
    accepted_fact: object | None = None
    accepted: bool = False
    failed: bool = False


def _method_pins():
    if (gt.LinuxNativeGTBroker.grant is not _GRANT or gt.LinuxNativeGTBroker.revoke is not _REVOKE
            or publication._OriginalPhaseInputPublisher.publish is not _PUBLISH
            or publication._OriginalPhaseInputPublisher.close is not _CLOSE
            or children._run_private_phase is not _LAUNCH
            or children._consume_private_phase_outcome is not _CONSUME
            or LinuxProductionOSPorts.require_installation_and_write_boundary is not _INSTALL_GATE
            or AppendOnlyLedger.append is not _APPEND or PhaseRunReceipt is not _RECEIPT):
        gt._deny("native phase executor lost its unchanged original implementations")


def _assembly_identity(state, *, installing=False):
    proof, issued, guard, assembly = state.proof, state.issued, state.guard, state.assembly
    frozen = contracts.require_frozen_admission()
    if (type(proof) is not bootstrap.SupervisorBootstrapProof
            or type(issued) is not bootstrap._IssuedBootstrap or bootstrap._ISSUED_BOOTSTRAP is not issued
            or issued.proof is not proof or proof.frozen_admission is not frozen
            or issued.pid != state.pid or issued.thread is not state.thread
            or state.pid != os.getpid() or state.thread is not threading.current_thread()
            or type(guard) is not BudgetGuard or type(state.ledger) is not AppendOnlyLedger
            or type(state.controller) is not LinuxProductionController
            or _ASSEMBLIES.get(state.controller) is not assembly
            or assembly.guard() is not guard or assembly.approval_ledger is not state.ledger
            or guard.enforcer is not state.controller or guard.ledger is not state.ledger
            or guard.limits is not assembly.limits or guard.invocation_id != assembly.invocation_id
            or guard._invocation_started_ns != assembly.started_ns
            or proof.start_clock is None or proof.start_clock.invocation_id != assembly.invocation_id
            or proof.start_clock.invocation_started_monotonic_ns != assembly.started_ns
            or assembly.pid != state.pid or assembly.thread is not state.thread
            or type(assembly.ports) is not LinuxProductionOSPorts or assembly.failed
            or assembly.supervisor() is None or assembly.supervisor().ops is not state.controller
            or assembly.supervisor().approval is not assembly.approval
            or proof.source_snapshot_sha256 != frozen.source_snapshot_sha256.lower()
            or proof.runtime_snapshot_sha256 != frozen.runtime_snapshot_sha256.lower()):
        gt._deny("native phase assembly lost its original bootstrap/controller/guard identity")
    if installing and (issued.consumed or guard._start_entered or guard._started or assembly.attempted
            or require_startup_binding(guard) is not None or gt._OWNERS.get(guard) is not None):
        gt._deny("native phase assembly must precede original guard startup and every GT actor")
    # After assembly, consuming the original bootstrap is the expected handoff.
    # A later preflight must not pretend an unclaimed bootstrap is still needed.
    return frozen


def _install_original_phase_runner(proof, guard):
    """Fixed factory: source/identity binding only, before guard.start()."""
    with bootstrap._INSTALL_LOCK, gt._LOCK:
        if type(guard) is not BudgetGuard or guard in _GUARD_EXECUTORS:
            gt._deny("native phase executor assembly is once-only for the original guard")
        controller = guard.enforcer
        assembly = _ASSEMBLIES.get(controller) if type(controller) is LinuxProductionController else None
        issued = bootstrap._ISSUED_BOOTSTRAP
        if assembly is None or issued is None:
            gt._deny("native phase executor requires its original issued bootstrap and controller assembly")
        handle = object.__new__(_OriginalNativePhaseRunner)
        state = _Executor(handle, proof, issued, guard, controller, assembly, guard.ledger,
                          os.getpid(), threading.current_thread())
        _assembly_identity(state, installing=True)
        # Keep the failed installation attempt too. No helper is loaded here.
        _EXECUTORS[handle] = state
        _GUARD_EXECUTORS[guard] = state
        try:
            _method_pins()
            frozen = contracts.require_frozen_admission()
            state.source_manifest = bootstrap._read_snapshot_manifest(
                frozen.source_snapshot_manifest_path, max_bytes=bootstrap.MAX_SOURCE_MANIFEST_BYTES)
            state.source_bytes = bootstrap._read_verified_source_file(
                Path(frozen.source_snapshot_root), _RELATIVE, max_bytes=1 << 20)
            state.source_proof = verify_snapshot_module(
                Path(frozen.source_snapshot_root), Path(__file__), state.source_manifest,
                expected_manifest_sha256=frozen.source_snapshot_sha256.lower(),
                expected_module_relative_path=_RELATIVE, mount_path=proof.snapshots.source_mount.mount_point,
                mountinfo_text=bootstrap._read_mountinfo())
            state.source_sha256 = hashlib.sha256(state.source_bytes).hexdigest()
            require_controller_owned_readonly_tree(Path(frozen.source_snapshot_root))
            if (state.source_sha256 != frozen.phase_runner_sha256.lower()
                    or state.source_proof.snapshot != proof.snapshots.source
                    or state.source_proof.mount != proof.snapshots.source_mount):
                gt._deny("native phase executor source is absent from the original frozen readonly snapshot")
            state.installed = True
            return handle
        except BaseException as error:
            state.failed = True
            state.errors.failure.primary_error = state.errors.first_error = error
            slot = next(state.errors._cursor, None)
            if slot is None:
                state.errors.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_executor_assembly", error, None
            raise


def _registered_executor(handle, guard, ledger):
    state = _EXECUTORS.get(handle) if type(handle) is _OriginalNativePhaseRunner else None
    if (type(state) is not _Executor or state.handle is not handle
            or _GUARD_EXECUTORS.get(guard) is not state or state.guard is not guard
            or state.ledger is not ledger or not state.installed or state.failed):
        gt._deny("native phases require the exact privately assembled original fixed executor")
    return state


def _require_original_executor(handle, guard, ledger):
    state = _registered_executor(handle, guard, ledger)
    _method_pins()
    frozen = _assembly_identity(state)
    state.current_source_bytes = bootstrap._read_verified_source_file(
        Path(frozen.source_snapshot_root), _RELATIVE, max_bytes=1 << 20)
    if (state.source_bytes is None or state.current_source_bytes != state.source_bytes
            or state.source_sha256 != frozen.phase_runner_sha256.lower()
            or state.source_proof is None
            or state.source_proof.snapshot != state.proof.snapshots.source
            or state.source_proof.mount != state.proof.snapshots.source_mount):
        gt._deny("native phase executor drifted from its original privately verified source")
    return state


def _retain(tx):
    """Retain original component slots before validating any returned value."""
    owner, publisher = tx.owner, tx.publisher
    if owner is not None:
        tx.retained_active = owner.active
        tx.retained_history, tx.retained_ledger = owner.facts, owner.ledger_facts
    if publisher is not None and publisher.active is not None:
        tx.batch = publisher.active
    batch = tx.batch
    if batch is not None:
        tx.child = batch.launch
        tx.child_outcome = tx.child.outcome if tx.child is not None else None
        tx.origins = (tx.errors, tx.executor.errors, owner.failure_errors, publisher.read.failures,
                      batch.errors, batch.read.failures, batch.cleanup_read.failures)
        if tx.child is not None:
            tx.origins += (tx.child.errors,)


def _raw_error(tx, error):
    # Bounded unwrapping excludes both own and foreign report wrappers from
    # raw error slots. Reports and their complete reserved slots stay strong.
    current = error
    for _ in range(16):
        report = getattr(current, "failure_capture", None)
        if type(report) is not NativeFailureCapture or report.failure is not current:
            return current
        if tx.report_count < len(tx.reports):
            tx.reports[tx.report_count] = report
            tx.report_count += 1
        following = report.failure.primary_error
        if following is None or following is current:
            following = report.first_error
        if following is None or following is current:
            return tx.wrapper_cycle_error
        current = following
    return tx.wrapper_cycle_error


def _preserve_failure(tx, operation, error):
    """Inline reserved slots only; no error-record/format helper before cleanup."""
    raw = _raw_error(tx, error)
    if tx.primary_error is None:
        tx.primary_error = raw
    for buffer in tx.buffers:
        if buffer.failure.primary_error is None:
            buffer.failure.primary_error = tx.primary_error
        if buffer.first_error is None:
            buffer.first_error = raw
        slot = next(buffer._cursor, None)
        if slot is None:
            buffer.overflowed = True
        else:
            slot.operation, slot.error, slot.descriptor = operation, raw, None
    # Raw secondaries already exist in the original native captures. Keep
    # every capture strong and additionally copy authentic report origins into
    # this transaction's preallocated slots, without cross-wrapper recursion.
    report = getattr(error, "failure_capture", None)
    if type(report) is NativeFailureCapture and report.failure is error and report is not tx.errors:
        tx.report_origin = report
        for original in report._slots:
            if original.error is None:
                continue
            secondary = _raw_error(tx, original.error)
            if secondary is raw:
                continue
            slot = next(tx.errors._cursor, None)
            if slot is None:
                tx.errors.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = original.operation, secondary, original.descriptor
        if report.aggregation_error is not None:
            secondary = _raw_error(tx, report.aggregation_error)
            slot = next(tx.errors._cursor, None)
            if slot is None:
                tx.errors.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_original_report_aggregation", secondary, None


def _fail(tx, operation, error):
    # Poison before any retention/report/cleanup entry. Actual failed backing,
    # birth/outcome and consumed attempts are retained for external quarantine.
    tx.failed = tx.executor.failed = True
    if tx.primary_report is None:
        tx.primary_report = error
    # The first raw/report origin and its reserved slot precede every helper,
    # including retention and reporting helpers. No wrapper becomes a raw
    # error in a different capture. The original report itself remains strong.
    report = getattr(error, "failure_capture", None)
    origin = error
    if type(report) is NativeFailureCapture and report.failure is error:
        tx.report_origin = report
        origin = report.failure.primary_error
        if origin is None or origin is report.failure:
            origin = report.first_error
        if origin is None or origin is report.failure:
            origin = tx.wrapper_cycle_error
    for _ in range(16):
        nested = getattr(origin, "failure_capture", None)
        if type(nested) is not NativeFailureCapture or nested.failure is not origin:
            break
        following = nested.failure.primary_error
        if following is None or following is origin:
            following = nested.first_error
        if following is None or following is origin:
            origin = tx.wrapper_cycle_error
            break
        origin = following
    else:
        origin = tx.wrapper_cycle_error
    if tx.primary_error is None:
        tx.primary_error = origin
    for buffer in tx.buffers:
        if buffer.failure.primary_error is None:
            buffer.failure.primary_error = tx.primary_error
        if buffer.first_error is None:
            buffer.first_error = origin
        slot = next(buffer._cursor, None)
        if slot is None:
            buffer.overflowed = True
        else:
            slot.operation, slot.error, slot.descriptor = operation, origin, None
    if tx.owner is None:
        # Preservation only, including source-check failure before execution
        # acquisition. Select the original owner internally; never install one.
        original = gt._OWNERS.get(tx.executor.guard)
        if (type(original) is gt._Owner and original.binding.ledger is tx.executor.ledger
                and original.binding.controller is tx.executor.controller
                and gt._broker_guard(original.broker) is tx.executor.guard):
            tx.owner, tx.broker, tx.binding = original, original.broker, original.binding
            candidate = original.phase_publisher
            if type(candidate) is publication._Publisher and candidate.owner is original:
                tx.publisher = candidate
            tx.buffers = (tx.errors, tx.executor.errors, original.failure_errors)
            tx.origins = tx.buffers
    if tx.owner is not None:
        tx.owner.failed = True
    if tx.publisher is not None:
        tx.publisher.failed = True
    try:
        _retain(tx)
        _preserve_failure(tx, operation, error)
    except BaseException as secondary:
        # Even failure to enter the preserving helper cannot replace the first
        # saved report or permit a retry. Existing source captures remain strong.
        tx.errors.failure.primary_error = tx.primary_error
        tx.errors.aggregation_error = secondary
        slot = next(tx.errors._cursor, None)
        if slot is None:
            tx.errors.overflowed = True
        else:
            slot.operation, slot.error, slot.descriptor = "phase_transaction_capture_entry", secondary, None


def _execution_owner(tx):
    state, guard = tx.executor, tx.executor.guard
    if (state.issued.consumed is not True or guard._started is not True
            or guard._stage_b_admitted is not True or not guard._activity_open
            or guard._finished or state.active is not tx
            or state.ledger._stage_b_volume_expanded is not True):
        gt._deny("native phase requires the original started Stage B owner and current reserved activity")
    tx.binding = require_startup_binding(guard)
    tx.owner = gt._OWNERS.get(guard)
    if (type(tx.owner) is not gt._Owner or tx.owner.binding is not tx.binding
            or tx.binding is None or tx.binding.controller is not state.controller
            or tx.binding.ledger is not state.ledger or tx.binding.approval is not state.assembly.approval
            or not tx.owner.installed or tx.owner.failed or tx.owner.active is not None
            or state.ledger._active_gt_release is not None):
        gt._deny("native phase has no healthy actually installed original GT owner")
    tx.broker, tx.publisher = tx.owner.broker, tx.owner.phase_publisher
    tx.buffers = (tx.errors, state.errors, tx.owner.failure_errors)
    tx.origins = tx.buffers
    if (tx.owner.phase_executor is not None and tx.owner.phase_executor is not state
            or state.owner is not None and state.owner is not tx.owner
            or tx.owner.phase_transactions != state.transactions[:-1]):
        gt._deny("native phase owner and original transaction history are discontinuous")
    state.owner = tx.owner
    tx.owner.phase_executor = state
    tx.owner.phase_transactions = state.transactions
    if (type(tx.broker) is not gt.LinuxNativeGTBroker or gt._broker_guard(tx.broker) is not guard
            or type(tx.publisher) is not publication._Publisher
            or tx.publisher.owner is not tx.owner or tx.publisher.binding is not tx.binding
            or tx.publisher.active is not None
            or publication._PUBLISHERS.get(tx.publisher.handle) is not tx.publisher):
        gt._deny("native phase lacks the exact privately installed original broker/publisher")
    tx.origins += (tx.publisher.read.failures,)
    tx.initial_ledger = tx.owner.ledger_facts
    # This unchanged real installation gate precedes grant as well as the
    # launcher's helper load. No policy/hash/callback can make it successful.
    assembly = LinuxProductionController._state(state.controller)
    if assembly is not state.assembly:
        gt._deny("native phase replaced its original controller assembly")
    tx.policy_result = LinuxProductionController._policy(state.controller, assembly)
    frozen, policy, _ = tx.policy_result
    _INSTALL_GATE(assembly.ports, policy, frozen, assembly.unit_observation)
    gt._live(guard, tx.owner)
    if publication._original(tx.publisher.handle) is not tx.publisher:
        gt._deny("native phase publisher is not its original current owner")
    tx.budget_result = publication._budget(tx.publisher)
    tx.stop_ns, tx.cleanup_ns = tx.budget_result
    tx.clock = publication._clock(tx.publisher)
    if len(tx.clock) != 3 or tx.clock[2] is None:
        gt._deny("native phase has no original already armed current activity clock")
    tx.journal = gt._journal(guard, tx.owner)
    gt._check_ledger(tx.owner, tx.journal.records)


def _science(tx):
    scope, registered = tx.scope, tx.registered_view
    if type(scope) is not TruthReadScope or type(registered) is not RegisteredFile:
        gt._deny("native phase requires exact scope and descriptive GT registration types")
    # The existing codec rejects callable/subclass scalar/container fields
    # before comparing descriptive caller metadata with original private facts.
    budget = [0]
    wire._walk(RegisteredFile, registered, True, tx.stop_ns, budget)
    for name, rule in wire._REQUEST:
        if name in {"expected_view_sha256", "gt_commitment_key"}:
            continue
        wire._walk(rule, tx.payload[name], True, tx.stop_ns, budget)
    expected = {StudyStage.TRAIN_LABELS: "training_labels", StudyStage.INNER_EVALUATION: "inner_evaluator",
                StudyStage.OUTER_EVALUATION: "outer_evaluator"}.get(scope.stage)
    if tx.operation != expected:
        gt._deny("native scientific operation differs from its original GT scope")
    tx.owner.graph.validate_scope(scope)
    role = scope.role_ids[0] if scope.stage is StudyStage.TRAIN_LABELS else scope.outer_id
    matches = tuple(view for view in tx.owner.views
                    if view.mapping.role_id == role and view.mapping.phase == scope.stage.value)
    if len(matches) != 1:
        gt._deny("native phase has no unique original protected GT view")
    tx.view = matches[0]
    mapping = tx.view.mapping
    if (registered.path != mapping.logical_path or registered.sha256.lower() != mapping.sha256.lower()
            or registered.role_id != mapping.role_id or registered.fields != stage_gt_fields(scope.stage)
            or registered.scope_sha256 != tx.view.scope_sha256
            or tx.view.scope_sha256 != scope.participant_scope_attestation
            or type(registered.projection_attestation) is not str or not registered.projection_attestation.strip()
            or tx.view.identity.source_path != gt._source(mapping)):
        gt._deny("descriptive GT registration differs from original mapping/scope/source facts")
    outer = scope.stage is StudyStage.OUTER_EVALUATION
    if (outer and (type(tx.control_final_matches) is not RegisteredFile or tx.reference_candidates is None
            or tx.control_metrics_sha256 != contracts.require_frozen_admission().a2_004_final_metrics_sha256.lower())
            or not outer and any(value is not None for value in (
                tx.control_final_matches, tx.control_metrics_sha256, tx.reference_candidates))):
        gt._deny("native phase historical science arguments differ from the fixed outer operation")
    # These hashes only describe the retained science; they install no OS right.
    tx.scope_bytes = _canonical(asdict(scope))
    tx.scope_sha256 = hashlib.sha256(tx.scope_bytes).hexdigest()
    tx.payload_sha256 = hashlib.sha256(_canonical({
        "candidates": [asdict(item) for item in tx.candidates],
        "reference_candidates": None if tx.reference_candidates is None else [asdict(item) for item in tx.reference_candidates],
        "control_final_matches": None if tx.control_final_matches is None else asdict(tx.control_final_matches),
        "control_metrics_sha256": tx.control_metrics_sha256,
        "predictions": [asdict(item) for item in tx.predictions],
        "participant_ids": list(tx.participant_ids),
    })).hexdigest()


def _fact(tx, event, *, digest=None):
    facts = tx.owner.ledger_facts[len(tx.initial_ledger):]
    found = tuple(fact for fact in facts if fact.event == event
                  and (digest is None or fact.sha256 == digest))
    if len(found) != 1:
        gt._deny("native phase lacks its unique actual durable transaction event")
    return found[0]


def _published(tx):
    batch, grant = tx.batch, tx.grant
    if (type(grant) is not gt._Grant or tx.owner.active is not grant
            or grant.view is not tx.view or grant.scope is not tx.scope or grant.scope_bytes != tx.scope_bytes
            or grant.receipt is not tx.grant_receipt or grant.release != tx.release
            or type(batch) is not publication._Batch or batch.grant is not grant
            or batch is not tx.publisher.active or batch.scope_bytes != tx.scope_bytes
            or batch.release != tx.release or not batch.published or batch.closed or batch.failed
            or (batch.stop_ns, batch.cleanup_ns) != (tx.stop_ns, tx.cleanup_ns)
            or any(now is not saved for now, saved in zip(batch.clock, tx.clock))
            or len(batch.copies) != (2 if tx.scope.stage is StudyStage.OUTER_EVALUATION else 1)):
        gt._deny("native transaction lost its actual grant/publication/armed-clock continuity")
    source = batch.copies[0].source
    if (type(source) is not publication._Source or source.mapping is not tx.view.mapping
            or source.identity is not tx.view.identity or source.frame != tx.view.frame
            or source.mount_id != grant.mount_id or source.path != tx.view.mapping.bind_path):
        gt._deny("published native GT copy differs from original protected source facts")
    if tx.scope.stage is StudyStage.OUTER_EVALUATION:
        tx.historical_source = batch.copies[1].source
        source, original = tx.historical_source, tx.publication_result
        caller = tx.control_final_matches
        if (type(source) is not publication._Source or type(original) is not RegisteredFile
                or source.registered is not original or caller != original
                or source.mapping.logical_path != original.path
                or source.mapping.sha256.lower() != original.sha256.lower()
                or source.mapping.role_id != tx.scope.outer_id
                or source.mapping.phase != OUTER_CONTROL_FINAL_MATCHES_PHASE
                or original.fields != CONTROL_FINAL_MATCH_FIELDS
                or original.role_id != tx.scope.outer_id
                or original.scope_sha256 != projection_scope_sha256("a2_004_final_matches", tx.scope.outer_id,
                    tx.scope.participants, CONTROL_FINAL_MATCH_FIELDS, role_graph_sha256=tx.scope.role_graph_sha256)
                or source.path != gt._source(source.mapping)
                or source.identity.source_path != source.path
                or (source.identity.device, source.identity.inode, source.identity.mode,
                    source.identity.uid, source.identity.nlink)
                    != (source.frame[0], source.frame[1], source.frame[2], source.frame[3], source.frame[5])
                or type(source.mount_id) is not int or source.mount_id <= 0):
            gt._deny("historical payload differs from original row/mapping/hash/scope/actual source")
    elif tx.publication_result is not None:
        gt._deny("nonouter native publication returned a historical input")


def _healthy(tx):
    if (tx.failed or tx.executor.failed or tx.owner.failed or tx.publisher.failed
            or any(buffer.first_error is not None or buffer.failure.primary_error is not None
                   or buffer.aggregation_error is not None or buffer.overflowed for buffer in tx.origins)):
        gt._deny("native phase transaction retains an original failure or incomplete error history")


def _closed_transaction(tx):
    _healthy(tx)
    owner, batch, child = tx.owner, tx.batch, tx.child
    if (type(owner) is not gt._Owner or owner.phase_executor is not tx.executor
            or owner.binding is not tx.binding or tx.executor.owner is not owner
            or gt._OWNERS.get(tx.executor.guard) is not owner
            or _TRANSACTIONS.get(tx.handle) is not tx
            or type(batch) is not publication._Batch or not any(item is batch for item in tx.publisher.batches)
            or batch.grant is not tx.grant or batch.launch is not child
            or type(child) is not children._Owned or child.outcome_handle is not tx.outcome_handle
            or child.outcome is not tx.outcome or child.result is not tx.result
            or type(tx.outcome) is not children._PhaseOutcome or tx.outcome.result is not tx.result
            or not tx.grant_attempted or not tx.publish_attempted or not tx.launch_attempted
            or not tx.consume_attempted or not tx.close_attempted or not tx.close_returned
            or not tx.revoke_attempted or owner.active is not None
            or tx.publisher.active is not None or tx.executor.ledger._active_gt_release is not None
            or publication._PUBLISHERS.get(tx.publisher.handle) is not tx.publisher
            or owner.phase_publisher is not tx.publisher or tx.publisher.owner is not owner):
        gt._deny("native phase result has no original completed grant/child/unpublication/revoke transaction")
    publication._require_closed(owner)
    children._require_retired_phase_batch(tx.publisher, batch)
    events = ((tx.release_fact, "gt_phase_released"), (tx.grant_fact, "gt_broker_grant_published"),
              (tx.published_fact, "gt_broker_phase_inputs_published"),
              (tx.unpublished_fact, "gt_broker_phase_inputs_unpublished"),
              (tx.revoke_confirmed_fact, "gt_broker_revoke_confirmed"),
              (tx.revoke_fact, "gt_phase_view_revoked"))
    if any(type(fact) is not gt._LedgerFact or fact.event != event
           or not any(original is fact for original in owner.ledger_facts) for fact, event in events):
        gt._deny("native phase result lost its original actual durable release/publication/revoke facts")
    release, grant, published, unpublished, confirmed, revoked = (json.loads(fact.payload) for fact, _ in events)
    if (tx.release_fact.sha256 != tx.release or release.get("scope_sha256") != tx.scope_sha256
            or release.get("stage") != tx.scope.stage.value or release.get("outer_id") != tx.scope.outer_id
            or release.get("role_ids") != list(tx.scope.role_ids)
            or grant.get("mount") != asdict(tx.grant_receipt)
            or published.get("release_sha256") != tx.release or unpublished.get("release_sha256") != tx.release
            or confirmed.get("release_sha256") != tx.release or confirmed.get("mount_id") != tx.grant.mount_id
            or confirmed.get("alias") != tx.view.mapping.bind_path
            or tx.revoke_result != tx.revoke_confirmed_fact.sha256
            or tx.revoke_event != tx.revoke_fact.sha256
            or revoked.get("release_event_sha256") != tx.release
            or revoked.get("scope_sha256") != tx.scope_sha256
            or revoked.get("os_revoke_receipt_sha256") != tx.revoke_result
            or tuple(fact.seq for fact, _ in events) != tuple(sorted(fact.seq for fact, _ in events))
            or len({fact.seq for fact, _ in events}) != len(events)):
        gt._deny("native phase result differs from original durable OS/release/revoke continuity")


def _current_transaction_clock(tx):
    # Retrieval/acceptance cannot borrow a later activity, retire the original
    # clock or turn data timestamps into an armed kernel deadline. Terminal
    # history checks intentionally do not use this live-clock-only fence.
    if publication._original(tx.publisher.handle) is not tx.publisher:
        gt._deny("native result lost its original privately installed publisher")
    tx.current_budget_result = publication._budget(tx.publisher)
    tx.current_clock = publication._clock(tx.publisher)
    if (tx.current_budget_result != (tx.stop_ns, tx.cleanup_ns) or len(tx.current_clock) != 3
            or len(tx.clock) != 3
            or any(now is not original for now, original in zip(tx.current_clock, tx.clock))):
        gt._deny("native phase result cannot replace its original absolute armed activity clock")


def _execute_original_phase(handle, *, scope, registered_view, operation, candidates,
                            reference_candidates, control_final_matches, control_metrics_sha256,
                            predictions, participant_ids, ledger, guard):
    """One original transaction; no caller release, clock, callback or exit flag."""
    with gt._LOCK:
        state = _registered_executor(handle, guard, ledger)
        if state.active is not None or len(state.transactions) >= _MAX_TRANSACTIONS:
            gt._deny("native executor retains an unfinished transaction or exhausted issuance history")
        tx = _Transaction(state, _TransactionHandle(), scope, registered_view, operation, candidates,
                          reference_candidates, control_final_matches, control_metrics_sha256,
                          predictions, participant_ids)
        tx.buffers = tx.origins = (tx.errors, state.errors)
        tx.payload = dict(scope=scope, operation=operation, expected_view_sha256=None,
                          gt_commitment_key=None, candidates=candidates, reference_candidates=reference_candidates,
                          control_final_matches=control_final_matches, control_metrics_sha256=control_metrics_sha256,
                          predictions=predictions, participant_ids=participant_ids)
        state.transactions += (tx,)
        state.active = tx
        _TRANSACTIONS[tx.handle] = tx
        try:
            tx.current_executor = _require_original_executor(handle, guard, ledger)
            _execution_owner(tx)
            _science(tx)
            tx.grant_attempted = True
            tx.grant_receipt = _GRANT(tx.broker, tx.scope)
            tx.grant = tx.owner.active
            tx.release = tx.grant.release if type(tx.grant) is gt._Grant else None
            _retain(tx)
            if (type(tx.grant) is not gt._Grant or tx.grant.receipt is not tx.grant_receipt
                    or tx.grant.view is not tx.view or tx.grant.scope is not scope
                    or tx.grant.scope_bytes != tx.scope_bytes):
                gt._deny("native grant return is not the original privately active issuance")
            tx.release_fact = _fact(tx, "gt_phase_released", digest=tx.release)
            tx.grant_fact = _fact(tx, "gt_broker_grant_published")
            tx.publish_attempted = True
            tx.publication_result = _PUBLISH(tx.publisher.handle, tx.scope,
                include_control_final_matches=scope.stage is StudyStage.OUTER_EVALUATION)
            tx.batch = tx.publisher.active
            _retain(tx)
            _published(tx)
            tx.published_fact = _fact(tx, "gt_broker_phase_inputs_published")
            tx.commitment_key = publication._current_phase_commitment_key(guard, tx.scope, tx.release)
            if (type(tx.commitment_key) is not bytes or len(tx.commitment_key) != 32
                    or tx.commitment_key is not tx.owner.commitment_key.raw):
                gt._deny("native phase has no exact original system-issued science key")
            tx.payload["expected_view_sha256"] = tx.view.mapping.sha256.lower()
            tx.payload["gt_commitment_key"] = tx.commitment_key
            # Preserve the original publisher row, including its logical path.
            # The unchanged child opens the independent fixed /inputs copy.
            tx.payload["control_final_matches"] = tx.publication_result
            wire._mapping(tx.payload, wire._REQUEST)
            tx.launch_attempted = True
            tx.outcome_handle = _LAUNCH(guard, payload=tx.payload, release_event_sha256=tx.release,
                stop_deadline_ns=tx.batch.stop_ns, cleanup_deadline_ns=tx.batch.cleanup_ns)
            tx.child = tx.batch.launch
            tx.child_outcome = tx.child.outcome if tx.child is not None else None
            _retain(tx)
            if (type(tx.child) is not children._Owned or tx.child.outcome_handle is not tx.outcome_handle
                    or children._OUTCOMES.get(tx.outcome_handle) is not tx.child):
                gt._deny("native child handle is not its original once-only registered outcome")
            tx.consume_attempted = True
            tx.outcome = _CONSUME(guard, tx.outcome_handle)
            tx.result = tx.outcome.result if type(tx.outcome) is children._PhaseOutcome else None
            _retain(tx)
            if tx.outcome is not tx.child.outcome or tx.result is not tx.child.result:
                gt._deny("native phase outcome/result was replaced after original consumption")
            _healthy(tx)
            # close() includes the original children/reference fence and actual
            # unpublication. It is consumed once and cannot be retried as success.
            tx.close_attempted = True
            tx.close_result = _CLOSE(tx.publisher.handle)
            tx.close_returned = True
            _retain(tx)
            tx.unpublished_fact = _fact(tx, "gt_broker_phase_inputs_unpublished")
            publication._require_closed(tx.owner)
            tx.revoke_attempted = True
            tx.revoke_result = _REVOKE(tx.broker)
            _retain(tx)
            tx.revoke_confirmed_fact = _fact(tx, "gt_broker_revoke_confirmed", digest=tx.revoke_result)
            tx.revoke_fact = _fact(tx, "gt_phase_view_revoked")
            tx.revoke_event = tx.revoke_fact.sha256
            _closed_transaction(tx)
            _current_transaction_clock(tx)
            tx.journal = gt._journal(guard, tx.owner)
            gt._check_ledger(tx.owner, tx.journal.records)
            tx.result_sha256 = hashlib.sha256(_canonical(asdict(tx.result))).hexdigest()
            tx.receipt = _RECEIPT(tx.operation, tx.scope_sha256, tx.payload_sha256, tx.result_sha256,
                tx.release, tx.revoke_result, True, True, tx.result)
            tx.complete = True
            return tx.handle
        except BaseException as error:
            # Save the original error inline even if the failure-preserving
            # helper cannot be entered. No cleanup/report entry precedes it.
            tx.primary_report = error
            tx.failed = state.failed = True
            report = getattr(error, "failure_capture", None)
            raw = error
            for _ in range(16):
                capture = getattr(raw, "failure_capture", None)
                if type(capture) is not NativeFailureCapture or capture.failure is not raw:
                    break
                tx.report_origin = capture
                following = capture.failure.primary_error
                if following is None or following is raw:
                    following = capture.first_error
                if following is None or following is raw:
                    raw = tx.wrapper_cycle_error
                    break
                raw = following
            else:
                raw = tx.wrapper_cycle_error
            tx.primary_error = tx.errors.failure.primary_error = raw
            tx.errors.first_error = raw
            slot = next(tx.errors._cursor, None)
            if slot is None:
                tx.errors.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = "phase_transaction_primary", raw, None
            if tx.owner is not None:
                tx.owner.failed = True
            if tx.publisher is not None:
                tx.publisher.failed = True
            try:
                _fail(tx, "phase_transaction_primary", error)
            except BaseException as secondary:
                tx.errors.aggregation_error = secondary
                slot = next(tx.errors._cursor, None)
                if slot is None:
                    tx.errors.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_failure_preservation_entry", secondary, None
            # Failed publisher close is not normal closure; failed broker state
            # cannot perform normal revoke. Do not relax a fence or repeat an
            # already consumed FD/birth/outcome/removal/revoke attempt.
            if tx.publisher is not None and tx.batch is not None and not tx.close_attempted:
                tx.close_attempted = True
                try:
                    tx.close_result = _CLOSE(tx.publisher.handle)
                    tx.close_returned = True
                except BaseException as secondary:
                    report = getattr(secondary, "failure_capture", None)
                    raw = secondary
                    for _ in range(16):
                        capture = getattr(raw, "failure_capture", None)
                        if type(capture) is not NativeFailureCapture or capture.failure is not raw:
                            break
                        tx.report_origin = capture
                        following = capture.failure.primary_error
                        if following is None or following is raw:
                            following = capture.first_error
                        if following is None or following is raw:
                            raw = tx.wrapper_cycle_error
                            break
                        raw = following
                    else:
                        raw = tx.wrapper_cycle_error
                    slot = next(tx.errors._cursor, None)
                    if slot is None:
                        tx.errors.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_transaction_failure_unpublication", raw, None
                    try:
                        _fail(tx, "phase_transaction_failure_unpublication", secondary)
                    except BaseException as entry_error:
                        tx.errors.aggregation_error = entry_error
                        slot = next(tx.errors._cursor, None)
                        if slot is None:
                            tx.errors.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = "phase_secondary_preservation_entry", entry_error, None
            try:
                tx.errors.raise_failure(tx.primary_error)
            except BaseException as report_error:
                if report_error is tx.errors.failure:
                    raise
                # Separate preallocated holders keep both actual reports;
                # neither overwrites an earlier original/secondary report.
                tx.report_entry_report = report_error
                raw_report = report_error
                for _ in range(16):
                    capture = getattr(raw_report, "failure_capture", None)
                    if type(capture) is not NativeFailureCapture or capture.failure is not raw_report:
                        break
                    tx.report_origin = capture
                    following = capture.failure.primary_error
                    if following is None or following is raw_report:
                        following = capture.first_error
                    if following is None or following is raw_report:
                        raw_report = tx.wrapper_cycle_error
                        break
                    raw_report = following
                else:
                    raw_report = tx.wrapper_cycle_error
                for buffer in tx.buffers:
                    buffer.aggregation_error = raw_report
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = "phase_transaction_report_entry", raw_report, None
                try:
                    _fail(tx, "phase_transaction_report_entry", report_error)
                except BaseException as entry_error:
                    tx.report_entry_preservation_report = entry_error
                    raw_entry = entry_error
                    for _ in range(16):
                        capture = getattr(raw_entry, "failure_capture", None)
                        if type(capture) is not NativeFailureCapture or capture.failure is not raw_entry:
                            break
                        tx.report_origin = capture
                        following = capture.failure.primary_error
                        if following is None or following is raw_entry:
                            following = capture.first_error
                        if following is None or following is raw_entry:
                            raw_entry = tx.wrapper_cycle_error
                            break
                        raw_entry = following
                    else:
                        raw_entry = tx.wrapper_cycle_error
                    for buffer in tx.buffers:
                        buffer.aggregation_error = raw_entry
                        slot = next(buffer._cursor, None)
                        if slot is None:
                            buffer.overflowed = True
                        else:
                            slot.operation, slot.error, slot.descriptor = (
                                "phase_transaction_report_preservation_entry", raw_entry, None)
                tx.errors.failure.secondary_errors = tx.errors._slots
                raise tx.errors.failure from tx.primary_error


def _transaction(handle, executor, guard, ledger):
    state = _registered_executor(executor, guard, ledger)
    tx = _TRANSACTIONS.get(handle) if type(handle) is _TransactionHandle else None
    if (type(tx) is not _Transaction or tx.handle is not handle or tx.executor is not state
            or state.active is not tx or not any(original is tx for original in state.transactions)
            or tx.owner is None or not any(original is tx for original in tx.owner.phase_transactions)):
        gt._deny("native phase result has no original privately registered transaction")
    return tx


def _take_original_phase_result(executor, handle, *, scope, operation, guard, ledger):
    with gt._LOCK:
        tx = _transaction(handle, executor, guard, ledger)
        if tx.take_attempted or not tx.complete or scope is not tx.scope or operation != tx.operation:
            gt._deny("native phase result retrieval is exact, original and once-only")
        tx.take_attempted = True
        try:
            tx.current_executor = _require_original_executor(executor, guard, ledger)
            _closed_transaction(tx)
            _current_transaction_clock(tx)
            gt._live(guard, tx.owner)
            tx.journal = gt._journal(guard, tx.owner)
            gt._check_ledger(tx.owner, tx.journal.records)
            if (type(tx.receipt) is not _RECEIPT or tx.receipt.result is not tx.outcome.result
                    or tx.receipt.authorization_event_sha256 != tx.release
                    or tx.receipt.os_revoke_receipt_sha256 != tx.revoke_result):
                gt._deny("descriptive phase receipt differs from the original actual transaction")
            tx.take_result = (tx.receipt, tx.release, tx.revoke_event)
            tx.retrieved = True
            return tx.take_result
        except BaseException as error:
            # Anchor original report/raw slots before the failure helper entry.
            if tx.primary_report is None:
                tx.primary_report = error
            tx.failed = tx.executor.failed = True
            raw = error
            for _ in range(16):
                capture = getattr(raw, "failure_capture", None)
                if type(capture) is not NativeFailureCapture or capture.failure is not raw:
                    break
                tx.report_origin = capture
                following = capture.failure.primary_error
                if following is None or following is raw:
                    following = capture.first_error
                if following is None or following is raw:
                    raw = tx.wrapper_cycle_error
                    break
                raw = following
            else:
                raw = tx.wrapper_cycle_error
            if tx.primary_error is None:
                tx.primary_error = raw
            for buffer in tx.buffers:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = tx.primary_error
                if buffer.first_error is None:
                    buffer.first_error = raw
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_transaction_result_retrieval", raw, None
            if tx.owner is not None:
                tx.owner.failed = True
            if tx.publisher is not None:
                tx.publisher.failed = True
            try:
                _fail(tx, "phase_transaction_result_retrieval", error)
            except BaseException as secondary:
                # Keep helper failure secondary; never replace the anchored primary.
                tx.secondary_report = secondary
                raw_secondary = secondary
                for _ in range(16):
                    capture = getattr(raw_secondary, "failure_capture", None)
                    if type(capture) is not NativeFailureCapture or capture.failure is not raw_secondary:
                        break
                    tx.report_origin = capture
                    following = capture.failure.primary_error
                    if following is None or following is raw_secondary:
                        following = capture.first_error
                    if following is None or following is raw_secondary:
                        raw_secondary = tx.wrapper_cycle_error
                        break
                    raw_secondary = following
                else:
                    raw_secondary = tx.wrapper_cycle_error
                for buffer in tx.buffers:
                    buffer.aggregation_error = raw_secondary
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = (
                            "phase_transaction_result_retrieval_preservation_entry", raw_secondary, None)
                tx.errors.failure.secondary_errors = tx.errors._slots
            raise


def _accept_original_phase_result(executor, handle, receipt, *, guard, ledger):
    with gt._LOCK:
        tx = _transaction(handle, executor, guard, ledger)
        if (tx.accept_attempted or not tx.retrieved or receipt is not tx.receipt
                or receipt.result is not tx.outcome.result):
            gt._deny("native acceptance requires its original retrieved transaction and exact retained result")
        tx.accept_attempted = True
        try:
            tx.current_executor = _require_original_executor(executor, guard, ledger)
            _closed_transaction(tx)
            _current_transaction_clock(tx)
            gt._live(guard, tx.owner)
            tx.journal = gt._journal(guard, tx.owner)
            gt._check_ledger(tx.owner, tx.journal.records)
            tx.acceptance_body = dict(stage=tx.scope.stage.value, outer_id=tx.scope.outer_id,
                role_ids=list(tx.scope.role_ids), operation=tx.operation,
                authorization_event_sha256=tx.release, revocation_event_sha256=tx.revoke_event,
                os_revoke_receipt_sha256=tx.revoke_result, result_sha256=tx.result_sha256)
            tx.acceptance_result = _APPEND(ledger, "gt_phase_result_accepted", tx.acceptance_body)
            tx.retained_ledger = tx.owner.ledger_facts
            tx.acceptance_tail_result = gt._remember_tail(guard, tx.owner, "gt_phase_result_accepted")
            tx.retained_ledger = tx.owner.ledger_facts
            tx.accepted_fact = tx.retained_ledger[-1]
            if (tx.acceptance_result != tx.acceptance_tail_result
                    or tx.accepted_fact.sha256 != tx.acceptance_result
                    or tx.accepted_fact.payload != _canonical(tx.acceptance_body)
                    or tx.accepted_fact.seq <= tx.revoke_fact.seq):
                gt._deny("native result acceptance is not the original actual durable owner tail")
            tx.accepted = True
            tx.executor.active = None
            return tx.acceptance_result
        except BaseException as error:
            # Anchor original report/raw slots before the failure helper entry.
            if tx.primary_report is None:
                tx.primary_report = error
            tx.failed = tx.executor.failed = True
            raw = error
            for _ in range(16):
                capture = getattr(raw, "failure_capture", None)
                if type(capture) is not NativeFailureCapture or capture.failure is not raw:
                    break
                tx.report_origin = capture
                following = capture.failure.primary_error
                if following is None or following is raw:
                    following = capture.first_error
                if following is None or following is raw:
                    raw = tx.wrapper_cycle_error
                    break
                raw = following
            else:
                raw = tx.wrapper_cycle_error
            if tx.primary_error is None:
                tx.primary_error = raw
            for buffer in tx.buffers:
                if buffer.failure.primary_error is None:
                    buffer.failure.primary_error = tx.primary_error
                if buffer.first_error is None:
                    buffer.first_error = raw
                slot = next(buffer._cursor, None)
                if slot is None:
                    buffer.overflowed = True
                else:
                    slot.operation, slot.error, slot.descriptor = "phase_transaction_result_acceptance", raw, None
            if tx.owner is not None:
                tx.owner.failed = True
            if tx.publisher is not None:
                tx.publisher.failed = True
            try:
                _fail(tx, "phase_transaction_result_acceptance", error)
            except BaseException as secondary:
                # Keep helper failure secondary; never replace the anchored primary.
                tx.secondary_report = secondary
                raw_secondary = secondary
                for _ in range(16):
                    capture = getattr(raw_secondary, "failure_capture", None)
                    if type(capture) is not NativeFailureCapture or capture.failure is not raw_secondary:
                        break
                    tx.report_origin = capture
                    following = capture.failure.primary_error
                    if following is None or following is raw_secondary:
                        following = capture.first_error
                    if following is None or following is raw_secondary:
                        raw_secondary = tx.wrapper_cycle_error
                        break
                    raw_secondary = following
                else:
                    raw_secondary = tx.wrapper_cycle_error
                for buffer in tx.buffers:
                    buffer.aggregation_error = raw_secondary
                    slot = next(buffer._cursor, None)
                    if slot is None:
                        buffer.overflowed = True
                    else:
                        slot.operation, slot.error, slot.descriptor = (
                            "phase_transaction_result_acceptance_preservation_entry", raw_secondary, None)
                tx.errors.failure.secondary_errors = tx.errors._slots
            raise


def _reject_original_phase_result(executor, handle, error, *, guard, ledger):
    # Only preservation, never an alternate success/cleanup authority path.
    tx = _TRANSACTIONS.get(handle) if type(handle) is _TransactionHandle else None
    state = _EXECUTORS.get(executor) if type(executor) is _OriginalNativePhaseRunner else None
    if (type(tx) is not _Transaction or tx.executor is not state or state.guard is not guard
            or state.ledger is not ledger or tx.handle is not handle):
        gt._deny("native result rejection lost its original retained transaction")
    # Anchor original report/raw slots before the failure helper entry.
    if tx.primary_report is None:
        tx.primary_report = error
    tx.failed = tx.executor.failed = True
    raw = error
    for _ in range(16):
        capture = getattr(raw, "failure_capture", None)
        if type(capture) is not NativeFailureCapture or capture.failure is not raw:
            break
        tx.report_origin = capture
        following = capture.failure.primary_error
        if following is None or following is raw:
            following = capture.first_error
        if following is None or following is raw:
            raw = tx.wrapper_cycle_error
            break
        raw = following
    else:
        raw = tx.wrapper_cycle_error
    if tx.primary_error is None:
        tx.primary_error = raw
    for buffer in tx.buffers:
        if buffer.failure.primary_error is None:
            buffer.failure.primary_error = tx.primary_error
        if buffer.first_error is None:
            buffer.first_error = raw
        slot = next(buffer._cursor, None)
        if slot is None:
            buffer.overflowed = True
        else:
            slot.operation, slot.error, slot.descriptor = "phase_transaction_scientific_acceptance", raw, None
    if tx.owner is not None:
        tx.owner.failed = True
    if tx.publisher is not None:
        tx.publisher.failed = True
    try:
        _fail(tx, "phase_transaction_scientific_acceptance", error)
    except BaseException as secondary:
        # Keep helper failure secondary; never replace the anchored primary.
        tx.secondary_report = secondary
        raw_secondary = secondary
        for _ in range(16):
            capture = getattr(raw_secondary, "failure_capture", None)
            if type(capture) is not NativeFailureCapture or capture.failure is not raw_secondary:
                break
            tx.report_origin = capture
            following = capture.failure.primary_error
            if following is None or following is raw_secondary:
                following = capture.first_error
            if following is None or following is raw_secondary:
                raw_secondary = tx.wrapper_cycle_error
                break
            raw_secondary = following
        else:
            raw_secondary = tx.wrapper_cycle_error
        for buffer in tx.buffers:
            buffer.aggregation_error = raw_secondary
            slot = next(buffer._cursor, None)
            if slot is None:
                buffer.overflowed = True
            else:
                slot.operation, slot.error, slot.descriptor = (
                    "phase_transaction_scientific_acceptance_preservation_entry", raw_secondary, None)
        tx.errors.failure.secondary_errors = tx.errors._slots


def _transaction_snapshot(owner):
    """Process-private continuity, including raw/error/attempt identities."""
    state = owner.phase_executor
    if state is None:
        return (None, owner.phase_transactions)
    return (state, state.handle, state.proof, state.issued, state.guard, state.controller, state.assembly,
        state.ledger, state.pid, state.thread, state.source_proof, state.source_manifest,
        state.source_bytes, state.current_source_bytes,
        state.source_sha256, state.installed, state.failed, state.owner, state.active,
        state.transactions, owner.phase_transactions,
        tuple((tx, tx.handle, tx.scope, tx.registered_view, tx.operation, tx.candidates,
            tx.reference_candidates, tx.control_final_matches, tx.control_metrics_sha256,
            tx.predictions, tx.participant_ids, tx.owner, tx.publisher, tx.broker, tx.binding,
            tx.current_executor,
            tx.view, tx.initial_ledger, tx.retained_history, tx.retained_ledger, tx.retained_active,
            tx.policy_result, tx.budget_result, tx.journal, tx.current_budget_result, tx.current_clock,
            tx.stop_ns, tx.cleanup_ns, tx.clock, tx.scope_bytes, tx.scope_sha256,
            _payload_snapshot(tx),
            tx.payload_sha256, tx.grant_attempted, tx.grant_receipt, tx.grant, tx.release,
            tx.release_fact, tx.grant_fact, tx.publish_attempted, tx.publication_result,
            tx.batch, tx.published_fact, tx.historical_source, tx.commitment_key,
            tx.launch_attempted, tx.outcome_handle, tx.child, tx.child_outcome,
            tx.consume_attempted, tx.outcome, tx.result, tx.close_attempted, tx.close_result,
            tx.close_returned, tx.unpublished_fact, tx.revoke_attempted, tx.revoke_result,
            tx.revoke_confirmed_fact, tx.revoke_fact, tx.revoke_event, tx.result_sha256,
            tx.receipt, tx.complete, tx.take_attempted, tx.take_result, tx.retrieved,
            tx.accept_attempted, _canonical(tx.acceptance_body), tx.acceptance_result,
            tx.acceptance_tail_result, tx.accepted_fact, tx.accepted, tx.failed,
            tx.primary_error, tx.primary_report, tx.secondary_report,
            tx.report_entry_report, tx.report_entry_preservation_report, tx.report_origin, tuple(tx.reports),
            tx.report_count, tx.buffers, tx.origins,
            tuple((buffer, buffer.failure, buffer.failure.primary_error, buffer.first_error,
                buffer.aggregation_error, buffer.overflowed,
                tuple((slot.operation, slot.error, slot.descriptor) for slot in buffer._slots))
                  for buffer in tx.origins)) for tx in owner.phase_transactions))


def _payload_snapshot(tx):
    payload = tx.payload
    if payload is None:
        return None
    return (payload, payload["scope"], _canonical(asdict(payload["scope"])),
        payload["operation"], payload["expected_view_sha256"], payload["gt_commitment_key"],
        _canonical([asdict(row) for row in payload["candidates"]]),
        None if payload["reference_candidates"] is None else _canonical([asdict(row) for row in payload["reference_candidates"]]),
        payload["control_final_matches"], None if payload["control_final_matches"] is None
            else _canonical(asdict(payload["control_final_matches"])),
        payload["control_metrics_sha256"], _canonical([asdict(row) for row in payload["predictions"]]),
        _canonical(list(payload["participant_ids"])))


def _require_transaction_history(owner):
    """Only at a genuinely GT-free boundary, never inside broker.revoke()."""
    state, transactions = owner.phase_executor, owner.phase_transactions
    publisher = owner.phase_publisher
    if state is None:
        if (transactions or publisher is not None and publisher.batches
                or any(fact.event in gt._LEDGER_EVENTS for fact in owner.ledger_facts)):
            gt._deny("original GT phase history has no fixed native transaction executor")
        return  # Stage A/no-GT early closure has no executor transaction.
    if (type(state) is not _Executor or _EXECUTORS.get(state.handle) is not state
            or _GUARD_EXECUTORS.get(state.guard) is not state or gt._OWNERS.get(state.guard) is not owner
            or state.owner is not owner or state.failed or not state.installed or state.active is not None
            or state.ledger is not owner.binding.ledger or state.controller is not owner.binding.controller
            or state.pid != owner.binding.pid or state.thread is not owner.binding.thread
            or transactions is not state.transactions or state.source_proof is None
            or state.source_sha256 != state.proof.frozen_admission.phase_runner_sha256.lower()
            or owner.active is not None):
        gt._deny("original GT-free history retains an absent, active or failed native executor transaction")
    if publisher is None or tuple(tx.batch for tx in transactions) != publisher.batches:
        gt._deny("original phase batches and fixed transaction issuances are incomplete")
    # Every actual GT release, revoke and result acceptance belongs to one
    # original transaction; extra legacy/direct events cannot disappear.
    for event, attribute in (("gt_phase_released", "release_fact"),
                             ("gt_phase_view_revoked", "revoke_fact"),
                             ("gt_phase_result_accepted", "accepted_fact")):
        observed = tuple(fact for fact in owner.ledger_facts if fact.event == event)
        expected = tuple(getattr(tx, attribute) for tx in transactions)
        if len(observed) != len(expected) or any(fact is not original for fact, original in zip(observed, expected)):
            gt._deny("original GT history contains an omitted or nontransaction durable phase event")
    for tx in transactions:
        _closed_transaction(tx)
        if (not tx.complete or not tx.retrieved or not tx.accepted or not tx.take_attempted
                or not tx.accept_attempted or type(tx.accepted_fact) is not gt._LedgerFact
                or not any(fact is tx.accepted_fact for fact in owner.ledger_facts)
                or tx.accepted_fact.event != "gt_phase_result_accepted"
                or tx.accepted_fact.sha256 != tx.acceptance_result
                or tx.acceptance_result != tx.acceptance_tail_result
                or tx.accepted_fact.payload != _canonical(tx.acceptance_body)
                or tx.accepted_fact.seq <= tx.revoke_fact.seq):
            gt._deny("original native transaction lacks its once-only actual durable result acceptance")


__all__ = []
