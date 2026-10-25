/* Separate Windows x64 C11 translation unit. Do not include or compile the
 * existing catalog/observation/mount-helper textual include chain here.
 * This owns actual local children; it is not its own earlier build supervisor.
 */
#if !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0A00 || !defined(_WIN64) || \
    !(defined(_M_X64) || defined(__x86_64__))
#error "build owner requires native Windows x64 and explicit Windows 10 target"
#endif
#ifndef PSAPI_VERSION
#define PSAPI_VERSION 2
#endif
#include <Windows.h>
#include <Psapi.h>
#ifndef PROC_THREAD_ATTRIBUTE_JOB_LIST
#error "SDK must expose PROC_THREAD_ATTRIBUTE_JOB_LIST"
#endif
#include <limits.h>
#include <string.h>
#include <wchar.h>
#include "route2_windows_build_owner.h"

#define R2_WBO_JOB_FLAGS (JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_AFFINITY | \
    JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
#define R2_WBO_CPU_FLAGS (JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP)
#define R2_WBO_CREATE_FLAGS (CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | \
    EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW)
#define R2_WBO_NO_STAGE UINT32_MAX
#define R2_WBO_STOP_EXIT 0xE0000001u

struct r2_wbo_stage_private_v1 {
    WCHAR application[R2_WBO_APP_UNITS];
    WCHAR command[R2_WBO_COMMAND_UNITS];
    WCHAR directory[R2_WBO_DIRECTORY_UNITS];
    WCHAR environment[R2_WBO_ENVIRONMENT_UNITS];
    HANDLE process, thread;
};
struct r2_wbo_private_v1 {
    struct r2_wbo_stage_private_v1 stages[R2_WBO_STAGES];
    HANDLE creator, job, jobs[1];
    STARTUPINFOEXW startup;
    PROCESS_INFORMATION pi;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
    JOBOBJECT_CPU_RATE_CONTROL_INFORMATION cpu;
    union { max_align_t align; unsigned char bytes[R2_WBO_ATTRIBUTE_BYTES]; } attributes;
    uint32_t attribute_live, step_calls, cleanup_mode;
    uint32_t final_attempted[R2_WBO_STAGES], final_verified[R2_WBO_STAGES];
    HANDLE cpu_event, cpu_thread;
    DWORD cpu_thread_id, cpu_expected_count;
    FILETIME cpu_idle, cpu_kernel, cpu_user;
    int64_t cpu_last_qpc;
    uint32_t cpu_has_baseline, cpu_thread_final_attempted, cpu_thread_final_verified;
    struct r2_wbo_system_cpu_v1 cpu_published;
    volatile LONG cpu_failure, cpu_error, cpu_reported, cpu_failure_phase;
    volatile LONG cpu_pairs, cpu_joined, cpu_cleanup_mode;
    volatile LONG cpu_job_claim, cpu_job_result, cpu_job_error;
    volatile LONG cpu_birth_generation, cpu_job_covered_birth;
    volatile LONG cpu_job_phase, cpu_job_reported;
    volatile LONG cpu_primary_steps, cpu_cleanup_steps;
    volatile LONG cpu_primary_calls, cpu_cleanup_calls;
};

_Static_assert(sizeof(void *) == 8 && sizeof(WCHAR) == 2 && sizeof(LONG) == 4,
    "native Windows x64 UTF16 layout");
_Static_assert(sizeof(struct r2_wbo_text_v1) == 16 &&
    sizeof(struct r2_wbo_stage_spec_v1) == 64 &&
    sizeof(struct r2_wbo_spec_v1) == 144, "build owner input ABI");
_Static_assert(sizeof(struct r2_wbo_fault_v1) == 24 &&
    sizeof(struct r2_wbo_handle_v1) == 16 &&
    sizeof(struct r2_wbo_sample_v1) <= 160, "build owner raw ABI");
_Static_assert(sizeof(struct r2_wbo_private_v1) +
    sizeof(struct r2_wbo_report_v1) <= 65536, "private input plus report cap");
_Static_assert(R2_WBO_OP_CPU_CLOSE < R2_WBO_FAULTS &&
    R2_WBO_STAGES == 2 && R2_WBO_PRIMARY_STEPS == 40000,
    "fixed fault/stage/step capacities");
_Static_assert(sizeof(struct r2_wbo_report_v1) <= UINT32_MAX,
    "report size field");

static volatile LONG r2_wbo_guard_v1;
static volatile LONG r2_wbo_stop_v1;
static SRWLOCK r2_wbo_cpu_lock_v1 = SRWLOCK_INIT;
static void r2_wbo_cpu_sync_v1(void);
static struct r2_wbo_private_v1 r2_wbo_private_v1;
static struct r2_wbo_report_v1 r2_wbo_report_v1 = {
    .abi = R2_WBO_ABI, .size = sizeof(struct r2_wbo_report_v1),
    .stage_running = R2_WBO_NO_STAGE
};

static int r2_wbo_enter_v1(void)
{
    return InterlockedCompareExchange(&r2_wbo_guard_v1, 1, 0) == 0;
}
static int r2_wbo_stopped_v1(void)
{
    return InterlockedCompareExchange(&r2_wbo_stop_v1, 0, 0) != 0;
}
static uint32_t r2_wbo_leave_v1(uint32_t result)
{
    r2_wbo_cpu_sync_v1();
    r2_wbo_report_v1.status = result;
    r2_wbo_report_v1.stop_new = (uint32_t)r2_wbo_stopped_v1();
    InterlockedExchange(&r2_wbo_guard_v1, 0);
    return result;
}
static int r2_wbo_range_v1(const void *pointer, size_t bytes, size_t alignment)
{
    uintptr_t address = (uintptr_t)pointer;
    return address && address % alignment == 0 && bytes <= UINTPTR_MAX - address;
}
static int r2_wbo_overlap_v1(const void *a, size_t na, const void *b, size_t nb)
{
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return x < y + nb && y < x + na;
}
static uint64_t r2_wbo_filetime_v1(FILETIME value)
{
    return ((uint64_t)value.dwHighDateTime << 32) | value.dwLowDateTime;
}
static void r2_wbo_fault_raw_v1(uint32_t operation, uint32_t kind,
    uint32_t code, DWORD win32_error)
{
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    struct r2_wbo_fault_v1 *f;
    uint32_t i, phase = r2_wbo_private_v1.cleanup_mode ? 2u : 1u;
    uint32_t error = kind == R2_WBO_WIN32 ? (uint32_t)win32_error : 0u;
    InterlockedExchange(&r2_wbo_stop_v1, 1);
    r->stop_new = 1;
    if (!operation || operation >= R2_WBO_FAULTS) {
        r->fault_overflow = 1; r->residual_bits |= R2_WBO_RESIDUAL_SAMPLE;
        return;
    }
    for (i = 0; i < r->fault_count; ++i) {
        f = &r->faults[i];
        if (f->operation == operation && f->kind == kind && f->code == code &&
            f->win32_error == error && f->phase == phase) {
            if (f->occurrences < UINT32_MAX) ++f->occurrences;
            return;
        }
    }
    if (r->fault_count >= R2_WBO_FAULTS) {
        r->fault_overflow = 1; r->residual_bits |= R2_WBO_RESIDUAL_SAMPLE;
        return;
    }
    f = &r->faults[r->fault_count];
    f->operation = operation; f->kind = kind; f->code = code;
    f->win32_error = error; f->phase = phase; f->occurrences = 1;
    if (!r->fault_count) r->primary = *f;
    ++r->fault_count;
}
static void r2_wbo_fault_v1(uint32_t operation, uint32_t kind,
    uint32_t code, DWORD win32_error)
{
    r2_wbo_cpu_sync_v1();
    r2_wbo_fault_raw_v1(operation, kind, code, win32_error);
}
static void r2_wbo_error_v1(uint32_t operation, DWORD error)
{
    r2_wbo_fault_v1(operation, R2_WBO_WIN32, 0, error);
}
static void r2_wbo_bad_v1(uint32_t operation, uint32_t code)
{
    r2_wbo_fault_v1(operation, R2_WBO_INVARIANT, code, 0);
}
/* Every potentially blocking OS operation and QPC read is charged before its
 * call. Each public work step has <=48 such calls. Failed calls consume work.
 * A separate cleanup reserve survives exhaustion of primary work. */
static int r2_wbo_call_v1(void)
{
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    uint32_t *total = r2_wbo_private_v1.cleanup_mode ? &r->cleanup_calls : &r->primary_calls;
    uint32_t limit = r2_wbo_private_v1.cleanup_mode ? R2_WBO_CLEANUP_CALLS : R2_WBO_PRIMARY_CALLS;
    if (r2_wbo_private_v1.step_calls >= R2_WBO_CALLS_PER_STEP || *total >= limit) {
        r2_wbo_bad_v1(R2_WBO_OP_WORK_LIMIT, 1);
        r->residual_bits |= R2_WBO_RESIDUAL_SAMPLE;
        return 0;
    }
    ++r2_wbo_private_v1.step_calls; ++*total;
    return 1;
}
static int r2_wbo_step_v1(int cleanup)
{
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    r2_wbo_private_v1.cleanup_mode = (uint32_t)cleanup;
    r2_wbo_private_v1.step_calls = 0;
    if (cleanup) {
        if (r->cleanup_steps >= R2_WBO_CLEANUP_STEPS) {
            r2_wbo_bad_v1(R2_WBO_OP_WORK_LIMIT, 2);
            r->residual_bits |= R2_WBO_RESIDUAL_JOIN;
            return 0;
        }
        ++r->cleanup_steps;
    } else {
        if (r->primary_steps >= R2_WBO_PRIMARY_STEPS) {
            r2_wbo_bad_v1(R2_WBO_OP_WORK_LIMIT, 3);
            return 0;
        }
        ++r->primary_steps;
    }
    return 1;
}
/* Deadline failure keeps a valid, monotone QPC usable for the original
 * cleanup window. Counter failure/regression quarantines time permanently. */
static int r2_wbo_clock_v1(int deadline, int sample_age)
{
    LARGE_INTEGER now;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    int64_t limit = r2_wbo_private_v1.cleanup_mode ? r->cleanup_deadline_qpc : r->active_deadline_qpc;
    if (r->clock_quarantined || !r2_wbo_call_v1()) return 0;
    if (!QueryPerformanceCounter(&now)) {
        DWORD error = GetLastError();
        r2_wbo_error_v1(R2_WBO_OP_CLOCK, error);
        r->clock_trusted = 0; r->clock_quarantined = 1;
        r->residual_bits |= R2_WBO_RESIDUAL_CLOCK;
        return 0;
    }
    if (now.QuadPart <= 0 || (r->last_qpc && now.QuadPart < r->last_qpc) ||
        !r->clock_trusted && r->last_qpc) {
        r2_wbo_bad_v1(R2_WBO_OP_CLOCK, 1);
        r->clock_trusted = 0; r->clock_quarantined = 1;
        r->residual_bits |= R2_WBO_RESIDUAL_CLOCK;
        return 0;
    }
    r->last_qpc = now.QuadPart;
    r->clock_trusted = 1;
    if (deadline && limit && now.QuadPart >= limit) {
        r2_wbo_bad_v1(R2_WBO_OP_DEADLINE, r2_wbo_private_v1.cleanup_mode ? 2 : 1);
        if (r2_wbo_private_v1.cleanup_mode) r->residual_bits |= R2_WBO_RESIDUAL_DEADLINE;
        return 0;
    }
    if (sample_age && r->last_sample_qpc &&
        now.QuadPart - r->last_sample_qpc > r->frequency_qpc / 10) {
        r2_wbo_bad_v1(R2_WBO_OP_FRESHNESS, 1);
        return 0;
    }
    return 1;
}
static int r2_wbo_fresh_v1(int64_t started)
{
    if (r2_wbo_report_v1.last_qpc - started > r2_wbo_report_v1.frequency_qpc / 10) {
        r2_wbo_bad_v1(R2_WBO_OP_FRESHNESS, 2);
        return 0;
    }
    return 1;
}
/* The observer alone writes its counters and sample. Its only shared OS handle
 * is the Job, which the public finisher cannot close until the thread joins. */
static int r2_wbo_cpu_charge_v1(uint32_t cleanup, uint32_t *step_calls, int emergency)
{
    volatile LONG *total = cleanup ? &r2_wbo_private_v1.cpu_cleanup_calls :
        &r2_wbo_private_v1.cpu_primary_calls;
    LONG limit = cleanup ? R2_WBO_CPU_CLEANUP_CALLS : R2_WBO_CPU_PRIMARY_CALLS;
    LONG used = InterlockedCompareExchange(total, 0, 0);
    if (used >= limit || (!emergency && *step_calls >= R2_WBO_CPU_CALLS_PER_STEP)) return 0;
    InterlockedIncrement(total);
    if (!emergency) ++*step_calls;
    return 1;
}
static int r2_wbo_cpu_step_v1(uint32_t cleanup)
{
    volatile LONG *steps = cleanup ? &r2_wbo_private_v1.cpu_cleanup_steps :
        &r2_wbo_private_v1.cpu_primary_steps;
    LONG limit = cleanup ? R2_WBO_CPU_CLEANUP_STEPS : R2_WBO_CPU_PRIMARY_STEPS;
    if (InterlockedCompareExchange(steps, 0, 0) >= limit) return 0;
    InterlockedIncrement(steps);
    return 1;
}
static void r2_wbo_cpu_terminate_v1(uint32_t worker, uint32_t cleanup,
    uint32_t *step_calls)
{
    BOOL success;
    DWORD error = 0;
    if (!r2_wbo_private_v1.job ||
        InterlockedCompareExchange(&r2_wbo_private_v1.cpu_job_claim, 1, 0)) return;
    InterlockedExchange(&r2_wbo_private_v1.cpu_job_phase, cleanup ? 2 : 1);
    if (worker ? !r2_wbo_cpu_charge_v1(cleanup, step_calls, 1) : !r2_wbo_call_v1()) {
        InterlockedExchange(&r2_wbo_private_v1.cpu_job_result, -1);
        return;
    }
    /* Only births published before the request are covered by its success. */
    InterlockedExchange(&r2_wbo_private_v1.cpu_job_covered_birth,
        InterlockedCompareExchange(&r2_wbo_private_v1.cpu_birth_generation, 0, 0));
    success = TerminateJobObject(r2_wbo_private_v1.job, R2_WBO_STOP_EXIT);
    if (!success) error = GetLastError();
    InterlockedExchange(&r2_wbo_private_v1.cpu_job_error, (LONG)error);
    InterlockedExchange(&r2_wbo_private_v1.cpu_job_result, success ? 1 : -1);
}
static void r2_wbo_cpu_fail_v1(LONG reason, DWORD error, uint32_t cleanup,
    uint32_t *step_calls)
{
    struct r2_wbo_private_v1 *p = &r2_wbo_private_v1;
    if (!InterlockedCompareExchange(&p->cpu_failure, 0, 0)) {
        InterlockedExchange(&p->cpu_error, (LONG)error);
        InterlockedExchange(&p->cpu_failure_phase, cleanup ? 2 : 1);
        InterlockedExchange(&p->cpu_failure, reason);
    }
    /* The cause is complete before another thread can observe this STOP. */
    InterlockedExchange(&r2_wbo_stop_v1, 1);
    r2_wbo_cpu_terminate_v1(1, cleanup, step_calls);
}
/* No CRT calls, allocations, mutable child handles, or report writes here. */
static DWORD WINAPI r2_wbo_cpu_thread_v1(LPVOID ignored)
{
    struct r2_wbo_private_v1 *p = &r2_wbo_private_v1;
    struct r2_wbo_system_cpu_v1 sample;
    FILETIME idle, kernel, user;
    LARGE_INTEGER before, after, wake;
    uint64_t di, dk, du, total, busy;
    WORD groups;
    DWORD count, result, error;
    uint32_t calls, cleanup;
    (void)ignored;
    for (;;) {
        cleanup = (uint32_t)InterlockedCompareExchange(&p->cpu_cleanup_mode, 0, 0);
        calls = 0;
        if (!r2_wbo_cpu_step_v1(cleanup)) {
            r2_wbo_cpu_fail_v1(8, 0, cleanup, &calls); break;
        }
        if (!r2_wbo_cpu_charge_v1(cleanup, &calls, 0)) {
            r2_wbo_cpu_fail_v1(8, 0, cleanup, &calls); break;
        }
        if (!QueryPerformanceCounter(&before)) {
            error = GetLastError(); r2_wbo_cpu_fail_v1(1, error, cleanup, &calls); break;
        }
        if (before.QuadPart <= 0 || before.QuadPart < p->cpu_last_qpc) {
            r2_wbo_cpu_fail_v1(10, 0, cleanup, &calls); break;
        }
        if (before.QuadPart - p->cpu_last_qpc > r2_wbo_report_v1.frequency_qpc / 10) {
            r2_wbo_cpu_fail_v1(6, 0, cleanup, &calls); break;
        }
        if (before.QuadPart >= (cleanup ? r2_wbo_report_v1.cleanup_deadline_qpc :
            r2_wbo_report_v1.active_deadline_qpc)) {
            r2_wbo_cpu_fail_v1(7, 0, cleanup, &calls); break;
        }
        if (!r2_wbo_cpu_charge_v1(cleanup, &calls, 0)) {
            r2_wbo_cpu_fail_v1(8, 0, cleanup, &calls); break;
        }
        groups = GetActiveProcessorGroupCount();
        if (!r2_wbo_cpu_charge_v1(cleanup, &calls, 0)) {
            r2_wbo_cpu_fail_v1(8, 0, cleanup, &calls); break;
        }
        count = GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
        if (groups != 1 || count != p->cpu_expected_count || !count || count > 64) {
            r2_wbo_cpu_fail_v1(2, 0, cleanup, &calls); break;
        }
        if (!r2_wbo_cpu_charge_v1(cleanup, &calls, 0)) {
            r2_wbo_cpu_fail_v1(8, 0, cleanup, &calls); break;
        }
        if (!GetSystemTimes(&idle, &kernel, &user)) {
            error = GetLastError(); r2_wbo_cpu_fail_v1(3, error, cleanup, &calls); break;
        }
        if (!r2_wbo_cpu_charge_v1(cleanup, &calls, 0)) {
            r2_wbo_cpu_fail_v1(8, 0, cleanup, &calls); break;
        }
        if (!QueryPerformanceCounter(&after)) {
            error = GetLastError(); r2_wbo_cpu_fail_v1(1, error, cleanup, &calls); break;
        }
        if (after.QuadPart < before.QuadPart) {
            r2_wbo_cpu_fail_v1(10, 0, cleanup, &calls); break;
        }
        if (after.QuadPart - before.QuadPart > r2_wbo_report_v1.frequency_qpc / 10) {
            r2_wbo_cpu_fail_v1(6, 0, cleanup, &calls); break;
        }
        if (after.QuadPart - p->cpu_last_qpc > r2_wbo_report_v1.frequency_qpc / 10) {
            r2_wbo_cpu_fail_v1(6, 0, cleanup, &calls); break;
        }
        if (after.QuadPart >= (cleanup ? r2_wbo_report_v1.cleanup_deadline_qpc :
            r2_wbo_report_v1.active_deadline_qpc)) {
            r2_wbo_cpu_fail_v1(7, 0, cleanup, &calls); break;
        }
        sample.start_qpc = before.QuadPart; sample.end_qpc = after.QuadPart;
        sample.idle_100ns = r2_wbo_filetime_v1(idle);
        sample.kernel_100ns = r2_wbo_filetime_v1(kernel);
        sample.user_100ns = r2_wbo_filetime_v1(user);
        sample.groups = groups; sample.processors = count;
        sample.total_delta_100ns = sample.busy_delta_100ns = 0;
        sample.pair_valid = sample.high = 0;
        if (sample.idle_100ns > sample.kernel_100ns ||
            (p->cpu_has_baseline &&
             (sample.idle_100ns < r2_wbo_filetime_v1(p->cpu_idle) ||
              sample.kernel_100ns < r2_wbo_filetime_v1(p->cpu_kernel) ||
              sample.user_100ns < r2_wbo_filetime_v1(p->cpu_user)))) {
            r2_wbo_cpu_fail_v1(4, 0, cleanup, &calls); break;
        }
        if (p->cpu_has_baseline) {
            di = sample.idle_100ns - r2_wbo_filetime_v1(p->cpu_idle);
            dk = sample.kernel_100ns - r2_wbo_filetime_v1(p->cpu_kernel);
            du = sample.user_100ns - r2_wbo_filetime_v1(p->cpu_user);
            if (di > dk || dk > UINT64_MAX - du) {
                r2_wbo_cpu_fail_v1(4, 0, cleanup, &calls); break;
            }
            total = dk + du;
            if (total) {
                busy = total - di;
                sample.total_delta_100ns = total;
                sample.busy_delta_100ns = busy;
                sample.pair_valid = 1;
                sample.high = r2_wbo_system_busy_ge90_v1(busy, total);
            } else if (InterlockedCompareExchange(&p->cpu_pairs, 0, 0)) {
                r2_wbo_cpu_fail_v1(4, 0, cleanup, &calls); break;
            }
        }
        p->cpu_idle = idle; p->cpu_kernel = kernel; p->cpu_user = user;
        p->cpu_has_baseline = 1; p->cpu_last_qpc = after.QuadPart;
        if (!TryAcquireSRWLockExclusive(&r2_wbo_cpu_lock_v1)) {
            r2_wbo_cpu_fail_v1(9, 0, cleanup, &calls); break;
        }
        p->cpu_published = sample;
        if (sample.pair_valid) InterlockedIncrement(&p->cpu_pairs);
        ReleaseSRWLockExclusive(&r2_wbo_cpu_lock_v1);
        if (sample.high) {
            r2_wbo_cpu_fail_v1(5, 0, cleanup, &calls); break;
        }
        if (!r2_wbo_cpu_charge_v1(cleanup, &calls, 0)) {
            r2_wbo_cpu_fail_v1(8, 0, cleanup, &calls); break;
        }
        result = WaitForSingleObject(p->cpu_event, 20);
        if (result == WAIT_OBJECT_0) {
            cleanup = (uint32_t)InterlockedCompareExchange(&p->cpu_cleanup_mode, 0, 0);
            if (!r2_wbo_cpu_charge_v1(cleanup, &calls, 0)) {
                r2_wbo_cpu_fail_v1(8, 0, cleanup, &calls); break;
            }
            if (!QueryPerformanceCounter(&wake)) {
                error = GetLastError(); r2_wbo_cpu_fail_v1(1, error, cleanup, &calls); break;
            }
            if (wake.QuadPart <= 0 || wake.QuadPart < p->cpu_last_qpc) {
                r2_wbo_cpu_fail_v1(10, 0, cleanup, &calls); break;
            }
            if (wake.QuadPart - p->cpu_last_qpc > r2_wbo_report_v1.frequency_qpc / 10) {
                r2_wbo_cpu_fail_v1(6, 0, cleanup, &calls); break;
            }
            if (wake.QuadPart >= (cleanup ? r2_wbo_report_v1.cleanup_deadline_qpc :
                r2_wbo_report_v1.active_deadline_qpc)) {
                r2_wbo_cpu_fail_v1(7, 0, cleanup, &calls); break;
            }
            break;
        }
        if (result != WAIT_TIMEOUT) {
            error = result == WAIT_FAILED ? GetLastError() : 0;
            r2_wbo_cpu_fail_v1(9, error, cleanup, &calls); break;
        }
    }
    return 0;
}
static void r2_wbo_cpu_sync_v1(void)
{
    struct r2_wbo_private_v1 *p = &r2_wbo_private_v1;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    LONG job = InterlockedCompareExchange(&p->cpu_job_result, 0, 0);
    LONG reason = InterlockedCompareExchange(&p->cpu_failure, 0, 0);
    uint32_t prior = p->cleanup_mode;
    r->cpu_primary_steps = (uint32_t)InterlockedCompareExchange(&p->cpu_primary_steps, 0, 0);
    r->cpu_cleanup_steps = (uint32_t)InterlockedCompareExchange(&p->cpu_cleanup_steps, 0, 0);
    r->cpu_primary_calls = (uint32_t)InterlockedCompareExchange(&p->cpu_primary_calls, 0, 0);
    r->cpu_cleanup_calls = (uint32_t)InterlockedCompareExchange(&p->cpu_cleanup_calls, 0, 0);
    r->cpu_pair_count = (uint32_t)InterlockedCompareExchange(&p->cpu_pairs, 0, 0);
    if (reason && !p->cpu_reported) {
        uint32_t op = reason == 1 || reason == 10 ? R2_WBO_OP_CLOCK :
            reason == 2 ? R2_WBO_OP_CPU_TOPOLOGY :
            reason == 7 ? R2_WBO_OP_DEADLINE :
            reason == 8 ? R2_WBO_OP_WORK_LIMIT : R2_WBO_OP_SYSTEM_CPU;
        DWORD error = (DWORD)InterlockedCompareExchange(&p->cpu_error, 0, 0);
        p->cpu_reported = 1;
        r->cpu_stop_reason = (uint32_t)reason; r->cpu_stop_error = error;
        if (reason == 1 || reason == 10) {
            r->clock_trusted = 0;
            r->clock_quarantined = 1;
            r->residual_bits |= R2_WBO_RESIDUAL_CLOCK;
        }
        p->cleanup_mode = InterlockedCompareExchange(&p->cpu_failure_phase, 0, 0) == 2;
        r2_wbo_fault_raw_v1(op, error ? R2_WBO_WIN32 : R2_WBO_INVARIANT,
            (uint32_t)reason, error);
        p->cleanup_mode = prior;
    }
    if (InterlockedCompareExchange(&p->cpu_job_claim, 0, 0)) r->terminate_job_attempted = 1;
    if (job == 1) r->terminate_job_succeeded = 1;
    if (job == -1 && !p->cpu_job_reported) {
        DWORD error = (DWORD)InterlockedCompareExchange(&p->cpu_job_error, 0, 0);
        p->cpu_job_reported = 1;
        p->cleanup_mode = InterlockedCompareExchange(&p->cpu_job_phase, 0, 0) == 2;
        r2_wbo_fault_raw_v1(R2_WBO_OP_TERMINATE_JOB,
            error ? R2_WBO_WIN32 : R2_WBO_INVARIANT, 1, error);
        r->residual_bits |= R2_WBO_RESIDUAL_JOIN;
        p->cleanup_mode = prior;
    }
}
static int r2_wbo_cpu_gate_v1(int require_pair)
{
    struct r2_wbo_system_cpu_v1 sample;
    struct r2_wbo_private_v1 *p = &r2_wbo_private_v1;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    r2_wbo_cpu_sync_v1();
    if (r2_wbo_stopped_v1()) return 0;
    if (!TryAcquireSRWLockShared(&r2_wbo_cpu_lock_v1)) {
        r2_wbo_bad_v1(R2_WBO_OP_SYSTEM_CPU, 9);
        r2_wbo_cpu_terminate_v1(0, p->cleanup_mode, NULL); return 0;
    }
    sample = p->cpu_published;
    ReleaseSRWLockShared(&r2_wbo_cpu_lock_v1);
    if (!r2_wbo_clock_v1(1, 0)) return 0;
    r->system_cpu = sample;
    if (!sample.pair_valid) {
        if (!require_pair) return 2;
        r2_wbo_bad_v1(R2_WBO_OP_SYSTEM_CPU, 10);
        r2_wbo_cpu_terminate_v1(0, p->cleanup_mode, NULL); return 0;
    }
    if (sample.high || sample.end_qpc <= 0 || sample.end_qpc > r->last_qpc ||
        r->last_qpc - sample.end_qpc > r->frequency_qpc / 10) {
        r2_wbo_bad_v1(R2_WBO_OP_SYSTEM_CPU, sample.high ? 5 : 6);
        r2_wbo_cpu_terminate_v1(0, p->cleanup_mode, NULL); return 0;
    }
    return !r2_wbo_stopped_v1();
}
static int r2_wbo_absolute_v1(const WCHAR *p, uint32_t length)
{
    if (length >= 4 && p[1] == L':' && (p[2] == L'\\' || p[2] == L'/') &&
        ((p[0] >= L'A' && p[0] <= L'Z') || (p[0] >= L'a' && p[0] <= L'z')))
        return 1;
    return length >= 5 && p[0] == L'\\' && p[1] == L'\\' &&
        p[2] != L'\\' && p[2] != L'\0';
}
static int r2_wbo_text_v1(WCHAR *out, uint32_t capacity,
    const struct r2_wbo_text_v1 *in, int environment, int absolute)
{
    uint32_t i;
    if (in->reserved || !in->units || in->units > capacity ||
        !r2_wbo_range_v1(in->data, (size_t)in->units * sizeof(uint16_t), _Alignof(uint16_t)) ||
        r2_wbo_overlap_v1(in->data, (size_t)in->units * sizeof(uint16_t),
            &r2_wbo_private_v1, sizeof(r2_wbo_private_v1)) ||
        r2_wbo_overlap_v1(in->data, (size_t)in->units * sizeof(uint16_t),
            &r2_wbo_report_v1, sizeof(r2_wbo_report_v1))) return 0;
    if (environment) {
        if (in->units < 2 || in->data[in->units - 1] || in->data[in->units - 2]) return 0;
        for (i = 0; i + 1 < in->units - 1; ++i)
            if (!in->data[i] && !in->data[i + 1]) return 0;
    } else {
        if (in->data[in->units - 1] || (absolute && !r2_wbo_absolute_v1((const WCHAR *)in->data, in->units))) return 0;
        for (i = 0; i + 1 < in->units; ++i) if (!in->data[i]) return 0;
    }
    memcpy(out, in->data, (size_t)in->units * sizeof(WCHAR));
    return 1;
}
static int r2_wbo_creator_v1(void)
{
    DWORD id, current_id, current_thread;
    FILETIME creation, exit_time, kernel, user;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    if (!r2_wbo_private_v1.creator || !r2_wbo_call_v1()) return 0;
    id = GetProcessId(r2_wbo_private_v1.creator);
    if (!id) { DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CREATOR_ID, e); return 0; }
    if (!r2_wbo_call_v1()) return 0;
    current_id = GetCurrentProcessId();
    if (!r2_wbo_call_v1()) return 0;
    current_thread = GetCurrentThreadId();
    if (id != r->creator_id || id != current_id ||
        r->creator_thread_id != current_thread) {
        r2_wbo_bad_v1(R2_WBO_OP_CREATOR_ID, 1); return 0;
    }
    if (!r2_wbo_call_v1()) return 0;
    if (!GetProcessTimes(r2_wbo_private_v1.creator, &creation, &exit_time, &kernel, &user)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CREATOR_TIME, e); return 0;
    }
    if (r->creator_creation_100ns &&
        r->creator_creation_100ns != r2_wbo_filetime_v1(creation)) {
        r2_wbo_bad_v1(R2_WBO_OP_CREATOR_TIME, 1); return 0;
    }
    r->creator_creation_100ns = r2_wbo_filetime_v1(creation);
    return 1;
}
static int r2_wbo_child_identity_v1(uint32_t index)
{
    DWORD id, tid;
    BOOL member = FALSE;
    FILETIME creation, exit_time, kernel, user;
    struct r2_wbo_stage_private_v1 *p = &r2_wbo_private_v1.stages[index];
    struct r2_wbo_stage_report_v1 *s = &r2_wbo_report_v1.stages[index];
    if (!p->process || !p->thread || !r2_wbo_call_v1()) return 0;
    id = GetProcessId(p->process);
    if (!id) { DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_PROCESS_ID, e); return 0; }
    if (!r2_wbo_call_v1()) return 0;
    tid = GetThreadId(p->thread);
    if (!tid) { DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_THREAD_ID, e); return 0; }
    if (id != s->process_id || tid != s->thread_id || id == r2_wbo_report_v1.creator_id) {
        r2_wbo_bad_v1(R2_WBO_OP_PROCESS_ID, 1); return 0;
    }
    if (!r2_wbo_call_v1()) return 0;
    if (!GetProcessTimes(p->process, &creation, &exit_time, &kernel, &user)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_PROCESS_TIME, e); return 0;
    }
    if (s->process_creation_100ns && s->process_creation_100ns != r2_wbo_filetime_v1(creation)) {
        r2_wbo_bad_v1(R2_WBO_OP_PROCESS_TIME, 1); return 0;
    }
    s->process_creation_100ns = r2_wbo_filetime_v1(creation);
    if (!r2_wbo_call_v1()) return 0;
    if (!GetThreadTimes(p->thread, &creation, &exit_time, &kernel, &user)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_THREAD_TIME, e); return 0;
    }
    if (s->thread_creation_100ns && s->thread_creation_100ns != r2_wbo_filetime_v1(creation)) {
        r2_wbo_bad_v1(R2_WBO_OP_THREAD_TIME, 1); return 0;
    }
    s->thread_creation_100ns = r2_wbo_filetime_v1(creation);
    if (!r2_wbo_call_v1()) return 0;
    if (!IsProcessInJob(p->process, r2_wbo_private_v1.job, &member)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_MEMBERSHIP, e); return 0;
    }
    if (!member) { r2_wbo_bad_v1(R2_WBO_OP_MEMBERSHIP, 1); return 0; }
    s->membership = 1;
    return 1;
}
/* One bounded point snapshot. Every returned length, configured limit and
 * process count is checked. Child memory is sampled only while observed live;
 * missing final memory never becomes a fabricated zero. */
static int r2_wbo_sample_v1(struct r2_wbo_sample_v1 *out, uint32_t index, int process_live)
{
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION a;
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
    JOBOBJECT_CPU_RATE_CONTROL_INFORMATION cpu;
    PROCESS_MEMORY_COUNTERS_EX memory;
    FILETIME creation, exit_time, kernel, user;
    DWORD returned = 0;
    int64_t started;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    memset(out, 0, sizeof(*out));
    if (!r2_wbo_clock_v1(1, 0)) return 0;
    out->start_qpc = started = r->last_qpc;
    if (!r2_wbo_call_v1()) return 0;
    if (!QueryInformationJobObject(r2_wbo_private_v1.job,
        JobObjectBasicAccountingInformation, &a, sizeof(a), &returned)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_JOB_ACCOUNT, e); return 0;
    }
    if (returned != sizeof(a) || a.TotalUserTime.QuadPart < 0 || a.TotalKernelTime.QuadPart < 0) {
        r2_wbo_bad_v1(R2_WBO_OP_JOB_ACCOUNT, 1); return 0;
    }
    out->job_valid = 1;
    out->total_processes = a.TotalProcesses;
    out->active_processes = a.ActiveProcesses;
    out->terminated_processes = a.TotalTerminatedProcesses;
    out->page_faults = a.TotalPageFaultCount;
    out->job_user_100ns = (uint64_t)a.TotalUserTime.QuadPart;
    out->job_kernel_100ns = (uint64_t)a.TotalKernelTime.QuadPart;
    returned = 0;
    if (!r2_wbo_call_v1()) return 0;
    if (!QueryInformationJobObject(r2_wbo_private_v1.job,
        JobObjectExtendedLimitInformation, &limits, sizeof(limits), &returned)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_JOB_QUERY_LIMIT, e); return 0;
    }
    if (returned != sizeof(limits) || limits.BasicLimitInformation.LimitFlags != R2_WBO_JOB_FLAGS ||
        limits.BasicLimitInformation.ActiveProcessLimit != 1 ||
        limits.BasicLimitInformation.Affinity != r2_wbo_private_v1.limits.BasicLimitInformation.Affinity ||
        limits.JobMemoryLimit != (SIZE_T)R2_WBO_JOB_COMMIT_BYTES ||
        limits.ProcessMemoryLimit != 0 ||
        limits.PeakJobMemoryUsed > (SIZE_T)R2_WBO_JOB_COMMIT_BYTES) {
        r2_wbo_bad_v1(R2_WBO_OP_JOB_QUERY_LIMIT, 1); return 0;
    }
    out->limit_valid = 1;
    out->limit_flags = limits.BasicLimitInformation.LimitFlags;
    out->active_limit = limits.BasicLimitInformation.ActiveProcessLimit;
    out->peak_job_commit = limits.PeakJobMemoryUsed;
    out->peak_process_commit = limits.PeakProcessMemoryUsed;
    returned = 0;
    if (!r2_wbo_call_v1()) return 0;
    if (!QueryInformationJobObject(r2_wbo_private_v1.job,
        JobObjectCpuRateControlInformation, &cpu, sizeof(cpu), &returned)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_JOB_QUERY_CPU, e); return 0;
    }
    if (returned != sizeof(cpu) || cpu.ControlFlags != R2_WBO_CPU_FLAGS ||
        cpu.CpuRate != r2_wbo_private_v1.cpu.CpuRate) {
        r2_wbo_bad_v1(R2_WBO_OP_JOB_QUERY_CPU, 1); return 0;
    }
    out->cpu_valid = 1;
    out->cpu_flags = cpu.ControlFlags; out->cpu_rate = cpu.CpuRate;
    if (process_live && index < R2_WBO_STAGES) {
        memset(&memory, 0, sizeof(memory)); memory.cb = sizeof(memory);
        if (!r2_wbo_call_v1()) return 0;
        if (!K32GetProcessMemoryInfo(r2_wbo_private_v1.stages[index].process,
            (PROCESS_MEMORY_COUNTERS *)&memory, sizeof(memory))) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_PROCESS_MEMORY, e); return 0;
        }
        if (memory.cb != sizeof(memory)) { r2_wbo_bad_v1(R2_WBO_OP_PROCESS_MEMORY, 1); return 0; }
        out->process_working_set = memory.WorkingSetSize;
        out->process_private_commit = memory.PrivateUsage;
        if (!r2_wbo_call_v1()) return 0;
        if (!GetProcessTimes(r2_wbo_private_v1.stages[index].process,
            &creation, &exit_time, &kernel, &user)) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_PROCESS_TIME, e); return 0;
        }
        if (r->stages[index].process_creation_100ns &&
            r->stages[index].process_creation_100ns != r2_wbo_filetime_v1(creation)) {
            r2_wbo_bad_v1(R2_WBO_OP_PROCESS_TIME, 1); return 0;
        }
        if (r2_wbo_filetime_v1(user) > INT64_MAX || r2_wbo_filetime_v1(kernel) > INT64_MAX) {
            r2_wbo_bad_v1(R2_WBO_OP_PROCESS_TIME, 2); return 0;
        }
        out->process_user_100ns = r2_wbo_filetime_v1(user);
        out->process_kernel_100ns = r2_wbo_filetime_v1(kernel);
        out->process_valid = 1;
    }
    if (!r2_wbo_clock_v1(1, 0)) return 0;
    out->end_qpc = r->last_qpc;
    if (!r2_wbo_fresh_v1(started)) return 0;
    r->last_sample_qpc = out->end_qpc;
    return 1;
}
static int r2_wbo_counts_v1(const struct r2_wbo_sample_v1 *s,
    uint32_t expected_total, uint32_t expected_active)
{
    if (s->job_valid && (s->total_processes != expected_total ||
        s->terminated_processes > s->total_processes))
        r2_wbo_report_v1.residual_bits |= R2_WBO_RESIDUAL_HISTORY;
    if (!s->job_valid || s->total_processes != expected_total ||
        s->active_processes != expected_active ||
        s->terminated_processes > s->total_processes) {
        r2_wbo_bad_v1(R2_WBO_OP_JOB_ACCOUNT, 2); return 0;
    }
    r2_wbo_report_v1.job_empty = expected_active == 0;
    return 1;
}
static int r2_wbo_cleanup_empty_v1(const struct r2_wbo_sample_v1 *s,
    uint32_t expected_total)
{
    if (!s->job_valid || s->active_processes != 0u) return 0;
    r2_wbo_report_v1.job_empty = 1;
    if (s->total_processes != expected_total ||
        s->terminated_processes > s->total_processes) {
        r2_wbo_report_v1.residual_bits |= R2_WBO_RESIDUAL_HISTORY;
        r2_wbo_bad_v1(R2_WBO_OP_JOB_ACCOUNT, 5);
    }
    return 1;
}
/* A close is attempted once. A failed original stays in its private slot;
 * no retry or inferred release follows from CloseHandle failure. */
static int r2_wbo_close_v1(HANDLE *slot, struct r2_wbo_handle_v1 *state, uint32_t operation)
{
    if (!*slot) return !state->acquired || state->close_succeeded;
    if (state->close_attempted || !r2_wbo_clock_v1(1, 0) || !r2_wbo_call_v1()) return 0;
    state->close_attempted = 1;
    if (!CloseHandle(*slot)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(operation, e);
        r2_wbo_report_v1.residual_bits |= R2_WBO_RESIDUAL_CLOSE;
        return 0;
    }
    *slot = NULL; state->close_succeeded = 1;
    return r2_wbo_clock_v1(1, 0);
}
static DWORD r2_wbo_wait_slice_v1(void)
{
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    int64_t deadline = r2_wbo_private_v1.cleanup_mode ? r->cleanup_deadline_qpc : r->active_deadline_qpc;
    int64_t remaining = deadline - r->last_qpc;
    uint64_t milliseconds;
    if (remaining <= 0 || r->frequency_qpc <= 0) return 0;
    milliseconds = ((uint64_t)remaining / (uint64_t)r->frequency_qpc) * 1000u +
        ((uint64_t)remaining % (uint64_t)r->frequency_qpc) * 1000u /
        (uint64_t)r->frequency_qpc;
    return (DWORD)(milliseconds > 50u ? 50u : milliseconds);
}

/* Called only after both originals signal and the Job is empty. A failed
 * identity/final query leaves originals retained; no second final query is
 * attempted. Exit code 259 is valid after a signaled process handle. */
static int r2_wbo_complete_stage_v1(uint32_t index)
{
    DWORD code;
    FILETIME creation, exit_time, kernel, user;
    struct r2_wbo_stage_private_v1 *p = &r2_wbo_private_v1.stages[index];
    struct r2_wbo_stage_report_v1 *s = &r2_wbo_report_v1.stages[index];
    if (!s->process_signaled || !s->thread_signaled) goto residual;
    if (r2_wbo_private_v1.cleanup_mode) {
        if (!r2_wbo_cleanup_empty_v1(&s->latest_sample, index + 1u)) goto residual;
    } else if (!r2_wbo_counts_v1(&s->latest_sample, index + 1u, 0u))
        return 0; /* history STOP; cleanup still owns both originals */
    if (!r2_wbo_private_v1.final_attempted[index]) {
        r2_wbo_private_v1.final_attempted[index] = 1;
        if (!r2_wbo_child_identity_v1(index) || !r2_wbo_call_v1()) goto residual;
        if (!GetExitCodeProcess(p->process, &code)) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_EXIT_CODE, e); goto residual;
        }
        s->exit_code_valid = 1; s->exit_code = code;
        if (!r2_wbo_call_v1()) goto residual;
        if (!GetProcessTimes(p->process, &creation, &exit_time, &kernel, &user)) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_PROCESS_TIME, e); goto residual;
        }
        if (r2_wbo_filetime_v1(creation) != s->process_creation_100ns) {
            r2_wbo_bad_v1(R2_WBO_OP_PROCESS_TIME, 2); goto residual;
        }
        s->final_process_user_100ns = r2_wbo_filetime_v1(user);
        s->final_process_kernel_100ns = r2_wbo_filetime_v1(kernel);
        if (!r2_wbo_call_v1()) goto residual;
        if (!GetThreadTimes(p->thread, &creation, &exit_time, &kernel, &user)) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_THREAD_TIME, e); goto residual;
        }
        if (r2_wbo_filetime_v1(creation) != s->thread_creation_100ns) {
            r2_wbo_bad_v1(R2_WBO_OP_THREAD_TIME, 2); goto residual;
        }
        s->final_thread_user_100ns = r2_wbo_filetime_v1(user);
        s->final_thread_kernel_100ns = r2_wbo_filetime_v1(kernel);
        r2_wbo_private_v1.final_verified[index] = 1;
        if (code) r2_wbo_bad_v1(R2_WBO_OP_EXIT_CODE, code);
    }
    if (!r2_wbo_private_v1.final_verified[index]) goto residual;
    code = s->exit_code;
    if (!r2_wbo_close_v1(&p->thread, &s->thread, R2_WBO_OP_CLOSE_THREAD) ||
        !r2_wbo_close_v1(&p->process, &s->process, R2_WBO_OP_CLOSE_PROCESS)) goto residual;
    s->complete = 1;
    r2_wbo_report_v1.stage_running = R2_WBO_NO_STAGE;
    /* The final identity/exit/close sequence is a primary operation too.
     * A stale end point blocks the next stage even with both handles closed. */
    if (!r2_wbo_clock_v1(1, r2_wbo_private_v1.cleanup_mode ? 0 : 1)) return 0;
    if (!code && !r2_wbo_stopped_v1()) r2_wbo_report_v1.stage_next = index + 1u;
    return 1;
residual:
    r2_wbo_report_v1.residual_bits |= R2_WBO_RESIDUAL_ORIGINAL | R2_WBO_RESIDUAL_SAMPLE;
    InterlockedExchange(&r2_wbo_stop_v1, 1);
    return 0;
}

R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_describe_v1(
    struct r2_wbo_abi_v1 *out, size_t size)
{
    const struct r2_wbo_abi_v1 value = {
        R2_WBO_ABI, sizeof(struct r2_wbo_abi_v1), sizeof(struct r2_wbo_spec_v1),
        sizeof(struct r2_wbo_report_v1), sizeof(struct r2_wbo_stage_report_v1),
        sizeof(struct r2_wbo_sample_v1), sizeof(struct r2_wbo_fault_v1),
        sizeof(struct r2_wbo_handle_v1), R2_WBO_STAGES, R2_WBO_FAULTS,
        sizeof(struct r2_wbo_private_v1) + sizeof(struct r2_wbo_report_v1),
        R2_WBO_PRIMARY_STEPS, R2_WBO_CLEANUP_STEPS,
        R2_WBO_PRIMARY_CALLS, R2_WBO_CLEANUP_CALLS, 0,
        R2_WBO_CPU_PRIMARY_STEPS, R2_WBO_CPU_CLEANUP_STEPS,
        R2_WBO_CPU_PRIMARY_CALLS, R2_WBO_CPU_CLEANUP_CALLS
    };
    if (size != sizeof(value) || !r2_wbo_range_v1(out, size, _Alignof(struct r2_wbo_abi_v1)) ||
        r2_wbo_overlap_v1(out, size, &r2_wbo_private_v1, sizeof(r2_wbo_private_v1)) ||
        r2_wbo_overlap_v1(out, size, &r2_wbo_report_v1, sizeof(r2_wbo_report_v1)))
        return R2_WBO_BAD_ARGUMENT;
    memcpy(out, &value, sizeof(value));
    return R2_WBO_OK;
}

R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_begin_once_v1(
    const struct r2_wbo_spec_v1 *spec, size_t size)
{
    LARGE_INTEGER frequency;
    DWORD_PTR allowed, system, first, remaining;
    WORD groups;
    DWORD count;
    DWORD thread_id;
    HANDLE self;
    FILETIME creation, exit_time, kernel_time, user_time;
    uint32_t i;
    uint64_t active_ticks, cleanup_ticks;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    if (!r2_wbo_enter_v1()) return R2_WBO_BUSY;
    if (r->attempt_consumed) return r2_wbo_leave_v1(R2_WBO_BAD_STATE);
    r->attempt_consumed = 1; r->lifecycle = R2_WBO_INITIALIZING;
    if (!r2_wbo_step_v1(0) || r2_wbo_stopped_v1() || !r2_wbo_clock_v1(0, 0))
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r->epoch_qpc = r->last_qpc;
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!QueryPerformanceFrequency(&frequency)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_FREQUENCY, e);
        r->clock_trusted = 0; r->clock_quarantined = 1;
        r->residual_bits |= R2_WBO_RESIDUAL_CLOCK;
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (frequency.QuadPart < 1000 || frequency.QuadPart > INT64_MAX / 1800) {
        r2_wbo_bad_v1(R2_WBO_OP_FREQUENCY, 1);
        r->clock_trusted = 0; r->clock_quarantined = 1;
        r->residual_bits |= R2_WBO_RESIDUAL_CLOCK;
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (size != sizeof(*spec) || !r2_wbo_range_v1(spec, size, _Alignof(struct r2_wbo_spec_v1)) ||
        r2_wbo_overlap_v1(spec, size, &r2_wbo_private_v1, sizeof(r2_wbo_private_v1)) ||
        r2_wbo_overlap_v1(spec, size, &r2_wbo_report_v1, sizeof(r2_wbo_report_v1))) {
        r2_wbo_fault_v1(R2_WBO_OP_BEGIN, R2_WBO_ARGUMENT, 1, 0);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    r->frequency_qpc = frequency.QuadPart;
    if (spec->abi != R2_WBO_ABI || spec->size != size ||
        spec->active_ms < 1 || spec->active_ms > 1740000 ||
        spec->cleanup_ms < 1 || spec->cleanup_ms > 60000 ||
        spec->active_ms > 1800000u - spec->cleanup_ms) {
        r2_wbo_fault_v1(R2_WBO_OP_BEGIN, R2_WBO_ARGUMENT, 2, 0);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    active_ticks = (uint64_t)frequency.QuadPart / 1000u * spec->active_ms +
        ((uint64_t)frequency.QuadPart % 1000u) * spec->active_ms / 1000u;
    cleanup_ticks = (uint64_t)frequency.QuadPart / 1000u * spec->cleanup_ms +
        ((uint64_t)frequency.QuadPart % 1000u) * spec->cleanup_ms / 1000u;
    if (!active_ticks || !cleanup_ticks || active_ticks > INT64_MAX - r->epoch_qpc ||
        cleanup_ticks > INT64_MAX - r->epoch_qpc - active_ticks) {
        r2_wbo_fault_v1(R2_WBO_OP_BEGIN, R2_WBO_ARGUMENT, 3, 0);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    r->active_deadline_qpc = r->epoch_qpc + (int64_t)active_ticks;
    r->cleanup_deadline_qpc = r->active_deadline_qpc + (int64_t)cleanup_ticks;
    for (i = 0; i < R2_WBO_STAGES; ++i) {
        const struct r2_wbo_stage_spec_v1 *stage = &spec->stages[i];
        struct r2_wbo_stage_private_v1 *p = &r2_wbo_private_v1.stages[i];
        if (!r2_wbo_text_v1(p->application, R2_WBO_APP_UNITS, &stage->application, 0, 1) ||
            !r2_wbo_text_v1(p->command, R2_WBO_COMMAND_UNITS, &stage->command, 0, 0) ||
            !r2_wbo_text_v1(p->directory, R2_WBO_DIRECTORY_UNITS, &stage->directory, 0, 1) ||
            !r2_wbo_text_v1(p->environment, R2_WBO_ENVIRONMENT_UNITS, &stage->environment, 1, 0)) {
            r2_wbo_fault_v1(R2_WBO_OP_TEXT, R2_WBO_ARGUMENT, i + 1u, 0);
            return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
        }
    }
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r->creator_id = GetCurrentProcessId();
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r->creator_thread_id = GetCurrentThreadId();
    if (!r->creator_id || !r->creator_thread_id || !r2_wbo_clock_v1(1, 0))
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    self = GetCurrentProcess();
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!DuplicateHandle(self, self, self,
        &r2_wbo_private_v1.creator, 0, FALSE, DUPLICATE_SAME_ACCESS)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CREATOR_DUPLICATE, e);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    r->creator.acquired = 1;
    if (!r2_wbo_creator_v1() || !r2_wbo_clock_v1(1, 0))
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    groups = GetActiveProcessorGroupCount();
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    count = GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
    if (groups != 1 || !count || count > sizeof(DWORD_PTR) * CHAR_BIT) {
        r2_wbo_bad_v1(R2_WBO_OP_GROUPS, 1);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!GetProcessAffinityMask(r2_wbo_private_v1.creator, &allowed, &system)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_AFFINITY, e);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (!allowed || (allowed & ~system)) {
        r2_wbo_bad_v1(R2_WBO_OP_AFFINITY, 1);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    first = allowed & (~allowed + 1u); remaining = allowed ^ first;
    r2_wbo_private_v1.limits.BasicLimitInformation.LimitFlags = R2_WBO_JOB_FLAGS;
    r2_wbo_private_v1.limits.BasicLimitInformation.ActiveProcessLimit = 1;
    r2_wbo_private_v1.limits.BasicLimitInformation.Affinity = first | (remaining & (~remaining + 1u));
    r2_wbo_private_v1.limits.JobMemoryLimit = (SIZE_T)R2_WBO_JOB_COMMIT_BYTES;
    r2_wbo_private_v1.cpu.ControlFlags = R2_WBO_CPU_FLAGS;
    r2_wbo_private_v1.cpu.CpuRate = count <= 2 ? 10000u : 20000u / count;
    if (!r2_wbo_clock_v1(1, 0) || !r2_wbo_call_v1())
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r2_wbo_private_v1.job = CreateJobObjectW(NULL, NULL);
    if (!r2_wbo_private_v1.job) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_JOB_CREATE, e);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    r->job.acquired = 1;
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!SetInformationJobObject(r2_wbo_private_v1.job, JobObjectExtendedLimitInformation,
        &r2_wbo_private_v1.limits, sizeof(r2_wbo_private_v1.limits))) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_JOB_LIMIT, e);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!SetInformationJobObject(r2_wbo_private_v1.job, JobObjectCpuRateControlInformation,
        &r2_wbo_private_v1.cpu, sizeof(r2_wbo_private_v1.cpu))) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_JOB_CPU, e);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    r->job_configured = 1;
    if (!r2_wbo_sample_v1(&r->initial_sample, R2_WBO_NO_STAGE, 0) ||
        !r2_wbo_counts_v1(&r->initial_sample, 0, 0) || !r2_wbo_clock_v1(1, 1))
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r2_wbo_private_v1.cpu_expected_count = count;
    r2_wbo_private_v1.cpu_last_qpc = r->last_qpc;
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r2_wbo_private_v1.cpu_event = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!r2_wbo_private_v1.cpu_event) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CPU_EVENT, e);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    r->cpu_observer_event.acquired = 1;
    if (!r2_wbo_clock_v1(1, 0) || !r2_wbo_call_v1())
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r2_wbo_private_v1.cpu_thread = CreateThread(NULL, 65536u,
        r2_wbo_cpu_thread_v1, NULL, STACK_SIZE_PARAM_IS_A_RESERVATION, &thread_id);
    if (!r2_wbo_private_v1.cpu_thread) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CPU_THREAD, e);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    r->cpu_observer_thread.acquired = r->cpu_observer_started = 1;
    r->cpu_observer_id = thread_id;
    r2_wbo_private_v1.cpu_thread_id = thread_id;
    if (!r2_wbo_clock_v1(1, 0) || !r2_wbo_call_v1())
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (GetThreadId(r2_wbo_private_v1.cpu_thread) != thread_id || !thread_id) {
        r2_wbo_bad_v1(R2_WBO_OP_CPU_THREAD, 1);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!GetThreadTimes(r2_wbo_private_v1.cpu_thread,
        &creation, &exit_time, &kernel_time, &user_time)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CPU_THREAD, e);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    r->cpu_observer_creation_100ns = r2_wbo_filetime_v1(creation);
    if (!r->cpu_observer_creation_100ns || !r2_wbo_clock_v1(1, 0))
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r2_wbo_cpu_sync_v1();
    if (r2_wbo_stopped_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r->lifecycle = R2_WBO_READY;
    return r2_wbo_leave_v1(R2_WBO_OK);
}

R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_start_stage_once_v1(uint32_t index)
{
    SIZE_T attribute_size = 0;
    BOOL result;
    DWORD error;
    int64_t operation_start;
    uint32_t warmup;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    struct r2_wbo_stage_private_v1 *p;
    struct r2_wbo_stage_report_v1 *s;
    if (!r2_wbo_enter_v1()) return R2_WBO_BUSY;
    if (!r->attempt_consumed || index >= R2_WBO_STAGES || index != r->stage_next ||
        r->stage_running != R2_WBO_NO_STAGE || r->lifecycle != R2_WBO_READY ||
        r2_wbo_stopped_v1()) {
        if (r->attempt_consumed && !r2_wbo_stopped_v1()) r2_wbo_bad_v1(R2_WBO_OP_STATE, 2);
        return r2_wbo_leave_v1(R2_WBO_BAD_STATE);
    }
    if (!r2_wbo_step_v1(0) || !r2_wbo_clock_v1(1, 1) || !r2_wbo_creator_v1())
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    operation_start = r->last_qpc;
    for (warmup = 0; warmup < 4u; ++warmup) {
        int cpu = r2_wbo_cpu_gate_v1(0);
        if (cpu == 1) break;
        if (cpu == 0) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
        if (!r2_wbo_call_v1()) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
        Sleep(20);
        if (!r2_wbo_clock_v1(1, 0) || !r2_wbo_fresh_v1(operation_start))
            return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (warmup == 4u) {
        r2_wbo_bad_v1(R2_WBO_OP_SYSTEM_CPU, 10);
        r2_wbo_cpu_terminate_v1(0, 0, NULL);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (!r2_wbo_cpu_gate_v1(1)) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    p = &r2_wbo_private_v1.stages[index];
    s = &r->stages[index];
    if (s->attempted || (index &&
        (!r->stages[0].complete || !r->stages[0].exit_code_valid ||
        r->stages[0].exit_code || !r->stages[0].process.close_succeeded ||
        !r->stages[0].thread.close_succeeded))) {
        r2_wbo_bad_v1(R2_WBO_OP_STATE, 1);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    /* The birth reservation is permanent, including a failed OS call. */
    s->attempted = 1;
    if (!r2_wbo_sample_v1(&s->latest_sample, R2_WBO_NO_STAGE, 0) ||
        !r2_wbo_counts_v1(&s->latest_sample, index, 0) ||
        !r2_wbo_clock_v1(1, 1)) goto failed;
    if (!r2_wbo_call_v1()) goto failed;
    result = InitializeProcThreadAttributeList(NULL, 1, 0, &attribute_size);
    error = result ? 0 : GetLastError();
    if (result || error != ERROR_INSUFFICIENT_BUFFER || !attribute_size ||
        attribute_size > sizeof(r2_wbo_private_v1.attributes.bytes)) {
        if (!result && error != ERROR_INSUFFICIENT_BUFFER)
            r2_wbo_error_v1(R2_WBO_OP_ATTRIBUTE_SIZE, error);
        else r2_wbo_bad_v1(R2_WBO_OP_ATTRIBUTE_SIZE, 1);
        goto failed;
    }
    memset(&r2_wbo_private_v1.startup, 0, sizeof(r2_wbo_private_v1.startup));
    r2_wbo_private_v1.startup.StartupInfo.cb = sizeof(r2_wbo_private_v1.startup);
    r2_wbo_private_v1.startup.lpAttributeList =
        (LPPROC_THREAD_ATTRIBUTE_LIST)r2_wbo_private_v1.attributes.bytes;
    if (!r2_wbo_call_v1()) goto failed;
    if (!InitializeProcThreadAttributeList(r2_wbo_private_v1.startup.lpAttributeList,
        1, 0, &attribute_size)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_ATTRIBUTE_INIT, e); goto failed;
    }
    r2_wbo_private_v1.attribute_live = 1;
    r2_wbo_private_v1.jobs[0] = r2_wbo_private_v1.job;
    if (!r2_wbo_call_v1()) goto failed;
    if (!UpdateProcThreadAttribute(r2_wbo_private_v1.startup.lpAttributeList, 0,
        PROC_THREAD_ATTRIBUTE_JOB_LIST, r2_wbo_private_v1.jobs,
        sizeof(r2_wbo_private_v1.jobs), NULL, NULL)) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_ATTRIBUTE_UPDATE, e); goto failed;
    }
    if (!r2_wbo_clock_v1(1, 1) || !r2_wbo_cpu_gate_v1(1) ||
        r2_wbo_stopped_v1() || !r2_wbo_call_v1()) goto failed;
    result = CreateProcessW(p->application, p->command, NULL, NULL, FALSE,
        R2_WBO_CREATE_FLAGS, p->environment, p->directory,
        &r2_wbo_private_v1.startup.StartupInfo, &r2_wbo_private_v1.pi);
    if (!result) {
        DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_PROCESS_CREATE, e); goto failed;
    }
    /* First instructions after BOOL success adopt BOTH originals. */
    p->process = r2_wbo_private_v1.pi.hProcess;
    p->thread = r2_wbo_private_v1.pi.hThread;
    s->process.acquired = s->thread.acquired = 1;
    InterlockedIncrement(&r2_wbo_private_v1.cpu_birth_generation);
    s->process_id = r2_wbo_private_v1.pi.dwProcessId;
    s->thread_id = r2_wbo_private_v1.pi.dwThreadId;
    s->created = 1;
    r->stage_running = index;
    r->job_empty = 0;
    r2_wbo_private_v1.attribute_live = 0;
    DeleteProcThreadAttributeList(r2_wbo_private_v1.startup.lpAttributeList);
    if (!r2_wbo_clock_v1(1, 0) || !r2_wbo_fresh_v1(operation_start) ||
        !r2_wbo_cpu_gate_v1(1) ||
        !r2_wbo_child_identity_v1(index) ||
        !r2_wbo_sample_v1(&s->birth_sample, index, 1) ||
        !r2_wbo_counts_v1(&s->birth_sample, index + 1u, 1u) ||
        r2_wbo_stopped_v1() || !r2_wbo_clock_v1(1, 1) ||
        !r2_wbo_cpu_gate_v1(1) || !r2_wbo_call_v1()) goto failed;
    {
        DWORD previous = ResumeThread(p->thread);
        if (previous == (DWORD)-1) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_RESUME, e); goto failed;
        }
        if (previous != 1) { r2_wbo_bad_v1(R2_WBO_OP_RESUME, previous); goto failed; }
    }
    s->resumed = 1;
    r->lifecycle = R2_WBO_RUNNING;
    if (!r2_wbo_clock_v1(1, 1) || !r2_wbo_cpu_gate_v1(1)) goto failed;
    return r2_wbo_leave_v1(R2_WBO_OK);
failed:
    if (r2_wbo_private_v1.attribute_live) {
        r2_wbo_private_v1.attribute_live = 0;
        DeleteProcThreadAttributeList(r2_wbo_private_v1.startup.lpAttributeList);
    }
    InterlockedExchange(&r2_wbo_stop_v1, 1);
    return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
}

static int r2_wbo_wait_originals_v1(uint32_t index, int cleanup)
{
    DWORD result;
    struct r2_wbo_stage_private_v1 *p = &r2_wbo_private_v1.stages[index];
    struct r2_wbo_stage_report_v1 *s = &r2_wbo_report_v1.stages[index];
    if (!s->process_signaled) {
        if (!r2_wbo_call_v1()) return 0;
        result = WaitForSingleObject(p->process, r2_wbo_wait_slice_v1());
        if (result == WAIT_FAILED) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_PROCESS_WAIT, e); return 0;
        }
        if (result == WAIT_OBJECT_0) s->process_signaled = 1;
        else if (result != WAIT_TIMEOUT) { r2_wbo_bad_v1(R2_WBO_OP_PROCESS_WAIT, result); return 0; }
    }
    if (!r2_wbo_clock_v1(1, cleanup ? 0 : 1)) return 0;
    if (!s->thread_signaled) {
        if (!r2_wbo_call_v1()) return 0;
        result = WaitForSingleObject(p->thread, 0);
        if (result == WAIT_FAILED) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_THREAD_WAIT, e); return 0;
        }
        if (result == WAIT_OBJECT_0) s->thread_signaled = 1;
        else if (result != WAIT_TIMEOUT) { r2_wbo_bad_v1(R2_WBO_OP_THREAD_WAIT, result); return 0; }
    }
    if (s->process_signaled && !s->thread_signaled) {
        r2_wbo_bad_v1(R2_WBO_OP_THREAD_WAIT, 1); return 0;
    }
    return 1;
}

R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_observe_step_v1(void)
{
    uint32_t index;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    struct r2_wbo_stage_report_v1 *s;
    if (!r2_wbo_enter_v1()) return R2_WBO_BUSY;
    index = r->stage_running;
    if (r->lifecycle != R2_WBO_RUNNING || index >= R2_WBO_STAGES || r2_wbo_stopped_v1()) {
        if (r->attempt_consumed && !r2_wbo_stopped_v1()) r2_wbo_bad_v1(R2_WBO_OP_STATE, 3);
        return r2_wbo_leave_v1(R2_WBO_BAD_STATE);
    }
    if (!r2_wbo_step_v1(0) || !r2_wbo_clock_v1(1, 1) ||
        !r2_wbo_cpu_gate_v1(1) || !r2_wbo_creator_v1())
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    s = &r->stages[index];
    if (!r2_wbo_child_identity_v1(index) || !r2_wbo_wait_originals_v1(index, 0) ||
        !r2_wbo_sample_v1(&s->latest_sample, index, !s->process_signaled) ||
        !r2_wbo_cpu_gate_v1(1))
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    if (!s->process_signaled) {
        if (!r2_wbo_counts_v1(&s->latest_sample, index + 1u, 1u))
            return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
        return r2_wbo_leave_v1(R2_WBO_PENDING);
    }
    if (s->latest_sample.total_processes != index + 1u ||
        s->latest_sample.active_processes > 1u) {
        if (s->latest_sample.total_processes != index + 1u)
            r->residual_bits |= R2_WBO_RESIDUAL_HISTORY;
        r2_wbo_bad_v1(R2_WBO_OP_JOB_ACCOUNT, 3);
        return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    }
    if (s->latest_sample.active_processes == 1u) return r2_wbo_leave_v1(R2_WBO_PENDING);
    if (!r2_wbo_complete_stage_v1(index)) return r2_wbo_leave_v1(R2_WBO_NEEDS_CLEANUP);
    r->lifecycle = R2_WBO_READY;
    return r2_wbo_leave_v1(R2_WBO_STAGE_EXITED);
}

R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_stop_new_v1(void)
{
    InterlockedExchange(&r2_wbo_stop_v1, 1);
    if (!r2_wbo_enter_v1()) return R2_WBO_BUSY;
    return r2_wbo_leave_v1(R2_WBO_OK);
}

/* Only the public owner waits/queries/closes these two original handles.
 * A live observer keeps its Job borrowed until its thread really signals. */
static int r2_wbo_cpu_join_v1(void)
{
    struct r2_wbo_private_v1 *p = &r2_wbo_private_v1;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    FILETIME creation, exit_time, kernel, user;
    DWORD wait, code, id;
    if (p->cpu_thread && !r->cpu_observer_signaled) {
        if (!r2_wbo_clock_v1(1, 0) || !r2_wbo_call_v1()) return 0;
        wait = WaitForSingleObject(p->cpu_thread, r2_wbo_wait_slice_v1());
        if (wait == WAIT_TIMEOUT) return 2;
        if (wait != WAIT_OBJECT_0) {
            DWORD e = wait == WAIT_FAILED ? GetLastError() : 0;
            if (e) r2_wbo_error_v1(R2_WBO_OP_CPU_JOIN, e);
            else r2_wbo_bad_v1(R2_WBO_OP_CPU_JOIN, wait);
            return 0;
        }
        r->cpu_observer_signaled = 1;
        InterlockedExchange(&p->cpu_joined, 1);
    }
    r2_wbo_cpu_sync_v1();
    if (p->cpu_thread && !p->cpu_thread_final_attempted) {
        p->cpu_thread_final_attempted = 1;
        if (!r->cpu_observer_creation_100ns || !r2_wbo_call_v1()) return 0;
        id = GetThreadId(p->cpu_thread);
        if (!id || id != p->cpu_thread_id) {
            r2_wbo_bad_v1(R2_WBO_OP_CPU_THREAD, 2); return 0;
        }
        if (!r2_wbo_call_v1()) return 0;
        if (!GetExitCodeThread(p->cpu_thread, &code)) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CPU_THREAD, e); return 0;
        }
        r->cpu_observer_exit_valid = 1; r->cpu_observer_exit_code = code;
        if (code || !r2_wbo_call_v1()) {
            if (code) r2_wbo_bad_v1(R2_WBO_OP_CPU_THREAD, 3);
            return 0;
        }
        if (!GetThreadTimes(p->cpu_thread, &creation, &exit_time, &kernel, &user)) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CPU_THREAD, e); return 0;
        }
        if (r2_wbo_filetime_v1(creation) != r->cpu_observer_creation_100ns) {
            r2_wbo_bad_v1(R2_WBO_OP_CPU_THREAD, 4); return 0;
        }
        r->cpu_observer_final_kernel_100ns = r2_wbo_filetime_v1(kernel);
        r->cpu_observer_final_user_100ns = r2_wbo_filetime_v1(user);
        p->cpu_thread_final_verified = 1;
    }
    if (p->cpu_thread && !p->cpu_thread_final_verified) return 0;
    if (p->cpu_thread && !r2_wbo_close_v1(&p->cpu_thread,
        &r->cpu_observer_thread, R2_WBO_OP_CPU_CLOSE)) return 0;
    if (p->cpu_event && !r2_wbo_close_v1(&p->cpu_event,
        &r->cpu_observer_event, R2_WBO_OP_CPU_CLOSE)) return 0;
    return 1;
}

R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_finish_step_v1(void)
{
    uint32_t index, expected_total = 0;
    uint32_t i;
    struct r2_wbo_report_v1 *r = &r2_wbo_report_v1;
    InterlockedExchange(&r2_wbo_stop_v1, 1);
    if (!r2_wbo_enter_v1()) return R2_WBO_BUSY;
    if (!r->attempt_consumed) return r2_wbo_leave_v1(R2_WBO_BAD_STATE);
    if (r->lifecycle == R2_WBO_DONE) return r2_wbo_leave_v1(R2_WBO_FINISHED);
    if (r->lifecycle == R2_WBO_RETAINED) return r2_wbo_leave_v1(R2_WBO_RESIDUAL);
    if (!r2_wbo_step_v1(1)) goto residual;
    r->finish_started = 1; r->lifecycle = R2_WBO_STOPPING;
    InterlockedExchange(&r2_wbo_private_v1.cpu_cleanup_mode, 1);
    r2_wbo_cpu_sync_v1();
    if (r2_wbo_private_v1.cpu_event && !r->cpu_event_signal_attempted) {
        r->cpu_event_signal_attempted = 1;
        if (!r2_wbo_call_v1()) goto residual;
        if (!SetEvent(r2_wbo_private_v1.cpu_event)) {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_CPU_EVENT, e);
            /* The observer may remain live, but child termination and known
             * original cleanup still proceed within their existing window. */
        } else {
            r->cpu_event_signal_succeeded = 1;
        }
    }
    /* A termination request is attempted once even if the clock has already
     * failed. It does not imply exit, a join, or any renewed time allowance. */
    index = r->stage_running;
    if (index < R2_WBO_STAGES && r2_wbo_private_v1.job)
        r2_wbo_cpu_terminate_v1(0, 1, NULL);
    r2_wbo_cpu_sync_v1();
    if (index < R2_WBO_STAGES && !r->stages[index].process_signaled &&
        (!r->terminate_job_succeeded ||
         InterlockedCompareExchange(&r2_wbo_private_v1.cpu_job_covered_birth, 0, 0) <
         InterlockedCompareExchange(&r2_wbo_private_v1.cpu_birth_generation, 0, 0)) &&
        !r->stages[index].terminate_attempted &&
        r2_wbo_private_v1.stages[index].process) {
        r->stages[index].terminate_attempted = 1;
        if (!r2_wbo_call_v1()) goto residual;
        if (TerminateProcess(r2_wbo_private_v1.stages[index].process, R2_WBO_STOP_EXIT))
            r->stages[index].terminate_succeeded = 1;
        else {
            DWORD e = GetLastError(); r2_wbo_error_v1(R2_WBO_OP_TERMINATE_PROCESS, e);
            r->residual_bits |= R2_WBO_RESIDUAL_JOIN;
        }
    }
    if (!r2_wbo_clock_v1(1, 0)) goto residual;
    if (index < R2_WBO_STAGES) {
        struct r2_wbo_stage_report_v1 *s = &r->stages[index];
        r->lifecycle = R2_WBO_JOINING;
        if (!r2_wbo_wait_originals_v1(index, 1) ||
            !r2_wbo_sample_v1(&s->latest_sample, index, 0)) goto residual;
        if (!s->process_signaled || !s->thread_signaled ||
            s->latest_sample.active_processes != 0u) {
            if (!s->latest_sample.job_valid) goto residual;
            if (s->latest_sample.total_processes != index + 1u ||
                s->latest_sample.terminated_processes > s->latest_sample.total_processes) {
                r->residual_bits |= R2_WBO_RESIDUAL_HISTORY;
                r2_wbo_bad_v1(R2_WBO_OP_JOB_ACCOUNT, 4);
            }
            return r2_wbo_leave_v1(R2_WBO_PENDING);
        }
        if (!r2_wbo_complete_stage_v1(index)) goto residual;
        return r2_wbo_leave_v1(R2_WBO_PENDING);
    }
    for (i = 0; i < R2_WBO_STAGES; ++i) {
        if (r->stages[i].created) ++expected_total;
        if ((r->stages[i].process.acquired && !r->stages[i].process.close_succeeded) ||
            (r->stages[i].thread.acquired && !r->stages[i].thread.close_succeeded)) goto residual;
    }
    if (r2_wbo_private_v1.job && r->job_configured) {
        if (!r2_wbo_sample_v1(&r->final_sample, R2_WBO_NO_STAGE, 0) ||
            !r2_wbo_cleanup_empty_v1(&r->final_sample, expected_total)) goto residual;
        r->final_sample_valid = 1;
    }
    {
        int joined = r2_wbo_cpu_join_v1();
        if (joined == 2) return r2_wbo_leave_v1(R2_WBO_PENDING);
        if (!joined) goto residual;
    }
    if ((r2_wbo_private_v1.creator && !r2_wbo_creator_v1()) ||
        !r2_wbo_clock_v1(1, 0)) goto residual;
    r->lifecycle = R2_WBO_CLOSING;
    if (!r2_wbo_close_v1(&r2_wbo_private_v1.job, &r->job, R2_WBO_OP_CLOSE_JOB) ||
        !r2_wbo_close_v1(&r2_wbo_private_v1.creator, &r->creator, R2_WBO_OP_CLOSE_CREATOR)) goto residual;
    if (!r2_wbo_clock_v1(1, 0)) goto residual;
    r->final_complete = r->job_configured && !r->residual_bits;
    if (r->residual_bits) {
        r->lifecycle = R2_WBO_RETAINED;
        return r2_wbo_leave_v1(R2_WBO_RESIDUAL);
    }
    r->lifecycle = R2_WBO_DONE;
    return r2_wbo_leave_v1(R2_WBO_FINISHED);
residual:
    if (r2_wbo_private_v1.job || r2_wbo_private_v1.creator ||
        r2_wbo_private_v1.cpu_thread || r2_wbo_private_v1.cpu_event ||
        r2_wbo_private_v1.stages[0].process || r2_wbo_private_v1.stages[0].thread ||
        r2_wbo_private_v1.stages[1].process || r2_wbo_private_v1.stages[1].thread)
        r->residual_bits |= R2_WBO_RESIDUAL_ORIGINAL;
    r->lifecycle = R2_WBO_RETAINED;
    return r2_wbo_leave_v1(R2_WBO_RESIDUAL);
}

R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_copy_report_v1(
    struct r2_wbo_report_v1 *out, size_t size)
{
    if (size != sizeof(*out) || !r2_wbo_range_v1(out, size, _Alignof(struct r2_wbo_report_v1)) ||
        r2_wbo_overlap_v1(out, size, &r2_wbo_private_v1, sizeof(r2_wbo_private_v1)) ||
        r2_wbo_overlap_v1(out, size, &r2_wbo_report_v1, sizeof(r2_wbo_report_v1)))
        return R2_WBO_BAD_ARGUMENT;
    if (!r2_wbo_enter_v1()) return R2_WBO_BUSY;
    r2_wbo_cpu_sync_v1();
    r2_wbo_report_v1.stop_new = (uint32_t)r2_wbo_stopped_v1();
    if (!TryAcquireSRWLockShared(&r2_wbo_cpu_lock_v1)) {
        InterlockedExchange(&r2_wbo_guard_v1, 0);
        return R2_WBO_BUSY;
    }
    r2_wbo_report_v1.system_cpu = r2_wbo_private_v1.cpu_published;
    ReleaseSRWLockShared(&r2_wbo_cpu_lock_v1);
    memcpy(out, &r2_wbo_report_v1, sizeof(*out));
    InterlockedExchange(&r2_wbo_guard_v1, 0);
    return R2_WBO_OK;
}
