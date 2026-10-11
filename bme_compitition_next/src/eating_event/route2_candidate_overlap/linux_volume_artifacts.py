"""Held-FD byte checks for the exact 105 replayed treatment outputs.

This proves byte hash/size/newline count against the authenticated journal,
not JSON semantics, interval fingerprints, or reference/input provenance.
It grants no admission. The study lock and all 105 advisory artifact locks
remain held until expansion completes or fails; production paths are walked
through root-owned, non-worker-writable directories with NOFOLLOW/NONBLOCK.
This serialization assumes the trusted controller is the only authorized
writer. A separate privileged root writer ignoring those locks is outside
that guarantee. Every checkpoint rehashes held FDs and fences the whole set
with dev/inode/size/mtime/ctime checks after its last streamed read.
"""

from __future__ import annotations

import hashlib
import stat

from .stage_a_replay import StageAReplayReceipt


CHUNK_BYTES = 65536
MAX_ARTIFACT_BYTES = 2 << 30


def _snapshot(info, *, volume_device: int, file_bytes: int) -> tuple[int, ...]:
    names = ("st_dev", "st_ino", "st_rdev", "st_size", "st_mtime_ns", "st_ctime_ns",
             "st_mode", "st_uid", "st_nlink")
    values = tuple(getattr(info, name, None) for name in names)
    if (any(type(value) is not int for value in values)
            or info.st_dev != volume_device or info.st_ino <= 0 or info.st_rdev != 0
            or info.st_size != file_bytes or info.st_mtime_ns < 0 or info.st_ctime_ns < 0
            or not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) & 0o7077):
        raise PermissionError("candidate artifact is not an exact protected regular file on the study volume")
    return values


class HeldTreatmentArtifacts:
    """Retain the replay's exact files; never accept a supplied verification flag."""

    def __init__(self, ports, replay: StageAReplayReceipt, *, volume_device: int,
                 deadline_ns: int, not_before_ns: int):
        if (type(replay) is not StageAReplayReceipt or len(replay.treatment_files) != 105
                or len({item.path for item in replay.treatment_files}) != 105
                or not 0 <= replay.candidate_file_bytes_b <= MAX_ARTIFACT_BYTES
                or sum(item.file_bytes for item in replay.treatment_files) != replay.candidate_file_bytes_b
                or type(volume_device) is not int or volume_device <= 0
                or type(deadline_ns) is not int or type(not_before_ns) is not int
                or not 0 < not_before_ns < deadline_ns):
            raise PermissionError("artifact verification requires the exact bounded Stage A replay")
        self._ports = ports
        self._files = replay.treatment_files
        self._device = volume_device
        self._deadline = deadline_ns
        self._last_ns = not_before_ns
        self._held = []
        self._opened = False
        self._closed = False

    def _time(self):
        now = self._ports.monotonic_ns()
        if type(now) is not int or not self._last_ns <= now <= self._deadline:
            raise PermissionError("candidate artifact verification exceeded the invocation wall deadline")
        self._last_ns = now

    def _metadata(self, receipt, descriptor):
        held = _snapshot(self._ports.fstat(descriptor), volume_device=self._device,
                         file_bytes=receipt.file_bytes)
        visible = _snapshot(self._ports.path_stat(receipt.path, kind="file"),
                            volume_device=self._device, file_bytes=receipt.file_bytes)
        if held != visible:
            raise PermissionError("candidate artifact visible path differs from its held descriptor")
        return held

    def _stream(self, receipt, descriptor):
        self._ports.rewind_fd(descriptor)
        digest = hashlib.sha256()
        offset = rows = 0
        last = b""
        while offset < receipt.file_bytes:
            self._time()
            maximum = min(CHUNK_BYTES, receipt.file_bytes - offset)
            chunk = self._ports.read_chunk(descriptor, max_bytes=maximum)
            if type(chunk) is not bytes or not 0 < len(chunk) <= maximum:
                raise PermissionError("candidate artifact stream is incomplete or exceeds its exact byte boundary")
            digest.update(chunk)
            rows += chunk.count(b"\n")
            offset += len(chunk)
            last = chunk[-1:]
        self._time()
        # One bounded EOF probe also protects against growth after the stat sample.
        tail = self._ports.read_chunk(descriptor, max_bytes=1)
        if type(tail) is not bytes or tail != b"":
            raise PermissionError("candidate artifact exceeds its receipt byte boundary")
        if (offset != receipt.file_bytes or rows != receipt.row_count
                or (offset and last != b"\n") or digest.hexdigest() != receipt.sha256):
            raise PermissionError("candidate artifact SHA-256, rows, bytes or final newline differ from the replay")

    def open_and_verify(self):
        if self._opened or self._closed:
            raise PermissionError("candidate artifact descriptor set is one-shot")
        self._opened = True
        try:
            for receipt in self._files:
                self._time()
                descriptor = self._ports.open_existing(receipt.path, kind="file", writable=False)
                # Register immediately so stat/flock/stream failures close this FD too.
                self._held.append((receipt, descriptor, None))
                self._ports.lock_exclusive(descriptor)
                baseline = self._metadata(receipt, descriptor)
                self._held[-1] = (receipt, descriptor, baseline)
                self._stream(receipt, descriptor)
                if self._metadata(receipt, descriptor) != baseline:
                    raise PermissionError("candidate artifact changed during its initial held-FD read")
            self._fence()
        except BaseException:
            self.close()
            raise

    def _fence(self):
        # Catch changes to earlier files while later files were being read. Linux
        # ctime cannot be restored by ordinary writers even if mtime is restored.
        for receipt, descriptor, baseline in self._held:
            self._time()
            if self._metadata(receipt, descriptor) != baseline:
                raise PermissionError("candidate artifact identity or metadata changed across the descriptor set")

    def checkpoint(self):
        if not self._opened or self._closed or len(self._held) != 105:
            raise PermissionError("all 105 candidate artifact descriptors must remain held")
        for receipt, descriptor, baseline in self._held:
            self._time()
            if self._metadata(receipt, descriptor) != baseline:
                raise PermissionError("candidate artifact snapshot changed before an expansion checkpoint")
            self._stream(receipt, descriptor)
            if self._metadata(receipt, descriptor) != baseline:
                raise PermissionError("candidate artifact changed during a checkpoint stream")
        self._fence()

    def close(self):
        if self._closed:
            return
        self._closed = True
        failure = None
        for _, descriptor, _ in reversed(self._held):
            try:
                self._ports.close(descriptor)
            except BaseException as exc:
                failure = failure or exc
        if failure is not None:
            raise failure
