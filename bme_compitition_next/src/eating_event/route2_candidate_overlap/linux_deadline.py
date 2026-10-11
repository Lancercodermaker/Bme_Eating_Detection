"""Linux kernel deadlines for the trusted controller, without helper tasks.

Nothing is armed at import or construction. This primitive kills the controller
at an absolute monotonic deadline. Installed systemd KillMode=control-group
must independently terminate its workers; this primitive alone proves no
cgroup teardown, terminal, wall acceptance or experiment admission.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os
import platform
import signal
import threading
import time
import weakref


class _Timespec(ctypes.Structure):
    _fields_ = [("seconds", ctypes.c_long), ("nanoseconds", ctypes.c_long)]


class _Itimerspec(ctypes.Structure):
    _fields_ = [("interval", _Timespec), ("value", _Timespec)]


class _Sigevent(ctypes.Structure):
    # This adapter is deliberately restricted to Linux x86-64 glibc.
    _fields_ = [("value", ctypes.c_void_p), ("signo", ctypes.c_int),
                ("notify", ctypes.c_int), ("padding", ctypes.c_int * 12)]


@dataclass(slots=True)
class _NativeTimer:
    library: object
    timer_id: object
    pid: int
    thread: object
    deadline_ns: int
    consumed: bool = False
    armed: bool = False


_TIMERS = weakref.WeakKeyDictionary()


class LinuxKernelDeadline:
    """A one-use, noncatchable SIGKILL timer owned by its creating controller.

    An abandoned armed handle deliberately remains armed. There is no GC
    disarm, exception fallback, background Python thread or subprocess.
    """

    def arm(self, deadline_ns: int) -> None:
        if self in _TIMERS:
            raise PermissionError("kernel deadline may be armed only once")
        if (platform.system() != "Linux" or platform.machine() != "x86_64"
                or platform.libc_ver()[0] != "glibc"
                or ctypes.sizeof(ctypes.c_void_p) != 8
                or ctypes.sizeof(ctypes.c_long) != 8
                or ctypes.sizeof(_Sigevent) != 64):
            raise PermissionError("kernel deadline requires the reviewed Linux x86-64 glibc ABI")
        if threading.current_thread() is not threading.main_thread():
            raise PermissionError("kernel deadline requires the original main controller thread")
        if type(deadline_ns) is not int or deadline_ns <= time.monotonic_ns():
            raise PermissionError("kernel deadline is absent or already expired")
        libc = ctypes.CDLL(None, use_errno=True)
        libc.timer_create.argtypes = [ctypes.c_int, ctypes.POINTER(_Sigevent),
                                      ctypes.POINTER(ctypes.c_void_p)]
        libc.timer_create.restype = ctypes.c_int
        libc.timer_settime.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                       ctypes.POINTER(_Itimerspec), ctypes.c_void_p]
        libc.timer_settime.restype = ctypes.c_int
        libc.timer_delete.argtypes = [ctypes.c_void_p]
        libc.timer_delete.restype = ctypes.c_int
        timer_id = ctypes.c_void_p()
        event = _Sigevent()
        event.signo, event.notify = signal.SIGKILL, 0  # SIGEV_SIGNAL
        if libc.timer_create(1, ctypes.byref(event), ctypes.byref(timer_id)) != 0:
            raise OSError(ctypes.get_errno(), "timer_create(CLOCK_MONOTONIC, SIGKILL) failed")
        state = _NativeTimer(libc, timer_id, os.getpid(), threading.current_thread(), deadline_ns)
        _TIMERS[self] = state
        settings = _Itimerspec()
        settings.value.seconds, settings.value.nanoseconds = divmod(deadline_ns, 1_000_000_000)
        if libc.timer_settime(timer_id, 1, ctypes.byref(settings), None) != 0:  # TIMER_ABSTIME
            state.consumed = True
            failure = ctypes.get_errno()
            if libc.timer_delete(timer_id) != 0:
                raise OSError(ctypes.get_errno(), "failed to delete an unarmed kernel deadline")
            raise OSError(failure, "timer_settime absolute kernel deadline failed")
        state.armed = True

    def finish(self) -> None:
        """Consume after original-controller cleanup; failed/late finish denies.

        The controller must verify worker/GT quiescence before calling this.
        Calling it is not itself evidence that those checks happened.
        """
        state = _TIMERS.get(self)
        if (state is None or state.consumed or not state.armed or state.pid != os.getpid()
                or state.thread is not threading.current_thread()):
            raise PermissionError("kernel deadline is not owned by this live controller")
        state.consumed = True
        if time.monotonic_ns() >= state.deadline_ns:
            # Keep the timer armed; never turn a late operation into success.
            raise PermissionError("controller cleanup reached its kernel deadline")
        if state.library.timer_delete(state.timer_id) != 0:
            raise OSError(ctypes.get_errno(), "kernel deadline deletion failed")
        if time.monotonic_ns() >= state.deadline_ns:
            # timer_delete disarms; a crossing after deletion cannot be left
            # as an exception a caller may catch and continue past the cap.
            try:
                os.kill(state.pid, signal.SIGKILL)
            finally:
                os._exit(137)


__all__ = ["LinuxKernelDeadline"]
