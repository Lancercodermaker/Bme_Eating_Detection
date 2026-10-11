"""Live startup bindings, separate from mutable guard/supervisor attributes.

This registry freezes an already approved controller connection; it issues no
approval. Module state is part of the trusted, read-only controller process.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import threading
import weakref


@dataclass(frozen=True, slots=True)
class StartupBinding:
    owner: object
    approval: object
    controller: object
    ledger: object
    limits: object
    study_root: object
    invocation_id: str
    started_ns: int
    controller_sha256: str
    write_volumes: tuple[str, ...]
    ledger_paths: tuple[object, ...]
    pid: int
    thread: object


_BINDINGS = weakref.WeakKeyDictionary()
_PREPARE_ENTERED = weakref.WeakSet()


def registered_startup(guard) -> StartupBinding | None:
    return _BINDINGS.get(guard)


def mark_volume_preparing(guard) -> None:
    if require_startup_binding(guard) is not None:
        _PREPARE_ENTERED.add(guard)


def volume_preparation_entered(guard) -> bool:
    return guard in _PREPARE_ENTERED


def register_startup(owner, guard) -> None:
    if guard in _BINDINGS:
        raise PermissionError("startup owner is already registered")
    _BINDINGS[guard] = StartupBinding(
        weakref.ref(owner), owner.approval, owner.ops, guard.ledger, guard.limits,
        guard.study_root, guard.invocation_id, guard._invocation_started_ns,
        guard.approved_controller_sha256, guard.approved_write_volumes,
        (guard.ledger.study_root, guard.ledger.path, guard.ledger.lock_path),
        os.getpid(), threading.current_thread(),
    )


def require_startup_binding(guard, approval=None) -> StartupBinding | None:
    binding = registered_startup(guard)
    if binding is None:
        if guard._lifecycle_supervisor is not None:
            raise PermissionError("startup owner lacks a live registered binding")
        return None
    owner = binding.owner()
    if (owner is None or os.getpid() != binding.pid or threading.current_thread() is not binding.thread
            or guard._lifecycle_supervisor is not owner or owner._budget_guard is not guard
            or (approval is not None and approval is not binding.approval)
            or owner.approval is not binding.approval or owner.ops is not binding.controller
            or guard.enforcer is not binding.controller or guard.ledger is not binding.ledger
            or guard.limits is not binding.limits or owner.limits is not binding.limits
            or guard.study_root != binding.study_root
            or guard.invocation_id != binding.invocation_id or owner.invocation_id != binding.invocation_id
            or type(guard._invocation_started_ns) is not int or guard._invocation_started_ns != binding.started_ns
            or guard.approved_controller_sha256 != binding.controller_sha256
            or guard.approved_write_volumes != binding.write_volumes
            or (guard.ledger.study_root, guard.ledger.path, guard.ledger.lock_path) != binding.ledger_paths):
        raise PermissionError("registered startup controller, clock, invocation or storage identity drifted")
    return binding
