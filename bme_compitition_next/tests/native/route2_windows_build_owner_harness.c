/* SOURCE ONLY. Future real Windows x64 C11 harness, one case per process.
 * It links the separate route2_windows_build_owner.c object. It is not an H1
 * entry or an accounting/cleanup issuer. No test is run by adding this file.
 * The outer original owner must own this executable, its CRT/loader closure,
 * stdout, absolute cutoff, resources, writers, process join and all fees.
 */
#if !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0A00 || !defined(_WIN64)
#error "harness requires native Windows x64 and explicit Windows 10 target"
#endif
#include <Windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "../../src/eating_event/route2_candidate_overlap/native/route2_windows_build_owner.h"

#define H_STEPS 400u
#define H_CANARY UINT64_C(0xC4B0C4B0C4B0C4B0)
#define H_DESC_JOINED 0xE1000001u
#define H_DESC_UNJOINED 0xE1000002u
#define H_STOP_EXIT 0xE0000001u
struct h_guarded_report {
    uint64_t before;
    struct r2_wbo_report_v1 report;
    uint64_t after;
};
static struct h_guarded_report h_report;
static struct r2_wbo_spec_v1 h_spec;
static WCHAR h_exe[R2_WBO_APP_UNITS];
static WCHAR h_dir[R2_WBO_DIRECTORY_UNITS];
static WCHAR h_commands[R2_WBO_STAGES][R2_WBO_COMMAND_UNITS];
static const uint16_t h_empty_environment[2] = { 0, 0 };
static int64_t h_child_cutoff;

static int h_copy(void)
{
    h_report.before = h_report.after = H_CANARY;
    return route2_win_build_owner_copy_report_v1(&h_report.report,
        sizeof(h_report.report)) == R2_WBO_OK &&
        h_report.before == H_CANARY && h_report.after == H_CANARY &&
        h_report.report.abi == R2_WBO_ABI &&
        h_report.report.size == sizeof(h_report.report);
}
static int h_abi(void)
{
    struct { uint64_t before; struct r2_wbo_abi_v1 value; uint64_t after; } a;
    if (r2_wbo_system_busy_ge90_v1(0, 0) ||
        r2_wbo_system_busy_ge90_v1(8, 10) ||
        !r2_wbo_system_busy_ge90_v1(9, 10) ||
        r2_wbo_system_busy_ge90_v1(UINT64_MAX - UINT64_MAX / 10u - 1u,
            UINT64_MAX) ||
        !r2_wbo_system_busy_ge90_v1(UINT64_MAX - UINT64_MAX / 10u,
            UINT64_MAX)) return 0;
    memset(&a, 0xA5, sizeof(a));
    if (route2_win_build_owner_describe_v1(NULL, sizeof(a.value)) != R2_WBO_BAD_ARGUMENT ||
        route2_win_build_owner_describe_v1(&a.value, sizeof(a.value) - 1) != R2_WBO_BAD_ARGUMENT ||
        a.before != UINT64_C(0xA5A5A5A5A5A5A5A5) ||
        a.after != UINT64_C(0xA5A5A5A5A5A5A5A5)) return 0;
    if (route2_win_build_owner_describe_v1(&a.value, sizeof(a.value)) != R2_WBO_OK ||
        a.value.abi != R2_WBO_ABI || a.value.stages != 2 ||
        a.value.cpu_primary_steps != R2_WBO_CPU_PRIMARY_STEPS ||
        a.value.cpu_cleanup_steps != R2_WBO_CPU_CLEANUP_STEPS ||
        a.value.cpu_primary_calls != R2_WBO_CPU_PRIMARY_CALLS ||
        a.value.cpu_cleanup_calls != R2_WBO_CPU_CLEANUP_CALLS ||
        a.value.private_bytes > 65536 || a.value.report_size != sizeof(h_report.report) ||
        a.before != UINT64_C(0xA5A5A5A5A5A5A5A5) ||
        a.after != UINT64_C(0xA5A5A5A5A5A5A5A5)) return 0;
    return 1;
}
static int h_paths(void)
{
    DWORD n = GetModuleFileNameW(NULL, h_exe, R2_WBO_APP_UNITS);
    uint32_t i;
    if (n < 4 || n >= R2_WBO_APP_UNITS || n >= R2_WBO_DIRECTORY_UNITS) return 0;
    memcpy(h_dir, h_exe, (n + 1u) * sizeof(WCHAR));
    for (i = n; i; --i) {
        if (h_dir[i - 1] == L'\\' || h_dir[i - 1] == L'/') {
            h_dir[i] = 0;
            return i > 2;
        }
    }
    return 0;
}
static void h_text(struct r2_wbo_text_v1 *out, const WCHAR *p)
{
    out->data = (const uint16_t *)p;
    out->units = (uint32_t)wcslen(p) + 1u;
}
static int h_prepare(const WCHAR *mode)
{
    uint32_t i;
    LARGE_INTEGER before, frequency;
    uint64_t seconds;
    if (!h_paths()) return 0;
    memset(&h_spec, 0, sizeof(h_spec));
    h_spec.abi = R2_WBO_ABI;
    h_spec.size = sizeof(h_spec);
    h_spec.active_ms = !wcscmp(mode, L"deadline") ? 5000u : 30000u;
    h_spec.cleanup_ms = !wcscmp(mode, L"deadline") ? 5000u : 10000u;
    if (!QueryPerformanceCounter(&before) || !QueryPerformanceFrequency(&frequency) ||
        before.QuadPart <= 0 || frequency.QuadPart <= 0 ||
        frequency.QuadPart > INT64_MAX / 1800) return 0;
    seconds = (h_spec.active_ms + h_spec.cleanup_ms) / 1000u;
    if (seconds > (uint64_t)(INT64_MAX - before.QuadPart) / (uint64_t)frequency.QuadPart)
        return 0;
    /* Conservative fixture cutoff precedes the native begin epoch's cleanup
     * deadline. It is no new lease or caller proof for the production owner. */
    h_child_cutoff = before.QuadPart + (int64_t)(seconds * (uint64_t)frequency.QuadPart);
    for (i = 0; i < R2_WBO_STAGES; ++i) {
        uint32_t code = i == 0 && !wcscmp(mode, L"cpu_idle") ? 23u :
            (i == 0 && !wcscmp(mode, L"nonzero") ? 17u :
            (i == 0 && !wcscmp(mode, L"descendant") ? 7u : 0u));
        uint32_t spawn = i == 0 && !wcscmp(mode, L"descendant");
        int n = swprintf_s(h_commands[i], R2_WBO_COMMAND_UNITS,
            L"\"%ls\" --child %u %u %lld", h_exe, code, spawn,
            (long long)h_child_cutoff);
        if (n < 0 || n >= R2_WBO_COMMAND_UNITS) return 0;
        h_text(&h_spec.stages[i].application, h_exe);
        h_text(&h_spec.stages[i].command, h_commands[i]);
        h_text(&h_spec.stages[i].directory, h_dir);
        h_spec.stages[i].environment.data = h_empty_environment;
        h_spec.stages[i].environment.units = 2;
    }
    return 1;
}
static int h_child(unsigned code, unsigned spawn, int64_t cutoff)
{
    if (spawn) {
        STARTUPINFOW startup;
        PROCESS_INFORMATION pi;
        WCHAR command[R2_WBO_COMMAND_UNITS];
        WCHAR empty_env[2] = {0, 0};
        BOOL result;
        DWORD wait = WAIT_TIMEOUT;
        uint32_t i;
        LARGE_INTEGER now;
        if (!h_paths() || swprintf_s(command, R2_WBO_COMMAND_UNITS,
            L"\"%ls\" --child 0 0 %lld", h_exe, (long long)cutoff) < 0) return 90;
        memset(&startup, 0, sizeof(startup));
        memset(&pi, 0, sizeof(pi));
        startup.cb = sizeof(startup);
        /* A quota failure is the specific expected fixture result. Other
         * native failures preserve their actual GetLastError in the exit code
         * and fail the parent assertion. This error is an observed platform
         * behavior, not a generic proof of the exact denying Job. */
        result = CreateProcessW(h_exe, command, NULL, NULL, FALSE,
            CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
            empty_env, h_dir, &startup, &pi);
        if (!result) {
            DWORD error = GetLastError();
            ExitProcess(error ? error : H_DESC_UNJOINED);
        }
        /* Adopt both original PI handles immediately. Any unexpected birth
         * is terminated once, joined within the earlier fixture cutoff, then
         * closed once. A failed join is a distinct failed/residual case. */
        {
            HANDLE process = pi.hProcess, thread = pi.hThread;
            wait = WaitForSingleObject(process, 0);
            if (wait == WAIT_TIMEOUT && !TerminateProcess(process, H_DESC_UNJOINED))
                wait = WaitForSingleObject(process, 0);
            for (i = 0; i < 1600u && wait == WAIT_TIMEOUT; ++i) {
                if (!QueryPerformanceCounter(&now) || now.QuadPart >= cutoff) break;
                wait = WaitForSingleObject(process, 25);
            }
            if (wait == WAIT_OBJECT_0 && WaitForSingleObject(thread, 0) == WAIT_OBJECT_0) {
                BOOL thread_closed = CloseHandle(thread);
                BOOL process_closed = CloseHandle(process);
                ExitProcess(thread_closed && process_closed ? H_DESC_JOINED : H_DESC_UNJOINED);
            }
            /* No success claim: the outer original Job owner must retain the
             * incomplete descendant obligation and fail this fixture case. */
            ExitProcess(H_DESC_UNJOINED);
        }
    }
    if (code == 23u) { Sleep(500); ExitProcess(0); }
    ExitProcess(code);
    return 91;
}
static int h_observe_until_exit(void)
{
    uint32_t i, status;
    for (i = 0; i < H_STEPS; ++i) {
        status = route2_win_build_owner_observe_step_v1();
        if (!h_copy()) return 0;
        if (status == R2_WBO_STAGE_EXITED) return 1;
        if (status != R2_WBO_PENDING) return 0;
    }
    route2_win_build_owner_stop_new_v1();
    return 0;
}
static uint32_t h_finish(void)
{
    uint32_t i, status;
    for (i = 0; i < R2_WBO_CLEANUP_STEPS; ++i) {
        status = route2_win_build_owner_finish_step_v1();
        if (!h_copy()) return 0;
        if (status == R2_WBO_FINISHED || status == R2_WBO_RESIDUAL) return status;
        if (status != R2_WBO_PENDING) return 0;
    }
    return 0;
}
static int h_wait_past_active(void)
{
    LARGE_INTEGER now;
    uint32_t i;
    for (i = 0; i < 600u; ++i) {
        if (!QueryPerformanceCounter(&now)) return 0;
        if (now.QuadPart >= h_report.report.active_deadline_qpc) return 1;
        Sleep(10);
    }
    return 0;
}
int wmain(int argc, WCHAR **argv)
{
    int good = 0, first_exit = 0, cpu_observed = 0, cpu_environment_stop = 0;
    uint32_t finish_status, start_second;
    uint32_t i;
    int64_t original_epoch = 0;
    if (argc == 5 && !wcscmp(argv[1], L"--child")) {
        unsigned code, spawn;
        long long cutoff;
        if (swscanf_s(argv[2], L"%u", &code) != 1 ||
            swscanf_s(argv[3], L"%u", &spawn) != 1 ||
            swscanf_s(argv[4], L"%lld", &cutoff) != 1 ||
            cutoff <= 0 || spawn > 1) return 92;
        return h_child(code, spawn, (int64_t)cutoff);
    }
    if (argc != 2 || (wcscmp(argv[1], L"two") && wcscmp(argv[1], L"nonzero") &&
        wcscmp(argv[1], L"cpu_idle") &&
        wcscmp(argv[1], L"descendant") && wcscmp(argv[1], L"deadline"))) return 93;
    if (!h_abi() || !h_prepare(argv[1]) ||
        route2_win_build_owner_begin_once_v1(&h_spec, sizeof(h_spec)) != R2_WBO_OK ||
        !h_copy() || !h_report.report.epoch_qpc ||
        h_child_cutoff <= h_report.report.epoch_qpc ||
        h_child_cutoff > h_report.report.cleanup_deadline_qpc ||
        route2_win_build_owner_start_stage_once_v1(0) != R2_WBO_OK || !h_copy())
        goto cleanup;
    original_epoch = h_report.report.epoch_qpc;
    if (!wcscmp(argv[1], L"cpu_idle")) {
        uint32_t before_pairs = h_report.report.cpu_pair_count;
        LARGE_INTEGER now, frequency;
        Sleep(150); /* No owner API calls: its private observer must advance. */
        if (!h_copy() || !QueryPerformanceCounter(&now) ||
            !QueryPerformanceFrequency(&frequency) || frequency.QuadPart <= 0)
            goto cleanup;
        cpu_environment_stop = h_report.report.stop_new &&
            h_report.report.cpu_stop_reason == 5u;
        cpu_observed = h_report.report.cpu_pair_count > before_pairs &&
            h_report.report.system_cpu.pair_valid &&
            h_report.report.system_cpu.groups == 1u &&
            h_report.report.system_cpu.processors >= 1u &&
            h_report.report.system_cpu.processors <= 64u &&
            h_report.report.system_cpu.total_delta_100ns > 0u &&
            h_report.report.system_cpu.busy_delta_100ns <=
                h_report.report.system_cpu.total_delta_100ns &&
            h_report.report.system_cpu.end_qpc > h_report.report.epoch_qpc &&
            h_report.report.system_cpu.end_qpc <= now.QuadPart &&
            now.QuadPart - h_report.report.system_cpu.end_qpc <= frequency.QuadPart / 10;
        if (!cpu_environment_stop && !cpu_observed) goto cleanup;
    }
    if (!cpu_environment_stop) first_exit = h_observe_until_exit();
    if (!wcscmp(argv[1], L"cpu_idle") && h_report.report.cpu_stop_reason == 5u)
        cpu_environment_stop = 1;
    if (!wcscmp(argv[1], L"two")) {
        if (!first_exit || !h_report.report.stages[0].complete ||
            !h_report.report.stages[0].process.close_succeeded ||
            !h_report.report.stages[0].thread.close_succeeded ||
            h_report.report.stages[0].exit_code ||
            route2_win_build_owner_start_stage_once_v1(1) != R2_WBO_OK ||
            !h_copy() || !h_observe_until_exit()) goto cleanup;
        good = h_report.report.stages[1].complete &&
            h_report.report.stages[1].exit_code_valid &&
            h_report.report.stages[1].exit_code == 0 &&
            h_report.report.stages[1].latest_sample.total_processes == 2 &&
            h_report.report.epoch_qpc == original_epoch;
    } else if (!wcscmp(argv[1], L"deadline")) {
        if (!first_exit || !h_report.report.stages[0].complete ||
            !h_report.report.stages[0].process.close_succeeded ||
            !h_report.report.stages[0].thread.close_succeeded ||
            h_report.report.fault_count || !h_report.report.clock_trusted ||
            !h_wait_past_active()) goto cleanup;
        start_second = route2_win_build_owner_start_stage_once_v1(1);
        good = (start_second == R2_WBO_NEEDS_CLEANUP ||
            start_second == R2_WBO_BAD_STATE) && h_copy() &&
            h_report.report.stop_new && !h_report.report.stages[1].attempted &&
            h_report.report.clock_trusted && h_report.report.epoch_qpc == original_epoch &&
            h_report.report.primary.operation == R2_WBO_OP_DEADLINE &&
            h_report.report.primary.kind == R2_WBO_INVARIANT &&
            (h_report.report.primary.code == 1u ||
             (h_report.report.primary.code == 7u &&
              h_report.report.cpu_stop_reason == 7u));
    } else if (!wcscmp(argv[1], L"cpu_idle")) {
        /* The caller gap intentionally makes the separate Job point sample
         * stale. CPU observation must still have advanced independently;
         * the ordinary freshness STOP then owns and joins the live child. */
        good = cpu_observed && !first_exit && h_report.report.stop_new &&
            h_report.report.primary.operation == R2_WBO_OP_FRESHNESS &&
            !h_report.report.stages[1].attempted;
    } else if (!wcscmp(argv[1], L"nonzero")) {
        if (!first_exit || !h_report.report.stages[0].created ||
            !h_report.report.stages[0].resumed ||
            !h_report.report.stages[0].process_signaled ||
            !h_report.report.stages[0].thread_signaled ||
            !h_report.report.stages[0].complete ||
            !h_report.report.stages[0].exit_code_valid ||
            h_report.report.stages[0].exit_code != 17u ||
            h_report.report.primary.operation != R2_WBO_OP_EXIT_CODE ||
            h_report.report.primary.kind != R2_WBO_INVARIANT ||
            h_report.report.primary.code != 17u) goto cleanup;
        start_second = route2_win_build_owner_start_stage_once_v1(1);
        good = start_second == R2_WBO_BAD_STATE && h_copy() &&
            h_report.report.stop_new && !h_report.report.stages[1].attempted;
    } else {
        if (!h_copy() || !h_report.report.stages[0].created ||
            !h_report.report.stages[0].resumed) goto cleanup;
        start_second = route2_win_build_owner_start_stage_once_v1(1);
        if (!h_copy() || !h_report.report.stop_new ||
            h_report.report.stages[1].attempted ||
            (start_second != R2_WBO_BAD_STATE && start_second != R2_WBO_NEEDS_CLEANUP))
            goto cleanup;
        /* Final original exit facts may be established during cleanup after a
         * lifetime-count anomaly. The exact quota code is checked below. */
        good = h_report.report.job_configured && h_report.report.stages[0].membership &&
            h_report.report.stages[0].birth_sample.limit_valid &&
            h_report.report.stages[0].birth_sample.active_limit == 1u &&
            h_report.report.stages[0].birth_sample.total_processes == 1u &&
            h_report.report.stages[0].birth_sample.active_processes == 1u;
    }
cleanup:
    finish_status = h_finish();
    if (!h_copy()) good = 0;
    if (!wcscmp(argv[1], L"cpu_idle") &&
        h_report.report.cpu_stop_reason == 5u) cpu_environment_stop = 1;
    if (!h_report.report.cpu_observer_started ||
        !h_report.report.cpu_observer_signaled ||
        !h_report.report.cpu_observer_exit_valid ||
        h_report.report.cpu_observer_exit_code ||
        !h_report.report.cpu_observer_thread.close_succeeded ||
        !h_report.report.cpu_observer_event.close_succeeded) good = 0;
    if (!wcscmp(argv[1], L"descendant")) {
        int exit_fault = 0;
        for (i = 0; i < h_report.report.fault_count && i < R2_WBO_FAULTS; ++i) {
            const struct r2_wbo_fault_v1 *f = &h_report.report.faults[i];
            if (f->operation == R2_WBO_OP_EXIT_CODE && f->kind == R2_WBO_INVARIANT &&
                f->code == ERROR_NOT_ENOUGH_QUOTA) exit_fault = 1;
        }
        good = good && exit_fault && !h_report.report.fault_overflow &&
            h_report.report.stages[0].process_signaled &&
            h_report.report.stages[0].thread_signaled &&
            h_report.report.stages[0].complete &&
            h_report.report.stages[0].exit_code_valid &&
            h_report.report.stages[0].exit_code == ERROR_NOT_ENOUGH_QUOTA &&
            h_report.report.stages[0].process.close_succeeded &&
            h_report.report.stages[0].thread.close_succeeded &&
            h_report.report.job.close_succeeded &&
            h_report.report.creator.close_succeeded &&
            h_report.report.final_sample_valid && h_report.report.job_empty &&
            !h_report.report.stages[1].attempted &&
            !(h_report.report.residual_bits & ~R2_WBO_RESIDUAL_HISTORY) &&
            ((finish_status == R2_WBO_FINISHED &&
              h_report.report.final_complete && !h_report.report.residual_bits &&
              h_report.report.final_sample.total_processes == 1u) ||
             (finish_status == R2_WBO_RESIDUAL &&
              !h_report.report.final_complete &&
              h_report.report.residual_bits == R2_WBO_RESIDUAL_HISTORY &&
              h_report.report.final_sample.total_processes == 2u));
    } else if (finish_status != R2_WBO_FINISHED || !h_report.report.final_complete ||
        h_report.report.residual_bits) good = 0;
    if (good && !wcscmp(argv[1], L"deadline"))
        good = h_report.report.primary.operation == R2_WBO_OP_DEADLINE &&
            h_report.report.clock_trusted && h_report.report.epoch_qpc == original_epoch &&
            !h_report.report.stages[1].attempted;
    if (good && !wcscmp(argv[1], L"nonzero"))
        good = h_report.report.stages[0].exit_code == 17u &&
            h_report.report.primary.operation == R2_WBO_OP_EXIT_CODE &&
            !h_report.report.stages[1].attempted;
    if (h_copy() && !wcscmp(argv[1], L"two"))
        good = good && h_report.report.final_complete &&
            h_report.report.final_sample.total_processes == 2 &&
            h_report.report.stage_next == 2;
    if (cpu_environment_stop) {
        int expected_faults = h_report.report.fault_count > 0u;
        for (i = 0; i < h_report.report.fault_count && i < R2_WBO_FAULTS; ++i) {
            const struct r2_wbo_fault_v1 *f = &h_report.report.faults[i];
            if (!((f->operation == R2_WBO_OP_SYSTEM_CPU &&
                    f->kind == R2_WBO_INVARIANT && f->code == 5u) ||
                  (f->operation == R2_WBO_OP_EXIT_CODE &&
                    f->kind == R2_WBO_INVARIANT && f->code == H_STOP_EXIT)))
                expected_faults = 0;
        }
        int child_closed = h_report.report.stages[0].created ?
            (h_report.report.stages[0].process_signaled &&
             h_report.report.stages[0].thread_signaled &&
             h_report.report.stages[0].complete &&
             h_report.report.stages[0].process.close_succeeded &&
             h_report.report.stages[0].thread.close_succeeded &&
             h_report.report.final_sample.total_processes == 1u) :
            (!h_report.report.stages[0].process.acquired &&
             !h_report.report.stages[0].thread.acquired &&
             h_report.report.final_sample.total_processes == 0u);
        int joined = expected_faults && finish_status == R2_WBO_FINISHED &&
            h_report.report.final_complete && !h_report.report.residual_bits &&
            !h_report.report.fault_overflow && h_report.report.stop_new &&
            h_report.report.primary.operation == R2_WBO_OP_SYSTEM_CPU &&
            h_report.report.primary.kind == R2_WBO_INVARIANT &&
            h_report.report.primary.code == 5u &&
            h_report.report.system_cpu.pair_valid &&
            h_report.report.system_cpu.high &&
            r2_wbo_system_busy_ge90_v1(
                h_report.report.system_cpu.busy_delta_100ns,
                h_report.report.system_cpu.total_delta_100ns) &&
            h_report.report.final_sample_valid && h_report.report.job_empty &&
            h_report.report.final_sample.active_processes == 0u &&
            !h_report.report.stages[1].attempted && child_closed &&
            h_report.report.cpu_observer_signaled &&
            h_report.report.cpu_observer_exit_valid &&
            h_report.report.cpu_observer_exit_code == 0u &&
            h_report.report.cpu_observer_thread.close_succeeded &&
            h_report.report.cpu_observer_event.close_succeeded &&
            h_report.report.job.close_succeeded &&
            h_report.report.creator.close_succeeded &&
            h_report.report.terminate_job_attempted &&
            h_report.report.terminate_job_succeeded;
        printf("build_owner_case=cpu_idle environmental_cpu_stop joined=%u faults=%u residual=%u\n",
            joined, h_report.report.fault_count, h_report.report.residual_bits);
        return joined ? 77 : 1; /* observed host overload is never a pass */
    }
    printf("build_owner_case=%ls assertions=%s status=%u faults=%u residual=%u\n",
        argv[1], good ? "met" : "failed", h_report.report.status,
        h_report.report.fault_count, h_report.report.residual_bits);
    return good ? 0 : 1;
}
