#ifndef ROUTE2_WINDOWS_BUILD_OWNER_H
#define ROUTE2_WINDOWS_BUILD_OWNER_H
/* Raw native owner for at most two sequential Windows build processes.
 * SOURCE ONLY: no installed entry, H1 grant, complete resource meter, writer
 * boundary, independent watchdog, provider drain, or admission claim.
 * Caller memory must remain accessible, stable and exclusive during each call.
 * No caller-supplied handle, PID, epoch, or assertion is accepted as authority.
 */
#include <stddef.h>
#include <stdint.h>

#define R2_WBO_ABI 1u
#define R2_WBO_STAGES 2u
#define R2_WBO_FAULTS 64u
#define R2_WBO_APP_UNITS 1024u
#define R2_WBO_COMMAND_UNITS 2048u
#define R2_WBO_DIRECTORY_UNITS 1024u
#define R2_WBO_ENVIRONMENT_UNITS 4096u
#define R2_WBO_ATTRIBUTE_BYTES 4096u
#define R2_WBO_PRIMARY_STEPS 40000u
#define R2_WBO_CLEANUP_STEPS 2000u
#define R2_WBO_CALLS_PER_STEP 48u
#define R2_WBO_PRIMARY_CALLS (R2_WBO_PRIMARY_STEPS * R2_WBO_CALLS_PER_STEP + 256u)
#define R2_WBO_CLEANUP_CALLS (R2_WBO_CLEANUP_STEPS * R2_WBO_CALLS_PER_STEP)
#define R2_WBO_JOB_COMMIT_BYTES UINT64_C(4294967296)
#define R2_WBO_EXPORT __declspec(dllexport)

/* FINISHED reports bounded cleanup of the known original process/thread,
 * Job and creator handles. A workload can exit nonzero or leave faults and
 * STOP_NEW set while cleanup still returns FINISHED. Check the report's
 * primary/faults/stop_new/residual_bits separately. This raw status proves
 * neither complete Job history, provider drain, H1 nor admission PASS. */
enum r2_wbo_status_v1 {
    R2_WBO_OK = 1, R2_WBO_PENDING, R2_WBO_STAGE_EXITED,
    R2_WBO_NEEDS_CLEANUP, R2_WBO_FINISHED, R2_WBO_RESIDUAL,
    R2_WBO_BAD_ARGUMENT, R2_WBO_BAD_STATE, R2_WBO_BUSY
};
enum r2_wbo_lifecycle_v1 {
    R2_WBO_UNUSED = 0, R2_WBO_INITIALIZING, R2_WBO_READY,
    R2_WBO_RUNNING, R2_WBO_STOPPING, R2_WBO_JOINING,
    R2_WBO_CLOSING, R2_WBO_DONE, R2_WBO_RETAINED
};
enum r2_wbo_fault_kind_v1 { R2_WBO_ARGUMENT = 1, R2_WBO_WIN32, R2_WBO_INVARIANT };
enum r2_wbo_operation_v1 {
    R2_WBO_OP_BEGIN = 1, R2_WBO_OP_CLOCK, R2_WBO_OP_FREQUENCY,
    R2_WBO_OP_TEXT, R2_WBO_OP_CREATOR_DUPLICATE, R2_WBO_OP_CREATOR_ID,
    R2_WBO_OP_CREATOR_TIME, R2_WBO_OP_GROUPS, R2_WBO_OP_AFFINITY,
    R2_WBO_OP_JOB_CREATE, R2_WBO_OP_JOB_LIMIT, R2_WBO_OP_JOB_CPU,
    R2_WBO_OP_JOB_ACCOUNT, R2_WBO_OP_JOB_QUERY_LIMIT,
    R2_WBO_OP_JOB_QUERY_CPU, R2_WBO_OP_ATTRIBUTE_SIZE,
    R2_WBO_OP_ATTRIBUTE_INIT, R2_WBO_OP_ATTRIBUTE_UPDATE,
    R2_WBO_OP_PROCESS_CREATE, R2_WBO_OP_PROCESS_ID,
    R2_WBO_OP_THREAD_ID, R2_WBO_OP_PROCESS_TIME,
    R2_WBO_OP_THREAD_TIME, R2_WBO_OP_MEMBERSHIP,
    R2_WBO_OP_PROCESS_MEMORY, R2_WBO_OP_RESUME,
    R2_WBO_OP_PROCESS_WAIT, R2_WBO_OP_THREAD_WAIT,
    R2_WBO_OP_EXIT_CODE, R2_WBO_OP_TERMINATE_JOB,
    R2_WBO_OP_TERMINATE_PROCESS, R2_WBO_OP_CLOSE_THREAD,
    R2_WBO_OP_CLOSE_PROCESS, R2_WBO_OP_CLOSE_JOB,
    R2_WBO_OP_CLOSE_CREATOR, R2_WBO_OP_STATE,
    R2_WBO_OP_WORK_LIMIT, R2_WBO_OP_FRESHNESS,
    R2_WBO_OP_DEADLINE
};
enum r2_wbo_residual_v1 {
    R2_WBO_RESIDUAL_CLOCK = 1u, R2_WBO_RESIDUAL_DEADLINE = 2u,
    R2_WBO_RESIDUAL_JOIN = 4u, R2_WBO_RESIDUAL_SAMPLE = 8u,
    R2_WBO_RESIDUAL_CLOSE = 16u, R2_WBO_RESIDUAL_ORIGINAL = 32u,
    R2_WBO_RESIDUAL_HISTORY = 64u
};

struct r2_wbo_text_v1 { const uint16_t *data; uint32_t units, reserved; };
struct r2_wbo_stage_spec_v1 {
    struct r2_wbo_text_v1 application, command, directory, environment;
};
struct r2_wbo_spec_v1 {
    uint32_t abi, size, active_ms, cleanup_ms;
    struct r2_wbo_stage_spec_v1 stages[R2_WBO_STAGES];
};
struct r2_wbo_fault_v1 {
    uint32_t operation, kind, code, win32_error, occurrences, phase;
};
struct r2_wbo_handle_v1 {
    uint32_t acquired, close_attempted, close_succeeded, reserved;
};
/* Raw fields are meaningful only when the matching valid flag is set.
 * Job commit is committed virtual memory, not complete causal physical RAM.
 * Point process memory/time samples and Job process counts are not a complete
 * birth/thread history or MONITORED4 certification. */
struct r2_wbo_sample_v1 {
    int64_t start_qpc, end_qpc;
    uint32_t job_valid, limit_valid, cpu_valid, process_valid;
    uint32_t total_processes, active_processes, terminated_processes, page_faults;
    uint32_t limit_flags, active_limit, cpu_flags, cpu_rate;
    uint64_t peak_job_commit, peak_process_commit;
    uint64_t job_user_100ns, job_kernel_100ns;
    uint64_t process_working_set, process_private_commit;
    uint64_t process_user_100ns, process_kernel_100ns;
};
struct r2_wbo_stage_report_v1 {
    uint32_t attempted, created, resumed, process_signaled;
    uint32_t thread_signaled, exit_code_valid, exit_code, complete;
    uint32_t process_id, thread_id, membership, reserved;
    uint32_t terminate_attempted, terminate_succeeded;
    uint64_t process_creation_100ns, thread_creation_100ns;
    uint64_t final_process_user_100ns, final_process_kernel_100ns;
    uint64_t final_thread_user_100ns, final_thread_kernel_100ns;
    struct r2_wbo_handle_v1 process, thread;
    struct r2_wbo_sample_v1 birth_sample, latest_sample;
};
struct r2_wbo_report_v1 {
    uint32_t abi, size, status, lifecycle;
    uint32_t attempt_consumed, stop_new, finish_started, fault_count;
    uint32_t clock_trusted, residual_bits, stage_next, stage_running;
    uint32_t primary_steps, cleanup_steps, primary_calls, cleanup_calls;
    uint32_t creator_id, creator_thread_id, job_configured, job_empty;
    uint32_t terminate_job_attempted, terminate_job_succeeded;
    /* final_complete=1 concerns known-original cleanup only, even with a
     * failed workload/faults/STOP_NEW. HISTORY returns RESIDUAL and leaves it
     * zero; neither value certifies whole history, provider drain or H1. */
    uint32_t final_sample_valid, final_complete, fault_overflow, clock_quarantined;
    int64_t epoch_qpc, frequency_qpc, active_deadline_qpc;
    int64_t cleanup_deadline_qpc, last_qpc, last_sample_qpc;
    uint64_t creator_creation_100ns;
    struct r2_wbo_handle_v1 creator, job;
    struct r2_wbo_fault_v1 primary;
    struct r2_wbo_fault_v1 faults[R2_WBO_FAULTS];
    struct r2_wbo_sample_v1 initial_sample, final_sample;
    struct r2_wbo_stage_report_v1 stages[R2_WBO_STAGES];
};
struct r2_wbo_abi_v1 {
    uint32_t abi, size, spec_size, report_size;
    uint32_t stage_size, sample_size, fault_size, handle_size;
    uint32_t stages, faults, private_bytes, primary_steps;
    uint32_t cleanup_steps, primary_calls, cleanup_calls, reserved;
};

R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_describe_v1(
    struct r2_wbo_abi_v1 *out, size_t size);
R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_begin_once_v1(
    const struct r2_wbo_spec_v1 *spec, size_t size);
R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_start_stage_once_v1(uint32_t index);
R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_observe_step_v1(void);
R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_stop_new_v1(void);
R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_finish_step_v1(void);
R2_WBO_EXPORT uint32_t __cdecl route2_win_build_owner_copy_report_v1(
    struct r2_wbo_report_v1 *out, size_t size);
#endif
