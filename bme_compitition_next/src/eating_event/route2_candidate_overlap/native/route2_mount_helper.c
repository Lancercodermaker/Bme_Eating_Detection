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
