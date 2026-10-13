/* Route 2 native contracts: SOURCE_ONLY; v2 producers NOT_IMPLEMENTED.
 * Select exactly one R2_TARGET_WINDOWS_SEED, R2_TARGET_LINUX_START, or
 * R2_TARGET_MOUNT_LIBRARY. There is no implicit/default target.
 * The Linux mount-library branch preserves the reviewed v1 syscall bodies.
 * SYS_* comes ONLY from actual target toolchain headers; no guessed numbers,
 * retries, constructors, entry-point bodies, loaders, or fallback mounts.
 * No compilation, linking, loading, or native operation occurs in this source.
 */
#if defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_MOUNT_LIBRARY)
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#endif
#include "route2_mount_helper.h"

#if defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_MOUNT_LIBRARY)
#include <errno.h>
#include <features.h>
#include <sys/syscall.h>
#include <unistd.h>

#if !defined(__linux__) || !defined(__x86_64__) || !defined(__GLIBC__)
#error "Route 2 Linux targets require the reviewed Linux x86-64 glibc ABI"
#endif
#if __GLIBC__ != 2 || __GLIBC_MINOR__ != 35
#error "This source baseline requires glibc 2.35; a change needs new review/freeze"
#endif
#if !defined(SYS_open_tree) || !defined(SYS_mount_setattr) || !defined(SYS_move_mount) || !defined(SYS_umount2)
#error "Actual target syscall headers must provide every required SYS_* constant"
#endif
#ifndef MOUNT_ATTR_SIZE_VER0
#error "Actual target UAPI must provide mount_attr version zero"
#endif

_Static_assert(sizeof(void *) == 8 && sizeof(long) == 8, "x86-64 LP64 required");
_Static_assert(sizeof(struct mount_attr) == MOUNT_ATTR_SIZE_VER0, "mount_attr ABI changed");
_Static_assert(sizeof(((struct mount_attr *)0)->attr_set) == 8, "mount_attr field ABI changed");
_Static_assert(offsetof(struct mount_attr, attr_set) == 0, "attr_set ABI changed");
_Static_assert(offsetof(struct mount_attr, attr_clr) == 8, "attr_clr ABI changed");
_Static_assert(offsetof(struct mount_attr, propagation) == 16, "propagation ABI changed");
_Static_assert(offsetof(struct mount_attr, userns_fd) == 24, "userns_fd ABI changed");
_Static_assert(sizeof(struct route2_mount_abi_v1) == 40, "description ABI changed");
#endif

/* Existing v1 definitions belong only to the legacy mount-library target.
 * Linux start and future seed/start entry declarations remain dormant.
 */
#if defined(R2_TARGET_MOUNT_LIBRARY)
int route2_mount_helper_describe_v1(struct route2_mount_abi_v1 *out, size_t size)
{
    if (out == NULL || size != sizeof(*out)) {
        errno = EINVAL;
        return -1;
    }
    *out = (struct route2_mount_abi_v1) {
        1, __GLIBC__, __GLIBC_MINOR__, sizeof(void *), sizeof(long),
        sizeof(struct mount_attr), offsetof(struct mount_attr, attr_set),
        offsetof(struct mount_attr, attr_clr), offsetof(struct mount_attr, propagation),
        offsetof(struct mount_attr, userns_fd)
    };
    return 0;
}

int route2_open_tree(int dfd, const char *path, unsigned int flags)
{
    return (int)syscall(SYS_open_tree, dfd, path, flags);
}

int route2_mount_setattr(int dfd, const char *path, unsigned int flags,
                        const struct mount_attr *attr, size_t size)
{
    if (attr == NULL || size != sizeof(*attr)) {
        errno = EINVAL;
        return -1;
    }
    return (int)syscall(SYS_mount_setattr, dfd, path, flags, attr, size);
}

int route2_move_mount(int from_dfd, const char *from_path,
                     int to_dfd, const char *to_path, unsigned int flags)
{
    return (int)syscall(SYS_move_mount, from_dfd, from_path, to_dfd, to_path, flags);
}

int route2_umount2(const char *path, int flags)
{
    return (int)syscall(SYS_umount2, path, flags);
}
#endif

#if defined(R2_TARGET_WINDOWS_SEED)
/* Documented SDK floor for limited-query rights; no automatic target default.
 * Installed SDK/compiler/architecture/loader remain UNKNOWN.
 */
#if !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0600
#error "C02-B1 Windows source requires explicit _WIN32_WINNT >= 0x0600"
#endif
#if !defined(__STDC_VERSION__) || __STDC_VERSION__ < 201112L
#error "C02-B1 Windows source requires C11"
#endif
#include <Windows.h>

_Static_assert(sizeof(DWORD) == sizeof(uint32_t), "DWORD must retain all 32 bits");
_Static_assert(sizeof(LONGLONG) == sizeof(int64_t), "QPC requires signed64 storage");
_Static_assert(sizeof(HANDLE) == sizeof(uintptr_t), "HANDLE value width changed");
_Static_assert(sizeof(struct r2_win_raw_process_observation_v1) <= UINT32_MAX,
               "raw native size field overflow");

/* One primary query/argument/invariant fault ends querying. Cleanup can add
 * one close fault, then one endpoint fault: exactly three slots suffice.
 * Caller must exclusively retain out; this helper is private, not a registry.
 */
static void r2_win_raw_add_fault(
    struct r2_win_raw_process_observation_v1 *out,
    uint32_t operation, uint32_t kind, uint32_t code, uint32_t win32_error)
{
    struct r2_win_raw_fault_v1 *fault = &out->faults[out->fault_count++];
    fault->operation = operation;
    fault->kind = kind;
    fault->code = code;
    fault->win32_error = win32_error;
    fault->win32_error_valid = kind == R2_WIN_RAW_FAULT_WIN32;
    if (out->fault_count == 1) {
        out->status = kind == R2_WIN_RAW_FAULT_ARGUMENT ? R2_WIN_RAW_BAD_ARGUMENT :
                      kind == R2_WIN_RAW_FAULT_WIN32 ? R2_WIN_RAW_API_FAILED :
                      R2_WIN_RAW_INVARIANT_FAILED;
    }
}

static uint64_t r2_win_raw_filetime_100ns(const FILETIME *value)
{
    return ((uint64_t)value->dwHighDateTime << 32) | value->dwLowDateTime;
}

/* SOURCE_ONLY / IMPLEMENTED_BUT_UNCOMPILED, not a seed/monitor/controller.
 * GetProcessId precedes every wait and checks the borrowed input before
 * duplication. The successful private duplicate stabilizes the kernel
 * process object through queries and once-close, never issuer provenance.
 */
enum r2_win_raw_status route2_win_raw_process_observe_v1(
    uintptr_t borrowed_process,
    struct r2_win_raw_process_observation_v1 *out, size_t size)
{
    HANDLE borrowed = (HANDLE)borrowed_process;
    HANDLE current_container, owned = NULL;
    int owns_duplicate = 0;
    DWORD pid, exit_code, wait_before, wait_after;
    FILETIME creation, exit_time, kernel, user;
    LARGE_INTEGER frequency, begin, end;

    if (out == NULL || size != sizeof(*out)) {
        return R2_WIN_RAW_BAD_ARGUMENT;
    }
    *out = (struct r2_win_raw_process_observation_v1) {0};
    out->abi = 1;
    out->size = (uint32_t)sizeof(*out);
    if (borrowed == NULL || borrowed == INVALID_HANDLE_VALUE) {
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_ARGUMENT,
                            R2_WIN_RAW_FAULT_ARGUMENT,
                            borrowed == NULL ? R2_WIN_RAW_NULL_PROCESS :
                                               R2_WIN_RAW_INVALID_OR_CURRENT_PSEUDO,
                            0);
        return (enum r2_win_raw_status)out->status;
    }

    if (!QueryPerformanceFrequency(&frequency)) {
        DWORD error = GetLastError();
        out->qpc_frequency.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_QPC_FREQUENCY,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        goto finish;
    }
    out->qpc_frequency.value = (int64_t)frequency.QuadPart;
    out->qpc_frequency.state = R2_WIN_RAW_FIELD_VALID;
    if (frequency.QuadPart <= 0) {
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_QPC_FREQUENCY,
                            R2_WIN_RAW_FAULT_INVARIANT,
                            R2_WIN_RAW_FREQUENCY_NONPOSITIVE, 0);
        goto finish;
    }
    if (!QueryPerformanceCounter(&begin)) {
        DWORD error = GetLastError();
        out->qpc_begin.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_QPC_BEGIN,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        goto finish;
    }
    out->qpc_begin.value = (int64_t)begin.QuadPart;
    out->qpc_begin.state = R2_WIN_RAW_FIELD_VALID;

    pid = GetProcessId(borrowed);
    if (pid == 0) {
        DWORD error = GetLastError();
        out->borrowed_pid.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_BORROWED_PID,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        goto finish;
    }
    out->borrowed_pid.value = (uint32_t)pid;
    out->borrowed_pid.state = R2_WIN_RAW_FIELD_VALID;
    current_container = GetCurrentProcess();
    if (!DuplicateHandle(current_container, borrowed, current_container, &owned,
                         0, FALSE, DUPLICATE_SAME_ACCESS)) {
        DWORD error = GetLastError();
        out->duplicate_state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_DUPLICATE,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        /* Failed output HANDLE is undefined: owns_duplicate remains false. */
        goto finish;
    }
    owns_duplicate = 1;
    out->duplicate_state = R2_WIN_RAW_FIELD_VALID;
    pid = GetProcessId(owned);
    if (pid == 0) {
        DWORD error = GetLastError();
        out->duplicate_pid.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_DUPLICATE_PID,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        goto finish;
    }
    out->duplicate_pid.value = (uint32_t)pid;
    out->duplicate_pid.state = R2_WIN_RAW_FIELD_VALID;
    if (out->duplicate_pid.value != out->borrowed_pid.value) {
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_DUPLICATE_PID,
                            R2_WIN_RAW_FAULT_INVARIANT,
                            R2_WIN_RAW_PID_CHANGED, 0);
        goto finish;
    }

    wait_before = WaitForSingleObject(owned, 0);
    if (wait_before == WAIT_FAILED) {
        DWORD error = GetLastError();
        out->wait_before.value = (uint32_t)wait_before;
        out->wait_before.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_WAIT_BEFORE,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        goto finish;
    }
    out->wait_before.value = (uint32_t)wait_before;
    if (wait_before != WAIT_OBJECT_0 && wait_before != WAIT_TIMEOUT) {
        out->wait_before.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_WAIT_BEFORE,
                            R2_WIN_RAW_FAULT_INVARIANT,
                            R2_WIN_RAW_WAIT_UNEXPECTED, 0);
        goto finish;
    }
    out->wait_before.state = R2_WIN_RAW_FIELD_VALID;
    if (!GetProcessTimes(owned, &creation, &exit_time, &kernel, &user)) {
        DWORD error = GetLastError();
        out->creation_before_100ns.state = R2_WIN_RAW_FIELD_FAILED;
        out->kernel_cpu_before_100ns.state = R2_WIN_RAW_FIELD_FAILED;
        out->user_cpu_before_100ns.state = R2_WIN_RAW_FIELD_FAILED;
        if (wait_before == WAIT_OBJECT_0) {
            out->exit_filetime_100ns.state = R2_WIN_RAW_FIELD_FAILED;
        }
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_TIMES_BEFORE,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        goto finish;
    }
    out->creation_before_100ns.value = r2_win_raw_filetime_100ns(&creation);
    out->creation_before_100ns.state = R2_WIN_RAW_FIELD_VALID;
    out->kernel_cpu_before_100ns.value = r2_win_raw_filetime_100ns(&kernel);
    out->kernel_cpu_before_100ns.state = R2_WIN_RAW_FIELD_VALID;
    out->user_cpu_before_100ns.value = r2_win_raw_filetime_100ns(&user);
    out->user_cpu_before_100ns.state = R2_WIN_RAW_FIELD_VALID;
    if (wait_before == WAIT_OBJECT_0) {
        out->exit_filetime_100ns.value = r2_win_raw_filetime_100ns(&exit_time);
        out->exit_filetime_100ns.state = R2_WIN_RAW_FIELD_VALID;
    }
    /* exit_time is never read when the first poll was nonsignaled. */

    wait_after = WaitForSingleObject(owned, 0);
    if (wait_after == WAIT_FAILED) {
        DWORD error = GetLastError();
        out->wait_after.value = (uint32_t)wait_after;
        out->wait_after.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_WAIT_AFTER,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        goto finish;
    }
    out->wait_after.value = (uint32_t)wait_after;
    if (wait_after != WAIT_OBJECT_0 && wait_after != WAIT_TIMEOUT) {
        out->wait_after.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_WAIT_AFTER,
                            R2_WIN_RAW_FAULT_INVARIANT,
                            R2_WIN_RAW_WAIT_UNEXPECTED, 0);
        goto finish;
    }
    out->wait_after.state = R2_WIN_RAW_FIELD_VALID;
    if (wait_before == WAIT_OBJECT_0 && wait_after != WAIT_OBJECT_0) {
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_WAIT_AFTER,
                            R2_WIN_RAW_FAULT_INVARIANT,
                            R2_WIN_RAW_SIGNAL_REGRESSED, 0);
        goto finish;
    }
    if (wait_after == WAIT_OBJECT_0) {
        if (wait_before == WAIT_TIMEOUT) {
            /* Fresh call after signal: its exit FILETIME is now defined.
             * Preserve both creation/CPU observations even if identity fails.
             */
            if (!GetProcessTimes(owned, &creation, &exit_time, &kernel, &user)) {
                DWORD error = GetLastError();
                out->creation_after_100ns.state = R2_WIN_RAW_FIELD_FAILED;
                out->kernel_cpu_after_100ns.state = R2_WIN_RAW_FIELD_FAILED;
                out->user_cpu_after_100ns.state = R2_WIN_RAW_FIELD_FAILED;
                out->exit_filetime_100ns.state = R2_WIN_RAW_FIELD_FAILED;
                r2_win_raw_add_fault(out, R2_WIN_RAW_OP_TIMES_AFTER,
                                    R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
                goto finish;
            }
            out->creation_after_100ns.value = r2_win_raw_filetime_100ns(&creation);
            out->creation_after_100ns.state = R2_WIN_RAW_FIELD_VALID;
            out->kernel_cpu_after_100ns.value = r2_win_raw_filetime_100ns(&kernel);
            out->kernel_cpu_after_100ns.state = R2_WIN_RAW_FIELD_VALID;
            out->user_cpu_after_100ns.value = r2_win_raw_filetime_100ns(&user);
            out->user_cpu_after_100ns.state = R2_WIN_RAW_FIELD_VALID;
            out->exit_filetime_100ns.value = r2_win_raw_filetime_100ns(&exit_time);
            out->exit_filetime_100ns.state = R2_WIN_RAW_FIELD_VALID;
            if (out->creation_after_100ns.value != out->creation_before_100ns.value) {
                r2_win_raw_add_fault(out, R2_WIN_RAW_OP_TIMES_AFTER,
                                    R2_WIN_RAW_FAULT_INVARIANT,
                                    R2_WIN_RAW_CREATION_CHANGED, 0);
                goto finish;
            }
        }
        if (!GetExitCodeProcess(owned, &exit_code)) {
            DWORD error = GetLastError();
            out->exit_code.state = R2_WIN_RAW_FIELD_FAILED;
            r2_win_raw_add_fault(out, R2_WIN_RAW_OP_EXIT_CODE,
                                R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
            goto finish;
        }
        out->exit_code.value = (uint32_t)exit_code;
        out->exit_code.state = R2_WIN_RAW_FIELD_VALID;
        /* Actual signal is the witness: exit code 259 is never reinterpreted. */
        if (wait_before == WAIT_TIMEOUT) {
            out->sample_kind = R2_WIN_RAW_EXITED_BETWEEN_POLLS;
            out->status = R2_WIN_RAW_EXIT_RACED; /* incomplete / STOP_NEW */
        } else {
            out->sample_kind = R2_WIN_RAW_EXITED_BEFORE_FIRST_POLL;
            out->status = R2_WIN_RAW_SAMPLE_COMPLETE;
        }
    } else {
        out->sample_kind = R2_WIN_RAW_LIVE_AT_BOTH_POLLS;
        out->status = R2_WIN_RAW_SAMPLE_COMPLETE;
    }

finish:
    if (owns_duplicate) {
        if (!CloseHandle(owned)) {
            DWORD error = GetLastError();
            out->close_state = R2_WIN_RAW_FIELD_FAILED;
            r2_win_raw_add_fault(out, R2_WIN_RAW_OP_CLOSE,
                                R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
        } else {
            out->close_state = R2_WIN_RAW_FIELD_VALID;
        }
        /* One attempt only, including failure; never close borrowed/container. */
    }
    if (!QueryPerformanceCounter(&end)) {
        DWORD error = GetLastError();
        out->qpc_end.state = R2_WIN_RAW_FIELD_FAILED;
        r2_win_raw_add_fault(out, R2_WIN_RAW_OP_QPC_END,
                            R2_WIN_RAW_FAULT_WIN32, 0, (uint32_t)error);
    } else {
        out->qpc_end.value = (int64_t)end.QuadPart;
        out->qpc_end.state = R2_WIN_RAW_FIELD_VALID;
        if (out->qpc_begin.state == R2_WIN_RAW_FIELD_VALID &&
            out->qpc_end.value < out->qpc_begin.value) {
            r2_win_raw_add_fault(out, R2_WIN_RAW_OP_QPC_END,
                                R2_WIN_RAW_FAULT_INVARIANT,
                                R2_WIN_RAW_QPC_REGRESSED, 0);
        }
    }
    return (enum r2_win_raw_status)out->status;
}

enum r2_scope_result route2_win_refuse_vm_service_scope_v1(void)
{
    return R2_VM_SERVICE_SCOPE_UNPROVEN;
}

enum r2_scope_result route2_win_refuse_e_physical_cap_v1(void)
{
    return R2_E_PHYSICAL_CAP_UNPROVEN;
}

enum r2_scope_result route2_win_refuse_owner_exit_join_v1(void)
{
    return R2_OWNER_EXIT_JOIN_UNPROVEN;
}
#endif
