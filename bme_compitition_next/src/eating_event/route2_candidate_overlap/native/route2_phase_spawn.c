#define _GNU_SOURCE
#include "route2_phase_spawn.h"
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <limits.h>
#include <linux/audit.h>
#include <linux/capability.h>
#include <linux/filter.h>
#include <linux/mount.h>
#include <linux/openat2.h>
#include <linux/sched.h>
#include <linux/seccomp.h>
#include <poll.h>
#include <signal.h>
#include <stddef.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include <asm/unistd.h>

#if !defined(__linux__) || !defined(__x86_64__) || !defined(__LP64__)
#error "route2 phase spawning requires native Linux x86_64 LP64"
#endif
#if !defined(__GLIBC__) || __GLIBC__ != 2 || __GLIBC_MINOR__ != 35
#error "this source unit requires the reviewed glibc 2.35 ABI; dependency closure is still uninstalled"
#endif
#if !defined(SYS_clone3) || !defined(SYS_open_tree) || !defined(SYS_mount_setattr) || !defined(SYS_move_mount) || !defined(SYS_openat2) || !defined(SYS_close_range) || !defined(SYS_execveat) || !defined(SYS_pidfd_open)
#error "reviewed kernel UAPI headers with the required modern syscalls are mandatory"
#endif
#ifndef STATX_MNT_ID
#error "statx mount identities from reviewed kernel UAPI headers are mandatory"
#endif
_Static_assert(sizeof(struct r2_phase_spec) == 32, "phase spec ABI");
_Static_assert(sizeof(struct r2_phase_status) == 208, "phase status ABI");
_Static_assert(sizeof(struct r2_phase_result) == 224, "phase result ABI");

struct child_context {
    int status, held[16];
    struct r2_phase_status failure;
    uint64_t deadline;
};

static void record(struct r2_error *rows, uint32_t *count, int op, int err, int fd)
{
    /* The fixed acquisition/close graph has fewer than sixteen error sites
     * on any path. The original errno is copied before any subsequent call. */
    if (*count < R2_PHASE_ERRORS) rows[(*count)++] = (struct r2_error){op, err, fd};
    else *count = R2_PHASE_ERRORS + 1; /* explicit incomplete capsule; never success */
}
static uint64_t now_ns(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) < 0) return 0;
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}
static int gate_read(int fd, unsigned char expected, uint64_t deadline)
{
    for (;;) {
        uint64_t now = now_ns();
        if (!now) return -1;
        if (now >= deadline) { errno = ETIMEDOUT; return -1; }
        struct pollfd p = {fd, POLLIN, 0};
        uint64_t ms = (deadline - now + 999999ULL) / 1000000ULL;
        int n = poll(&p, 1, ms > 50 ? 50 : (int)ms);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) return -1;
        if (!n) continue;
        unsigned char value;
        ssize_t got = read(fd, &value, 1);
        if (got < 0 && (errno == EAGAIN || errno == EINTR)) continue;
        if (got != 1 || value != expected) { if (got >= 0) errno = EPROTO; return -1; }
        now = now_ns(); if (!now) return -1;
        if (now >= deadline) { errno = ETIMEDOUT; return -1; }
        return 0;
    }
}
static int keep(struct child_context *c, int fd)
{
    for (unsigned i = 0; i < 16; ++i) if (c->held[i] == -1) { c->held[i] = fd; return fd; }
    errno = EOVERFLOW; return -1;
}
static void child_close(struct child_context *c, unsigned i)
{
    int fd = c->held[i]; c->held[i] = -1;
    if (close(fd) < 0) record(c->failure.errors, &c->failure.error_count, R2_CLOSE, errno, fd);
}
static _Noreturn void child_fail(struct child_context *c, int op, int err, int fd)
{
    if (op) record(c->failure.errors, &c->failure.error_count, op, err, fd);
    for (unsigned i = 0; i < 16; ++i)
        if (c->held[i] >= 0 && c->held[i] != c->status) child_close(c, i);
    c->failure.kind = R2_FAILED_STATUS;
    /* Fixed-size numeric capsule only. There is no text/path/GT exception
     * transport and no blocking extension of an exhausted deadline. */
    ssize_t sent = send(c->status, &c->failure, sizeof(c->failure), MSG_NOSIGNAL | MSG_DONTWAIT);
    if (sent != sizeof(c->failure)) {
        record(c->failure.errors, &c->failure.error_count, R2_READY, sent < 0 ? errno : EIO, c->status);
        _exit(125); /* capsule/errno transport UNKNOWN, not complete preservation */
    }
    _exit(126); /* kernel releases the final status fd; it is never retried */
}
#define CHECK(c, call, op, fd) do { if ((call) < 0) { int e = errno; child_fail(c, op, e, fd); } } while (0)

static int fixed_directory(struct child_context *c, const char *path, int operation)
{
    struct open_how how = {.flags = O_PATH | O_DIRECTORY | O_CLOEXEC,
        .resolve = RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS};
    int fd = (int)syscall(SYS_openat2, AT_FDCWD, path, &how, sizeof(how));
    CHECK(c, fd, operation, -1); keep(c, fd);
    struct stat st;
    CHECK(c, fstat(fd, &st), operation, fd);
    if (!S_ISDIR(st.st_mode) || st.st_uid || (st.st_mode & 0022)) child_fail(c, operation, EPERM, fd);
    return fd;
}
static int parent_alive(int fd)
{
    struct pollfd p = {fd, POLLIN, 0};
    int result = poll(&p, 1, 0);
    if (result < 0) return -1;
    if (p.revents) { errno = (p.revents & POLLNVAL) ? EBADF : ESRCH; return -1; }
    return 0;
}

static int install_filter(void)
{
    /* Default deny, native architecture only. Pointer-valued openat2 is not
     * allowed. Read-only open flags and private mmap are inspected directly.
     * No mount/namespace/socket/fork/clone/ptrace/shm/memfd/file mutation API
     * appears in the allowlist. Runtime compatibility is not attested here. */
    struct sock_filter b[256]; unsigned n = 0;
#define STMT(code, k) b[n++] = (struct sock_filter)BPF_STMT(code, k)
#define JUMP(code, k, yes, no) b[n++] = (struct sock_filter)BPF_JUMP(code, k, yes, no)
#define ALLOW(nr) JUMP(BPF_JMP | BPF_JEQ | BPF_K, nr, 0, 1); STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)
#define FD_ONLY(nr, fd) JUMP(BPF_JMP | BPF_JEQ | BPF_K, nr, 0, 4); STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0])); JUMP(BPF_JMP | BPF_JEQ | BPF_K, fd, 0, 1); STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW); STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM)
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch));
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS);
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr));
    JUMP(BPF_JMP | BPF_JSET | BPF_K, __X32_SYSCALL_BIT, 0, 1);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS);
    /* execve is denied; the pre-opened approved ELF is the sole initial exec
     * target. fd 5 and all setup channels close on that successful exec. */
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_execveat, 0, 7);
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0]));
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, R2_PHASE_EXEC, 0, 4);
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[4]));
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, AT_EMPTY_PATH, 0, 2);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    FD_ONLY(SYS_sendto, R2_PHASE_STATUS);
    /* write is limited to the private IPC and setup status descriptors. */
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_write, 0, 5);
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0]));
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, R2_PHASE_IPC, 2, 0);
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, R2_PHASE_STATUS, 1, 0);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW);
    int opens[2] = {SYS_open, SYS_openat};
    for (unsigned i = 0; i < 2; ++i) {
        JUMP(BPF_JMP | BPF_JEQ | BPF_K, opens[i], 0, 4);
        STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args) + (i ? 2 : 1) * 8);
        JUMP(BPF_JMP | BPF_JSET | BPF_K, O_WRONLY | O_RDWR | O_CREAT | O_EXCL | O_TRUNC | O_APPEND | (O_TMPFILE & ~O_DIRECTORY), 1, 0);
        STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW);
        STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    }
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_mmap, 0, 4);
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[3]));
    JUMP(BPF_JMP | BPF_JSET | BPF_K, MAP_SHARED, 1, 0);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_prlimit64, 0, 6);
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[2]));
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, 0, 0, 3);
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[2]) + 4);
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, 0, 0, 1);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    /* fcntl may observe FD/stream flags, never duplicate or change them. */
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_fcntl, 0, 5);
    STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[1]));
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, F_GETFD, 2, 0);
    JUMP(BPF_JMP | BPF_JEQ | BPF_K, F_GETFL, 1, 0);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW);
    ALLOW(SYS_read); ALLOW(SYS_pread64); ALLOW(SYS_readv); ALLOW(SYS_close); ALLOW(SYS_lseek);
    ALLOW(SYS_fstat); ALLOW(SYS_newfstatat); ALLOW(SYS_stat); ALLOW(SYS_lstat); ALLOW(SYS_statx);
    ALLOW(SYS_fstatfs);
    ALLOW(SYS_getdents64); ALLOW(SYS_readlink); ALLOW(SYS_readlinkat); ALLOW(SYS_access);
    ALLOW(SYS_faccessat); ALLOW(SYS_faccessat2); ALLOW(SYS_mprotect); ALLOW(SYS_munmap);
    ALLOW(SYS_mremap); ALLOW(SYS_madvise); ALLOW(SYS_brk); ALLOW(SYS_rt_sigaction);
    ALLOW(SYS_rt_sigprocmask); ALLOW(SYS_rt_sigreturn); ALLOW(SYS_sigaltstack); ALLOW(SYS_futex);
    ALLOW(SYS_arch_prctl); ALLOW(SYS_set_tid_address); ALLOW(SYS_set_robust_list); ALLOW(SYS_rseq);
    ALLOW(SYS_clock_gettime); ALLOW(SYS_clock_nanosleep); ALLOW(SYS_nanosleep); ALLOW(SYS_gettimeofday);
    ALLOW(SYS_poll); ALLOW(SYS_ppoll); ALLOW(SYS_select); ALLOW(SYS_pselect6); ALLOW(SYS_getrandom);
    ALLOW(SYS_getpid); ALLOW(SYS_getppid); ALLOW(SYS_gettid); ALLOW(SYS_getuid); ALLOW(SYS_geteuid);
    ALLOW(SYS_getgid); ALLOW(SYS_getegid); ALLOW(SYS_uname); ALLOW(SYS_sched_getaffinity);
    ALLOW(SYS_getresuid); ALLOW(SYS_getresgid); ALLOW(SYS_getgroups);
    ALLOW(SYS_getrlimit); ALLOW(SYS_getrusage); ALLOW(SYS_exit); ALLOW(SYS_exit_group);
    STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM);
    struct sock_fprog program = {.len = (unsigned short)n, .filter = b};
    return (int)syscall(SYS_seccomp, SECCOMP_SET_MODE_FILTER, 0, &program);
#undef FD_ONLY
#undef ALLOW
#undef STMT
#undef JUMP
}

static _Noreturn void child_main(const struct r2_phase_spec *s, int ipc, int status, int gate, int parent,
                                char *stop_text)
{
    struct child_context c = {.status = status, .failure.abi = R2_PHASE_ABI, .deadline = s->stop_deadline_ns};
    for (unsigned i = 0; i < 16; ++i) c.held[i] = -1;
    keep(&c, ipc); keep(&c, status); keep(&c, gate); keep(&c, parent);
    CHECK(&c, prctl(PR_SET_PDEATHSIG, SIGKILL), R2_SIGNALS, -1);
    CHECK(&c, parent_alive(parent), R2_PARENT_LIVE, parent);
    CHECK(&c, gate_read(gate, 1, c.deadline), R2_BIRTH, gate);
    CHECK(&c, mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL), R2_PRIVATE, -1);
    int source = fixed_directory(&c, R2_PHASE_SOURCE, R2_ROOT_OPEN);
    int target = fixed_directory(&c, R2_PHASE_ROOT, R2_ROOT_OPEN);
    int tree = (int)syscall(SYS_open_tree, source, "", AT_EMPTY_PATH | AT_RECURSIVE | OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC);
    CHECK(&c, tree, R2_TREE, source); keep(&c, tree);
    struct mount_attr attr = {.attr_set = MOUNT_ATTR_RDONLY | MOUNT_ATTR_NOSUID | MOUNT_ATTR_NODEV,
                             .propagation = MS_PRIVATE};
    CHECK(&c, syscall(SYS_mount_setattr, tree, "", AT_EMPTY_PATH | AT_RECURSIVE, &attr, sizeof(attr)), R2_ATTRIBUTES, tree);
    struct stat expected, actual;
    CHECK(&c, fstat(tree, &expected), R2_TREE, tree);
    struct statx detached_mount, published_mount;
    CHECK(&c, syscall(SYS_statx, tree, "", AT_EMPTY_PATH, STATX_MNT_ID, &detached_mount), R2_TREE, tree);
    if (!(detached_mount.stx_mask & STATX_MNT_ID)) child_fail(&c, R2_TREE, EOPNOTSUPP, tree);
    CHECK(&c, syscall(SYS_move_mount, tree, "", target, "", MOVE_MOUNT_F_EMPTY_PATH | MOVE_MOUNT_T_EMPTY_PATH), R2_PUBLISH, tree);
    /* Reopen through this namespace. An inherited/source FD can retain the
     * parent's old vfsmount even after publishing a new mount on that path. */
    int inside = fixed_directory(&c, R2_PHASE_ROOT, R2_ROOT_REOPEN);
    CHECK(&c, fstat(inside, &actual), R2_ROOT_REOPEN, inside);
    CHECK(&c, syscall(SYS_statx, inside, "", AT_EMPTY_PATH, STATX_MNT_ID, &published_mount), R2_ROOT_REOPEN, inside);
    if (!(published_mount.stx_mask & STATX_MNT_ID)) child_fail(&c, R2_ROOT_REOPEN, EOPNOTSUPP, inside);
    if (published_mount.stx_mnt_id != detached_mount.stx_mnt_id) child_fail(&c, R2_ROOT_REOPEN, ESTALE, inside);
    if (actual.st_dev != expected.st_dev || actual.st_ino != expected.st_ino) child_fail(&c, R2_ROOT_REOPEN, ESTALE, inside);
    CHECK(&c, fchdir(inside), R2_CHROOT, inside);
    CHECK(&c, chroot("."), R2_CHROOT, inside);
    CHECK(&c, chdir("/"), R2_CHROOT, inside);
    int executable = open("/runtime/bin/python3", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    CHECK(&c, executable, R2_EXEC_OPEN, -1); keep(&c, executable);
    CHECK(&c, fstat(executable, &actual), R2_EXEC_OPEN, executable);
    unsigned char magic[4]; ssize_t got = pread(executable, magic, sizeof(magic), 0);
    if (got < 0) child_fail(&c, R2_EXEC_OPEN, errno, executable);
    if (!S_ISREG(actual.st_mode) || actual.st_uid || (actual.st_mode & 0022) || got != 4 || memcmp(magic, "\177ELF", 4))
        child_fail(&c, R2_EXEC_OPEN, ENOEXEC, executable);
    int originals[5] = {ipc, status, executable, gate, parent}, copies[5];
    for (unsigned i = 0; i < 5; ++i) {
        copies[i] = fcntl(originals[i], F_DUPFD_CLOEXEC, 16);
        CHECK(&c, copies[i], R2_DUP, originals[i]); keep(&c, copies[i]);
    }
    c.status = copies[1];
    for (unsigned i = 0; i < 16; ++i) if (c.held[i] >= 0) {
        int needed = 0;
        for (unsigned j = 0; j < 5; ++j) if (c.held[i] == copies[j]) needed = 1;
        if (!needed) child_close(&c, i);
    }
    if (c.failure.error_count) child_fail(&c, 0, 0, -1);
    CHECK(&c, syscall(SYS_close_range, 0U, 15U, 0U), R2_CLOSE_RANGE, -1);
    int destinations[5] = {R2_PHASE_IPC, R2_PHASE_STATUS, R2_PHASE_EXEC, R2_PHASE_PERMIT, R2_PHASE_PARENT};
    for (unsigned i = 0; i < 5; ++i) {
        CHECK(&c, dup3(copies[i], destinations[i], i == 0 ? 0 : O_CLOEXEC), R2_DUP, copies[i]);
        keep(&c, destinations[i]); if (i == 1) c.status = R2_PHASE_STATUS;
    }
    for (unsigned i = 0; i < 16; ++i) if (c.held[i] > 7) child_close(&c, i);
    if (c.failure.error_count) child_fail(&c, 0, 0, -1);
    CHECK(&c, syscall(SYS_close_range, 8U, UINT_MAX, 0U), R2_CLOSE_RANGE, -1);
    struct sigaction action = {.sa_handler = SIG_DFL}; sigemptyset(&action.sa_mask);
    for (int sig = 1; sig < NSIG; ++sig) if (sig != SIGKILL && sig != SIGSTOP) {
        if (sigaction(sig, &action, NULL) < 0 && errno != EINVAL) child_fail(&c, R2_SIGNALS, errno, -1);
    }
    action.sa_handler = SIG_IGN; CHECK(&c, sigaction(SIGPIPE, &action, NULL), R2_SIGNALS, -1);
    sigset_t mask; sigemptyset(&mask); CHECK(&c, sigprocmask(SIG_SETMASK, &mask, NULL), R2_SIGNALS, -1);
    struct rlimit limit = {s->as_limit_bytes, s->as_limit_bytes};
    CHECK(&c, setrlimit(RLIMIT_AS, &limit), R2_LIMITS, -1);
    limit.rlim_cur = limit.rlim_max = 0;
    int zero_limits[2] = {RLIMIT_CORE, RLIMIT_FSIZE};
    for (unsigned i = 0; i < 2; ++i) CHECK(&c, setrlimit(zero_limits[i], &limit), R2_LIMITS, -1);
    /* Inherit the existing RLIMIT_NPROC policy. A UID-global zero limit can
     * flag PF_NPROC_EXCEEDED on the UID 65534 transition and reject exec with
     * EAGAIN when ambient same-usernamespace tasks exist. Seccomp denies all
     * task creation; the original cgroup's TasksMax=2 authority remains required. */
    limit.rlim_cur = limit.rlim_max = 64; CHECK(&c, setrlimit(RLIMIT_NOFILE, &limit), R2_LIMITS, -1);
    CHECK(&c, sethostname("route2-phase", 12), R2_CREDENTIALS, -1);
    CHECK(&c, setgroups(0, NULL), R2_CREDENTIALS, -1);
    CHECK(&c, prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0), R2_CREDENTIALS, -1);
    CHECK(&c, prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0), R2_CREDENTIALS, -1);
    for (int cap = 0; cap <= CAP_LAST_CAP; ++cap) CHECK(&c, prctl(PR_CAPBSET_DROP, cap, 0, 0, 0), R2_CREDENTIALS, -1);
    CHECK(&c, setresgid(65534, 65534, 65534), R2_CREDENTIALS, -1);
    CHECK(&c, setresuid(65534, 65534, 65534), R2_CREDENTIALS, -1);
    struct __user_cap_header_struct header = {_LINUX_CAPABILITY_VERSION_3, 0};
    struct __user_cap_data_struct caps[2] = {{0}, {0}};
    CHECK(&c, syscall(SYS_capset, &header, caps), R2_CREDENTIALS, -1);
    CHECK(&c, prctl(PR_SET_DUMPABLE, 0), R2_CREDENTIALS, -1);
    CHECK(&c, prctl(PR_SET_PDEATHSIG, SIGKILL), R2_SIGNALS, -1);
    /* UID changes clear PDEATHSIG. The original parent's kernel pidfd closes
     * that race: death before rearm is readable; death after rearm kills us. */
    CHECK(&c, parent_alive(R2_PHASE_PARENT), R2_PARENT_LIVE, R2_PHASE_PARENT);
    CHECK(&c, install_filter(), R2_SECCOMP, -1);
    struct r2_phase_status ready = {.abi = R2_PHASE_ABI, .kind = R2_READY_STATUS};
    ssize_t sent = write(R2_PHASE_STATUS, &ready, sizeof(ready));
    if (sent != sizeof(ready)) child_fail(&c, R2_READY, sent < 0 ? errno : EIO, R2_PHASE_STATUS);
    CHECK(&c, gate_read(R2_PHASE_PERMIT, 2, c.deadline), R2_PERMIT, R2_PHASE_PERMIT);
    CHECK(&c, parent_alive(R2_PHASE_PARENT), R2_PARENT_LIVE, R2_PHASE_PARENT);
    char *argv[] = {"/runtime/bin/python3", "-I", "-S", "-B",
        "/source/src/eating_event/route2_candidate_overlap/phase_worker_entry.py", stop_text, NULL};
    char *env[] = {"PATH=/runtime/bin", "HOME=/readonly", "TMPDIR=/readonly", "TMP=/readonly", "TEMP=/readonly",
        "XDG_CACHE_HOME=/readonly", "XDG_CONFIG_HOME=/readonly", "XDG_DATA_HOME=/readonly", "XDG_RUNTIME_DIR=/readonly",
        "PYTHONDONTWRITEBYTECODE=1", "PYTHONNOUSERSITE=1", "PYTHONPYCACHEPREFIX=/readonly",
        "OMP_NUM_THREADS=1", "OMP_THREAD_LIMIT=1", "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1",
        "BLIS_NUM_THREADS=1", "NUMEXPR_NUM_THREADS=1", "VECLIB_MAXIMUM_THREADS=1", "LC_ALL=C", NULL};
    (void)syscall(SYS_execveat, R2_PHASE_EXEC, "", argv, env, AT_EMPTY_PATH);
    child_fail(&c, R2_EXECVE, errno, R2_PHASE_EXEC);
}

uint32_t route2_phase_spawn_abi(uint32_t spec_size, uint32_t result_size)
{
    return spec_size == sizeof(struct r2_phase_spec) && result_size == sizeof(struct r2_phase_result) ? R2_PHASE_ABI : 0;
}
static void parent_close(int *fd, struct r2_phase_result *r)
{
    if (*fd < 0) return;
    int value = *fd; *fd = -1;
    if (close(value) < 0) record(r->errors, &r->error_count, R2_CLOSE, errno, value);
}
int route2_phase_spawn(const struct r2_phase_spec *s, struct r2_phase_result *r)
{
    if (!r) { errno = EINVAL; return -1; }
    memset(r, 0, sizeof(*r)); r->abi = R2_PHASE_ABI; r->size = sizeof(*r);
    r->pid = r->pidfd = r->ipc_fd = r->status_fd = r->permit_fd = -1;
    struct sigaction child_action; struct rlimit inherited;
    uint64_t now = now_ns();
    if (!now) { record(r->errors, &r->error_count, R2_CLOCK, errno, -1); return -1; }
    if (!s || s->abi != R2_PHASE_ABI || s->size != sizeof(*s) || !s->as_limit_bytes || s->as_limit_bytes > (1ULL << 31)
        || !now || now >= s->stop_deadline_ns || s->stop_deadline_ns >= s->cleanup_deadline_ns || getuid() || geteuid()) {
        record(r->errors, &r->error_count, R2_VALIDATE, EINVAL, -1); return -1;
    }
    if (sigaction(SIGCHLD, NULL, &child_action) < 0 || getrlimit(RLIMIT_AS, &inherited) < 0) {
        record(r->errors, &r->error_count, R2_VALIDATE, errno, -1); return -1;
    }
    if (child_action.sa_handler != SIG_DFL || (child_action.sa_flags & SA_NOCLDWAIT)
        || inherited.rlim_cur != s->as_limit_bytes || inherited.rlim_max != s->as_limit_bytes) {
        record(r->errors, &r->error_count, R2_VALIDATE, EPERM, -1); return -1;
    }
    int pairs[3][2] = {{-1, -1}, {-1, -1}, {-1, -1}}, parent = -1;
    /* This self-pidfd is a parent-liveness anchor, never a fallback for the
     * child's mandatory CLONE_PIDFD and never passed to project Python. */
    parent = (int)syscall(SYS_pidfd_open, getpid(), 0);
    if (parent < 0) { record(r->errors, &r->error_count, R2_PARENT_OPEN, errno, -1); goto finish; }
    for (unsigned i = 0; i < 3; ++i) if (socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0, pairs[i]) < 0) {
        record(r->errors, &r->error_count, R2_SOCKET, errno, -1); goto finish;
    }
    char stop_text[21]; unsigned pos = sizeof(stop_text) - 1; stop_text[pos] = '\0';
    uint64_t value = s->stop_deadline_ns;
    do { stop_text[--pos] = (char)('0' + value % 10); value /= 10; } while (value);
    struct clone_args clone = {.flags = CLONE_PIDFD | CLONE_NEWNS | CLONE_NEWIPC | CLONE_NEWNET | CLONE_NEWPID | CLONE_NEWUTS | CLONE_NEWCGROUP,
        .pidfd = (uint64_t)(uintptr_t)&r->pidfd, .exit_signal = SIGCHLD};
    long pid = syscall(SYS_clone3, &clone, sizeof(clone));
    if (!pid) child_main(s, pairs[0][1], pairs[1][1], pairs[2][1], parent, &stop_text[pos]);
    if (pid < 0) { record(r->errors, &r->error_count, R2_CLONE, errno, -1); goto finish; }
    r->pid = (int32_t)pid;
    r->ipc_fd = pairs[0][0]; pairs[0][0] = -1;
    r->status_fd = pairs[1][0]; pairs[1][0] = -1;
    r->permit_fd = pairs[2][0]; pairs[2][0] = -1;
    /* clone3 acquired the original pidfd atomically. Only now may the native
     * child leave its first gate. No pidfd_open/numeric-PID fallback exists. */
    unsigned char birth = 1;
    ssize_t sent = send(r->permit_fd, &birth, 1, MSG_NOSIGNAL | MSG_DONTWAIT);
    if (sent != 1) record(r->errors, &r->error_count, R2_BIRTH, sent < 0 ? errno : EIO, r->permit_fd);
finish:
    for (unsigned i = 0; i < 3; ++i) for (unsigned j = 0; j < 2; ++j) parent_close(&pairs[i][j], r);
    parent_close(&parent, r);
    return r->error_count ? -1 : 0;
}
