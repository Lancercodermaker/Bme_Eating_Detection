/* Route 2 native interfaces: SOURCE_ONLY; v2 producers NOT_IMPLEMENTED.
 * Records and declarations issue no approval, ownership, or scope proof.
 * Installed runtime is UNKNOWN; costs are UNKNOWN_NOT_ZERO.
 */
#ifndef ROUTE2_MOUNT_HELPER_H
#define ROUTE2_MOUNT_HELPER_H

/* Exactly one explicit target; no compatibility default or OS fallback. */
#if (defined(R2_TARGET_WINDOWS_SEED) + defined(R2_TARGET_LINUX_START) + defined(R2_TARGET_MOUNT_LIBRARY)) != 1
#error "Select exactly one Route 2 native target"
#endif
#if defined(R2_TARGET_WINDOWS_SEED)
#if !defined(_WIN32) || defined(__linux__)
#error "R2_TARGET_WINDOWS_SEED requires Windows"
#endif
#else
#if !defined(__linux__) || defined(_WIN32)
#error "Route 2 Linux targets require Linux"
#endif
#endif

#include <stddef.h>
#include <stdint.h>
#if defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_MOUNT_LIBRARY)
#include <linux/mount.h>
#define ROUTE2_EXPORT __attribute__((visibility("default")))
#else
/* Windows raw component uses ordinary native declarations; loader UNKNOWN. */
#define ROUTE2_EXPORT
#endif

struct route2_mount_abi_v1 {
    uint32_t version;
    uint32_t glibc_major;
    uint32_t glibc_minor;
    uint32_t pointer_bytes;
    uint32_t long_bytes;
    uint32_t mount_attr_bytes;
    uint32_t attr_set_offset;
    uint32_t attr_clr_offset;
    uint32_t propagation_offset;
    uint32_t userns_fd_offset;
};
#if defined(R2_TARGET_MOUNT_LIBRARY)
ROUTE2_EXPORT int route2_mount_helper_describe_v1(struct route2_mount_abi_v1 *out, size_t size);
ROUTE2_EXPORT int route2_open_tree(int dfd, const char *path, unsigned int flags);
ROUTE2_EXPORT int route2_mount_setattr(int dfd, const char *path, unsigned int flags,
                                      const struct mount_attr *attr, size_t size);
ROUTE2_EXPORT int route2_move_mount(int from_dfd, const char *from_path,
                                   int to_dfd, const char *to_path, unsigned int flags);
ROUTE2_EXPORT int route2_umount2(const char *path, int flags);
#endif

/* SOURCE_ONLY scope names; C02-B1 emits only named UNPROVEN refusals.
 * R2_SCOPE_PROVEN is a contract value, never evidence of support.
 */
enum r2_scope_result {
    R2_SCOPE_PROVEN = 0,
    R2_VM_SERVICE_SCOPE_UNPROVEN = 1,
    R2_E_PHYSICAL_CAP_UNPROVEN = 2,
    R2_OWNER_EXIT_JOIN_UNPROVEN = 3
};

struct r2_native_error_v2 {
    uint32_t operation;
    int32_t native_error;
    uint64_t object_serial;
    int64_t descriptor;
};

struct r2_birth_v2 {
    uint32_t abi, size;
    uint64_t original_monotonic_ns, original_available_bytes;
    uint64_t external_qpc_ticks, qpc_frequency;
    uint64_t stop_deadline_ns, cleanup_deadline_ns;
    int32_t pid, pidfd, start_memfd, transport_fd;
};

struct r2_verity_spec_v2 {
    uint32_t abi, size, data_block_bytes, hash_block_bytes;
    uint64_t data_blocks, hash_start_block, generation;
    int32_t data_fd, tree_fd, target_dir_fd;
    uint8_t root_sha256[32], salt[32];
};

struct r2_verity_result_v2 {
    uint32_t abi, size, error_count, reserved;
    uint64_t object_serial, data_loop_number, tree_loop_number;
    uint64_t dm_device, mount_id;
    int32_t data_loop_fd, tree_loop_fd, dm_block_fd, dm_control_fd;
    struct r2_native_error_v2 errors[32];
};

/* NOT_IMPLEMENTED / SOURCE_ONLY future interfaces, not executable stubs.
 * No seed, start, verity publisher/remover, authority factory, registry,
 * original error producer, or consumption/cleanup continuity is supplied.
 */
int route2_native_seed_main_v2(void);
int route2_native_linux_start_main_v2(void);
int route2_verity_publish_v2(const struct r2_verity_spec_v2 *spec,
                            struct r2_verity_result_v2 *result);
int route2_verity_remove_v2(struct r2_verity_result_v2 *result,
                           uint64_t original_cleanup_deadline_ns);


#if defined(R2_TARGET_WINDOWS_SEED)
/* C02-B1 raw component IMPLEMENTED_BUT_UNCOMPILED / SOURCE_ONLY.
 * These statuses are NOT r2_scope_result and never admit an application.
 * Exact native size/ABI only; this memory record is not a transport schema.
 */
enum r2_win_raw_status {
    R2_WIN_RAW_UNKNOWN = 0,
    R2_WIN_RAW_SAMPLE_COMPLETE = 1,
    R2_WIN_RAW_BAD_ARGUMENT = 2,
    R2_WIN_RAW_API_FAILED = 3,
    R2_WIN_RAW_INVARIANT_FAILED = 4,
    R2_WIN_RAW_EXIT_RACED = 5
};

enum r2_win_raw_field_state {
    R2_WIN_RAW_FIELD_UNKNOWN = 0,
    R2_WIN_RAW_FIELD_VALID = 1,
    R2_WIN_RAW_FIELD_FAILED = 2
};

enum r2_win_raw_sample_kind {
    R2_WIN_RAW_SAMPLE_UNKNOWN = 0,
    R2_WIN_RAW_LIVE_AT_BOTH_POLLS = 1,
    R2_WIN_RAW_EXITED_BEFORE_FIRST_POLL = 2,
    R2_WIN_RAW_EXITED_BETWEEN_POLLS = 3
};

enum r2_win_raw_operation {
    R2_WIN_RAW_OP_ARGUMENT = 1,
    R2_WIN_RAW_OP_QPC_FREQUENCY = 2,
    R2_WIN_RAW_OP_QPC_BEGIN = 3,
    R2_WIN_RAW_OP_BORROWED_PID = 4,
    R2_WIN_RAW_OP_DUPLICATE = 5,
    R2_WIN_RAW_OP_DUPLICATE_PID = 6,
    R2_WIN_RAW_OP_WAIT_BEFORE = 7,
    R2_WIN_RAW_OP_TIMES_BEFORE = 8,
    R2_WIN_RAW_OP_WAIT_AFTER = 9,
    R2_WIN_RAW_OP_TIMES_AFTER = 10,
    R2_WIN_RAW_OP_EXIT_CODE = 11,
    R2_WIN_RAW_OP_CLOSE = 12,
    R2_WIN_RAW_OP_QPC_END = 13
};

enum r2_win_raw_fault_kind {
    R2_WIN_RAW_FAULT_ARGUMENT = 1,
    R2_WIN_RAW_FAULT_WIN32 = 2,
    R2_WIN_RAW_FAULT_INVARIANT = 3
};

enum r2_win_raw_invariant {
    R2_WIN_RAW_NULL_PROCESS = 1,
    R2_WIN_RAW_INVALID_OR_CURRENT_PSEUDO = 2,
    R2_WIN_RAW_FREQUENCY_NONPOSITIVE = 3,
    R2_WIN_RAW_PID_CHANGED = 4,
    R2_WIN_RAW_WAIT_UNEXPECTED = 5,
    R2_WIN_RAW_SIGNAL_REGRESSED = 6,
    R2_WIN_RAW_CREATION_CHANGED = 7,
    R2_WIN_RAW_QPC_REGRESSED = 8
};

struct r2_win_raw_u32_v1 { uint32_t value, state; };
struct r2_win_raw_u64_v1 { uint64_t value; uint32_t state; };
struct r2_win_raw_i64_v1 { int64_t value; uint32_t state; };

struct r2_win_raw_fault_v1 {
    uint32_t operation, kind, code;
    uint32_t win32_error, win32_error_valid; /* all DWORD bits, even zero */
};

#define R2_WIN_RAW_FAULT_CAPACITY 3
struct r2_win_raw_process_observation_v1 {
    uint32_t abi, size, status, sample_kind;
    uint32_t duplicate_state, close_state, fault_count;
    struct r2_win_raw_fault_v1 faults[R2_WIN_RAW_FAULT_CAPACITY];
    struct r2_win_raw_u32_v1 borrowed_pid, duplicate_pid;
    struct r2_win_raw_u32_v1 wait_before, wait_after, exit_code;
    struct r2_win_raw_u64_v1 creation_before_100ns, creation_after_100ns;
    struct r2_win_raw_u64_v1 kernel_cpu_before_100ns, user_cpu_before_100ns;
    struct r2_win_raw_u64_v1 kernel_cpu_after_100ns, user_cpu_after_100ns;
    struct r2_win_raw_u64_v1 exit_filetime_100ns;
    struct r2_win_raw_i64_v1 qpc_frequency, qpc_begin, qpc_end;
};

/* Caller supplies a REAL borrowed process HANDLE value via uintptr_t, with
 * QUERY_INFORMATION or QUERY_LIMITED_INFORMATION and SYNCHRONIZE rights.
 * Keep original open/stable through duplication; own/exclusively retain out
 * through return. Neither input nor these facts certify creator membership.
 * NULL/INVALID_HANDLE_VALUE/current-process pseudo input is BAD_ARGUMENT.
 * Other unsupported pseudo/object input is GetProcessId raw failure.
 * out must be non-NULL and size exactly sizeof(*out); bad out returns
 * BAD_ARGUMENT without writing. Successful duplicate is privately owned
 * only through this call and receives one close attempt on every later path.
 * A close failure is FAILED, never retried or hidden. Caller is never closed.
 * FIELD_VALID means the API produced this raw fact, not scope acceptance.
 * Timeout describes that poll only. A racing exit is incomplete/STOP_NEW.
 * Live exit FILETIME/exit code remain UNKNOWN. Signaled code 259 is retained.
 * Process CPU covers all its threads only; do not add thread CPU again.
 * FILETIME 100ns and signed64 QPC ticks/frequency remain separate units.
 * Window includes private once-close, excludes earlier frequency/startup.
 * No original join/once-close history, final fees, whole liveness/hard limit,
 * epoch/M0, durable handoff, admission or native-controller proof is returned.
 */
enum r2_win_raw_status route2_win_raw_process_observe_v1(
    uintptr_t borrowed_process,
    struct r2_win_raw_process_observation_v1 *out, size_t size);

/* Actual named refusal bodies; none can return R2_SCOPE_PROVEN. */
enum r2_scope_result route2_win_refuse_vm_service_scope_v1(void);
enum r2_scope_result route2_win_refuse_e_physical_cap_v1(void);
enum r2_scope_result route2_win_refuse_owner_exit_join_v1(void);
#endif

#if defined(R2_TARGET_WINDOWS_SEED)
/* C02-A COMPONENT_SOURCE_IMPLEMENTED_UNCOMPILED: independent raw Job ABI.
 * This is neither r2_scope_result nor authenticated transport/approval.
 */
enum r2_win_job_raw_status {
    R2_WIN_JOB_RAW_UNKNOWN = 0, R2_WIN_JOB_RAW_OK = 1,
    R2_WIN_JOB_RAW_BAD_ARGUMENT = 2, R2_WIN_JOB_RAW_BAD_STATE = 3,
    R2_WIN_JOB_RAW_API_FAILED = 4, R2_WIN_JOB_RAW_INVARIANT_FAILED = 5,
    R2_WIN_JOB_RAW_EXIT_RACED = 6, R2_WIN_JOB_RAW_BUSY = 7
};
enum r2_win_job_raw_state {
    R2_WIN_JOB_NEW = 0, R2_WIN_JOB_ORIGINAL_HELD = 1,
    R2_WIN_JOB_LIMITS_READBACK = 2, R2_WIN_JOB_PROCESS_ASSIGNED = 3,
    R2_WIN_JOB_POISONED = 4, R2_WIN_JOB_HANDLES_CONSUMED = 5
};
enum r2_win_job_raw_field_state {
    R2_WIN_JOB_FIELD_UNKNOWN = 0, R2_WIN_JOB_FIELD_VALID = 1,
    R2_WIN_JOB_FIELD_FAILED = 2
};
enum r2_win_job_raw_fault_kind {
    R2_WIN_JOB_FAULT_ARGUMENT = 1, R2_WIN_JOB_FAULT_WIN32 = 2,
    R2_WIN_JOB_FAULT_INVARIANT = 3, R2_WIN_JOB_FAULT_API_NO_ERROR = 4
};
enum r2_win_job_raw_operation {
    R2_WIN_JOB_OP_STATE = 1, R2_WIN_JOB_OP_CREATE = 2,
    R2_WIN_JOB_OP_GROUPS = 3, R2_WIN_JOB_OP_COUNT = 4,
    R2_WIN_JOB_OP_AFFINITY = 5, R2_WIN_JOB_OP_SET_LIMITS = 6,
    R2_WIN_JOB_OP_SET_CPU = 7, R2_WIN_JOB_OP_QUERY_LIMITS = 8,
    R2_WIN_JOB_OP_QUERY_CPU = 9, R2_WIN_JOB_OP_QUERY_ACCOUNTING = 10,
    R2_WIN_JOB_OP_BORROWED_PID = 11, R2_WIN_JOB_OP_SELF_PID = 12,
    R2_WIN_JOB_OP_DUPLICATE = 13, R2_WIN_JOB_OP_PID_BEFORE = 14,
    R2_WIN_JOB_OP_WAIT_BEFORE = 15, R2_WIN_JOB_OP_TIMES_BEFORE = 16,
    R2_WIN_JOB_OP_ASSIGN = 17, R2_WIN_JOB_OP_MEMBERSHIP = 18,
    R2_WIN_JOB_OP_PID_AFTER = 19, R2_WIN_JOB_OP_TIMES_AFTER = 20,
    R2_WIN_JOB_OP_WAIT_AFTER = 21, R2_WIN_JOB_OP_CLOSE_PROCESS = 22,
    R2_WIN_JOB_OP_CLOSE_JOB = 23
};
enum r2_win_job_raw_invariant {
    R2_WIN_JOB_BAD_LIFECYCLE = 1, R2_WIN_JOB_NULL_OR_PSEUDO = 2,
    R2_WIN_JOB_SELF_PROCESS = 3, R2_WIN_JOB_BAD_TOPOLOGY = 4,
    R2_WIN_JOB_BAD_LENGTH = 5, R2_WIN_JOB_LIMITS_CHANGED = 6,
    R2_WIN_JOB_CPU_CHANGED = 7, R2_WIN_JOB_PID_CHANGED = 8,
    R2_WIN_JOB_CREATION_CHANGED = 9, R2_WIN_JOB_EXIT_OBSERVED = 10,
    R2_WIN_JOB_BAD_WAIT = 11, R2_WIN_JOB_MEMBERSHIP_ABSENT = 12,
    R2_WIN_JOB_NEGATIVE_ACCOUNTING = 13
};
struct r2_win_job_raw_u32_v1 { uint32_t value, state; };
struct r2_win_job_raw_u64_v1 { uint64_t value; uint32_t state, reserved; };
struct r2_win_job_raw_i64_v1 { int64_t value; uint32_t state, reserved; };
struct r2_win_job_raw_fault_v1 {
    uint32_t operation, kind, code, win32_error, win32_error_valid;
};
struct r2_win_job_raw_snapshot_v1 {
    uint32_t limits_readback_state, cpu_readback_state, accounting_state, reserved;
    struct r2_win_job_raw_u32_v1 limit_flags, active_process_limit;
    struct r2_win_job_raw_u64_v1 affinity, job_commit_limit, process_commit_limit;
    struct r2_win_job_raw_u64_v1 peak_process_commit, peak_job_commit;
    struct r2_win_job_raw_u32_v1 cpu_control_flags, cpu_rate;
    struct r2_win_job_raw_i64_v1 total_user_100ns, total_kernel_100ns;
    struct r2_win_job_raw_i64_v1 period_user_100ns, period_kernel_100ns;
    struct r2_win_job_raw_u32_v1 page_faults, total_processes;
    struct r2_win_job_raw_u32_v1 active_processes, terminated_by_limits;
};
#define R2_WIN_JOB_RAW_FAULT_CAPACITY 3
struct r2_win_job_raw_report_v1 {
    uint32_t abi, size, status, lifecycle;
    uint32_t poisoned, fault_count, assignment_attempted, cleanup_attempted;
    uint32_t job_acquire_state, duplicate_acquire_state;
    uint32_t job_consumed, duplicate_consumed, job_close_state, duplicate_close_state;
    uint32_t set_limits_state, set_cpu_state, assign_state, reserved;
    struct r2_win_job_raw_fault_v1 faults[R2_WIN_JOB_RAW_FAULT_CAPACITY];
    struct r2_win_job_raw_u32_v1 processor_groups, processor_count;
    struct r2_win_job_raw_u64_v1 allowed_affinity, system_affinity, selected_affinity;
    struct r2_win_job_raw_u32_v1 borrowed_pid, current_pid, duplicate_pid_before;
    struct r2_win_job_raw_u32_v1 duplicate_pid_after, wait_before, wait_after, membership;
    struct r2_win_job_raw_u64_v1 creation_before_100ns, creation_after_100ns;
    struct r2_win_job_raw_snapshot_v1 configured, latest_query;
};

/* One native capsule per loaded component. C11 atomic_flag serializes all
 * calls; concurrent/reentrant calls return BUSY without capsule access.
 * No recreate/reset; first primary fault is sticky, then only copy/cleanup.
 * One existing real process association, not atomic prebirth or run approval.
 * Borrowed stays open/stable until successful private SAME_ACCESS duplicate.
 * Needs SET_QUOTA|TERMINATE, QUERY_INFORMATION or LIMITED_INFORMATION, and
 * SYNCHRONIZE. NULL/INVALID/current pseudo and real self process are refused;
 * other pseudo/nonprocess input fails GetProcessId before duplication.
 * Private original Job/duplicate never cross a Python/HANDLE conversion.
 * close consumes both before either one-time attempt, retaining both errors.
 * Failed duplicate output never owned; borrowed/container never closed.
 * KILL last-close requests termination, supplies no observed exit or join.
 * copy requires exclusively writable valid native out of exact sizeof;
 * NULL/size mismatch returns BAD_ARGUMENT without modifying private history.
 * A successful copy returns OK even when copied report records a fault.
 * UNKNOWN/FAILED values are unusable; VALID is a raw native fact only.
 * configured preserves create readback; latest_query is replaced per query
 * attempt (unqueried fields UNKNOWN); no complete query/membership history.
 * Commit is not RSS/whole RAM/VM; four processes not TIDs; interval CPU cap
 * is not instantaneous wallclock, nested CPU quota can be stricter.
 * No scope PASS, MONITORED4, full fees, budget, authority or durable join.
 */
enum r2_win_job_raw_status route2_win_raw_job_capsule_create_fixed_v1(void);
enum r2_win_job_raw_status route2_win_raw_job_capsule_assign_borrowed_v1(uintptr_t);
enum r2_win_job_raw_status route2_win_raw_job_capsule_query_v1(void);
enum r2_win_job_raw_status route2_win_raw_job_capsule_close_once_v1(void);
enum r2_win_job_raw_status route2_win_raw_job_capsule_copy_report_v1(
    struct r2_win_job_raw_report_v1 *out, size_t size);
#endif
#endif

/* C03 independent byte parser: SOURCE_ONLY / IMPLEMENTED_BUT_UNCOMPILED.
 * A parsed value proves no original M0, prebirth, ownership or admission.
 */
#if defined(R2_TARGET_LINUX_START)
#ifndef R2_LINUX_MEMAVAILABLE_PARSE_V1_DECLARED
#define R2_LINUX_MEMAVAILABLE_PARSE_V1_DECLARED
#define R2_LINUX_MEMINFO_INPUT_MAX_BYTES 16384u
#define R2_LINUX_MEMINFO_LINE_MAX_BYTES 512u
#define R2_LINUX_MEMINFO_KEY_MAX_BYTES 64u
#define R2_LINUX_MEMINFO_DECIMAL_MAX_BYTES 20u

enum r2_linux_memavailable_parse_status_v1 {
    R2_LINUX_MEMINFO_PARSED = 0,
    R2_LINUX_MEMINFO_BAD_ARGUMENT = 1,
    R2_LINUX_MEMINFO_INPUT_TOO_LARGE = 2,
    R2_LINUX_MEMINFO_INVALID_BYTE = 3,
    R2_LINUX_MEMINFO_LINE_TOO_LONG = 4,
    R2_LINUX_MEMINFO_TRUNCATED = 5,
    R2_LINUX_MEMINFO_MALFORMED_LINE = 6,
    R2_LINUX_MEMINFO_MISSING_MEMAVAILABLE = 7,
    R2_LINUX_MEMINFO_DUPLICATE_MEMAVAILABLE = 8,
    R2_LINUX_MEMINFO_VALUE_OUT_OF_RANGE = 9
};

/* Exact native memory layout only: not a wire frame or capture receipt. */
struct r2_linux_memavailable_parse_v1 {
    uint32_t abi, size, status, value_valid;
    uint64_t memavailable_kib, memavailable_bytes;
};

/* Caller owns accessible input and an exclusively writable output object.
 * NULL/wrong-size/unaligned/wrapped output, wrapped nonempty input ranges and
 * input/output overlap return BAD_ARGUMENT without output writes. With an
 * accepted output, NULL/empty input and every parsing failure write abi=1,
 * size=32, failure status, validity=0 and both numeric fields=0.
 * Complete LF-terminated input only: 1..16384 bytes; each line <=512 bytes
 * including LF. KEY is [A-Za-z][A-Za-z0-9_()]* (<=64 bytes), then ':',
 * one or more ASCII spaces/HT, then 1..20 digits. The suffix grammar is
 * DECIMAL [ HSPACE+ "kB" ] HSPACE* LF, where HSPACE is space or HT.
 * Brackets make the whole unit group optional; a present unit requires
 * at least one separating space/HT. Other keys may omit the unit;
 * MemAvailable requires exact 'kB'. Blank lines, CR/NUL/non-ASCII, signs and extra tokens
 * reject. Exactly one case-sensitive MemAvailable is required. Decimal and
 * KiB*1024 must fit uint64. Leading zeros and a raw zero value are allowed.
 * Range preconditions precede writes; parsing detects errors as it consumes
 * bytes from left to right. A second target key rejects at its colon.
 * No I/O, allocation, globals, once claim, errno access or authority output.
 */
uint32_t route2_linux_parse_memavailable_v1(
    const uint8_t *bytes, size_t length,
    struct r2_linux_memavailable_parse_v1 *out, size_t out_size);
#endif
#endif

/* C03 real raw Linux capture: SOURCE_IMPLEMENTED / UNCOMPILED.
 * The preceding parser, C02 components and dormant v2 declarations are intact.
 */
#if defined(R2_TARGET_LINUX_START)
#ifndef R2_LINUX_START_CAPTURE_V1_DECLARED
#define R2_LINUX_START_CAPTURE_V1_DECLARED
#define R2_LINUX_CAPTURE_PRIMARY_ATTEMPT_MAX 64u
#define R2_LINUX_CAPTURE_END_CLOCK_ATTEMPT_MAX 4u

enum r2_linux_start_capture_status_v1 {
    R2_LINUX_CAPTURE_UNKNOWN = 0,
    R2_LINUX_CAPTURE_COMPLETE = 1,
    R2_LINUX_CAPTURE_BAD_ARGUMENT = 2,
    R2_LINUX_CAPTURE_ALREADY_ATTEMPTED = 3,
    R2_LINUX_CAPTURE_API_FAILED = 4,
    R2_LINUX_CAPTURE_INVARIANT_FAILED = 5,
    R2_LINUX_CAPTURE_ATTEMPTS_EXHAUSTED = 6,
    R2_LINUX_CAPTURE_INPUT_TOO_LARGE = 7,
    R2_LINUX_CAPTURE_PARSE_FAILED = 8,
    R2_LINUX_CAPTURE_CLEANUP_FAILED = 9
};
enum r2_linux_start_capture_state_v1 {
    R2_LINUX_CAPTURE_UNATTEMPTED = 0,
    R2_LINUX_CAPTURE_VALID = 1,
    R2_LINUX_CAPTURE_FAILED = 2
};
enum r2_linux_start_capture_field_v1 {
    R2_LINUX_CAPTURE_BEGIN_VALID = 1u,
    R2_LINUX_CAPTURE_END_VALID = 2u,
    R2_LINUX_CAPTURE_PROC_STAT_VALID = 4u,
    R2_LINUX_CAPTURE_PROC_FS_VALID = 8u,
    R2_LINUX_CAPTURE_MEMINFO_STAT_VALID = 16u,
    R2_LINUX_CAPTURE_MEMINFO_FS_VALID = 32u,
    R2_LINUX_CAPTURE_EOF_VALID = 64u,
    R2_LINUX_CAPTURE_PARSER_RESULT_VALID = 128u,
    R2_LINUX_CAPTURE_POST_STAT_VALID = 256u
};
enum r2_linux_start_capture_operation_v1 {
    R2_LINUX_CAPTURE_OP_BEGIN_CLOCK = 1,
    R2_LINUX_CAPTURE_OP_OPEN_PROC = 2,
    R2_LINUX_CAPTURE_OP_PROC_STATFS = 3,
    R2_LINUX_CAPTURE_OP_PROC_STAT = 4,
    R2_LINUX_CAPTURE_OP_OPEN_MEMINFO = 5,
    R2_LINUX_CAPTURE_OP_MEMINFO_STATFS = 6,
    R2_LINUX_CAPTURE_OP_MEMINFO_STAT = 7,
    R2_LINUX_CAPTURE_OP_READ = 8,
    R2_LINUX_CAPTURE_OP_POST_STAT = 9,
    R2_LINUX_CAPTURE_OP_CLOSE_MEMINFO = 10,
    R2_LINUX_CAPTURE_OP_CLOSE_PROC = 11,
    R2_LINUX_CAPTURE_OP_END_CLOCK = 12,
    R2_LINUX_CAPTURE_OP_PARSE = 13
};
enum r2_linux_start_capture_fault_kind_v1 {
    R2_LINUX_CAPTURE_FAULT_NONE = 0,
    R2_LINUX_CAPTURE_FAULT_ERRNO = 1,
    R2_LINUX_CAPTURE_FAULT_INVARIANT = 2,
    R2_LINUX_CAPTURE_FAULT_BUDGET = 3,
    R2_LINUX_CAPTURE_FAULT_PARSER = 4
};
enum r2_linux_start_capture_invariant_v1 {
    R2_LINUX_CAPTURE_BAD_CLOCK = 1,
    R2_LINUX_CAPTURE_NOT_PROCFS = 2,
    R2_LINUX_CAPTURE_NOT_DIRECTORY = 3,
    R2_LINUX_CAPTURE_NOT_REGULAR = 4,
    R2_LINUX_CAPTURE_SOURCE_ALIAS = 5,
    R2_LINUX_CAPTURE_NONZERO_PROC_SIZE = 6,
    R2_LINUX_CAPTURE_IDENTITY_CHANGED = 7,
    R2_LINUX_CAPTURE_BAD_READ_RESULT = 8,
    R2_LINUX_CAPTURE_CLOCK_REGRESSED = 9,
    R2_LINUX_CAPTURE_BAD_API_RESULT = 10,
    R2_LINUX_CAPTURE_OVER_BOUND = 11
};
enum r2_linux_start_capture_source_v1 {
    R2_LINUX_CAPTURE_SOURCE_UNKNOWN = 0,
    R2_LINUX_CAPTURE_SOURCE_FIXED_PROC_MEMINFO = 1
};

/* Exact native LP64 ABI: 256 bytes, alignment 8; NOT a wire schema. */
struct r2_linux_start_capture_v1 {
    uint32_t abi, size, status, sample_valid;                         /* 0 */
    uint32_t attempt_consumed, valid_fields, primary_attempts, read_attempts; /* 16 */
    uint32_t bytes_read, eof_seen, parser_status, source_kind;        /* 32 */
    uint32_t primary_operation, primary_kind, primary_code, primary_errno_valid; /* 48 */
    int32_t primary_errno, meminfo_close_errno, proc_close_errno, end_clock_errno; /* 64 */
    uint32_t meminfo_close_state, proc_close_state, end_clock_state, value_valid; /* 80 */
    uint64_t monotonic_begin_ns, monotonic_end_ns;                    /* 96 */
    uint64_t memavailable_kib, memavailable_bytes;                    /* 112 */
    uint64_t proc_dev, proc_ino, meminfo_dev, meminfo_ino;             /* 128 */
    int64_t meminfo_size, proc_fs_type, meminfo_fs_type;               /* 160 */
    int32_t proc_fsid[2], meminfo_fsid[2];                            /* 184 */
    uint32_t proc_mode, proc_uid, meminfo_mode, meminfo_uid;           /* 200 */
    uint64_t proc_nlink, meminfo_nlink;                               /* 216 */
    uint32_t proc_gid, meminfo_gid, post_stat_state, end_clock_attempts; /* 232 */
    uint32_t end_clock_fault_kind, end_clock_fault_code;              /* 248 */
};

/* REAL production primitive for the R2_TARGET_LINUX_START executable only.
 * Link exactly one native instance; invoke in its original native entry BEFORE
 * any fork/clone/spawn/exec of a Python/controller child or Python startup.
 * This function has no constructor/entry body, and cannot prove call ordering.
 * No bytes, clock, path or descriptor supplied by a caller is a sample source.
 * It samples CLOCK_MONOTONIC, opens fixed /proc and relative meminfo using
 * openat2, checks owned fstatfs/fstat identities, consumes a single bounded
 * stream to EOF, invokes the existing complete parser, closes owned fds once,
 * and samples the end clock. No reopen, seek, repeated sample or fallback.
 * Root resolution refuses symlink/magic-link components; relative meminfo also
 * refuses every mount crossing (including bind aliases). Root mount/namespace
 * authenticity is NOT established: its dev/ino/fsid/type are raw local facts.
 * The original caller must bind these facts to its approved creator/root.
 * A stable regular procfs file with size zero, nlink one and same root device
 * is required. Before/after stat identity, owner, mode, size, mtime and ctime
 * must match. This cannot turn dynamic procfs counters into an atomic snapshot.
 * Input max is 16384 complete bytes; one extra byte detects oversize. The fixed
 * 16385-byte buffer is private stack storage; there is no heap allocation.
 * Every primary native call, including EINTR retries and short reads, consumes
 * the SAME finite 64-attempt budget. Each acquired fd then gets exactly ONE
 * close attempt, even on failure/budget exhaustion; Linux close is never
 * retried, including EINTR. End clock has a separate finite 4-attempt budget.
 * At most 70 clock/fd interface attempts; this does NOT bound a blocked call
 * or signal-handler time. The future outer owner must enforce its deadline.
 * Bad NULL/size/alignment/wrapped output returns BAD_ARGUMENT with no write,
 * no clock/I/O and no once consumption. Caller guarantees writable accessible
 * exclusive memory: range checks cannot prove accessibility or ownership.
 * Thereafter atomic once is consumed for this native executable lifetime even
 * on failure. Concurrent/reentrant/repeated calls return ALREADY_ATTEMPTED in
 * a fresh deterministic report without I/O; no reset exists. Fork inherits
 * the consumed state; re-exec/unload is not a continuity mechanism.
 * All report bytes initialize zero. attempt_consumed means the opportunity
 * was already or is now consumed, NOT that this call sampled successfully.
 * valid_fields marks individually returned raw facts only. Parser status is
 * meaningful only with PARSER_RESULT_VALID. sample_valid/value_valid become
 * one ONLY on complete capture, parse, both closes and end clock; otherwise
 * both memory values are zero. Successful raw zero remains value_valid=1.
 * Raw timestamp flags can remain valid on a later failure; they are interval
 * facts ONLY, never an admitted t0 or atomic M0 at t0. No startup-authority
 * value, study-wide once, process ancestry, original-root authentication,
 * transport authentication, scope acceptance or application admission issues.
 * First primary fault is retained; each failed close retains its errno even
 * if zero, identified by FAILED state. Secondary end-clock kind/code/errno is
 * separate and cannot overwrite an earlier primary or either cleanup fault.
 * Caller must require return COMPLETE plus sample_valid/value_valid, retain
 * this native result under its original ownership, then perform future
 * provenance/admission work before it may create its downstream children.
 */
uint32_t route2_linux_start_capture_once_v1(
    struct r2_linux_start_capture_v1 *out, size_t out_size);
#endif
#endif

/* C02 owned-child SOURCE component. This appended ABI does not change C02-A,
 * C02-B1 or C03. Native memory layout only; no authenticated transport or
 * admission. The original caller supplies already-bound raw intent and its
 * ORIGINAL absolute QPC deadlines. This component does not verify a lease,
 * readonly image closure, original H1/root epoch, RAM/VM/service scope, whole
 * fees, physical writes or an external hard-deadline executor.
 */
#if defined(R2_TARGET_WINDOWS_SEED)
#ifndef R2_WIN_OWNED_CHILD_V1_DECLARED
#define R2_WIN_OWNED_CHILD_V1_DECLARED
#define R2_WIN_OWNED_ABI 1u
#define R2_WIN_OWNED_TEXT_CAPACITY 32768u
#define R2_WIN_OWNED_ATTRIBUTE_CAPACITY 65536u
#define R2_WIN_OWNED_FAULT_CAPACITY 64u
#define R2_WIN_OWNED_THREAD_SCAN_CAPACITY 65536u
#define R2_WIN_OWNED_EXPORT __declspec(dllexport)

enum r2_win_owned_status_v1 {
    R2_OWN_OK = 1, R2_OWN_PENDING = 2, R2_OWN_EXITED = 3,
    R2_OWN_NEEDS_CLEANUP = 4, R2_OWN_FINISHED = 5,
    R2_OWN_RESIDUAL = 6, R2_OWN_BAD_ARGUMENT = 7,
    R2_OWN_BAD_STATE = 8, R2_OWN_BUSY = 9
};
enum r2_win_owned_lifecycle_v1 {
    R2_OWN_UNUSED = 0, R2_OWN_INITIALIZING = 1, R2_OWN_INTENT_HELD = 2,
    R2_OWN_SUSPENDED = 3, R2_OWN_RUNNING = 4, R2_OWN_STOPPING = 5,
    R2_OWN_JOINING = 6, R2_OWN_FINAL_SAMPLING = 7,
    R2_OWN_CLOSING = 8, R2_OWN_DONE = 9, R2_OWN_RETAINED = 10
};
enum r2_win_owned_operation_v1 {
    R2_OWN_OP_ARGUMENT = 1, R2_OWN_OP_FIRST_CLOCK, R2_OWN_OP_FREQUENCY,
    R2_OWN_OP_CLOCK, R2_OWN_OP_CREATOR_DUPLICATE, R2_OWN_OP_CREATOR_PID,
    R2_OWN_OP_CREATOR_TIMES, R2_OWN_OP_GROUPS, R2_OWN_OP_COUNT,
    R2_OWN_OP_AFFINITY, R2_OWN_OP_CREATE_JOB, R2_OWN_OP_SET_LIMITS,
    R2_OWN_OP_SET_CPU, R2_OWN_OP_QUERY_LIMITS, R2_OWN_OP_QUERY_CPU,
    R2_OWN_OP_QUERY_ACCOUNTING, R2_OWN_OP_ATTRIBUTE_SIZE,
    R2_OWN_OP_ATTRIBUTE_INIT, R2_OWN_OP_ATTRIBUTE_UPDATE,
    R2_OWN_OP_CREATE_PROCESS, R2_OWN_OP_CHILD_PID, R2_OWN_OP_CHILD_TID,
    R2_OWN_OP_PROCESS_TIMES, R2_OWN_OP_THREAD_TIMES,
    R2_OWN_OP_MEMBERSHIP, R2_OWN_OP_RESUME, R2_OWN_OP_WAIT_PROCESS,
    R2_OWN_OP_WAIT_THREAD, R2_OWN_OP_EXIT_CODE, R2_OWN_OP_TERMINATE_JOB,
    R2_OWN_OP_TERMINATE_PROCESS, R2_OWN_OP_SNAPSHOT,
    R2_OWN_OP_THREAD_FIRST, R2_OWN_OP_THREAD_NEXT,
    R2_OWN_OP_CLOSE_SNAPSHOT, R2_OWN_OP_CLOSE_THREAD,
    R2_OWN_OP_CLOSE_PROCESS, R2_OWN_OP_CLOSE_JOB,
    R2_OWN_OP_CLOSE_CREATOR, R2_OWN_OP_FINAL_CLOCK,
    R2_OWN_OP_THREAD_LIMIT, R2_OWN_OP_BIRTH_HISTORY, R2_OWN_OP_STATE,
    R2_OWN_OP_CREATOR_WAIT
};
enum r2_win_owned_residual_v1 {
    R2_OWN_RESIDUAL_DEADLINE = 1u, R2_OWN_RESIDUAL_CLOCK = 2u,
    R2_OWN_RESIDUAL_JOIN = 4u, R2_OWN_RESIDUAL_SAMPLE = 8u,
    R2_OWN_RESIDUAL_CLOSE = 16u
};
struct r2_win_owned_text_v1 {
    const uint16_t *text;
    uint32_t units, reserved;
};
struct r2_win_owned_spec_v1 {
    uint32_t abi, size;
    int64_t lease_epoch_qpc, lease_qpc_frequency;
    int64_t stop_deadline_qpc, cleanup_deadline_qpc;
    uint64_t intent_serial;
    struct r2_win_owned_text_v1 application, command_line;
    struct r2_win_owned_text_v1 current_directory, environment;
};
struct r2_win_owned_fault_v1 {
    uint32_t operation, kind, code, win32_error, win32_error_valid, occurrences;
};
struct r2_win_owned_handle_state_v1 {
    uint32_t acquired, consumed, close_state, reserved;
};
struct r2_win_owned_report_v1 {
    uint32_t abi, size, status, lifecycle;
    uint32_t attempt_consumed, stop_new, birth_attempted, resume_attempted;
    uint32_t finish_started, membership, process_signaled, thread_signaled;
    uint32_t job_empty, final_complete, residual_bits, fault_count;
    uint32_t configured_valid, latest_valid, final_valid, clock_valid;
    uint32_t creator_pid, creator_tid, child_pid, child_tid;
    uint32_t terminate_job_state, terminate_process_state;
    uint32_t attribute_initialized, attribute_deleted;
    uint32_t thread_scan_state, thread_scan_entries, parent_threads, child_threads;
    uint32_t thread_live_at_both_polls, thread_warning_limit;
    uint32_t thread_transient_coverage, complete_birth_history;
    uint64_t intent_serial;
    int64_t lease_epoch_qpc, qpc_frequency, context_observed_qpc;
    int64_t stop_deadline_qpc, cleanup_deadline_qpc, last_qpc;
    struct r2_win_job_raw_u64_v1 creator_creation_100ns;
    struct r2_win_job_raw_u64_v1 child_creation_100ns, primary_creation_100ns;
    struct r2_win_job_raw_u64_v1 final_exit_100ns, final_kernel_100ns, final_user_100ns;
    struct r2_win_job_raw_u64_v1 final_thread_kernel_100ns, final_thread_user_100ns;
    struct r2_win_job_raw_u32_v1 final_exit_code, wait_before, wait_after, thread_wait;
    struct r2_win_job_raw_u32_v1 processor_groups, processor_count;
    struct r2_win_job_raw_u64_v1 allowed_affinity, system_affinity, selected_affinity;
    struct r2_win_owned_handle_state_v1 creator, job, process, thread, snapshot;
    struct r2_win_owned_fault_v1 primary;
    struct r2_win_owned_fault_v1 faults[R2_WIN_OWNED_FAULT_CAPACITY];
    struct r2_win_job_raw_snapshot_v1 configured, latest, final_sample;
};
struct r2_win_owned_abi_v1 {
    uint32_t abi, size, spec_size, report_size;
    uint32_t pointer_size, text_size, fault_size, handle_state_size;
    uint32_t snapshot_size, report_faults_offset, report_configured_offset, reserved;
};

/* One never-reclaimed private singleton per loaded native component. All
 * successful acquisitions are stored in C before any subsequent API/FFI
 * conversion. No HANDLE values leave this ABI. Original creator identity is
 * current-context identity, not pre-load ancestry. Caller memory must be
 * accessible, stable and exclusive through each call; size/range checks do
 * not establish that property. Text lengths include NUL; environment includes
 * final double NUL. Explicit absolute application/directory, no shell search.
 * Inputs are raw intent, never a verified lease or permission receipt.
 * begin consumes its sole chance even on bad arguments/failure. Subsequent
 * begin/birth/resume never reset history. copy bad output changes no history.
 * STOP_NEW is an independent Interlocked latch, including when another call
 * is BUSY. A reserved in-flight birth/resume may finish and must be cleaned.
 * Waits are <=1s and use the SAME supplied absolute cleanup deadline; native
 * synchronous calls and a stalled caller have no independent hard executor.
 * Raw Job commit4GiB/active1/affinity<=2/CPU are not RAM/thread/VM certification.
 * Toolhelp counts are bounded point snapshots of the original parent/child
 * only; >4 or incomplete scan stops new work. No transient/lifetime coverage,
 * whole-group scope or original HANDLE for each observed TID is claimed.
 * finish repeats bounded JOINING steps, then final raw sample and once-close.
 * Unjoined, late, failed required query/final sample retains native anchors;
 * a failed close consumes its usable slot but never claims actual release.
 * Residual context/library/monitor ownership MUST remain strongly retained.
 * DONE requires local join/final facts/closes, not absence of earlier faults,
 * complete fees, service/provider join, durable handoff or application PASS.
 */
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_describe_v1(
    struct r2_win_owned_abi_v1 *, size_t);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_begin_once_v1(
    const struct r2_win_owned_spec_v1 *, size_t);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_birth_suspended_once_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_resume_once_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_observe_step_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_stop_new_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_finish_step_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_child_copy_report_v1(
    struct r2_win_owned_report_v1 *, size_t);
#endif
#endif

/* C03-B1 bounded on-disk PE dependency facts, SOURCE ONLY. Independent ABI.
 * Microsoft PE format: https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
 * No loader, provider selection, closure verifier, receipt, authority or export.
 */
#if defined(R2_TARGET_WINDOWS_SEED)
#ifndef R2_PE_PRELOAD_RAW_V1_DECLARED
#define R2_PE_PRELOAD_RAW_V1_DECLARED
#define R2_PE_RAW_ABI 1u
#define R2_PE_RAW_REPORT_BYTES 209984u
#define R2_PE_RAW_FILE_LIMIT 67108864u
#define R2_PE_RAW_SECTION_LIMIT 96u
#define R2_PE_RAW_DESCRIPTOR_LIMIT 128u
#define R2_PE_RAW_SYMBOL_LIMIT 4096u
#define R2_PE_RAW_NAME_LIMIT 512u
#define R2_PE_RAW_NAME_BYTES_LIMIT 1048576u
#define R2_PE_RAW_TLS_CALLBACK_LIMIT 64u
#define R2_PE_RAW_WORK_LIMIT 8388608u

enum r2_pe_raw_status_v1 {
    R2_PE_RAW_COMPLETE = 0xC301u,
    R2_PE_RAW_INCOMPLETE = 0xC302u,
    R2_PE_RAW_REJECTED = 0xC303u,
    R2_PE_RAW_BAD_ARGUMENT = 0xC304u,
    R2_PE_RAW_APPLICATION_TLS_PRESENT = 0xC305u
};
enum r2_pe_raw_reason_v1 {
    R2_PE_REASON_NONE = 0,
    R2_PE_REASON_FILE_LIMIT, R2_PE_REASON_TRUNCATED,
    R2_PE_REASON_DOS, R2_PE_REASON_PE_SIGNATURE,
    R2_PE_REASON_MACHINE, R2_PE_REASON_OPTIONAL_HEADER,
    R2_PE_REASON_SECTION_LIMIT, R2_PE_REASON_SECTION_RANGE,
    R2_PE_REASON_SECTION_OVERLAP, R2_PE_REASON_HEADER_OVERLAP,
    R2_PE_REASON_RVA_OVERFLOW, R2_PE_REASON_RVA_UNMAPPED,
    R2_PE_REASON_ZERO_FILL, R2_PE_REASON_SPAN_CROSSING,
    R2_PE_REASON_DIRECTORY, R2_PE_REASON_DESCRIPTOR_LIMIT,
    R2_PE_REASON_DESCRIPTOR_TERMINATOR, R2_PE_REASON_LOOKUP_ABSENT,
    R2_PE_REASON_BOUND_UNSUPPORTED, R2_PE_REASON_THUNK_TERMINATOR,
    R2_PE_REASON_SYMBOL_LIMIT, R2_PE_REASON_ORDINAL_BITS,
    R2_PE_REASON_NAME_RVA_BITS, R2_PE_REASON_EMPTY_NAME,
    R2_PE_REASON_NAME_TERMINATOR, R2_PE_REASON_NAME_LIMIT,
    R2_PE_REASON_NAME_BYTES_LIMIT, R2_PE_REASON_WORK_LIMIT,
    R2_PE_REASON_DELAY_LEGACY_VA, R2_PE_REASON_DELAY_ATTRIBUTES,
    R2_PE_REASON_TLS_VA, R2_PE_REASON_TLS_TEMPLATE,
    R2_PE_REASON_TLS_CALLBACK_LIMIT, R2_PE_REASON_TLS_TERMINATOR,
    R2_PE_REASON_APPLICATION_TLS_PRESENT, R2_PE_REASON_IAT_TERMINATOR,
    R2_PE_REASON_ALIGNMENT, R2_PE_REASON_IAT_CONTENT,
    R2_PE_REASON_BOUND_TERMINATOR, R2_PE_REASON_UNLOAD_CONTENT,
    R2_PE_REASON_DELAY_HANDLE
};
/* This value is intentionally unrelated to r2_scope_result / any authority ABI. */
#define R2_PE_PRELOAD_CLOSURE_UNPROVEN 0xC3FFu
#define R2_PE_IMPORT_NORMAL 1u
#define R2_PE_IMPORT_DELAY 2u
#define R2_PE_SYMBOL_NAME 1u
#define R2_PE_SYMBOL_ORDINAL 2u

struct r2_pe_raw_name_v1 { uint32_t file_offset, length; };
struct r2_pe_raw_directory_v1 { uint32_t rva, size; };
struct r2_pe_raw_section_v1 {
    uint32_t rva, virtual_size, raw_offset, raw_size, virtual_extent, characteristics;
};
/* valid_fields: bit0 descriptor bytes, bit1 DLL name, bit2 terminated lookup.
 * Unset fields and slots are zero; counts include partial descriptors/symbols.
 */
struct r2_pe_raw_descriptor_v1 {
    uint32_t kind, valid_fields, descriptor_offset, lookup_rva;
    uint32_t iat_rva, module_handle_rva, bound_rva, unload_rva;
    uint32_t time_stamp, forwarder_chain, attributes, first_symbol;
    uint32_t symbol_count, lookup_terminated, reserved[2];
    struct r2_pe_raw_name_v1 dll_name;
};
/* kind==0 means a retained but incompletely decoded thunk. Name length excludes
 * NUL; hint is a raw 16-bit value and ordinal is the exact low 16 bits.
 */
struct r2_pe_raw_symbol_v1 {
    uint32_t descriptor_index, kind, thunk_offset, iat_offset;
    uint32_t name_offset, name_length, hint, ordinal;
    uint64_t raw_lookup, raw_iat;
};
struct r2_pe_raw_tls_v1 {
    uint32_t present, fields_valid, directory_offset, directory_size;
    uint64_t raw_start_va, raw_end_va, index_va, callbacks_va;
    uint32_t zero_fill, characteristics, template_offset, template_bytes;
    uint32_t index_offset, callback_count, callbacks_terminated, reserved;
};
struct r2_pe_raw_callback_v1 {
    uint64_t raw_va;
    uint32_t pointer_offset, target_rva, target_offset, reserved;
};
struct r2_pe_raw_report_v1 {
    uint32_t abi, size, raw_status, reason;
    uint32_t preload_scope, structural_complete, section_count, descriptor_count;
    uint32_t normal_count, delay_count, symbol_count, names_inspected_bytes;
    uint32_t directory_count, reserved[3];
    uint64_t failure_offset, work_units, image_base, file_bytes;
    uint32_t size_of_image, size_of_headers, entrypoint_rva, optional_directory_count;
    struct r2_pe_raw_directory_v1 directories[16];
    struct r2_pe_raw_section_v1 sections[R2_PE_RAW_SECTION_LIMIT];
    struct r2_pe_raw_descriptor_v1 descriptors[R2_PE_RAW_DESCRIPTOR_LIMIT];
    struct r2_pe_raw_symbol_v1 symbols[R2_PE_RAW_SYMBOL_LIMIT];
    struct r2_pe_raw_tls_v1 tls;
    struct r2_pe_raw_callback_v1 callbacks[R2_PE_RAW_TLS_CALLBACK_LIMIT];
};
/* Caller supplies an accessible, STABLE FILE byte span (not a mapped image),
 * and aligned, accessible, exclusive output for the entire call. const does
 * not prove immutability. C pointer/range checks cannot prove accessibility.
 * Input and output must be disjoint. Bad ABI/size/ranges/overlap return
 * BAD_ARGUMENT without writing output; there is no probing or exception trap.
 * All other returns initialize the whole fixed report and preserve partial
 * facts. failure_offset is a FILE offset when a file location is known; for
 * unmappable addresses it is the failing RVA (TLS_VA uses its field offset).
 * work_units charges every inspected file byte and mapping/overlap candidate;
 * fixed report initialization is bounded separately, not a RAM/time grant.
 * A name may inspect at most 512 bytes INCLUDING its NUL, aggregate <=1MiB.
 * Limits are conservative refusals, never truncation-as-complete. COMPLETE
 * only covers these supported dependency structures, not whole PE validity.
 * Supported normal IATs exactly match unbound lookup entries; delay IATs
 * may hold nonzero stub addresses. Delay handle storage is required. Optional
 * bound tables terminate in lockstep; unload tables equal the original IAT.
 * Low alignment (<4096) requires each backed section FILE offset == RVA.
 * APPLICATION_TLS_PRESENT retains complete structural facts but refuses the
 * application callback condition. No callback is called. Empty/absent TLS
 * proves nothing about CRT/DllMain. Export forwarders, API sets, SxS/search,
 * mapped identities, transitive providers, existing 40-byte transport,
 * original bytes provenance and actual preload closure remain UNPROVEN.
 * No R2_SCOPE_PROVEN, v2 closure verifier, issuer receipt or handoff is issued.
 */
uint32_t route2_pe_preload_parse_raw_v1(
    const unsigned char *file, size_t file_size, uint32_t report_abi,
    struct r2_pe_raw_report_v1 *out, size_t out_size);
#endif
#endif

/* C03 bounded original-FILE ELF facts, SOURCE ONLY; independent Linux-start ABI.
 * Format references: gabi.xinuos.com/v42/elf/{02-eheader,07-pheader,08-dynamic}.html
 * and a-emachine.html. These are format facts, not installed loader support.
 */
#if defined(R2_TARGET_LINUX_START)
#ifndef R2_ELF_PRELOAD_RAW_V1_DECLARED
#define R2_ELF_PRELOAD_RAW_V1_DECLARED
#define R2_ELF_RAW_ABI 1u
#define R2_ELF_RAW_REPORT_BYTES 147808u
#define R2_ELF_RAW_FILE_LIMIT 67108864u
#define R2_ELF_RAW_PROGRAM_LIMIT 128u
#define R2_ELF_RAW_DYNAMIC_LIMIT 4096u
#define R2_ELF_RAW_NEEDED_LIMIT 256u
#define R2_ELF_RAW_STRING_RECORD_LIMIT 259u
#define R2_ELF_RAW_STRING_LIMIT 512u
#define R2_ELF_RAW_STRING_BYTES_LIMIT 1048576u
#define R2_ELF_RAW_WORK_LIMIT 8388608u
#define R2_ELF_PRELOAD_CLOSURE_UNPROVEN 0xC3EFu

enum r2_elf_raw_status_v1 {
    R2_ELF_RAW_COMPLETE = 0xC311u,
    R2_ELF_RAW_INCOMPLETE = 0xC312u,
    R2_ELF_RAW_REJECTED = 0xC313u,
    R2_ELF_RAW_BAD_ARGUMENT = 0xC314u,
    R2_ELF_RAW_UNSUPPORTED = 0xC315u,
    R2_ELF_RAW_APPLICATION_CONDITIONS = 0xC316u
};
enum r2_elf_raw_reason_v1 {
    R2_ELF_REASON_NONE = 0,
    R2_ELF_REASON_FILE_LIMIT, R2_ELF_REASON_TRUNCATED,
    R2_ELF_REASON_MAGIC, R2_ELF_REASON_CLASS, R2_ELF_REASON_ENCODING,
    R2_ELF_REASON_TARGET, R2_ELF_REASON_VERSION, R2_ELF_REASON_OSABI,
    R2_ELF_REASON_HEADER_SIZE, R2_ELF_REASON_PROGRAM_ENTRY_SIZE,
    R2_ELF_REASON_EXTENDED_COUNT, R2_ELF_REASON_PROGRAM_LIMIT,
    R2_ELF_REASON_PROGRAM_RANGE, R2_ELF_REASON_NO_LOAD,
    R2_ELF_REASON_LOAD_SIZE, R2_ELF_REASON_VIRTUAL_OVERFLOW,
    R2_ELF_REASON_LOAD_ALIGNMENT, R2_ELF_REASON_LOAD_ORDER,
    R2_ELF_REASON_LOAD_OVERLAP, R2_ELF_REASON_UNMAPPED,
    R2_ELF_REASON_AMBIGUOUS_MAPPING, R2_ELF_REASON_ZERO_FILL,
    R2_ELF_REASON_SPAN_CROSSING, R2_ELF_REASON_MAPPING_MISMATCH,
    R2_ELF_REASON_INTERPRETER, R2_ELF_REASON_INTERPRETER_ORDER,
    R2_ELF_REASON_DUPLICATE_PROGRAM, R2_ELF_REASON_UNKNOWN_PROGRAM,
    R2_ELF_REASON_DYNAMIC_SIZE, R2_ELF_REASON_DYNAMIC_LIMIT,
    R2_ELF_REASON_DYNAMIC_TERMINATOR, R2_ELF_REASON_DUPLICATE_TAG,
    R2_ELF_REASON_UNKNOWN_DYNAMIC, R2_ELF_REASON_NEEDED_LIMIT,
    R2_ELF_REASON_STRING_TABLE_PAIR, R2_ELF_REASON_STRING_TABLE,
    R2_ELF_REASON_STRING_INDEX, R2_ELF_REASON_STRING_TERMINATOR,
    R2_ELF_REASON_STRING_LIMIT, R2_ELF_REASON_STRING_BYTES_LIMIT,
    R2_ELF_REASON_STRING_ASCII, R2_ELF_REASON_EMPTY_NAME,
    R2_ELF_REASON_ARRAY_PAIR, R2_ELF_REASON_ARRAY_ALIGNMENT,
    R2_ELF_REASON_WORK_LIMIT
};
#define R2_ELF_VALUE_FILE_OFFSET 1u
#define R2_ELF_VALUE_VIRTUAL_ADDRESS 2u
#define R2_ELF_VALUE_SCALAR 3u
#define R2_ELF_STRING_NEEDED 1u
#define R2_ELF_STRING_SONAME 2u
#define R2_ELF_STRING_RPATH 3u
#define R2_ELF_STRING_RUNPATH 4u
#define R2_ELF_DYNAMIC_STRING 1u
#define R2_ELF_DYNAMIC_TABLE 2u
#define R2_ELF_DYNAMIC_APPLICATION 3u
#define R2_ELF_DYNAMIC_RAW_ONLY 4u
#define R2_ELF_DYNAMIC_UNKNOWN 5u
#define R2_ELF_DYNAMIC_TERMINATOR 6u
#define R2_ELF_CONDITION_INTERPRETER 1u
#define R2_ELF_CONDITION_TLS 2u
#define R2_ELF_CONDITION_INIT 4u
#define R2_ELF_CONDITION_FINI 8u
#define R2_ELF_CONDITION_INIT_FINI 12u /* composite convenience mask */
#define R2_ELF_CONDITION_INIT_ARRAY 16u
#define R2_ELF_CONDITION_FINI_ARRAY 32u
#define R2_ELF_CONDITION_PREINIT_ARRAY 64u
#define R2_ELF_CONDITION_SEARCH_PATH 128u
/* Unconditional even for structurally complete static files. */
#define R2_ELF_UNPROVEN_SECTIONS_SYMBOLS 1u
#define R2_ELF_UNPROVEN_RELOCATION_VERSION_IFUNC 2u
#define R2_ELF_UNPROVEN_DYNAMIC_RAW_SEMANTICS 4u
#define R2_ELF_UNPROVEN_AMBIENT_TRANSITIVE_PROVIDER 8u
#define R2_ELF_UNPROVEN_ORIGINAL_IDENTITY 16u
#define R2_ELF_UNPROVEN_PRELOAD_AUTHORITY 32u
#define R2_ELF_UNPROVEN_ALL 63u

struct r2_elf_raw_program_v1 {
    uint32_t type, flags;
    uint64_t file_offset, virtual_address, physical_address;
    uint64_t file_size, memory_size, alignment, header_offset;
};
struct r2_elf_raw_dynamic_v1 {
    uint64_t raw_tag, raw_value, file_offset;
    uint32_t interpretation, reserved;
};
struct r2_elf_raw_string_v1 {
    uint32_t kind, dynamic_index, file_offset, length;
    uint64_t string_index;
    uint32_t complete, reserved;
};
struct r2_elf_raw_report_v1 {
    uint32_t abi, size, raw_status, reason;
    uint32_t preload_scope, structural_complete, program_count, load_count;
    uint32_t dynamic_count, strings_count, needed_count, dynamic_terminated;
    uint32_t unknown_program_count, unknown_dynamic_count;
    uint32_t application_conditions, remaining_unproven;
    uint32_t string_bytes_inspected, header_valid, declared_phnum, dynamic_present;
    uint32_t interpreter_present, tls_present, string_table_present, string_size_present;
    uint64_t file_bytes, work_units, failure_offset, failure_value;
    uint64_t entry, program_table_offset, dynamic_offset, dynamic_size;
    uint64_t string_table_address, string_table_size, string_table_offset;
    uint64_t interpreter_offset, interpreter_size, tls_offset, tls_filesz, tls_memsz;
    uint32_t failure_value_kind, failure_subject_type, dynamic_declared_entries;
    uint32_t dynamic_remainder_unknown, needed_remainder_unknown, interpreter_length;
    uint32_t elf_type, elf_flags;
    struct r2_elf_raw_program_v1 programs[R2_ELF_RAW_PROGRAM_LIMIT];
    struct r2_elf_raw_dynamic_v1 dynamics[R2_ELF_RAW_DYNAMIC_LIMIT];
    struct r2_elf_raw_string_v1 strings[R2_ELF_RAW_STRING_RECORD_LIMIT];
};
/* Caller supplies stable, readable original FILE bytes, never a mapped image,
 * and distinct aligned accessible exclusive output memory for the whole call.
 * const/range checks cannot establish those preconditions or immutable file
 * identity. Invalid ABI/exact size/alignment/integer ranges/overlap returns
 * BAD_ARGUMENT with ALL previous output bytes untouched. Check the return;
 * caller-provided parse/status fields are never accepted as evidence.
 * Other returns initialize output, retain partial raw records, and leave
 * structural_complete zero on truncation, limits or unsupported semantics.
 * Program records include every inspected entry, including PT_NULL whose
 * undefined fields are retained and ignored. Counts include partial strings.
 * The 1MiB string-byte ceiling is also enforced; under these entry/name caps
 * it is conservatively redundant (all references plus interpreter <1MiB).
 * Dynamic records stop at first DT_NULL; declared extent and unknown remainder
 * are distinct. needed_remainder_unknown stays set until all selected raw
 * checks finish and remains set for unknown program/dynamic semantics.
 * String lengths exclude NUL; all original-FILE string reads,
 * including interpreter and repeat references, charge the inclusive-NUL cap.
 * failure_offset is the field/entry FILE offset when available; failure_value
 * and its kind retain the failing scalar/address separately. First reason is
 * preserved even if a later structural error is also encountered.
 * Selected profile: ELF64 LE x86-64, EXEC/DYN, current versions, OSABI System V
 * or Linux with ABI version zero, 64/56-byte headers, program table after the
 * 64-byte ELF header, ordinary program count,
 * at least one ordered nonoverlapping LOAD. No section-count fallback.
 * Each consumed virtual-pointer metadata span maps uniquely inside ONE LOAD's
 * original raw bytes. INTERP uses its explicit FILE offset, not a VA;
 * virtual zero fill is never read as FILE bytes. Unknown program/dynamic
 * semantics remain explicitly UNSUPPORTED; GNU EH_FRAME/STACK/RELRO/PROPERTY,
 * NOTE, PHDR and familiar hash/symbol/relocation/version/flags dynamic
 * tags are named/raw-only facts, not semantic validation or loader support.
 * Reserved PT_SHLIB is retained as unsupported, with other unknown programs.
 * Strings are a bounded ASCII subset; NEEDED/SONAME must be nonempty. Even an
 * empty RPATH/RUNPATH is PRESENT. TLS (including empty), interpreter, INIT,
 * FINI and all three initializer arrays are separate application conditions.
 * Array pairs/alignment/raw extent are checked; entries are not executed or
 * interpreted. Sections/symbols/relocations/version/IFUNC remain unvalidated.
 * Work units conservatively reserve initialization, reads, entries, scans and
 * comparisons BEFORE work. There are no refunds. Algorithmic limits establish
 * neither causal billing nor a runtime deadline, RAM grant or OS enforcement.
 * COMPLETE covers only this selected raw structural profile. Every report
 * unconditionally retains PRELOAD_CLOSURE_UNPROVEN. No ambient resolution,
 * provider/transitive closure, immutable manifest, birth/transport, C00, Stage,
 * v2 success path, loader or authority is established or invoked.
 */
uint32_t route2_elf_preload_parse_raw_v1(
    const unsigned char *file, size_t file_size, uint32_t report_abi,
    struct r2_elf_raw_report_v1 *out, size_t out_size);
#endif
#endif

/* C00 positive machine-memory acquisition limb, SOURCE ONLY / UNCOMPILED.
 * This independent raw ABI neither replaces the protected owned-child ABI
 * nor supplies VM/service scope, resource admission or causal accounting.
 */
#if defined(R2_TARGET_WINDOWS_SEED)
#ifndef R2_WIN_MACHINE_MEMORY_V1_DECLARED
#define R2_WIN_MACHINE_MEMORY_V1_DECLARED
#define R2_WIN_MACHINE_MEMORY_ABI 1u
#define R2_WIN_MACHINE_MEMORY_REPORT_BYTES 1064u
#define R2_WIN_MACHINE_MEMORY_UNPROVEN_ALL 63u
#define R2_MM_VALID_INSTALLED_KIB 1u
#define R2_MM_VALID_INSTALLED_BYTES 2u
#define R2_MM_VALID_GLOBAL_FIELDS 4u
#define R2_MM_VALID_BEGIN_CLOCK 8u
#define R2_MM_VALID_INSTALLED_BEGIN_CLOCK 16u
#define R2_MM_VALID_INSTALLED_END_CLOCK 32u
#define R2_MM_VALID_END_CLOCK 64u

enum r2_win_machine_memory_status_v1 {
    R2_MM_RAW_COMPLETE = 0xC001u, R2_MM_RAW_PARTIAL = 0xC002u,
    R2_MM_BAD_ARGUMENT = 0xC003u, R2_MM_BUSY = 0xC004u,
    R2_MM_LIMIT_REACHED = 0xC005u, R2_MM_COPY_OK = 0xC006u
};
enum r2_win_machine_memory_operation_v1 {
    R2_MM_OP_STATE = 1, R2_MM_OP_OWNER_BEFORE, R2_MM_OP_CLOCK_BEGIN,
    R2_MM_OP_CLOCK_INSTALLED_BEGIN, R2_MM_OP_INSTALLED, R2_MM_OP_CLOCK_INSTALLED_END, R2_MM_OP_GLOBAL,
    R2_MM_OP_OWNER_AFTER, R2_MM_OP_CLOCK_END, R2_MM_OP_VALUES,
    R2_MM_OP_CAPACITY_CHANGE, R2_MM_OP_COUNTER
};
enum r2_win_machine_memory_fault_kind_v1 {
    R2_MM_FAULT_WIN32 = 1, R2_MM_FAULT_INVARIANT = 2,
    R2_MM_FAULT_OWNER = 3
};
enum r2_win_machine_memory_reason_v1 {
    R2_MM_REASON_STATE = 1, R2_MM_REASON_IDENTITY, R2_MM_REASON_CLOCK,
    R2_MM_REASON_DEADLINE, R2_MM_REASON_VALUE, R2_MM_REASON_OVERFLOW,
    R2_MM_REASON_CAPACITY_CHANGE, R2_MM_REASON_COUNTER
};
struct r2_win_machine_memory_fault_v1 {
    uint32_t operation, kind, code, win32_error, win32_error_valid, reserved;
};
struct r2_win_machine_memory_clock_v1 {
    int64_t raw_qpc;
    uint32_t attempted, raw_result, win32_error, win32_error_valid;
};
struct r2_win_machine_memory_snapshot_v1 {
    uint32_t ordinal, lifecycle, valid_fields, raw_complete;
    struct r2_win_machine_memory_clock_v1 clocks[4];
    uint32_t installed_attempted, installed_raw_result;
    uint32_t installed_win32_error, installed_error_valid;
    uint32_t global_attempted, global_raw_result;
    uint32_t global_win32_error, global_error_valid;
    uint64_t installed_kib, installed_bytes;
    uint32_t native_length, native_memory_load;
    uint64_t total_phys, avail_phys, total_page_file, avail_page_file;
    uint64_t total_virtual, avail_virtual, avail_extended_virtual;
    uint32_t owner_before, owner_after, prebirth_first, reserved;
    uint32_t fault_count, omitted_fault_count, reserved_faults[2];
    struct r2_win_machine_memory_fault_v1 faults[2];
};
struct r2_win_machine_memory_report_v1 {
    uint32_t abi, size, status, stop_new;
    uint32_t attempt_count, initial_present, latest_present, failed_present;
    uint32_t successful_captures, failed_captures, fault_count, omitted_fault_count;
    uint32_t creator_pid, creator_tid, remaining_unproven, reserved;
    uint64_t intent_serial;
    int64_t lease_epoch_qpc, qpc_frequency, stop_deadline_qpc, cleanup_deadline_qpc;
    struct r2_win_machine_memory_fault_v1 primary, secondary;
    struct r2_win_machine_memory_snapshot_v1 initial, latest, failed;
};
/* No parameters supply samples, clocks, handles, flags, permissions or limits.
 * The first attempted observation must find the ORIGINAL private C02 context
 * INTENT_HELD, not stopped, before any birth reservation. It consumes that
 * initial serialized position even on failure; no later capture repairs it.
 * Each call uses the existing owner guard, held original creator identity and
 * original PID/TID, lease, QPC frequency and absolute stop/cleanup deadlines.
 * Subsequent calls may retain diagnostic observations after STOP_NEW while
 * the original creator remains held and its ORIGINAL cleanup time remains.
 * No clock, attempt, native ownership, STOP_NEW or fault history is reset.
 * Failed/busy/state/identity/clock/deadline/value observations latch the SAME
 * owned-child STOP_NEW. Failed observations mark its residual SAMPLE liability.
 * No automatic birth/resume/termination/join/close or new thread is performed.
 * Original finish/drain is still required; this API owns no additional HANDLE.
 *
 * GetPhysicallyInstalledSystemMemory supplies SMBIOS-reported KiB, not a proven
 * immutable hardware ceiling. GlobalMemoryStatusEx supplies separate volatile
 * facts. clocks[0..3] bracket entry/installed start/installed return/end; they
 * do not make the
 * two memory calls atomic. Raw BOOL and each failed call's immediate Win32
 * error are retained; validity bits distinguish failure from a valid raw zero.
 * A successful native result can retain raw values yet fail invariants.
 * All returned MEMORYSTATUSEX fields are retained. Physical fields cover all
 * NUMA nodes; available includes standby/free/zero lists. Pagefile fields are
 * caller-constrained commit facts and virtual fields are caller address space,
 * not whole-system commitment. No subtraction is a causal RAM charge.
 * Checked KiB conversion, nonzero totals, returned-field consistency and
 * observed changes in installed/OS physical totals fail closed. This detects
 * observed drift ONLY; unchanged samples do not exclude hot-add/removal between
 * calls or prove capacity, provider closure, RAM/VRAM/CPU caps or phase fees.
 * remaining_unproven always retains all six exclusions: whole RAM, VRAM, CPU,
 * immutable topology, phase/causal billing, and trusted pre-load provenance.
 * No SCOPE_PROVEN/16GiB PASS or authority is produced, even on RAW_COMPLETE.
 *
 * Fixed private initial/latest/failed snapshots retain the first attempt,
 * most recent complete sample and most recent failed attempt, respectively.
 * Primary/secondary report faults never change after their first assignments;
 * per-snapshot faults retain the first two, with omitted counts. This is NOT
 * a complete sample/fault ledger. C02 identity-query faults remain in its
 * protected owner report; new memory/clock outcomes remain here. Counters
 * never wrap; exhaustion stops.
 * A synchronous native stall is not cancelled or bounded by these checks:
 * original owner/liability remains pending; no successful result is emitted.
 * copy requires exact ABI size, aligned accessible exclusive writable memory
 * disjoint from private owner/report/guard storage. Range checks cannot prove
 * accessibility. Copy has no native sampling, clock or attempt consumption;
 * COPY_OK means only that bytes were copied; inspect the retained status.
 * BAD_ARGUMENT/BUSY leave output untouched and issue no proof.
 */
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_machine_memory_observe_step_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_machine_memory_copy_report_v1(
    struct r2_win_machine_memory_report_v1 *out, size_t out_size);
#endif
#endif

/* C00 GPU original-adapter limb: SOURCE ONLY / UNCOMPILED. Explicit opt-in.
 * Build this existing Windows-seed C11 translation unit with Windows extensions,
 * R2_ENABLE_WIN_GPU_RAW_V1, Windows SDK 10.0.26100 or newer, _WIN32_WINNT targeting
 * Windows 10+, NTDDI_VERSION >= NTDDI_WIN11_GE and the actual SDK's WDDM 3.2+
 * interface. Windows.h precedes d3dkmthk.h. Link onecoreuap.lib (EnumAdapters3)
 * and Gdi32.lib (QueryAdapterInfo/CloseAdapter); documented DLL: Gdi32.dll.
 * Compile guards establish declaration availability only. Installed SDK, OS,
 * runtime support, driver behavior and dependency closure are NOT certified.
 */
#if defined(R2_TARGET_WINDOWS_SEED) && defined(R2_ENABLE_WIN_GPU_RAW_V1)
#ifndef R2_WIN_GPU_RAW_V1_DECLARED
#define R2_WIN_GPU_RAW_V1_DECLARED
#define R2_WIN_GPU_RAW_ABI 1u
#define R2_WIN_GPU_REPORT_BYTES 31536u
#define R2_WIN_GPU_ADAPTER_CAP 16u
#define R2_WIN_GPU_MEMBER_CAP 8u
#define R2_WIN_GPU_FAULT_CAP 8u
#define R2_WIN_GPU_NATIVE_WORK_CAP 194u
#define R2_WIN_GPU_UNPROVEN_ALL 255u

enum r2_win_gpu_status_v1 {
    R2_GPU_UNUSED = 0, R2_GPU_PENDING = 0xC101u,
    R2_GPU_RAW_COMPLETE = 0xC102u, R2_GPU_RAW_PARTIAL = 0xC103u,
    R2_GPU_RETAINED = 0xC104u, R2_GPU_BAD_ARGUMENT = 0xC105u,
    R2_GPU_BUSY = 0xC106u, R2_GPU_COPY_OK = 0xC107u
};
enum r2_win_gpu_ownership_v1 {
    R2_GPU_OWN_NONE = 0, R2_GPU_OWN_KNOWN = 1,
    R2_GPU_ENUM_FAILED_OWNERSHIP_UNKNOWN = 2,
    R2_GPU_ENUM_INVALID_OWNERSHIP_UNKNOWN = 3
};
enum r2_win_gpu_operation_v1 {
    R2_GPU_OP_STATE = 1, R2_GPU_OP_ENUM_SIZE, R2_GPU_OP_ENUM_POPULATE,
    R2_GPU_OP_ADAPTER_TYPE, R2_GPU_OP_SEGMENTS, R2_GPU_OP_MEMBER_COUNT,
    R2_GPU_OP_MEMBER_SEGMENTS, R2_GPU_OP_CLOSE, R2_GPU_OP_FINISH
};
enum r2_win_gpu_fault_kind_v1 {
    R2_GPU_FAULT_NTSTATUS = 1, R2_GPU_FAULT_WIN32 = 2,
    R2_GPU_FAULT_INVARIANT = 3, R2_GPU_FAULT_OWNER = 4
};
enum r2_win_gpu_reason_v1 {
    R2_GPU_REASON_STATE = 1, R2_GPU_REASON_IDENTITY, R2_GPU_REASON_CLOCK,
    R2_GPU_REASON_DEADLINE, R2_GPU_REASON_BOUND, R2_GPU_REASON_HANDLE,
    R2_GPU_REASON_DUPLICATE, R2_GPU_REASON_INDEX, R2_GPU_REASON_RACE,
    R2_GPU_REASON_COUNTER, R2_GPU_REASON_CONTEXT_CHANGED
};
struct r2_win_gpu_clock_v1 {
    int64_t raw_qpc;
    uint32_t attempted, raw_result, win32_error, win32_error_valid;
};
struct r2_win_gpu_call_v1 {
    uint32_t attempted, ntstatus_bits, ntstatus_valid, data_valid;
    struct r2_win_gpu_clock_v1 clocks[4];
};
struct r2_win_gpu_fault_v1 {
    uint32_t operation, kind, reason, raw_code;
    uint32_t adapter_index, member_index, reserved[2];
};
struct r2_win_gpu_member_v1 {
    uint32_t input_index, returned_index, reserved[2];
    uint64_t legacy_dedicated_video, legacy_dedicated_system, legacy_shared_system;
    uint64_t local_bytes, nonlocal_bytes, nonbudget_bytes;
    struct r2_win_gpu_call_v1 segments;
};
struct r2_win_gpu_adapter_v1 {
    uint32_t luid_low; int32_t luid_high;
    uint32_t sources, precise_present_regions_bits;
    uint32_t adopted, close_consumed, close_succeeded, member_count;
    uint32_t adapter_type_bits, reserved[3];
    uint64_t dedicated_video, dedicated_system, shared_system;
    struct r2_win_gpu_call_v1 type, segments, count, close;
    struct r2_win_gpu_member_v1 members[R2_WIN_GPU_MEMBER_CAP];
};
struct r2_win_gpu_report_v1 {
    uint32_t abi, size, status, stop_new;
    uint32_t acquisition_consumed, acquisition_complete, finish_consumed, ownership;
    uint32_t sizing_count_bits, sizing_count_valid, populated_count_bits, populated_count_valid;
    uint32_t adopted_count, close_consumed_count, close_succeeded_count, all_known_once_closed;
    uint32_t pending_liability, native_work_count, fault_count, omitted_fault_count;
    uint32_t creator_pid, creator_tid, remaining_unproven, owner_lifecycle;
    uint64_t intent_serial, creator_creation_100ns;
    int64_t lease_epoch_qpc, qpc_frequency, stop_deadline_qpc, cleanup_deadline_qpc;
    struct r2_win_gpu_fault_v1 primary, secondary;
    struct r2_win_gpu_fault_v1 faults[R2_WIN_GPU_FAULT_CAP];
    struct r2_win_gpu_call_v1 sizing, populate;
    struct r2_win_gpu_adapter_v1 adapters[R2_WIN_GPU_ADAPTER_CAP];
};
/* No caller handles/PIDs/samples/permission flags/callbacks/allocations. This
 * sole acquisition chance is consumed even on failure. It requires ORIGINAL
 * C02 INTENT_HELD, before child birth reservation and STOP_NEW; every native
 * boundary rechecks the same creator handle/PID/TID/creation/intent/lease and
 * ORIGINAL absolute stop/cleanup clocks. No original history or clock resets.
 * One sizing query and at most one populated EnumAdapters3 use all three
 * inclusion flags with reserved zero. Caps 16/8 and <=194 lifetime D3DKMT calls
 * are implementation policies, NOT SDK/hardware maxima or time/RAM grants.
 * Win64 report is 31,536 bytes; native private buffers plus report are statically
 * constrained below 65,536 bytes. Stack locals and identity/QPC work are bounded
 * per call; synchronous wall time and external driver allocations are unproven.
 * All successful, bounded, nonzero, distinct original typed KMT handles are
 * adopted before QueryAdapterInfo. Handles stay private: no PID/LUID reopen.
 * Per adapter: separate ADAPTERTYPE, GETSEGMENTSIZE, PHYSICALADAPTERCOUNT, then
 * bounded GETSEGMENTGROUPSIZE per member. Zeroed SDK buffers, raw NTSTATUS bits,
 * validity, failed partial scalar values and four QPC endpoints are retained.
 * Clocks bracket pre-identity, native entry/return and post-identity; identity
 * query faults also remain in the unchanged C02 report. No GetLastError is
 * substituted for NTSTATUS. Successful raw zero memory is not missing data.
 *
 * A failed populated enumeration has UNDEFINED NumAdapters: the entire native
 * array remains OPAQUE/private, is never iterated and is never speculatively
 * closed. Impossible successful counts, zero/duplicate handles likewise retain
 * ambiguous ownership. STOP_NEW and pending original-process liability remain.
 * There is no fallback/re-enumeration, speculative CloseHandle, retry or reopen.
 * finish_once consumes each known original handle before its sole documented
 * D3DKMTCloseAdapter attempt. Independent remaining closes can proceed after a
 * failed close while original identity/time remain. Failed/ambiguous attempts
 * retain raw outcomes and liability; consumed never means released.
 *
 * finish_once closes ONLY GPU handles. It does not invoke or wire C02 cleanup.
 * A future consumer MUST call it before existing C02 finish can close creator;
 * calling C02 finish first is misuse and this limb rejects the lost identity,
 * retains liability and cannot claim cleanup. Unresolved contexts, native
 * buffers and library MUST remain strongly retained until known completion or
 * an explicit unresolved original-owner handoff (not implemented here).
 * RAW_COMPLETE requires complete raw acquisition, all known handles once
 * successfully closed, and no component fault/pending liability. It proves
 * neither original child exit nor C02 DONE. COPY_OK only means copied bytes.
 * Synchronous stalls are not cancelled/bounded by checks; no pending result
 * accepts capacity. Fault primary/secondary are immutable; first eight faults
 * and saturating omitted counts are a bounded partial history, not a ledger.
 * BUSY acquisition/finish atomically latch a race and the original STOP_NEW;
 * the next guarded operation/copy retains that fault. Copy may materialize
 * that already-latched race but performs no native sampling or attempt reset.
 *
 * Legacy/local/nonlocal/shared/dedicated-system/nonbudget fields are separate
 * observations, never summed into VRAM or assumed disjoint physical capacity.
 * LUID/member indexes are raw mappings only. GPU-PV count 1 can differ from
 * host topology. remaining_unproven always includes hidden/physical topology,
 * immutable capacity, whole RAM/VRAM, full-phase CPU, phase/causal fees, provider
 * closure, pre-load/first-entry provenance and owner exit. All phase fees remain
 * UNKNOWN_NOT_ZERO; no zero-initialized raw field bills. No 16GiB/8GiB PASS,
 * VM_SERVICE_SCOPE, E_PHYSICAL_CAP, OWNER_EXIT or generic authority is emitted.
 * No C04-C12 source/consumer assembly, export-map/mount ABI or loader wiring.
 *
 * copy requires exact sizeof(report), natural alignment, nonwrapping range,
 * disjointness from ALL new private and original owner/RAM/report/guard/stop
 * objects, and caller-provided accessible stable exclusive writable storage.
 * Checks do not establish accessibility/exclusivity. BAD_ARGUMENT/BUSY do not
 * write output. No automatic native call, birth, thread or driver action.
 */
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_gpu_acquire_once_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_gpu_finish_once_v1(void);
R2_WIN_OWNED_EXPORT uint32_t __cdecl route2_win_owned_gpu_copy_report_v1(
    struct r2_win_gpu_report_v1 *out, size_t out_size);
#endif
#endif
