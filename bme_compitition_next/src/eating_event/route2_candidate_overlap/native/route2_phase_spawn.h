/* Private source primitive, not installation, GT-release or budget authority.
 * The original controller must supply its original absolute CLOCK_MONOTONIC
 * deadlines and C/2 limit. A reviewed parent producer must already own the
 * fixed, protected, phase-only source tree and empty root placeholder. Neither
 * this ABI nor a scan establishes that tree's creation/deletion history.
 * No caller paths, callbacks, root FDs, factories or receipts enter this ABI.
 * Independent of route2_mount_helper's existing 40-byte ABI. */
#ifndef ROUTE2_PHASE_SPAWN_H
#define ROUTE2_PHASE_SPAWN_H
#include <stdint.h>

#define R2_PHASE_ABI 1U
#define R2_PHASE_ERRORS 16U
#define R2_PHASE_SOURCE "/run/route2-phase-source"
#define R2_PHASE_ROOT "/run/route2-phase-root"
#define R2_PHASE_IPC 3
#define R2_PHASE_STATUS 4
#define R2_PHASE_EXEC 5
#define R2_PHASE_PERMIT 6
#define R2_PHASE_PARENT 7

enum r2_operation {
    R2_VALIDATE = 1, R2_SOCKET, R2_CLONE, R2_BIRTH, R2_ROOT_OPEN,
    R2_PRIVATE, R2_TREE, R2_ATTRIBUTES, R2_PUBLISH, R2_ROOT_REOPEN,
    R2_CHROOT, R2_EXEC_OPEN, R2_DUP, R2_CLOSE, R2_CLOSE_RANGE,
    R2_SIGNALS, R2_LIMITS, R2_CREDENTIALS, R2_SECCOMP, R2_READY,
    R2_PERMIT, R2_EXECVE, R2_CLOCK, R2_POLL, R2_PARENT_OPEN, R2_PARENT_LIVE
};
enum r2_status_kind { R2_READY_STATUS = 1, R2_FAILED_STATUS = 2 };

struct r2_error { int32_t operation, error_number, descriptor; };
struct r2_phase_spec {
    uint32_t abi, size;
    uint64_t as_limit_bytes, stop_deadline_ns, cleanup_deadline_ns;
};
struct r2_phase_status {
    uint32_t abi, kind, error_count, reserved;
    struct r2_error errors[R2_PHASE_ERRORS];
};
struct r2_phase_result {
    uint32_t abi, size;
    int32_t pid, pidfd, ipc_fd, status_fd, permit_fd;
    uint32_t error_count;
    struct r2_error errors[R2_PHASE_ERRORS];
};

/* All returned FDs, including after a post-clone error, belong to the parent.
 * The PID and original CLONE_PIDFD fd describe birth only; they are not a
 * sandbox/GT receipt. Child branches never return through the Python FFI.
 * The child blocks until the native parent holds the atomic pidfd, then emits
 * a fixed typed READY/FAILED status. READY does not execute Python: only the
 * original parent can send the final one-byte permit on its private FD. */
uint32_t route2_phase_spawn_abi(uint32_t spec_size, uint32_t result_size);
int route2_phase_spawn(const struct r2_phase_spec *, struct r2_phase_result *);
#endif
