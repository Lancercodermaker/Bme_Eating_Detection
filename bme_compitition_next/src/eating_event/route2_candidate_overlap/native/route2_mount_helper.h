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
#endif
