/* C02 additive SOURCE_ONLY / UNCOMPILED raw observation companion.
 * Build this translation unit INSTEAD OF route2_mount_helper.c, never both.
 * The textual inclusion preserves reviewed source bytes and shares its ONE
 * original static owner and guard. A separately linked/copied owner is wrong.
 * Existing .def/build targets/17-export images do not contain these exports.
 * No loader, startup owner, deployment or runtime permission is supplied here.
 * Future compilation requires explicit R2_TARGET_WINDOWS_SEED, Win10 x64 C11
 * SDK contracts and kernel32; no psapi.dll load or compatibility fallback.
 * Public declarations below are native layout, not authenticated transport.
 *
 * Microsoft contracts retrieved through Context7 then Microsoft Learn:
 * jobapi2/QueryInformationJobObject; winnt/JOBOBJECT_BASIC_AND_IO_ACCOUNTING_
 * INFORMATION and JOBOBJECT_EXTENDED_LIMIT_INFORMATION; psapi/
 * GetProcessMemoryInfo and PROCESS_MEMORY_COUNTERS_EX; processthreadsapi/
 * GetProcessTimes and GetProcessId. Public documentation is not local support.
 */
#if !defined(R2_TARGET_WINDOWS_SEED) || defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_MOUNT_LIBRARY)
#error "Observation companion requires only the explicit Windows seed target"
#endif
#include "route2_mount_helper.c"
#if defined(PSAPI_VERSION) && PSAPI_VERSION < 2
#error "Observation requires kernel32 K32GetProcessMemoryInfo, PSAPI_VERSION >= 2"
#endif
#ifndef PSAPI_VERSION
#define PSAPI_VERSION 2
#endif
#include <psapi.h>

#define R2_OBS_ABI 1u
#define R2_OBS_ATTEMPT_CAPACITY 256u
#define R2_OBS_FAULT_CAPACITY 32u
enum r2_obs_status_v1 {
    R2_OBS_OK = 1, R2_OBS_PARTIAL = 2, R2_OBS_FAILED = 3,
    R2_OBS_BUSY = 4, R2_OBS_BAD_ARGUMENT = 5, R2_OBS_BAD_STATE = 6,
    R2_OBS_EXHAUSTED = 7
};
enum r2_obs_process_disposition_v1 {
    R2_OBS_NOT_ACQUIRED = 0, R2_OBS_LIVE_BOTH_POLLS = 1,
    R2_OBS_EXITED_BEFORE = 2, R2_OBS_EXIT_RACED = 3, R2_OBS_PROCESS_FAILED = 4
};
enum r2_obs_operation_v1 {
    R2_OBS_CONTEXT = 1, R2_OBS_CLOCK, R2_OBS_JOB_IO, R2_OBS_JOB_LIMITS,
    R2_OBS_JOB_CPU, R2_OBS_CREATOR_WAIT_BEFORE, R2_OBS_CREATOR_PID_BEFORE,
    R2_OBS_CREATOR_TIMES_BEFORE, R2_OBS_CREATOR_MEMORY,
    R2_OBS_CREATOR_PID_AFTER, R2_OBS_CREATOR_TIMES_AFTER, R2_OBS_CREATOR_WAIT_AFTER,
    R2_OBS_CHILD_WAIT_BEFORE, R2_OBS_CHILD_PID_BEFORE, R2_OBS_CHILD_TIMES_BEFORE,
    R2_OBS_CHILD_MEMBERSHIP, R2_OBS_CHILD_MEMORY,
    R2_OBS_CHILD_PID_AFTER, R2_OBS_CHILD_TIMES_AFTER, R2_OBS_CHILD_WAIT_AFTER,
    R2_OBS_RESERVATION
};
enum r2_obs_fault_kind_v1 { R2_OBS_WIN32 = 1, R2_OBS_INVARIANT = 2, R2_OBS_NO_EXTENDED_ERROR = 3 };
enum r2_obs_invariant_v1 {
    R2_OBS_IDENTITY_CHANGED = 1, R2_OBS_LENGTH_CHANGED, R2_OBS_LIMIT_CHANGED,
    R2_OBS_NEGATIVE_TIME, R2_OBS_COUNT_CHANGED, R2_OBS_CLOCK_REGRESSED,
    R2_OBS_DEADLINE, R2_OBS_BAD_WAIT, R2_OBS_NO_RESERVATION
};
struct r2_obs_process_v1 {
    uint32_t acquired, disposition, identity_valid, live_memory_usable;
    struct r2_win_job_raw_u32_v1 wait_before, wait_after, pid_before, pid_after;
    struct r2_win_job_raw_u64_v1 creation_before_100ns, creation_after_100ns;
    struct r2_win_job_raw_u64_v1 kernel_100ns, user_100ns, exit_100ns;
    uint32_t memory_state, reserved;
    struct r2_win_job_raw_u32_v1 memory_cb, page_fault_count;
    struct r2_win_job_raw_u64_v1 peak_working_set_bytes, working_set_bytes;
    struct r2_win_job_raw_u64_v1 peak_paged_pool_bytes, paged_pool_bytes;
    struct r2_win_job_raw_u64_v1 peak_nonpaged_pool_bytes, nonpaged_pool_bytes;
    struct r2_win_job_raw_u64_v1 pagefile_commit_bytes, peak_pagefile_commit_bytes;
    struct r2_win_job_raw_u64_v1 private_commit_bytes;
};
struct r2_obs_snapshot_v1 {
    uint32_t sequence, owner_lifecycle, completed_within_deadline, local_fault_count;
    uint32_t job_acquired, job_io_state, job_counts_valid, reserved;
    uint64_t intent_serial;
    int64_t lease_epoch_qpc, qpc_frequency, effective_deadline_qpc;
    int64_t start_qpc, end_qpc;
    struct r2_win_job_raw_snapshot_v1 job;
    struct r2_win_job_raw_u64_v1 read_operations, write_operations, other_operations;
    struct r2_win_job_raw_u64_v1 read_transfer_bytes, write_transfer_bytes, other_transfer_bytes;
    struct r2_obs_process_v1 creator, child;
};
struct r2_obs_fault_v1 {
    uint32_t operation, kind, code, win32_error, win32_error_valid, occurrences;
};
struct r2_obs_report_v1 {
    uint32_t abi, size, status, attempts, first_frozen, latest_valid;
    uint32_t fault_count, stop_new, owner_residual_bits, reserved;
    struct r2_obs_fault_v1 primary, faults[R2_OBS_FAULT_CAPACITY];
    struct r2_obs_snapshot_v1 first, latest;
};
struct r2_obs_abi_v1 {
    uint32_t abi, size, report_size, snapshot_size, process_size, fault_size;
    uint32_t report_first_offset, report_latest_offset, pointer_size, attempt_capacity;
    uint32_t fault_capacity, reserved;
};
/* Exact native caller-owned accessible/exclusive output only. Bad output and
 * BUSY do not reserve an attempt. No HANDLE/PID/callback/deadline input exists.
 * copy may recover raw facts after a caller's foreign conversion fails; it
 * performs no new sample and cannot reset reservation/first/sticky faults.
 */
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_observation_describe_v1(struct r2_obs_abi_v1 *, size_t);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_observation_sample_step_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_observation_copy_report_v1(struct r2_obs_report_v1 *, size_t);

_Static_assert(sizeof(PROCESS_MEMORY_COUNTERS_EX) == 80 &&
    offsetof(PROCESS_MEMORY_COUNTERS_EX, PrivateUsage) == 72, "Win64 process memory ABI");
_Static_assert(sizeof(JOBOBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION) == 96 &&
    offsetof(JOBOBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION, IoInfo) == 48, "Win64 Job IO ABI");
_Static_assert(sizeof(IO_COUNTERS) == 48 && sizeof(struct r2_obs_fault_v1) == 24, "raw counter/fault ABI");
_Static_assert(sizeof(struct r2_obs_process_v1) == 296 && sizeof(struct r2_obs_snapshot_v1) == 992 &&
    sizeof(struct r2_obs_report_v1) == 2816 && sizeof(struct r2_obs_abi_v1) == 48 &&
    offsetof(struct r2_obs_report_v1, first) == 832 && offsetof(struct r2_obs_report_v1, latest) == 1824,
    "versioned observation native layout");
_Static_assert(R2_OBS_RESERVATION < R2_OBS_FAULT_CAPACITY &&
    sizeof(struct r2_obs_report_v1) <= UINT32_MAX, "bounded observation ABI");

/* All storage exists before the first sampling attempt. No heap, vectors,
 * callbacks, enumeration, PID reopen, duplication, close, launch or waits >0.
 * At most 256 sampling attempts; 32 sticky first-fault slots, no reset.
 * Queries have a fixed finite call graph; no retry of any failed API.
 */
static struct r2_obs_report_v1 r2_obs_report_v1 = {
    .abi = R2_OBS_ABI, .size = sizeof(struct r2_obs_report_v1)
};
static JOBOBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION r2_obs_io_v1;
static JOBOBJECT_EXTENDED_LIMIT_INFORMATION r2_obs_limits_v1;
static JOBOBJECT_CPU_RATE_CONTROL_INFORMATION r2_obs_cpu_v1;
static PROCESS_MEMORY_COUNTERS_EX r2_obs_memory_v1;
static int64_t r2_obs_last_qpc_v1;
static uint32_t r2_obs_step_faults_v1;

static void r2_obs_fault_v1(uint32_t op, uint32_t kind, uint32_t code, DWORD error)
{
    struct r2_obs_fault_v1 *f = &r2_obs_report_v1.faults[op];
    InterlockedExchange(&r2_own_stop_v1, 1);
    r2_own_report_v1.stop_new = 1;
    r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_SAMPLE;
    ++r2_obs_step_faults_v1; /* fixed call graph, cannot approach UINT32_MAX */
    if (!f->occurrences) {
        f->operation = op; f->kind = kind; f->code = code;
        f->win32_error = error; f->win32_error_valid = kind == R2_OBS_WIN32;
        f->occurrences = 1;
        if (!r2_obs_report_v1.fault_count) r2_obs_report_v1.primary = *f;
        ++r2_obs_report_v1.fault_count;
    } else if (f->occurrences != UINT32_MAX) ++f->occurrences;
}
static void r2_obs_api_v1(uint32_t op, DWORD error)
{
    r2_obs_fault_v1(op, error ? R2_OBS_WIN32 : R2_OBS_NO_EXTENDED_ERROR, 0, error);
}
static int r2_obs_clock_v1(int64_t deadline, int64_t *out)
{
    LARGE_INTEGER now;
    if (!QueryPerformanceCounter(&now)) {
        DWORD error = GetLastError(); r2_obs_api_v1(R2_OBS_CLOCK, error);
        r2_own_report_v1.clock_valid = 0;
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_CLOCK; return 0;
    }
    *out = now.QuadPart;
    if (now.QuadPart <= 0 || now.QuadPart < r2_own_report_v1.last_qpc ||
        now.QuadPart < r2_obs_last_qpc_v1 || !r2_own_report_v1.clock_valid) {
        r2_obs_fault_v1(R2_OBS_CLOCK, R2_OBS_INVARIANT, R2_OBS_CLOCK_REGRESSED, 0);
        r2_own_report_v1.clock_valid = 0;
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_CLOCK; return 0;
    }
    r2_obs_last_qpc_v1 = now.QuadPart;
    r2_own_report_v1.last_qpc = now.QuadPart;
    if (now.QuadPart >= deadline) {
        r2_obs_fault_v1(R2_OBS_CLOCK, R2_OBS_INVARIANT, R2_OBS_DEADLINE, 0);
        r2_own_report_v1.residual_bits |= R2_OWN_RESIDUAL_DEADLINE; return 0;
    }
    return 1;
}
static int r2_obs_ready_v1(void)
{
    struct r2_obs_snapshot_v1 *s = &r2_obs_report_v1.latest;
    if (r2_own_report_v1.residual_bits & (R2_OWN_RESIDUAL_CLOCK | R2_OWN_RESIDUAL_DEADLINE)) return 0;
    return r2_obs_clock_v1(s->effective_deadline_qpc, &s->end_qpc);
}
static int r2_obs_query_v1(JOBOBJECTINFOCLASS cls, void *out, DWORD size, uint32_t op)
{
    DWORD returned = 0;
    if (!r2_obs_ready_v1()) return 0;
    if (!QueryInformationJobObject(r2_own_v1.job, cls, out, size, &returned)) {
        DWORD error = GetLastError(); r2_obs_api_v1(op, error); return 0;
    }
    if (returned != size) {
        r2_obs_fault_v1(op, R2_OBS_INVARIANT, R2_OBS_LENGTH_CHANGED, 0); return 0;
    }
    return 1;
}
static void r2_obs_job_v1(struct r2_obs_snapshot_v1 *s)
{
    struct r2_win_job_raw_snapshot_v1 *j = &s->job;
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION *a = &r2_obs_io_v1.BasicInfo;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION *l = &r2_obs_limits_v1;
    JOBOBJECT_CPU_RATE_CONTROL_INFORMATION *c = &r2_obs_cpu_v1;
    s->job_acquired = r2_own_report_v1.job.acquired;
    if (!r2_own_v1.job || r2_own_report_v1.job.consumed) return;
    memset(&r2_obs_io_v1, 0, sizeof(r2_obs_io_v1));
    s->job_io_state = j->accounting_state = R2_WIN_JOB_FIELD_FAILED;
    if (r2_obs_query_v1(JobObjectBasicAndIoAccountingInformation, &r2_obs_io_v1, sizeof(r2_obs_io_v1), R2_OBS_JOB_IO)) {
        r2_own_u64_v1(&s->read_operations, r2_obs_io_v1.IoInfo.ReadOperationCount);
        r2_own_u64_v1(&s->write_operations, r2_obs_io_v1.IoInfo.WriteOperationCount);
        r2_own_u64_v1(&s->other_operations, r2_obs_io_v1.IoInfo.OtherOperationCount);
        r2_own_u64_v1(&s->read_transfer_bytes, r2_obs_io_v1.IoInfo.ReadTransferCount);
        r2_own_u64_v1(&s->write_transfer_bytes, r2_obs_io_v1.IoInfo.WriteTransferCount);
        r2_own_u64_v1(&s->other_transfer_bytes, r2_obs_io_v1.IoInfo.OtherTransferCount);
        s->job_io_state = R2_WIN_JOB_FIELD_VALID;
        if (a->TotalUserTime.QuadPart < 0 || a->TotalKernelTime.QuadPart < 0 ||
            a->ThisPeriodTotalUserTime.QuadPart < 0 || a->ThisPeriodTotalKernelTime.QuadPart < 0) {
            r2_obs_fault_v1(R2_OBS_JOB_IO, R2_OBS_INVARIANT, R2_OBS_NEGATIVE_TIME, 0);
        } else {
            r2_own_i64_v1(&j->total_user_100ns, a->TotalUserTime.QuadPart);
            r2_own_i64_v1(&j->total_kernel_100ns, a->TotalKernelTime.QuadPart);
            r2_own_i64_v1(&j->period_user_100ns, a->ThisPeriodTotalUserTime.QuadPart);
            r2_own_i64_v1(&j->period_kernel_100ns, a->ThisPeriodTotalKernelTime.QuadPart);
            r2_own_u32_v1(&j->page_faults, a->TotalPageFaultCount);
            r2_own_u32_v1(&j->total_processes, a->TotalProcesses);
            r2_own_u32_v1(&j->active_processes, a->ActiveProcesses);
            r2_own_u32_v1(&j->terminated_by_limits, a->TotalTerminatedProcesses);
            j->accounting_state = R2_WIN_JOB_FIELD_VALID;
            s->job_counts_valid = a->ActiveProcesses <= 1 && a->TotalTerminatedProcesses == 0 &&
                a->TotalProcesses == (r2_own_report_v1.process.acquired ? 1u : 0u);
            if (!s->job_counts_valid) r2_obs_fault_v1(R2_OBS_JOB_IO, R2_OBS_INVARIANT, R2_OBS_COUNT_CHANGED, 0);
        }
    }
    /* IoInfo in the extended-limit structure is RESERVED, never read. */
    memset(l, 0, sizeof(*l)); j->limits_readback_state = R2_WIN_JOB_FIELD_FAILED;
    if (r2_obs_query_v1(JobObjectExtendedLimitInformation, l, sizeof(*l), R2_OBS_JOB_LIMITS)) {
        r2_own_u32_v1(&j->limit_flags, l->BasicLimitInformation.LimitFlags);
        r2_own_u32_v1(&j->active_process_limit, l->BasicLimitInformation.ActiveProcessLimit);
        r2_own_u64_v1(&j->affinity, l->BasicLimitInformation.Affinity);
        r2_own_u64_v1(&j->job_commit_limit, l->JobMemoryLimit);
        r2_own_u64_v1(&j->process_commit_limit, l->ProcessMemoryLimit);
        r2_own_u64_v1(&j->peak_process_commit, l->PeakProcessMemoryUsed);
        r2_own_u64_v1(&j->peak_job_commit, l->PeakJobMemoryUsed);
        if (l->BasicLimitInformation.LimitFlags != R2_OWN_FLAGS || l->BasicLimitInformation.ActiveProcessLimit != 1 ||
            l->BasicLimitInformation.Affinity != r2_own_v1.limits.BasicLimitInformation.Affinity ||
            l->JobMemoryLimit != (SIZE_T)R2_OWN_COMMIT || l->ProcessMemoryLimit != 0 ||
            l->PeakProcessMemoryUsed > (SIZE_T)R2_OWN_COMMIT || l->PeakJobMemoryUsed > (SIZE_T)R2_OWN_COMMIT)
            r2_obs_fault_v1(R2_OBS_JOB_LIMITS, R2_OBS_INVARIANT, R2_OBS_LIMIT_CHANGED, 0);
        else j->limits_readback_state = R2_WIN_JOB_FIELD_VALID;
    }
    memset(c, 0, sizeof(*c)); j->cpu_readback_state = R2_WIN_JOB_FIELD_FAILED;
    if (r2_obs_query_v1(JobObjectCpuRateControlInformation, c, sizeof(*c), R2_OBS_JOB_CPU)) {
        r2_own_u32_v1(&j->cpu_control_flags, c->ControlFlags); r2_own_u32_v1(&j->cpu_rate, c->CpuRate);
        if (c->ControlFlags != R2_OWN_CPU_FLAGS || c->CpuRate != r2_own_v1.cpu.CpuRate)
            r2_obs_fault_v1(R2_OBS_JOB_CPU, R2_OBS_INVARIANT, R2_OBS_LIMIT_CHANGED, 0);
        else j->cpu_readback_state = R2_WIN_JOB_FIELD_VALID;
    }
}
static int r2_obs_wait_v1(HANDLE h, struct r2_win_job_raw_u32_v1 *out, uint32_t op)
{
    DWORD value;
    if (!r2_obs_ready_v1()) return 0;
    value = WaitForSingleObject(h, 0);
    if (value == WAIT_FAILED) { DWORD error = GetLastError(); out->state = R2_WIN_JOB_FIELD_FAILED; r2_obs_api_v1(op, error); return 0; }
    r2_own_u32_v1(out, value);
    if (value != WAIT_OBJECT_0 && value != WAIT_TIMEOUT) { r2_obs_fault_v1(op, R2_OBS_INVARIANT, R2_OBS_BAD_WAIT, 0); return 0; }
    return 1;
}
static int r2_obs_identity_v1(HANDLE h, uint32_t expected_pid, uint64_t expected_creation,
    struct r2_obs_process_v1 *p, int after, uint32_t pid_op, uint32_t times_op)
{
    FILETIME creation, exit_time, kernel, user;
    DWORD pid;
    if (!r2_obs_ready_v1()) return 0;
    pid = GetProcessId(h);
    if (!pid) { DWORD error = GetLastError(); r2_obs_api_v1(pid_op, error); return 0; }
    r2_own_u32_v1(after ? &p->pid_after : &p->pid_before, pid);
    if (pid != expected_pid) { r2_obs_fault_v1(pid_op, R2_OBS_INVARIANT, R2_OBS_IDENTITY_CHANGED, 0); return 0; }
    if (!r2_obs_ready_v1()) return 0;
    if (!GetProcessTimes(h, &creation, &exit_time, &kernel, &user)) {
        DWORD error = GetLastError(); r2_obs_api_v1(times_op, error); return 0;
    }
    r2_own_u64_v1(after ? &p->creation_after_100ns : &p->creation_before_100ns, r2_own_filetime_v1(creation));
    if (r2_own_filetime_v1(creation) != expected_creation) {
        r2_obs_fault_v1(times_op, R2_OBS_INVARIANT, R2_OBS_IDENTITY_CHANGED, 0); return 0;
    }
    r2_own_u64_v1(&p->kernel_100ns, r2_own_filetime_v1(kernel));
    r2_own_u64_v1(&p->user_100ns, r2_own_filetime_v1(user));
    /* Exit FILETIME is undefined for a live process. Read only after a
     * signaled BEFORE poll, not because a later poll happened to signal. */
    if (p->wait_before.state == R2_WIN_JOB_FIELD_VALID && p->wait_before.value == WAIT_OBJECT_0)
        r2_own_u64_v1(&p->exit_100ns, r2_own_filetime_v1(exit_time));
    return 1;
}
static void r2_obs_memory_map_v1(struct r2_obs_process_v1 *p)
{
    PROCESS_MEMORY_COUNTERS_EX *m = &r2_obs_memory_v1;
    r2_own_u32_v1(&p->memory_cb, m->cb); r2_own_u32_v1(&p->page_fault_count, m->PageFaultCount);
    r2_own_u64_v1(&p->peak_working_set_bytes, m->PeakWorkingSetSize);
    r2_own_u64_v1(&p->working_set_bytes, m->WorkingSetSize);
    r2_own_u64_v1(&p->peak_paged_pool_bytes, m->QuotaPeakPagedPoolUsage);
    r2_own_u64_v1(&p->paged_pool_bytes, m->QuotaPagedPoolUsage);
    r2_own_u64_v1(&p->peak_nonpaged_pool_bytes, m->QuotaPeakNonPagedPoolUsage);
    r2_own_u64_v1(&p->nonpaged_pool_bytes, m->QuotaNonPagedPoolUsage);
    r2_own_u64_v1(&p->pagefile_commit_bytes, m->PagefileUsage);
    r2_own_u64_v1(&p->peak_pagefile_commit_bytes, m->PeakPagefileUsage);
    r2_own_u64_v1(&p->private_commit_bytes, m->PrivateUsage);
    p->memory_state = R2_WIN_JOB_FIELD_VALID;
}
static void r2_obs_process_v1(int child, struct r2_obs_process_v1 *p)
{
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    struct r2_win_owned_handle_state_v1 *hs = child ? &o->process : &o->creator;
    struct r2_win_job_raw_u64_v1 *birth = child ? &o->child_creation_100ns : &o->creator_creation_100ns;
    HANDLE h = child ? r2_own_v1.process : r2_own_v1.creator;
    uint32_t base = child ? R2_OBS_CHILD_WAIT_BEFORE : R2_OBS_CREATOR_WAIT_BEFORE;
    uint32_t after = child ? R2_OBS_CHILD_PID_AFTER : R2_OBS_CREATOR_PID_AFTER;
    uint32_t memory_op = child ? R2_OBS_CHILD_MEMORY : R2_OBS_CREATOR_MEMORY;
    uint32_t expected_pid = child ? o->child_pid : o->creator_pid;
    BOOL member = FALSE;
    int before_ok, after_ok;
    p->acquired = hs->acquired;
    if (!h || hs->consumed) return; /* UNKNOWN values, never empty => zero. */
    p->disposition = R2_OBS_PROCESS_FAILED;
    if (!expected_pid || birth->state != R2_WIN_JOB_FIELD_VALID) {
        r2_obs_fault_v1(base + 1, R2_OBS_INVARIANT, R2_OBS_IDENTITY_CHANGED, 0); return;
    }
    before_ok = r2_obs_wait_v1(h, &p->wait_before, base);
    if (!r2_obs_identity_v1(h, expected_pid, birth->value, p, 0, base + 1, base + 2)) before_ok = 0;
    if (!before_ok) return;
    if (p->wait_before.value == WAIT_OBJECT_0) {
        p->disposition = R2_OBS_EXITED_BEFORE;
        /* Postexit memory deliberately unqueried/UNKNOWN; retained original
         * process timing is still a raw fact, no exit-snapshot resource proof. */
    } else {
        if (child) {
            if (!r2_obs_ready_v1()) return;
            if (!IsProcessInJob(h, r2_own_v1.job, &member)) {
                DWORD error = GetLastError(); r2_obs_api_v1(R2_OBS_CHILD_MEMBERSHIP, error); return;
            }
            if (!member) { r2_obs_fault_v1(R2_OBS_CHILD_MEMBERSHIP, R2_OBS_INVARIANT, R2_OBS_IDENTITY_CHANGED, 0); return; }
        }
        memset(&r2_obs_memory_v1, 0, sizeof(r2_obs_memory_v1));
        r2_obs_memory_v1.cb = sizeof(r2_obs_memory_v1);
        p->memory_state = R2_WIN_JOB_FIELD_FAILED;
        if (!r2_obs_ready_v1()) return;
        if (!K32GetProcessMemoryInfo(h, (PROCESS_MEMORY_COUNTERS *)&r2_obs_memory_v1, sizeof(r2_obs_memory_v1))) {
            DWORD error = GetLastError(); r2_obs_api_v1(memory_op, error);
        } else if (r2_obs_memory_v1.cb != sizeof(r2_obs_memory_v1)) {
            r2_obs_fault_v1(memory_op, R2_OBS_INVARIANT, R2_OBS_LENGTH_CHANGED, 0);
        } else r2_obs_memory_map_v1(p);
    }
    after_ok = r2_obs_identity_v1(h, expected_pid, birth->value, p, 1, after, after + 1);
    if (!r2_obs_wait_v1(h, &p->wait_after, after + 2)) after_ok = 0;
    p->identity_valid = after_ok;
    if (!after_ok) return;
    if (p->wait_before.value == WAIT_OBJECT_0 && p->wait_after.value != WAIT_OBJECT_0) {
        p->identity_valid = 0; p->disposition = R2_OBS_PROCESS_FAILED;
        r2_obs_fault_v1(after + 2, R2_OBS_INVARIANT, R2_OBS_BAD_WAIT, 0); return;
    }
    if (p->wait_before.value == WAIT_TIMEOUT && p->wait_after.value == WAIT_TIMEOUT) {
        p->disposition = R2_OBS_LIVE_BOTH_POLLS;
        p->live_memory_usable = p->memory_state == R2_WIN_JOB_FIELD_VALID;
    } else if (p->wait_before.value == WAIT_TIMEOUT) p->disposition = R2_OBS_EXIT_RACED;
    else if (!child) r2_obs_fault_v1(R2_OBS_CREATOR_WAIT_BEFORE, R2_OBS_INVARIANT, R2_OBS_BAD_WAIT, 0);
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_observation_describe_v1(struct r2_obs_abi_v1 *out, size_t size)
{
    const struct r2_obs_abi_v1 value = { R2_OBS_ABI, sizeof(value), sizeof(struct r2_obs_report_v1),
        sizeof(struct r2_obs_snapshot_v1), sizeof(struct r2_obs_process_v1), sizeof(struct r2_obs_fault_v1),
        offsetof(struct r2_obs_report_v1, first), offsetof(struct r2_obs_report_v1, latest),
        sizeof(void *), R2_OBS_ATTEMPT_CAPACITY, R2_OBS_FAULT_CAPACITY, 0 };
    if (size != sizeof(value) || !r2_own_range_v1(out, size, _Alignof(struct r2_obs_abi_v1))) return R2_OBS_BAD_ARGUMENT;
    memcpy(out, &value, sizeof(value)); return R2_OBS_OK;
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_observation_sample_step_v1(void)
{
    struct r2_obs_report_v1 *r = &r2_obs_report_v1;
    struct r2_win_owned_report_v1 *o = &r2_own_report_v1;
    struct r2_obs_snapshot_v1 *s = &r->latest;
    uint32_t status;
    if (!r2_own_enter_v1()) return R2_OBS_BUSY;
    /* The capability is the actual private owner, not caller metadata. Same
     * guard blocks all owner close/finish operations throughout observation. */
    if (!o->attempt_consumed || !r2_own_v1.deadline_bound ||
        o->lifecycle < R2_OWN_INTENT_HELD || o->lifecycle >= R2_OWN_CLOSING ||
        !r2_own_v1.creator || o->creator.consumed) {
        InterlockedExchange(&r2_own_guard_v1, 0); return R2_OBS_BAD_STATE;
    }
    r2_obs_step_faults_v1 = 0;
    if (r->fault_count) { r->status = R2_OBS_FAILED; goto leave; } /* copy/owner cleanup only; no retry */
    if (o->creator_pid != GetCurrentProcessId() || o->creator_tid != GetCurrentThreadId()) {
        r2_obs_fault_v1(R2_OBS_CONTEXT, R2_OBS_INVARIANT, R2_OBS_IDENTITY_CHANGED, 0);
        r->status = R2_OBS_FAILED; goto leave;
    }
    if (r->attempts == R2_OBS_ATTEMPT_CAPACITY) {
        r2_obs_fault_v1(R2_OBS_RESERVATION, R2_OBS_INVARIANT, R2_OBS_NO_RESERVATION, 0);
        r->status = R2_OBS_EXHAUSTED; goto leave;
    }
    ++r->attempts; /* irreversible reservation BEFORE any sampling API */
    memset(s, 0, sizeof(*s)); r->latest_valid = 0;
    s->sequence = r->attempts; s->owner_lifecycle = o->lifecycle; s->intent_serial = o->intent_serial;
    s->lease_epoch_qpc = o->lease_epoch_qpc; s->qpc_frequency = o->qpc_frequency;
    s->effective_deadline_qpc = o->finish_started ? o->cleanup_deadline_qpc : o->stop_deadline_qpc;
    if (!r2_obs_clock_v1(s->effective_deadline_qpc, &s->start_qpc)) goto sampled;
    r2_obs_job_v1(s);
    if (!r2_obs_clock_v1(s->effective_deadline_qpc, &s->end_qpc)) goto sampled;
    r2_obs_process_v1(0, &s->creator);
    if (!r2_obs_clock_v1(s->effective_deadline_qpc, &s->end_qpc)) goto sampled;
    r2_obs_process_v1(1, &s->child);
    s->completed_within_deadline = r2_obs_clock_v1(s->effective_deadline_qpc, &s->end_qpc);
sampled:
    s->local_fault_count = r2_obs_step_faults_v1;
    if (!s->completed_within_deadline) {
        s->creator.live_memory_usable = 0; s->child.live_memory_usable = 0;
    }
    r->latest_valid = 1; /* raw attempt retained, not whole-snapshot validity */
    if (!r->first_frozen) { memcpy(&r->first, s, sizeof(*s)); r->first_frozen = 1; }
    r->status = r->fault_count ? R2_OBS_FAILED :
        (s->job_counts_valid && s->creator.live_memory_usable && s->child.live_memory_usable ? R2_OBS_OK : R2_OBS_PARTIAL);
leave:
    r->stop_new = (uint32_t)r2_own_stopped_v1();
    r->owner_residual_bits = o->residual_bits; status = r->status;
    o->stop_new = r->stop_new;
    InterlockedExchange(&r2_own_guard_v1, 0); return status;
}
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_observation_copy_report_v1(struct r2_obs_report_v1 *out, size_t size)
{
    if (size != sizeof(*out) || !r2_own_range_v1(out, size, _Alignof(struct r2_obs_report_v1))) return R2_OBS_BAD_ARGUMENT;
    if (!r2_own_enter_v1()) return R2_OBS_BUSY;
    /* Native caller must additionally provide accessible, exclusive memory.
     * Reject overlap with all private owner/observation storage we expose in
     * this translation unit; no copy can overwrite the source or original PI. */
#define R2_OBS_OVERLAP(object) ((uintptr_t)out < (uintptr_t)&(object) + sizeof(object) && (uintptr_t)&(object) < (uintptr_t)out + size)
    if (R2_OBS_OVERLAP(r2_obs_report_v1) || R2_OBS_OVERLAP(r2_own_v1) || R2_OBS_OVERLAP(r2_own_report_v1) ||
        R2_OBS_OVERLAP(r2_own_guard_v1) || R2_OBS_OVERLAP(r2_own_stop_v1) ||
        R2_OBS_OVERLAP(r2_obs_io_v1) || R2_OBS_OVERLAP(r2_obs_limits_v1) || R2_OBS_OVERLAP(r2_obs_cpu_v1) ||
        R2_OBS_OVERLAP(r2_obs_memory_v1) || R2_OBS_OVERLAP(r2_obs_last_qpc_v1) || R2_OBS_OVERLAP(r2_obs_step_faults_v1)) {
        InterlockedExchange(&r2_own_guard_v1, 0); return R2_OBS_BAD_ARGUMENT;
    }
#undef R2_OBS_OVERLAP
    r2_obs_report_v1.stop_new = (uint32_t)r2_own_stopped_v1();
    r2_obs_report_v1.owner_residual_bits = r2_own_report_v1.residual_bits;
    memcpy(out, &r2_obs_report_v1, size);
    InterlockedExchange(&r2_own_guard_v1, 0); return R2_OBS_OK;
}
/* Interpretation limits: Job I/O counts include processes formerly assigned;
 * transfer counts are neither physical allocation nor disk writes attribution.
 * WorkingSetSize is one process's sampled resident working set including
 * shared pages, not unique physical RAM, complete RAM, VM, kernel/service or
 * whole-task coverage. Private/Pagefile/Job peaks are commitment, not RAM.
 * No summation, delta, rate, unit conversion or zero for an absent actor is
 * computed. QPC ticks and FILETIME100ns remain separate units and origins.
 * Live at both polls is not full interval, transient or creator history proof.
 * Raw Job/process API failures are independent/sticky and stop new owner work;
 * only the existing owner performs cleanup, with all originals still retained.
 * Synchronous API stalls, full fees and external closure remain UNKNOWN.
 * A caller must sample before original finish closes handles; this component
 * has no final callback/terminal coordinator. No whole-condition PASS results.
 */
