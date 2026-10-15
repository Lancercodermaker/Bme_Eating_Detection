/* C03 capture ABI/failure harness: SOURCE ONLY, uncompiled and unexecuted.
 * Link real helper using GNU ld --wrap=clock_gettime,syscall,fstatfs,fstat,
 * read,close. No production hooks. Synthetic fds are never kernel objects.
 * Parent never calls capture. Serial clone3(CLONE_PIDFD), separate address
 * space, gives each child the inherited unconsumed once. No reset/exec/fork
 * fallback, Python, threads, actual procfs, GT, file writes or admission.
 * Requires original absolute monotonic STOP_NS CLEANUP_NS; one invocation
 * clamps them to stricter TEST-ONLY 15s/20s limits, never per-case resets.
 * Supervisor bypasses wrappers, retains original creator pidfd, polls and
 * waitid(P_PIDFD), SIGKILLs through pidfd, and closes once. Unknown/unjoined
 * exit or close failure prevents success and further child births. Blocking
 * kernel calls still cannot be guaranteed finite. Stdout: numeric counts.
 * Future preparation must prove inherited descriptors are controlled 0/1/2
 * only; this source neither enumerates nor closes unknown inherited fds.
 * Only original creator pidfds are acquired. Cases never touch real stdio.
 * RLIMIT_CORE soft/hard zero is set AND read back before any child birth.
 * One numeric stdout line is <=256 bytes; output/flush failure forbids success.
 */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#if !defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_WINDOWS_SEED) || defined(R2_TARGET_MOUNT_LIBRARY)
#error "Harness requires explicit R2_TARGET_LINUX_START only"
#endif
#include "route2_mount_helper.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/magic.h>
#include <linux/openat2.h>
#include <linux/sched.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/vfs.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#if !defined(SYS_clone3) || !defined(SYS_pidfd_send_signal) || !defined(SYS_waitid) || !defined(SYS_close) || !defined(SYS_openat2)
#error "Actual target headers must supply every harness SYS_* constant"
#endif
extern long __real_syscall(long number, ...);
extern int __real_clock_gettime(clockid_t id, struct timespec *out);
#define ROOT_FD 7001
#define LEAF_FD 7002
#define ALL_FIELDS 511u
#define NORMAL_BUDGET 4096u
#define CLEANUP_BUDGET 1024u
#define BILLION UINT64_C(1000000000)

enum case_id {
    NONZERO, ZERO, BAD_OUTPUT, REENTRANT, EXACT_LIMIT, OVER_LIMIT,
    MISSING_LF, PARSE_OVERFLOW, DUPLICATE, READ_EINTR, SHORT_READ, SHORT_READ_CAP,
    SHARED_EINTR, ROOT_NONPROC, LEAF_NONPROC, ROOT_MODE, LEAF_MODE,
    DEV_ALIAS, FSID_ALIAS, NLINK_ALIAS, INODE_ALIAS, NONZERO_SIZE,
    POST_INODE, POST_MTIME, POST_CTIME, ROOT_ELOOP, LEAF_ELOOP,
    LEAF_EXDEV, OPEN_ENOSYS, BEGIN_NEGATIVE, BEGIN_NSEC, BEGIN_OVERFLOW,
    END_NEGATIVE, END_NSEC, END_OVERFLOW, END_REGRESSION,
    COMBINED_FAULTS, CLOSE_EINTR, END_EINTR, BEGIN_ERRNO, CASE_COUNT
};
struct expectation {
    enum case_id id;
    uint32_t status, operation, kind, code, fields;
    int error;
};
#define PASS(ID) {ID,R2_LINUX_CAPTURE_COMPLETE,0,0,0,ALL_FIELDS,0}
#define INV(ID,OP,CODE,FIELDS) {ID,R2_LINUX_CAPTURE_INVARIANT_FAILED,OP,R2_LINUX_CAPTURE_FAULT_INVARIANT,CODE,FIELDS,0}
#define API(ID,OP,ERR,FIELDS) {ID,R2_LINUX_CAPTURE_API_FAILED,OP,R2_LINUX_CAPTURE_FAULT_ERRNO,0,FIELDS,ERR}
#define PARSE(ID,CODE) {ID,R2_LINUX_CAPTURE_PARSE_FAILED,R2_LINUX_CAPTURE_OP_PARSE,R2_LINUX_CAPTURE_FAULT_PARSER,CODE,ALL_FIELDS,0}
#define BUDGET(ID) {ID,R2_LINUX_CAPTURE_ATTEMPTS_EXHAUSTED,R2_LINUX_CAPTURE_OP_READ,R2_LINUX_CAPTURE_FAULT_BUDGET,64,63,0}
static const struct expectation cases[] = {
    PASS(NONZERO), PASS(ZERO), PASS(BAD_OUTPUT), PASS(REENTRANT), PASS(EXACT_LIMIT),
    {OVER_LIMIT,R2_LINUX_CAPTURE_INPUT_TOO_LARGE,R2_LINUX_CAPTURE_OP_READ,
     R2_LINUX_CAPTURE_FAULT_INVARIANT,R2_LINUX_CAPTURE_OVER_BOUND,63,0},
    PARSE(MISSING_LF,R2_LINUX_MEMINFO_TRUNCATED),
    PARSE(PARSE_OVERFLOW,R2_LINUX_MEMINFO_VALUE_OUT_OF_RANGE),
    PARSE(DUPLICATE,R2_LINUX_MEMINFO_DUPLICATE_MEMAVAILABLE),
    BUDGET(READ_EINTR), PASS(SHORT_READ), BUDGET(SHORT_READ_CAP), BUDGET(SHARED_EINTR),
    INV(ROOT_NONPROC,R2_LINUX_CAPTURE_OP_PROC_STATFS,R2_LINUX_CAPTURE_NOT_PROCFS,11),
    INV(LEAF_NONPROC,R2_LINUX_CAPTURE_OP_MEMINFO_STATFS,R2_LINUX_CAPTURE_NOT_PROCFS,47),
    INV(ROOT_MODE,R2_LINUX_CAPTURE_OP_PROC_STAT,R2_LINUX_CAPTURE_NOT_DIRECTORY,15),
    INV(LEAF_MODE,R2_LINUX_CAPTURE_OP_MEMINFO_STAT,R2_LINUX_CAPTURE_NOT_REGULAR,63),
    INV(DEV_ALIAS,R2_LINUX_CAPTURE_OP_MEMINFO_STAT,R2_LINUX_CAPTURE_SOURCE_ALIAS,63),
    INV(FSID_ALIAS,R2_LINUX_CAPTURE_OP_MEMINFO_STATFS,R2_LINUX_CAPTURE_SOURCE_ALIAS,47),
    INV(NLINK_ALIAS,R2_LINUX_CAPTURE_OP_MEMINFO_STAT,R2_LINUX_CAPTURE_SOURCE_ALIAS,63),
    INV(INODE_ALIAS,R2_LINUX_CAPTURE_OP_MEMINFO_STAT,R2_LINUX_CAPTURE_SOURCE_ALIAS,63),
    INV(NONZERO_SIZE,R2_LINUX_CAPTURE_OP_MEMINFO_STAT,R2_LINUX_CAPTURE_NONZERO_PROC_SIZE,63),
    INV(POST_INODE,R2_LINUX_CAPTURE_OP_POST_STAT,R2_LINUX_CAPTURE_IDENTITY_CHANGED,127),
    INV(POST_MTIME,R2_LINUX_CAPTURE_OP_POST_STAT,R2_LINUX_CAPTURE_IDENTITY_CHANGED,127),
    INV(POST_CTIME,R2_LINUX_CAPTURE_OP_POST_STAT,R2_LINUX_CAPTURE_IDENTITY_CHANGED,127),
    API(ROOT_ELOOP,R2_LINUX_CAPTURE_OP_OPEN_PROC,ELOOP,3),
    API(LEAF_ELOOP,R2_LINUX_CAPTURE_OP_OPEN_MEMINFO,ELOOP,15),
    API(LEAF_EXDEV,R2_LINUX_CAPTURE_OP_OPEN_MEMINFO,EXDEV,15),
    API(OPEN_ENOSYS,R2_LINUX_CAPTURE_OP_OPEN_PROC,ENOSYS,3),
    INV(BEGIN_NEGATIVE,R2_LINUX_CAPTURE_OP_BEGIN_CLOCK,R2_LINUX_CAPTURE_BAD_CLOCK,2),
    INV(BEGIN_NSEC,R2_LINUX_CAPTURE_OP_BEGIN_CLOCK,R2_LINUX_CAPTURE_BAD_CLOCK,2),
    INV(BEGIN_OVERFLOW,R2_LINUX_CAPTURE_OP_BEGIN_CLOCK,R2_LINUX_CAPTURE_BAD_CLOCK,2),
    INV(END_NEGATIVE,R2_LINUX_CAPTURE_OP_END_CLOCK,R2_LINUX_CAPTURE_BAD_CLOCK,509),
    INV(END_NSEC,R2_LINUX_CAPTURE_OP_END_CLOCK,R2_LINUX_CAPTURE_BAD_CLOCK,509),
    INV(END_OVERFLOW,R2_LINUX_CAPTURE_OP_END_CLOCK,R2_LINUX_CAPTURE_BAD_CLOCK,509),
    INV(END_REGRESSION,R2_LINUX_CAPTURE_OP_END_CLOCK,R2_LINUX_CAPTURE_CLOCK_REGRESSED,509),
    API(COMBINED_FAULTS,R2_LINUX_CAPTURE_OP_READ,EIO,61),
    {CLOSE_EINTR,R2_LINUX_CAPTURE_CLEANUP_FAILED,R2_LINUX_CAPTURE_OP_CLOSE_MEMINFO,
     R2_LINUX_CAPTURE_FAULT_ERRNO,0,ALL_FIELDS,EINTR},
    {END_EINTR,R2_LINUX_CAPTURE_ATTEMPTS_EXHAUSTED,R2_LINUX_CAPTURE_OP_END_CLOCK,
     R2_LINUX_CAPTURE_FAULT_BUDGET,4,509,EINTR},
    API(BEGIN_ERRNO,R2_LINUX_CAPTURE_OP_BEGIN_CLOCK,EIO,2)
};
#undef PASS
#undef INV
#undef API
#undef PARSE
#undef BUDGET
_Static_assert(sizeof(cases)/sizeof(cases[0]) == CASE_COUNT,"List every case");

struct fixture {
    enum case_id id;
    int active, bad, begin_done, reentered;
    unsigned calls, primary_calls, begin_calls, end_calls;
    unsigned root_opens, leaf_opens, root_fs, leaf_fs, root_stats, leaf_stats;
    unsigned leaf_stat_success, reads, root_closes, leaf_closes;
    unsigned root_ever, leaf_ever, root_owned, leaf_owned;
    size_t length, cursor;
    uint8_t input[16385];
};
static struct fixture fx;
static int error_result(int value) { errno=value; return -1; }
static int bad_mock(void) { fx.bad=1; return error_result(EINVAL); }
static int repeated_ok(const struct r2_linux_start_capture_v1 *r)
{
    struct r2_linux_start_capture_v1 expected;
    memset(&expected,0,sizeof(expected));
    expected.abi=1; expected.size=256;
    expected.status=R2_LINUX_CAPTURE_ALREADY_ATTEMPTED;
    expected.attempt_consumed=1;
    return memcmp(r,&expected,sizeof(expected))==0;
}

int __wrap_clock_gettime(clockid_t id, struct timespec *out)
{
    if (!fx.active || id!=CLOCK_MONOTONIC || out==NULL) return bad_mock();
    ++fx.calls;
    if (!fx.begin_done) {
        struct r2_linux_start_capture_v1 nested;
        unsigned before;
        ++fx.primary_calls; ++fx.begin_calls; fx.begin_done=1;
        if (fx.id==REENTRANT) {
            fx.reentered=1; before=fx.calls;
            memset(&nested,0xa5,sizeof(nested));
            if (route2_linux_start_capture_once_v1(&nested,sizeof(nested))!=
                R2_LINUX_CAPTURE_ALREADY_ATTEMPTED || !repeated_ok(&nested) ||
                fx.calls!=before) fx.bad=1;
        }
        if (fx.id==BEGIN_ERRNO) return error_result(EIO);
        out->tv_sec=fx.id==BEGIN_NEGATIVE ? -1 : 10;
        out->tv_nsec=fx.id==BEGIN_NSEC ? 1000000000L : 100;
        if (fx.id==BEGIN_OVERFLOW) out->tv_sec=INT64_MAX;
    } else {
        ++fx.end_calls;
        if (fx.id==COMBINED_FAULTS) return error_result(EIO);
        if (fx.id==END_EINTR) return error_result(EINTR);
        out->tv_sec=fx.id==END_NEGATIVE ? -1 : fx.id==END_REGRESSION ? 9 : 10;
        out->tv_nsec=fx.id==END_NSEC ? 1000000000L : 500;
        if (fx.id==END_OVERFLOW) out->tv_sec=INT64_MAX;
    }
    return 0;
}

long __wrap_syscall(long number,...)
{
    va_list ap;
    int dirfd;
    const char *path;
    const struct open_how *how;
    size_t size;
    if (!fx.active || number!=SYS_openat2) return bad_mock();
    va_start(ap,number);
    /* Exact actual variadic types: literals decay to char *, &how is mutable. */
    dirfd=va_arg(ap,int); path=va_arg(ap,char *);
    how=va_arg(ap,struct open_how *); size=va_arg(ap,size_t);
    va_end(ap);
    ++fx.calls; ++fx.primary_calls;
    if (!path || !how || size!=sizeof(*how) || how->mode!=0) return bad_mock();
    if (dirfd==AT_FDCWD) {
        ++fx.root_opens;
        if (strcmp(path,"/proc") || fx.root_owned ||
            how->flags!=(uint64_t)(O_PATH|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW) ||
            how->resolve!=(RESOLVE_NO_SYMLINKS|RESOLVE_NO_MAGICLINKS)) return bad_mock();
        if (fx.id==ROOT_ELOOP) return error_result(ELOOP);
        if (fx.id==OPEN_ENOSYS) return error_result(ENOSYS);
        if (fx.id==SHARED_EINTR && fx.root_opens<=2) return error_result(EINTR);
        fx.root_owned=fx.root_ever=1;
        return ROOT_FD;
    }
    if (dirfd!=ROOT_FD || !fx.root_owned || fx.leaf_owned || strcmp(path,"meminfo") ||
        how->flags!=(uint64_t)(O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK) ||
        how->resolve!=(RESOLVE_NO_SYMLINKS|RESOLVE_NO_MAGICLINKS|RESOLVE_NO_XDEV)) return bad_mock();
    ++fx.leaf_opens;
    if (fx.id==LEAF_ELOOP) return error_result(ELOOP);
    if (fx.id==LEAF_EXDEV) return error_result(EXDEV);
    fx.leaf_owned=fx.leaf_ever=1;
    return LEAF_FD;
}

int __wrap_fstatfs(int fd, struct statfs *out)
{
    int words[2]={123,456};
    if (!fx.active || !out || (fd!=ROOT_FD && fd!=LEAF_FD)) return bad_mock();
    ++fx.calls; ++fx.primary_calls;
    if (fd==ROOT_FD) {
        if (!fx.root_owned) return bad_mock();
        ++fx.root_fs;
        if (fx.id==SHARED_EINTR && fx.root_fs<=3) return error_result(EINTR);
    } else {
        if (!fx.leaf_owned) return bad_mock();
        ++fx.leaf_fs;
        if (fx.id==FSID_ALIAS) words[1]=457;
    }
    memset(out,0,sizeof(*out));
    out->f_type=(fd==ROOT_FD && fx.id==ROOT_NONPROC) ||
        (fd==LEAF_FD && fx.id==LEAF_NONPROC) ? 1 : PROC_SUPER_MAGIC;
    _Static_assert(sizeof(words)==sizeof(out->f_fsid),"Synthetic fsid width");
    memcpy(&out->f_fsid,words,sizeof(words));
    return 0;
}

int __wrap_fstat(int fd, struct stat *out)
{
    int leaf=fd==LEAF_FD;
    if (!fx.active || !out || (fd!=ROOT_FD && fd!=LEAF_FD)) return bad_mock();
    ++fx.calls; ++fx.primary_calls;
    if (leaf) {
        if (!fx.leaf_owned) return bad_mock();
        ++fx.leaf_stats;
        if (fx.id==SHARED_EINTR && fx.leaf_stats<=4) return error_result(EINTR);
        ++fx.leaf_stat_success;
    } else {
        if (!fx.root_owned) return bad_mock();
        ++fx.root_stats;
    }
    memset(out,0,sizeof(*out));
    out->st_dev=leaf && fx.id==DEV_ALIAS ? 124 : 123;
    out->st_ino=leaf && fx.id!=INODE_ALIAS ? 2 : 1;
    out->st_mode=leaf ? (S_IFREG|0400) : (S_IFDIR|0500);
    if (!leaf && fx.id==ROOT_MODE) out->st_mode=S_IFREG|0400;
    if (leaf && fx.id==LEAF_MODE) out->st_mode=S_IFIFO|0400;
    out->st_nlink=leaf && fx.id!=NLINK_ALIAS ? 1 : 2;
    out->st_uid=17; out->st_gid=18;
    out->st_size=leaf && fx.id==NONZERO_SIZE ? 1 : 0;
    out->st_mtim.tv_sec=3; out->st_mtim.tv_nsec=4;
    out->st_ctim.tv_sec=5; out->st_ctim.tv_nsec=6;
    if (leaf && fx.leaf_stat_success==2) {
        if (fx.id==POST_INODE) out->st_ino=3;
        if (fx.id==POST_MTIME) ++out->st_mtim.tv_nsec;
        if (fx.id==POST_CTIME) ++out->st_ctim.tv_nsec;
    }
    return 0;
}

ssize_t __wrap_read(int fd, void *out, size_t capacity)
{
    size_t count;
    if (!fx.active || fd!=LEAF_FD || !fx.leaf_owned || !out ||
        capacity==0 || capacity>sizeof(fx.input)) return bad_mock();
    ++fx.calls; ++fx.primary_calls; ++fx.reads;
    if (fx.id==READ_EINTR || fx.id==SHARED_EINTR) return error_result(EINTR);
    if (fx.id==COMBINED_FAULTS) return error_result(EIO);
    count=fx.length-fx.cursor;
    if (count>capacity) count=capacity;
    if ((fx.id==SHORT_READ || fx.id==SHORT_READ_CAP) && count>1) count=1;
    memcpy(out,fx.input+fx.cursor,count);
    fx.cursor+=count;
    return (ssize_t)count;
}

int __wrap_close(int fd)
{
    if (!fx.active) return bad_mock();
    ++fx.calls;
    if (fd==LEAF_FD) {
        ++fx.leaf_closes;
        if (!fx.leaf_owned) return bad_mock();
        fx.leaf_owned=0;
        if (fx.id==CLOSE_EINTR || fx.id==COMBINED_FAULTS) return error_result(EINTR);
    } else if (fd==ROOT_FD) {
        ++fx.root_closes;
        if (!fx.root_owned) return bad_mock();
        fx.root_owned=0;
        if (fx.id==COMBINED_FAULTS) return error_result(EBADF);
    } else return bad_mock();
    return 0;
}

static void prepare_fixture(enum case_id id)
{
    const char *text="MemAvailable: 17 kB\n";
    size_t target;
    memset(&fx,0,sizeof(fx));
    fx.id=id; fx.active=1;
    if (id==ZERO) text="MemAvailable: 0 kB\n";
    if (id==PARSE_OVERFLOW) text="MemAvailable: 18446744073709551615 kB\n";
    if (id==DUPLICATE) text="MemAvailable: 1 kB\nMemAvailable: 2 kB\n";
    if (id==EXACT_LIMIT || id==OVER_LIMIT || id==SHORT_READ_CAP) text="MemAvailable: 1 kB\n";
    fx.length=strlen(text);
    memcpy(fx.input,text,fx.length);
    if (id==MISSING_LF) --fx.length;
    if (id!=EXACT_LIMIT && id!=OVER_LIMIT && id!=SHORT_READ_CAP) return;
    target=id==OVER_LIMIT ? 16385u : 16384u;
    while (target-fx.length>512u) {
        memcpy(fx.input+fx.length,"X: 0\n",5);
        fx.length+=5;
    }
    /* Final valid <=512-byte line: trailing spaces, not a long decimal. */
    memcpy(fx.input+fx.length,"X: 0",4);
    fx.length+=4;
    while (fx.length+1<target) fx.input[fx.length++]=' ';
    fx.input[fx.length++]='\n';
}

#define EXPECT(CONDITION) do { if (!(CONDITION)) ++failures; } while (0)
static unsigned abi_checks(void)
{
    unsigned failures=0;
    EXPECT(sizeof(struct r2_linux_start_capture_v1)==256);
    EXPECT(_Alignof(struct r2_linux_start_capture_v1)==8);
#define OFFSET(F,N) EXPECT(offsetof(struct r2_linux_start_capture_v1,F)==N)
    OFFSET(abi,0); OFFSET(size,4); OFFSET(status,8); OFFSET(sample_valid,12);
    OFFSET(attempt_consumed,16); OFFSET(valid_fields,20);
    OFFSET(primary_attempts,24); OFFSET(read_attempts,28);
    OFFSET(bytes_read,32); OFFSET(eof_seen,36); OFFSET(parser_status,40);
    OFFSET(source_kind,44); OFFSET(primary_operation,48); OFFSET(primary_kind,52);
    OFFSET(primary_code,56); OFFSET(primary_errno_valid,60); OFFSET(primary_errno,64);
    OFFSET(meminfo_close_errno,68); OFFSET(proc_close_errno,72); OFFSET(end_clock_errno,76);
    OFFSET(meminfo_close_state,80); OFFSET(proc_close_state,84);
    OFFSET(end_clock_state,88); OFFSET(value_valid,92);
    OFFSET(monotonic_begin_ns,96); OFFSET(monotonic_end_ns,104);
    OFFSET(memavailable_kib,112); OFFSET(memavailable_bytes,120);
    OFFSET(proc_dev,128); OFFSET(proc_ino,136); OFFSET(meminfo_dev,144);
    OFFSET(meminfo_ino,152); OFFSET(meminfo_size,160); OFFSET(proc_fs_type,168);
    OFFSET(meminfo_fs_type,176); OFFSET(proc_fsid,184); OFFSET(meminfo_fsid,192);
    OFFSET(proc_mode,200); OFFSET(proc_uid,204); OFFSET(meminfo_mode,208);
    OFFSET(meminfo_uid,212); OFFSET(proc_nlink,216); OFFSET(meminfo_nlink,224);
    OFFSET(proc_gid,232); OFFSET(meminfo_gid,236); OFFSET(post_stat_state,240);
    OFFSET(end_clock_attempts,244); OFFSET(end_clock_fault_kind,248);
    OFFSET(end_clock_fault_code,252);
#undef OFFSET
    return failures;
}

static unsigned invalid_output_checks(void)
{
    struct r2_linux_start_capture_v1 object,saved;
    _Alignas(8) uint8_t canary[sizeof(object)+16],previous[sizeof(canary)];
    uintptr_t wrapped=UINTPTR_MAX & ~(uintptr_t)7u;
    unsigned failures=0;
    memset(&object,0xa5,sizeof(object)); memcpy(&saved,&object,sizeof(saved));
    memset(canary,0x5a,sizeof(canary)); memcpy(previous,canary,sizeof(canary));
    EXPECT(route2_linux_start_capture_once_v1(NULL,sizeof(object))==R2_LINUX_CAPTURE_BAD_ARGUMENT);
    EXPECT(route2_linux_start_capture_once_v1(&object,sizeof(object)-1)==R2_LINUX_CAPTURE_BAD_ARGUMENT);
    EXPECT(route2_linux_start_capture_once_v1(&object,sizeof(object)+1)==R2_LINUX_CAPTURE_BAD_ARGUMENT);
    EXPECT(route2_linux_start_capture_once_v1((void *)(canary+1),sizeof(object))==R2_LINUX_CAPTURE_BAD_ARGUMENT);
    EXPECT(route2_linux_start_capture_once_v1((void *)wrapped,sizeof(object))==R2_LINUX_CAPTURE_BAD_ARGUMENT);
    EXPECT(memcmp(&object,&saved,sizeof(object))==0);
    EXPECT(memcmp(canary,previous,sizeof(canary))==0);
    EXPECT(fx.calls==0);
    return failures;
}

static int run_case(const struct expectation *want)
{
    struct guarded_report {
        uint64_t before;
        struct r2_linux_start_capture_v1 report;
        uint64_t after;
    } guarded;
    struct r2_linux_start_capture_v1 again;
    struct r2_linux_start_capture_v1 *r=&guarded.report;
    unsigned failures=abi_checks(),before;
    uint32_t result;
    uint64_t kib;
    prepare_fixture(want->id);
    if (want->id==BAD_OUTPUT) failures+=invalid_output_checks();
    guarded.before=UINT64_C(0x123456789abcdef0);
    guarded.after=UINT64_C(0xfedcba9876543210);
    memset(r,0xa5,sizeof(*r));
    result=route2_linux_start_capture_once_v1(r,sizeof(*r));
    EXPECT(result==want->status && r->status==want->status);
    EXPECT(r->abi==1 && r->size==256 && r->attempt_consumed==1);
    EXPECT(guarded.before==UINT64_C(0x123456789abcdef0));
    EXPECT(guarded.after==UINT64_C(0xfedcba9876543210));
    EXPECT(r->source_kind==R2_LINUX_CAPTURE_SOURCE_FIXED_PROC_MEMINFO);
    EXPECT(r->primary_operation==want->operation && r->primary_kind==want->kind);
    EXPECT(r->primary_code==want->code && r->primary_errno==want->error);
    EXPECT(r->primary_errno_valid==(uint32_t)(want->kind==R2_LINUX_CAPTURE_FAULT_ERRNO || want->id==END_EINTR));
    EXPECT(r->valid_fields==want->fields);
    EXPECT(r->primary_attempts==fx.primary_calls && r->primary_attempts<=64);
    EXPECT(r->read_attempts==fx.reads && r->end_clock_attempts==fx.end_calls);
    EXPECT(fx.calls<=70 && fx.root_closes==fx.root_ever && fx.leaf_closes==fx.leaf_ever);
    EXPECT(!fx.root_owned && !fx.leaf_owned && !fx.bad);
    EXPECT(r->bytes_read==fx.cursor);
    EXPECT(r->eof_seen==!!(want->fields & R2_LINUX_CAPTURE_EOF_VALID));
    EXPECT(r->monotonic_begin_ns==((want->fields & R2_LINUX_CAPTURE_BEGIN_VALID) ? UINT64_C(10000000100) : 0));
    EXPECT(r->monotonic_end_ns==((want->fields & R2_LINUX_CAPTURE_END_VALID) ? UINT64_C(10000000500) : 0));
    EXPECT(r->proc_close_state==(fx.root_ever ?
        (want->id==COMBINED_FAULTS ? R2_LINUX_CAPTURE_FAILED : R2_LINUX_CAPTURE_VALID) :
        R2_LINUX_CAPTURE_UNATTEMPTED));
    EXPECT(r->meminfo_close_state==(fx.leaf_ever ?
        (want->id==COMBINED_FAULTS || want->id==CLOSE_EINTR ?
            R2_LINUX_CAPTURE_FAILED : R2_LINUX_CAPTURE_VALID) : R2_LINUX_CAPTURE_UNATTEMPTED));
    EXPECT(r->post_stat_state==((want->fields & R2_LINUX_CAPTURE_POST_STAT_VALID) ?
        R2_LINUX_CAPTURE_VALID : (want->id==POST_INODE || want->id==POST_MTIME ||
        want->id==POST_CTIME) ? R2_LINUX_CAPTURE_FAILED : R2_LINUX_CAPTURE_UNATTEMPTED));
    if (want->status==R2_LINUX_CAPTURE_COMPLETE) {
        kib=want->id==ZERO ? 0 : want->id==EXACT_LIMIT ? 1 : 17;
        EXPECT(r->sample_valid==1 && r->value_valid==1);
        EXPECT(r->memavailable_kib==kib && r->memavailable_bytes==kib*1024);
        EXPECT(r->parser_status==R2_LINUX_MEMINFO_PARSED);
    } else {
        EXPECT(!r->sample_valid && !r->value_valid);
        EXPECT(!r->memavailable_kib && !r->memavailable_bytes);
    }
    EXPECT(r->meminfo_close_errno==((want->id==COMBINED_FAULTS || want->id==CLOSE_EINTR) ? EINTR : 0));
    EXPECT(r->proc_close_errno==(want->id==COMBINED_FAULTS ? EBADF : 0));
    if (want->kind==R2_LINUX_CAPTURE_FAULT_PARSER) EXPECT(r->parser_status==want->code);
    if (want->fields & R2_LINUX_CAPTURE_PROC_STAT_VALID)
        EXPECT(r->proc_dev==123 && r->proc_ino==1 && r->proc_uid==17 && r->proc_gid==18);
    if (want->fields & R2_LINUX_CAPTURE_MEMINFO_STAT_VALID)
        EXPECT(r->meminfo_ino==(want->id==INODE_ALIAS ? 1u : 2u));
    if (want->id==READ_EINTR || want->id==SHARED_EINTR) {
        EXPECT(r->primary_attempts==64 && r->read_attempts>0);
        EXPECT(!r->bytes_read && !r->eof_seen);
    }
    if (want->id==SHARED_EINTR)
        EXPECT(fx.root_opens==3 && fx.root_fs==4 && fx.leaf_stats==5);
    if (want->id==SHORT_READ) EXPECT(fx.reads==fx.length+1);
    if (want->id==SHORT_READ_CAP)
        EXPECT(r->primary_attempts==64 && r->bytes_read>0 &&
            r->bytes_read<fx.length && r->bytes_read==fx.reads && !r->eof_seen);
    if (want->id==EXACT_LIMIT) EXPECT(r->bytes_read==16384 && r->eof_seen==1 && fx.reads==2);
    if (want->id==OVER_LIMIT) EXPECT(r->bytes_read==16385 && !r->eof_seen && fx.reads==1);
    if (want->id==REENTRANT) EXPECT(fx.reentered==1);
    if (want->id==CLOSE_EINTR) EXPECT(fx.leaf_closes==1 && fx.root_closes==1);
    if (want->id==COMBINED_FAULTS) {
        EXPECT(r->primary_errno_valid==1 && r->primary_errno==EIO);
        EXPECT(r->end_clock_state==R2_LINUX_CAPTURE_FAILED && r->end_clock_errno==EIO);
        EXPECT(r->end_clock_fault_kind==R2_LINUX_CAPTURE_FAULT_ERRNO && !r->end_clock_fault_code);
        EXPECT(fx.leaf_closes==1 && fx.root_closes==1 && fx.end_calls==1);
    }
    if (want->id==END_EINTR) {
        EXPECT(fx.end_calls==4 && r->end_clock_errno==EINTR);
        EXPECT(r->end_clock_fault_kind==R2_LINUX_CAPTURE_FAULT_BUDGET && r->end_clock_fault_code==4);
    }
    if (want->operation==R2_LINUX_CAPTURE_OP_END_CLOCK && want->kind==R2_LINUX_CAPTURE_FAULT_INVARIANT)
        EXPECT(r->end_clock_state==R2_LINUX_CAPTURE_FAILED &&
            r->end_clock_fault_kind==R2_LINUX_CAPTURE_FAULT_INVARIANT && r->end_clock_fault_code==want->code);
    if (want->fields & R2_LINUX_CAPTURE_END_VALID)
        EXPECT(r->end_clock_state==R2_LINUX_CAPTURE_VALID && !r->end_clock_errno &&
            !r->end_clock_fault_kind && !r->end_clock_fault_code);
    before=fx.calls;
    memset(&again,0xa5,sizeof(again));
    EXPECT(route2_linux_start_capture_once_v1(&again,sizeof(again))==R2_LINUX_CAPTURE_ALREADY_ATTEMPTED);
    EXPECT(repeated_ok(&again) && fx.calls==before);
    fx.active=0;
    return failures ? 1 : 0;
}
#undef EXPECT

struct owner {
    uint64_t stop_ns,cleanup_ns;
    unsigned normal_attempts,cleanup_attempts;
    unsigned faults,unknown,joined,close_failures,killed;
};

static int real_now_ns(uint64_t *out)
{
    struct timespec ts;
    unsigned attempt;
    for (attempt=0; attempt<4; ++attempt) {
        if (__real_clock_gettime(CLOCK_MONOTONIC,&ts)==0) {
            uint64_t sec,nsec;
            if (ts.tv_sec<0 || ts.tv_nsec<0 || ts.tv_nsec>=1000000000L) return 0;
            sec=(uint64_t)ts.tv_sec; nsec=(uint64_t)ts.tv_nsec;
            if (sec>(UINT64_MAX-nsec)/BILLION) return 0;
            *out=sec*BILLION+nsec;
            return 1;
        }
        if (errno!=EINTR) return 0;
    }
    return 0;
}

static int decimal_u64(const char *text,uint64_t *out)
{
    uint64_t value=0;
    unsigned digits=0;
    if (!text || !*text) return 0;
    while (*text) {
        unsigned digit=(unsigned char)*text++-(unsigned)'0';
        if (digit>9 || ++digits>20 || value>(UINT64_MAX-digit)/10) return 0;
        value=value*10+digit;
    }
    *out=value;
    return 1;
}

static int owner_step(struct owner *owner,int cleanup)
{
    unsigned *used=cleanup ? &owner->cleanup_attempts : &owner->normal_attempts;
    unsigned limit=cleanup ? CLEANUP_BUDGET : NORMAL_BUDGET;
    if (*used>=limit) return 0;
    ++*used;
    return 1;
}

/* Only original creator pidfd is signaled. ESRCH is not an observed join. */
static int owner_kill(struct owner *owner,int pidfd)
{
    unsigned attempt;
    uint64_t now;
    owner->killed=1;
    for (attempt=0; attempt<4; ++attempt) {
        if (!real_now_ns(&now) || now>=owner->cleanup_ns || !owner_step(owner,1)) return 0;
        if (__real_syscall(SYS_pidfd_send_signal,pidfd,SIGKILL,NULL,0u)==0) return 1;
        if (errno==ESRCH) return 1;
        if (errno!=EINTR) return 0;
    }
    return 0;
}

static void enter_cleanup(struct owner *owner,int pidfd,int *cleanup)
{
    if (*cleanup) return;
    *cleanup=1;
    ++owner->faults;
    if (!owner_kill(owner,pidfd)) ++owner->faults;
}

/* WNOHANG never requests a blocking wait. Poll/EINTR use shared finite
 * budgets and unchanged absolute invocation deadlines. No result is counted
 * passed without verified exit from this creator child and pidfd once-close.
 */
static int supervise_case(struct owner *owner,const struct expectation *test)
{
    struct clone_args args;
    struct pollfd watched;
    siginfo_t info;
    uint64_t now;
    int pidfd=-1,owned_pidfd,cleanup=0,joined=0,case_ok=0,close_ok;
    long child,result;
    memset(&args,0,sizeof(args));
    if (!real_now_ns(&now) || now>=owner->stop_ns || !owner_step(owner,0)) {
        ++owner->faults;
        return 0;
    }
    args.flags=CLONE_PIDFD;
    args.pidfd=(uint64_t)(uintptr_t)&pidfd;
    args.exit_signal=SIGCHLD;
    /* No CLONE_VM and no supplied stack: fork-like separate VM semantics. */
    child=__real_syscall(SYS_clone3,&args,sizeof(args));
    if (child==0) {
        uint64_t child_now;
        if (!real_now_ns(&child_now) || child_now>=owner->stop_ns) _exit(2);
        _exit(run_case(test));
    }
    if (child<0) {
        ++owner->faults;
        return 0; /* No spawn retry, replacement child or fork fallback. */
    }
    if (pidfd<0 || child>INT_MAX) {
        ++owner->faults; ++owner->unknown;
        if (pidfd>=0) {
            owned_pidfd=pidfd; pidfd=-1;
            if (__real_syscall(SYS_close,owned_pidfd)!=0) ++owner->close_failures;
        }
        return 0;
    }
    watched.fd=pidfd; watched.events=POLLIN;
    for (;;) {
        uint64_t deadline,remaining_ms;
        int timeout;
        if (!real_now_ns(&now)) {
            enter_cleanup(owner,pidfd,&cleanup);
            break; /* Clock unknown: no claim of join/deadline continuity. */
        }
        if (!cleanup && (now>=owner->stop_ns || owner->normal_attempts>=NORMAL_BUDGET))
        {
            enter_cleanup(owner,pidfd,&cleanup);
            if (!real_now_ns(&now)) break;
        }
        deadline=cleanup ? owner->cleanup_ns : owner->stop_ns;
        if (now>=deadline || !owner_step(owner,cleanup)) break;
        remaining_ms=(deadline-now)/UINT64_C(1000000);
        if ((deadline-now)%UINT64_C(1000000)) ++remaining_ms;
        timeout=remaining_ms>250 ? 250 : (int)remaining_ms;
        watched.revents=0;
        result=poll(&watched,1,timeout);
        if (result<0) {
            if (errno==EINTR) continue;
            if (cleanup) { ++owner->faults; break; }
            enter_cleanup(owner,pidfd,&cleanup);
            continue;
        }
        if (result==0) continue;
        if (result!=1 || !(watched.revents & POLLIN) ||
            (watched.revents & (POLLERR|POLLNVAL))) {
            if (cleanup) { ++owner->faults; break; }
            enter_cleanup(owner,pidfd,&cleanup);
            continue;
        }
        /* Poll may return after its requested timeout; never admit late work. */
        if (!real_now_ns(&now)) {
            enter_cleanup(owner,pidfd,&cleanup);
            break;
        }
        if (!cleanup && now>=owner->stop_ns) {
            enter_cleanup(owner,pidfd,&cleanup);
            if (!real_now_ns(&now)) break;
        }
        if (now>=owner->cleanup_ns) break;
        if (!owner_step(owner,cleanup)) continue;
        memset(&info,0,sizeof(info));
        result=__real_syscall(SYS_waitid,P_PIDFD,(id_t)pidfd,&info,WEXITED|WNOHANG,NULL);
        if (result<0) {
            if (errno==EINTR) continue;
            if (cleanup) { ++owner->faults; break; }
            enter_cleanup(owner,pidfd,&cleanup);
            continue;
        }
        if (result!=0) {
            if (cleanup) { ++owner->faults; break; }
            enter_cleanup(owner,pidfd,&cleanup);
            continue;
        }
        if (!info.si_pid) continue;
        if (info.si_pid!=(pid_t)child || info.si_signo!=SIGCHLD ||
            (info.si_code!=CLD_EXITED && info.si_code!=CLD_KILLED && info.si_code!=CLD_DUMPED)) {
            enter_cleanup(owner,pidfd,&cleanup);
            break;
        }
        joined=1; ++owner->joined;
        if (!real_now_ns(&now) || now>=owner->stop_ns || now>=owner->cleanup_ns)
            ++owner->faults;
        else case_ok=!cleanup && info.si_code==CLD_EXITED && info.si_status==0;
        break;
    }
    if (!joined) { ++owner->unknown; ++owner->faults; }
    owned_pidfd=pidfd; pidfd=-1; /* Consume before exactly one close attempt. */
    close_ok=__real_syscall(SYS_close,owned_pidfd)==0;
    if (!close_ok) { ++owner->close_failures; ++owner->faults; }
    if (!real_now_ns(&now) || now>=owner->cleanup_ns) {
        ++owner->faults;
        case_ok=0;
    }
    return case_ok && joined && close_ok;
}

int main(int argc,char **argv)
{
    struct owner owner;
    struct rlimit no_core={0,0},core_readback;
    uint64_t now,supplied_stop,supplied_cleanup;
    unsigned index,passed=0,attempted=0,failed=0;
    int written;
    memset(&owner,0,sizeof(owner));
    if (argc!=3 || !decimal_u64(argv[1],&supplied_stop) ||
        !decimal_u64(argv[2],&supplied_cleanup) || !real_now_ns(&now) ||
        supplied_stop<=now || supplied_cleanup<=supplied_stop ||
        now>UINT64_MAX-UINT64_C(20000000000) ||
        setrlimit(RLIMIT_CORE,&no_core)!=0 || getrlimit(RLIMIT_CORE,&core_readback)!=0 ||
        core_readback.rlim_cur!=0 || core_readback.rlim_max!=0) {
        printf("cases_total=%u cases_attempted=0 cases_passed=0 cases_failed=0 owner_faults=1 joined=0 unknown=0 pidfd_close_failures=0\n",(unsigned)CASE_COUNT);
        (void)fflush(stdout);
        return 2;
    }
    owner.stop_ns=supplied_stop<now+UINT64_C(15000000000) ? supplied_stop : now+UINT64_C(15000000000);
    owner.cleanup_ns=supplied_cleanup<now+UINT64_C(20000000000) ? supplied_cleanup : now+UINT64_C(20000000000);
    for (index=0; index<CASE_COUNT; ++index) {
        unsigned before=owner.faults;
        ++attempted;
        if (supervise_case(&owner,&cases[index])) ++passed;
        else { ++failed; break; } /* Unexpected assertion/exit is STOP_NEW. */
        if (owner.unknown || owner.close_failures || owner.faults!=before) break;
    }
    written=printf("cases_total=%u cases_attempted=%u cases_passed=%u cases_failed=%u owner_faults=%u joined=%u unknown=%u pidfd_close_failures=%u\n",
        (unsigned)CASE_COUNT,attempted,passed,failed,owner.faults,owner.joined,
        owner.unknown,owner.close_failures);
    if (fflush(stdout)!=0 || written<1 || written>256) return 1;
    if (!real_now_ns(&now) || now>=owner.cleanup_ns) return 1;
    return attempted==CASE_COUNT && passed==CASE_COUNT && !failed && !owner.faults &&
        !owner.unknown && !owner.close_failures && owner.joined==CASE_COUNT ? 0 : 1;
}
