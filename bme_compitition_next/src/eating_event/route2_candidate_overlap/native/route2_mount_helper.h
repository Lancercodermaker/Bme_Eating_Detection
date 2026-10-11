/* Route 2 mount ABI v1. Source preparation only; no installed authority.
 * Compile/header/ELF/runtime pins and owner budgets must be reviewed before
 * this library is loaded. No entry point creates approval or GT history.
 */
#ifndef ROUTE2_MOUNT_HELPER_H
#define ROUTE2_MOUNT_HELPER_H

#include <stddef.h>
#include <stdint.h>
#include <linux/mount.h>

#define ROUTE2_EXPORT __attribute__((visibility("default")))

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

ROUTE2_EXPORT int route2_mount_helper_describe_v1(struct route2_mount_abi_v1 *out, size_t size);
ROUTE2_EXPORT int route2_open_tree(int dfd, const char *path, unsigned int flags);
ROUTE2_EXPORT int route2_mount_setattr(int dfd, const char *path, unsigned int flags,
                                      const struct mount_attr *attr, size_t size);
ROUTE2_EXPORT int route2_move_mount(int from_dfd, const char *from_path,
                                   int to_dfd, const char *to_path, unsigned int flags);
ROUTE2_EXPORT int route2_umount2(const char *path, int flags);

#endif
