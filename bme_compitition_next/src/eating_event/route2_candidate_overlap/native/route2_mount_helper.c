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

/* C03-B1 raw FILE PE dependency parser. SOURCE ONLY; no system calls.
 * This append is independent of the dormant v2 and owned-child components.
 */
#if defined(R2_TARGET_WINDOWS_SEED)
#ifndef R2_PE_PRELOAD_RAW_V1_BODY
#define R2_PE_PRELOAD_RAW_V1_BODY
_Static_assert(sizeof(uintptr_t) == 8 && sizeof(size_t) == 8,
               "raw PE parser requires native AMD64 sizes");
_Static_assert(sizeof(struct r2_pe_raw_section_v1) == 24 &&
               sizeof(struct r2_pe_raw_descriptor_v1) == 72 &&
               sizeof(struct r2_pe_raw_symbol_v1) == 48 &&
               sizeof(struct r2_pe_raw_tls_v1) == 80 &&
               sizeof(struct r2_pe_raw_callback_v1) == 24,
               "raw PE fact layout changed");
_Static_assert(sizeof(struct r2_pe_raw_report_v1) == R2_PE_RAW_REPORT_BYTES &&
               offsetof(struct r2_pe_raw_report_v1, directories) == 112 &&
               offsetof(struct r2_pe_raw_report_v1, symbols) == 11760 &&
               offsetof(struct r2_pe_raw_report_v1, tls) == 208368,
               "raw PE fixed report ABI changed");
struct r2_pe_context_v1 {
    const unsigned char *file;
    uint64_t length;
    struct r2_pe_raw_report_v1 *r;
};
static int r2_pe_fail_v1(struct r2_pe_context_v1 *c, uint32_t status,
                         uint32_t reason, uint64_t offset)
{
    if (c->r->reason == R2_PE_REASON_NONE) {
        c->r->raw_status = status;
        c->r->reason = reason;
        c->r->failure_offset = offset;
    }
    return 0;
}
static int r2_pe_bad_v1(struct r2_pe_context_v1 *c, uint32_t reason, uint64_t off)
{
    return r2_pe_fail_v1(c, R2_PE_RAW_REJECTED, reason, off);
}
static int r2_pe_limit_v1(struct r2_pe_context_v1 *c, uint32_t reason, uint64_t off)
{
    return r2_pe_fail_v1(c, R2_PE_RAW_INCOMPLETE, reason, off);
}
static int r2_pe_charge_v1(struct r2_pe_context_v1 *c, uint64_t n, uint64_t off)
{
    if (n > R2_PE_RAW_WORK_LIMIT - c->r->work_units)
        return r2_pe_limit_v1(c, R2_PE_REASON_WORK_LIMIT, off);
    c->r->work_units += n;
    return 1;
}
static int r2_pe_file_range_v1(struct r2_pe_context_v1 *c, uint64_t off, uint64_t n)
{
    if (off > c->length || n > c->length - off)
        return r2_pe_bad_v1(c, R2_PE_REASON_TRUNCATED, off);
    return 1;
}
/* All untrusted integer decoding is byte-wise, explicitly little endian. */
static int r2_pe_read_v1(struct r2_pe_context_v1 *c, uint64_t off,
                         uint32_t n, uint64_t *v)
{
    uint32_t i;
    uint64_t x = 0;
    if (!r2_pe_file_range_v1(c, off, n) || !r2_pe_charge_v1(c, n, off)) return 0;
    for (i = 0; i < n; ++i) x |= (uint64_t)c->file[(size_t)(off + i)] << (8u * i);
    *v = x;
    return 1;
}
static int r2_pe_u32_v1(struct r2_pe_context_v1 *c, uint64_t off, uint32_t *v)
{
    uint64_t x;
    if (!r2_pe_read_v1(c, off, 4, &x)) return 0;
    *v = (uint32_t)x;
    return 1;
}
/* The single RVA mapper. It returns one FILE-backed contiguous span. It never
 * stitches sections, invents zero-fill, or resolves aliases. Every section
 * candidate is charged even when a header/earlier section already matches.
 */
static int r2_pe_map_v1(struct r2_pe_context_v1 *c, uint32_t rva, uint64_t n,
                        uint32_t *offset, uint32_t *available)
{
    uint32_t i, matches = 0, zero = 0, off = 0, span = 0;
    uint64_t image = c->r->size_of_image;
    if (!n || rva >= image || n > image - rva)
        return r2_pe_bad_v1(c, R2_PE_REASON_RVA_OVERFLOW, rva);
    if (!r2_pe_charge_v1(c, 1, rva)) return 0;
    if (rva < c->r->size_of_headers) {
        ++matches; off = rva; span = c->r->size_of_headers - rva;
    }
    for (i = 0; i < c->r->section_count; ++i) {
        const struct r2_pe_raw_section_v1 *s = &c->r->sections[i];
        uint32_t d;
        if (!r2_pe_charge_v1(c, 1, rva)) return 0;
        if (rva < s->rva || (uint64_t)rva - s->rva >= s->virtual_extent) continue;
        d = rva - s->rva;
        if (d >= s->raw_size) { zero = 1; continue; }
        ++matches; off = s->raw_offset + d;
        span = s->raw_size - d;
        if (span > s->virtual_extent - d) span = s->virtual_extent - d;
    }
    if (matches > 1) return r2_pe_bad_v1(c, R2_PE_REASON_SECTION_OVERLAP, rva);
    if (!matches) return r2_pe_bad_v1(c,
        zero ? R2_PE_REASON_ZERO_FILL : R2_PE_REASON_RVA_UNMAPPED, rva);
    if (n > span) return r2_pe_bad_v1(c, R2_PE_REASON_SPAN_CROSSING, rva);
    if (!r2_pe_file_range_v1(c, off, span)) return 0;
    *offset = off;
    if (available) *available = span;
    return 1;
}
static int r2_pe_name_v1(struct r2_pe_context_v1 *c, uint32_t rva,
                         struct r2_pe_raw_name_v1 *name)
{
    uint32_t off, span, i;
    if (!r2_pe_map_v1(c, rva, 1, &off, &span)) return 0;
    for (i = 0; i < span && i < R2_PE_RAW_NAME_LIMIT; ++i) {
        unsigned char b;
        if (c->r->names_inspected_bytes == R2_PE_RAW_NAME_BYTES_LIMIT)
            return r2_pe_limit_v1(c, R2_PE_REASON_NAME_BYTES_LIMIT, off + i);
        if (!r2_pe_charge_v1(c, 1, off + i)) return 0;
        ++c->r->names_inspected_bytes;
        b = c->file[off + i];
        if (b == 0) {
            if (!i) return r2_pe_bad_v1(c, R2_PE_REASON_EMPTY_NAME, off);
            name->file_offset = off; name->length = i;
            return 1;
        }
    }
    if (i == R2_PE_RAW_NAME_LIMIT)
        return r2_pe_limit_v1(c, R2_PE_REASON_NAME_LIMIT, off + i);
    return r2_pe_bad_v1(c, R2_PE_REASON_NAME_TERMINATOR, off + i);
}
static int r2_pe_dir_v1(struct r2_pe_context_v1 *c, uint32_t index,
                        uint32_t minimum, uint32_t *off, uint32_t *size)
{
    const struct r2_pe_raw_directory_v1 *d = &c->r->directories[index];
    *off = 0; *size = d->size;
    if (!d->rva && !d->size) return 1;
    if (!d->rva || d->size < minimum)
        return r2_pe_bad_v1(c, R2_PE_REASON_DIRECTORY, d->rva);
    return r2_pe_map_v1(c, d->rva, d->size, off, NULL);
}
static int r2_pe_power2_v1(uint32_t x) { return x && !(x & (x - 1u)); }
static int r2_pe_headers_v1(struct r2_pe_context_v1 *c)
{
    uint64_t x, pe, opt, table;
    uint32_t count, optional_size, dirs, i, j, section_align, file_align;
    if (!r2_pe_read_v1(c, 0, 2, &x)) return 0;
    if (x != 0x5A4Du) return r2_pe_bad_v1(c, R2_PE_REASON_DOS, 0);
    if (!r2_pe_file_range_v1(c, 0, 64) || !r2_pe_read_v1(c, 0x3C, 4, &pe)) return 0;
    if (pe < 64) return r2_pe_bad_v1(c, R2_PE_REASON_PE_SIGNATURE, pe);
    if (!r2_pe_file_range_v1(c, pe, 24) || !r2_pe_read_v1(c, pe, 4, &x)) return 0;
    if (x != 0x00004550u) return r2_pe_bad_v1(c, R2_PE_REASON_PE_SIGNATURE, pe);
    if (!r2_pe_read_v1(c, pe + 4, 2, &x)) return 0;
    if (x != 0x8664u) return r2_pe_bad_v1(c, R2_PE_REASON_MACHINE, pe + 4);
    if (!r2_pe_read_v1(c, pe + 6, 2, &x)) return 0;
    count = (uint32_t)x;
    if (!count || count > R2_PE_RAW_SECTION_LIMIT)
        return r2_pe_limit_v1(c, R2_PE_REASON_SECTION_LIMIT, pe + 6);
    if (!r2_pe_read_v1(c, pe + 20, 2, &x)) return 0;
    optional_size = (uint32_t)x; opt = pe + 24;
    if (optional_size < 112)
        return r2_pe_bad_v1(c, R2_PE_REASON_OPTIONAL_HEADER, pe + 20);
    if (!r2_pe_file_range_v1(c, opt, optional_size) || !r2_pe_read_v1(c, opt, 2, &x)) return 0;
    if (x != 0x20Bu) return r2_pe_bad_v1(c, R2_PE_REASON_OPTIONAL_HEADER, opt);
    if (!r2_pe_read_v1(c, opt + 24, 8, &c->r->image_base) ||
        !r2_pe_u32_v1(c, opt + 16, &c->r->entrypoint_rva) ||
        !r2_pe_u32_v1(c, opt + 32, &section_align) ||
        !r2_pe_u32_v1(c, opt + 36, &file_align) ||
        !r2_pe_u32_v1(c, opt + 56, &c->r->size_of_image) ||
        !r2_pe_u32_v1(c, opt + 60, &c->r->size_of_headers) ||
        !r2_pe_u32_v1(c, opt + 108, &dirs)) return 0;
    c->r->optional_directory_count = dirs;
    if (dirs > 16 || dirs > (optional_size - 112u) / 8u)
        return r2_pe_bad_v1(c, R2_PE_REASON_OPTIONAL_HEADER, opt + 108);
    if (!r2_pe_power2_v1(section_align) || !r2_pe_power2_v1(file_align) ||
        section_align < file_align ||
        (section_align < 4096 ? file_align != section_align :
          (file_align < 512 || file_align > 65536)) ||
        !c->r->size_of_image || c->r->size_of_image % section_align ||
        !c->r->size_of_headers || c->r->size_of_headers % file_align)
        return r2_pe_bad_v1(c, R2_PE_REASON_ALIGNMENT, opt + 32);
    table = opt + optional_size;
    if (!r2_pe_file_range_v1(c, table, (uint64_t)count * 40)) return 0;
    if (c->r->size_of_headers > c->length ||
        c->r->size_of_headers > c->r->size_of_image ||
        table + (uint64_t)count * 40 > c->r->size_of_headers ||
        c->r->image_base > UINT64_MAX - c->r->size_of_image ||
        c->r->entrypoint_rva >= c->r->size_of_image)
        return r2_pe_bad_v1(c, R2_PE_REASON_SECTION_RANGE, opt + 56);
    for (i = 0; i < dirs; ++i) {
        if (!r2_pe_u32_v1(c, opt + 112 + i * 8, &c->r->directories[i].rva) ||
            !r2_pe_u32_v1(c, opt + 116 + i * 8, &c->r->directories[i].size)) return 0;
        ++c->r->directory_count;
    }
    for (i = 0; i < count; ++i) {
        struct r2_pe_raw_section_v1 *s = &c->r->sections[i];
        uint64_t at = table + (uint64_t)i * 40, vend, rend;
        if (!r2_pe_u32_v1(c, at + 8, &s->virtual_size) ||
            !r2_pe_u32_v1(c, at + 12, &s->rva) ||
            !r2_pe_u32_v1(c, at + 16, &s->raw_size) ||
            !r2_pe_u32_v1(c, at + 20, &s->raw_offset) ||
            !r2_pe_u32_v1(c, at + 36, &s->characteristics)) return 0;
        s->virtual_extent = s->virtual_size > s->raw_size ? s->virtual_size : s->raw_size;
        vend = (uint64_t)s->rva + s->virtual_extent;
        rend = (uint64_t)s->raw_offset + s->raw_size;
        if (vend > UINT32_MAX || vend > c->r->size_of_image ||
            rend > UINT32_MAX || rend > c->length)
            return r2_pe_bad_v1(c, R2_PE_REASON_SECTION_RANGE, at + 8);
        if ((s->virtual_extent && s->rva < c->r->size_of_headers) ||
            (s->raw_size && s->raw_offset < c->r->size_of_headers))
            return r2_pe_bad_v1(c, R2_PE_REASON_HEADER_OVERLAP, at + 12);
        if (s->rva % section_align || (s->raw_size &&
            (s->raw_offset % file_align || s->raw_size % file_align ||
             (section_align < 4096 && s->raw_offset != s->rva))))
            return r2_pe_bad_v1(c, R2_PE_REASON_ALIGNMENT, at + 12);
        for (j = 0; j < i; ++j) {
            const struct r2_pe_raw_section_v1 *p = &c->r->sections[j];
            if (!r2_pe_charge_v1(c, 1, at)) return 0;
            if ((s->virtual_extent && p->virtual_extent &&
                 s->rva < (uint64_t)p->rva + p->virtual_extent && p->rva < vend) ||
                (s->raw_size && p->raw_size &&
                 s->raw_offset < (uint64_t)p->raw_offset + p->raw_size && p->raw_offset < rend))
                return r2_pe_bad_v1(c, R2_PE_REASON_SECTION_OVERLAP, at);
        }
        ++c->r->section_count;
    }
    return 1;
}
/* Lookup and IAT advance in lockstep and must each terminate. The lookup is
 * never replaced by IAT contents. Supported normal IATs are unbound copies of
 * their lookup tables. Delay IATs may contain different nonzero stub addresses.
 * Optional bound tables terminate in lockstep; unload tables are exact copies
 * of the original on-disk delay IAT, including the zero terminator.
 */
static int r2_pe_thunks_v1(struct r2_pe_context_v1 *c, uint32_t di)
{
    struct r2_pe_raw_descriptor_v1 *d = &c->r->descriptors[di];
    uint32_t lo, ls, io, is, bo = 0, bs = 0, uo = 0, us = 0, i;
    if (!d->lookup_rva) return r2_pe_bad_v1(c, R2_PE_REASON_LOOKUP_ABSENT, d->descriptor_offset);
    if (!d->iat_rva) return r2_pe_bad_v1(c, R2_PE_REASON_DIRECTORY, d->descriptor_offset);
    if (!r2_pe_map_v1(c, d->lookup_rva, 8, &lo, &ls) ||
        !r2_pe_map_v1(c, d->iat_rva, 8, &io, &is)) return 0;
    if (d->bound_rva && !r2_pe_map_v1(c, d->bound_rva, 8, &bo, &bs)) return 0;
    if (d->unload_rva && !r2_pe_map_v1(c, d->unload_rva, 8, &uo, &us)) return 0;
    for (i = 0; ; ++i) {
        uint64_t lookup, iat, bound = 0, unload = 0, step = (uint64_t)i * 8;
        struct r2_pe_raw_symbol_v1 *s;
        if (step + 8 > ls)
            return r2_pe_bad_v1(c, R2_PE_REASON_THUNK_TERMINATOR, lo + step);
        if (step + 8 > is)
            return r2_pe_bad_v1(c, R2_PE_REASON_IAT_TERMINATOR, io + step);
        if (!r2_pe_read_v1(c, lo + step, 8, &lookup) ||
            !r2_pe_read_v1(c, io + step, 8, &iat)) return 0;
        if (d->bound_rva) {
            if (step + 8 > bs)
                return r2_pe_bad_v1(c, R2_PE_REASON_BOUND_TERMINATOR, bo + step);
            if (!r2_pe_read_v1(c, bo + step, 8, &bound)) return 0;
        }
        if (d->unload_rva) {
            if (step + 8 > us)
                return r2_pe_bad_v1(c, R2_PE_REASON_UNLOAD_CONTENT, uo + step);
            if (!r2_pe_read_v1(c, uo + step, 8, &unload)) return 0;
        }
        if (!lookup) {
            d->lookup_terminated = 1; d->valid_fields |= 4u;
            if (iat) return r2_pe_bad_v1(c, R2_PE_REASON_IAT_TERMINATOR, io + step);
            if (d->bound_rva && bound)
                return r2_pe_bad_v1(c, R2_PE_REASON_BOUND_TERMINATOR, bo + step);
            if (d->unload_rva && unload)
                return r2_pe_bad_v1(c, R2_PE_REASON_UNLOAD_CONTENT, uo + step);
            return 1;
        }
        if (c->r->symbol_count == R2_PE_RAW_SYMBOL_LIMIT)
            return r2_pe_limit_v1(c, R2_PE_REASON_SYMBOL_LIMIT, lo + step);
        s = &c->r->symbols[c->r->symbol_count++];
        ++d->symbol_count;
        s->descriptor_index = di; s->thunk_offset = lo + (uint32_t)step;
        s->iat_offset = io + (uint32_t)step; s->raw_lookup = lookup; s->raw_iat = iat;
        if (!iat) return r2_pe_bad_v1(c, R2_PE_REASON_IAT_TERMINATOR, io + step);
        if (d->kind == R2_PE_IMPORT_NORMAL && iat != lookup)
            return r2_pe_bad_v1(c, R2_PE_REASON_IAT_CONTENT, io + step);
        if (d->bound_rva && !bound)
            return r2_pe_bad_v1(c, R2_PE_REASON_BOUND_TERMINATOR, bo + step);
        if (d->unload_rva && unload != iat)
            return r2_pe_bad_v1(c, R2_PE_REASON_UNLOAD_CONTENT, uo + step);
        if (lookup & UINT64_C(0x8000000000000000)) {
            if (lookup & UINT64_C(0x7FFFFFFFFFFF0000))
                return r2_pe_bad_v1(c, R2_PE_REASON_ORDINAL_BITS, lo + step);
            s->ordinal = (uint32_t)(lookup & 0xFFFFu); s->kind = R2_PE_SYMBOL_ORDINAL;
        } else {
            struct r2_pe_raw_name_v1 name;
            uint32_t no;
            uint64_t hint;
            /* PE32+ named lookup RVAs use only bits 30..0. */
            if (lookup > UINT64_C(0x7FFFFFFF))
                return r2_pe_bad_v1(c, R2_PE_REASON_NAME_RVA_BITS, lo + step);
            if (!r2_pe_map_v1(c, (uint32_t)lookup, 3, &no, NULL) ||
                !r2_pe_read_v1(c, no, 2, &hint)) return 0;
            s->hint = (uint32_t)hint;
            if (!r2_pe_name_v1(c, (uint32_t)lookup + 2u, &name)) return 0;
            s->name_offset = name.file_offset; s->name_length = name.length;
            s->kind = R2_PE_SYMBOL_NAME;
        }
    }
}
static int r2_pe_imports_v1(struct r2_pe_context_v1 *c, uint32_t delay)
{
    uint32_t off, size, cursor, width = delay ? 32u : 20u;
    if (!r2_pe_dir_v1(c, delay ? 13u : 1u, width, &off, &size)) return 0;
    if (!size) return 1;
    for (cursor = 0; ; cursor += width) {
        uint32_t f[8] = {0}, i, any = 0, di;
        struct r2_pe_raw_descriptor_v1 *d;
        if (cursor > size || width > size - cursor)
            return r2_pe_bad_v1(c, R2_PE_REASON_DESCRIPTOR_TERMINATOR, (uint64_t)off + cursor);
        for (i = 0; i < width / 4; ++i) {
            if (!r2_pe_u32_v1(c, (uint64_t)off + cursor + i * 4, &f[i])) return 0;
            any |= f[i];
        }
        if (!any) return 1;
        if (c->r->descriptor_count == R2_PE_RAW_DESCRIPTOR_LIMIT)
            return r2_pe_limit_v1(c, R2_PE_REASON_DESCRIPTOR_LIMIT, (uint64_t)off + cursor);
        di = c->r->descriptor_count++;
        d = &c->r->descriptors[di];
        d->kind = delay ? R2_PE_IMPORT_DELAY : R2_PE_IMPORT_NORMAL;
        d->valid_fields = 1; d->descriptor_offset = off + cursor;
        d->first_symbol = c->r->symbol_count;
        if (delay) {
            uint32_t unused;
            ++c->r->delay_count;
            d->attributes = f[0]; d->module_handle_rva = f[2];
            d->iat_rva = f[3]; d->lookup_rva = f[4];
            d->bound_rva = f[5]; d->unload_rva = f[6]; d->time_stamp = f[7];
            if (f[0] & ~1u) return r2_pe_bad_v1(c, R2_PE_REASON_DELAY_ATTRIBUTES, off + cursor);
            if (!(f[0] & 1u)) return r2_pe_bad_v1(c, R2_PE_REASON_DELAY_LEGACY_VA, off + cursor);
            if (!d->module_handle_rva)
                return r2_pe_bad_v1(c, R2_PE_REASON_DELAY_HANDLE, off + cursor + 8);
            if (!r2_pe_map_v1(c, d->module_handle_rva, 8, &unused, NULL)) return 0;
        } else {
            ++c->r->normal_count;
            d->lookup_rva = f[0]; d->time_stamp = f[1]; d->forwarder_chain = f[2]; d->iat_rva = f[4];
            if (f[1] || f[2]) return r2_pe_bad_v1(c, R2_PE_REASON_BOUND_UNSUPPORTED, off + cursor + 4);
        }
        if (!(delay ? f[1] : f[3])) return r2_pe_bad_v1(c, R2_PE_REASON_DIRECTORY, off + cursor);
        if (!r2_pe_name_v1(c, delay ? f[1] : f[3], &d->dll_name)) return 0;
        d->valid_fields |= 2u;
        if (!r2_pe_thunks_v1(c, di)) return 0;
    }
}
static int r2_pe_va_v1(struct r2_pe_context_v1 *c, uint64_t va,
                       uint32_t endpoint, uint32_t *rva, uint64_t field)
{
    uint64_t delta;
    if (va < c->r->image_base) return r2_pe_bad_v1(c, R2_PE_REASON_TLS_VA, field);
    delta = va - c->r->image_base;
    if (delta > UINT32_MAX || delta > c->r->size_of_image ||
        (!endpoint && delta == c->r->size_of_image))
        return r2_pe_bad_v1(c, R2_PE_REASON_TLS_VA, field);
    *rva = (uint32_t)delta;
    return 1;
}
static int r2_pe_tls_v1(struct r2_pe_context_v1 *c)
{
    struct r2_pe_raw_tls_v1 *t = &c->r->tls;
    uint32_t off, size, start, end, rva, po, span, i;
    if (!r2_pe_dir_v1(c, 9, 40, &off, &size)) return 0;
    if (!size) return 1;
    t->present = 1; t->directory_offset = off; t->directory_size = size;
    if (!r2_pe_read_v1(c, off, 8, &t->raw_start_va) ||
        !r2_pe_read_v1(c, off + 8, 8, &t->raw_end_va) ||
        !r2_pe_read_v1(c, off + 16, 8, &t->index_va) ||
        !r2_pe_read_v1(c, off + 24, 8, &t->callbacks_va) ||
        !r2_pe_u32_v1(c, off + 32, &t->zero_fill) ||
        !r2_pe_u32_v1(c, off + 36, &t->characteristics)) return 0;
    t->fields_valid = 1;
    if ((!t->raw_start_va) != (!t->raw_end_va) || t->raw_end_va < t->raw_start_va)
        return r2_pe_bad_v1(c, R2_PE_REASON_TLS_TEMPLATE, off);
    if (t->raw_start_va) {
        if (!r2_pe_va_v1(c, t->raw_start_va, 1, &start, off) ||
            !r2_pe_va_v1(c, t->raw_end_va, 1, &end, off + 8)) return 0;
        t->template_bytes = end - start;
        if (t->template_bytes && !r2_pe_map_v1(c, start, t->template_bytes, &t->template_offset, NULL)) return 0;
    }
    if (!t->index_va) return r2_pe_bad_v1(c, R2_PE_REASON_TLS_VA, off + 16);
    if (!r2_pe_va_v1(c, t->index_va, 0, &rva, off + 16) ||
        !r2_pe_map_v1(c, rva, 4, &t->index_offset, NULL)) return 0;
    /* A zero address is absence, not an observed array terminator. */
    if (!t->callbacks_va) return 1;
    if (!r2_pe_va_v1(c, t->callbacks_va, 0, &rva, off + 24) ||
        !r2_pe_map_v1(c, rva, 8, &po, &span)) return 0;
    for (i = 0; ; ++i) {
        uint64_t va, step = (uint64_t)i * 8;
        struct r2_pe_raw_callback_v1 *cb;
        if (step + 8 > span)
            return r2_pe_bad_v1(c, R2_PE_REASON_TLS_TERMINATOR, po + step);
        if (!r2_pe_read_v1(c, po + step, 8, &va)) return 0;
        if (!va) { t->callbacks_terminated = 1; return 1; }
        if (i == R2_PE_RAW_TLS_CALLBACK_LIMIT)
            return r2_pe_limit_v1(c, R2_PE_REASON_TLS_CALLBACK_LIMIT, po + step);
        cb = &c->r->callbacks[t->callback_count++];
        cb->raw_va = va; cb->pointer_offset = po + (uint32_t)step;
        if (!r2_pe_va_v1(c, va, 0, &cb->target_rva, po + step) ||
            !r2_pe_map_v1(c, cb->target_rva, 1, &cb->target_offset, NULL)) return 0;
    }
}
uint32_t route2_pe_preload_parse_raw_v1(
    const unsigned char *file, size_t file_size, uint32_t report_abi,
    struct r2_pe_raw_report_v1 *out, size_t out_size)
{
    uintptr_t in_begin = (uintptr_t)file, out_begin = (uintptr_t)out;
    uintptr_t in_end, out_end;
    size_t i;
    unsigned char *clear;
    struct r2_pe_context_v1 c;
    uint32_t unused, size;
    /* No output bytes are touched before all integer ranges, ABI, alignment
     * and disjointness checks. The caller still owns accessibility/stability.
     */
    if (!file || !out || report_abi != R2_PE_RAW_ABI ||
        out_size != R2_PE_RAW_REPORT_BYTES ||
        out_begin % _Alignof(struct r2_pe_raw_report_v1) ||
        file_size > UINTPTR_MAX - in_begin || out_size > UINTPTR_MAX - out_begin)
        return R2_PE_RAW_BAD_ARGUMENT;
    in_end = in_begin + file_size; out_end = out_begin + out_size;
    if (file_size && in_begin < out_end && out_begin < in_end) return R2_PE_RAW_BAD_ARGUMENT;
    clear = (unsigned char *)out;
    for (i = 0; i < out_size; ++i) clear[i] = 0;
    out->abi = R2_PE_RAW_ABI; out->size = R2_PE_RAW_REPORT_BYTES;
    out->raw_status = R2_PE_RAW_REJECTED;
    out->preload_scope = R2_PE_PRELOAD_CLOSURE_UNPROVEN;
    out->file_bytes = file_size;
    c.file = file; c.length = file_size; c.r = out;
    if (file_size > R2_PE_RAW_FILE_LIMIT) {
        r2_pe_limit_v1(&c, R2_PE_REASON_FILE_LIMIT, 0); return out->raw_status;
    }
    if (!r2_pe_headers_v1(&c)) return out->raw_status;
    /* A bound import directory is retained but is unsupported by this parser.
     * It must never cause a resolved address to be decoded as a spelling.
     */
    if (out->directories[11].rva || out->directories[11].size) {
        r2_pe_bad_v1(&c, R2_PE_REASON_BOUND_UNSUPPORTED, out->directories[11].rva);
        return out->raw_status;
    }
    if (!r2_pe_dir_v1(&c, 12, 8, &unused, &size) ||
        !r2_pe_imports_v1(&c, 0) || !r2_pe_imports_v1(&c, 1) || !r2_pe_tls_v1(&c))
        return out->raw_status;
    out->structural_complete = 1;
    out->raw_status = R2_PE_RAW_COMPLETE;
    if (out->tls.callback_count) {
        out->raw_status = R2_PE_RAW_APPLICATION_TLS_PRESENT;
        out->reason = R2_PE_REASON_APPLICATION_TLS_PRESENT;
        out->failure_offset = out->tls.directory_offset;
    }
    return out->raw_status;
}
#endif
#endif

/* C03 original-FILE ELF64 raw profile. SOURCE ONLY, UNCOMPILED / UNRUN.
 * No path lookup, allocation, OS call, constructor, resolver or authority.
 * Every helper in this independent suffix is Linux-start only.
 * GNU numeric format tags additionally cross-checked against public glibc
 * https://raw.githubusercontent.com/bminor/glibc/glibc-2.35/elf/elf.h
 * This does not establish installed headers or loader behavior.
 */
#if defined(R2_TARGET_LINUX_START)
#ifndef R2_ELF_PRELOAD_RAW_V1_DEFINED
#define R2_ELF_PRELOAD_RAW_V1_DEFINED
#if !defined(__STDC_VERSION__) || __STDC_VERSION__ < 201112L
#error "The bounded ELF raw parser requires C11"
#endif
_Static_assert(sizeof(struct r2_elf_raw_program_v1) == 64, "ELF program record ABI");
_Static_assert(sizeof(struct r2_elf_raw_dynamic_v1) == 32, "ELF dynamic record ABI");
_Static_assert(sizeof(struct r2_elf_raw_string_v1) == 32, "ELF string record ABI");
_Static_assert(offsetof(struct r2_elf_raw_report_v1, programs) == 256, "ELF report prefix ABI");
_Static_assert(sizeof(struct r2_elf_raw_report_v1) == R2_ELF_RAW_REPORT_BYTES, "ELF report ABI");
_Static_assert(R2_ELF_RAW_REPORT_BYTES < R2_ELF_RAW_WORK_LIMIT, "ELF initialization reservation");
struct r2_elf_context_v1 {
    const unsigned char *file;
    size_t length;
    struct r2_elf_raw_report_v1 *r;
};
static int r2_elf_fail_v1(struct r2_elf_context_v1 *c, uint32_t status,
    uint32_t reason, uint64_t field, uint64_t value, uint32_t kind, uint32_t subject)
{
    if (!c->r->reason) {
        c->r->reason = reason; c->r->failure_offset = field;
        c->r->failure_value = value; c->r->failure_value_kind = kind;
        c->r->failure_subject_type = subject;
    }
    c->r->raw_status = status;
    return 0;
}
static int r2_elf_charge_v1(struct r2_elf_context_v1 *c, uint64_t units, uint64_t off)
{
    if (units > R2_ELF_RAW_WORK_LIMIT ||
        c->r->work_units > R2_ELF_RAW_WORK_LIMIT - units)
        return r2_elf_fail_v1(c, R2_ELF_RAW_INCOMPLETE, R2_ELF_REASON_WORK_LIMIT,
                            off, units, R2_ELF_VALUE_SCALAR, 0);
    c->r->work_units += units;
    return 1;
}
static int r2_elf_range_v1(struct r2_elf_context_v1 *c, uint64_t off,
                         uint64_t n, uint64_t field)
{
    if (!r2_elf_charge_v1(c, 16, field)) return 0;
    if (off > c->length || n > (uint64_t)c->length - off)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_TRUNCATED,
                            field, off, R2_ELF_VALUE_FILE_OFFSET, 0);
    return 1;
}
/* Reads reserve loop, shifts and byte inspections before the first access.
 * No host-endian/unaligned casts and no access to a virtual zero-fill byte.
 */
static int r2_elf_read_v1(struct r2_elf_context_v1 *c, uint64_t off,
                        uint32_t n, uint64_t *value)
{
    uint32_t i;
    uint64_t v = 0;
    if (!r2_elf_charge_v1(c, 16u + (uint64_t)n * 4u, off) ||
        !r2_elf_range_v1(c, off, n, off)) return 0;
    for (i = 0; i < n; ++i) v |= (uint64_t)c->file[(size_t)off + i] << (8u * i);
    *value = v;
    return 1;
}
static int r2_elf_map_v1(struct r2_elf_context_v1 *c, uint64_t va,
    uint64_t n, uint64_t field, uint32_t subject, uint64_t *file_off)
{
    uint32_t i, hits = 0;
    const struct r2_elf_raw_program_v1 *found = NULL;
    uint64_t end, delta;
    if (!r2_elf_charge_v1(c, 32, field)) return 0;
    if (!n || n > UINT64_MAX - va)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_VIRTUAL_OVERFLOW,
                            field, va, R2_ELF_VALUE_VIRTUAL_ADDRESS, subject);
    end = va + n;
    for (i = 0; i < c->r->program_count; ++i) {
        const struct r2_elf_raw_program_v1 *p;
        if (!r2_elf_charge_v1(c, 64, field)) return 0;
        p = &c->r->programs[i];
        if (p->type != 1 || !p->memory_size) continue;
        /* LOAD virtual ends were already checked. Count ANY intersection,
         * not merely fully containing candidates, to reject ambiguity.
         */
        if (va < p->virtual_address + p->memory_size && p->virtual_address < end) {
            ++hits; found = p;
        }
    }
    if (hits > 1)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_AMBIGUOUS_MAPPING,
                            field, va, R2_ELF_VALUE_VIRTUAL_ADDRESS, subject);
    if (!found)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_UNMAPPED,
                            field, va, R2_ELF_VALUE_VIRTUAL_ADDRESS, subject);
    if (va < found->virtual_address || end > found->virtual_address + found->memory_size)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_SPAN_CROSSING,
                            field, va, R2_ELF_VALUE_VIRTUAL_ADDRESS, subject);
    delta = va - found->virtual_address;
    if (delta >= found->file_size || n > found->file_size - delta)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_ZERO_FILL,
                            field, va, R2_ELF_VALUE_VIRTUAL_ADDRESS, subject);
    /* file_offset+file_size was checked against the bounded FILE. */
    *file_off = found->file_offset + delta;
    return r2_elf_range_v1(c, *file_off, n, field);
}
static int r2_elf_header_v1(struct r2_elf_context_v1 *c)
{
    uint64_t v, cls, enc, version, osabi, abiver, machine, kind, ehsize, phsize;
    if (!r2_elf_range_v1(c, 0, 64, 0) ||
        !r2_elf_read_v1(c, 0, 4, &v)) return 0;
    if (v != UINT64_C(0x464c457f))
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_MAGIC,
                            0, v, R2_ELF_VALUE_SCALAR, 0);
    if (!r2_elf_read_v1(c, 4, 1, &cls) || !r2_elf_read_v1(c, 5, 1, &enc) ||
        !r2_elf_read_v1(c, 6, 1, &version) || !r2_elf_read_v1(c, 7, 1, &osabi) ||
        !r2_elf_read_v1(c, 8, 1, &abiver)) return 0;
    if (cls != 2)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_CLASS,
                            4, cls, R2_ELF_VALUE_SCALAR, 0);
    if (enc != 1)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_ENCODING,
                            5, enc, R2_ELF_VALUE_SCALAR, 0);
    if (version != 1)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_VERSION,
                            6, version, R2_ELF_VALUE_SCALAR, 0);
    if ((osabi != 0 && osabi != 3) || abiver != 0)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_OSABI,
                            abiver ? 8 : 7, abiver ? abiver : osabi, R2_ELF_VALUE_SCALAR, 0);
    if (!r2_elf_read_v1(c, 16, 2, &kind) || !r2_elf_read_v1(c, 18, 2, &machine) ||
        !r2_elf_read_v1(c, 20, 4, &version)) return 0;
    c->r->elf_type = (uint32_t)kind;
    if ((kind != 2 && kind != 3) || machine != 62)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_TARGET,
                            machine != 62 ? 18 : 16, machine != 62 ? machine : kind,
                            R2_ELF_VALUE_SCALAR, 0);
    if (version != 1)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_VERSION,
                            20, version, R2_ELF_VALUE_SCALAR, 0);
    if (!r2_elf_read_v1(c, 24, 8, &c->r->entry) ||
        !r2_elf_read_v1(c, 32, 8, &c->r->program_table_offset) ||
        !r2_elf_read_v1(c, 48, 4, &v)) return 0;
    c->r->elf_flags = (uint32_t)v;
    if (!r2_elf_read_v1(c, 52, 2, &ehsize) || !r2_elf_read_v1(c, 54, 2, &phsize) ||
        !r2_elf_read_v1(c, 56, 2, &v)) return 0;
    c->r->declared_phnum = (uint32_t)v;
    if (ehsize != 64)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_HEADER_SIZE,
                            52, ehsize, R2_ELF_VALUE_SCALAR, 0);
    if (phsize != 56)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_PROGRAM_ENTRY_SIZE,
                            54, phsize, R2_ELF_VALUE_SCALAR, 0);
    if (v == 65535)
        return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_EXTENDED_COUNT,
                            56, v, R2_ELF_VALUE_SCALAR, 0);
    if (v > R2_ELF_RAW_PROGRAM_LIMIT)
        return r2_elf_fail_v1(c, R2_ELF_RAW_INCOMPLETE, R2_ELF_REASON_PROGRAM_LIMIT,
                            56, v, R2_ELF_VALUE_SCALAR, 0);
    if (c->r->program_table_offset < 64 ||
        !r2_elf_range_v1(c, c->r->program_table_offset, v * 56u, 32)) {
        if (!c->r->reason) r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED,
            R2_ELF_REASON_PROGRAM_RANGE, 32, c->r->program_table_offset,
            R2_ELF_VALUE_FILE_OFFSET, 0);
        return 0;
    }
    c->r->header_valid = 1;
    return 1;
}
static int r2_elf_program_extent_v1(struct r2_elf_context_v1 *c,
                                  const struct r2_elf_raw_program_v1 *p)
{
    if (!r2_elf_range_v1(c, p->file_offset, p->file_size, p->header_offset + 8)) return 0;
    if (p->memory_size > UINT64_MAX - p->virtual_address)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_VIRTUAL_OVERFLOW,
            p->header_offset + 16, p->virtual_address, R2_ELF_VALUE_VIRTUAL_ADDRESS, p->type);
    return 1;
}
static int r2_elf_programs_v1(struct r2_elf_context_v1 *c)
{
    uint32_t i, j;
    uint64_t last_load = 0;
    for (i = 0; i < c->r->declared_phnum; ++i) {
        struct r2_elf_raw_program_v1 *p;
        uint64_t off = c->r->program_table_offset + (uint64_t)i * 56u, v;
        if (!r2_elf_charge_v1(c, 256, off)) return 0;
        p = &c->r->programs[c->r->program_count++]; p->header_offset = off;
        if (!r2_elf_read_v1(c, off, 4, &v)) return 0;
        p->type = (uint32_t)v;
        if (!r2_elf_read_v1(c, off + 4, 4, &v)) return 0;
        p->flags = (uint32_t)v;
        if (!r2_elf_read_v1(c, off + 8, 8, &p->file_offset) ||
            !r2_elf_read_v1(c, off + 16, 8, &p->virtual_address) ||
            !r2_elf_read_v1(c, off + 24, 8, &p->physical_address) ||
            !r2_elf_read_v1(c, off + 32, 8, &p->file_size) ||
            !r2_elf_read_v1(c, off + 40, 8, &p->memory_size) ||
            !r2_elf_read_v1(c, off + 48, 8, &p->alignment)) return 0;
        if (!p->type) continue; /* PT_NULL undefined fields are only raw facts. */
        if (!(p->type == 1 || p->type == 2 || p->type == 3 || p->type == 4 ||
              p->type == 6 || p->type == 7 ||
              p->type == UINT32_C(0x6474e550) || p->type == UINT32_C(0x6474e551) ||
              p->type == UINT32_C(0x6474e552) || p->type == UINT32_C(0x6474e553))) {
            /* Unknown semantics: retain exact fields without inventing ranges
             * or treating the entry as an ignorable/safe directory.
             */
            ++c->r->unknown_program_count;
            r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_UNKNOWN_PROGRAM,
                          off, p->type, R2_ELF_VALUE_SCALAR, p->type);
            continue;
        }
        if (p->type == 1) { /* PT_LOAD */
            if (!r2_elf_program_extent_v1(c, p)) return 0;
            if (p->file_size > p->memory_size)
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_LOAD_SIZE,
                    off + 32, p->file_size, R2_ELF_VALUE_SCALAR, p->type);
            if (p->alignment > 1 &&
                ((p->alignment & (p->alignment - 1)) ||
                 (p->virtual_address % p->alignment != p->file_offset % p->alignment)))
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_LOAD_ALIGNMENT,
                    off + 48, p->alignment, R2_ELF_VALUE_SCALAR, p->type);
            if (c->r->load_count && p->virtual_address < last_load)
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_LOAD_ORDER,
                    off + 16, p->virtual_address, R2_ELF_VALUE_VIRTUAL_ADDRESS, p->type);
            for (j = 0; j < i; ++j) {
                const struct r2_elf_raw_program_v1 *q;
                if (!r2_elf_charge_v1(c, 64, off)) return 0;
                q = &c->r->programs[j];
                if (q->type == 1 && p->memory_size && q->memory_size &&
                    p->virtual_address < q->virtual_address + q->memory_size &&
                    q->virtual_address < p->virtual_address + p->memory_size)
                    return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_LOAD_OVERLAP,
                        off + 16, p->virtual_address, R2_ELF_VALUE_VIRTUAL_ADDRESS, p->type);
            }
            last_load = p->virtual_address; ++c->r->load_count;
        } else if (p->type == 2) { /* PT_DYNAMIC */
            if (c->r->dynamic_present)
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_DUPLICATE_PROGRAM,
                    off, p->type, R2_ELF_VALUE_SCALAR, p->type);
            c->r->dynamic_present = 1; c->r->dynamic_offset = p->file_offset;
            c->r->dynamic_size = p->file_size;
        } else if (p->type == 3) { /* PT_INTERP */
            if (c->r->interpreter_present)
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_DUPLICATE_PROGRAM,
                    off, p->type, R2_ELF_VALUE_SCALAR, p->type);
            c->r->interpreter_present = 1; c->r->interpreter_offset = p->file_offset;
            c->r->interpreter_size = p->file_size;
            c->r->application_conditions |= R2_ELF_CONDITION_INTERPRETER;
            if (c->r->load_count)
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_INTERPRETER_ORDER,
                    off, p->type, R2_ELF_VALUE_SCALAR, p->type);
        } else if (p->type == 7) { /* PT_TLS presence, even empty. */
            if (c->r->tls_present)
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_DUPLICATE_PROGRAM,
                    off, p->type, R2_ELF_VALUE_SCALAR, p->type);
            c->r->tls_present = 1; c->r->tls_offset = p->file_offset;
            c->r->tls_filesz = p->file_size; c->r->tls_memsz = p->memory_size;
            c->r->application_conditions |= R2_ELF_CONDITION_TLS;
            if (p->file_size > p->memory_size)
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_LOAD_SIZE,
                    off + 32, p->file_size, R2_ELF_VALUE_SCALAR, p->type);
        } else if (p->type == 4 || p->type == 6 ||
                   p->type == UINT32_C(0x6474e550) || p->type == UINT32_C(0x6474e551) ||
                   p->type == UINT32_C(0x6474e552) || p->type == UINT32_C(0x6474e553)) {
            /* NOTE, PHDR, GNU EH_FRAME/STACK/RELRO/PROPERTY: raw only.
             * No content/permission/relocation/property semantics validated.
             */
        }
        /* Presence and declared ranges above survive a malformed extent.
         * LOADs are checked earlier, before any virtual overlap arithmetic.
         */
        if (p->type != 1 && !r2_elf_program_extent_v1(c, p)) return 0;
    }
    if (!c->r->load_count)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_NO_LOAD,
                            56, 0, R2_ELF_VALUE_SCALAR, 1);
    return 1;
}
/* Keys 1..43 fit one local singleton bitset; NEEDED is explicitly repeatable.
 * Recognized raw-only tags are NOT symbol/relocation/version validation.
 * Unlisted extensions (including FILTER/AUXILIARY/AUDIT/DEPAUDIT) are UNKNOWN,
 * retained in order and prevent structural_complete. No dependency is omitted
 * under a claim of complete dependency closure.
 */
static uint32_t r2_elf_tag_v1(uint64_t tag, uint32_t *meaning)
{
    *meaning = R2_ELF_DYNAMIC_RAW_ONLY;
    switch (tag) {
    case 0: *meaning = R2_ELF_DYNAMIC_TERMINATOR; return 0;
    case 1: *meaning = R2_ELF_DYNAMIC_STRING; return 0;
    case 5: case 10: *meaning = R2_ELF_DYNAMIC_TABLE; return (uint32_t)tag;
    case 14: case 15: case 29:
        *meaning = R2_ELF_DYNAMIC_STRING; return (uint32_t)tag;
    case 12: case 13: case 25: case 26: case 27: case 28: case 32: case 33:
        *meaning = R2_ELF_DYNAMIC_APPLICATION; return (uint32_t)tag;
    case 2: case 3: case 4: case 6: case 7: case 8: case 9: case 11:
    case 16: case 17: case 18: case 19: case 20: case 21: case 22: case 23:
    case 24: case 30: case 34:
        return (uint32_t)tag;
    case UINT64_C(0x6ffffef5): return 35; /* GNU_HASH */
    case UINT64_C(0x6ffffff0): return 36; /* VERSYM */
    case UINT64_C(0x6ffffff9): return 37; /* RELACOUNT */
    case UINT64_C(0x6ffffffa): return 38; /* RELCOUNT */
    case UINT64_C(0x6ffffffb): return 39; /* FLAGS_1 */
    case UINT64_C(0x6ffffffc): return 40; /* VERDEF */
    case UINT64_C(0x6ffffffd): return 41; /* VERDEFNUM */
    case UINT64_C(0x6ffffffe): return 42; /* VERNEED */
    case UINT64_C(0x6fffffff): return 43; /* VERNEEDNUM */
    default: *meaning = R2_ELF_DYNAMIC_UNKNOWN; return 0;
    }
}
static int r2_elf_dynamics_v1(struct r2_elf_context_v1 *c)
{
    uint32_t i, n, needed_seen = 0;
    uint64_t seen = 0, mapped;
    const struct r2_elf_raw_program_v1 *p = NULL;
    if (!c->r->dynamic_present) {
        c->r->dynamic_remainder_unknown = 0;
        return 1;
    }
    for (i = 0; i < c->r->program_count; ++i) {
        if (!r2_elf_charge_v1(c, 32, c->r->dynamic_offset)) return 0;
        if (c->r->programs[i].type == 2) p = &c->r->programs[i];
    }
    if (!p) return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED,
        R2_ELF_REASON_DYNAMIC_SIZE, 0, 0, R2_ELF_VALUE_SCALAR, 2);
    if (!p->file_size || p->file_size % 16 || p->file_size > p->memory_size)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_DYNAMIC_SIZE,
                            p->header_offset + 32, p->file_size, R2_ELF_VALUE_SCALAR, 2);
    c->r->dynamic_declared_entries = (uint32_t)(p->file_size / 16);
    if (c->r->dynamic_declared_entries > R2_ELF_RAW_DYNAMIC_LIMIT)
        return r2_elf_fail_v1(c, R2_ELF_RAW_INCOMPLETE, R2_ELF_REASON_DYNAMIC_LIMIT,
                            p->header_offset + 32, p->file_size / 16, R2_ELF_VALUE_SCALAR, 2);
    if (!r2_elf_map_v1(c, p->virtual_address, p->file_size, p->header_offset + 16, 2, &mapped)) return 0;
    if (mapped != p->file_offset)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_MAPPING_MISMATCH,
                            p->header_offset + 8, p->file_offset, R2_ELF_VALUE_FILE_OFFSET, 2);
    for (n = 0; n < c->r->dynamic_declared_entries; ++n) {
        struct r2_elf_raw_dynamic_v1 *d;
        uint32_t key;
        uint64_t off = p->file_offset + (uint64_t)n * 16u;
        if (!r2_elf_charge_v1(c, 128, off)) return 0;
        d = &c->r->dynamics[c->r->dynamic_count++]; d->file_offset = off;
        if (!r2_elf_read_v1(c, off, 8, &d->raw_tag) ||
            !r2_elf_read_v1(c, off + 8, 8, &d->raw_value)) return 0;
        key = r2_elf_tag_v1(d->raw_tag, &d->interpretation);
        if (!d->raw_tag) {
            c->r->dynamic_terminated = 1; c->r->dynamic_remainder_unknown = 0;
            return 1; /* Trailing declared bytes are padding, not decoded tags. */
        }
        if (key) {
            uint64_t bit = UINT64_C(1) << key;
            if (seen & bit)
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_DUPLICATE_TAG,
                                    off, d->raw_tag, R2_ELF_VALUE_SCALAR, (uint32_t)d->raw_tag);
            seen |= bit;
        }
        if (d->raw_tag == 1 && ++needed_seen > R2_ELF_RAW_NEEDED_LIMIT)
            return r2_elf_fail_v1(c, R2_ELF_RAW_INCOMPLETE, R2_ELF_REASON_NEEDED_LIMIT,
                                off, needed_seen, R2_ELF_VALUE_SCALAR, 1);
        if (d->raw_tag == 5) {
            c->r->string_table_present = 1; c->r->string_table_address = d->raw_value;
        } else if (d->raw_tag == 10) {
            c->r->string_size_present = 1; c->r->string_table_size = d->raw_value;
        } else if (d->raw_tag == 12) {
            c->r->application_conditions |= R2_ELF_CONDITION_INIT;
        } else if (d->raw_tag == 13) {
            c->r->application_conditions |= R2_ELF_CONDITION_FINI;
        } else if (d->raw_tag == 25 || d->raw_tag == 27) {
            c->r->application_conditions |= R2_ELF_CONDITION_INIT_ARRAY;
        } else if (d->raw_tag == 26 || d->raw_tag == 28) {
            c->r->application_conditions |= R2_ELF_CONDITION_FINI_ARRAY;
        } else if (d->raw_tag == 32 || d->raw_tag == 33) {
            c->r->application_conditions |= R2_ELF_CONDITION_PREINIT_ARRAY;
        } else if (d->raw_tag == 15 || d->raw_tag == 29) {
            /* Presence is independent of whether the spelling is empty. */
            c->r->application_conditions |= R2_ELF_CONDITION_SEARCH_PATH;
        } else if (d->interpretation == R2_ELF_DYNAMIC_UNKNOWN) {
            ++c->r->unknown_dynamic_count;
            r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_UNKNOWN_DYNAMIC,
                          off, d->raw_tag, R2_ELF_VALUE_SCALAR, (uint32_t)d->raw_tag);
        }
    }
    return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_DYNAMIC_TERMINATOR,
                        p->file_offset + p->file_size, 0, R2_ELF_VALUE_FILE_OFFSET, 2);
}
/* All calls to this helper inspect original FILE string bytes, including
 * interpreter bytes and repeated references. Reserve BOTH counters BEFORE
 * reading, and never rescan a spelling after validating it.
 */
static int r2_elf_string_byte_v1(struct r2_elf_context_v1 *c, uint64_t off,
                              uint32_t subject, unsigned char *v)
{
    if (!r2_elf_charge_v1(c, 48, off)) return 0;
    if (c->r->string_bytes_inspected == R2_ELF_RAW_STRING_BYTES_LIMIT)
        return r2_elf_fail_v1(c, R2_ELF_RAW_INCOMPLETE, R2_ELF_REASON_STRING_BYTES_LIMIT,
                            off, c->r->string_bytes_inspected, R2_ELF_VALUE_SCALAR, subject);
    if (!r2_elf_range_v1(c, off, 1, off)) return 0;
    ++c->r->string_bytes_inspected;
    *v = c->file[(size_t)off];
    return 1;
}
static int r2_elf_interpreter_tls_v1(struct r2_elf_context_v1 *c)
{
    uint32_t i;
    if (c->r->interpreter_present) {
        uint64_t n = c->r->interpreter_size;
        if (n < 2)
            return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_INTERPRETER,
                c->r->interpreter_offset, n, R2_ELF_VALUE_SCALAR, 3);
        if (n > R2_ELF_RAW_STRING_LIMIT)
            return r2_elf_fail_v1(c, R2_ELF_RAW_INCOMPLETE, R2_ELF_REASON_STRING_LIMIT,
                c->r->interpreter_offset, n, R2_ELF_VALUE_SCALAR, 3);
        for (i = 0; i < (uint32_t)n; ++i) {
            unsigned char ch;
            if (!r2_elf_string_byte_v1(c, c->r->interpreter_offset + i, 3, &ch)) return 0;
            if (ch > 127)
                return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_STRING_ASCII,
                    c->r->interpreter_offset + i, ch, R2_ELF_VALUE_SCALAR, 3);
            if ((!i && ch != '/') || (i + 1 < n && !ch) || (i + 1 == n && ch))
                return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_INTERPRETER,
                    c->r->interpreter_offset + i, ch, R2_ELF_VALUE_SCALAR, 3);
            if (ch) ++c->r->interpreter_length;
        }
    }
    for (i = 0; i < c->r->program_count; ++i) {
        const struct r2_elf_raw_program_v1 *p;
        uint64_t off;
        if (!r2_elf_charge_v1(c, 32, 0)) return 0;
        p = &c->r->programs[i];
        if (p->type != 7 || !p->file_size) continue;
        if (!r2_elf_map_v1(c, p->virtual_address, p->file_size, p->header_offset + 16, 7, &off)) return 0;
        if (off != p->file_offset)
            return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_MAPPING_MISMATCH,
                                p->header_offset + 8, p->file_offset, R2_ELF_VALUE_FILE_OFFSET, 7);
    }
    return 1;
}
static int r2_elf_strings_v1(struct r2_elf_context_v1 *c)
{
    uint32_t i;
    if (c->r->string_table_present != c->r->string_size_present)
        return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_STRING_TABLE_PAIR,
                            c->r->dynamic_offset, 0, R2_ELF_VALUE_SCALAR, 5);
    if (c->r->string_table_present) {
        if (!c->r->string_table_size)
            return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_STRING_TABLE,
                                c->r->dynamic_offset, 0, R2_ELF_VALUE_SCALAR, 10);
        if (!r2_elf_map_v1(c, c->r->string_table_address, c->r->string_table_size,
                         c->r->dynamic_offset, 5, &c->r->string_table_offset)) return 0;
    }
    for (i = 0; i < c->r->dynamic_count; ++i) {
        const struct r2_elf_raw_dynamic_v1 *d;
        struct r2_elf_raw_string_v1 *s;
        uint32_t j, kind;
        uint64_t remaining;
        if (!r2_elf_charge_v1(c, 64, c->r->dynamic_offset)) return 0;
        d = &c->r->dynamics[i];
        if (d->raw_tag == 1) kind = R2_ELF_STRING_NEEDED;
        else if (d->raw_tag == 14) kind = R2_ELF_STRING_SONAME;
        else if (d->raw_tag == 15) kind = R2_ELF_STRING_RPATH;
        else if (d->raw_tag == 29) kind = R2_ELF_STRING_RUNPATH;
        else continue;
        /* Capacity is independent of interpreter storage: 256+1+1+1. */
        if (c->r->strings_count == R2_ELF_RAW_STRING_RECORD_LIMIT)
            return r2_elf_fail_v1(c, R2_ELF_RAW_INCOMPLETE, R2_ELF_REASON_NEEDED_LIMIT,
                                d->file_offset, c->r->strings_count, R2_ELF_VALUE_SCALAR, 1);
        s = &c->r->strings[c->r->strings_count++];
        s->kind = kind; s->dynamic_index = i; s->string_index = d->raw_value;
        if (kind == R2_ELF_STRING_NEEDED) ++c->r->needed_count;
        if (!c->r->string_table_present)
            return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_STRING_TABLE_PAIR,
                                d->file_offset, d->raw_value, R2_ELF_VALUE_SCALAR, (uint32_t)d->raw_tag);
        if (d->raw_value >= c->r->string_table_size)
            return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_STRING_INDEX,
                                d->file_offset + 8, d->raw_value, R2_ELF_VALUE_SCALAR, (uint32_t)d->raw_tag);
        remaining = c->r->string_table_size - d->raw_value;
        s->file_offset = (uint32_t)(c->r->string_table_offset + d->raw_value);
        for (j = 0; j < R2_ELF_RAW_STRING_LIMIT && j < remaining; ++j) {
            unsigned char ch;
            if (!r2_elf_string_byte_v1(c, (uint64_t)s->file_offset + j, (uint32_t)d->raw_tag, &ch)) return 0;
            if (ch > 127)
                return r2_elf_fail_v1(c, R2_ELF_RAW_UNSUPPORTED, R2_ELF_REASON_STRING_ASCII,
                    (uint64_t)s->file_offset + j, ch, R2_ELF_VALUE_SCALAR, (uint32_t)d->raw_tag);
            if (!ch) {
                if (!j && (kind == R2_ELF_STRING_NEEDED || kind == R2_ELF_STRING_SONAME))
                    return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_EMPTY_NAME,
                        s->file_offset, 0, R2_ELF_VALUE_SCALAR, (uint32_t)d->raw_tag);
                s->complete = 1;
                break;
            }
            ++s->length;
        }
        if (!s->complete)
            return r2_elf_fail_v1(c, j == R2_ELF_RAW_STRING_LIMIT ? R2_ELF_RAW_INCOMPLETE : R2_ELF_RAW_REJECTED,
                j == R2_ELF_RAW_STRING_LIMIT ? R2_ELF_REASON_STRING_LIMIT : R2_ELF_REASON_STRING_TERMINATOR,
                (uint64_t)s->file_offset + j, j, R2_ELF_VALUE_SCALAR, (uint32_t)d->raw_tag);
    }
    return 1;
}
static int r2_elf_arrays_v1(struct r2_elf_context_v1 *c)
{
    uint32_t pair, i;
    for (pair = 0; pair < 3; ++pair) {
        const struct r2_elf_raw_dynamic_v1 *address = NULL, *size = NULL;
        uint64_t atag = pair == 0 ? 25u : pair == 1 ? 26u : 32u;
        uint64_t stag = pair == 0 ? 27u : pair == 1 ? 28u : 33u, off;
        for (i = 0; i < c->r->dynamic_count; ++i) {
            const struct r2_elf_raw_dynamic_v1 *d;
            if (!r2_elf_charge_v1(c, 32, c->r->dynamic_offset)) return 0;
            d = &c->r->dynamics[i];
            if (d->raw_tag == atag) address = d;
            if (d->raw_tag == stag) size = d;
        }
        if (!!address != !!size)
            return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_ARRAY_PAIR,
                address ? address->file_offset : size->file_offset, atag, R2_ELF_VALUE_SCALAR, (uint32_t)atag);
        if (!address) continue;
        if (address->raw_value % 8u || size->raw_value % 8u)
            return r2_elf_fail_v1(c, R2_ELF_RAW_REJECTED, R2_ELF_REASON_ARRAY_ALIGNMENT,
                address->raw_value % 8u ? address->file_offset + 8 : size->file_offset + 8,
                address->raw_value % 8u ? address->raw_value : size->raw_value,
                R2_ELF_VALUE_SCALAR, (uint32_t)atag);
        if (!address->raw_value && !size->raw_value) continue;
        /* Even an empty nonzero address must anchor inside backed bytes. */
        if (!r2_elf_map_v1(c, address->raw_value, size->raw_value ? size->raw_value : 1u,
                         address->file_offset + 8, (uint32_t)atag, &off)) return 0;
    }
    return 1;
}
uint32_t route2_elf_preload_parse_raw_v1(
    const unsigned char *file, size_t file_size, uint32_t report_abi,
    struct r2_elf_raw_report_v1 *out, size_t out_size)
{
    uintptr_t ib = (uintptr_t)file, ob = (uintptr_t)out, ie, oe;
    uint64_t initialization_work;
    size_t i;
    unsigned char *clear;
    struct r2_elf_context_v1 c;
    /* Exact independent ABI/size/alignment/ranges/disjointness before writing
     * any report byte. Accessible/stable/exclusive memory remains caller duty.
     */
    if (!file || !out || report_abi != R2_ELF_RAW_ABI ||
        out_size != R2_ELF_RAW_REPORT_BYTES ||
        ob % _Alignof(struct r2_elf_raw_report_v1) ||
        file_size > UINTPTR_MAX - ib || out_size > UINTPTR_MAX - ob)
        return R2_ELF_RAW_BAD_ARGUMENT;
    ie = ib + file_size; oe = ob + out_size;
    if (file_size && ib < oe && ob < ie) return R2_ELF_RAW_BAD_ARGUMENT;
    /* Local reservation is completed BEFORE clearing. No report copy or
     * large automatic array; the caller owns the fixed output storage.
     */
    initialization_work = (uint64_t)out_size + 1024u;
    if (initialization_work > R2_ELF_RAW_WORK_LIMIT) return R2_ELF_RAW_BAD_ARGUMENT;
    clear = (unsigned char *)out;
    for (i = 0; i < out_size; ++i) clear[i] = 0;
    out->abi = R2_ELF_RAW_ABI; out->size = R2_ELF_RAW_REPORT_BYTES;
    out->raw_status = R2_ELF_RAW_REJECTED;
    out->preload_scope = R2_ELF_PRELOAD_CLOSURE_UNPROVEN;
    out->remaining_unproven = R2_ELF_UNPROVEN_ALL;
    out->file_bytes = file_size; out->work_units = initialization_work;
    out->dynamic_remainder_unknown = 1; out->needed_remainder_unknown = 1;
    c.file = file; c.length = file_size; c.r = out;
    if (file_size > R2_ELF_RAW_FILE_LIMIT) {
        r2_elf_fail_v1(&c, R2_ELF_RAW_INCOMPLETE, R2_ELF_REASON_FILE_LIMIT,
                      0, file_size, R2_ELF_VALUE_SCALAR, 0);
        return out->raw_status;
    }
    if (!r2_elf_header_v1(&c) || !r2_elf_programs_v1(&c) ||
        !r2_elf_interpreter_tls_v1(&c) || !r2_elf_dynamics_v1(&c) ||
        !r2_elf_strings_v1(&c) || !r2_elf_arrays_v1(&c)) return out->raw_status;
    out->needed_remainder_unknown =
        (out->unknown_program_count || out->unknown_dynamic_count) ? 1u : 0u;
    if (out->unknown_program_count || out->unknown_dynamic_count) {
        out->raw_status = R2_ELF_RAW_UNSUPPORTED;
        return out->raw_status;
    }
    out->structural_complete = 1;
    out->raw_status = out->application_conditions ?
        R2_ELF_RAW_APPLICATION_CONDITIONS : R2_ELF_RAW_COMPLETE;
    return out->raw_status;
}
#endif
#endif

/* C00 machine-memory raw acquisition; root selected this exact limb before
 * authoring. Public APIs: sysinfoapi.h / Windows.h, Kernel32.lib; installed
 * memory requires Vista SP1. Existing C11/Windows-seed build contract applies.
 * No dynamic loading, new thread, caller evidence or admission integration.
 */
#if defined(R2_TARGET_WINDOWS_SEED)
#ifndef R2_WIN_MACHINE_MEMORY_V1_BODY
#define R2_WIN_MACHINE_MEMORY_V1_BODY
_Static_assert(sizeof(ULONGLONG) == sizeof(uint64_t) && sizeof(BOOL) == 4,
               "machine-memory native scalar ABI changed");
_Static_assert(sizeof(MEMORYSTATUSEX) == 64 &&
    sizeof(struct r2_win_machine_memory_fault_v1) == 24 &&
    sizeof(struct r2_win_machine_memory_clock_v1) == 24 &&
    sizeof(struct r2_win_machine_memory_snapshot_v1) == 304 &&
    sizeof(struct r2_win_machine_memory_report_v1) == R2_WIN_MACHINE_MEMORY_REPORT_BYTES,
    "machine-memory raw report ABI changed");
static struct r2_win_machine_memory_report_v1 r2_mm_report_v1 = {
    .abi = R2_WIN_MACHINE_MEMORY_ABI,
    .size = sizeof(struct r2_win_machine_memory_report_v1),
    .remaining_unproven = R2_WIN_MACHINE_MEMORY_UNPROVEN_ALL
};
static void r2_mm_stop_v1(void)
{
    InterlockedExchange(&r2_own_stop_v1, 1);
    r2_own_report_v1.stop_new = 1;
    r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
    r2_mm_report_v1.stop_new = 1;
}
static void r2_mm_fault_v1(struct r2_win_machine_memory_snapshot_v1 *s,
    uint32_t operation, uint32_t kind, uint32_t code, DWORD error)
{
    struct r2_win_machine_memory_fault_v1 f = {
        operation, kind, code, (uint32_t)error, kind == R2_MM_FAULT_WIN32, 0
    };
    struct r2_win_machine_memory_report_v1 *r = &r2_mm_report_v1;
    r2_mm_stop_v1();
    if (s->fault_count < 2) s->faults[s->fault_count] = f;
    else if (s->omitted_fault_count != UINT32_MAX) ++s->omitted_fault_count;
    if (s->fault_count != UINT32_MAX) ++s->fault_count;
    if (!r->fault_count) r->primary = f;
    else if (r->fault_count == 1) r->secondary = f;
    else if (r->omitted_fault_count != UINT32_MAX) ++r->omitted_fault_count;
    if (r->fault_count != UINT32_MAX) ++r->fault_count;
}
static int r2_mm_clock_v1(struct r2_win_machine_memory_snapshot_v1 *s,
    uint32_t index, uint32_t operation, int64_t deadline)
{
    LARGE_INTEGER now = {0};
    BOOL result;
    struct r2_win_machine_memory_clock_v1 *c = &s->clocks[index];
    c->attempted = 1;
    result = QueryPerformanceCounter(&now);
    if (!result) {
        DWORD error = GetLastError();
        c->raw_result = (uint32_t)result;
        c->win32_error = error; c->win32_error_valid = 1;
        r2_own_report_v1.clock_valid = 0;
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        r2_mm_fault_v1(s, operation, R2_MM_FAULT_WIN32, 0, error);
        return 0;
    }
    c->raw_result = (uint32_t)result; c->raw_qpc = now.QuadPart;
    if (now.QuadPart <= 0 || now.QuadPart < r2_own_report_v1.last_qpc ||
        !r2_own_report_v1.clock_valid ||
        (r2_own_report_v1.residual_bits & R2_OWN_RESIDUAL_CLOCK)) {
        r2_own_report_v1.clock_valid = 0;
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        r2_mm_fault_v1(s, operation, R2_MM_FAULT_INVARIANT, R2_MM_REASON_CLOCK, 0);
        return 0;
    }
    r2_own_report_v1.last_qpc = now.QuadPart;
    if (deadline <= 0 || now.QuadPart >= deadline) {
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_DEADLINE;
        r2_mm_fault_v1(s, operation, R2_MM_FAULT_INVARIANT, R2_MM_REASON_DEADLINE, 0);
        return 0;
    }
    s->valid_fields |= index == 0 ? R2_MM_VALID_BEGIN_CLOCK :
        index == 1 ? R2_MM_VALID_INSTALLED_BEGIN_CLOCK :
        index == 2 ? R2_MM_VALID_INSTALLED_END_CLOCK : R2_MM_VALID_END_CLOCK;
    return 1;
}
static int r2_mm_identity_v1(struct r2_win_machine_memory_snapshot_v1 *s,
    uint32_t operation)
{
    /* C02 retains the actual creator-query errors in its original report. */
    if (GetCurrentProcessId() != r2_own_report_v1.creator_pid ||
        GetCurrentThreadId() != r2_own_report_v1.creator_tid ||
        !r2_own_creator_identity_v1()) {
        r2_mm_fault_v1(s, operation, R2_MM_FAULT_OWNER, R2_MM_REASON_IDENTITY, 0);
        return 0;
    }
    return 1;
}
static uint32_t r2_mm_publish_v1(struct r2_win_machine_memory_snapshot_v1 *s)
{
    struct r2_win_machine_memory_report_v1 *r = &r2_mm_report_v1;
    if (!r->initial_present) { r->initial = *s; r->initial_present = 1; }
    if (s->raw_complete) {
        r->latest = *s; r->latest_present = 1;
        if (r->successful_captures != UINT32_MAX) ++r->successful_captures;
        r->status = R2_MM_RAW_COMPLETE;
    } else {
        r->failed = *s; r->failed_present = 1;
        if (r->failed_captures != UINT32_MAX) ++r->failed_captures;
        r->status = R2_MM_RAW_PARTIAL;
    }
    r->stop_new = (uint32_t)r2_own_stopped_v1();
    /* Preserve this call's result before releasing shared report ownership. */
    uint32_t status = r->status;
    InterlockedExchange(&r2_own_guard_v1, 0);
    return status;
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_machine_memory_observe_step_v1(void)
{
    struct r2_win_machine_memory_snapshot_v1 s = {0};
    struct r2_win_machine_memory_report_v1 *r = &r2_mm_report_v1;
    struct r2_win_owned_report_v1 *owner = &r2_own_report_v1;
    MEMORYSTATUSEX native = {0};
    ULONGLONG installed = 0;
    BOOL result;
    int64_t deadline;
    int first;
    if (!r2_own_enter_v1()) {
        /* Do not mutate guarded storage from the losing caller. */
        InterlockedExchange(&r2_own_stop_v1, 1);
        return R2_MM_BUSY;
    }
    if (r->attempt_count == UINT32_MAX) {
        s.ordinal = UINT32_MAX; s.lifecycle = owner->lifecycle;
        r2_mm_fault_v1(&s, R2_MM_OP_COUNTER, R2_MM_FAULT_INVARIANT, R2_MM_REASON_COUNTER, 0);
        r->failed = s; r->failed_present = 1;
        if (r->failed_captures != UINT32_MAX) ++r->failed_captures;
        r->status = R2_MM_LIMIT_REACHED;
        InterlockedExchange(&r2_own_guard_v1, 0);
        return R2_MM_LIMIT_REACHED;
    }
    first = !r->initial_present;
    s.ordinal = ++r->attempt_count; s.lifecycle = owner->lifecycle;
    if (!owner->attempt_consumed || !r2_own_v1.deadline_bound || !r2_own_v1.creator ||
        owner->creator_creation_100ns.state != R2_WIN_JOB_FIELD_VALID ||
        owner->lease_epoch_qpc <= 0 || owner->qpc_frequency <= 0 ||
        owner->stop_deadline_qpc <= owner->lease_epoch_qpc ||
        owner->cleanup_deadline_qpc <= owner->stop_deadline_qpc ||
        owner->lifecycle < R2_OWN_INTENT_HELD || owner->lifecycle == R2_OWN_DONE ||
        owner->lifecycle == R2_OWN_CLOSING || owner->lifecycle > R2_OWN_RETAINED ||
        (first && (owner->lifecycle != R2_OWN_INTENT_HELD || owner->birth_attempted ||
                   r2_own_stopped_v1()))) {
        r2_mm_fault_v1(&s, R2_MM_OP_STATE, R2_MM_FAULT_INVARIANT, R2_MM_REASON_STATE, 0);
        return r2_mm_publish_v1(&s);
    }
    r->creator_pid = owner->creator_pid; r->creator_tid = owner->creator_tid;
    r->intent_serial = owner->intent_serial; r->lease_epoch_qpc = owner->lease_epoch_qpc;
    r->qpc_frequency = owner->qpc_frequency;
    r->stop_deadline_qpc = owner->stop_deadline_qpc;
    r->cleanup_deadline_qpc = owner->cleanup_deadline_qpc;
    deadline = r2_own_stopped_v1() || owner->lifecycle >= R2_OWN_STOPPING ?
        owner->cleanup_deadline_qpc : owner->stop_deadline_qpc;
    if (!r2_mm_clock_v1(&s, 0, R2_MM_OP_CLOCK_BEGIN, deadline)) return r2_mm_publish_v1(&s);
    if (!r2_mm_identity_v1(&s, R2_MM_OP_OWNER_BEFORE)) return r2_mm_publish_v1(&s);
    s.owner_before = 1; s.prebirth_first = first ? 1u : 0u;
    /* Recheck after synchronous identity queries before beginning memory I/O. */
    if (!r2_mm_clock_v1(&s, 1, R2_MM_OP_CLOCK_INSTALLED_BEGIN, deadline))
        return r2_mm_publish_v1(&s);
    s.installed_attempted = 1;
    result = GetPhysicallyInstalledSystemMemory(&installed);
    if (!result) {
        DWORD error = GetLastError();
        s.installed_raw_result = (uint32_t)result;
        s.installed_win32_error = error; s.installed_error_valid = 1;
        r2_mm_fault_v1(&s, R2_MM_OP_INSTALLED, R2_MM_FAULT_WIN32, 0, error);
    } else {
        s.installed_raw_result = (uint32_t)result; s.installed_kib = installed;
        s.valid_fields |= R2_MM_VALID_INSTALLED_KIB;
        if (!installed) r2_mm_fault_v1(&s, R2_MM_OP_VALUES,
            R2_MM_FAULT_INVARIANT, R2_MM_REASON_VALUE, 0);
        else if (installed > UINT64_MAX / 1024u) r2_mm_fault_v1(&s, R2_MM_OP_VALUES,
            R2_MM_FAULT_INVARIANT, R2_MM_REASON_OVERFLOW, 0);
        else { s.installed_bytes = (uint64_t)installed * 1024u;
               s.valid_fields |= R2_MM_VALID_INSTALLED_BYTES; }
    }
    /* After a primary failure, endpoint diagnostics use only the unchanged
     * original cleanup deadline. They never revive active work. */
    if (!r2_mm_clock_v1(&s, 2, R2_MM_OP_CLOCK_INSTALLED_END,
        s.fault_count ? owner->cleanup_deadline_qpc : deadline)) return r2_mm_publish_v1(&s);
    if (!s.fault_count) {
        native.dwLength = sizeof(native); s.global_attempted = 1;
        result = GlobalMemoryStatusEx(&native);
        if (!result) {
            DWORD error = GetLastError();
            s.global_raw_result = (uint32_t)result;
            s.global_win32_error = error; s.global_error_valid = 1;
            r2_mm_fault_v1(&s, R2_MM_OP_GLOBAL, R2_MM_FAULT_WIN32, 0, error);
        } else {
            s.global_raw_result = (uint32_t)result;
            s.valid_fields |= R2_MM_VALID_GLOBAL_FIELDS;
        }
        /* Retain the returned buffer even on FALSE, without granting its
         * fields validity. The error was captured before this local copy. */
        s.native_length = native.dwLength; s.native_memory_load = native.dwMemoryLoad;
        s.total_phys = native.ullTotalPhys; s.avail_phys = native.ullAvailPhys;
        s.total_page_file = native.ullTotalPageFile; s.avail_page_file = native.ullAvailPageFile;
        s.total_virtual = native.ullTotalVirtual; s.avail_virtual = native.ullAvailVirtual;
        s.avail_extended_virtual = native.ullAvailExtendedVirtual;
        if (result) {
            if (native.dwLength != sizeof(native) || native.dwMemoryLoad > 100 ||
                !s.total_phys || s.avail_phys > s.total_phys ||
                !s.total_page_file || s.avail_page_file > s.total_page_file ||
                !s.total_virtual || s.avail_virtual > s.total_virtual ||
                s.avail_extended_virtual || s.total_phys > s.installed_bytes)
                r2_mm_fault_v1(&s, R2_MM_OP_VALUES, R2_MM_FAULT_INVARIANT, R2_MM_REASON_VALUE, 0);
            if (r->initial.raw_complete &&
                (s.installed_bytes != r->initial.installed_bytes || s.total_phys != r->initial.total_phys))
                r2_mm_fault_v1(&s, R2_MM_OP_CAPACITY_CHANGE, R2_MM_FAULT_INVARIANT,
                    R2_MM_REASON_CAPACITY_CHANGE, 0);
        }
    }
    if (r2_mm_identity_v1(&s, R2_MM_OP_OWNER_AFTER)) s.owner_after = 1;
    if (!r2_mm_clock_v1(&s, 3, R2_MM_OP_CLOCK_END,
        s.fault_count ? owner->cleanup_deadline_qpc : deadline)) return r2_mm_publish_v1(&s);
    if (!s.fault_count && s.owner_before && s.owner_after &&
        s.valid_fields == (R2_MM_VALID_INSTALLED_KIB | R2_MM_VALID_INSTALLED_BYTES |
            R2_MM_VALID_GLOBAL_FIELDS | R2_MM_VALID_BEGIN_CLOCK |
            R2_MM_VALID_INSTALLED_BEGIN_CLOCK | R2_MM_VALID_INSTALLED_END_CLOCK | R2_MM_VALID_END_CLOCK)) s.raw_complete = 1;
    if (!s.raw_complete) r2_mm_stop_v1();
    return r2_mm_publish_v1(&s);
}
static int r2_mm_disjoint_v1(const void *out, size_t size, const void *private_bytes, size_t private_size)
{
    uintptr_t a = (uintptr_t)out, b = (uintptr_t)private_bytes;
    return a + size <= b || b + private_size <= a;
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_machine_memory_copy_report_v1(
    struct r2_win_machine_memory_report_v1 *out, size_t out_size)
{
    if (out_size != sizeof(*out) ||
        !r2_own_range_v1(out, out_size, _Alignof(struct r2_win_machine_memory_report_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, &r2_mm_report_v1, sizeof(r2_mm_report_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, &r2_own_report_v1, sizeof(r2_own_report_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, &r2_own_v1, sizeof(r2_own_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, (const void *)&r2_own_guard_v1, sizeof(r2_own_guard_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, (const void *)&r2_own_stop_v1, sizeof(r2_own_stop_v1)))
        return R2_MM_BAD_ARGUMENT;
    if (!r2_own_enter_v1()) return R2_MM_BUSY;
    r2_mm_report_v1.stop_new = (uint32_t)r2_own_stopped_v1();
    memcpy(out, &r2_mm_report_v1, sizeof(*out));
    InterlockedExchange(&r2_own_guard_v1, 0);
    return R2_MM_COPY_OK;
}
#endif
#endif

/* C00 selected original-adapter GPU source limb; no consumer assembly. */
#if defined(R2_TARGET_WINDOWS_SEED) && defined(R2_ENABLE_WIN_GPU_RAW_V1)
#ifndef R2_WIN_GPU_RAW_V1_BODY
#define R2_WIN_GPU_RAW_V1_BODY
#include <Windows.h>
#include <d3dkmthk.h>
#if !defined(NTDDI_WIN11_GE) || !defined(WDK_NTDDI_VERSION) || \
    !defined(NTDDI_VERSION) || !defined(_WIN32_WINNT_WIN10) || \
    !defined(_WIN32_WINNT) || !defined(DXGKDDI_INTERFACE_VERSION_WDDM3_2) || \
    !defined(DXGKDDI_INTERFACE_VERSION)
#error "GPU opt-in requires actual Windows 11 24H2 / SDK 10.0.26100+ declarations"
#endif
#if NTDDI_VERSION < NTDDI_WIN11_GE || WDK_NTDDI_VERSION < NTDDI_WIN11_GE || \
    _WIN32_WINNT < _WIN32_WINNT_WIN10 || \
    DXGKDDI_INTERFACE_VERSION < DXGKDDI_INTERFACE_VERSION_WDDM3_2
#error "GPU opt-in requires Windows 11 24H2 target and WDDM 3.2+ interface"
#endif
/* No SDK constants, function declarations, COM vtables or imports are emulated.
 * The existing top Windows PE TU remains the sole core inclusion site.
 * Microsoft primary declaration evidence (Context7 resolved first):
 * win32metadata/.../shared/{sdkddkver.h,d3dukmdt.h,d3dkmthk.h}; Learn DDI pages
 * nf-d3dkmthk-{d3dkmtenumadapters3,d3dkmtqueryadapterinfo,d3dkmtcloseadapter},
 * ns-d3dkmthk-{_d3dkmt_enumadapters3,_d3dkmt_segmentgroupsizeinfo}.
 */
_Static_assert(sizeof(NTSTATUS) == 4 && sizeof(D3DKMT_HANDLE) == 4 &&
    sizeof(UINT) == 4 && sizeof(ULONG) == 4, "GPU SDK scalar ABI");
_Static_assert(sizeof(struct r2_win_gpu_clock_v1) == 24 &&
    sizeof(struct r2_win_gpu_call_v1) == 112 &&
    sizeof(struct r2_win_gpu_fault_v1) == 32 &&
    sizeof(struct r2_win_gpu_member_v1) == 176 &&
    sizeof(struct r2_win_gpu_adapter_v1) == 1928 &&
    sizeof(struct r2_win_gpu_report_v1) == R2_WIN_GPU_REPORT_BYTES, "GPU raw Win64 report ABI");
_Static_assert(sizeof(D3DKMT_ADAPTERTYPE) <= UINT_MAX &&
    sizeof(D3DKMT_SEGMENTSIZEINFO) <= UINT_MAX &&
    sizeof(D3DKMT_PHYSICAL_ADAPTER_COUNT) <= UINT_MAX &&
    sizeof(D3DKMT_SEGMENTGROUPSIZEINFO) <= UINT_MAX,
    "GPU exact SDK query payload sizes must fit UINT");
_Static_assert(R2_WIN_GPU_NATIVE_WORK_CAP ==
    2u + R2_WIN_GPU_ADAPTER_CAP * (4u + R2_WIN_GPU_MEMBER_CAP),
    "GPU lifetime native work policy");
struct r2_gpu_private_v1 {
    HANDLE original_creator;
    volatile LONG race;
    uint32_t race_recorded;
    D3DKMT_ENUMADAPTERS3 sizing, populate;
    D3DKMT_ADAPTERINFO opaque_adapters[R2_WIN_GPU_ADAPTER_CAP];
    D3DKMT_HANDLE original[R2_WIN_GPU_ADAPTER_CAP];
    D3DKMT_ADAPTERTYPE types[R2_WIN_GPU_ADAPTER_CAP];
    D3DKMT_SEGMENTSIZEINFO segments[R2_WIN_GPU_ADAPTER_CAP];
    D3DKMT_PHYSICAL_ADAPTER_COUNT counts[R2_WIN_GPU_ADAPTER_CAP];
    D3DKMT_SEGMENTGROUPSIZEINFO members[R2_WIN_GPU_ADAPTER_CAP][R2_WIN_GPU_MEMBER_CAP];
};
static struct r2_gpu_private_v1 r2_gpu_v1;
static struct r2_win_gpu_report_v1 r2_gpu_report_v1 = {
    .abi = R2_WIN_GPU_RAW_ABI, .size = sizeof(struct r2_win_gpu_report_v1),
    .remaining_unproven = R2_WIN_GPU_UNPROVEN_ALL
};
_Static_assert(sizeof(struct r2_gpu_private_v1) +
    sizeof(struct r2_win_gpu_report_v1) < 65536u,
    "GPU fixed control storage policy, not a whole-memory grant");
static void r2_gpu_stop_v1(uint32_t residual)
{
    InterlockedExchange(&r2_own_stop_v1, 1);
    r2_own_report_v1.stop_new = 1;
    r2_own_report_v1.residual_bits |= residual;
    if ((r2_own_v1.process && !r2_own_report_v1.process_signaled) ||
        (r2_own_v1.thread && !r2_own_report_v1.thread_signaled) ||
        (r2_own_v1.job && !r2_own_report_v1.job_empty))
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_JOIN;
    r2_gpu_report_v1.stop_new = 1;
}
static void r2_gpu_fault_v1(uint32_t op, uint32_t kind, uint32_t reason,
    uint32_t raw, uint32_t adapter, uint32_t member)
{
    struct r2_win_gpu_report_v1 *r = &r2_gpu_report_v1;
    struct r2_win_gpu_fault_v1 f = {op, kind, reason, raw, adapter, member, {0, 0}};
    r2_gpu_stop_v1(R2_OWN_RESIDUAL_SAMPLE);
    if (r->fault_count < R2_WIN_GPU_FAULT_CAP) r->faults[r->fault_count] = f;
    else if (r->omitted_fault_count != UINT32_MAX) ++r->omitted_fault_count;
    if (!r->fault_count) r->primary = f;
    else if (r->fault_count == 1) r->secondary = f;
    if (r->fault_count != UINT32_MAX) ++r->fault_count;
}
static int r2_gpu_context_v1(uint32_t op, uint32_t adapter, uint32_t member)
{
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    const struct r2_win_gpu_report_v1 *r = &r2_gpu_report_v1;
    if (!r2_own_v1.creator || r2_own_v1.creator != r2_gpu_v1.original_creator ||
        !r2_own_v1.deadline_bound ||
        !o->attempt_consumed || o->creator_creation_100ns.state != R2_WIN_JOB_FIELD_VALID ||
        o->lifecycle < R2_OWN_INTENT_HELD || o->lifecycle == R2_OWN_CLOSING ||
        o->lifecycle == R2_OWN_DONE || o->lifecycle > R2_OWN_RETAINED ||
        o->creator_pid != r->creator_pid || o->creator_tid != r->creator_tid ||
        o->creator_creation_100ns.value != r->creator_creation_100ns ||
        o->intent_serial != r->intent_serial || o->lease_epoch_qpc != r->lease_epoch_qpc ||
        o->qpc_frequency != r->qpc_frequency ||
        o->stop_deadline_qpc != r->stop_deadline_qpc ||
        o->cleanup_deadline_qpc != r->cleanup_deadline_qpc) {
        r2_gpu_fault_v1(op, R2_GPU_FAULT_OWNER, R2_GPU_REASON_CONTEXT_CHANGED, 0, adapter, member);
        return 0;
    }
    if (GetCurrentProcessId() != r->creator_pid || GetCurrentThreadId() != r->creator_tid ||
        !r2_own_creator_identity_v1()) {
        r2_gpu_fault_v1(op, R2_GPU_FAULT_OWNER, R2_GPU_REASON_IDENTITY, 0, adapter, member);
        return 0;
    }
    return 1;
}
static int r2_gpu_clock_v1(struct r2_win_gpu_call_v1 *call, uint32_t endpoint,
    uint32_t op, uint32_t adapter, uint32_t member, int cleanup)
{
    struct r2_win_gpu_clock_v1 *c = &call->clocks[endpoint];
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    LARGE_INTEGER now = {0};
    int64_t deadline = cleanup ? r2_gpu_report_v1.cleanup_deadline_qpc :
        r2_gpu_report_v1.stop_deadline_qpc;
    BOOL result;
    c->attempted = 1;
    result = QueryPerformanceCounter(&now);
    c->raw_result = (uint32_t)result;
    if (!result) {
        DWORD error = GetLastError();
        c->win32_error = error; c->win32_error_valid = 1;
        o->clock_valid = 0; o->residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        r2_gpu_fault_v1(op, R2_GPU_FAULT_WIN32, R2_GPU_REASON_CLOCK, error, adapter, member);
        return 0;
    }
    c->raw_qpc = now.QuadPart;
    if (now.QuadPart <= 0 || now.QuadPart < o->last_qpc || !o->clock_valid ||
        (o->residual_bits & R2_OWN_RESIDUAL_CLOCK)) {
        o->clock_valid = 0; o->residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        r2_gpu_fault_v1(op, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_CLOCK, 0, adapter, member);
        return 0;
    }
    o->last_qpc = now.QuadPart;
    if (deadline <= 0 || now.QuadPart >= deadline) {
        o->residual_bits |= R2_OWN_RESIDUAL_DEADLINE;
        r2_gpu_fault_v1(op, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_DEADLINE, 0, adapter, member);
        return 0;
    }
    return 1;
}
static int r2_gpu_before_v1(struct r2_win_gpu_call_v1 *call, uint32_t op,
    uint32_t adapter, uint32_t member, int cleanup)
{
    if (r2_gpu_report_v1.native_work_count >= R2_WIN_GPU_NATIVE_WORK_CAP) {
        r2_gpu_fault_v1(op, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_COUNTER, 0, adapter, member);
        return 0;
    }
    if (!cleanup && (r2_own_stopped_v1() || r2_own_report_v1.birth_attempted ||
        r2_own_report_v1.lifecycle != R2_OWN_INTENT_HELD)) {
        r2_gpu_fault_v1(op, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_RACE, 0, adapter, member);
        return 0;
    }
    if (!r2_gpu_clock_v1(call, 0, op, adapter, member, cleanup)) return 0;
    if (!r2_gpu_context_v1(op, adapter, member)) return 0;
    if (!r2_gpu_clock_v1(call, 1, op, adapter, member, cleanup)) return 0;
    if (!cleanup && r2_own_stopped_v1()) {
        r2_gpu_fault_v1(op, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_RACE, 0, adapter, member);
        return 0;
    }
    return 1;
}
static int r2_gpu_after_v1(struct r2_win_gpu_call_v1 *call, uint32_t op,
    uint32_t adapter, uint32_t member, int cleanup)
{
    int clock_ok = r2_gpu_clock_v1(call, 2, op, adapter, member, cleanup);
    if (!clock_ok) return 0;
    int identity_ok = r2_gpu_context_v1(op, adapter, member);
    int end_ok = r2_gpu_clock_v1(call, 3, op, adapter, member, cleanup || !clock_ok || !identity_ok);
    if (!cleanup && r2_own_stopped_v1()) {
        r2_gpu_fault_v1(op, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_RACE, 0, adapter, member);
        return 0;
    }
    return clock_ok && identity_ok && end_ok;
}
static void r2_gpu_result_v1(struct r2_win_gpu_call_v1 *call, NTSTATUS status,
    uint32_t op, uint32_t adapter, uint32_t member)
{
    call->ntstatus_bits = (uint32_t)status; call->ntstatus_valid = 1;
    if (status != 0)
        r2_gpu_fault_v1(op, R2_GPU_FAULT_NTSTATUS, 0, (uint32_t)status, adapter, member);
}
static void r2_gpu_refresh_v1(void)
{
    struct r2_win_gpu_report_v1 *r = &r2_gpu_report_v1;
    if (InterlockedCompareExchange(&r2_gpu_v1.race, 0, 0) && !r2_gpu_v1.race_recorded) {
        r2_gpu_v1.race_recorded = 1;
        r2_gpu_fault_v1(R2_GPU_OP_STATE, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_RACE, 0, 0, 0);
    }
    r->stop_new = (uint32_t)r2_own_stopped_v1();
    r->owner_lifecycle = r2_own_report_v1.lifecycle;
    r->all_known_once_closed = r->ownership == R2_GPU_OWN_KNOWN &&
        r->close_succeeded_count == r->adopted_count &&
        r->close_consumed_count == r->adopted_count;
    r->pending_liability = r->fault_count != 0 ||
        r->ownership == R2_GPU_ENUM_FAILED_OWNERSHIP_UNKNOWN ||
        r->ownership == R2_GPU_ENUM_INVALID_OWNERSHIP_UNKNOWN ||
        (r->adopted_count && !r->all_known_once_closed);
    if (r->fault_count && r->finish_consumed) r->status = R2_GPU_RETAINED;
    else if (r->acquisition_complete && r->all_known_once_closed && !r->fault_count &&
        !r->pending_liability) r->status = R2_GPU_RAW_COMPLETE;
    else if (r->fault_count) r->status = R2_GPU_RAW_PARTIAL;
    else r->status = r->acquisition_consumed ? R2_GPU_PENDING : R2_GPU_UNUSED;
}
static uint32_t r2_gpu_leave_v1(void)
{
    r2_gpu_refresh_v1();
    struct r2_win_gpu_report_v1 *r = &r2_gpu_report_v1;
    uint32_t status = r->status;
    InterlockedExchange(&r2_own_guard_v1, 0);
    return status;
}
static int r2_gpu_query_v1(uint32_t adapter, uint32_t member,
    KMTQUERYADAPTERINFOTYPE type, void *native, size_t native_size,
    struct r2_win_gpu_call_v1 *call, uint32_t op)
{
    D3DKMT_QUERYADAPTERINFO query = {0};
    NTSTATUS status;
    if (adapter >= R2_WIN_GPU_ADAPTER_CAP || member >= R2_WIN_GPU_MEMBER_CAP ||
        !native_size || native_size > UINT_MAX || !r2_gpu_v1.original[adapter]) {
        r2_gpu_fault_v1(op, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_BOUND, 0, adapter, member);
        return 0;
    }
    if (!r2_gpu_before_v1(call, op, adapter, member, 0)) return 0;
    query.hAdapter = r2_gpu_v1.original[adapter]; query.Type = type;
    query.pPrivateDriverData = native; query.PrivateDriverDataSize = (UINT)native_size;
    call->attempted = 1; ++r2_gpu_report_v1.native_work_count;
    status = D3DKMTQueryAdapterInfo(&query);
    r2_gpu_result_v1(call, status, op, adapter, member);
    int endpoint_ok = r2_gpu_after_v1(call, op, adapter, member, status != 0);
    call->data_valid = status == 0 && endpoint_ok;
    return call->data_valid != 0;
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_gpu_acquire_once_v1(void)
{
    struct r2_win_gpu_report_v1 *r = &r2_gpu_report_v1;
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    NTSTATUS status;
    uint32_t i, j, n;
    int valid;
    if (!r2_own_enter_v1()) {
        InterlockedExchange(&r2_gpu_v1.race, 1);
        InterlockedExchange(&r2_own_stop_v1, 1);
        return R2_GPU_BUSY;
    }
    if (r->acquisition_consumed || r->finish_consumed) {
        r2_gpu_fault_v1(R2_GPU_OP_STATE, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_STATE, 0, 0, 0);
        return r2_gpu_leave_v1();
    }
    r->acquisition_consumed = 1;
    r2_gpu_v1.original_creator = r2_own_v1.creator;
    r->creator_pid = o->creator_pid; r->creator_tid = o->creator_tid;
    r->creator_creation_100ns = o->creator_creation_100ns.value;
    r->intent_serial = o->intent_serial; r->lease_epoch_qpc = o->lease_epoch_qpc;
    r->qpc_frequency = o->qpc_frequency; r->stop_deadline_qpc = o->stop_deadline_qpc;
    r->cleanup_deadline_qpc = o->cleanup_deadline_qpc;
    if (!o->attempt_consumed || !r2_own_v1.deadline_bound || !r2_own_v1.creator ||
        o->creator_creation_100ns.state != R2_WIN_JOB_FIELD_VALID ||
        o->lifecycle != R2_OWN_INTENT_HELD || o->birth_attempted || o->finish_started ||
        r2_own_stopped_v1() || o->lease_epoch_qpc <= 0 || o->qpc_frequency <= 0 ||
        o->stop_deadline_qpc <= o->lease_epoch_qpc ||
        o->cleanup_deadline_qpc <= o->stop_deadline_qpc) {
        r2_gpu_fault_v1(R2_GPU_OP_STATE, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_STATE, 0, 0, 0);
        return r2_gpu_leave_v1();
    }
    r2_gpu_v1.sizing.Filter.IncludeComputeOnly = 1;
    r2_gpu_v1.sizing.Filter.IncludeDisplayOnly = 1;
    r2_gpu_v1.sizing.Filter.IncludeVirtualGpuOnly = 1;
    if (!r2_gpu_before_v1(&r->sizing, R2_GPU_OP_ENUM_SIZE, 0, 0, 0)) return r2_gpu_leave_v1();
    r->sizing.attempted = 1; ++r->native_work_count;
    status = D3DKMTEnumAdapters3(&r2_gpu_v1.sizing);
    r2_gpu_result_v1(&r->sizing, status, R2_GPU_OP_ENUM_SIZE, 0, 0);
    r->sizing_count_bits = r2_gpu_v1.sizing.NumAdapters;
    valid = r2_gpu_after_v1(&r->sizing, R2_GPU_OP_ENUM_SIZE, 0, 0, status != 0);
    if (status != 0 || !valid) return r2_gpu_leave_v1();
    r->sizing_count_valid = 1; r->sizing.data_valid = 1;
    if (!r->sizing_count_bits || r->sizing_count_bits > R2_WIN_GPU_ADAPTER_CAP) {
        r2_gpu_fault_v1(R2_GPU_OP_ENUM_SIZE, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_BOUND, 0, 0, 0);
        return r2_gpu_leave_v1();
    }
    r2_gpu_v1.populate.Filter.IncludeComputeOnly = 1;
    r2_gpu_v1.populate.Filter.IncludeDisplayOnly = 1;
    r2_gpu_v1.populate.Filter.IncludeVirtualGpuOnly = 1;
    r2_gpu_v1.populate.NumAdapters = r->sizing_count_bits;
    r2_gpu_v1.populate.pAdapters = r2_gpu_v1.opaque_adapters;
    if (!r2_gpu_before_v1(&r->populate, R2_GPU_OP_ENUM_POPULATE, 0, 0, 0)) return r2_gpu_leave_v1();
    r->populate.attempted = 1; ++r->native_work_count;
    status = D3DKMTEnumAdapters3(&r2_gpu_v1.populate);
    /* This count is retained as bits ONLY until success and complete validation.
     * On failure, do not derive any index, handle or cleanup from this count. */
    r->populated_count_bits = r2_gpu_v1.populate.NumAdapters;
    r2_gpu_result_v1(&r->populate, status, R2_GPU_OP_ENUM_POPULATE, 0, 0);
    if (status != 0) {
        r->ownership = R2_GPU_ENUM_FAILED_OWNERSHIP_UNKNOWN;
        r2_gpu_stop_v1(R2_OWN_RESIDUAL_SAMPLE | R2_OWN_RESIDUAL_CLOSE);
        (void)r2_gpu_after_v1(&r->populate, R2_GPU_OP_ENUM_POPULATE, 0, 0, 1);
        return r2_gpu_leave_v1();
    }
    n = r->populated_count_bits;
    valid = n != 0 && n <= R2_WIN_GPU_ADAPTER_CAP && n <= r->sizing_count_bits;
    if (valid) {
        for (i = 0; i < n; ++i) {
            if (!r2_gpu_v1.opaque_adapters[i].hAdapter) { valid = 0; break; }
            for (j = 0; j < i; ++j)
                if (r2_gpu_v1.opaque_adapters[j].hAdapter == r2_gpu_v1.opaque_adapters[i].hAdapter)
                    { valid = 0; break; }
            if (!valid) break;
        }
    }
    if (!valid) {
        r->ownership = R2_GPU_ENUM_INVALID_OWNERSHIP_UNKNOWN;
        r2_gpu_fault_v1(R2_GPU_OP_ENUM_POPULATE, R2_GPU_FAULT_INVARIANT,
            n == 0 || n > R2_WIN_GPU_ADAPTER_CAP || n > r->sizing_count_bits ?
                R2_GPU_REASON_BOUND : R2_GPU_REASON_HANDLE, 0, 0, 0);
        r2_gpu_stop_v1(R2_OWN_RESIDUAL_CLOSE);
        (void)r2_gpu_after_v1(&r->populate, R2_GPU_OP_ENUM_POPULATE, 0, 0, 1);
        return r2_gpu_leave_v1();
    }
    /* All original handles are adopted before ANY subsequent native query,
     * including the post-enumeration creator-identity checks that can fail. */
    for (i = 0; i < n; ++i) {
        D3DKMT_ADAPTERINFO *a = &r2_gpu_v1.opaque_adapters[i];
        r2_gpu_v1.original[i] = a->hAdapter; r->adapters[i].adopted = 1;
        r->adapters[i].luid_low = a->AdapterLuid.LowPart;
        r->adapters[i].luid_high = a->AdapterLuid.HighPart;
        r->adapters[i].sources = a->NumOfSources;
        r->adapters[i].precise_present_regions_bits = (uint32_t)a->bPrecisePresentRegionsPreferred;
    }
    r->adopted_count = n; r->ownership = R2_GPU_OWN_KNOWN;
    r->populated_count_valid = 1;
    if (!r2_gpu_after_v1(&r->populate, R2_GPU_OP_ENUM_POPULATE, 0, 0, 0)) return r2_gpu_leave_v1();
    r->populate.data_valid = 1;
    for (i = 0; i < n; ++i) {
        struct r2_win_gpu_adapter_v1 *a = &r->adapters[i];
        valid = r2_gpu_query_v1(i, 0, KMTQAITYPE_ADAPTERTYPE, &r2_gpu_v1.types[i],
            sizeof(r2_gpu_v1.types[i]), &a->type, R2_GPU_OP_ADAPTER_TYPE);
        a->adapter_type_bits = r2_gpu_v1.types[i].Value;
        if (!valid) return r2_gpu_leave_v1();
        valid = r2_gpu_query_v1(i, 0, KMTQAITYPE_GETSEGMENTSIZE, &r2_gpu_v1.segments[i],
            sizeof(r2_gpu_v1.segments[i]), &a->segments, R2_GPU_OP_SEGMENTS);
        a->dedicated_video = r2_gpu_v1.segments[i].DedicatedVideoMemorySize;
        a->dedicated_system = r2_gpu_v1.segments[i].DedicatedSystemMemorySize;
        a->shared_system = r2_gpu_v1.segments[i].SharedSystemMemorySize;
        if (!valid) return r2_gpu_leave_v1();
        valid = r2_gpu_query_v1(i, 0, KMTQAITYPE_PHYSICALADAPTERCOUNT, &r2_gpu_v1.counts[i],
            sizeof(r2_gpu_v1.counts[i]), &a->count, R2_GPU_OP_MEMBER_COUNT);
        a->member_count = r2_gpu_v1.counts[i].Count;
        if (!valid) return r2_gpu_leave_v1();
        if (!a->member_count || a->member_count > R2_WIN_GPU_MEMBER_CAP) {
            a->count.data_valid = 0;
            r2_gpu_fault_v1(R2_GPU_OP_MEMBER_COUNT, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_BOUND, 0, i, 0);
            return r2_gpu_leave_v1();
        }
        for (j = 0; j < a->member_count; ++j) {
            D3DKMT_SEGMENTGROUPSIZEINFO *native = &r2_gpu_v1.members[i][j];
            struct r2_win_gpu_member_v1 *m = &a->members[j];
            native->PhysicalAdapterIndex = j; m->input_index = j;
            valid = r2_gpu_query_v1(i, j, KMTQAITYPE_GETSEGMENTGROUPSIZE, native,
                sizeof(*native), &m->segments, R2_GPU_OP_MEMBER_SEGMENTS);
            m->returned_index = native->PhysicalAdapterIndex;
            m->legacy_dedicated_video = native->LegacyInfo.DedicatedVideoMemorySize;
            m->legacy_dedicated_system = native->LegacyInfo.DedicatedSystemMemorySize;
            m->legacy_shared_system = native->LegacyInfo.SharedSystemMemorySize;
            m->local_bytes = native->LocalMemory; m->nonlocal_bytes = native->NonLocalMemory;
            m->nonbudget_bytes = native->NonBudgetMemory;
            if (!valid) return r2_gpu_leave_v1();
            if (m->returned_index != j) {
                m->segments.data_valid = 0;
                r2_gpu_fault_v1(R2_GPU_OP_MEMBER_SEGMENTS, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_INDEX, 0, i, j);
                return r2_gpu_leave_v1();
            }
        }
    }
    r->acquisition_complete = 1;
    return r2_gpu_leave_v1();
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_gpu_finish_once_v1(void)
{
    struct r2_win_gpu_report_v1 *r = &r2_gpu_report_v1;
    uint32_t i;
    InterlockedExchange(&r2_own_stop_v1, 1);
    if (!r2_own_enter_v1()) {
        InterlockedExchange(&r2_gpu_v1.race, 1);
        return R2_GPU_BUSY;
    }
    if (r->finish_consumed) return r2_gpu_leave_v1();
    r->finish_consumed = 1;
    if (!r->acquisition_consumed) {
        r2_gpu_fault_v1(R2_GPU_OP_FINISH, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_STATE, 0, 0, 0);
        return r2_gpu_leave_v1();
    }
    if (r->ownership == R2_GPU_ENUM_FAILED_OWNERSHIP_UNKNOWN ||
        r->ownership == R2_GPU_ENUM_INVALID_OWNERSHIP_UNKNOWN) {
        r2_gpu_stop_v1(R2_OWN_RESIDUAL_CLOSE);
        return r2_gpu_leave_v1();
    }
    for (i = 0; i < r->adopted_count; ++i) {
        struct r2_win_gpu_adapter_v1 *a = &r->adapters[i];
        D3DKMT_CLOSEADAPTER close = {0};
        NTSTATUS status;
        if (a->close_consumed) continue;
        if (!a->adopted || !r2_gpu_v1.original[i]) {
            r2_gpu_fault_v1(R2_GPU_OP_CLOSE, R2_GPU_FAULT_INVARIANT, R2_GPU_REASON_HANDLE, 0, i, 0);
            r2_gpu_stop_v1(R2_OWN_RESIDUAL_CLOSE); continue;
        }
        if (!r2_gpu_before_v1(&a->close, R2_GPU_OP_CLOSE, i, 0, 1)) {
            r2_gpu_stop_v1(R2_OWN_RESIDUAL_CLOSE); break;
        }
        close.hAdapter = r2_gpu_v1.original[i];
        /* Original typed handle retained privately even after consumption.
         * No later call can use it again; uncertain failure is not a release. */
        a->close_consumed = 1; ++r->close_consumed_count;
        a->close.attempted = 1; ++r->native_work_count;
        status = D3DKMTCloseAdapter(&close);
        r2_gpu_result_v1(&a->close, status, R2_GPU_OP_CLOSE, i, 0);
        if (status == 0) { a->close_succeeded = 1; ++r->close_succeeded_count; }
        else r2_gpu_stop_v1(R2_OWN_RESIDUAL_CLOSE);
        int endpoint_ok = r2_gpu_after_v1(&a->close, R2_GPU_OP_CLOSE, i, 0, 1);
        a->close.data_valid = status == 0 && endpoint_ok;
        if (!endpoint_ok) r2_gpu_stop_v1(R2_OWN_RESIDUAL_CLOSE);
    }
    return r2_gpu_leave_v1();
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_gpu_copy_report_v1(
    struct r2_win_gpu_report_v1 *out, size_t out_size)
{
    if (out_size != sizeof(*out) ||
        !r2_own_range_v1(out, out_size, _Alignof(struct r2_win_gpu_report_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, &r2_gpu_v1, sizeof(r2_gpu_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, &r2_gpu_report_v1, sizeof(r2_gpu_report_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, &r2_own_v1, sizeof(r2_own_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, &r2_own_report_v1, sizeof(r2_own_report_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, &r2_mm_report_v1, sizeof(r2_mm_report_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, (const void *)&r2_own_guard_v1, sizeof(r2_own_guard_v1)) ||
        !r2_mm_disjoint_v1(out, out_size, (const void *)&r2_own_stop_v1, sizeof(r2_own_stop_v1)))
        return R2_GPU_BAD_ARGUMENT;
    if (!r2_own_enter_v1()) return R2_GPU_BUSY;
    r2_gpu_refresh_v1();
    memcpy(out, &r2_gpu_report_v1, sizeof(*out));
    InterlockedExchange(&r2_own_guard_v1, 0);
    return R2_GPU_COPY_OK;
}
#endif
#endif

/* C00 positive original-storage source limb, opt-in only; see public contract.
 * Primary SDK references: fileapi/CreateFileW; ioapiset/DeviceIoControl;
 * winioctl/VOLUME_DISK_EXTENTS, STORAGE_DEVICE_ID_DESCRIPTOR,
 * STORAGE_ACCESS_ALIGNMENT_DESCRIPTOR; ntddstor/STORAGE_IDENTIFIER.
 * First ERROR_MORE_DATA sizing is documented by VOLUME_DISK_EXTENTS.
 */
#if defined(R2_TARGET_WINDOWS_SEED) && defined(R2_ENABLE_WIN_STORAGE_RAW_V1)
#ifndef R2_WIN_STORAGE_RAW_V1_BODY
#define R2_WIN_STORAGE_RAW_V1_BODY
#include <Windows.h>
#include <winioctl.h>

_Static_assert(sizeof(DISK_EXTENT) == 24 && offsetof(DISK_EXTENT, StartingOffset) == 8 &&
    offsetof(DISK_EXTENT, ExtentLength) == 16 && offsetof(VOLUME_DISK_EXTENTS, Extents) == 8 &&
    offsetof(VOLUME_DISK_EXTENTS, Extents) + 8 * sizeof(DISK_EXTENT) == 200 &&
    sizeof(STORAGE_DEVICE_NUMBER) == 12 && sizeof(GET_LENGTH_INFORMATION) == 8 &&
    sizeof(STORAGE_ACCESS_ALIGNMENT_DESCRIPTOR) == 28,
    "storage requires actual naturally aligned Win64 SDK layouts");
_Static_assert(sizeof(struct r2_win_storage_spec_v1) == 32 &&
    sizeof(struct r2_win_storage_clock_v1) == 24 &&
    sizeof(struct r2_win_storage_call_v1) == 160 &&
    sizeof(struct r2_win_storage_identifier_v1) == 32 &&
    sizeof(struct r2_win_storage_extent_v1) == 32 &&
    sizeof(struct r2_win_storage_disk_v1) == 6312 &&
    sizeof(struct r2_win_storage_report_v1) == R2_WIN_STORAGE_REPORT_BYTES,
    "storage raw public ABI changed");
_Static_assert(sizeof(((struct r2_win_storage_disk_v1 *)0)->device_number_opaque) >=
    sizeof(STORAGE_DEVICE_NUMBER) &&
    sizeof(((struct r2_win_storage_disk_v1 *)0)->alignment_opaque) >=
    sizeof(STORAGE_ACCESS_ALIGNMENT_DESCRIPTOR) &&
    offsetof(STORAGE_IDENTIFIER, Identifier) <= sizeof(STORAGE_IDENTIFIER),
    "storage SDK spans must fit fixed raw buffers");

struct r2_storage_private_v1 {
    HANDLE original_creator, originals[1 + R2_WIN_STORAGE_DISK_CAP];
    uint32_t usable[1 + R2_WIN_STORAGE_DISK_CAP];
    WCHAR volume[R2_WIN_STORAGE_PATH_UNITS], derived_disk[32];
    volatile LONG acquire_race, finish_race;
    uint32_t acquire_race_recorded, finish_race_recorded;
};
static struct r2_storage_private_v1 r2_storage_v1;
static struct r2_win_storage_report_v1 r2_storage_report_v1 = {
    .abi = R2_WIN_STORAGE_RAW_ABI, .size = sizeof(struct r2_win_storage_report_v1),
    .remaining_unproven = R2_WIN_STORAGE_UNPROVEN_ALL
};
_Static_assert(sizeof(r2_storage_v1) + sizeof(r2_storage_report_v1) <= 73728,
    "storage fixed private state and report bound");
_Static_assert(R2_WIN_STORAGE_CALL_CAP == 1 + 2 + 8 * 5 + 9,
    "storage lifetime API work bound");

static void r2_storage_stop_v1(uint32_t residual)
{
    InterlockedExchange(&r2_own_stop_v1, 1);
    r2_own_report_v1.stop_new = 1;
    r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE | residual;
    r2_storage_report_v1.stop_new = 1;
    if ((r2_own_v1.process && !r2_own_report_v1.process_signaled) ||
        (r2_own_v1.thread && !r2_own_report_v1.thread_signaled) ||
        (r2_own_v1.job && !r2_own_report_v1.job_empty))
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_JOIN;
}
static void r2_storage_fault_v1(uint32_t op, uint32_t kind, uint32_t reason,
    DWORD error, uint32_t ordinal, uint32_t disk)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    struct r2_win_storage_fault_v1 f = {
        op, kind, reason, ordinal, disk, (uint32_t)error,
        kind == R2_STORAGE_FAULT_WIN32, 0
    };
    r2_storage_stop_v1(op == R2_STORAGE_OP_CLOSE ? R2_OWN_RESIDUAL_CLOSE : 0);
    if (!r->fault_count) r->primary = f;
    else if (r->fault_count == 1) r->secondary = f;
    if (r->fault_count < R2_WIN_STORAGE_FAULT_CAP) r->faults[r->fault_count] = f;
    else if (r->omitted_fault_count != UINT32_MAX) ++r->omitted_fault_count;
    if (r->fault_count != UINT32_MAX) ++r->fault_count;
}
static int r2_storage_bad_v1(uint32_t op, uint32_t reason,
    struct r2_win_storage_call_v1 *c, uint32_t disk)
{
    r2_storage_fault_v1(op, R2_STORAGE_FAULT_INVARIANT, reason, 0,
        c ? c->ordinal : 0, disk);
    return 0;
}
static void r2_storage_refresh_v1(void)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    if (InterlockedCompareExchange(&r2_storage_v1.acquire_race, 0, 0) &&
        !r2_storage_v1.acquire_race_recorded) {
        r2_storage_v1.acquire_race_recorded = 1; r->acquisition_consumed = 1;
        r2_storage_bad_v1(R2_STORAGE_OP_STATE, R2_STORAGE_REASON_RACE, NULL, 0);
    }
    if (InterlockedCompareExchange(&r2_storage_v1.finish_race, 0, 0) &&
        !r2_storage_v1.finish_race_recorded) {
        r2_storage_v1.finish_race_recorded = 1; r->finish_consumed = 1;
        r2_storage_bad_v1(R2_STORAGE_OP_FINISH, R2_STORAGE_REASON_RACE, NULL, 0);
    }
    r->stop_new = (uint32_t)r2_own_stopped_v1();
    r->owner_lifecycle = r2_own_report_v1.lifecycle;
    r->all_known_once_closed = r->acquisition_consumed && !r->ambiguous_ownership &&
        r->close_consumed_count == r->adopted_count &&
        r->close_succeeded_count == r->adopted_count;
    r->pending_liability = r->in_flight || r->ambiguous_ownership || r->fault_count ||
        (r->adopted_count && !r->all_known_once_closed);
    if (r->finish_consumed && r->pending_liability) r->status = R2_STORAGE_RETAINED;
    else if (r->acquisition_complete && r->finish_consumed && r->all_known_once_closed &&
        !r->fault_count && !r->pending_liability) r->status = R2_STORAGE_RAW_COMPLETE;
    else if (r->fault_count) r->status = R2_STORAGE_RAW_PARTIAL;
    else r->status = r->acquisition_consumed ? R2_STORAGE_PENDING : R2_STORAGE_UNUSED;
}
static uint32_t r2_storage_leave_v1(void)
{
    uint32_t status;
    r2_storage_refresh_v1(); status = r2_storage_report_v1.status;
    InterlockedExchange(&r2_own_guard_v1, 0);
    return status;
}
/* Each operand is a complete static object; caller range was checked first. */
static int r2_storage_disjoint_v1(const void *p, size_t size)
{
#define R2_STORAGE_DISJOINT(object) \
    if (!r2_mm_disjoint_v1(p, size, (const void *)&(object), sizeof(object))) return 0
    R2_STORAGE_DISJOINT(r2_storage_v1);
    R2_STORAGE_DISJOINT(r2_storage_report_v1);
    R2_STORAGE_DISJOINT(r2_own_v1);
    R2_STORAGE_DISJOINT(r2_own_report_v1);
    R2_STORAGE_DISJOINT(r2_own_guard_v1);
    R2_STORAGE_DISJOINT(r2_own_stop_v1);
    R2_STORAGE_DISJOINT(r2_mm_report_v1);
#if defined(R2_ENABLE_WIN_GPU_RAW_V1)
    R2_STORAGE_DISJOINT(r2_gpu_v1);
    R2_STORAGE_DISJOINT(r2_gpu_report_v1);
#endif
#undef R2_STORAGE_DISJOINT
    return 1;
}
static int r2_storage_context_v1(struct r2_win_storage_call_v1 *c)
{
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    if (!r2_own_v1.creator || r2_own_v1.creator != r2_storage_v1.original_creator ||
        !r2_own_v1.deadline_bound || !o->attempt_consumed || o->finish_started ||
        o->creator_creation_100ns.state != R2_WIN_JOB_FIELD_VALID ||
        o->lifecycle < R2_OWN_INTENT_HELD || o->lifecycle == R2_OWN_CLOSING ||
        o->lifecycle == R2_OWN_DONE || o->lifecycle > R2_OWN_RETAINED ||
        o->creator_pid != r->creator_pid || o->creator_tid != r->creator_tid ||
        o->creator_creation_100ns.value != r->creator_creation_100ns ||
        o->intent_serial != r->intent_serial || o->lease_epoch_qpc != r->lease_epoch_qpc ||
        o->qpc_frequency != r->qpc_frequency ||
        o->stop_deadline_qpc != r->stop_deadline_qpc ||
        o->cleanup_deadline_qpc != r->cleanup_deadline_qpc) {
        r2_storage_fault_v1(c->operation, R2_STORAGE_FAULT_OWNER,
            R2_STORAGE_REASON_CONTEXT, 0, c->ordinal, c->disk_index);
        return 0;
    }
    if (r->identity_check_count >= 2 * R2_WIN_STORAGE_CALL_CAP)
        return r2_storage_bad_v1(c->operation, R2_STORAGE_REASON_COUNTER, c, c->disk_index);
    ++r->identity_check_count;
    if (GetCurrentProcessId() != r->creator_pid || GetCurrentThreadId() != r->creator_tid ||
        !r2_own_creator_identity_v1()) {
        r2_storage_fault_v1(c->operation, R2_STORAGE_FAULT_OWNER,
            R2_STORAGE_REASON_IDENTITY, 0, c->ordinal, c->disk_index);
        return 0;
    }
    return 1;
}
static int r2_storage_clock_v1(struct r2_win_storage_call_v1 *c,
    uint32_t endpoint, int cleanup)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    struct r2_win_storage_clock_v1 *clock = &c->clocks[endpoint];
    LARGE_INTEGER now = {0};
    BOOL result;
    DWORD error;
    int64_t deadline = cleanup ? r->cleanup_deadline_qpc : r->stop_deadline_qpc;
    if (r->qpc_work_count >= 4 * R2_WIN_STORAGE_CALL_CAP)
        return r2_storage_bad_v1(c->operation, R2_STORAGE_REASON_COUNTER, c, c->disk_index);
    ++r->qpc_work_count; clock->attempted = 1;
    result = QueryPerformanceCounter(&now);
    if (!result) {
        error = GetLastError();
        clock->raw_result = (uint32_t)result;
        clock->win32_error = error; clock->win32_error_valid = 1;
        o->clock_valid = 0; o->residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        r2_storage_fault_v1(c->operation, R2_STORAGE_FAULT_WIN32,
            R2_STORAGE_REASON_CLOCK, error, c->ordinal, c->disk_index);
        return 0;
    }
    clock->raw_result = (uint32_t)result; clock->raw_qpc = now.QuadPart;
    if (now.QuadPart <= 0 || now.QuadPart < o->last_qpc || !o->clock_valid ||
        (o->residual_bits & R2_OWN_RESIDUAL_CLOCK)) {
        o->clock_valid = 0; o->residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        return r2_storage_bad_v1(c->operation, R2_STORAGE_REASON_CLOCK, c, c->disk_index);
    }
    o->last_qpc = now.QuadPart;
    if (deadline <= 0 || now.QuadPart >= deadline) {
        o->residual_bits |= R2_OWN_RESIDUAL_DEADLINE;
        return r2_storage_bad_v1(c->operation, R2_STORAGE_REASON_DEADLINE, c, c->disk_index);
    }
    return 1;
}
static struct r2_win_storage_call_v1 *r2_storage_call_v1(uint32_t op,
    uint32_t disk, uint32_t capacity, int cleanup)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    struct r2_win_storage_call_v1 *c;
    int identity_ok, clock_ok;
    if (r->call_count >= R2_WIN_STORAGE_CALL_CAP ||
        r->native_work_count >= R2_WIN_STORAGE_CALL_CAP) {
        r2_storage_bad_v1(op, R2_STORAGE_REASON_COUNTER, NULL, disk); return NULL;
    }
    c = &r->calls[r->call_count++]; c->ordinal = r->call_count;
    c->operation = op; c->disk_index = disk; c->capacity = capacity;
    if (!cleanup && (r2_own_stopped_v1() || r2_own_report_v1.birth_attempted ||
        r2_own_report_v1.lifecycle != R2_OWN_INTENT_HELD || r->finish_consumed)) {
        r2_storage_bad_v1(op, R2_STORAGE_REASON_STATE, c, disk); return NULL;
    }
    if (!r2_storage_clock_v1(c, 0, cleanup)) return NULL;
    identity_ok = r2_storage_context_v1(c);
    clock_ok = r2_storage_clock_v1(c, 1, cleanup);
    if (!identity_ok || !clock_ok) return NULL;
    if (!cleanup && r2_own_stopped_v1()) {
        r2_storage_bad_v1(op, R2_STORAGE_REASON_RACE, c, disk); return NULL;
    }
    return c;
}
static void r2_storage_enter_native_v1(struct r2_win_storage_call_v1 *c)
{
    c->attempted = 1; ++r2_storage_report_v1.native_work_count;
    r2_storage_report_v1.in_flight_ordinal = c->ordinal;
    r2_storage_report_v1.in_flight = 1;
    r2_storage_report_v1.pending_liability = 1;
}
static int r2_storage_after_v1(struct r2_win_storage_call_v1 *c, int cleanup)
{
    int first_ok, identity_ok, last_ok;
    r2_storage_report_v1.in_flight = 0;
    first_ok = r2_storage_clock_v1(c, 2, cleanup);
    identity_ok = r2_storage_context_v1(c);
    last_ok = r2_storage_clock_v1(c, 3, cleanup);
    if (!cleanup && r2_own_stopped_v1()) {
        /* API failure is already a primary event; an external stop is a race. */
        if (!r2_storage_report_v1.fault_count)
            r2_storage_bad_v1(c->operation, R2_STORAGE_REASON_RACE, c, c->disk_index);
        return 0;
    }
    c->boundary_valid = first_ok && identity_ok && last_ok;
    return c->boundary_valid != 0;
}
static int r2_storage_open_v1(const WCHAR *path, uint32_t slot, uint32_t disk)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    uint32_t op = slot ? R2_STORAGE_OP_DISK_OPEN : R2_STORAGE_OP_VOLUME_OPEN;
    struct r2_win_storage_call_v1 *c = r2_storage_call_v1(op, disk, 0, 0);
    HANDLE original;
    DWORD error;
    int boundary;
    if (!c) return 0;
    r2_storage_enter_native_v1(c);
    original = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_EXISTING, 0, NULL);
    if (original == INVALID_HANDLE_VALUE) {
        error = GetLastError();
        c->handle_outcome = R2_STORAGE_HANDLE_INVALID;
        c->win32_error = error; c->win32_error_valid = 1;
        r2_storage_fault_v1(op, R2_STORAGE_FAULT_WIN32, 0, error, c->ordinal, disk);
    } else {
        /* Ownership is recorded BEFORE any clock, identity query or other API. */
        r2_storage_v1.originals[slot] = original;
        if (original) {
            r2_storage_v1.usable[slot] = 1; ++r->adopted_count;
            if (slot) r->disks[disk].adopted = 1; else r->volume_adopted = 1;
            c->handle_outcome = R2_STORAGE_HANDLE_VALID;
        } else {
            c->handle_outcome = R2_STORAGE_HANDLE_NULL_AMBIGUOUS;
            r->ambiguous_ownership = 1;
            r2_storage_bad_v1(op, R2_STORAGE_REASON_HANDLE, c, disk);
        }
    }
    boundary = r2_storage_after_v1(c, 0);
    return c->handle_outcome == R2_STORAGE_HANDLE_VALID && boundary;
}
/* Returned FALSE bytes are always retained as opaque. The sole documented
 * first-extent partial is interpreted by its caller, never here. */
static int r2_storage_ioctl_v1(uint32_t slot, uint32_t disk, uint32_t op,
    DWORD control, void *input, DWORD input_size, void *output, DWORD capacity,
    int first_extent, struct r2_win_storage_call_v1 **observed)
{
    struct r2_win_storage_call_v1 *c = r2_storage_call_v1(op, disk, capacity, 0);
    DWORD returned = 0, error = 0;
    BOOL result;
    int boundary;
    *observed = c;
    if (!c) return 0;
    if (!r2_storage_v1.usable[slot])
        return r2_storage_bad_v1(op, R2_STORAGE_REASON_HANDLE, c, disk);
    r2_storage_enter_native_v1(c);
    result = DeviceIoControl(r2_storage_v1.originals[slot], control, input,
        input_size, output, capacity, &returned, NULL);
    if (!result) error = GetLastError();
    c->raw_bool = (uint32_t)result; c->bool_observed = 1;
    c->raw_bytes_returned = returned;
    c->opaque_bytes = result && returned <= capacity ? returned : capacity;
    if (!result) {
        c->win32_error = error; c->win32_error_valid = 1;
        if (first_extent && error == ERROR_MORE_DATA) c->documented_partial = 1;
        else r2_storage_fault_v1(op, R2_STORAGE_FAULT_WIN32, 0, error, c->ordinal, disk);
    }
    boundary = r2_storage_after_v1(c, 0);
    if (!boundary) return 0;
    if (returned > capacity)
        return r2_storage_bad_v1(op, R2_STORAGE_REASON_BOUND, c, disk);
    return result ? 1 : (c->documented_partial ? 2 : 0);
}
static int r2_storage_hex_v1(WCHAR c)
{
    return (c >= L'0' && c <= L'9') || (c >= L'a' && c <= L'f') ||
        (c >= L'A' && c <= L'F');
}
static int r2_storage_copy_intent_v1(const struct r2_win_storage_spec_v1 *spec)
{
    struct r2_win_storage_spec_v1 s;
    uint32_t i;
    size_t bytes;
    if (!r2_own_range_v1(spec, sizeof(*spec), _Alignof(struct r2_win_storage_spec_v1)) ||
        !r2_storage_disjoint_v1(spec, sizeof(*spec))) return 0;
    s = *spec;
    if (s.abi != R2_WIN_STORAGE_RAW_ABI || s.size != sizeof(s) ||
        s.reserved[0] || s.reserved[1] || s.reserved[2] ||
        s.units < 7 || s.units > R2_WIN_STORAGE_PATH_UNITS) return 0;
    bytes = (size_t)s.units * sizeof(uint16_t);
    if (!r2_own_range_v1(s.volume_device, bytes, _Alignof(uint16_t)) ||
        !r2_storage_disjoint_v1(s.volume_device, bytes) ||
        !r2_mm_disjoint_v1(s.volume_device, bytes, spec, sizeof(*spec))) return 0;
    for (i = 0; i < s.units; ++i) r2_storage_v1.volume[i] = s.volume_device[i];
    if (r2_storage_v1.volume[s.units - 1] != 0) return 0;
    for (i = 0; i + 1 < s.units; ++i) if (!r2_storage_v1.volume[i]) return 0;
    if (s.units == 7) {
        const WCHAR *p = r2_storage_v1.volume;
        if (p[0] != L'\\' || p[1] != L'\\' || p[2] != L'.' || p[3] != L'\\' ||
            p[4] < L'A' || p[4] > L'Z' || p[5] != L':') return 0;
    } else {
        const WCHAR *p = r2_storage_v1.volume;
        static const WCHAR prefix[] = L"\\\\?\\Volume{";
        if (s.units != 49 || p[47] != L'}') return 0;
        for (i = 0; i < 11; ++i) if (p[i] != prefix[i]) return 0;
        for (i = 11; i < 47; ++i) {
            if (i == 19 || i == 24 || i == 29 || i == 34) {
                if (p[i] != L'-') return 0;
            } else if (!r2_storage_hex_v1(p[i])) return 0;
        }
    }
    r2_storage_report_v1.path_units = s.units;
    memcpy(r2_storage_report_v1.volume_device, r2_storage_v1.volume, bytes);
    r2_storage_report_v1.intent_valid = 1;
    return 1;
}
/* Disk path is derived ONLY from complete extents; no CRT/locale conversion. */
static int r2_storage_disk_path_v1(DWORD number)
{
    static const WCHAR prefix[] = L"\\\\.\\PhysicalDrive";
    WCHAR reversed[10];
    uint32_t n = 0, i, at = (uint32_t)(sizeof(prefix) / sizeof(prefix[0]) - 1);
    do {
        if (n >= 10) return 0;
        reversed[n++] = (WCHAR)(L'0' + number % 10); number /= 10;
    } while (number);
    if (at + n + 1 > sizeof(r2_storage_v1.derived_disk) / sizeof(WCHAR)) return 0;
    for (i = 0; i < at; ++i) r2_storage_v1.derived_disk[i] = prefix[i];
    for (i = 0; i < n; ++i) r2_storage_v1.derived_disk[at + i] = reversed[n - 1 - i];
    r2_storage_v1.derived_disk[at + n] = 0;
    return 1;
}
static int r2_storage_extents_v1(void)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    struct r2_win_storage_call_v1 *c = NULL;
    DWORD count = 0, initial_count = 0;
    uint32_t source = 0, i, j;
    size_t offset = offsetof(VOLUME_DISK_EXTENTS, Extents), available;
    int result = r2_storage_ioctl_v1(0, 0, R2_STORAGE_OP_EXTENTS,
        IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, NULL, 0, r->extent_opaque[0].bytes,
        (DWORD)sizeof(VOLUME_DISK_EXTENTS), 1, &c);
    if (!result || !c) return 0;
    if (c->raw_bytes_returned < offset)
        return r2_storage_bad_v1(R2_STORAGE_OP_EXTENTS, R2_STORAGE_REASON_BOUND, c, 0);
    memcpy(&count, r->extent_opaque[0].bytes +
        offsetof(VOLUME_DISK_EXTENTS, NumberOfDiskExtents), sizeof(count));
    r->extent_reported_count = count;
    if (!count || count > R2_WIN_STORAGE_EXTENT_CAP)
        return r2_storage_bad_v1(R2_STORAGE_OP_EXTENTS, R2_STORAGE_REASON_BOUND, c, 0);
    if (result == 2) {
        if (count <= 1)
            return r2_storage_bad_v1(R2_STORAGE_OP_EXTENTS, R2_STORAGE_REASON_FORMAT, c, 0);
        initial_count = count; source = 1;
        result = r2_storage_ioctl_v1(0, 0, R2_STORAGE_OP_EXTENTS,
            IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, NULL, 0, r->extent_opaque[1].bytes,
            (DWORD)(offset + R2_WIN_STORAGE_EXTENT_CAP * sizeof(DISK_EXTENT)), 0, &c);
        if (result != 1 || !c) return 0;
        if (c->raw_bytes_returned < offset)
            return r2_storage_bad_v1(R2_STORAGE_OP_EXTENTS, R2_STORAGE_REASON_BOUND, c, 0);
        memcpy(&count, r->extent_opaque[1].bytes +
            offsetof(VOLUME_DISK_EXTENTS, NumberOfDiskExtents), sizeof(count));
        r->extent_reported_count = count;
        if (count != initial_count)
            return r2_storage_bad_v1(R2_STORAGE_OP_EXTENTS, R2_STORAGE_REASON_ASSOCIATION, c, 0);
    }
    available = c->raw_bytes_returned - offset;
    if (!count || count > R2_WIN_STORAGE_EXTENT_CAP ||
        count > available / sizeof(DISK_EXTENT) ||
        count > (c->capacity - offset) / sizeof(DISK_EXTENT))
        return r2_storage_bad_v1(R2_STORAGE_OP_EXTENTS, R2_STORAGE_REASON_BOUND, c, 0);
    /* No derived disk exists until the entire complete array fits both spans. */
    c->output_valid = 1; r->extent_count_valid = 1; r->extent_source_call = c->ordinal;
    for (i = 0; i < count; ++i) {
        DISK_EXTENT native;
        struct r2_win_storage_extent_v1 *e = &r->extents[i];
        memcpy(&native, r->extent_opaque[source].bytes + offset + i * sizeof(native), sizeof(native));
        e->disk_number = native.DiskNumber;
        e->starting_offset = native.StartingOffset.QuadPart;
        e->extent_length = native.ExtentLength.QuadPart;
        ++r->extent_count;
        if (e->starting_offset < 0 || e->extent_length <= 0)
            return r2_storage_bad_v1(R2_STORAGE_OP_EXTENTS, R2_STORAGE_REASON_RANGE, c, i);
    }
    for (i = 0; i < count; ++i) {
        for (j = 0; j < r->disk_count; ++j)
            if (r->disks[j].extent_disk_number == r->extents[i].disk_number) break;
        if (j == r->disk_count) {
            if (j >= R2_WIN_STORAGE_DISK_CAP)
                return r2_storage_bad_v1(R2_STORAGE_OP_EXTENTS, R2_STORAGE_REASON_BOUND, c, i);
            r->disks[j].extent_disk_number = r->extents[i].disk_number; ++r->disk_count;
        }
        r->extents[i].disk_index = j;
    }
    return 1;
}
static int r2_storage_fixed_v1(uint32_t disk, uint32_t op, DWORD control,
    void *input, DWORD input_size, void *output, DWORD size,
    struct r2_win_storage_call_v1 **observed)
{
    if (r2_storage_ioctl_v1(disk + 1, disk, op, control, input, input_size,
        output, size, 0, observed) != 1) return 0;
    if ((*observed)->raw_bytes_returned != size)
        return r2_storage_bad_v1(op, R2_STORAGE_REASON_BOUND, *observed, disk);
    (*observed)->output_valid = 1;
    return 1;
}
/* First pass validates every forward, nonoverlapping header/payload span.
 * Second pass publishes metadata only; payload bytes always remain raw. */
static int r2_storage_ids_v1(uint32_t disk, struct r2_win_storage_call_v1 *c)
{
    struct r2_win_storage_disk_v1 *d = &r2_storage_report_v1.disks[disk];
    STORAGE_DEVICE_ID_DESCRIPTOR header;
    STORAGE_IDENTIFIER identifier;
    size_t start = offsetof(STORAGE_DEVICE_ID_DESCRIPTOR, Identifiers);
    size_t fixed = offsetof(STORAGE_IDENTIFIER, Identifier), at, remaining, end = start;
    uint32_t i, pass;
    if (c->raw_bytes_returned < start)
        return r2_storage_bad_v1(R2_STORAGE_OP_IDS, R2_STORAGE_REASON_BOUND, c, disk);
    memset(&header, 0, sizeof(header)); memcpy(&header, d->id_opaque.bytes, start);
    d->id_version = header.Version; d->id_size = header.Size;
    d->id_reported_count = header.NumberOfIdentifiers; d->id_header_valid = 1;
    d->id_state = R2_STORAGE_IDS_UNINTERPRETED;
    if (header.Size < start || header.Size > c->raw_bytes_returned ||
        header.Size > R2_WIN_STORAGE_ID_BYTES)
        return r2_storage_bad_v1(R2_STORAGE_OP_IDS, R2_STORAGE_REASON_BOUND, c, disk);
    c->output_valid = 1;
    d->id_tail_offset = (uint32_t)start; d->id_tail_bytes = c->raw_bytes_returned - (uint32_t)start;
    if (header.Version != sizeof(STORAGE_DEVICE_ID_DESCRIPTOR))
        return r2_storage_bad_v1(R2_STORAGE_OP_IDS, R2_STORAGE_REASON_UNSUPPORTED, c, disk);
    if (header.Size < sizeof(STORAGE_DEVICE_ID_DESCRIPTOR) ||
        header.NumberOfIdentifiers > R2_WIN_STORAGE_IDENTIFIER_CAP)
        return r2_storage_bad_v1(R2_STORAGE_OP_IDS, R2_STORAGE_REASON_BOUND, c, disk);
    if (!header.NumberOfIdentifiers) return 1;
    for (pass = 0; pass < 2; ++pass) {
        at = start;
        for (i = 0; i < header.NumberOfIdentifiers; ++i) {
            if (at > header.Size || fixed > header.Size - at) goto malformed;
            remaining = header.Size - at;
            memset(&identifier, 0, sizeof(identifier));
            memcpy(&identifier, d->id_opaque.bytes + at, fixed);
            if (identifier.IdentifierSize > remaining - fixed) goto malformed;
            end = at + fixed + identifier.IdentifierSize;
            if (i + 1 < header.NumberOfIdentifiers) {
                if (!identifier.NextOffset || identifier.NextOffset < fixed + identifier.IdentifierSize ||
                    identifier.NextOffset > remaining ||
                    fixed > remaining - identifier.NextOffset) goto malformed;
            } else if (identifier.NextOffset != 0) goto malformed;
            if (pass) {
                struct r2_win_storage_identifier_v1 *out = &d->identifiers[i];
                out->code_set = (uint32_t)identifier.CodeSet;
                out->type = (uint32_t)identifier.Type;
                out->association = (uint32_t)identifier.Association;
                out->identifier_size = identifier.IdentifierSize;
                out->next_offset = identifier.NextOffset; out->source_offset = (uint32_t)at;
                out->payload_offset = (uint32_t)(at + fixed);
                out->payload_bytes = identifier.IdentifierSize;
                ++d->id_parsed_count;
            }
            if (i + 1 < header.NumberOfIdentifiers) at += identifier.NextOffset;
        }
    }
    d->id_state = R2_STORAGE_IDS_PARSED;
    d->id_tail_offset = (uint32_t)end;
    d->id_tail_bytes = c->raw_bytes_returned - (uint32_t)end;
    return 1;
malformed:
    d->id_state = R2_STORAGE_IDS_MALFORMED;
    return r2_storage_bad_v1(R2_STORAGE_OP_IDS, R2_STORAGE_REASON_FORMAT, c, disk);
}
static int r2_storage_disk_v1(uint32_t disk)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    struct r2_win_storage_disk_v1 *d = &r->disks[disk];
    struct r2_win_storage_call_v1 *c = NULL;
    STORAGE_DEVICE_NUMBER number;
    GET_LENGTH_INFORMATION length;
    STORAGE_ACCESS_ALIGNMENT_DESCRIPTOR alignment;
    STORAGE_PROPERTY_QUERY query;
    uint32_t i;
    if (!r2_storage_disk_path_v1(d->extent_disk_number))
        return r2_storage_bad_v1(R2_STORAGE_OP_DISK_OPEN, R2_STORAGE_REASON_BOUND, NULL, disk);
    if (!r2_storage_open_v1(r2_storage_v1.derived_disk, disk + 1, disk)) return 0;
    if (!r2_storage_fixed_v1(disk, R2_STORAGE_OP_DEVICE_NUMBER,
        IOCTL_STORAGE_GET_DEVICE_NUMBER, NULL, 0, d->device_number_opaque,
        (DWORD)sizeof(number), &c)) return 0;
    memcpy(&number, d->device_number_opaque, sizeof(number));
    d->device_type = number.DeviceType; d->device_number = number.DeviceNumber;
    d->partition_number = number.PartitionNumber; d->device_number_valid = 1;
    if (number.DeviceType != FILE_DEVICE_DISK || number.DeviceNumber != d->extent_disk_number)
        return r2_storage_bad_v1(R2_STORAGE_OP_DEVICE_NUMBER, R2_STORAGE_REASON_ASSOCIATION, c, disk);
    if (!r2_storage_fixed_v1(disk, R2_STORAGE_OP_LENGTH, IOCTL_DISK_GET_LENGTH_INFO,
        NULL, 0, d->length_opaque, (DWORD)sizeof(length), &c)) return 0;
    memcpy(&length, d->length_opaque, sizeof(length));
    d->disk_length = length.Length.QuadPart; d->length_valid = 1;
    if (d->disk_length <= 0)
        return r2_storage_bad_v1(R2_STORAGE_OP_LENGTH, R2_STORAGE_REASON_RANGE, c, disk);
    for (i = 0; i < r->extent_count; ++i) {
        struct r2_win_storage_extent_v1 *e = &r->extents[i];
        if (e->disk_index != disk) continue;
        if (e->starting_offset < 0 || e->extent_length <= 0 ||
            e->starting_offset > d->disk_length ||
            e->extent_length > d->disk_length - e->starting_offset)
            return r2_storage_bad_v1(R2_STORAGE_OP_LENGTH, R2_STORAGE_REASON_RANGE, c, disk);
        e->range_valid = 1;
    }
    memset(&query, 0, sizeof(query));
    query.PropertyId = StorageAccessAlignmentProperty; query.QueryType = PropertyStandardQuery;
    if (!r2_storage_fixed_v1(disk, R2_STORAGE_OP_ALIGNMENT, IOCTL_STORAGE_QUERY_PROPERTY,
        &query, (DWORD)sizeof(query), d->alignment_opaque, (DWORD)sizeof(alignment), &c)) return 0;
    memcpy(&alignment, d->alignment_opaque, sizeof(alignment));
    d->alignment_version = alignment.Version; d->alignment_size = alignment.Size;
    d->bytes_per_cache_line = alignment.BytesPerCacheLine;
    d->cache_alignment_offset = alignment.BytesOffsetForCacheAlignment;
    d->bytes_per_logical_sector = alignment.BytesPerLogicalSector;
    d->bytes_per_physical_sector = alignment.BytesPerPhysicalSector;
    d->sector_alignment_offset = alignment.BytesOffsetForSectorAlignment;
    if (alignment.Version != sizeof(alignment) || alignment.Size != sizeof(alignment))
        return r2_storage_bad_v1(R2_STORAGE_OP_ALIGNMENT, R2_STORAGE_REASON_UNSUPPORTED, c, disk);
    if (!alignment.BytesPerLogicalSector || !alignment.BytesPerPhysicalSector ||
        (alignment.BytesPerLogicalSector & (alignment.BytesPerLogicalSector - 1)) ||
        (alignment.BytesPerPhysicalSector & (alignment.BytesPerPhysicalSector - 1)) ||
        alignment.BytesPerPhysicalSector < alignment.BytesPerLogicalSector ||
        alignment.BytesPerPhysicalSector % alignment.BytesPerLogicalSector ||
        alignment.BytesOffsetForSectorAlignment >= alignment.BytesPerPhysicalSector ||
        alignment.BytesOffsetForSectorAlignment % alignment.BytesPerLogicalSector ||
        (uint64_t)d->disk_length % alignment.BytesPerLogicalSector)
        return r2_storage_bad_v1(R2_STORAGE_OP_ALIGNMENT, R2_STORAGE_REASON_RANGE, c, disk);
    d->alignment_valid = 1;
    for (i = 0; i < r->extent_count; ++i) {
        struct r2_win_storage_extent_v1 *e = &r->extents[i];
        if (e->disk_index != disk) continue;
        if (!e->range_valid || (uint64_t)e->starting_offset % alignment.BytesPerLogicalSector ||
            (uint64_t)e->extent_length % alignment.BytesPerLogicalSector)
            return r2_storage_bad_v1(R2_STORAGE_OP_ALIGNMENT, R2_STORAGE_REASON_RANGE, c, disk);
        e->sector_mapping_valid = 1;
    }
    memset(&query, 0, sizeof(query));
    query.PropertyId = StorageDeviceIdProperty; query.QueryType = PropertyStandardQuery;
    if (r2_storage_ioctl_v1(disk + 1, disk, R2_STORAGE_OP_IDS, IOCTL_STORAGE_QUERY_PROPERTY,
        &query, (DWORD)sizeof(query), d->id_opaque.bytes, R2_WIN_STORAGE_ID_BYTES, 0, &c) != 1)
        return 0;
    return r2_storage_ids_v1(disk, c);
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_storage_acquire_once_v1(
    const struct r2_win_storage_spec_v1 *raw_spec)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    uint32_t i;
    if (!r2_own_enter_v1()) {
        InterlockedExchange(&r2_storage_v1.acquire_race, 1);
        InterlockedExchange(&r2_own_stop_v1, 1);
        return R2_STORAGE_BUSY;
    }
    r2_storage_refresh_v1();
    if (r->acquisition_consumed || r->finish_consumed) {
        r2_storage_bad_v1(R2_STORAGE_OP_STATE, R2_STORAGE_REASON_STATE, NULL, 0);
        return r2_storage_leave_v1();
    }
    r->acquisition_consumed = 1;
    r2_storage_v1.original_creator = r2_own_v1.creator;
    r->creator_pid = o->creator_pid; r->creator_tid = o->creator_tid;
    r->creator_creation_100ns = o->creator_creation_100ns.value;
    r->intent_serial = o->intent_serial; r->lease_epoch_qpc = o->lease_epoch_qpc;
    r->qpc_frequency = o->qpc_frequency; r->stop_deadline_qpc = o->stop_deadline_qpc;
    r->cleanup_deadline_qpc = o->cleanup_deadline_qpc;
    if (!o->attempt_consumed || !r2_own_v1.deadline_bound || !r2_own_v1.creator ||
        o->creator_creation_100ns.state != R2_WIN_JOB_FIELD_VALID ||
        o->lifecycle != R2_OWN_INTENT_HELD || o->birth_attempted || o->finish_started ||
        r2_own_stopped_v1() || o->lease_epoch_qpc <= 0 || o->qpc_frequency <= 0 ||
        o->stop_deadline_qpc <= o->lease_epoch_qpc ||
        o->cleanup_deadline_qpc <= o->stop_deadline_qpc) {
        r2_storage_bad_v1(R2_STORAGE_OP_STATE, R2_STORAGE_REASON_STATE, NULL, 0);
        return r2_storage_leave_v1();
    }
    if (!r2_storage_copy_intent_v1(raw_spec)) {
        r2_storage_bad_v1(R2_STORAGE_OP_ARGUMENT, R2_STORAGE_REASON_FORMAT, NULL, 0);
        r2_storage_leave_v1(); return R2_STORAGE_BAD_ARGUMENT;
    }
    if (!r2_storage_open_v1(r2_storage_v1.volume, 0, 0) || !r2_storage_extents_v1())
        return r2_storage_leave_v1();
    for (i = 0; i < r->disk_count; ++i)
        if (!r2_storage_disk_v1(i)) return r2_storage_leave_v1();
    if (!r->fault_count && !r2_own_stopped_v1()) r->acquisition_complete = 1;
    return r2_storage_leave_v1();
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_storage_finish_once_v1(void)
{
    struct r2_win_storage_report_v1 *r = &r2_storage_report_v1;
    uint32_t slot;
    InterlockedExchange(&r2_own_stop_v1, 1);
    if (!r2_own_enter_v1()) {
        InterlockedExchange(&r2_storage_v1.finish_race, 1);
        return R2_STORAGE_BUSY;
    }
    r2_storage_refresh_v1();
    if (r->finish_consumed) return r2_storage_leave_v1();
    r->finish_consumed = 1;
    if (!r->acquisition_consumed) {
        r2_storage_bad_v1(R2_STORAGE_OP_FINISH, R2_STORAGE_REASON_STATE, NULL, 0);
        return r2_storage_leave_v1();
    }
    /* Known original handles only, disks in reverse order, then volume. */
    for (slot = 1 + R2_WIN_STORAGE_DISK_CAP; slot-- > 0;) {
        uint32_t disk = slot ? slot - 1 : UINT32_MAX;
        struct r2_win_storage_call_v1 *c;
        BOOL result;
        DWORD error = 0;
        int boundary;
        if (!r2_storage_v1.usable[slot]) continue;
        c = r2_storage_call_v1(R2_STORAGE_OP_CLOSE, disk, 0, 1);
        if (!c) { r2_storage_stop_v1(R2_OWN_RESIDUAL_CLOSE); break; }
        /* Preserve numeric original privately, consume usability BEFORE close. */
        r2_storage_v1.usable[slot] = 0;
        if (slot) r->disks[disk].close_consumed = 1; else r->volume_close_consumed = 1;
        ++r->close_consumed_count;
        r2_storage_enter_native_v1(c);
        result = CloseHandle(r2_storage_v1.originals[slot]);
        if (!result) error = GetLastError();
        c->raw_bool = (uint32_t)result; c->bool_observed = 1;
        if (!result) {
            c->win32_error = error; c->win32_error_valid = 1;
            r2_storage_fault_v1(R2_STORAGE_OP_CLOSE, R2_STORAGE_FAULT_WIN32,
                0, error, c->ordinal, disk);
        } else {
            if (slot) r->disks[disk].close_succeeded = 1; else r->volume_close_succeeded = 1;
            ++r->close_succeeded_count;
        }
        boundary = r2_storage_after_v1(c, 1);
        if (!boundary) { r2_storage_stop_v1(R2_OWN_RESIDUAL_CLOSE); break; }
    }
    if (r->close_succeeded_count != r->adopted_count || r->ambiguous_ownership)
        r2_storage_stop_v1(R2_OWN_RESIDUAL_CLOSE);
    return r2_storage_leave_v1();
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_storage_copy_report_v1(
    struct r2_win_storage_report_v1 *out, size_t out_size)
{
    if (out_size != sizeof(*out) ||
        !r2_own_range_v1(out, out_size, _Alignof(struct r2_win_storage_report_v1)) ||
        !r2_storage_disjoint_v1(out, out_size)) return R2_STORAGE_BAD_ARGUMENT;
    if (!r2_own_enter_v1()) return R2_STORAGE_BUSY;
    r2_storage_refresh_v1();
    memcpy(out, &r2_storage_report_v1, sizeof(*out));
    InterlockedExchange(&r2_own_guard_v1, 0);
    return R2_STORAGE_COPY_OK;
}
#endif
#endif

/* C00 original GPT association. Primary references: winioctl partition/layout
 * IOCTLs and structures, ioapiset/DeviceIoControl; actual public SDK layouts,
 * never the extra PartitionOrdinal shown in current Learn web syntax.
 */
#if defined(R2_TARGET_WINDOWS_SEED) && defined(R2_ENABLE_WIN_STORAGE_IDENTITY_RAW_V1)
#ifndef R2_WIN_STORAGE_IDENTITY_RAW_V1_BODY
#define R2_WIN_STORAGE_IDENTITY_RAW_V1_BODY
_Static_assert(sizeof(GUID) == 16 && sizeof(WCHAR) == 2 &&
    sizeof(PARTITION_INFORMATION_EX) == 144 &&
    offsetof(PARTITION_INFORMATION_EX, StartingOffset) == 8 &&
    offsetof(PARTITION_INFORMATION_EX, PartitionLength) == 16 &&
    offsetof(PARTITION_INFORMATION_EX, PartitionNumber) == 24 &&
    offsetof(PARTITION_INFORMATION_EX, Gpt) == 32 &&
    sizeof(PARTITION_INFORMATION_GPT) == 112 &&
    sizeof(DRIVE_LAYOUT_INFORMATION_GPT) == 40 &&
    offsetof(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry) == 48 &&
    48 + R2_WIN_STORAGE_IDENTITY_PARTITION_CAP * 144 ==
        R2_WIN_STORAGE_IDENTITY_LAYOUT_BYTES,
    "identity requires actual naturally aligned Win64 SDK layouts");
_Static_assert(sizeof(struct r2_win_storage_identity_report_v1) ==
    R2_WIN_STORAGE_IDENTITY_REPORT_BYTES &&
    R2_WIN_STORAGE_CALL_CAP + R2_WIN_STORAGE_IDENTITY_CALL_CAP == 54,
    "identity report ABI and combined storage lifetime bound");
struct r2_storage_identity_private_v1 {
    HANDLE original_creator;
    volatile LONG acquire_race;
    uint32_t race_recorded;
};
static struct r2_storage_identity_private_v1 r2_storage_identity_v1;
static struct r2_win_storage_identity_report_v1 r2_storage_identity_report_v1 = {
    .abi = R2_WIN_STORAGE_IDENTITY_RAW_ABI,
    .size = sizeof(struct r2_win_storage_identity_report_v1),
    .remaining_unproven = R2_WIN_STORAGE_UNPROVEN_ALL
};
_Static_assert(sizeof(r2_storage_identity_v1) + sizeof(r2_storage_identity_report_v1)
    <= 32768, "identity fixed private state and report bound");
_Static_assert(sizeof(r2_storage_v1) + sizeof(r2_storage_report_v1) +
    sizeof(r2_storage_identity_v1) + sizeof(r2_storage_identity_report_v1) <= 106496,
    "combined original storage and identity fixed memory bound");

static void r2_storage_identity_fault_v1(uint32_t op, uint32_t kind,
    uint32_t reason, DWORD error, const struct r2_win_storage_call_v1 *c)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    struct r2_win_storage_fault_v1 f = {
        op, kind, reason, c ? c->ordinal : 0,
        c ? c->disk_index : UINT32_MAX, (uint32_t)error,
        kind == R2_STORAGE_FAULT_WIN32, 0
    };
    r2_storage_stop_v1(0); r->stop_new = 1;
    if (!r->fault_count) r->primary = f;
    else if (r->fault_count == 1) r->secondary = f;
    if (r->fault_count < R2_WIN_STORAGE_FAULT_CAP) r->faults[r->fault_count] = f;
    else if (r->omitted_fault_count != UINT32_MAX) ++r->omitted_fault_count;
    if (r->fault_count != UINT32_MAX) ++r->fault_count;
}
static int r2_storage_identity_bad_v1(uint32_t op, uint32_t reason,
    const struct r2_win_storage_call_v1 *c)
{
    r2_storage_identity_fault_v1(op, R2_STORAGE_FAULT_INVARIANT, reason, 0, c);
    return 0;
}
static void r2_storage_identity_refresh_v1(void)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    struct r2_win_storage_report_v1 *s = &r2_storage_report_v1;
    r2_storage_refresh_v1();
    if (InterlockedCompareExchange(&r2_storage_identity_v1.acquire_race, 0, 0) &&
        !r2_storage_identity_v1.race_recorded) {
        r2_storage_identity_v1.race_recorded = 1; r->acquisition_consumed = 1;
        r2_storage_identity_bad_v1(R2_STORAGE_IDENTITY_OP_STATE,
            R2_STORAGE_REASON_RACE, NULL);
    }
    r->stop_new = (uint32_t)r2_own_stopped_v1();
    r->owner_lifecycle = r2_own_report_v1.lifecycle;
    r->storage_finish_observed = s->finish_consumed;
    r->pending_liability = r->in_flight || r->fault_count ||
        (r->acquisition_consumed && s->pending_liability);
    if (r->acquisition_consumed && s->finish_consumed && r->pending_liability)
        r->status = R2_STORAGE_IDENTITY_RETAINED;
    else if (r->acquisition_complete && s->acquisition_complete &&
        s->finish_consumed && s->all_known_once_closed && !s->fault_count &&
        !r->pending_liability)
        r->status = R2_STORAGE_IDENTITY_RAW_COMPLETE;
    else if (r->fault_count) r->status = R2_STORAGE_IDENTITY_RAW_PARTIAL;
    else r->status = r->acquisition_consumed ?
        R2_STORAGE_IDENTITY_PENDING : R2_STORAGE_IDENTITY_UNUSED;
}
static uint32_t r2_storage_identity_leave_v1(void)
{
    uint32_t status;
    r2_storage_identity_refresh_v1(); status = r2_storage_identity_report_v1.status;
    InterlockedExchange(&r2_own_guard_v1, 0);
    return status;
}
static int r2_storage_identity_disjoint_v1(const void *p, size_t size)
{
    return r2_storage_disjoint_v1(p, size) &&
        r2_mm_disjoint_v1(p, size, &r2_storage_identity_v1, sizeof(r2_storage_identity_v1)) &&
        r2_mm_disjoint_v1(p, size, &r2_storage_identity_report_v1,
            sizeof(r2_storage_identity_report_v1));
}
static int r2_storage_identity_context_v1(struct r2_win_storage_call_v1 *c)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    struct r2_win_storage_report_v1 *s = &r2_storage_report_v1;
    if (!r2_own_v1.creator || r2_own_v1.creator != r2_storage_identity_v1.original_creator ||
        r2_own_v1.creator != r2_storage_v1.original_creator || !r2_own_v1.deadline_bound ||
        !o->attempt_consumed || o->finish_started || o->birth_attempted ||
        o->lifecycle != R2_OWN_INTENT_HELD ||
        o->creator_creation_100ns.state != R2_WIN_JOB_FIELD_VALID ||
        !s->acquisition_complete || s->finish_consumed || s->fault_count ||
        s->ambiguous_ownership || !r2_storage_v1.usable[0] || !r2_storage_v1.usable[1] ||
        o->creator_pid != r->creator_pid || o->creator_tid != r->creator_tid ||
        o->creator_creation_100ns.value != r->creator_creation_100ns ||
        o->intent_serial != r->intent_serial || o->lease_epoch_qpc != r->lease_epoch_qpc ||
        o->qpc_frequency != r->qpc_frequency || o->stop_deadline_qpc != r->stop_deadline_qpc ||
        o->cleanup_deadline_qpc != r->cleanup_deadline_qpc ||
        s->creator_pid != r->creator_pid || s->creator_tid != r->creator_tid ||
        s->creator_creation_100ns != r->creator_creation_100ns ||
        s->intent_serial != r->intent_serial || s->lease_epoch_qpc != r->lease_epoch_qpc ||
        s->qpc_frequency != r->qpc_frequency || s->stop_deadline_qpc != r->stop_deadline_qpc ||
        s->cleanup_deadline_qpc != r->cleanup_deadline_qpc) {
        r2_storage_identity_fault_v1(c->operation, R2_STORAGE_FAULT_OWNER,
            R2_STORAGE_REASON_CONTEXT, 0, c); return 0;
    }
    if (r->identity_check_count >= 2 * R2_WIN_STORAGE_IDENTITY_CALL_CAP)
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_COUNTER, c);
    ++r->identity_check_count;
    if (GetCurrentProcessId() != r->creator_pid || GetCurrentThreadId() != r->creator_tid ||
        !r2_own_creator_identity_v1()) {
        r2_storage_identity_fault_v1(c->operation, R2_STORAGE_FAULT_OWNER,
            R2_STORAGE_REASON_IDENTITY, 0, c); return 0;
    }
    return 1;
}
static int r2_storage_identity_clock_v1(struct r2_win_storage_call_v1 *c, uint32_t endpoint)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    struct r2_win_storage_clock_v1 *clock = &c->clocks[endpoint];
    LARGE_INTEGER now = {0};
    BOOL result;
    DWORD error;
    if (r->qpc_work_count >= 4 * R2_WIN_STORAGE_IDENTITY_CALL_CAP)
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_COUNTER, c);
    ++r->qpc_work_count; clock->attempted = 1;
    result = QueryPerformanceCounter(&now);
    if (!result) {
        error = GetLastError();
        clock->raw_result = (uint32_t)result;
        clock->win32_error = error; clock->win32_error_valid = 1;
        o->clock_valid = 0; o->residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        r2_storage_identity_fault_v1(c->operation, R2_STORAGE_FAULT_WIN32,
            R2_STORAGE_REASON_CLOCK, error, c); return 0;
    }
    clock->raw_result = (uint32_t)result; clock->raw_qpc = now.QuadPart;
    if (now.QuadPart <= 0 || now.QuadPart < o->last_qpc || !o->clock_valid ||
        (o->residual_bits & R2_OWN_RESIDUAL_CLOCK)) {
        o->clock_valid = 0; o->residual_bits |= R2_OWN_RESIDUAL_CLOCK;
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_CLOCK, c);
    }
    o->last_qpc = now.QuadPart;
    if (r->stop_deadline_qpc <= 0 || now.QuadPart >= r->stop_deadline_qpc) {
        o->residual_bits |= R2_OWN_RESIDUAL_DEADLINE;
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_DEADLINE, c);
    }
    return 1;
}
static int r2_storage_identity_ioctl_v1(uint32_t slot, uint32_t op,
    DWORD control, void *output, DWORD capacity, struct r2_win_storage_call_v1 **observed)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    struct r2_win_storage_call_v1 *c;
    DWORD returned = 0, error = 0;
    BOOL result;
    int before_identity, before_clock, after_first, after_identity, after_last;
    *observed = NULL;
    if (r->call_count >= R2_WIN_STORAGE_IDENTITY_CALL_CAP ||
        r->native_work_count >= R2_WIN_STORAGE_IDENTITY_CALL_CAP)
        return r2_storage_identity_bad_v1(op, R2_STORAGE_REASON_COUNTER, NULL);
    c = &r->calls[r->call_count++]; *observed = c;
    c->ordinal = r->call_count; c->operation = op;
    c->disk_index = slot ? 0 : UINT32_MAX; c->capacity = capacity;
    if (r2_own_stopped_v1())
        return r2_storage_identity_bad_v1(op, R2_STORAGE_REASON_STATE, c);
    if (!r2_storage_identity_clock_v1(c, 0)) return 0;
    before_identity = r2_storage_identity_context_v1(c);
    before_clock = r2_storage_identity_clock_v1(c, 1);
    if (!before_identity || !before_clock) return 0;
    if (r2_own_stopped_v1())
        return r2_storage_identity_bad_v1(op, R2_STORAGE_REASON_RACE, c);
    c->attempted = 1; ++r->native_work_count;
    r->in_flight_ordinal = c->ordinal; r->in_flight = 1; r->pending_liability = 1;
    result = DeviceIoControl(r2_storage_v1.originals[slot], control, NULL, 0,
        output, capacity, &returned, NULL);
    if (!result) error = GetLastError();
    c->raw_bool = (uint32_t)result; c->bool_observed = 1;
    c->raw_bytes_returned = returned;
    c->opaque_bytes = result && returned <= capacity ? returned : capacity;
    if (!result) {
        c->win32_error = error; c->win32_error_valid = 1;
        r2_storage_identity_fault_v1(op, R2_STORAGE_FAULT_WIN32, 0, error, c);
    }
    r->in_flight = 0;
    after_first = r2_storage_identity_clock_v1(c, 2);
    after_identity = r2_storage_identity_context_v1(c);
    after_last = r2_storage_identity_clock_v1(c, 3);
    c->boundary_valid = after_first && after_identity && after_last;
    if (r2_own_stopped_v1()) {
        if (!r->fault_count)
            r2_storage_identity_bad_v1(op, R2_STORAGE_REASON_RACE, c);
        return 0;
    }
    if (!c->boundary_valid || !result) return 0;
    if (returned > capacity)
        return r2_storage_identity_bad_v1(op, R2_STORAGE_REASON_BOUND, c);
    return 1;
}
static int r2_storage_identity_zero_guid_v1(const GUID *guid)
{
    const unsigned char *p = (const unsigned char *)guid;
    size_t i;
    for (i = 0; i < sizeof(*guid); ++i) if (p[i]) return 0;
    return 1;
}
static int r2_storage_identity_range_v1(int64_t start, int64_t length,
    int64_t disk_length, uint32_t sector)
{
    return sector && start >= 0 && length > 0 && disk_length > 0 &&
        start <= disk_length && length <= disk_length - start &&
        (uint64_t)start % sector == 0 && (uint64_t)length % sector == 0;
}
static int r2_storage_identity_partition_v1(void)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    struct r2_win_storage_disk_v1 *d = &r2_storage_report_v1.disks[0];
    struct r2_win_storage_call_v1 *c = NULL;
    PARTITION_INFORMATION_EX partition;
    if (!r2_storage_identity_ioctl_v1(0, R2_STORAGE_IDENTITY_OP_PARTITION,
        IOCTL_DISK_GET_PARTITION_INFO_EX, r->partition_opaque.bytes,
        (DWORD)sizeof(partition), &c)) return 0;
    if (c->raw_bytes_returned != sizeof(partition))
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_BOUND, c);
    memcpy(&partition, r->partition_opaque.bytes, sizeof(partition));
    r->partition_style = (uint32_t)partition.PartitionStyle;
    if (partition.PartitionStyle != PARTITION_STYLE_GPT)
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_UNSUPPORTED, c);
    /* The union is inspected only AFTER its actual style is known. */
    if (r2_storage_identity_zero_guid_v1(&partition.Gpt.PartitionType) ||
        r2_storage_identity_zero_guid_v1(&partition.Gpt.PartitionId) ||
        !partition.PartitionNumber ||
        !r2_storage_identity_range_v1(partition.StartingOffset.QuadPart,
            partition.PartitionLength.QuadPart, d->disk_length, d->bytes_per_logical_sector))
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_RANGE, c);
    r->partition_number = partition.PartitionNumber;
    r->partition_start = partition.StartingOffset.QuadPart;
    r->partition_length = partition.PartitionLength.QuadPart;
    memcpy(r->partition_type, &partition.Gpt.PartitionType, sizeof(GUID));
    memcpy(r->partition_id, &partition.Gpt.PartitionId, sizeof(GUID));
    r->partition_attributes = partition.Gpt.Attributes;
    memcpy(r->partition_name, partition.Gpt.Name, sizeof(r->partition_name));
    r->volume_source_ordinal = c->ordinal;
    c->output_valid = 1; r->partition_valid = 1;
    return 1;
}
/* Complete bounded spans were checked before any entry read. SDK locals avoid
 * alignment/effective-type assumptions about the opaque byte arrays. */
static void r2_storage_identity_entry_v1(uint32_t index, PARTITION_INFORMATION_EX *out)
{
    memcpy(out, r2_storage_identity_report_v1.layout_opaque.bytes +
        offsetof(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry) + index * sizeof(*out), sizeof(*out));
}
static int r2_storage_identity_layout_v1(void)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    struct r2_win_storage_disk_v1 *d = &r2_storage_report_v1.disks[0];
    struct r2_win_storage_call_v1 *c = NULL;
    DRIVE_LAYOUT_INFORMATION_EX header;
    PARTITION_INFORMATION_EX entry, previous;
    size_t offset = offsetof(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry);
    uint32_t count, i, j, used = 0;
    int64_t usable_start, usable_length;
    if (!r2_storage_identity_ioctl_v1(1, R2_STORAGE_IDENTITY_OP_LAYOUT,
        IOCTL_DISK_GET_DRIVE_LAYOUT_EX, r->layout_opaque.bytes,
        R2_WIN_STORAGE_IDENTITY_LAYOUT_BYTES, &c)) return 0;
    if (c->raw_bytes_returned < offset)
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_BOUND, c);
    memset(&header, 0, sizeof(header)); memcpy(&header, r->layout_opaque.bytes, offset);
    r->layout_partition_style = header.PartitionStyle;
    r->layout_partition_count = header.PartitionCount;
    count = header.PartitionCount;
    if (count > R2_WIN_STORAGE_IDENTITY_PARTITION_CAP ||
        count > (c->raw_bytes_returned - offset) / sizeof(entry) ||
        count > (c->capacity - offset) / sizeof(entry))
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_BOUND, c);
    if (header.PartitionStyle != PARTITION_STYLE_GPT)
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_UNSUPPORTED, c);
    /* Only the GPT arm is defined by the supported actual discriminator. */
    usable_start = header.Gpt.StartingUsableOffset.QuadPart;
    usable_length = header.Gpt.UsableLength.QuadPart;
    if (r2_storage_identity_zero_guid_v1(&header.Gpt.DiskId) ||
        !header.Gpt.MaxPartitionCount || count > header.Gpt.MaxPartitionCount ||
        !r2_storage_identity_range_v1(usable_start, usable_length,
            d->disk_length, d->bytes_per_logical_sector))
        return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_RANGE, c);
    memcpy(r->disk_id, &header.Gpt.DiskId, sizeof(GUID));
    r->gpt_usable_offset = usable_start; r->gpt_usable_length = usable_length;
    r->max_partition_count = header.Gpt.MaxPartitionCount; r->layout_header_valid = 1;
    for (i = 0; i < count; ++i) {
        r2_storage_identity_entry_v1(i, &entry);
        if (entry.PartitionStyle != PARTITION_STYLE_GPT)
            return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_UNSUPPORTED, c);
        if (r2_storage_identity_zero_guid_v1(&entry.Gpt.PartitionType)) {
            ++r->layout_validated_count; continue; /* unused/raw, no ID/name interpretation */
        }
        if (r2_storage_identity_zero_guid_v1(&entry.Gpt.PartitionId) || !entry.PartitionNumber ||
            !r2_storage_identity_range_v1(entry.StartingOffset.QuadPart,
                entry.PartitionLength.QuadPart, d->disk_length, d->bytes_per_logical_sector) ||
            entry.StartingOffset.QuadPart < usable_start ||
            entry.StartingOffset.QuadPart - usable_start > usable_length ||
            entry.PartitionLength.QuadPart >
                usable_length - (entry.StartingOffset.QuadPart - usable_start))
            return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_RANGE, c);
        for (j = 0; j < i; ++j) {
            r2_storage_identity_entry_v1(j, &previous);
            /* Every earlier discriminator/range was validated on its iteration. */
            if (previous.PartitionStyle != PARTITION_STYLE_GPT)
                return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_UNSUPPORTED, c);
            if (r2_storage_identity_zero_guid_v1(&previous.Gpt.PartitionType)) continue;
            if (entry.PartitionNumber == previous.PartitionNumber ||
                !memcmp(&entry.Gpt.PartitionId, &previous.Gpt.PartitionId, sizeof(GUID)) ||
                (entry.StartingOffset.QuadPart < previous.StartingOffset.QuadPart +
                    previous.PartitionLength.QuadPart &&
                 previous.StartingOffset.QuadPart < entry.StartingOffset.QuadPart +
                    entry.PartitionLength.QuadPart))
                return r2_storage_identity_bad_v1(c->operation, R2_STORAGE_REASON_ASSOCIATION, c);
        }
        ++used; ++r->layout_validated_count;
    }
    r->used_entry_count = used;
    r->layout_tail_offset = (uint32_t)(offset + count * sizeof(entry));
    r->layout_tail_bytes = c->raw_bytes_returned - r->layout_tail_offset;
    r->layout_source_ordinal = c->ordinal;
    c->output_valid = 1; r->layout_valid = 1;
    return 1;
}
static int r2_storage_identity_associate_v1(void)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    const struct r2_win_storage_extent_v1 *extent = &r2_storage_report_v1.extents[0];
    /* Documented PARTITION_BASIC_DATA_GUID, not an observed target identity.
     * winioctl/PARTITION_INFORMATION_GPT documents the retained OEM exception;
     * this type gate does not establish that the disk itself is basic.
     */
    const GUID basic_data_type = {
        0xebd0a0a2u, 0xb9e5u, 0x4433u, {0x87u, 0xc0u, 0x68u, 0xb6u, 0xb7u, 0x26u, 0x99u, 0xc7u}
    };
    PARTITION_INFORMATION_EX entry;
    uint32_t i, matches = 0, matched = 0;
    if (!r->partition_valid || !r->layout_valid || extent->disk_index != 0 ||
        extent->disk_number != r2_storage_report_v1.disks[0].extent_disk_number ||
        !extent->range_valid || !extent->sector_mapping_valid ||
        extent->starting_offset != r->partition_start || extent->extent_length != r->partition_length)
        return r2_storage_identity_bad_v1(R2_STORAGE_IDENTITY_OP_ASSOCIATION,
            R2_STORAGE_REASON_ASSOCIATION, NULL);
    for (i = 0; i < r->layout_partition_count; ++i) {
        r2_storage_identity_entry_v1(i, &entry);
        if (entry.PartitionStyle != PARTITION_STYLE_GPT)
            return r2_storage_identity_bad_v1(R2_STORAGE_IDENTITY_OP_ASSOCIATION,
                R2_STORAGE_REASON_UNSUPPORTED, NULL);
        if (r2_storage_identity_zero_guid_v1(&entry.Gpt.PartitionType)) continue;
        if (entry.PartitionNumber == r->partition_number &&
            entry.StartingOffset.QuadPart == r->partition_start &&
            entry.PartitionLength.QuadPart == r->partition_length &&
            !memcmp(&entry.Gpt.PartitionType, r->partition_type, sizeof(GUID)) &&
            !memcmp(&entry.Gpt.PartitionId, r->partition_id, sizeof(GUID)) &&
            entry.Gpt.Attributes == r->partition_attributes &&
            !memcmp(entry.Gpt.Name, r->partition_name, sizeof(r->partition_name))) {
            matched = i; ++matches;
        }
    }
    if (matches != 1)
        return r2_storage_identity_bad_v1(R2_STORAGE_IDENTITY_OP_ASSOCIATION,
            R2_STORAGE_REASON_ASSOCIATION, NULL);
    /* Other layout types remain raw structural facts. Only the exact matched
     * target must be BasicData before any supported association is published.
     */
    if (memcmp(r->partition_type, &basic_data_type, sizeof(basic_data_type)))
        return r2_storage_identity_bad_v1(R2_STORAGE_IDENTITY_OP_ASSOCIATION,
            R2_STORAGE_REASON_UNSUPPORTED, NULL);
    r->matched_layout_index = matched; r->association_valid = 1;
    r->supported_gpt_observed = 1;
    return 1;
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_storage_identity_acquire_once_v1(void)
{
    struct r2_win_storage_identity_report_v1 *r = &r2_storage_identity_report_v1;
    struct r2_win_storage_report_v1 *s = &r2_storage_report_v1;
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    if (!r2_own_enter_v1()) {
        InterlockedExchange(&r2_storage_identity_v1.acquire_race, 1);
        InterlockedExchange(&r2_own_stop_v1, 1);
        return R2_STORAGE_IDENTITY_BUSY;
    }
    r2_storage_identity_refresh_v1();
    if (r->acquisition_consumed) {
        r2_storage_identity_bad_v1(R2_STORAGE_IDENTITY_OP_STATE, R2_STORAGE_REASON_STATE, NULL);
        return r2_storage_identity_leave_v1();
    }
    r->acquisition_consumed = 1;
    r2_storage_identity_v1.original_creator = r2_own_v1.creator;
    r->creator_pid = o->creator_pid; r->creator_tid = o->creator_tid;
    r->creator_creation_100ns = o->creator_creation_100ns.value;
    r->intent_serial = o->intent_serial; r->lease_epoch_qpc = o->lease_epoch_qpc;
    r->qpc_frequency = o->qpc_frequency; r->stop_deadline_qpc = o->stop_deadline_qpc;
    r->cleanup_deadline_qpc = o->cleanup_deadline_qpc;
    if (!s->acquisition_complete || s->finish_consumed || s->fault_count || s->ambiguous_ownership ||
        !r2_storage_v1.usable[0] || !r2_storage_v1.usable[1] ||
        !r2_own_v1.creator || !r2_own_v1.deadline_bound || !o->attempt_consumed ||
        o->creator_creation_100ns.state != R2_WIN_JOB_FIELD_VALID ||
        o->lifecycle != R2_OWN_INTENT_HELD || o->birth_attempted || o->finish_started ||
        r2_own_stopped_v1() || r->lease_epoch_qpc <= 0 || r->qpc_frequency <= 0 ||
        r->stop_deadline_qpc <= r->lease_epoch_qpc ||
        r->cleanup_deadline_qpc <= r->stop_deadline_qpc) {
        r2_storage_identity_bad_v1(R2_STORAGE_IDENTITY_OP_STATE, R2_STORAGE_REASON_STATE, NULL);
        return r2_storage_identity_leave_v1();
    }
    if (!s->extent_count_valid || s->extent_count != 1 || s->disk_count != 1 ||
        !s->disks[0].adopted || !s->disks[0].device_number_valid ||
        !s->disks[0].length_valid || !s->disks[0].alignment_valid) {
        r2_storage_identity_bad_v1(R2_STORAGE_IDENTITY_OP_STATE,
            R2_STORAGE_REASON_UNSUPPORTED, NULL);
        return r2_storage_identity_leave_v1();
    }
    r->extent_disk_number = s->extents[0].disk_number;
    r->extent_sector_mapping_valid = s->extents[0].sector_mapping_valid;
    if (!r2_storage_identity_partition_v1() || !r2_storage_identity_layout_v1() ||
        !r2_storage_identity_associate_v1()) return r2_storage_identity_leave_v1();
    if (!r->fault_count && !r2_own_stopped_v1()) r->acquisition_complete = 1;
    return r2_storage_identity_leave_v1();
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_storage_identity_copy_report_v1(
    struct r2_win_storage_identity_report_v1 *out, size_t out_size)
{
    if (out_size != sizeof(*out) ||
        !r2_own_range_v1(out, out_size, _Alignof(struct r2_win_storage_identity_report_v1)) ||
        !r2_storage_identity_disjoint_v1(out, out_size)) return R2_STORAGE_IDENTITY_BAD_ARGUMENT;
    if (!r2_own_enter_v1()) return R2_STORAGE_IDENTITY_BUSY;
    r2_storage_identity_refresh_v1();
    memcpy(out, &r2_storage_identity_report_v1, sizeof(*out));
    InterlockedExchange(&r2_own_guard_v1, 0);
    return R2_STORAGE_IDENTITY_COPY_OK;
}
#endif
#endif
