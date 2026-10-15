/* SOURCE_ONLY, NOT COMPILED/RUN. Future admitted Windows native harness.
 * This SINGLE TU includes the companion/unchanged original owner once. Never
 * link route2_mount_helper.c or the companion again. Explicit Win10 x64 C11
 * target flags and the actual SDK/kernel32 are future build requirements.
 * No current DLL/17-export-image compatibility or installed closure is claimed.
 *
 * Future invocation: harness MODE ORIGINAL_EPOCH ORIGINAL_FREQUENCY
 * ORIGINAL_STOP ORIGINAL_CLEANUP (positive signed64 QPC decimal values).
 * The original installation owner must separately admit the entire build,
 * first load, harness/fixture, writable closure and cleanup in its SAME lease.
 * Input clocks alone are unverified raw intent, never that admission.
 * One mode per fresh admitted process; no self-relaunch, reset or retry of an
 * owner attempt. Running several modes needs separately lawful scheduling,
 * not repeated consumption of H1. There is NO runtime invocation in this work.
 *
 * Modes: real, mapping, short, api, multiple, clock, late, regress, identity,
 * race, memory-short, busy, conversion, reservation, cleanup, exited.
 * Fault shims are confined to this harness translation unit. They exercise
 * native successful mappings and failure branches; injected facts are not
 * observations of this machine. Production has no callback/test switch.
 * `conversion` models a foreign consumer discarding a native return; it is
 * not a ctypes test and proves no actual foreign-runtime exception behavior.
 */
#include <Windows.h>
#ifndef PSAPI_VERSION
#define PSAPI_VERSION 2
#endif
#include <psapi.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

enum harness_mode { H_REAL, H_MAPPING, H_SHORT, H_API, H_MULTIPLE, H_CLOCK,
    H_LATE, H_REGRESS, H_IDENTITY, H_RACE, H_MEMORY_SHORT, H_BUSY,
    H_CONVERSION, H_RESERVATION, H_CLEANUP, H_EXITED };
static enum harness_mode h_mode;
static int h_inject, h_cleanup_inject;
static unsigned h_query_calls, h_memory_calls, h_child_memory_calls, h_clock_calls, h_close_calls;
static HANDLE h_child;
static int64_t h_deadline, h_previous;

/* Real calls are defined BEFORE the preprocessor shims to avoid recursion. */
static BOOL WINAPI h_query(HANDLE job, JOBOBJECTINFOCLASS cls, LPVOID out, DWORD size, LPDWORD returned)
{
    BOOL result;
    if (h_inject) ++h_query_calls;
    if (h_inject && cls == JobObjectBasicAndIoAccountingInformation &&
        (h_mode == H_API || h_mode == H_MULTIPLE || h_mode == H_CLEANUP)) {
        SetLastError(ERROR_ACCESS_DENIED); return FALSE;
    }
    result = QueryInformationJobObject(job, cls, out, size, returned);
    if (result && h_inject && cls == JobObjectBasicAndIoAccountingInformation) {
        if (h_mode == H_SHORT) *returned = size - 1;
        if (h_mode == H_MAPPING) {
            JOBOBJECT_BASIC_AND_IO_ACCOUNTING_INFORMATION *a = out;
            a->IoInfo.ReadOperationCount = UINT64_C(0x100000001);
            a->IoInfo.WriteOperationCount = UINT64_C(0x200000002);
            a->IoInfo.OtherOperationCount = UINT64_C(0x300000003);
            a->IoInfo.ReadTransferCount = UINT64_C(0x400000004);
            a->IoInfo.WriteTransferCount = UINT64_C(0x500000005);
            a->IoInfo.OtherTransferCount = UINT64_C(0x600000006);
        }
    }
    return result;
}
static BOOL WINAPI h_memory(HANDLE process, PPROCESS_MEMORY_COUNTERS out, DWORD size)
{
    BOOL result;
    if (h_inject) { ++h_memory_calls; if (process == h_child) ++h_child_memory_calls; }
    if (h_inject && h_mode == H_MULTIPLE) { SetLastError(ERROR_PARTIAL_COPY); return FALSE; }
    result = K32GetProcessMemoryInfo(process, out, size);
    if (result && h_inject) {
        PROCESS_MEMORY_COUNTERS_EX *m = (PROCESS_MEMORY_COUNTERS_EX *)out;
        if (h_mode == H_MEMORY_SHORT) m->cb = size - 1;
        if (h_mode == H_MAPPING) {
            m->PageFaultCount = UINT32_C(0xF0000001);
            m->PeakWorkingSetSize = (SIZE_T)UINT64_C(0x100000001);
            m->WorkingSetSize = (SIZE_T)UINT64_C(0x200000002);
            m->QuotaPeakPagedPoolUsage = (SIZE_T)UINT64_C(0x300000003);
            m->QuotaPagedPoolUsage = (SIZE_T)UINT64_C(0x400000004);
            m->QuotaPeakNonPagedPoolUsage = (SIZE_T)UINT64_C(0x500000005);
            m->QuotaNonPagedPoolUsage = (SIZE_T)UINT64_C(0x600000006);
            m->PagefileUsage = (SIZE_T)UINT64_C(0x700000007);
            m->PeakPagefileUsage = (SIZE_T)UINT64_C(0x800000008);
            m->PrivateUsage = (SIZE_T)UINT64_C(0x900000009);
        }
    }
    return result;
}
static BOOL WINAPI h_qpc(LARGE_INTEGER *out)
{
    if (h_inject) {
        ++h_clock_calls;
        if (h_mode == H_CLOCK) { SetLastError(ERROR_GEN_FAILURE); return FALSE; }
        if (h_mode == H_LATE) { out->QuadPart = h_deadline; return TRUE; }
        if (h_mode == H_REGRESS) { out->QuadPart = h_previous - 1; return TRUE; }
    }
    return QueryPerformanceCounter(out);
}
static BOOL WINAPI h_times(HANDLE process, LPFILETIME creation, LPFILETIME exit_time, LPFILETIME kernel, LPFILETIME user)
{
    BOOL result = GetProcessTimes(process, creation, exit_time, kernel, user);
    if (result && h_inject && h_mode == H_IDENTITY && process == h_child)
        creation->dwLowDateTime ^= 1u;
    return result;
}
static DWORD WINAPI h_wait(HANDLE object, DWORD milliseconds)
{
    if (h_inject && h_mode == H_RACE && object == h_child && h_child_memory_calls)
        return WAIT_OBJECT_0; /* injected race, not actual process exit */
    return WaitForSingleObject(object, milliseconds);
}
static BOOL WINAPI h_terminate_job(HANDLE job, UINT code)
{
    if (h_cleanup_inject) { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
    return TerminateJobObject(job, code);
}
static BOOL WINAPI h_close(HANDLE handle)
{
    if (h_inject) ++h_close_calls;
    return CloseHandle(handle);
}
#define QueryInformationJobObject h_query
#define K32GetProcessMemoryInfo h_memory
#define QueryPerformanceCounter h_qpc
#define GetProcessTimes h_times
#define WaitForSingleObject h_wait
#define TerminateJobObject h_terminate_job
#define CloseHandle h_close
#include "../../src/eating_event/route2_candidate_overlap/native/route2_windows_owned_observation.c"
#undef QueryInformationJobObject
#undef K32GetProcessMemoryInfo
#undef QueryPerformanceCounter
#undef GetProcessTimes
#undef WaitForSingleObject
#undef TerminateJobObject
#undef CloseHandle

static struct r2_obs_report_v1 h_report, h_saved;
static struct r2_win_owned_report_v1 h_owner_report;
static struct r2_win_owned_spec_v1 h_spec;
static WCHAR h_path[R2_WIN_OWNED_TEXT_CAPACITY], h_command[R2_WIN_OWNED_TEXT_CAPACITY];
static WCHAR h_directory[R2_WIN_OWNED_TEXT_CAPACITY];
static const WCHAR h_environment[] = L"R2_OBSERVATION_HARNESS=1\0";

static int h_decimal(const WCHAR *text, int64_t *out)
{
    uint64_t value = 0;
    if (!*text) return 0;
    for (; *text; ++text) {
        uint32_t digit;
        if (*text < L'0' || *text > L'9') return 0;
        digit = (uint32_t)(*text - L'0');
        if (value > ((uint64_t)INT64_MAX - digit) / 10) return 0;
        value = value * 10 + digit;
    }
    if (!value) return 0;
    *out = (int64_t)value; return 1;
}
static int h_fixture(void)
{
    /* Real future fixture: bounded private allocation/touch and NUL device
     * IO; no file output. None of this is executed during SOURCE work. */
    unsigned char *memory = VirtualAlloc(NULL, 1024u * 1024u, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    HANDLE device;
    DWORD written;
    unsigned i;
    if (!memory) return 11;
    for (i = 0; i < 1024u * 1024u; i += 4096u) memory[i] = (unsigned char)i;
    device = CreateFileW(L"NUL", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (device == INVALID_HANDLE_VALUE) { VirtualFree(memory, 0, MEM_RELEASE); return 12; }
    if (!WriteFile(device, memory, 4096, &written, NULL) || written != 4096) {
        CloseHandle(device); VirtualFree(memory, 0, MEM_RELEASE); return 13;
    }
    Sleep(500);
    if (!CloseHandle(device)) { VirtualFree(memory, 0, MEM_RELEASE); return 14; }
    return VirtualFree(memory, 0, MEM_RELEASE) ? 0 : 15;
}
static int h_prepare(WCHAR **argv)
{
    DWORD units;
    size_t i;
    int count;
    h_spec.abi = R2_WIN_OWNED_ABI; h_spec.size = sizeof(h_spec); h_spec.intent_serial = 1;
    if (!h_decimal(argv[2], &h_spec.lease_epoch_qpc) || !h_decimal(argv[3], &h_spec.lease_qpc_frequency) ||
        !h_decimal(argv[4], &h_spec.stop_deadline_qpc) || !h_decimal(argv[5], &h_spec.cleanup_deadline_qpc)) return 0;
    units = GetModuleFileNameW(NULL, h_path, R2_WIN_OWNED_TEXT_CAPACITY);
    if (!units || units >= R2_WIN_OWNED_TEXT_CAPACITY) return 0;
    count = swprintf(h_command, R2_WIN_OWNED_TEXT_CAPACITY, L"\"%ls\" --fixture", h_path);
    if (count < 0 || (unsigned)count >= R2_WIN_OWNED_TEXT_CAPACITY) return 0;
    memcpy(h_directory, h_path, ((size_t)units + 1) * sizeof(WCHAR));
    for (i = units; i && h_directory[i - 1] != L'\\'; --i) {}
    if (i < 3) return 0;
    h_directory[i] = 0;
    h_spec.application = (struct r2_win_owned_text_v1){ (const uint16_t *)h_path, units + 1, 0 };
    h_spec.command_line = (struct r2_win_owned_text_v1){ (const uint16_t *)h_command, (uint32_t)count + 1, 0 };
    h_spec.current_directory = (struct r2_win_owned_text_v1){ (const uint16_t *)h_directory, (uint32_t)i + 1, 0 };
    h_spec.environment = (struct r2_win_owned_text_v1){ (const uint16_t *)h_environment, sizeof(h_environment) / sizeof(WCHAR), 0 };
    return 1;
}
static int h_mapping_ok(const struct r2_obs_process_v1 *p)
{
    return p->identity_valid && p->live_memory_usable && p->memory_cb.value == 80 &&
        p->page_fault_count.value == UINT32_C(0xF0000001) &&
        p->peak_working_set_bytes.value == UINT64_C(0x100000001) && p->working_set_bytes.value == UINT64_C(0x200000002) &&
        p->peak_paged_pool_bytes.value == UINT64_C(0x300000003) && p->paged_pool_bytes.value == UINT64_C(0x400000004) &&
        p->peak_nonpaged_pool_bytes.value == UINT64_C(0x500000005) && p->nonpaged_pool_bytes.value == UINT64_C(0x600000006) &&
        p->pagefile_commit_bytes.value == UINT64_C(0x700000007) && p->peak_pagefile_commit_bytes.value == UINT64_C(0x800000008) &&
        p->private_commit_bytes.value == UINT64_C(0x900000009);
}
#define H_CHECK(condition) do { if (!(condition)) { fwprintf(stderr, L"source harness assertion line %u\n", (unsigned)__LINE__); failed = 1; goto cleanup; } } while (0)
int wmain(int argc, WCHAR **argv)
{
    static const WCHAR *names[] = { L"real", L"mapping", L"short", L"api", L"multiple", L"clock", L"late", L"regress",
        L"identity", L"race", L"memory-short", L"busy", L"conversion", L"reservation", L"cleanup", L"exited" };
    uint32_t result, attempts, finish = R2_OWN_BAD_STATE;
    unsigned i, calls;
    int found = 0, failed = 0, begin_attempted = 0;
    int64_t parsed;
    struct r2_obs_abi_v1 abi;
    if (argc == 2 && !wcscmp(argv[1], L"--fixture")) return h_fixture();
    if (argc != 6) return 2;
    for (i = 0; i < sizeof(names) / sizeof(names[0]); ++i) if (!wcscmp(argv[1], names[i])) { h_mode = (enum harness_mode)i; found = 1; break; }
    if (!found || !h_prepare(argv)) return 2;
    H_CHECK(h_decimal(L"9223372036854775807", &parsed) && parsed == INT64_MAX);
    H_CHECK(!h_decimal(L"9223372036854775808", &parsed) && !h_decimal(L"-1", &parsed) &&
        !h_decimal(L"0", &parsed) && !h_decimal(L"1x", &parsed));
    H_CHECK(route2_win_owned_observation_describe_v1(&abi, sizeof(abi)) == R2_OBS_OK);
    H_CHECK(abi.report_size == sizeof(h_report) && abi.pointer_size == 8 && abi.attempt_capacity == 256 && abi.fault_capacity == 32);
    H_CHECK(route2_win_owned_observation_sample_step_v1() == R2_OBS_BAD_STATE);
    begin_attempted = 1;
    H_CHECK(route2_win_owned_child_begin_once_v1(&h_spec, sizeof(h_spec)) == R2_OWN_OK);
    /* Child absent is UNKNOWN, with a valid original creator sample; it is
     * not fabricated zero resource usage or a complete population sample. */
    H_CHECK(route2_win_owned_observation_sample_step_v1() == R2_OBS_PARTIAL);
    H_CHECK(route2_win_owned_observation_copy_report_v1(&h_report, sizeof(h_report)) == R2_OBS_OK);
    H_CHECK(!h_report.first.child.acquired && h_report.first.child.working_set_bytes.state == R2_WIN_JOB_FIELD_UNKNOWN);
    memcpy(&h_saved, &h_report, sizeof(h_saved));
    H_CHECK(route2_win_owned_child_birth_suspended_once_v1() == R2_OWN_OK);
    h_child = r2_own_v1.process; h_deadline = h_spec.stop_deadline_qpc; h_previous = r2_own_report_v1.last_qpc;
    if (h_mode == H_BUSY) {
        InterlockedExchange(&r2_own_guard_v1, 1);
        result = route2_win_owned_observation_sample_step_v1();
        H_CHECK(result == R2_OBS_BUSY);
        H_CHECK(route2_win_owned_observation_copy_report_v1(&h_report, sizeof(h_report)) == R2_OBS_BUSY);
        InterlockedExchange(&r2_own_guard_v1, 0);
    }
    if (h_mode == H_EXITED) {
        H_CHECK(route2_win_owned_child_resume_once_v1() == R2_OWN_OK);
        for (i = 0; i < 8; ++i) {
            result = route2_win_owned_child_observe_step_v1();
            if (result != R2_OWN_PENDING) break;
        }
        H_CHECK(result == R2_OWN_EXITED);
    }
    h_inject = 1;
    result = route2_win_owned_observation_sample_step_v1();
    H_CHECK(h_close_calls == 0); /* observation never consumes owner slots */
    H_CHECK(route2_win_owned_observation_copy_report_v1(&h_report, sizeof(h_report)) == R2_OBS_OK);
    H_CHECK(h_report.attempts == 2 && h_report.latest.sequence == 2);
    H_CHECK(!memcmp(&h_report.first, &h_saved.first, sizeof(h_report.first)));
    H_CHECK(!r2_own_report_v1.process.consumed && !r2_own_report_v1.job.consumed);
    if (h_mode == H_MAPPING) {
        H_CHECK(result == R2_OBS_OK && h_mapping_ok(&h_report.latest.creator) && h_mapping_ok(&h_report.latest.child));
        H_CHECK(h_report.latest.read_operations.value == UINT64_C(0x100000001) &&
            h_report.latest.write_operations.value == UINT64_C(0x200000002) && h_report.latest.other_operations.value == UINT64_C(0x300000003) &&
            h_report.latest.read_transfer_bytes.value == UINT64_C(0x400000004) && h_report.latest.write_transfer_bytes.value == UINT64_C(0x500000005) &&
            h_report.latest.other_transfer_bytes.value == UINT64_C(0x600000006));
    } else if (h_mode == H_SHORT || h_mode == H_API || h_mode == H_MULTIPLE || h_mode == H_CLEANUP) {
        H_CHECK(result == R2_OBS_FAILED && h_report.faults[R2_OBS_JOB_IO].occurrences == 1 &&
            h_report.latest.read_operations.state == R2_WIN_JOB_FIELD_UNKNOWN);
        H_CHECK(h_report.primary.kind == (h_mode == H_SHORT ? R2_OBS_INVARIANT : R2_OBS_WIN32));
        if (h_mode == H_MULTIPLE) H_CHECK(h_report.faults[R2_OBS_CREATOR_MEMORY].occurrences == 1 && h_report.faults[R2_OBS_CHILD_MEMORY].occurrences == 1);
    } else if (h_mode == H_CLOCK || h_mode == H_LATE || h_mode == H_REGRESS) {
        H_CHECK(result == R2_OBS_FAILED && !h_report.latest.completed_within_deadline && h_query_calls == 0 && h_memory_calls == 0);
        H_CHECK(h_report.faults[R2_OBS_CLOCK].occurrences == 1);
    } else if (h_mode == H_IDENTITY) {
        H_CHECK(result == R2_OBS_FAILED && !h_report.latest.child.identity_valid && !h_child_memory_calls);
        H_CHECK(h_report.faults[R2_OBS_CHILD_TIMES_BEFORE].code == R2_OBS_IDENTITY_CHANGED);
    } else if (h_mode == H_RACE) {
        H_CHECK(result == R2_OBS_PARTIAL && h_report.latest.child.disposition == R2_OBS_EXIT_RACED &&
            h_report.latest.child.memory_state == R2_WIN_JOB_FIELD_VALID && !h_report.latest.child.live_memory_usable &&
            h_report.latest.child.exit_100ns.state == R2_WIN_JOB_FIELD_UNKNOWN);
    } else if (h_mode == H_MEMORY_SHORT) {
        H_CHECK(result == R2_OBS_FAILED && h_report.latest.creator.memory_state == R2_WIN_JOB_FIELD_FAILED &&
            h_report.faults[R2_OBS_CREATOR_MEMORY].code == R2_OBS_LENGTH_CHANGED);
    } else if (h_mode == H_EXITED) {
        H_CHECK(result == R2_OBS_PARTIAL && h_report.latest.child.disposition == R2_OBS_EXITED_BEFORE &&
            h_report.latest.child.working_set_bytes.state == R2_WIN_JOB_FIELD_UNKNOWN && !h_child_memory_calls &&
            h_report.latest.child.exit_100ns.state == R2_WIN_JOB_FIELD_VALID);
    } else H_CHECK(result == R2_OBS_OK && h_report.latest.creator.live_memory_usable && h_report.latest.child.live_memory_usable);
    H_CHECK(r2_own_guard_v1 == 0);
    attempts = h_report.attempts; calls = h_query_calls + h_memory_calls + h_clock_calls;
    if (h_report.fault_count) {
        H_CHECK(route2_win_owned_observation_sample_step_v1() == R2_OBS_FAILED);
        H_CHECK(r2_obs_report_v1.attempts == attempts && calls == h_query_calls + h_memory_calls + h_clock_calls);
        H_CHECK(r2_own_stopped_v1() && (r2_own_report_v1.residual_bits & R2_OWN_RESIDUAL_SAMPLE));
    }
    if (h_mode == H_CONVERSION) {
        /* Foreign-consumer rejection happens AFTER native storage. Discarding
         * the return cannot erase originals/sequence or require re-sampling. */
        memset(&h_report, 0xA5, sizeof(h_report));
        H_CHECK(route2_win_owned_observation_copy_report_v1(&h_report, sizeof(h_report) - 1) == R2_OBS_BAD_ARGUMENT);
        H_CHECK(h_report.abi == UINT32_C(0xA5A5A5A5));
        H_CHECK(route2_win_owned_observation_copy_report_v1(&h_report, sizeof(h_report)) == R2_OBS_OK);
        H_CHECK(h_report.attempts == attempts && calls == h_query_calls + h_memory_calls + h_clock_calls);
    }
    if (h_mode == H_RESERVATION) {
        for (i = attempts; i < R2_OBS_ATTEMPT_CAPACITY; ++i) H_CHECK(route2_win_owned_observation_sample_step_v1() == R2_OBS_OK);
        memcpy(&h_saved.latest, &r2_obs_report_v1.latest, sizeof(h_saved.latest));
        H_CHECK(route2_win_owned_observation_sample_step_v1() == R2_OBS_EXHAUSTED);
        H_CHECK(r2_obs_report_v1.attempts == 256 && !memcmp(&h_saved.latest, &r2_obs_report_v1.latest, sizeof(h_saved.latest)));
        H_CHECK(route2_win_owned_observation_sample_step_v1() == R2_OBS_FAILED);
    }
    /* A second begin cannot renew the supplied clocks or owner attempt. Test
     * only after observation assertions: refusal itself stops original work. */
    H_CHECK(route2_win_owned_child_begin_once_v1(&h_spec, sizeof(h_spec)) == R2_OWN_BAD_STATE);
cleanup:
    h_inject = 0;
    InterlockedExchange(&r2_own_guard_v1, 0); /* harness-held BUSY assertion only */
    h_cleanup_inject = h_mode == H_CLEANUP;
    if (begin_attempted) {
        route2_win_owned_child_stop_new_v1();
        for (i = 0; i < 8; ++i) {
            finish = route2_win_owned_child_finish_step_v1();
            if (finish != R2_OWN_PENDING) break;
        }
        /* No alternate close/reopen/kill. Failed original cleanup/residual
         * remains retained and the original owner owes all unjoined tails. */
        if (route2_win_owned_child_copy_report_v1(&h_owner_report, sizeof(h_owner_report)) != R2_OWN_OK) failed = 1;
        if (h_mode == H_CLEANUP && (!h_owner_report.faults[R2_OWN_OP_TERMINATE_JOB].occurrences ||
            !r2_obs_report_v1.faults[R2_OBS_JOB_IO].occurrences || h_owner_report.terminate_job_state != R2_WIN_JOB_FIELD_FAILED)) failed = 1;
    }
    fwprintf(stdout, L"LOCAL_HARNESS_ONLY assertions=%ls cleanup_status=%u residual=%u full_scope=UNKNOWN_NOT_ZERO\n",
        failed ? L"FAILED" : L"CHECKED", finish, h_owner_report.residual_bits);
    return failed ? 1 : 0; /* never a budget/admission/full-closure verdict */
}
