/* SOURCE ONLY: real C02 integration/ABI harness, never an admission issuer.
 * One mode per process/native image; no mocks, callbacks, DLL loading, reset,
 * GT, project input or explicit file writes. Output is one <=8192-byte stdout
 * record, including a native-memory report hex dump (NOT a transport schema).
 * A record is usable only together with successful harness process exit and
 * the outer owner's original deadline/join checks. A late/failed stdout flush
 * may already have written CASE_ASSERTIONS_MET; nonzero exit invalidates that
 * entire record. fwrite/fflush and CRT shutdown are NOT claimed to be bounded.
 * The future original outer owner must already own the immutable executable,
 * transitive CRT/DLL closure, exact FD set, independent hard deadlines, actual
 * infrastructure costs and original process/Job joins. Parent+serial fixture+
 * outer controller are THREE PREPARATION actors, not the study's two actors.
 * MONITORED4 below covers raw original-parent/child points only; infrastructure
 * and transient thread coverage remain UNKNOWN. Unknown observations stop.
 *
 * Future reviewed build templates, NOT commands executed by this source:
 * REAL_CLANG --no-default-config --target=x86_64-w64-windows-gnu -std=c11
 *   -D_WIN32_WINNT=0x0A00 -DR2_TARGET_WINDOWS_SEED -fintegrated-cc1
 *   -fintegrated-as -I<NATIVE_DIR> -c <production route2_mount_helper.c> -o prod.o
 * Same compile flags: -c <this source> -o harness.o
 * Fixture: same target/C11/Win10/integrated flags, -DR2_OWNED_CHILD_FIXTURE
 *   -c <this source> -o fixture.o (no production object needed in fixture).
 * Ordinary Unicode CRT links: future budgeted REAL_CLANG -### -municode
 *   harness.o prod.o -o harness.exe; separately fixture.o -o fixture.exe.
 * Preserve the exact ordinary CRT/startup/import-library argv from that preview
 * and invoke sealed real ld.lld with --threads=1. Never /NOENTRY, a custom raw
 * entry, an uncharged driver-spawned compiler, or an invented CRT argument set.
 *
 * Parent argv (exactly ten including argv[0]):
 *   MODE SEALED_FIXTURE_ABSOLUTE_PATH SEALED_ABSOLUTE_CWD
 *   ORIGINAL_EPOCH_QPC FREQUENCY ORIGINAL_STOP_QPC ORIGINAL_CLEANUP_QPC
 *   SERIAL ABSOLUTE_CHILD_RELEASE_QPC
 * MODE: invalid-begin | stop-before-birth | suspended-stop | zero |
 *       exit259 | exit-high. Release zero means immediate fixture exit;
 * otherwise original_epoch <= release < original_stop. No now+N lease.
 * Outer owner may invoke modes serially within the SAME original lease/H1;
 * a failed/incomplete case stops that suite, with no retry or fresh credit.
 *
 * On RESIDUAL this harness reports uncertainty and exits nonzero. Its exit
 * closes process handles and may request KILL_ON_JOB_CLOSE; that is NOT a
 * local join/charge/close proof. The outer original owner must stop further
 * modes, contain/join its original group and retain the incomplete obligation.
 * No local indefinite hold or second deadline is manufactured.
 */
#if !defined(_WIN32) || !defined(_WIN64) || !defined(_WIN32_WINNT) || _WIN32_WINNT < 0x0A00
#error "Harness requires explicit native Windows x64/Windows10 target"
#endif
#if !defined(__STDC_VERSION__) || __STDC_VERSION__ < 201112L
#error "Harness requires C11 and ordinary CRT startup"
#endif
#include <Windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <limits.h>

#define HARNESS_STEPS 4096u
static int number(const WCHAR *text, uint64_t maximum, uint64_t *out)
{
    uint64_t value = 0;
    unsigned base = 10, digits = 0;
    if (text[0] == L'0' && (text[1] == L'x' || text[1] == L'X')) { base = 16; text += 2; }
    while (*text) {
        unsigned digit;
        if (*text >= L'0' && *text <= L'9') digit = (unsigned)(*text - L'0');
        else if (*text >= L'a' && *text <= L'f') digit = (unsigned)(*text - L'a') + 10;
        else if (*text >= L'A' && *text <= L'F') digit = (unsigned)(*text - L'A') + 10;
        else return 0;
        if (digit >= base || value > (maximum - digit) / base || ++digits > 20) return 0;
        value = value * base + digit; ++text;
    }
    if (!digits) return 0;
    *out = value; return 1;
}
static int now(int64_t *out)
{
    LARGE_INTEGER value;
    if (!QueryPerformanceCounter(&value) || value.QuadPart <= 0) return 0;
    *out = value.QuadPart; return 1;
}

#if defined(R2_OWNED_CHILD_FIXTURE)
/* Ordinary wmain/CRT fixture: no stdout, files, other processes or threads.
 * Explicit ExitProcess(UINT) preserves all 32 bits, including 259/high-bit
 * values. The real parent must use signaled HANDLE evidence, not STILL_ACTIVE.
 */
int wmain(int argc, WCHAR **argv)
{
    uint64_t code, frequency, release, stop;
    LARGE_INTEGER actual_frequency;
    int64_t ticks;
    unsigned attempts = 0;
    if (argc != 6 || wcscmp(argv[1], L"--fixture") ||
        !number(argv[2], UINT32_MAX, &code) ||
        !number(argv[3], INT64_MAX / 1000, &frequency) || !frequency ||
        !number(argv[4], INT64_MAX, &release) ||
        !number(argv[5], INT64_MAX, &stop) || !stop || (release && release >= stop) ||
        !QueryPerformanceFrequency(&actual_frequency) ||
        actual_frequency.QuadPart != (int64_t)frequency) ExitProcess(0xE0000002u);
    for (;;) {
        uint64_t remaining, milliseconds;
        if (++attempts > HARNESS_STEPS || !now(&ticks) || ticks >= (int64_t)stop)
            ExitProcess(0xE0000002u);
        if (!release || ticks >= (int64_t)release) break;
        remaining = release - (uint64_t)ticks;
        milliseconds = remaining >= frequency ? 1000u : remaining * 1000u / frequency;
        Sleep((DWORD)(milliseconds > 10u ? 10u : milliseconds));
    }
    ExitProcess((UINT)code);
    return 95;
}
#else
#ifndef R2_TARGET_WINDOWS_SEED
#error "Parent must link the actual R2_TARGET_WINDOWS_SEED production object"
#endif
#include "route2_mount_helper.h"

_Static_assert(sizeof(void *) == 8 && sizeof(WCHAR) == 2, "Win64 UTF16");
_Static_assert(sizeof(struct r2_win_owned_spec_v1) == 112 &&
    sizeof(struct r2_win_owned_report_v1) == 2736 &&
    sizeof(struct r2_win_owned_abi_v1) == 48, "frozen production ABI");
enum mode { INVALID_BEGIN, STOP_BEFORE, SUSPENDED_STOP, ZERO_EXIT, EXIT_259, EXIT_HIGH };
static const WCHAR *mode_w[] = {L"invalid-begin", L"stop-before-birth", L"suspended-stop", L"zero", L"exit259", L"exit-high"};
static const char *mode_a[] = {"invalid-begin", "stop-before-birth", "suspended-stop", "zero", "exit259", "exit-high"};
struct guarded_report { uint64_t pre[2]; struct r2_win_owned_report_v1 value; uint64_t post[2]; };
struct guarded_abi { uint64_t pre[2]; struct r2_win_owned_abi_v1 value; uint64_t post[2]; };
static struct guarded_report report;
static struct r2_win_owned_report_v1 saved;
static struct r2_win_owned_spec_v1 spec;
static WCHAR command[R2_WIN_OWNED_TEXT_CAPACITY];
static const uint16_t empty_environment[2] = {0, 0};
static char output[8192];
/* Independent original caller timing, also present when native begin refuses
 * or a pre-begin ABI check fails. Never derive it from a native report. */
static struct {
    int initialized, failed;
    int64_t epoch, cleanup, last_qpc;
} output_clock;
static int output_clock_valid(void)
{
    int64_t ticks;
    if (!output_clock.initialized || output_clock.failed || !now(&ticks) ||
        ticks < output_clock.epoch || ticks < output_clock.last_qpc || ticks >= output_clock.cleanup) {
        output_clock.failed = 1;
        return 0;
    }
    output_clock.last_qpc = ticks;
    return 1;
}
#define CANARY UINT64_C(0xA5A5A5A5A5A5A5A5)
static int pattern(const void *p, size_t length)
{
    const unsigned char *bytes = p;
    size_t i;
    for (i = 0; i < length; ++i) if (bytes[i] != 0xA5) return 0;
    return 1;
}
static int copy_report(void)
{
    report.pre[0] = report.pre[1] = report.post[0] = report.post[1] = CANARY;
    return route2_win_owned_child_copy_report_v1(&report.value, sizeof(report.value)) == R2_OWN_OK &&
        report.pre[0] == CANARY && report.pre[1] == CANARY && report.post[0] == CANARY && report.post[1] == CANARY &&
        report.value.abi == 1 && report.value.size == sizeof(report.value);
}
static int abi_checks(void)
{
    struct guarded_abi a;
    memset(&a, 0xA5, sizeof(a)); memset(&report, 0xA5, sizeof(report));
    if (route2_win_owned_child_describe_v1(NULL, sizeof(a.value)) != R2_OWN_BAD_ARGUMENT ||
        route2_win_owned_child_describe_v1(&a.value, sizeof(a.value) - 1) != R2_OWN_BAD_ARGUMENT ||
        !pattern(&a, sizeof(a)) ||
        route2_win_owned_child_copy_report_v1(NULL, sizeof(report.value)) != R2_OWN_BAD_ARGUMENT ||
        route2_win_owned_child_copy_report_v1(&report.value, sizeof(report.value) - 1) != R2_OWN_BAD_ARGUMENT ||
        !pattern(&report, sizeof(report))) return 0;
    if (route2_win_owned_child_describe_v1(&a.value, sizeof(a.value)) != R2_OWN_OK ||
        a.pre[0] != CANARY || a.pre[1] != CANARY || a.post[0] != CANARY || a.post[1] != CANARY ||
        a.value.abi != 1 || a.value.size != sizeof(a.value) || a.value.spec_size != sizeof(spec) ||
        a.value.report_size != sizeof(report.value) || a.value.pointer_size != 8 ||
        a.value.text_size != sizeof(struct r2_win_owned_text_v1) ||
        a.value.fault_size != sizeof(struct r2_win_owned_fault_v1) ||
        a.value.handle_state_size != sizeof(struct r2_win_owned_handle_state_v1) ||
        a.value.snapshot_size != sizeof(struct r2_win_job_raw_snapshot_v1) ||
        a.value.report_faults_offset != offsetof(struct r2_win_owned_report_v1, faults) ||
        a.value.report_configured_offset != offsetof(struct r2_win_owned_report_v1, configured) || a.value.reserved ||
        !copy_report() || report.value.attempt_consumed || report.value.lifecycle != R2_OWN_UNUSED) return 0;
    return 1;
}
static int append_text(WCHAR *out, size_t *used, const WCHAR *text)
{
    while (*text) { if (*used + 1 >= R2_WIN_OWNED_TEXT_CAPACITY) return 0; out[(*used)++] = *text++; }
    out[*used] = 0; return 1;
}
static int append_number(WCHAR *out, size_t *used, uint64_t value)
{
    WCHAR reverse[21]; size_t n = 0;
    do { reverse[n++] = (WCHAR)(L'0' + value % 10); value /= 10; } while (value);
    while (n) { if (*used + 1 >= R2_WIN_OWNED_TEXT_CAPACITY) return 0; out[(*used)++] = reverse[--n]; }
    out[*used] = 0; return 1;
}
static int absolute_text(const WCHAR *text, uint32_t *units)
{
    size_t n = 0;
    while (text[n]) { if (text[n] == L'"' || ++n >= R2_WIN_OWNED_TEXT_CAPACITY) return 0; }
    if (n < 3 || !((text[0] >= L'A' && text[0] <= L'Z') || (text[0] >= L'a' && text[0] <= L'z')) ||
        text[1] != L':' || text[2] != L'\\') return 0;
    *units = (uint32_t)n + 1; return 1;
}
static int lease_matches(void)
{
    return report.value.lease_epoch_qpc == spec.lease_epoch_qpc &&
        report.value.qpc_frequency == spec.lease_qpc_frequency &&
        report.value.stop_deadline_qpc == spec.stop_deadline_qpc &&
        report.value.cleanup_deadline_qpc == spec.cleanup_deadline_qpc &&
        report.value.intent_serial == spec.intent_serial;
}
static int closed(struct r2_win_owned_handle_state_v1 h)
{
    return h.acquired == 1 && h.consumed == 1 && h.close_state == R2_WIN_JOB_FIELD_VALID;
}
static int completed_child(void)
{
    struct r2_win_owned_report_v1 *r = &report.value;
    return r->lifecycle == R2_OWN_DONE && r->final_complete && !r->residual_bits && r->clock_valid &&
        r->process_signaled && r->thread_signaled && r->job_empty && r->membership == 1 &&
        r->configured_valid && r->latest_valid && r->final_valid && lease_matches() &&
        closed(r->creator) && closed(r->job) && closed(r->process) && closed(r->thread) && closed(r->snapshot) &&
        r->creator_creation_100ns.state == 1 && r->child_creation_100ns.state == 1 && r->primary_creation_100ns.state == 1 &&
        r->final_exit_code.state == 1 && r->final_exit_100ns.state == 1 &&
        r->final_kernel_100ns.state == 1 && r->final_user_100ns.state == 1 &&
        r->final_thread_kernel_100ns.state == 1 && r->final_thread_user_100ns.state == 1 &&
        r->final_sample.limits_readback_state == 1 && r->final_sample.cpu_readback_state == 1 && r->final_sample.accounting_state == 1 &&
        r->final_sample.total_processes.state == 1 && r->final_sample.total_processes.value == 1 &&
        r->final_sample.active_processes.state == 1 && r->final_sample.active_processes.value == 0 &&
        r->final_sample.terminated_by_limits.state == 1 && r->final_sample.terminated_by_limits.value == 0 &&
        r->final_sample.total_user_100ns.state == 1 && r->final_sample.total_kernel_100ns.state == 1 &&
        r->final_sample.peak_job_commit.state == 1 && r->final_sample.peak_process_commit.state == 1 &&
        r->thread_transient_coverage == 0 && r->complete_birth_history == 0;
}
static int finish_native(void)
{
    unsigned steps;
    route2_win_owned_child_stop_new_v1();
    for (steps = 0; steps < HARNESS_STEPS; ++steps) {
        uint32_t status = route2_win_owned_child_finish_step_v1();
        if (status == R2_OWN_PENDING) continue;
        return status == R2_OWN_FINISHED && copy_report();
    }
    return 0; /* Outer owner retains the incomplete containment obligation. */
}
static int once_checks(void)
{
    saved = report.value;
    if (route2_win_owned_child_finish_step_v1() != R2_OWN_FINISHED || !copy_report() ||
        memcmp(&saved, &report.value, sizeof(saved))) return 0;
    if (route2_win_owned_child_begin_once_v1(&spec, sizeof(spec)) != R2_OWN_BAD_STATE || !copy_report()) return 0;
    saved.status = R2_OWN_BAD_STATE;
    return memcmp(&saved, &report.value, sizeof(saved)) == 0;
}
static int emit(enum mode m, int verdict, int clean)
{
    static const char hex[] = "0123456789abcdef";
    const unsigned char *bytes = (const unsigned char *)&report.value;
    const char *prefix = clean ? (verdict ? "CASE_ASSERTIONS_MET" : "CASE_ASSERTIONS_FAILED") : "RESIDUAL_OUTER_OWNER_REQUIRED";
    size_t used = 0, i;
    const char *part;
    if (!output_clock_valid()) return 94;
    part = prefix; while (*part) output[used++] = *part++;
    output[used++] = ' '; part = mode_a[m]; while (*part) output[used++] = *part++;
    part = " application_admission=NOT_ISSUED native_report_hex="; while (*part) output[used++] = *part++;
    for (i = 0; i < sizeof(report.value); ++i) {
        if (used + 3 >= sizeof(output)) return 94;
        output[used++] = hex[bytes[i] >> 4]; output[used++] = hex[bytes[i] & 15];
    }
    output[used++] = '\n';
    if (!output_clock_valid()) return 94;
    if (fwrite(output, 1, used, stdout) != used || fflush(stdout) != 0) return 94;
    /* No second record/retry after failure: even an already emitted MET line
     * is invalid unless this original-clock check and process exit succeed. */
    if (!output_clock_valid()) return 94;
    return !clean ? 93 : verdict ? 0 : 92;
}
int wmain(int argc, WCHAR **argv)
{
    uint64_t values[6], expected_code;
    uint32_t app_units, cwd_units, status;
    LARGE_INTEGER frequency;
    int64_t ticks;
    size_t used = 0;
    unsigned i, steps;
    enum mode m;
    int good = 1, clean = 0, began = 0, live_threads = 0;
    struct r2_win_owned_fault_v1 original_primary;
    if (argc != 10) return 90;
    for (i = 0; i < 6 && wcscmp(argv[1], mode_w[i]); ++i) {}
    if (i == 6) return 90;
    m = (enum mode)i;
    for (i = 0; i < 6; ++i) if (!number(argv[4 + i], i == 4 ? UINT64_MAX : INT64_MAX, &values[i])) return 90;
    if (!values[0] || !values[1] || values[1] > INT64_MAX / 1000 ||
        !(values[0] < values[2] && values[2] < values[3]) ||
        (values[5] && (values[5] < values[0] || values[5] >= values[2])) ||
        !absolute_text(argv[2], &app_units) || !absolute_text(argv[3], &cwd_units) ||
        !QueryPerformanceFrequency(&frequency) || frequency.QuadPart != (int64_t)values[1] ||
        !now(&ticks) || ticks < (int64_t)values[0] || ticks >= (int64_t)values[2]) return 90;
    output_clock.epoch = (int64_t)values[0];
    output_clock.cleanup = (int64_t)values[3];
    output_clock.last_qpc = ticks;
    output_clock.initialized = 1;
    if (!abi_checks()) return emit(m, 0, 1);
    expected_code = m == EXIT_259 ? 259u : m == EXIT_HIGH ? UINT32_C(0x80000001) : 0;
    if (!append_text(command, &used, L"\"") || !append_text(command, &used, argv[2]) ||
        !append_text(command, &used, L"\" --fixture ") || !append_number(command, &used, expected_code) ||
        !append_text(command, &used, L" ") || !append_number(command, &used, values[1]) ||
        !append_text(command, &used, L" ") || !append_number(command, &used, values[5]) ||
        !append_text(command, &used, L" ") || !append_number(command, &used, values[2]) || used + 1 > 32767) return 90;
    spec.abi = 1; spec.size = sizeof(spec); spec.lease_epoch_qpc = (int64_t)values[0];
    spec.lease_qpc_frequency = (int64_t)values[1]; spec.stop_deadline_qpc = (int64_t)values[2];
    spec.cleanup_deadline_qpc = (int64_t)values[3]; spec.intent_serial = values[4];
    spec.application = (struct r2_win_owned_text_v1){(const uint16_t *)argv[2], app_units, 0};
    spec.command_line = (struct r2_win_owned_text_v1){(const uint16_t *)command, (uint32_t)used + 1, 0};
    spec.current_directory = (struct r2_win_owned_text_v1){(const uint16_t *)argv[3], cwd_units, 0};
    spec.environment = (struct r2_win_owned_text_v1){empty_environment, 2, 0};
    began = 1;
    if (m == INVALID_BEGIN) {
        good = route2_win_owned_child_begin_once_v1(NULL, 0) == R2_OWN_NEEDS_CLEANUP && copy_report();
        original_primary = report.value.primary;
        good = good && report.value.attempt_consumed && original_primary.operation == R2_OWN_OP_ARGUMENT;
        if (route2_win_owned_child_begin_once_v1(&spec, sizeof(spec)) != R2_OWN_BAD_STATE || !copy_report() ||
            memcmp(&original_primary, &report.value.primary, sizeof(original_primary))) good = 0;
        goto cleanup;
    }
    if (route2_win_owned_child_begin_once_v1(&spec, sizeof(spec)) != R2_OWN_OK || !copy_report() || !lease_matches()) { good = 0; goto cleanup; }
    if (m == STOP_BEFORE) {
        if (route2_win_owned_child_stop_new_v1() != R2_OWN_OK ||
            route2_win_owned_child_birth_suspended_once_v1() != R2_OWN_NEEDS_CLEANUP) good = 0;
        goto cleanup;
    }
    if (route2_win_owned_child_birth_suspended_once_v1() != R2_OWN_OK || !copy_report()) { good = 0; goto cleanup; }
    live_threads = report.value.thread_scan_state == 1 && report.value.thread_live_at_both_polls &&
        report.value.parent_threads && report.value.child_threads && report.value.parent_threads + report.value.child_threads <= 4;
    if (!live_threads) { good = 0; goto cleanup; }
    if (m == SUSPENDED_STOP) {
        expected_code = UINT32_C(0xE0000001);
        if (route2_win_owned_child_stop_new_v1() != R2_OWN_OK ||
            route2_win_owned_child_resume_once_v1() != R2_OWN_NEEDS_CLEANUP) good = 0;
        goto cleanup;
    }
    if (route2_win_owned_child_resume_once_v1() != R2_OWN_OK) { good = 0; goto cleanup; }
    for (steps = 0; steps < HARNESS_STEPS; ++steps) {
        status = route2_win_owned_child_observe_step_v1();
        if (!copy_report()) { good = 0; break; }
        if (status == R2_OWN_PENDING) {
            if (report.value.thread_scan_state != 1 || !report.value.thread_live_at_both_polls ||
                report.value.parent_threads + report.value.child_threads > 4) { good = 0; break; }
            continue;
        }
        if (!(report.value.process_signaled && (status == R2_OWN_EXITED || status == R2_OWN_NEEDS_CLEANUP))) good = 0;
        break;
    }
    if (steps == HARNESS_STEPS) good = 0;
cleanup:
    if (began) clean = finish_native();
    if (!clean) { copy_report(); return emit(m, 0, 0); }
    if (m == INVALID_BEGIN) {
        good = good && report.value.lifecycle == R2_OWN_DONE && report.value.attempt_consumed &&
            !report.value.creator.acquired && !report.value.job.acquired && !report.value.process.acquired && !report.value.thread.acquired &&
            report.value.primary.operation == R2_OWN_OP_ARGUMENT && report.value.fault_count == 2;
    } else if (m == STOP_BEFORE) {
        good = good && lease_matches() && report.value.lifecycle == R2_OWN_DONE && report.value.final_complete &&
            !report.value.residual_bits && !report.value.fault_count && closed(report.value.creator) &&
            !report.value.birth_attempted && !report.value.job.acquired && !report.value.process.acquired && !report.value.thread.acquired;
    } else {
        good = good && live_threads && completed_child() && report.value.final_exit_code.value == (uint32_t)expected_code;
        if (expected_code) good = good && report.value.fault_count == 1 &&
            report.value.primary.operation == R2_OWN_OP_EXIT_CODE && report.value.primary.code == (uint32_t)expected_code &&
            report.value.faults[R2_OWN_OP_EXIT_CODE].occurrences >= 1;
        else good = good && report.value.fault_count == 0;
        if (m == SUSPENDED_STOP && report.value.resume_attempted) good = 0;
    }
    if (!once_checks()) good = 0;
    return emit(m, good, 1); /* Harness assertion result, NEVER application PASS. */
}
#endif
