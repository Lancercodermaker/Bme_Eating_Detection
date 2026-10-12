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
/* Windows seed has no implemented exports or platform-header dependency. */
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

/* SOURCE_ONLY v2 result names; no provider emits these declarations.
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

#endif
