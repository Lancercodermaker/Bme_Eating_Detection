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

#if defined(R2_TARGET_WINDOWS_SEED)
/* C02-A independent SOURCE component; old C02-B1 guard/body is unchanged. */
#if !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0602
#error "C02-A CPU-rate SDK contract requires explicit _WIN32_WINNT >= 0x0602"
#endif
#if !defined(_WIN64) || !(defined(_M_X64) || defined(__x86_64__))
#error "C02-A source requires native Windows x64"
#endif
#if !defined(__STDC_VERSION__) || __STDC_VERSION__ < 201112L
#error "C02-A source requires C11 including stdatomic.h"
#endif
#include <stdatomic.h>
#include <Jobapi.h>
#include <Jobapi2.h>

_Static_assert(sizeof(HANDLE) == 8 && sizeof(uintptr_t) == 8 &&
               sizeof(SIZE_T) == 8 && sizeof(DWORD_PTR) == 8,
               "C02-A native x64 HANDLE/commit/affinity widths required");
_Static_assert(sizeof(DWORD) == sizeof(uint32_t), "preserve every DWORD bit");
_Static_assert(sizeof(LONGLONG) == sizeof(int64_t), "native accounting is signed64");
_Static_assert(sizeof(enum r2_win_job_raw_status) == sizeof(uint32_t),
               "C02-A status native ABI must be 32 bits");
_Static_assert(sizeof(struct r2_win_job_raw_report_v1) <= UINT32_MAX,
               "C02-A report size must fit versioned native size field");
_Static_assert(sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION) <= UINT32_MAX &&
               sizeof(JOBOBJECT_CPU_RATE_CONTROL_INFORMATION) <= UINT32_MAX &&
               sizeof(JOBOBJECT_BASIC_ACCOUNTING_INFORMATION) <= UINT32_MAX,
               "native query lengths must fit DWORD");
_Static_assert(R2_WIN_JOB_RAW_FAULT_CAPACITY == 3,
               "one primary and both independent close faults");

#define R2_JOB_FIXED_FLAGS (JOB_OBJECT_LIMIT_ACTIVE_PROCESS | \
    JOB_OBJECT_LIMIT_AFFINITY | JOB_OBJECT_LIMIT_JOB_MEMORY | \
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
#define R2_JOB_FIXED_CPU_FLAGS (JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | \
    JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP)
#define R2_JOB_FIXED_COMMIT (UINT64_C(4) * 1024 * 1024 * 1024)

static atomic_flag r2_job_guard = ATOMIC_FLAG_INIT;
static HANDLE r2_job_original = NULL;
static HANDLE r2_job_duplicate = NULL;
static struct r2_win_job_raw_report_v1 r2_job_report = {
    .abi = 1, .size = sizeof(struct r2_win_job_raw_report_v1),
    .status = R2_WIN_JOB_RAW_UNKNOWN, .lifecycle = R2_WIN_JOB_NEW
};

static int r2_job_enter(void)
{
    return !atomic_flag_test_and_set_explicit(&r2_job_guard, memory_order_acquire);
}
static enum r2_win_job_raw_status r2_job_leave(enum r2_win_job_raw_status status)
{
    atomic_flag_clear_explicit(&r2_job_guard, memory_order_release);
    return status;
}
static enum r2_win_job_raw_status r2_job_status(void)
{
    return (enum r2_win_job_raw_status)r2_job_report.status;
}
/* Only one precleanup fault can reach here: it poisons all further native
 * work. Once-cleanup can append both close errors, and cannot run twice.
 * Thus fault_count is <=2 before every append, capacity is exactly three.
 */
static void r2_job_fault(uint32_t operation, uint32_t kind, uint32_t code,
                         uint32_t error, enum r2_win_job_raw_status status)
{
    struct r2_win_job_raw_fault_v1 *f =
        &r2_job_report.faults[r2_job_report.fault_count++];
    f->operation = operation; f->kind = kind; f->code = code;
    f->win32_error = error; f->win32_error_valid = kind == R2_WIN_JOB_FAULT_WIN32;
    if (r2_job_report.fault_count == 1) r2_job_report.status = status;
    r2_job_report.poisoned = 1;
    if (r2_job_report.lifecycle != R2_WIN_JOB_HANDLES_CONSUMED)
        r2_job_report.lifecycle = R2_WIN_JOB_POISONED;
}
static void r2_job_api_fault(uint32_t op, DWORD error)
{
    r2_job_fault(op, R2_WIN_JOB_FAULT_WIN32, 0, (uint32_t)error,
                 R2_WIN_JOB_RAW_API_FAILED);
}
static void r2_job_invariant(uint32_t op, uint32_t code)
{
    r2_job_fault(op, R2_WIN_JOB_FAULT_INVARIANT, code, 0,
                 R2_WIN_JOB_RAW_INVARIANT_FAILED);
}
static int r2_job_mutable(void)
{
    return !r2_job_report.poisoned &&
           r2_job_report.lifecycle != R2_WIN_JOB_HANDLES_CONSUMED;
}
static enum r2_win_job_raw_status r2_job_refused_status(void)
{
    return r2_job_report.poisoned ? r2_job_status() : R2_WIN_JOB_RAW_BAD_STATE;
}
static int r2_job_query_native(JOBOBJECTINFOCLASS cls, void *out,
                                DWORD size, uint32_t op)
{
    DWORD returned = 0;
    if (!QueryInformationJobObject(r2_job_original, cls, out, size, &returned)) {
        DWORD error = GetLastError();
        r2_job_api_fault(op, error);
        return 0;
    }
    if (returned != size) {
        r2_job_invariant(op, R2_WIN_JOB_BAD_LENGTH);
        return 0;
    }
    return 1;
}
#define R2_JOB_U32(dst, src) do { (dst).value = (uint32_t)(src); \
    (dst).state = R2_WIN_JOB_FIELD_VALID; } while (0)
#define R2_JOB_U64(dst, src) do { (dst).value = (uint64_t)(src); \
    (dst).state = R2_WIN_JOB_FIELD_VALID; } while (0)
#define R2_JOB_I64(dst, src) do { (dst).value = (int64_t)(src); \
    (dst).state = R2_WIN_JOB_FIELD_VALID; } while (0)
#define R2_JOB_FAILED(dst) ((dst).state = R2_WIN_JOB_FIELD_FAILED)

static int r2_job_read_limits(struct r2_win_job_raw_snapshot_v1 *s)
{
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    JOBOBJECT_CPU_RATE_CONTROL_INFORMATION cpu = {0};
    if (!r2_job_query_native(JobObjectExtendedLimitInformation, &limits,
            (DWORD)sizeof(limits), R2_WIN_JOB_OP_QUERY_LIMITS)) {
        s->limits_readback_state = R2_WIN_JOB_FIELD_FAILED;
        R2_JOB_FAILED(s->limit_flags); R2_JOB_FAILED(s->active_process_limit);
        R2_JOB_FAILED(s->affinity); R2_JOB_FAILED(s->job_commit_limit);
        R2_JOB_FAILED(s->process_commit_limit);
        R2_JOB_FAILED(s->peak_process_commit); R2_JOB_FAILED(s->peak_job_commit);
        return 0;
    }
    R2_JOB_U32(s->limit_flags, limits.BasicLimitInformation.LimitFlags);
    R2_JOB_U32(s->active_process_limit, limits.BasicLimitInformation.ActiveProcessLimit);
    R2_JOB_U64(s->affinity, limits.BasicLimitInformation.Affinity);
    R2_JOB_U64(s->job_commit_limit, limits.JobMemoryLimit);
    R2_JOB_U64(s->process_commit_limit, limits.ProcessMemoryLimit);
    R2_JOB_U64(s->peak_process_commit, limits.PeakProcessMemoryUsed);
    R2_JOB_U64(s->peak_job_commit, limits.PeakJobMemoryUsed);
    if (limits.BasicLimitInformation.LimitFlags != R2_JOB_FIXED_FLAGS ||
        limits.BasicLimitInformation.ActiveProcessLimit != 4 ||
        limits.BasicLimitInformation.Affinity !=
            (ULONG_PTR)r2_job_report.selected_affinity.value ||
        limits.JobMemoryLimit != (SIZE_T)R2_JOB_FIXED_COMMIT ||
        limits.ProcessMemoryLimit != 0) {
        s->limits_readback_state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_invariant(R2_WIN_JOB_OP_QUERY_LIMITS, R2_WIN_JOB_LIMITS_CHANGED);
        return 0;
    }
    s->limits_readback_state = R2_WIN_JOB_FIELD_VALID;
    if (!r2_job_query_native(JobObjectCpuRateControlInformation, &cpu,
            (DWORD)sizeof(cpu), R2_WIN_JOB_OP_QUERY_CPU)) {
        s->cpu_readback_state = R2_WIN_JOB_FIELD_FAILED;
        R2_JOB_FAILED(s->cpu_control_flags); R2_JOB_FAILED(s->cpu_rate);
        return 0;
    }
    R2_JOB_U32(s->cpu_control_flags, cpu.ControlFlags);
    R2_JOB_U32(s->cpu_rate, cpu.CpuRate);
    DWORD rate = 20000 / r2_job_report.processor_count.value;
    if (rate > 10000) rate = 10000;
    if (cpu.ControlFlags != R2_JOB_FIXED_CPU_FLAGS || cpu.CpuRate != rate) {
        s->cpu_readback_state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_invariant(R2_WIN_JOB_OP_QUERY_CPU, R2_WIN_JOB_CPU_CHANGED);
        return 0;
    }
    s->cpu_readback_state = R2_WIN_JOB_FIELD_VALID;
    return 1;
}
static int r2_job_read_accounting(struct r2_win_job_raw_snapshot_v1 *s)
{
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION a = {0};
    if (!r2_job_query_native(JobObjectBasicAccountingInformation, &a,
            (DWORD)sizeof(a), R2_WIN_JOB_OP_QUERY_ACCOUNTING)) {
        s->accounting_state = R2_WIN_JOB_FIELD_FAILED;
        R2_JOB_FAILED(s->total_user_100ns); R2_JOB_FAILED(s->total_kernel_100ns);
        R2_JOB_FAILED(s->period_user_100ns); R2_JOB_FAILED(s->period_kernel_100ns);
        R2_JOB_FAILED(s->page_faults); R2_JOB_FAILED(s->total_processes);
        R2_JOB_FAILED(s->active_processes); R2_JOB_FAILED(s->terminated_by_limits);
        return 0;
    }
    R2_JOB_I64(s->total_user_100ns, a.TotalUserTime.QuadPart);
    R2_JOB_I64(s->total_kernel_100ns, a.TotalKernelTime.QuadPart);
    R2_JOB_I64(s->period_user_100ns, a.ThisPeriodTotalUserTime.QuadPart);
    R2_JOB_I64(s->period_kernel_100ns, a.ThisPeriodTotalKernelTime.QuadPart);
    R2_JOB_U32(s->page_faults, a.TotalPageFaultCount);
    R2_JOB_U32(s->total_processes, a.TotalProcesses);
    R2_JOB_U32(s->active_processes, a.ActiveProcesses);
    R2_JOB_U32(s->terminated_by_limits, a.TotalTerminatedProcesses);
    if (a.TotalUserTime.QuadPart < 0 || a.TotalKernelTime.QuadPart < 0 ||
        a.ThisPeriodTotalUserTime.QuadPart < 0 ||
        a.ThisPeriodTotalKernelTime.QuadPart < 0) {
        s->accounting_state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_invariant(R2_WIN_JOB_OP_QUERY_ACCOUNTING, R2_WIN_JOB_NEGATIVE_ACCOUNTING);
        return 0;
    }
    s->accounting_state = R2_WIN_JOB_FIELD_VALID;
    return 1;
}

enum r2_win_job_raw_status route2_win_raw_job_capsule_create_fixed_v1(void)
{
    if (!r2_job_enter()) return R2_WIN_JOB_RAW_BUSY;
    if (!r2_job_mutable()) return r2_job_leave(r2_job_refused_status());
    if (r2_job_report.lifecycle != R2_WIN_JOB_NEW) {
        r2_job_invariant(R2_WIN_JOB_OP_STATE, R2_WIN_JOB_BAD_LIFECYCLE);
        return r2_job_leave(r2_job_status());
    }
    /* Direct native store retains successful acquisition before any caller
     * return/conversion. No owner can recreate or expose this raw HANDLE.
     */
    r2_job_original = CreateJobObjectW(NULL, NULL);
    if (r2_job_original == NULL) {
        DWORD error = GetLastError();
        r2_job_report.job_acquire_state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_api_fault(R2_WIN_JOB_OP_CREATE, error);
        return r2_job_leave(r2_job_status());
    }
    r2_job_report.job_acquire_state = R2_WIN_JOB_FIELD_VALID;
    r2_job_report.lifecycle = R2_WIN_JOB_ORIGINAL_HELD;

    WORD groups = GetActiveProcessorGroupCount();
    if (groups == 0) {
        R2_JOB_FAILED(r2_job_report.processor_groups);
        /* Documented zero failure supplies no GetLastError contract. */
        r2_job_fault(R2_WIN_JOB_OP_GROUPS, R2_WIN_JOB_FAULT_API_NO_ERROR,
                     0, 0, R2_WIN_JOB_RAW_API_FAILED);
        return r2_job_leave(r2_job_status());
    }
    R2_JOB_U32(r2_job_report.processor_groups, groups);
    DWORD count = GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
    if (count == 0) {
        DWORD error = GetLastError();
        R2_JOB_FAILED(r2_job_report.processor_count);
        r2_job_api_fault(R2_WIN_JOB_OP_COUNT, error);
        return r2_job_leave(r2_job_status());
    }
    R2_JOB_U32(r2_job_report.processor_count, count);
    if (groups != 1 || count > sizeof(DWORD_PTR) * 8) {
        r2_job_invariant(R2_WIN_JOB_OP_COUNT, R2_WIN_JOB_BAD_TOPOLOGY);
        return r2_job_leave(r2_job_status());
    }
    DWORD_PTR allowed, system;
    if (!GetProcessAffinityMask(GetCurrentProcess(), &allowed, &system)) {
        DWORD error = GetLastError();
        R2_JOB_FAILED(r2_job_report.allowed_affinity);
        R2_JOB_FAILED(r2_job_report.system_affinity);
        r2_job_api_fault(R2_WIN_JOB_OP_AFFINITY, error);
        return r2_job_leave(r2_job_status());
    }
    R2_JOB_U64(r2_job_report.allowed_affinity, allowed);
    R2_JOB_U64(r2_job_report.system_affinity, system);
    DWORD bits = 0;
    for (DWORD_PTR rest = system; rest != 0; rest &= rest - 1) ++bits;
    if (allowed == 0 || (allowed & ~system) != 0 || bits != count) {
        r2_job_invariant(R2_WIN_JOB_OP_AFFINITY, R2_WIN_JOB_BAD_TOPOLOGY);
        return r2_job_leave(r2_job_status());
    }
    DWORD_PTR first = allowed & ((DWORD_PTR)0 - allowed);
    DWORD_PTR rest = allowed ^ first;
    DWORD_PTR selected = first | (rest & ((DWORD_PTR)0 - rest));
    R2_JOB_U64(r2_job_report.selected_affinity, selected);

    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    JOBOBJECT_CPU_RATE_CONTROL_INFORMATION cpu = {0};
    limits.BasicLimitInformation.LimitFlags = R2_JOB_FIXED_FLAGS;
    limits.BasicLimitInformation.ActiveProcessLimit = 4;
    limits.BasicLimitInformation.Affinity = (ULONG_PTR)selected;
    limits.JobMemoryLimit = (SIZE_T)R2_JOB_FIXED_COMMIT;
    cpu.ControlFlags = R2_JOB_FIXED_CPU_FLAGS;
    cpu.CpuRate = 20000 / count;
    if (cpu.CpuRate > 10000) cpu.CpuRate = 10000;
    if (cpu.CpuRate == 0) {
        r2_job_invariant(R2_WIN_JOB_OP_SET_CPU, R2_WIN_JOB_BAD_TOPOLOGY);
        return r2_job_leave(r2_job_status());
    }
    if (!SetInformationJobObject(r2_job_original, JobObjectExtendedLimitInformation,
                                 &limits, (DWORD)sizeof(limits))) {
        DWORD error = GetLastError();
        r2_job_report.set_limits_state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_api_fault(R2_WIN_JOB_OP_SET_LIMITS, error);
        return r2_job_leave(r2_job_status());
    }
    r2_job_report.set_limits_state = R2_WIN_JOB_FIELD_VALID;
    if (!SetInformationJobObject(r2_job_original, JobObjectCpuRateControlInformation,
                                 &cpu, (DWORD)sizeof(cpu))) {
        DWORD error = GetLastError();
        r2_job_report.set_cpu_state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_api_fault(R2_WIN_JOB_OP_SET_CPU, error);
        return r2_job_leave(r2_job_status());
    }
    r2_job_report.set_cpu_state = R2_WIN_JOB_FIELD_VALID;
    if (!r2_job_read_limits(&r2_job_report.configured))
        return r2_job_leave(r2_job_status());
    r2_job_report.lifecycle = R2_WIN_JOB_LIMITS_READBACK;
    r2_job_report.status = R2_WIN_JOB_RAW_OK;
    return r2_job_leave(R2_WIN_JOB_RAW_OK);
}

static int r2_job_live_poll(struct r2_win_job_raw_u32_v1 *field, uint32_t op)
{
    DWORD wait = WaitForSingleObject(r2_job_duplicate, 0);
    if (wait == WAIT_FAILED) {
        DWORD error = GetLastError();
        field->value = (uint32_t)wait;
        field->state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_api_fault(op, error);
        return 0;
    }
    R2_JOB_U32(*field, wait);
    if (wait == WAIT_OBJECT_0) {
        r2_job_fault(op, R2_WIN_JOB_FAULT_INVARIANT,
                     R2_WIN_JOB_EXIT_OBSERVED, 0, R2_WIN_JOB_RAW_EXIT_RACED);
        return 0;
    }
    if (wait != WAIT_TIMEOUT) {
        field->state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_invariant(op, R2_WIN_JOB_BAD_WAIT);
        return 0;
    }
    return 1;
}
static int r2_job_creation(struct r2_win_job_raw_u64_v1 *field, uint32_t op)
{
    FILETIME creation, exit_time, kernel, user;
    if (!GetProcessTimes(r2_job_duplicate, &creation, &exit_time, &kernel, &user)) {
        DWORD error = GetLastError();
        field->state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_api_fault(op, error);
        return 0;
    }
    /* Only defined creation is read; live exit output is never consumed. */
    R2_JOB_U64(*field, ((uint64_t)creation.dwHighDateTime << 32) |
                       creation.dwLowDateTime);
    return 1;
}

enum r2_win_job_raw_status route2_win_raw_job_capsule_assign_borrowed_v1(
    uintptr_t borrowed_process)
{
    if (!r2_job_enter()) return R2_WIN_JOB_RAW_BUSY;
    if (!r2_job_mutable()) return r2_job_leave(r2_job_refused_status());
    if (r2_job_report.lifecycle != R2_WIN_JOB_LIMITS_READBACK ||
        r2_job_report.assignment_attempted) {
        r2_job_invariant(R2_WIN_JOB_OP_STATE, R2_WIN_JOB_BAD_LIFECYCLE);
        return r2_job_leave(r2_job_status());
    }
    r2_job_report.assignment_attempted = 1;
    HANDLE borrowed = (HANDLE)borrowed_process;
    HANDLE current = GetCurrentProcess();
    if (borrowed == NULL || borrowed == INVALID_HANDLE_VALUE || borrowed == current) {
        r2_job_fault(R2_WIN_JOB_OP_BORROWED_PID, R2_WIN_JOB_FAULT_ARGUMENT,
                     R2_WIN_JOB_NULL_OR_PSEUDO, 0, R2_WIN_JOB_RAW_BAD_ARGUMENT);
        return r2_job_leave(r2_job_status());
    }
    DWORD pid = GetProcessId(borrowed);
    if (pid == 0) {
        DWORD error = GetLastError();
        R2_JOB_FAILED(r2_job_report.borrowed_pid);
        r2_job_api_fault(R2_WIN_JOB_OP_BORROWED_PID, error);
        return r2_job_leave(r2_job_status());
    }
    R2_JOB_U32(r2_job_report.borrowed_pid, pid);
    DWORD self = GetProcessId(current);
    if (self == 0) {
        DWORD error = GetLastError();
        R2_JOB_FAILED(r2_job_report.current_pid);
        r2_job_api_fault(R2_WIN_JOB_OP_SELF_PID, error);
        return r2_job_leave(r2_job_status());
    }
    R2_JOB_U32(r2_job_report.current_pid, self);
    if (pid == self) {
        /* Real self HANDLE is also unsafe: last Job close can kill this
         * caller before its own close/report function has returned.
         */
        r2_job_fault(R2_WIN_JOB_OP_SELF_PID, R2_WIN_JOB_FAULT_ARGUMENT,
                     R2_WIN_JOB_SELF_PROCESS, 0, R2_WIN_JOB_RAW_BAD_ARGUMENT);
        return r2_job_leave(r2_job_status());
    }
    HANDLE duplicate;
    if (!DuplicateHandle(current, borrowed, current, &duplicate,
                         0, FALSE, DUPLICATE_SAME_ACCESS)) {
        DWORD error = GetLastError();
        r2_job_report.duplicate_acquire_state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_api_fault(R2_WIN_JOB_OP_DUPLICATE, error);
        /* Failed output undefined, never read, retained or closed. */
        return r2_job_leave(r2_job_status());
    }
    r2_job_duplicate = duplicate;
    r2_job_report.duplicate_acquire_state = R2_WIN_JOB_FIELD_VALID;
    pid = GetProcessId(r2_job_duplicate);
    if (pid == 0) {
        DWORD error = GetLastError();
        R2_JOB_FAILED(r2_job_report.duplicate_pid_before);
        r2_job_api_fault(R2_WIN_JOB_OP_PID_BEFORE, error);
        return r2_job_leave(r2_job_status());
    }
    R2_JOB_U32(r2_job_report.duplicate_pid_before, pid);
    if (pid != r2_job_report.borrowed_pid.value) {
        r2_job_invariant(R2_WIN_JOB_OP_PID_BEFORE, R2_WIN_JOB_PID_CHANGED);
        return r2_job_leave(r2_job_status());
    }
    if (!r2_job_live_poll(&r2_job_report.wait_before, R2_WIN_JOB_OP_WAIT_BEFORE) ||
        !r2_job_creation(&r2_job_report.creation_before_100ns, R2_WIN_JOB_OP_TIMES_BEFORE))
        return r2_job_leave(r2_job_status());
    if (!AssignProcessToJobObject(r2_job_original, r2_job_duplicate)) {
        DWORD error = GetLastError();
        r2_job_report.assign_state = R2_WIN_JOB_FIELD_FAILED;
        r2_job_api_fault(R2_WIN_JOB_OP_ASSIGN, error);
        /* Failure may terminate process. No rollback/normal-exit claim;
         * retain successful duplicate and original Job for once-cleanup.
         */
        return r2_job_leave(r2_job_status());
    }
    r2_job_report.assign_state = R2_WIN_JOB_FIELD_VALID;
    BOOL member;
    if (!IsProcessInJob(r2_job_duplicate, r2_job_original, &member)) {
        DWORD error = GetLastError();
        R2_JOB_FAILED(r2_job_report.membership);
        r2_job_api_fault(R2_WIN_JOB_OP_MEMBERSHIP, error);
        return r2_job_leave(r2_job_status());
    }
    R2_JOB_U32(r2_job_report.membership, member);
    if (member != TRUE) {
        r2_job_invariant(R2_WIN_JOB_OP_MEMBERSHIP, R2_WIN_JOB_MEMBERSHIP_ABSENT);
        return r2_job_leave(r2_job_status());
    }
    r2_job_report.latest_query = (struct r2_win_job_raw_snapshot_v1){0};
    if (!r2_job_read_limits(&r2_job_report.latest_query))
        return r2_job_leave(r2_job_status());
    pid = GetProcessId(r2_job_duplicate);
    if (pid == 0) {
        DWORD error = GetLastError();
        R2_JOB_FAILED(r2_job_report.duplicate_pid_after);
        r2_job_api_fault(R2_WIN_JOB_OP_PID_AFTER, error);
        return r2_job_leave(r2_job_status());
    }
    R2_JOB_U32(r2_job_report.duplicate_pid_after, pid);
    if (pid != r2_job_report.duplicate_pid_before.value) {
        r2_job_invariant(R2_WIN_JOB_OP_PID_AFTER, R2_WIN_JOB_PID_CHANGED);
        return r2_job_leave(r2_job_status());
    }
    if (!r2_job_creation(&r2_job_report.creation_after_100ns, R2_WIN_JOB_OP_TIMES_AFTER))
        return r2_job_leave(r2_job_status());
    if (r2_job_report.creation_after_100ns.value !=
        r2_job_report.creation_before_100ns.value) {
        r2_job_invariant(R2_WIN_JOB_OP_TIMES_AFTER, R2_WIN_JOB_CREATION_CHANGED);
        return r2_job_leave(r2_job_status());
    }
    if (!r2_job_live_poll(&r2_job_report.wait_after, R2_WIN_JOB_OP_WAIT_AFTER))
        return r2_job_leave(r2_job_status());
    r2_job_report.lifecycle = R2_WIN_JOB_PROCESS_ASSIGNED;
    r2_job_report.status = R2_WIN_JOB_RAW_OK;
    return r2_job_leave(R2_WIN_JOB_RAW_OK);
}

enum r2_win_job_raw_status route2_win_raw_job_capsule_query_v1(void)
{
    if (!r2_job_enter()) return R2_WIN_JOB_RAW_BUSY;
    if (!r2_job_mutable()) return r2_job_leave(r2_job_refused_status());
    if (r2_job_report.lifecycle != R2_WIN_JOB_LIMITS_READBACK &&
        r2_job_report.lifecycle != R2_WIN_JOB_PROCESS_ASSIGNED) {
        r2_job_invariant(R2_WIN_JOB_OP_STATE, R2_WIN_JOB_BAD_LIFECYCLE);
        return r2_job_leave(r2_job_status());
    }
    /* Latest attempt only; configured acquisition readback stays preserved.
     * Successful zero counters are native Job facts, never complete scope.
     */
    r2_job_report.latest_query = (struct r2_win_job_raw_snapshot_v1){0};
    if (!r2_job_read_limits(&r2_job_report.latest_query) ||
        !r2_job_read_accounting(&r2_job_report.latest_query))
        return r2_job_leave(r2_job_status());
    r2_job_report.status = R2_WIN_JOB_RAW_OK;
    return r2_job_leave(R2_WIN_JOB_RAW_OK);
}

enum r2_win_job_raw_status route2_win_raw_job_capsule_close_once_v1(void)
{
    if (!r2_job_enter()) return R2_WIN_JOB_RAW_BUSY;
    if (r2_job_report.cleanup_attempted ||
        r2_job_report.lifecycle == R2_WIN_JOB_HANDLES_CONSUMED)
        return r2_job_leave(R2_WIN_JOB_RAW_BAD_STATE);

    HANDLE process = r2_job_duplicate;
    HANDLE job = r2_job_original;
    /* Consume ALL acquired ownership before ANY close; never reopen/retry.
     * Close failure may leave resource open: consumed is not released.
     */
    r2_job_duplicate = NULL;
    r2_job_original = NULL;
    r2_job_report.cleanup_attempted = 1;
    r2_job_report.duplicate_consumed = process != NULL;
    r2_job_report.job_consumed = job != NULL;
    r2_job_report.lifecycle = R2_WIN_JOB_HANDLES_CONSUMED;
    if (process != NULL) {
        if (!CloseHandle(process)) {
            DWORD error = GetLastError();
            r2_job_report.duplicate_close_state = R2_WIN_JOB_FIELD_FAILED;
            r2_job_api_fault(R2_WIN_JOB_OP_CLOSE_PROCESS, error);
        } else r2_job_report.duplicate_close_state = R2_WIN_JOB_FIELD_VALID;
    }
    /* Always attempt the later Job close, even after process-close failure. */
    if (job != NULL) {
        if (!CloseHandle(job)) {
            DWORD error = GetLastError();
            r2_job_report.job_close_state = R2_WIN_JOB_FIELD_FAILED;
            r2_job_api_fault(R2_WIN_JOB_OP_CLOSE_JOB, error);
        } else r2_job_report.job_close_state = R2_WIN_JOB_FIELD_VALID;
    }
    if (!r2_job_report.poisoned) r2_job_report.status = R2_WIN_JOB_RAW_OK;
    return r2_job_leave(r2_job_status());
}

enum r2_win_job_raw_status route2_win_raw_job_capsule_copy_report_v1(
    struct r2_win_job_raw_report_v1 *out, size_t size)
{
    if (out == NULL || size != sizeof(*out)) return R2_WIN_JOB_RAW_BAD_ARGUMENT;
    if (!r2_job_enter()) return R2_WIN_JOB_RAW_BUSY;
    /* Caller guarantees accessible/exclusive native memory; nonNULL alone
     * cannot establish ownership. No caller pointer becomes capsule authority.
     */
    *out = r2_job_report;
    return r2_job_leave(R2_WIN_JOB_RAW_OK);
}
#undef R2_JOB_FIXED_FLAGS
#undef R2_JOB_FIXED_CPU_FLAGS
#undef R2_JOB_FIXED_COMMIT
#undef R2_JOB_U32
#undef R2_JOB_U64
#undef R2_JOB_I64
#undef R2_JOB_FAILED
#endif

#if defined(R2_TARGET_LINUX_START)
/* C03 independent bounded parser; no original capture/producer is supplied. */
_Static_assert(sizeof(struct r2_linux_memavailable_parse_v1) == 32,
               "MemAvailable parser record must be 32 bytes");
_Static_assert(_Alignof(struct r2_linux_memavailable_parse_v1) == 8,
               "MemAvailable parser record must align to 8 bytes");
_Static_assert(offsetof(struct r2_linux_memavailable_parse_v1, abi) == 0 &&
               offsetof(struct r2_linux_memavailable_parse_v1, size) == 4 &&
               offsetof(struct r2_linux_memavailable_parse_v1, status) == 8 &&
               offsetof(struct r2_linux_memavailable_parse_v1, value_valid) == 12 &&
               offsetof(struct r2_linux_memavailable_parse_v1, memavailable_kib) == 16 &&
               offsetof(struct r2_linux_memavailable_parse_v1, memavailable_bytes) == 24,
               "MemAvailable parser record offsets changed");
_Static_assert(sizeof(size_t) == 8 && sizeof(uintptr_t) == 8,
               "MemAvailable parser requires the existing LP64 target");

static uint32_t r2_linux_meminfo_result_v1(
    struct r2_linux_memavailable_parse_v1 *out, uint32_t status, uint64_t kib)
{
    uint32_t valid = status == R2_LINUX_MEMINFO_PARSED;
    out->abi = 1;
    out->size = 32;
    out->status = status;
    out->value_valid = valid;
    out->memavailable_kib = valid ? kib : 0;
    out->memavailable_bytes = valid ? kib * UINT64_C(1024) : 0;
    return status;
}

/* Every input dereference passes this length/line/ASCII check first. */
static uint32_t r2_linux_meminfo_peek_v1(
    const uint8_t *bytes, size_t length, size_t cursor, size_t line_start,
    uint8_t *ch)
{
    if (cursor >= length) {
        return R2_LINUX_MEMINFO_TRUNCATED;
    }
    if (cursor - line_start >= R2_LINUX_MEMINFO_LINE_MAX_BYTES) {
        return R2_LINUX_MEMINFO_LINE_TOO_LONG;
    }
    *ch = bytes[cursor];
    if (*ch != '\t' && *ch != '\n' && (*ch < 32 || *ch > 126)) {
        return R2_LINUX_MEMINFO_INVALID_BYTE;
    }
    return R2_LINUX_MEMINFO_PARSED;
}

static int r2_linux_meminfo_alpha_v1(uint8_t ch)
{
    return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z');
}

static int r2_linux_meminfo_digit_v1(uint8_t ch)
{
    return ch >= '0' && ch <= '9';
}

static int r2_linux_meminfo_hspace_v1(uint8_t ch)
{
    return ch == ' ' || ch == '\t';
}

uint32_t route2_linux_parse_memavailable_v1(
    const uint8_t *bytes, size_t length,
    struct r2_linux_memavailable_parse_v1 *out, size_t out_size)
{
    const uint8_t target[] = "MemAvailable";
    uintptr_t input_first, input_last, output_first, output_last;
    size_t cursor = 0;
    uint64_t found_kib = 0;
    int found = 0;

    if (out == NULL || out_size != sizeof(*out)) {
        return R2_LINUX_MEMINFO_BAD_ARGUMENT;
    }
    output_first = (uintptr_t)out;
    if (output_first % _Alignof(struct r2_linux_memavailable_parse_v1) != 0 ||
        output_first > UINTPTR_MAX - (sizeof(*out) - 1)) {
        return R2_LINUX_MEMINFO_BAD_ARGUMENT;
    }
    output_last = output_first + (sizeof(*out) - 1);
    if (bytes == NULL || length == 0) {
        return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_BAD_ARGUMENT, 0);
    }
    input_first = (uintptr_t)bytes;
    if (length - 1 > UINTPTR_MAX - input_first) {
        return R2_LINUX_MEMINFO_BAD_ARGUMENT;
    }
    input_last = input_first + (length - 1);
    if (input_first <= output_last && output_first <= input_last) {
        return R2_LINUX_MEMINFO_BAD_ARGUMENT;
    }
    if (length > R2_LINUX_MEMINFO_INPUT_MAX_BYTES) {
        return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_INPUT_TOO_LARGE, 0);
    }

    while (cursor < length) {
        size_t line_start = cursor, key_start = cursor, key_length, index;
        uint32_t status;
        uint64_t value = 0;
        unsigned int digits = 0;
        uint8_t ch;
        int is_target, has_unit = 0;

        status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
        if (status != R2_LINUX_MEMINFO_PARSED) {
            return r2_linux_meminfo_result_v1(out, status, 0);
        }
        if (!r2_linux_meminfo_alpha_v1(ch)) {
            return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
        }
        while (r2_linux_meminfo_alpha_v1(ch) || r2_linux_meminfo_digit_v1(ch) ||
               ch == '_' || ch == '(' || ch == ')') {
            if (cursor - key_start >= R2_LINUX_MEMINFO_KEY_MAX_BYTES) {
                return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
            }
            ++cursor;
            status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
            if (status != R2_LINUX_MEMINFO_PARSED) {
                return r2_linux_meminfo_result_v1(out, status, 0);
            }
        }
        if (ch != ':') {
            return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
        }
        key_length = cursor - key_start;
        is_target = key_length == sizeof(target) - 1;
        for (index = 0; is_target && index < key_length; ++index) {
            if (bytes[key_start + index] != target[index]) {
                is_target = 0;
            }
        }
        if (is_target && found) {
            return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_DUPLICATE_MEMAVAILABLE, 0);
        }
        ++cursor;
        status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
        if (status != R2_LINUX_MEMINFO_PARSED) {
            return r2_linux_meminfo_result_v1(out, status, 0);
        }
        if (!r2_linux_meminfo_hspace_v1(ch)) {
            return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
        }
        do {
            ++cursor;
            status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
            if (status != R2_LINUX_MEMINFO_PARSED) {
                return r2_linux_meminfo_result_v1(out, status, 0);
            }
        } while (r2_linux_meminfo_hspace_v1(ch));
        if (!r2_linux_meminfo_digit_v1(ch)) {
            return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
        }
        do {
            uint64_t digit = (uint64_t)(ch - '0');
            if (digits == R2_LINUX_MEMINFO_DECIMAL_MAX_BYTES) {
                return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
            }
            if (value > (UINT64_MAX - digit) / UINT64_C(10)) {
                return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_VALUE_OUT_OF_RANGE, 0);
            }
            value = value * UINT64_C(10) + digit;
            ++digits;
            ++cursor;
            status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
            if (status != R2_LINUX_MEMINFO_PARSED) {
                return r2_linux_meminfo_result_v1(out, status, 0);
            }
        } while (r2_linux_meminfo_digit_v1(ch));
        if (ch != '\n' && !r2_linux_meminfo_hspace_v1(ch)) {
            return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
        }
        while (r2_linux_meminfo_hspace_v1(ch)) {
            ++cursor;
            status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
            if (status != R2_LINUX_MEMINFO_PARSED) {
                return r2_linux_meminfo_result_v1(out, status, 0);
            }
        }
        if (ch != '\n') {
            if (ch != 'k') {
                return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
            }
            ++cursor;
            status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
            if (status != R2_LINUX_MEMINFO_PARSED) {
                return r2_linux_meminfo_result_v1(out, status, 0);
            }
            if (ch != 'B') {
                return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
            }
            ++cursor;
            status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
            if (status != R2_LINUX_MEMINFO_PARSED) {
                return r2_linux_meminfo_result_v1(out, status, 0);
            }
            while (r2_linux_meminfo_hspace_v1(ch)) {
                ++cursor;
                status = r2_linux_meminfo_peek_v1(bytes, length, cursor, line_start, &ch);
                if (status != R2_LINUX_MEMINFO_PARSED) {
                    return r2_linux_meminfo_result_v1(out, status, 0);
                }
            }
            if (ch != '\n') {
                return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
            }
            has_unit = 1;
        }
        if (is_target) {
            if (!has_unit) {
                return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_MALFORMED_LINE, 0);
            }
            if (value > UINT64_MAX / UINT64_C(1024)) {
                return r2_linux_meminfo_result_v1(out, R2_LINUX_MEMINFO_VALUE_OUT_OF_RANGE, 0);
            }
            found = 1;
            found_kib = value;
        }
        ++cursor; /* Consume the checked LF; the next line begins here. */
    }
    return r2_linux_meminfo_result_v1(out,
        found ? R2_LINUX_MEMINFO_PARSED : R2_LINUX_MEMINFO_MISSING_MEMAVAILABLE,
        found_kib);
}
#endif

#if defined(R2_TARGET_LINUX_START)
/* C03 production raw capture; no entry point, bootstrap or admission body. */
#include <fcntl.h>
#include <linux/magic.h>
#include <linux/openat2.h>
#include <stdatomic.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/vfs.h>
#include <time.h>

#if !defined(__STDC_VERSION__) || __STDC_VERSION__ < 201112L
#error "C03 capture requires C11 atomics and fixed native layout"
#endif
#if !defined(SYS_openat2)
#error "Actual target headers must provide SYS_openat2; no fallback"
#endif
#if !defined(PROC_SUPER_MAGIC) || !defined(RESOLVE_NO_XDEV) || !defined(RESOLVE_NO_SYMLINKS) || !defined(RESOLVE_NO_MAGICLINKS)
#error "Actual target UAPI must provide procfs and strict openat2 constants"
#endif
_Static_assert(sizeof(struct r2_linux_start_capture_v1) == 256 &&
               _Alignof(struct r2_linux_start_capture_v1) == 8,
               "Linux capture record must be 256 bytes aligned to 8");
#define R2_LSC_OFFSET(FIELD, VALUE) \
    _Static_assert(offsetof(struct r2_linux_start_capture_v1, FIELD) == VALUE, \
                   "Linux capture offset changed: " #FIELD)
R2_LSC_OFFSET(abi, 0);
R2_LSC_OFFSET(size, 4);
R2_LSC_OFFSET(status, 8);
R2_LSC_OFFSET(sample_valid, 12);
R2_LSC_OFFSET(attempt_consumed, 16);
R2_LSC_OFFSET(valid_fields, 20);
R2_LSC_OFFSET(primary_attempts, 24);
R2_LSC_OFFSET(read_attempts, 28);
R2_LSC_OFFSET(bytes_read, 32);
R2_LSC_OFFSET(eof_seen, 36);
R2_LSC_OFFSET(parser_status, 40);
R2_LSC_OFFSET(source_kind, 44);
R2_LSC_OFFSET(primary_operation, 48);
R2_LSC_OFFSET(primary_kind, 52);
R2_LSC_OFFSET(primary_code, 56);
R2_LSC_OFFSET(primary_errno_valid, 60);
R2_LSC_OFFSET(primary_errno, 64);
R2_LSC_OFFSET(meminfo_close_errno, 68);
R2_LSC_OFFSET(proc_close_errno, 72);
R2_LSC_OFFSET(end_clock_errno, 76);
R2_LSC_OFFSET(meminfo_close_state, 80);
R2_LSC_OFFSET(proc_close_state, 84);
R2_LSC_OFFSET(end_clock_state, 88);
R2_LSC_OFFSET(value_valid, 92);
R2_LSC_OFFSET(monotonic_begin_ns, 96);
R2_LSC_OFFSET(monotonic_end_ns, 104);
R2_LSC_OFFSET(memavailable_kib, 112);
R2_LSC_OFFSET(memavailable_bytes, 120);
R2_LSC_OFFSET(proc_dev, 128);
R2_LSC_OFFSET(proc_ino, 136);
R2_LSC_OFFSET(meminfo_dev, 144);
R2_LSC_OFFSET(meminfo_ino, 152);
R2_LSC_OFFSET(meminfo_size, 160);
R2_LSC_OFFSET(proc_fs_type, 168);
R2_LSC_OFFSET(meminfo_fs_type, 176);
R2_LSC_OFFSET(proc_fsid, 184);
R2_LSC_OFFSET(meminfo_fsid, 192);
R2_LSC_OFFSET(proc_mode, 200);
R2_LSC_OFFSET(proc_uid, 204);
R2_LSC_OFFSET(meminfo_mode, 208);
R2_LSC_OFFSET(meminfo_uid, 212);
R2_LSC_OFFSET(proc_nlink, 216);
R2_LSC_OFFSET(meminfo_nlink, 224);
R2_LSC_OFFSET(proc_gid, 232);
R2_LSC_OFFSET(meminfo_gid, 236);
R2_LSC_OFFSET(post_stat_state, 240);
R2_LSC_OFFSET(end_clock_attempts, 244);
R2_LSC_OFFSET(end_clock_fault_kind, 248);
R2_LSC_OFFSET(end_clock_fault_code, 252);
#undef R2_LSC_OFFSET
_Static_assert(sizeof(time_t) == 8 && (time_t)-1 < (time_t)0 &&
               sizeof(((struct timespec *)0)->tv_nsec) == 8,
               "Linux capture requires reviewed signed LP64 clock fields");
_Static_assert(sizeof(dev_t) == 8 && sizeof(ino_t) == 8 &&
               sizeof(nlink_t) == 8 && sizeof(off_t) == 8 &&
               sizeof(mode_t) == 4 && sizeof(uid_t) == 4 && sizeof(gid_t) == 4,
               "Linux capture requires reviewed stat scalar widths");
_Static_assert(sizeof(((struct statfs *)0)->f_type) == 8 &&
               sizeof(((struct statfs *)0)->f_fsid) == 8,
               "Linux capture requires reviewed statfs scalar widths");
_Static_assert(sizeof(struct open_how) == 24 &&
               offsetof(struct open_how, flags) == 0 &&
               offsetof(struct open_how, mode) == 8 &&
               offsetof(struct open_how, resolve) == 16,
               "Linux capture openat2 UAPI layout changed");

/* Permanently set, including failures; no reset/copy/constructor interface.
 * This target is linked once into the original native start executable.
 */
static atomic_flag r2_linux_start_capture_consumed_v1 = ATOMIC_FLAG_INIT;

static void r2_lsc_fault_v1(struct r2_linux_start_capture_v1 *r,
    uint32_t status, uint32_t operation, uint32_t kind, uint32_t code,
    int native_error, uint32_t errno_valid)
{
    if (r->status != R2_LINUX_CAPTURE_UNKNOWN) return;
    r->status = status;
    r->primary_operation = operation;
    r->primary_kind = kind;
    r->primary_code = code;
    r->primary_errno = errno_valid ? native_error : 0;
    r->primary_errno_valid = errno_valid;
}

static int r2_lsc_attempt_v1(struct r2_linux_start_capture_v1 *r,
    uint32_t operation)
{
    if (r->primary_attempts >= R2_LINUX_CAPTURE_PRIMARY_ATTEMPT_MAX) {
        r2_lsc_fault_v1(r, R2_LINUX_CAPTURE_ATTEMPTS_EXHAUSTED, operation,
            R2_LINUX_CAPTURE_FAULT_BUDGET,
            R2_LINUX_CAPTURE_PRIMARY_ATTEMPT_MAX, 0, 0);
        return 0;
    }
    ++r->primary_attempts;
    return 1;
}

static int r2_lsc_clock_ns_v1(const struct timespec *ts, uint64_t *out)
{
    uint64_t sec, nsec;
    if (ts->tv_sec < 0 || ts->tv_nsec < 0 || ts->tv_nsec >= 1000000000L)
        return 0;
    sec = (uint64_t)ts->tv_sec;
    nsec = (uint64_t)ts->tv_nsec;
    if (sec > (UINT64_MAX - nsec) / UINT64_C(1000000000)) return 0;
    *out = sec * UINT64_C(1000000000) + nsec;
    return 1;
}

static int r2_lsc_same_stat_v1(const struct stat *before,
    const struct stat *after)
{
    return before->st_dev == after->st_dev &&
        before->st_ino == after->st_ino &&
        before->st_mode == after->st_mode &&
        before->st_nlink == after->st_nlink &&
        before->st_uid == after->st_uid && before->st_gid == after->st_gid &&
        before->st_rdev == after->st_rdev && before->st_size == after->st_size &&
        before->st_mtim.tv_sec == after->st_mtim.tv_sec &&
        before->st_mtim.tv_nsec == after->st_mtim.tv_nsec &&
        before->st_ctim.tv_sec == after->st_ctim.tv_sec &&
        before->st_ctim.tv_nsec == after->st_ctim.tv_nsec;
}

/* Consume ownership BEFORE one close; always run for every acquired fd.
 * Failed close errno (even zero) is distinct from an earlier primary fault.
 */
static void r2_lsc_close_v1(struct r2_linux_start_capture_v1 *r, int *owned,
    uint32_t operation, uint32_t *state, int32_t *saved_errno)
{
    int fd = *owned;
    if (fd < 0) return;
    *owned = -1;
    if (close(fd) == 0) {
        *state = R2_LINUX_CAPTURE_VALID;
    } else {
        int error = errno;
        *state = R2_LINUX_CAPTURE_FAILED;
        *saved_errno = error;
        r2_lsc_fault_v1(r, R2_LINUX_CAPTURE_CLEANUP_FAILED, operation,
            R2_LINUX_CAPTURE_FAULT_ERRNO, 0, error, 1);
    }
}

static void r2_lsc_end_clock_v1(struct r2_linux_start_capture_v1 *r)
{
    struct timespec ts = {0};
    uint64_t ns = 0;
    int result, error;
    r->end_clock_state = R2_LINUX_CAPTURE_FAILED;
    while (r->end_clock_attempts < R2_LINUX_CAPTURE_END_CLOCK_ATTEMPT_MAX) {
        ++r->end_clock_attempts;
        result = clock_gettime(CLOCK_MONOTONIC, &ts);
        if (result == 0) {
            if (!r2_lsc_clock_ns_v1(&ts, &ns)) {
                r->end_clock_fault_kind = R2_LINUX_CAPTURE_FAULT_INVARIANT;
                r->end_clock_fault_code = R2_LINUX_CAPTURE_BAD_CLOCK;
                break;
            }
            if ((r->valid_fields & R2_LINUX_CAPTURE_BEGIN_VALID) &&
                ns < r->monotonic_begin_ns) {
                r->end_clock_fault_kind = R2_LINUX_CAPTURE_FAULT_INVARIANT;
                r->end_clock_fault_code = R2_LINUX_CAPTURE_CLOCK_REGRESSED;
                break;
            }
            r->monotonic_end_ns = ns;
            r->valid_fields |= R2_LINUX_CAPTURE_END_VALID;
            r->end_clock_state = R2_LINUX_CAPTURE_VALID;
            return;
        }
        error = errno;
        if (result != -1) {
            r->end_clock_fault_kind = R2_LINUX_CAPTURE_FAULT_INVARIANT;
            r->end_clock_fault_code = R2_LINUX_CAPTURE_BAD_API_RESULT;
            break;
        }
        if (error != EINTR) {
            r->end_clock_errno = error;
            r->end_clock_fault_kind = R2_LINUX_CAPTURE_FAULT_ERRNO;
            break;
        }
        if (r->end_clock_attempts == R2_LINUX_CAPTURE_END_CLOCK_ATTEMPT_MAX) {
            r->end_clock_errno = error;
            r->end_clock_fault_kind = R2_LINUX_CAPTURE_FAULT_BUDGET;
            r->end_clock_fault_code = R2_LINUX_CAPTURE_END_CLOCK_ATTEMPT_MAX;
        }
    }
    r2_lsc_fault_v1(r,
        r->end_clock_fault_kind == R2_LINUX_CAPTURE_FAULT_BUDGET ?
            R2_LINUX_CAPTURE_ATTEMPTS_EXHAUSTED :
        r->end_clock_fault_kind == R2_LINUX_CAPTURE_FAULT_ERRNO ?
            R2_LINUX_CAPTURE_API_FAILED : R2_LINUX_CAPTURE_INVARIANT_FAILED,
        R2_LINUX_CAPTURE_OP_END_CLOCK, r->end_clock_fault_kind,
        r->end_clock_fault_code, r->end_clock_errno,
        r->end_clock_fault_kind == R2_LINUX_CAPTURE_FAULT_ERRNO ||
        r->end_clock_fault_kind == R2_LINUX_CAPTURE_FAULT_BUDGET);
}

/* A native result outside this API's success/-1 contract is rejected too.
 * Every EINTR returns to the SAME global call budget, never a reset budget.
 */
#define R2_LSC_TRY(OPERATION, EXPRESSION, SUCCESS) do { \
    for (;;) { \
        long r2_lsc_rc; \
        int r2_lsc_error; \
        if (!r2_lsc_attempt_v1(&r, (OPERATION))) goto cleanup; \
        r2_lsc_rc = (long)(EXPRESSION); \
        if (SUCCESS) break; \
        r2_lsc_error = errno; \
        if (r2_lsc_rc != -1) { \
            r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED, (OPERATION), \
                R2_LINUX_CAPTURE_FAULT_INVARIANT, \
                R2_LINUX_CAPTURE_BAD_API_RESULT, 0, 0); \
            goto cleanup; \
        } \
        if (r2_lsc_error != EINTR) { \
            r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_API_FAILED, (OPERATION), \
                R2_LINUX_CAPTURE_FAULT_ERRNO, 0, r2_lsc_error, 1); \
            goto cleanup; \
        } \
    } \
} while (0)

uint32_t route2_linux_start_capture_once_v1(
    struct r2_linux_start_capture_v1 *out, size_t out_size)
{
    struct r2_linux_start_capture_v1 r;
    struct r2_linux_memavailable_parse_v1 parsed;
    struct timespec begin = {0};
    struct stat proc_stat = {0}, meminfo_stat = {0}, post_stat = {0};
    struct statfs proc_fs = {0}, meminfo_fs = {0};
    struct open_how how = {0};
    uint8_t bytes[R2_LINUX_MEMINFO_INPUT_MAX_BYTES + 1u];
    uintptr_t output_first;
    size_t length = 0;
    int proc_fd = -1, meminfo_fd = -1;

    if (out == NULL || out_size != sizeof(*out))
        return R2_LINUX_CAPTURE_BAD_ARGUMENT;
    output_first = (uintptr_t)out;
    if (output_first % _Alignof(struct r2_linux_start_capture_v1) != 0 ||
        output_first > UINTPTR_MAX - (sizeof(*out) - 1u))
        return R2_LINUX_CAPTURE_BAD_ARGUMENT;

    memset(&r, 0, sizeof(r));
    memset(&parsed, 0, sizeof(parsed));
    r.abi = 1;
    r.size = sizeof(r);
    r.attempt_consumed = 1;
    if (atomic_flag_test_and_set_explicit(
            &r2_linux_start_capture_consumed_v1, memory_order_relaxed)) {
        r.status = R2_LINUX_CAPTURE_ALREADY_ATTEMPTED;
        memcpy(out, &r, sizeof(r));
        return r.status;
    }
    r.source_kind = R2_LINUX_CAPTURE_SOURCE_FIXED_PROC_MEMINFO;

    R2_LSC_TRY(R2_LINUX_CAPTURE_OP_BEGIN_CLOCK,
        clock_gettime(CLOCK_MONOTONIC, &begin), r2_lsc_rc == 0);
    if (!r2_lsc_clock_ns_v1(&begin, &r.monotonic_begin_ns)) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_BEGIN_CLOCK, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_BAD_CLOCK, 0, 0);
        goto cleanup;
    }
    r.valid_fields |= R2_LINUX_CAPTURE_BEGIN_VALID;

    how.flags = O_PATH | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW;
    how.resolve = RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS;
    R2_LSC_TRY(R2_LINUX_CAPTURE_OP_OPEN_PROC,
        proc_fd = (int)syscall(SYS_openat2, AT_FDCWD, "/proc", &how, sizeof(how)),
        r2_lsc_rc >= 0);
    R2_LSC_TRY(R2_LINUX_CAPTURE_OP_PROC_STATFS,
        fstatfs(proc_fd, &proc_fs), r2_lsc_rc == 0);
    r.proc_fs_type = proc_fs.f_type;
    memcpy(r.proc_fsid, &proc_fs.f_fsid, sizeof(r.proc_fsid));
    r.valid_fields |= R2_LINUX_CAPTURE_PROC_FS_VALID;
    if (proc_fs.f_type != PROC_SUPER_MAGIC) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_PROC_STATFS, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_NOT_PROCFS, 0, 0);
        goto cleanup;
    }
    R2_LSC_TRY(R2_LINUX_CAPTURE_OP_PROC_STAT,
        fstat(proc_fd, &proc_stat), r2_lsc_rc == 0);
    r.proc_dev = proc_stat.st_dev;
    r.proc_ino = proc_stat.st_ino;
    r.proc_mode = proc_stat.st_mode;
    r.proc_uid = proc_stat.st_uid;
    r.proc_gid = proc_stat.st_gid;
    r.proc_nlink = proc_stat.st_nlink;
    r.valid_fields |= R2_LINUX_CAPTURE_PROC_STAT_VALID;
    if (!S_ISDIR(proc_stat.st_mode)) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_PROC_STAT, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_NOT_DIRECTORY, 0, 0);
        goto cleanup;
    }

    how.flags = O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK;
    how.resolve = RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV;
    R2_LSC_TRY(R2_LINUX_CAPTURE_OP_OPEN_MEMINFO,
        meminfo_fd = (int)syscall(SYS_openat2, proc_fd, "meminfo", &how, sizeof(how)),
        r2_lsc_rc >= 0);
    R2_LSC_TRY(R2_LINUX_CAPTURE_OP_MEMINFO_STATFS,
        fstatfs(meminfo_fd, &meminfo_fs), r2_lsc_rc == 0);
    r.meminfo_fs_type = meminfo_fs.f_type;
    memcpy(r.meminfo_fsid, &meminfo_fs.f_fsid, sizeof(r.meminfo_fsid));
    r.valid_fields |= R2_LINUX_CAPTURE_MEMINFO_FS_VALID;
    if (meminfo_fs.f_type != PROC_SUPER_MAGIC) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_MEMINFO_STATFS, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_NOT_PROCFS, 0, 0);
        goto cleanup;
    }
    if (memcmp(&proc_fs.f_fsid, &meminfo_fs.f_fsid, sizeof(proc_fs.f_fsid)) != 0) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_MEMINFO_STATFS, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_SOURCE_ALIAS, 0, 0);
        goto cleanup;
    }
    R2_LSC_TRY(R2_LINUX_CAPTURE_OP_MEMINFO_STAT,
        fstat(meminfo_fd, &meminfo_stat), r2_lsc_rc == 0);
    r.meminfo_dev = meminfo_stat.st_dev;
    r.meminfo_ino = meminfo_stat.st_ino;
    r.meminfo_mode = meminfo_stat.st_mode;
    r.meminfo_uid = meminfo_stat.st_uid;
    r.meminfo_gid = meminfo_stat.st_gid;
    r.meminfo_nlink = meminfo_stat.st_nlink;
    r.meminfo_size = meminfo_stat.st_size;
    r.valid_fields |= R2_LINUX_CAPTURE_MEMINFO_STAT_VALID;
    if (!S_ISREG(meminfo_stat.st_mode)) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_MEMINFO_STAT, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_NOT_REGULAR, 0, 0);
        goto cleanup;
    }
    if (meminfo_stat.st_dev != proc_stat.st_dev ||
        meminfo_stat.st_ino == proc_stat.st_ino || meminfo_stat.st_nlink != 1) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_MEMINFO_STAT, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_SOURCE_ALIAS, 0, 0);
        goto cleanup;
    }
    if (meminfo_stat.st_size != 0) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_MEMINFO_STAT, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_NONZERO_PROC_SIZE, 0, 0);
        goto cleanup;
    }

    for (;;) {
        size_t remaining = sizeof(bytes) - length;
        ssize_t count;
        int error;
        if (!r2_lsc_attempt_v1(&r, R2_LINUX_CAPTURE_OP_READ)) goto cleanup;
        ++r.read_attempts;
        count = read(meminfo_fd, bytes + length, remaining);
        if (count < 0) {
            error = errno;
            if (count == -1 && error == EINTR) continue;
            r2_lsc_fault_v1(&r,
                count == -1 ? R2_LINUX_CAPTURE_API_FAILED :
                    R2_LINUX_CAPTURE_INVARIANT_FAILED,
                R2_LINUX_CAPTURE_OP_READ,
                count == -1 ? R2_LINUX_CAPTURE_FAULT_ERRNO :
                    R2_LINUX_CAPTURE_FAULT_INVARIANT,
                count == -1 ? 0 : R2_LINUX_CAPTURE_BAD_READ_RESULT,
                count == -1 ? error : 0, count == -1);
            goto cleanup;
        }
        if ((uint64_t)count > (uint64_t)remaining) {
            r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
                R2_LINUX_CAPTURE_OP_READ, R2_LINUX_CAPTURE_FAULT_INVARIANT,
                R2_LINUX_CAPTURE_BAD_READ_RESULT, 0, 0);
            goto cleanup;
        }
        if (count == 0) {
            r.eof_seen = 1;
            r.valid_fields |= R2_LINUX_CAPTURE_EOF_VALID;
            break;
        }
        length += (size_t)count;
        r.bytes_read = (uint32_t)length;
        if (length > R2_LINUX_MEMINFO_INPUT_MAX_BYTES) {
            r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INPUT_TOO_LARGE,
                R2_LINUX_CAPTURE_OP_READ, R2_LINUX_CAPTURE_FAULT_INVARIANT,
                R2_LINUX_CAPTURE_OVER_BOUND, 0, 0);
            goto cleanup;
        }
    }

    r.post_stat_state = R2_LINUX_CAPTURE_FAILED;
    R2_LSC_TRY(R2_LINUX_CAPTURE_OP_POST_STAT,
        fstat(meminfo_fd, &post_stat), r2_lsc_rc == 0);
    if (!r2_lsc_same_stat_v1(&meminfo_stat, &post_stat)) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_INVARIANT_FAILED,
            R2_LINUX_CAPTURE_OP_POST_STAT, R2_LINUX_CAPTURE_FAULT_INVARIANT,
            R2_LINUX_CAPTURE_IDENTITY_CHANGED, 0, 0);
        goto cleanup;
    }
    r.post_stat_state = R2_LINUX_CAPTURE_VALID;
    r.valid_fields |= R2_LINUX_CAPTURE_POST_STAT_VALID;
    r.parser_status = route2_linux_parse_memavailable_v1(
        bytes, length, &parsed, sizeof(parsed));
    r.valid_fields |= R2_LINUX_CAPTURE_PARSER_RESULT_VALID;
    if (r.parser_status != R2_LINUX_MEMINFO_PARSED || parsed.value_valid != 1) {
        r2_lsc_fault_v1(&r, R2_LINUX_CAPTURE_PARSE_FAILED,
            R2_LINUX_CAPTURE_OP_PARSE, R2_LINUX_CAPTURE_FAULT_PARSER,
            r.parser_status, 0, 0);
        goto cleanup;
    }
    /* Raw zero is deliberately retained and may be refused by admission later. */
    r.memavailable_kib = parsed.memavailable_kib;
    r.memavailable_bytes = parsed.memavailable_bytes;

cleanup:
    r2_lsc_close_v1(&r, &meminfo_fd, R2_LINUX_CAPTURE_OP_CLOSE_MEMINFO,
        &r.meminfo_close_state, &r.meminfo_close_errno);
    r2_lsc_close_v1(&r, &proc_fd, R2_LINUX_CAPTURE_OP_CLOSE_PROC,
        &r.proc_close_state, &r.proc_close_errno);
    r2_lsc_end_clock_v1(&r);
    if (r.status == R2_LINUX_CAPTURE_UNKNOWN) {
        r.status = R2_LINUX_CAPTURE_COMPLETE;
        r.sample_valid = 1;
        r.value_valid = 1;
    } else {
        r.memavailable_kib = 0;
        r.memavailable_bytes = 0;
    }
    memcpy(out, &r, sizeof(r));
    return r.status;
}
#undef R2_LSC_TRY
#endif

#if defined(R2_TARGET_WINDOWS_SEED)
/* C02 generic raw owned-child owner; original C02-A/B1/C03 bytes above are
 * preserved. This is a downstream primitive, not an installed seed/lease
 * verifier. Interlocked LONGs are naturally 32-bit aligned static objects.
 * Winnt.h InterlockedCompareExchange/Exchange are XP+ full-fence operations;
 * this component explicitly requires Win10 because JOB_LIST birth does.
 */
#if !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0A00
#error "C02 owned-child requires explicit Windows 10 JOB_LIST SDK target"
#endif
#if !defined(_WIN64) || !(defined(_M_X64) || defined(__x86_64__))
#error "C02 owned-child requires native Windows x64"
#endif
#ifndef PROC_THREAD_ATTRIBUTE_JOB_LIST
#error "Actual SDK must expose PROC_THREAD_ATTRIBUTE_JOB_LIST; no fallback"
#endif
#include <TlHelp32.h>
#include <limits.h>
#include <string.h>
#include <wchar.h>

_Static_assert(sizeof(LONG) == 4 && sizeof(WCHAR) == 2 && sizeof(void *) == 8,
    "owned-child requires native Win64 LLP64/UTF16 ABI");
_Static_assert(sizeof(struct r2_win_owned_text_v1) == 16 &&
    sizeof(struct r2_win_owned_spec_v1) == 112, "owned-child spec ABI");
_Static_assert(offsetof(struct r2_win_owned_spec_v1, application) == 48 &&
    offsetof(struct r2_win_owned_spec_v1, command_line) == 64 &&
    offsetof(struct r2_win_owned_spec_v1, current_directory) == 80 &&
    offsetof(struct r2_win_owned_spec_v1, environment) == 96, "text ABI offsets");
_Static_assert(R2_OWN_OP_CREATOR_WAIT < R2_WIN_OWNED_FAULT_CAPACITY,
    "one bounded first-fault slot per native operation");
_Static_assert(sizeof(struct r2_win_owned_report_v1) <= UINT32_MAX,
    "owned-child report size field");
_Static_assert(sizeof(STARTUPINFOEXW) == 112 && sizeof(PROCESS_INFORMATION) == 24,
    "owned-child Windows process ABI");
_Static_assert(sizeof(struct r2_win_owned_fault_v1) == 24 &&
    sizeof(struct r2_win_owned_handle_state_v1) == 16 &&
    sizeof(struct r2_win_job_raw_snapshot_v1) == 224 &&
    sizeof(struct r2_win_owned_report_v1) == 2736 &&
    offsetof(struct r2_win_owned_report_v1, faults) == 528 &&
    offsetof(struct r2_win_owned_report_v1, configured) == 2064 &&
    sizeof(struct r2_win_owned_abi_v1) == 48, "owned-child report ABI");

#define R2_OWN_FLAGS (JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_AFFINITY | \
    JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
#define R2_OWN_CPU_FLAGS (JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP)
#define R2_OWN_COMMIT (UINT64_C(4) * 1024 * 1024 * 1024)
#define R2_OWN_CREATE_FLAGS (CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | \
    EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW)
#define R2_OWN_ERROR_ARGUMENT 1u
#define R2_OWN_ERROR_WIN32 2u
#define R2_OWN_ERROR_INVARIANT 3u
#define R2_OWN_ERROR_NO_EXTENDED 4u
#define R2_OWN_BAD_VALUE 1u
#define R2_OWN_DEADLINE 2u
#define R2_OWN_IDENTITY 3u
#define R2_OWN_LENGTH 4u
#define R2_OWN_LIMIT_CHANGED 5u
#define R2_OWN_COUNT_CHANGED 6u
#define R2_OWN_SCAN_BOUND 7u
#define R2_OWN_WAIT_RESULT 8u

struct r2_own_private_v1 {
    HANDLE creator, job, process, thread, snapshot;
    HANDLE jobs[1];
    PROCESS_INFORMATION pi;
    STARTUPINFOEXW startup;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
    JOBOBJECT_CPU_RATE_CONTROL_INFORMATION cpu;
    union { max_align_t alignment; unsigned char bytes[R2_WIN_OWNED_ATTRIBUTE_CAPACITY]; } attributes;
    WCHAR application[R2_WIN_OWNED_TEXT_CAPACITY];
    WCHAR command[R2_WIN_OWNED_TEXT_CAPACITY];
    WCHAR directory[R2_WIN_OWNED_TEXT_CAPACITY];
    WCHAR environment[R2_WIN_OWNED_TEXT_CAPACITY];
    int deadline_bound, final_attempted;
};
static volatile LONG r2_own_guard_v1 = 0;
static volatile LONG r2_own_stop_v1 = 0;
static struct r2_own_private_v1 r2_own_v1;
static struct r2_win_owned_report_v1 r2_own_report_v1 = {
    .abi = R2_WIN_OWNED_ABI, .size = sizeof(struct r2_win_owned_report_v1),
    .thread_warning_limit = 4
};

static int r2_own_enter_v1(void)
{
    return InterlockedCompareExchange(&r2_own_guard_v1, 1, 0) == 0;
}
static int r2_own_stopped_v1(void)
{
    return InterlockedCompareExchange(&r2_own_stop_v1, 0, 0) != 0;
}
static uint32_t r2_own_leave_v1(uint32_t status)
{
    r2_own_report_v1.status = status;
    r2_own_report_v1.stop_new = (uint32_t)r2_own_stopped_v1();
    InterlockedExchange(&r2_own_guard_v1, 0);
    return status;
}
static int r2_own_range_v1(const void *p, size_t size, size_t alignment)
{
    uintptr_t address = (uintptr_t)p;
    return address != 0 && address % alignment == 0 && size <= UINTPTR_MAX - address;
}
static void r2_own_u32_v1(struct r2_win_job_raw_u32_v1 *out, uint32_t value)
{
    out->value = value; out->state = R2_WIN_JOB_FIELD_VALID;
}
static void r2_own_u64_v1(struct r2_win_job_raw_u64_v1 *out, uint64_t value)
{
    out->value = value; out->state = R2_WIN_JOB_FIELD_VALID; out->reserved = 0;
}
static void r2_own_i64_v1(struct r2_win_job_raw_i64_v1 *out, int64_t value)
{
    out->value = value; out->state = R2_WIN_JOB_FIELD_VALID; out->reserved = 0;
}
static uint64_t r2_own_filetime_v1(FILETIME value)
{
    return ((uint64_t)value.dwHighDateTime << 32) | value.dwLowDateTime;
}
static void r2_own_fault_v1(uint32_t op, uint32_t kind, uint32_t code, DWORD error)
{
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    struct r2_win_owned_fault_v1 *f;
    InterlockedExchange(&r2_own_stop_v1, 1);
    r->stop_new = 1;
    if (op == 0 || op >= R2_WIN_OWNED_FAULT_CAPACITY) {
        r->residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
        return;
    }
    f = &r->faults[op];
    if (f->occurrences == 0) {
        f->operation = op; f->kind = kind; f->code = code;
        f->win32_error = (uint32_t)error;
        f->win32_error_valid = kind == R2_OWN_ERROR_WIN32;
        f->occurrences = 1;
        if (r->fault_count == 0) r->primary = *f;
        ++r->fault_count;
    } else if (f->occurrences != UINT32_MAX) {
        ++f->occurrences;
    }
}
static void r2_own_api_v1(uint32_t op, DWORD error)
{
    r2_own_fault_v1(op, R2_OWN_ERROR_WIN32, 0, error);
    if (op == R2_OWN_OP_CREATOR_PID || op == R2_OWN_OP_CREATOR_TIMES || op == R2_OWN_OP_CREATOR_WAIT ||
        op == R2_OWN_OP_CHILD_PID || op == R2_OWN_OP_CHILD_TID ||
        op == R2_OWN_OP_PROCESS_TIMES || op == R2_OWN_OP_THREAD_TIMES ||
        op == R2_OWN_OP_MEMBERSHIP || op == R2_OWN_OP_EXIT_CODE ||
        op == R2_OWN_OP_SNAPSHOT || op == R2_OWN_OP_THREAD_FIRST || op == R2_OWN_OP_THREAD_NEXT)
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
    if (op == R2_OWN_OP_WAIT_PROCESS || op == R2_OWN_OP_WAIT_THREAD)
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_JOIN;
}
static void r2_own_bad_v1(uint32_t op, uint32_t code)
{
    r2_own_fault_v1(op, R2_OWN_ERROR_INVARIANT, code, 0);
    if (op == R2_OWN_OP_CREATOR_PID || op == R2_OWN_OP_CREATOR_TIMES ||
        op == R2_OWN_OP_CREATOR_WAIT || op == R2_OWN_OP_SNAPSHOT)
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
}
/* A failed/regressed clock is irreversible. No later sample creates a fresh
 * epoch. Synchronous native calls are not claimed to be cancellable. */
static int r2_own_clock_v1(int64_t deadline, uint32_t op)
{
    LARGE_INTEGER value;
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    if (!QueryPerformanceCounter(&value)) {
        DWORD error = GetLastError();
        r2_own_api_v1(op, error);
        r->clock_valid = 0; r->residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        return 0;
    }
    if (value.QuadPart <= 0 || (r->last_qpc && value.QuadPart < r->last_qpc)) {
        r2_own_bad_v1(op, R2_OWN_BAD_VALUE);
        r->clock_valid = 0; r->residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        return 0;
    }
    r->last_qpc = value.QuadPart;
    r->clock_valid = (r->residual_bits & R2_OWN_RESIDUAL_CLOCK) == 0;
    if (deadline > 0 && value.QuadPart >= deadline) {
        r2_own_bad_v1(op, R2_OWN_DEADLINE);
        r->residual_bits |= R2_OWN_RESIDUAL_DEADLINE;
        return 0;
    }
    return r->clock_valid != 0;
}
static int r2_own_new_work_v1(uint32_t state)
{
    if (r2_own_report_v1.lifecycle != state) {
        if (r2_own_report_v1.lifecycle != R2_OWN_DONE && r2_own_report_v1.lifecycle != R2_OWN_RETAINED)
            r2_own_bad_v1(R2_OWN_OP_STATE, R2_OWN_BAD_VALUE);
        return 0;
    }
    if (r2_own_report_v1.fault_count || r2_own_stopped_v1())
        return 0;
    if (GetCurrentProcessId() != r2_own_report_v1.creator_pid ||
        GetCurrentThreadId() != r2_own_report_v1.creator_tid) {
        r2_own_bad_v1(R2_OWN_OP_STATE, R2_OWN_IDENTITY);
        return 0;
    }
    return r2_own_clock_v1(r2_own_report_v1.stop_deadline_qpc, R2_OWN_OP_CLOCK);
}
static int r2_own_copy_text_v1(WCHAR *out, const struct r2_win_owned_text_v1 *in,
                              int environment, int command, int absolute)
{
    uint32_t i, maximum = command ? 32767u : R2_WIN_OWNED_TEXT_CAPACITY;
    if (in->reserved || in->units < (environment ? 2u : 1u) || in->units > maximum ||
        !r2_own_range_v1(in->text, (size_t)in->units * sizeof(uint16_t), _Alignof(uint16_t)))
        return 0;
    if (in->text[in->units - 1] != 0 || (environment && in->text[in->units - 2] != 0)) return 0;
    for (i = 0; i + 1 < in->units; ++i) {
        if (!environment && in->text[i] == 0) return 0;
        if (environment && i + 2 < in->units && in->text[i] == 0 && in->text[i + 1] == 0) return 0;
    }
    /* Deliberately bounded supported path grammar: drive-absolute paths.
     * This is lexical validation only, never an image/readonly identity. */
    if (absolute && (in->units < 4 ||
        !((in->text[0] >= 'A' && in->text[0] <= 'Z') || (in->text[0] >= 'a' && in->text[0] <= 'z')) ||
        in->text[1] != ':' || in->text[2] != '\\')) return 0;
    memcpy(out, in->text, (size_t)in->units * sizeof(uint16_t));
    return 1;
}
static int r2_own_query_v1(JOBOBJECTINFOCLASS cls, void *out, DWORD size,
                          uint32_t op, int64_t deadline)
{
    DWORD returned = 0;
    if (!r2_own_clock_v1(deadline, R2_OWN_OP_CLOCK)) return 0;
    if (!QueryInformationJobObject(r2_own_v1.job, cls, out, size, &returned)) {
        DWORD error = GetLastError();
        r2_own_api_v1(op, error);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
        return 0;
    }
    if (returned != size) {
        r2_own_bad_v1(op, R2_OWN_LENGTH);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
        return 0;
    }
    return r2_own_clock_v1(deadline, R2_OWN_OP_CLOCK);
}
static int r2_own_limits_v1(struct r2_win_job_raw_snapshot_v1 *s, int64_t deadline)
{
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    JOBOBJECT_CPU_RATE_CONTROL_INFORMATION cpu = {0};
    memset(s, 0, sizeof(*s));
    s->limits_readback_state = R2_WIN_JOB_FIELD_FAILED;
    if (!r2_own_query_v1(JobObjectExtendedLimitInformation, &limits, sizeof(limits),
        R2_OWN_OP_QUERY_LIMITS, deadline)) return 0;
    r2_own_u32_v1(&s->limit_flags, limits.BasicLimitInformation.LimitFlags);
    r2_own_u32_v1(&s->active_process_limit, limits.BasicLimitInformation.ActiveProcessLimit);
    r2_own_u64_v1(&s->affinity, limits.BasicLimitInformation.Affinity);
    r2_own_u64_v1(&s->job_commit_limit, limits.JobMemoryLimit);
    r2_own_u64_v1(&s->process_commit_limit, limits.ProcessMemoryLimit);
    r2_own_u64_v1(&s->peak_process_commit, limits.PeakProcessMemoryUsed);
    r2_own_u64_v1(&s->peak_job_commit, limits.PeakJobMemoryUsed);
    if (limits.BasicLimitInformation.LimitFlags != R2_OWN_FLAGS ||
        limits.BasicLimitInformation.ActiveProcessLimit != 1 ||
        limits.BasicLimitInformation.Affinity != r2_own_v1.limits.BasicLimitInformation.Affinity ||
        limits.JobMemoryLimit != (SIZE_T)R2_OWN_COMMIT || limits.ProcessMemoryLimit != 0 ||
        limits.PeakJobMemoryUsed > (SIZE_T)R2_OWN_COMMIT || limits.PeakProcessMemoryUsed > (SIZE_T)R2_OWN_COMMIT) {
        r2_own_bad_v1(R2_OWN_OP_QUERY_LIMITS, R2_OWN_LIMIT_CHANGED);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
        return 0;
    }
    s->limits_readback_state = R2_WIN_JOB_FIELD_VALID;
    s->cpu_readback_state = R2_WIN_JOB_FIELD_FAILED;
    if (!r2_own_query_v1(JobObjectCpuRateControlInformation, &cpu, sizeof(cpu),
        R2_OWN_OP_QUERY_CPU, deadline)) return 0;
    r2_own_u32_v1(&s->cpu_control_flags, cpu.ControlFlags);
    r2_own_u32_v1(&s->cpu_rate, cpu.CpuRate);
    if (cpu.ControlFlags != R2_OWN_CPU_FLAGS || cpu.CpuRate != r2_own_v1.cpu.CpuRate) {
        r2_own_bad_v1(R2_OWN_OP_QUERY_CPU, R2_OWN_LIMIT_CHANGED);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
        return 0;
    }
    s->cpu_readback_state = R2_WIN_JOB_FIELD_VALID;
    return 1;
}
static int r2_own_sample_v1(struct r2_win_job_raw_snapshot_v1 *s, int64_t deadline)
{
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION a = {0};
    if (!r2_own_limits_v1(s, deadline)) return 0;
    s->accounting_state = R2_WIN_JOB_FIELD_FAILED;
    if (!r2_own_query_v1(JobObjectBasicAccountingInformation, &a, sizeof(a),
        R2_OWN_OP_QUERY_ACCOUNTING, deadline)) return 0;
    if (a.TotalUserTime.QuadPart < 0 || a.TotalKernelTime.QuadPart < 0 ||
        a.ThisPeriodTotalUserTime.QuadPart < 0 || a.ThisPeriodTotalKernelTime.QuadPart < 0) {
        r2_own_bad_v1(R2_OWN_OP_QUERY_ACCOUNTING, R2_OWN_BAD_VALUE);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
        return 0;
    }
    r2_own_i64_v1(&s->total_user_100ns, a.TotalUserTime.QuadPart);
    r2_own_i64_v1(&s->total_kernel_100ns, a.TotalKernelTime.QuadPart);
    r2_own_i64_v1(&s->period_user_100ns, a.ThisPeriodTotalUserTime.QuadPart);
    r2_own_i64_v1(&s->period_kernel_100ns, a.ThisPeriodTotalKernelTime.QuadPart);
    r2_own_u32_v1(&s->page_faults, a.TotalPageFaultCount);
    r2_own_u32_v1(&s->total_processes, a.TotalProcesses);
    r2_own_u32_v1(&s->active_processes, a.ActiveProcesses);
    r2_own_u32_v1(&s->terminated_by_limits, a.TotalTerminatedProcesses);
    s->accounting_state = R2_WIN_JOB_FIELD_VALID;
    r2_own_report_v1.job_empty = a.ActiveProcesses == 0;
    if (a.ActiveProcesses > 1 || a.TotalTerminatedProcesses != 0 ||
        a.TotalProcesses != (r2_own_report_v1.process.acquired ? 1u : 0u)) {
        r2_own_bad_v1(R2_OWN_OP_BIRTH_HISTORY, R2_OWN_COUNT_CHANGED);
        return 0;
    }
    return 1;
}
static int r2_own_creator_identity_v1(void)
{
    FILETIME creation, exit_time, kernel, user;
    DWORD wait = WaitForSingleObject(r2_own_v1.creator, 0);
    if (wait == WAIT_FAILED) { DWORD error = GetLastError(); r2_own_api_v1(R2_OWN_OP_CREATOR_WAIT, error); return 0; }
    if (wait != WAIT_TIMEOUT) { r2_own_bad_v1(R2_OWN_OP_CREATOR_WAIT, R2_OWN_WAIT_RESULT); return 0; }
    DWORD pid = GetProcessId(r2_own_v1.creator);
    if (!pid) { DWORD error = GetLastError(); r2_own_api_v1(R2_OWN_OP_CREATOR_PID, error); return 0; }
    if (pid != r2_own_report_v1.creator_pid || GetCurrentProcessId() != pid) {
        r2_own_bad_v1(R2_OWN_OP_CREATOR_PID, R2_OWN_IDENTITY); return 0;
    }
    if (!GetProcessTimes(r2_own_v1.creator, &creation, &exit_time, &kernel, &user)) {
        DWORD error = GetLastError(); r2_own_api_v1(R2_OWN_OP_CREATOR_TIMES, error);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE; return 0;
    }
    if (r2_own_report_v1.creator_creation_100ns.state == R2_WIN_JOB_FIELD_VALID &&
        r2_own_report_v1.creator_creation_100ns.value != r2_own_filetime_v1(creation)) {
        r2_own_bad_v1(R2_OWN_OP_CREATOR_TIMES, R2_OWN_IDENTITY); return 0;
    }
    r2_own_u64_v1(&r2_own_report_v1.creator_creation_100ns, r2_own_filetime_v1(creation));
    return 1;
}
static int r2_own_child_identity_v1(int final)
{
    FILETIME creation, exit_time, kernel, user;
    DWORD pid, tid;
    BOOL member = FALSE;
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    pid = GetProcessId(r2_own_v1.process);
    if (!pid) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_CHILD_PID, e); goto failed; }
    tid = GetThreadId(r2_own_v1.thread);
    if (!tid) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_CHILD_TID, e); goto failed; }
    if (pid != r->child_pid || tid != r->child_tid) {
        r2_own_bad_v1(R2_OWN_OP_CHILD_PID, R2_OWN_IDENTITY); goto failed;
    }
    if (!GetProcessTimes(r2_own_v1.process, &creation, &exit_time, &kernel, &user)) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_PROCESS_TIMES, e); goto failed;
    }
    if (r->child_creation_100ns.state == R2_WIN_JOB_FIELD_VALID &&
        r->child_creation_100ns.value != r2_own_filetime_v1(creation)) {
        r2_own_bad_v1(R2_OWN_OP_PROCESS_TIMES, R2_OWN_IDENTITY); goto failed;
    }
    r2_own_u64_v1(&r->child_creation_100ns, r2_own_filetime_v1(creation));
    if (final) {
        r2_own_u64_v1(&r->final_exit_100ns, r2_own_filetime_v1(exit_time));
        r2_own_u64_v1(&r->final_kernel_100ns, r2_own_filetime_v1(kernel));
        r2_own_u64_v1(&r->final_user_100ns, r2_own_filetime_v1(user));
    }
    if (!GetThreadTimes(r2_own_v1.thread, &creation, &exit_time, &kernel, &user)) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_THREAD_TIMES, e); goto failed;
    }
    if (r->primary_creation_100ns.state == R2_WIN_JOB_FIELD_VALID &&
        r->primary_creation_100ns.value != r2_own_filetime_v1(creation)) {
        r2_own_bad_v1(R2_OWN_OP_THREAD_TIMES, R2_OWN_IDENTITY); goto failed;
    }
    r2_own_u64_v1(&r->primary_creation_100ns, r2_own_filetime_v1(creation));
    if (final) {
        r2_own_u64_v1(&r->final_thread_kernel_100ns, r2_own_filetime_v1(kernel));
        r2_own_u64_v1(&r->final_thread_user_100ns, r2_own_filetime_v1(user));
    }
    /* Birth/live membership was verified on the original handles. Do not
     * require a dead process to retain live membership semantics. */
    if (final) return 1;
    if (!IsProcessInJob(r2_own_v1.process, r2_own_v1.job, &member)) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_MEMBERSHIP, e); goto failed;
    }
    if (!member) { r2_own_bad_v1(R2_OWN_OP_MEMBERSHIP, R2_OWN_IDENTITY); goto failed; }
    r->membership = 1;
    return 1;
failed:
    r->residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
    return 0;
}
static int r2_own_wait_process_v1(DWORD milliseconds)
{
    DWORD value;
    if (!r2_own_v1.process || r2_own_report_v1.process_signaled) return 1;
    value = WaitForSingleObject(r2_own_v1.process, milliseconds);
    if (value == WAIT_FAILED) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_WAIT_PROCESS, e);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_JOIN; return 0;
    }
    r2_own_u32_v1(&r2_own_report_v1.wait_after, value);
    if (value == WAIT_OBJECT_0) r2_own_report_v1.process_signaled = 1;
    else if (value != WAIT_TIMEOUT) {
        r2_own_bad_v1(R2_OWN_OP_WAIT_PROCESS, R2_OWN_WAIT_RESULT);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_JOIN; return 0;
    }
    return 1;
}
static int r2_own_close_v1(HANDLE *slot, struct r2_win_owned_handle_state_v1 *state,
                          uint32_t op, int64_t deadline)
{
    HANDLE handle;
    if (!*slot) return state->close_state != R2_WIN_JOB_FIELD_FAILED;
    if (!r2_own_clock_v1(deadline, R2_OWN_OP_CLOCK)) return 0;
    handle = *slot; *slot = NULL; state->consumed = 1;
    if (!CloseHandle(handle)) {
        DWORD e = GetLastError(); r2_own_api_v1(op, e);
        state->close_state = R2_WIN_JOB_FIELD_FAILED;
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_CLOSE;
        return 0;
    }
    state->close_state = R2_WIN_JOB_FIELD_VALID;
    return r2_own_clock_v1(deadline, R2_OWN_OP_CLOCK);
}
/* Bounded raw MONITORED4 observation of original parent and owned child.
 * Snapshot TIDs are not opened/reopened or promoted into creator handles.
 * Two liveness/creation checks exclude PID reuse within this observation;
 * transient threads between observations remain explicitly uncovered. */
static int r2_own_threads_v1(int64_t deadline)
{
    THREADENTRY32 entry;
    DWORD parent_count = 0, child_count = 0, entries = 0, before = WAIT_TIMEOUT;
    BOOL more;
    int complete = 0, ok = 0;
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    r->thread_scan_state = R2_WIN_JOB_FIELD_FAILED;
    r->thread_scan_entries = r->parent_threads = r->child_threads = 0;
    r->thread_live_at_both_polls = 0;
    if (r2_own_v1.snapshot || r->snapshot.close_state == R2_WIN_JOB_FIELD_FAILED) return 0;
    if (!r2_own_creator_identity_v1() || !r2_own_clock_v1(deadline, R2_OWN_OP_CLOCK)) return 0;
    if (r2_own_v1.process) {
        before = WaitForSingleObject(r2_own_v1.process, 0);
        if (before == WAIT_FAILED) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_WAIT_PROCESS, e); return 0; }
        r2_own_u32_v1(&r->wait_before, before);
        if (before == WAIT_OBJECT_0) {
            r->process_signaled = 1; InterlockedExchange(&r2_own_stop_v1, 1); return 1;
        }
        if (before != WAIT_TIMEOUT || !r2_own_child_identity_v1(0)) {
            r2_own_bad_v1(R2_OWN_OP_WAIT_PROCESS, R2_OWN_WAIT_RESULT); return 0;
        }
    }
    r2_own_v1.snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (r2_own_v1.snapshot == INVALID_HANDLE_VALUE) {
        DWORD e = GetLastError(); r2_own_v1.snapshot = NULL;
        r2_own_api_v1(R2_OWN_OP_SNAPSHOT, e); return 0;
    }
    if (!r2_own_v1.snapshot) { r2_own_bad_v1(R2_OWN_OP_SNAPSHOT, R2_OWN_BAD_VALUE); return 0; }
    r->snapshot = (struct r2_win_owned_handle_state_v1){1, 0, 0, 0};
    if (!r2_own_clock_v1(deadline, R2_OWN_OP_CLOCK)) goto cleanup;
    memset(&entry, 0, sizeof(entry)); entry.dwSize = sizeof(entry);
    more = Thread32First(r2_own_v1.snapshot, &entry);
    if (!more) {
        DWORD e = GetLastError();
        if (e != ERROR_NO_MORE_FILES) r2_own_api_v1(R2_OWN_OP_THREAD_FIRST, e);
        else r2_own_bad_v1(R2_OWN_OP_THREAD_FIRST, R2_OWN_BAD_VALUE);
        goto cleanup;
    }
    while (more) {
        if (++entries > R2_WIN_OWNED_THREAD_SCAN_CAPACITY ||
            entry.dwSize < offsetof(THREADENTRY32, th32OwnerProcessID) + sizeof(entry.th32OwnerProcessID)) {
            r2_own_bad_v1(R2_OWN_OP_THREAD_NEXT, R2_OWN_SCAN_BOUND); goto cleanup;
        }
        if (entry.th32OwnerProcessID == r->creator_pid) ++parent_count;
        if (r2_own_v1.process && entry.th32OwnerProcessID == r->child_pid) ++child_count;
        if (!r2_own_clock_v1(deadline, R2_OWN_OP_CLOCK)) goto cleanup;
        entry.dwSize = sizeof(entry);
        more = Thread32Next(r2_own_v1.snapshot, &entry);
        if (!more) {
            DWORD e = GetLastError();
            if (e != ERROR_NO_MORE_FILES) { r2_own_api_v1(R2_OWN_OP_THREAD_NEXT, e); goto cleanup; }
            complete = 1;
        }
    }
    if (!complete || parent_count == 0) {
        r2_own_bad_v1(R2_OWN_OP_THREAD_NEXT, R2_OWN_BAD_VALUE); goto cleanup;
    }
    if (!r2_own_creator_identity_v1()) goto cleanup;
    if (r2_own_v1.process) {
        DWORD after = WaitForSingleObject(r2_own_v1.process, 0);
        if (after == WAIT_FAILED) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_WAIT_PROCESS, e); goto cleanup; }
        r2_own_u32_v1(&r->wait_after, after);
        if (after == WAIT_OBJECT_0) {
            r->process_signaled = 1; InterlockedExchange(&r2_own_stop_v1, 1); goto cleanup;
        }
        if (after != WAIT_TIMEOUT || !r2_own_child_identity_v1(0) || child_count == 0) {
            r2_own_bad_v1(R2_OWN_OP_THREAD_NEXT, R2_OWN_IDENTITY); goto cleanup;
        }
    }
    r->thread_scan_entries = entries; r->parent_threads = parent_count; r->child_threads = child_count;
    r->thread_live_at_both_polls = r2_own_v1.process ? 1u : 0u;
    r->thread_scan_state = R2_WIN_JOB_FIELD_VALID;
    if (parent_count + child_count > 4) {
        r2_own_bad_v1(R2_OWN_OP_THREAD_LIMIT, R2_OWN_COUNT_CHANGED); goto cleanup;
    }
    ok = 1;
cleanup:
    if (!r2_own_close_v1(&r2_own_v1.snapshot, &r->snapshot, R2_OWN_OP_CLOSE_SNAPSHOT, deadline)) ok = 0;
    if (!ok && !r->process_signaled) InterlockedExchange(&r2_own_stop_v1, 1);
    return ok;
}
static DWORD r2_own_slice_v1(int64_t deadline)
{
    int64_t remaining = deadline - r2_own_report_v1.last_qpc;
    int64_t frequency = r2_own_report_v1.qpc_frequency;
    if (remaining <= 0 || frequency <= 0) return 0;
    if (remaining >= frequency) return 1000;
    /* Avoid overflowing remaining*1000 for unusual native frequencies. */
    return (DWORD)((remaining / frequency) * 1000 +
        ((uint64_t)(remaining % frequency) * 1000u) / (uint64_t)frequency);
}

R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_describe_v1(
    struct r2_win_owned_abi_v1 *out, size_t size)
{
    struct r2_win_owned_abi_v1 value = {
        R2_WIN_OWNED_ABI, sizeof(value), sizeof(struct r2_win_owned_spec_v1),
        sizeof(struct r2_win_owned_report_v1), sizeof(void *),
        sizeof(struct r2_win_owned_text_v1), sizeof(struct r2_win_owned_fault_v1),
        sizeof(struct r2_win_owned_handle_state_v1), sizeof(struct r2_win_job_raw_snapshot_v1),
        offsetof(struct r2_win_owned_report_v1, faults),
        offsetof(struct r2_win_owned_report_v1, configured), 0
    };
    if (size != sizeof(value) || !r2_own_range_v1(out, size, _Alignof(struct r2_win_owned_abi_v1)))
        return R2_OWN_BAD_ARGUMENT;
    memcpy(out, &value, sizeof(value));
    return R2_OWN_OK;
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_begin_once_v1(
    const struct r2_win_owned_spec_v1 *spec, size_t size)
{
    LARGE_INTEGER frequency;
    HANDLE creator = NULL;
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    if (!r2_own_enter_v1()) return R2_OWN_BUSY;
    if (r->attempt_consumed) {
        if (r->lifecycle != R2_OWN_DONE && r->lifecycle != R2_OWN_RETAINED)
            r2_own_bad_v1(R2_OWN_OP_STATE, R2_OWN_BAD_VALUE);
        return r2_own_leave_v1(R2_OWN_BAD_STATE);
    }
    r->attempt_consumed = 1; r->lifecycle = R2_OWN_INITIALIZING;
    if (r2_own_stopped_v1()) { r2_own_bad_v1(R2_OWN_OP_STATE, R2_OWN_BAD_VALUE); return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP); }
    if (!r2_own_clock_v1(0, R2_OWN_OP_FIRST_CLOCK)) return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    r->context_observed_qpc = r->last_qpc;
    if (!QueryPerformanceFrequency(&frequency)) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_FREQUENCY, e);
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    }
    if (frequency.QuadPart <= 0 || frequency.QuadPart > INT64_MAX / 1000 ||
        size != sizeof(*spec) || !r2_own_range_v1(spec, size, _Alignof(struct r2_win_owned_spec_v1))) {
        r2_own_fault_v1(R2_OWN_OP_ARGUMENT, R2_OWN_ERROR_ARGUMENT, R2_OWN_BAD_VALUE, 0);
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    }
    r->qpc_frequency = frequency.QuadPart;
    if (spec->abi != R2_WIN_OWNED_ABI || spec->size != size || spec->lease_epoch_qpc <= 0 ||
        spec->lease_qpc_frequency != frequency.QuadPart || spec->lease_epoch_qpc > r->context_observed_qpc ||
        spec->stop_deadline_qpc <= r->context_observed_qpc ||
        spec->cleanup_deadline_qpc <= spec->stop_deadline_qpc) {
        r2_own_fault_v1(R2_OWN_OP_ARGUMENT, R2_OWN_ERROR_ARGUMENT, R2_OWN_BAD_VALUE, 0);
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    }
    r->lease_epoch_qpc = spec->lease_epoch_qpc; r->intent_serial = spec->intent_serial;
    r->stop_deadline_qpc = spec->stop_deadline_qpc; r->cleanup_deadline_qpc = spec->cleanup_deadline_qpc;
    r2_own_v1.deadline_bound = 1;
    if (!r2_own_copy_text_v1(r2_own_v1.application, &spec->application, 0, 0, 1) ||
        !r2_own_copy_text_v1(r2_own_v1.command, &spec->command_line, 0, 1, 0) ||
        !r2_own_copy_text_v1(r2_own_v1.directory, &spec->current_directory, 0, 0, 1) ||
        !r2_own_copy_text_v1(r2_own_v1.environment, &spec->environment, 1, 0, 0)) {
        r2_own_fault_v1(R2_OWN_OP_ARGUMENT, R2_OWN_ERROR_ARGUMENT, R2_OWN_BAD_VALUE, 0);
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    }
    r->creator_pid = GetCurrentProcessId(); r->creator_tid = GetCurrentThreadId();
    if (!r->creator_pid || !r->creator_tid) {
        r2_own_bad_v1(R2_OWN_OP_CREATOR_PID, R2_OWN_BAD_VALUE);
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    }
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK))
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    if (!DuplicateHandle(GetCurrentProcess(), GetCurrentProcess(), GetCurrentProcess(),
        &creator, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_CREATOR_DUPLICATE, e);
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    }
    r2_own_v1.creator = creator; r->creator.acquired = 1;
    if (!r2_own_creator_identity_v1() || !r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK) ||
        !r2_own_threads_v1(r->stop_deadline_qpc)) return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    r->lifecycle = R2_OWN_INTENT_HELD;
    return r2_own_leave_v1(R2_OWN_OK);
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_birth_suspended_once_v1(void)
{
    WORD groups;
    DWORD count, i, pop = 0;
    DWORD_PTR allowed = 0, system = 0, first, remaining;
    SIZE_T attribute_size = 0;
    BOOL sized, created;
    DWORD sizing_error;
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    if (!r2_own_enter_v1()) return R2_OWN_BUSY;
    if (!r2_own_new_work_v1(R2_OWN_INTENT_HELD) || r->birth_attempted)
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    r->birth_attempted = 1;
    r2_own_v1.job = CreateJobObjectW(NULL, NULL);
    if (!r2_own_v1.job) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_CREATE_JOB, e); goto failed; }
    r->job.acquired = 1;
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK)) goto failed;
    groups = GetActiveProcessorGroupCount();
    if (!groups) { r2_own_fault_v1(R2_OWN_OP_GROUPS, R2_OWN_ERROR_NO_EXTENDED, 0, 0); goto failed; }
    count = GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
    if (!count) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_COUNT, e); goto failed; }
    r2_own_u32_v1(&r->processor_groups, groups); r2_own_u32_v1(&r->processor_count, count);
    if (groups != 1 || count > sizeof(DWORD_PTR) * CHAR_BIT) { r2_own_bad_v1(R2_OWN_OP_COUNT, R2_OWN_BAD_VALUE); goto failed; }
    if (!GetProcessAffinityMask(r2_own_v1.creator, &allowed, &system)) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_AFFINITY, e); goto failed;
    }
    for (i = 0; i < sizeof(DWORD_PTR) * CHAR_BIT; ++i) if (system & ((DWORD_PTR)1 << i)) ++pop;
    if (!allowed || (allowed & ~system) || pop != count) { r2_own_bad_v1(R2_OWN_OP_AFFINITY, R2_OWN_BAD_VALUE); goto failed; }
    first = allowed & (~allowed + 1); remaining = allowed ^ first;
    r2_own_v1.limits.BasicLimitInformation.LimitFlags = R2_OWN_FLAGS;
    r2_own_v1.limits.BasicLimitInformation.ActiveProcessLimit = 1;
    r2_own_v1.limits.BasicLimitInformation.Affinity = first | (remaining & (~remaining + 1));
    r2_own_v1.limits.JobMemoryLimit = (SIZE_T)R2_OWN_COMMIT;
    r2_own_v1.cpu.ControlFlags = R2_OWN_CPU_FLAGS;
    r2_own_v1.cpu.CpuRate = count <= 2 ? 10000 : 20000 / count;
    r2_own_u64_v1(&r->allowed_affinity, allowed); r2_own_u64_v1(&r->system_affinity, system);
    r2_own_u64_v1(&r->selected_affinity, r2_own_v1.limits.BasicLimitInformation.Affinity);
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK)) goto failed;
    if (!SetInformationJobObject(r2_own_v1.job, JobObjectExtendedLimitInformation,
        &r2_own_v1.limits, sizeof(r2_own_v1.limits))) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_SET_LIMITS, e); goto failed;
    }
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK)) goto failed;
    if (!SetInformationJobObject(r2_own_v1.job, JobObjectCpuRateControlInformation,
        &r2_own_v1.cpu, sizeof(r2_own_v1.cpu))) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_SET_CPU, e); goto failed;
    }
    if (!r2_own_sample_v1(&r->configured, r->stop_deadline_qpc)) goto failed;
    r->configured_valid = 1;
    sized = InitializeProcThreadAttributeList(NULL, 1, 0, &attribute_size);
    sizing_error = GetLastError();
    if (sized || sizing_error != ERROR_INSUFFICIENT_BUFFER || !attribute_size ||
        attribute_size > sizeof(r2_own_v1.attributes.bytes)) {
        if (!sized && sizing_error != ERROR_INSUFFICIENT_BUFFER) r2_own_api_v1(R2_OWN_OP_ATTRIBUTE_SIZE, sizing_error);
        else r2_own_bad_v1(R2_OWN_OP_ATTRIBUTE_SIZE, R2_OWN_LENGTH);
        goto failed;
    }
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK) || r2_own_stopped_v1()) goto failed;
    r2_own_v1.startup.StartupInfo.cb = sizeof(r2_own_v1.startup);
    r2_own_v1.startup.lpAttributeList = (LPPROC_THREAD_ATTRIBUTE_LIST)r2_own_v1.attributes.bytes;
    if (!InitializeProcThreadAttributeList(r2_own_v1.startup.lpAttributeList, 1, 0, &attribute_size)) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_ATTRIBUTE_INIT, e); goto failed;
    }
    r->attribute_initialized = 1;
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK) || r2_own_stopped_v1()) goto failed;
    r2_own_v1.jobs[0] = r2_own_v1.job;
    if (!UpdateProcThreadAttribute(r2_own_v1.startup.lpAttributeList, 0,
        PROC_THREAD_ATTRIBUTE_JOB_LIST, r2_own_v1.jobs, sizeof(r2_own_v1.jobs), NULL, NULL)) {
        DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_ATTRIBUTE_UPDATE, e); goto failed;
    }
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK) || r2_own_stopped_v1()) goto failed;
    created = CreateProcessW(r2_own_v1.application, r2_own_v1.command, NULL, NULL, FALSE,
        R2_OWN_CREATE_FLAGS, r2_own_v1.environment, r2_own_v1.directory,
        &r2_own_v1.startup.StartupInfo, &r2_own_v1.pi);
    if (!created) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_CREATE_PROCESS, e); goto failed; }
    /* First instructions after BOOL success adopt BOTH originals. No API,
     * clock, validation, report callback or foreign conversion intervenes. */
    r2_own_v1.process = r2_own_v1.pi.hProcess;
    r2_own_v1.thread = r2_own_v1.pi.hThread;
    r->process.acquired = r->thread.acquired = 1;
    r->job_empty = 0; /* Invalidate the pre-birth empty observation. */
    r->child_pid = r2_own_v1.pi.dwProcessId; r->child_tid = r2_own_v1.pi.dwThreadId;
    r->lifecycle = R2_OWN_SUSPENDED;
    DeleteProcThreadAttributeList(r2_own_v1.startup.lpAttributeList); r->attribute_deleted = 1;
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK) ||
        !r2_own_child_identity_v1(0) || !r2_own_sample_v1(&r->latest, r->stop_deadline_qpc)) goto failed;
    r->latest_valid = 1;
    if (!r2_own_threads_v1(r->stop_deadline_qpc) || r2_own_stopped_v1()) goto failed;
    return r2_own_leave_v1(R2_OWN_OK);
failed:
    if (r->attribute_initialized && !r->attribute_deleted) {
        DeleteProcThreadAttributeList(r2_own_v1.startup.lpAttributeList); r->attribute_deleted = 1;
    }
    InterlockedExchange(&r2_own_stop_v1, 1);
    return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_resume_once_v1(void)
{
    DWORD previous;
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    if (!r2_own_enter_v1()) return R2_OWN_BUSY;
    if (!r2_own_new_work_v1(R2_OWN_SUSPENDED) || r->resume_attempted)
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    r->latest_valid = 0;
    if (
        !r2_own_child_identity_v1(0) || !r2_own_threads_v1(r->stop_deadline_qpc) ||
        !r2_own_sample_v1(&r->latest, r->stop_deadline_qpc) || r2_own_stopped_v1())
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    r->latest_valid = 1; r->resume_attempted = 1;
    previous = ResumeThread(r2_own_v1.thread);
    if (previous == (DWORD)-1) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_RESUME, e); return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP); }
    if (previous != 1) { r2_own_bad_v1(R2_OWN_OP_RESUME, R2_OWN_BAD_VALUE); return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP); }
    r->lifecycle = R2_OWN_RUNNING;
    if (!r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK) || r2_own_stopped_v1())
        return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    return r2_own_leave_v1(R2_OWN_OK);
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_observe_step_v1(void)
{
    DWORD code;
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    if (!r2_own_enter_v1()) return R2_OWN_BUSY;
    if (!r2_own_new_work_v1(R2_OWN_RUNNING)) return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    if (!r2_own_wait_process_v1(r2_own_slice_v1(r->stop_deadline_qpc)) ||
        !r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK)) return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    r->latest_valid = r2_own_sample_v1(&r->latest, r->stop_deadline_qpc);
    if (!r->latest_valid) return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    if (r->process_signaled) {
        InterlockedExchange(&r2_own_stop_v1, 1);
        if (!GetExitCodeProcess(r2_own_v1.process, &code)) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_EXIT_CODE, e); return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP); }
        r2_own_u32_v1(&r->final_exit_code, code);
        if (code != 0) r2_own_bad_v1(R2_OWN_OP_EXIT_CODE, code);
        return r2_own_leave_v1(R2_OWN_EXITED);
    }
    if (!r2_own_child_identity_v1(0) || !r2_own_threads_v1(r->stop_deadline_qpc) ||
        !r2_own_clock_v1(r->stop_deadline_qpc, R2_OWN_OP_CLOCK)) return r2_own_leave_v1(R2_OWN_NEEDS_CLEANUP);
    if (r->process_signaled) return r2_own_leave_v1(R2_OWN_EXITED);
    return r2_own_leave_v1(r2_own_stopped_v1() ? R2_OWN_NEEDS_CLEANUP : R2_OWN_PENDING);
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_stop_new_v1(void)
{
    InterlockedExchange(&r2_own_stop_v1, 1);
    if (!r2_own_enter_v1()) return R2_OWN_BUSY;
    r2_own_report_v1.stop_new = 1;
    return r2_own_leave_v1(R2_OWN_OK);
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_finish_step_v1(void)
{
    DWORD value, code;
    int64_t slice_deadline;
    int clock_ok, final_ok = 1;
    struct r2_win_owned_report_v1 *r = &r2_own_report_v1;
    InterlockedExchange(&r2_own_stop_v1, 1);
    if (!r2_own_enter_v1()) return R2_OWN_BUSY;
    if (!r->attempt_consumed) return r2_own_leave_v1(R2_OWN_BAD_STATE);
    if (r->lifecycle == R2_OWN_DONE) return r2_own_leave_v1(R2_OWN_FINISHED);
    if (r->lifecycle == R2_OWN_RETAINED) return r2_own_leave_v1(R2_OWN_RESIDUAL);
    clock_ok = r2_own_v1.deadline_bound && r2_own_clock_v1(r->cleanup_deadline_qpc, R2_OWN_OP_CLOCK);
    if (!r->finish_started) {
        r->finish_started = 1; r->lifecycle = R2_OWN_STOPPING;
        /* Even a late first cleanup requests termination once. It never
         * invents more waiting time or turns that request into observed exit. */
        if (r2_own_v1.job && (!r->process_signaled || !r->job_empty)) {
            if (TerminateJobObject(r2_own_v1.job, 0xE0000001u)) r->terminate_job_state = R2_WIN_JOB_FIELD_VALID;
            else { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_TERMINATE_JOB, e); r->terminate_job_state = R2_WIN_JOB_FIELD_FAILED; }
        }
        if (r2_own_v1.process && !r->process_signaled &&
            (!r->membership || r->terminate_job_state != R2_WIN_JOB_FIELD_VALID)) {
            if (TerminateProcess(r2_own_v1.process, 0xE0000001u)) r->terminate_process_state = R2_WIN_JOB_FIELD_VALID;
            else { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_TERMINATE_PROCESS, e); r->terminate_process_state = R2_WIN_JOB_FIELD_FAILED; }
        }
    }
    if (!r2_own_v1.creator && !r2_own_v1.job && !r2_own_v1.process && !r2_own_v1.thread && !r2_own_v1.snapshot) {
        if (r->residual_bits) goto residual;
        r->final_complete = 1; r->lifecycle = R2_OWN_DONE;
        return r2_own_leave_v1(R2_OWN_FINISHED);
    }
    if (!clock_ok || !r2_own_clock_v1(r->cleanup_deadline_qpc, R2_OWN_OP_CLOCK)) goto residual;
    r->lifecycle = R2_OWN_JOINING;
    slice_deadline = r->cleanup_deadline_qpc - r->last_qpc > r->qpc_frequency ?
        r->last_qpc + r->qpc_frequency : r->cleanup_deadline_qpc;
    if (!r2_own_wait_process_v1(r2_own_slice_v1(slice_deadline)) ||
        !r2_own_clock_v1(r->cleanup_deadline_qpc, R2_OWN_OP_CLOCK)) goto residual;
    if (r2_own_v1.thread) {
        value = WaitForSingleObject(r2_own_v1.thread, 0);
        if (value == WAIT_FAILED) { DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_WAIT_THREAD, e); r->residual_bits |= R2_OWN_RESIDUAL_JOIN; goto residual; }
        r2_own_u32_v1(&r->thread_wait, value);
        if (value == WAIT_OBJECT_0) r->thread_signaled = 1;
        else if (value == WAIT_TIMEOUT && r->process_signaled) {
            r2_own_bad_v1(R2_OWN_OP_WAIT_THREAD, R2_OWN_WAIT_RESULT);
            r->residual_bits |= R2_OWN_RESIDUAL_JOIN; goto residual;
        }
        else if (value != WAIT_TIMEOUT) { r2_own_bad_v1(R2_OWN_OP_WAIT_THREAD, R2_OWN_WAIT_RESULT); r->residual_bits |= R2_OWN_RESIDUAL_JOIN; goto residual; }
    }
    if (r2_own_v1.job) {
        r->latest_valid = r2_own_sample_v1(&r->latest, r->cleanup_deadline_qpc);
        if (!r->latest_valid) r->residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
    }
    if ((r2_own_v1.process && !r->process_signaled) ||
        (r2_own_v1.thread && !r->thread_signaled) || (r2_own_v1.job && !r->job_empty)) {
        if (!r2_own_clock_v1(r->cleanup_deadline_qpc, R2_OWN_OP_CLOCK)) goto residual;
        if (r->process_signaled && r2_own_v1.job && !r->job_empty) {
            DWORD pause = r2_own_slice_v1(slice_deadline);
            if (pause) Sleep(pause);
            if (!r2_own_clock_v1(r->cleanup_deadline_qpc, R2_OWN_OP_CLOCK)) goto residual;
        }
        return r2_own_leave_v1(R2_OWN_PENDING);
    }
    if (!r2_own_v1.final_attempted) {
        r2_own_v1.final_attempted = 1; r->lifecycle = R2_OWN_FINAL_SAMPLING;
        if (r2_own_v1.process) {
            if (!r2_own_child_identity_v1(1)) final_ok = 0;
            if (!GetExitCodeProcess(r2_own_v1.process, &code)) {
                DWORD e = GetLastError(); r2_own_api_v1(R2_OWN_OP_EXIT_CODE, e); final_ok = 0;
            } else {
                r2_own_u32_v1(&r->final_exit_code, code);
                /* A nonzero exit is a work failure even when a thread-scan
                 * race was the first exit observation. Keep valid final CPU,
                 * identity/accounting and the real once-close path: a failed
                 * workload does not itself mean the original is unjoined. */
                if (code != 0) r2_own_bad_v1(R2_OWN_OP_EXIT_CODE, code);
            }
        }
        if (r2_own_v1.job) {
            r->final_valid = r2_own_sample_v1(&r->final_sample, r->cleanup_deadline_qpc);
            if (!r->final_valid || !r->job_empty) final_ok = 0;
        }
        if (!r2_own_clock_v1(r->cleanup_deadline_qpc, R2_OWN_OP_FINAL_CLOCK)) final_ok = 0;
        r->final_complete = final_ok;
        if (!final_ok) r->residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
    }
    if (r->residual_bits || !r->final_complete) goto residual;
    r->lifecycle = R2_OWN_CLOSING;
    /* Every slot is consumed before its sole attempt. Independent later
     * closes still run after one failed close while original time remains. */
    r2_own_close_v1(&r2_own_v1.snapshot, &r->snapshot, R2_OWN_OP_CLOSE_SNAPSHOT, r->cleanup_deadline_qpc);
    r2_own_close_v1(&r2_own_v1.thread, &r->thread, R2_OWN_OP_CLOSE_THREAD, r->cleanup_deadline_qpc);
    r2_own_close_v1(&r2_own_v1.process, &r->process, R2_OWN_OP_CLOSE_PROCESS, r->cleanup_deadline_qpc);
    r2_own_close_v1(&r2_own_v1.job, &r->job, R2_OWN_OP_CLOSE_JOB, r->cleanup_deadline_qpc);
    r2_own_close_v1(&r2_own_v1.creator, &r->creator, R2_OWN_OP_CLOSE_CREATOR, r->cleanup_deadline_qpc);
    if (!r2_own_clock_v1(r->cleanup_deadline_qpc, R2_OWN_OP_FINAL_CLOCK) || r->residual_bits ||
        r2_own_v1.snapshot || r2_own_v1.thread || r2_own_v1.process || r2_own_v1.job || r2_own_v1.creator) goto residual;
    r->lifecycle = R2_OWN_DONE;
    return r2_own_leave_v1(R2_OWN_FINISHED);
residual:
    if ((r2_own_v1.process && !r->process_signaled) ||
        (r2_own_v1.thread && !r->thread_signaled) || (r2_own_v1.job && !r->job_empty))
        r->residual_bits |= R2_OWN_RESIDUAL_JOIN;
    r->lifecycle = R2_OWN_RETAINED;
    return r2_own_leave_v1(R2_OWN_RESIDUAL);
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_copy_report_v1(
    struct r2_win_owned_report_v1 *out, size_t size)
{
    if (size != sizeof(*out) || !r2_own_range_v1(out, size, _Alignof(struct r2_win_owned_report_v1)))
        return R2_OWN_BAD_ARGUMENT;
    if (!r2_own_enter_v1()) return R2_OWN_BUSY;
    r2_own_report_v1.stop_new = (uint32_t)r2_own_stopped_v1();
    memcpy(out, &r2_own_report_v1, sizeof(*out));
    InterlockedExchange(&r2_own_guard_v1, 0);
    return R2_OWN_OK;
}
#endif
