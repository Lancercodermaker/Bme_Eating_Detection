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
