/* Route 2 native contracts: SOURCE_ONLY; v2 producers NOT_IMPLEMENTED.
 * Select exactly one R2_TARGET_WINDOWS_SEED, R2_TARGET_LINUX_START, or
 * R2_TARGET_MOUNT_LIBRARY. There is no implicit/default target.
 * The Linux mount-library branch preserves the reviewed v1 syscall bodies.
 * SYS_* comes ONLY from actual target toolchain headers; no guessed numbers,
 * retries, constructors, entry-point bodies, loaders, or fallback mounts.
 * No compilation, linking, loading, or native operation occurs in this source.
 */
#if defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_MOUNT_LIBRARY)
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#endif
#include "route2_mount_helper.h"

#if defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_MOUNT_LIBRARY)
#include <errno.h>
#include <features.h>
#include <sys/syscall.h>
#include <unistd.h>

#if !defined(__linux__) || !defined(__x86_64__) || !defined(__GLIBC__)
#error "Route 2 Linux targets require the reviewed Linux x86-64 glibc ABI"
#endif
#if __GLIBC__ != 2 || __GLIBC_MINOR__ != 35
#error "This source baseline requires glibc 2.35; a change needs new review/freeze"
#endif
#if !defined(SYS_open_tree) || !defined(SYS_mount_setattr) || !defined(SYS_move_mount) || !defined(SYS_umount2)
#error "Actual target syscall headers must provide every required SYS_* constant"
#endif
#ifndef MOUNT_ATTR_SIZE_VER0
#error "Actual target UAPI must provide mount_attr version zero"
#endif

_Static_assert(sizeof(void *) == 8 && sizeof(long) == 8, "x86-64 LP64 required");
_Static_assert(sizeof(struct mount_attr) == MOUNT_ATTR_SIZE_VER0, "mount_attr ABI changed");
_Static_assert(sizeof(((struct mount_attr *)0)->attr_set) == 8, "mount_attr field ABI changed");
_Static_assert(offsetof(struct mount_attr, attr_set) == 0, "attr_set ABI changed");
_Static_assert(offsetof(struct mount_attr, attr_clr) == 8, "attr_clr ABI changed");
_Static_assert(offsetof(struct mount_attr, propagation) == 16, "propagation ABI changed");
_Static_assert(offsetof(struct mount_attr, userns_fd) == 24, "userns_fd ABI changed");
_Static_assert(sizeof(struct route2_mount_abi_v1) == 40, "description ABI changed");
#endif

/* Only the legacy mount-library target has function definitions.
 * Windows seed and Linux start targets remain dormant declarations only.
 */
#if defined(R2_TARGET_MOUNT_LIBRARY)
int route2_mount_helper_describe_v1(struct route2_mount_abi_v1 *out, size_t size)
{
    if (out == NULL || size != sizeof(*out)) {
        errno = EINVAL;
        return -1;
    }
    *out = (struct route2_mount_abi_v1) {
        1, __GLIBC__, __GLIBC_MINOR__, sizeof(void *), sizeof(long),
        sizeof(struct mount_attr), offsetof(struct mount_attr, attr_set),
        offsetof(struct mount_attr, attr_clr), offsetof(struct mount_attr, propagation),
        offsetof(struct mount_attr, userns_fd)
    };
    return 0;
}

int route2_open_tree(int dfd, const char *path, unsigned int flags)
{
    return (int)syscall(SYS_open_tree, dfd, path, flags);
}

int route2_mount_setattr(int dfd, const char *path, unsigned int flags,
                        const struct mount_attr *attr, size_t size)
{
    if (attr == NULL || size != sizeof(*attr)) {
        errno = EINVAL;
        return -1;
    }
    return (int)syscall(SYS_mount_setattr, dfd, path, flags, attr, size);
}

int route2_move_mount(int from_dfd, const char *from_path,
                     int to_dfd, const char *to_path, unsigned int flags)
{
    return (int)syscall(SYS_move_mount, from_dfd, from_path, to_dfd, to_path, flags);
}

int route2_umount2(const char *path, int flags)
{
    return (int)syscall(SYS_umount2, path, flags);
}
#endif
