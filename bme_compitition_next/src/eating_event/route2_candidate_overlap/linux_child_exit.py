"""Private Linux pidfd exit consumption for a future fixed phase producer.

This implements kernel wait/reap/status and once-only failure cleanup. It is
not a launch producer or an exit attestation: only the private original spawn
owner may supply its held pidfd/PID and original stop/cleanup deadlines. No
production entry calls it yet. UID, sandbox, IPC, birth and backing history
remain UNKNOWN; nested production admission continues to refuse.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import select
import signal
import threading
import time

from .native_failure_capture import NativeFailureCapture


@dataclass(frozen=True, slots=True)
class _NativeExit:
    pid: int
    uid: int
    signo: int
    code: int
    status: int
    observed_monotonic_ns: int
    reaped_monotonic_ns: int


def _consume_pidfd_exit(*, pidfd: int, expected_pid: int,
                        stop_deadline_ns: int, cleanup_deadline_ns: int,
                        _failure_cleanup: bool = False) -> _NativeExit:
    """Consume native siginfo twice: WNOWAIT observation, then one reap.

    All arguments belong to the missing private spawn owner, not an approval
    API. In particular this routine cannot prove the deadlines' budget origin.
    A supplied PID/status/boolean never becomes an accepted production receipt.
    """
    if (platform.system() != "Linux" or threading.current_thread() is not threading.main_thread()
            or type(pidfd) is not int or pidfd < 0 or type(expected_pid) is not int or expected_pid <= 1
            or type(stop_deadline_ns) is not int or type(cleanup_deadline_ns) is not int
            or type(_failure_cleanup) is not bool or stop_deadline_ns < 0
            or not stop_deadline_ns < cleanup_deadline_ns
            or time.monotonic_ns() >= cleanup_deadline_ns
            or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
            or len(os.listdir("/proc/self/task")) != 1
            or not all(hasattr(os, name) for name in ("P_PIDFD", "WEXITED", "WNOWAIT", "WNOHANG"))
            or not hasattr(signal, "pidfd_send_signal")):
        raise PermissionError("native child consumption requires the single original Linux reaper and pidfd API")
    errors = NativeFailureCapture(8)
    errors.failure.native_exit = None
    errors.failure.observed_exit = None
    errors.failure.reaped = False
    errors.failure.child_exit_attestation = "NOT_ATTESTED"
    owned = metadata_fd = None
    child_confirmed = reap_attempted = kill_attempted = False
    observed = primary = None

    def validate(info):
        if (info is None or info.si_pid != expected_pid or info.si_signo != signal.SIGCHLD
                or info.si_code not in (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED)):
            raise PermissionError("native pidfd exit is absent or differs from the original child")
        return (info.si_pid, info.si_uid, info.si_signo, info.si_code, info.si_status)

    def wait_exit(deadline):
        poller = select.poll()
        poller.register(owned, select.POLLIN)
        while True:
            now = time.monotonic_ns()
            if now >= deadline:
                raise TimeoutError("original child exit deadline reached")
            info = os.waitid(os.P_PIDFD, owned, os.WEXITED | os.WNOWAIT | os.WNOHANG)
            if info is not None:
                errors.failure.observed_exit = info
                observed_ns = time.monotonic_ns()
                if observed_ns >= deadline:
                    raise TimeoutError("native child observation crossed its original deadline")
                return info, observed_ns
            events = poller.poll(min(50, max(1, (deadline - now) // 1_000_000)))
            if any(flags & (select.POLLERR | select.POLLNVAL) for _, flags in events):
                raise OSError("owned pidfd poll failed")

    def reap(info, observed_ns, deadline):
        nonlocal reap_attempted
        values = validate(info)
        if time.monotonic_ns() >= deadline:
            raise TimeoutError("native child reap cannot start past its original deadline")
        # The single native reap is consumed even if it raises or another
        # waiter has stolen the status. There is no waitpid/numeric-PID fallback.
        reap_attempted = True
        actual = os.waitid(os.P_PIDFD, owned, os.WEXITED | os.WNOHANG)
        if actual is not None:
            errors.failure.reaped = True
            errors.failure.native_exit = actual
        if validate(actual) != values:
            raise PermissionError("native reap status differs from the held WNOWAIT observation")
        result = _NativeExit(*values, observed_ns, time.monotonic_ns())
        errors.failure.native_exit = result
        return result

    try:
        owned = os.dup(pidfd)
        os.set_inheritable(owned, False)
        if os.readlink(f"/proc/self/fd/{owned}") != "anon_inode:[pidfd]":
            raise PermissionError("original child handle is not a native pidfd")
        metadata_fd = os.open(f"/proc/self/fdinfo/{owned}", os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        metadata = os.read(metadata_fd, 4097)
        if len(metadata) > 4096:
            raise PermissionError("pidfd kernel metadata exceeds its bound")
        rows = [row.split(b":", 1)[1].strip() for row in metadata.splitlines() if row.startswith(b"Pid:")]
        if len(rows) != 1 or rows[0] != str(expected_pid).encode("ascii"):
            raise PermissionError("held pidfd does not identify the original spawn PID")
        closing, metadata_fd = metadata_fd, None
        os.close(closing)
        # A successful P_PIDFD wait, including None, proves this kernel child
        # is waitable by the current parent. No foreign pidfd is signalled.
        observed = os.waitid(os.P_PIDFD, owned, os.WEXITED | os.WNOWAIT | os.WNOHANG)
        child_confirmed = True
        errors.failure.observed_exit = observed
        if not _failure_cleanup and time.monotonic_ns() >= stop_deadline_ns:
            raise TimeoutError("original child stop deadline expired before exit consumption")
        # An IPC/setup failure may arrive after stop. Its owner consumes the
        # original cleanup interval, never a renewed stop or duration. Prove
        # parenthood with P_PIDFD before signalling; there is no PID fallback.
        deadline = cleanup_deadline_ns if _failure_cleanup else stop_deadline_ns
        if _failure_cleanup and observed is None:
            kill_attempted = True
            try:
                if time.monotonic_ns() >= cleanup_deadline_ns:
                    raise TimeoutError("failed child kill cannot start past original cleanup deadline")
                signal.pidfd_send_signal(owned, signal.SIGKILL, None, 0)
            except BaseException as kill_error:
                errors._slots[1].operation = "native_child_failure_kill"
                errors._slots[1].error = kill_error
                errors._slots[1].descriptor = owned
        observed, observed_ns = (observed, time.monotonic_ns()) if observed is not None else wait_exit(deadline)
        result = reap(observed, observed_ns, deadline)
        if result.reaped_monotonic_ns >= deadline:
            raise TimeoutError("original child reap crossed its stop deadline")
        if errors._slots[1].error is not None:
            raise errors._slots[1].error
        if not _failure_cleanup and (result.code != os.CLD_EXITED or result.status != 0):
            raise ChildProcessError("phase child failed; raw native exit retained")
        return result
    except BaseException as exc:
        primary = exc
        errors.failure.primary_error = exc
        errors._slots[0].operation = "native_child_exit_primary"
        errors._slots[0].error = exc
        if child_confirmed and not reap_attempted:
            if not kill_attempted:
                kill_attempted = True
                try:
                    if time.monotonic_ns() >= cleanup_deadline_ns:
                        raise TimeoutError("failed child kill cannot start past original cleanup deadline")
                    signal.pidfd_send_signal(owned, signal.SIGKILL, None, 0)
                except BaseException as kill_error:
                    errors._slots[1].operation = "native_child_failure_kill"
                    errors._slots[1].error = kill_error
                    errors._slots[1].descriptor = owned
            try:
                info, timestamp = wait_exit(cleanup_deadline_ns)
                reap(info, timestamp, cleanup_deadline_ns)
                if time.monotonic_ns() >= cleanup_deadline_ns:
                    raise TimeoutError("failed child reap crossed original cleanup deadline")
            except BaseException as reap_error:
                errors._slots[2].operation = "native_child_failure_reap"
                errors._slots[2].error = reap_error
                errors._slots[2].descriptor = owned
        raise errors.failure from exc
    finally:
        close_failed = False
        if metadata_fd is not None:
            descriptor, metadata_fd = metadata_fd, None
            try:
                os.close(descriptor)
            except BaseException as close_error:
                close_failed = True
                if primary is None:
                    primary = errors.failure.primary_error = close_error
                # Fixed slots; neither formatting nor callback dispatch can
                # prevent the remaining descriptor from being consumed once.
                errors._slots[3].operation = "native_child_exit_metadata_close"
                errors._slots[3].error = close_error
                errors._slots[3].descriptor = descriptor
        if owned is not None:
            descriptor, owned = owned, None
            try:
                os.close(descriptor)
            except BaseException as close_error:
                close_failed = True
                if primary is None:
                    primary = errors.failure.primary_error = close_error
                errors._slots[4].operation = "native_child_exit_pidfd_close"
                errors._slots[4].error = close_error
                errors._slots[4].descriptor = descriptor
        if close_failed:
            raise errors.failure from primary


__all__ = []
