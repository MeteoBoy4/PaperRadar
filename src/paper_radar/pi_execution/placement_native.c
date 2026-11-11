/* Only this fixed, static executable receives AppArmor userns permission.
 * The post executable must make NNP/seccomp irreversible before any loader or
 * Python handshake. No NSS, dlopen, shell, setuid or file capabilities. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/audit.h>
#include <linux/capability.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <linux/securebits.h>
#include <sched.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/xattr.h>
#include <unistd.h>
#include "placement_config.h"

#if !defined(__x86_64__) || defined(__ILP32__)
#error sealed placement supports reviewed x86_64 ABI only
#endif
#define LOCKED_BITS (SECBIT_NOROOT | SECBIT_NOROOT_LOCKED | SECBIT_NO_SETUID_FIXUP | SECBIT_NO_SETUID_FIXUP_LOCKED | SECBIT_KEEP_CAPS_LOCKED | SECBIT_NO_CAP_AMBIENT_RAISE | SECBIT_NO_CAP_AMBIENT_RAISE_LOCKED)
static void refuse(void) { _exit(125); }
static void need(int value) { if (!value) refuse(); }

/* Every component is opened without following symlinks. Only root may change
 * the native executable, immutable configuration, resolver source or ancestors. */
static int protected_node(const char *path, int directory_only) {
    char copy[PATH_MAX];
    need(path[0] == '/' && strlen(path) < sizeof(copy));
    strcpy(copy, path + 1);
    int directory = open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    need(directory >= 0);
    char *save = NULL, *part = strtok_r(copy, "/", &save);
    while (part != NULL) {
        need(strcmp(part, ".") && strcmp(part, ".."));
        char *next = strtok_r(NULL, "/", &save);
        int descriptor = openat(directory, part, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | (next ? O_DIRECTORY : 0));
        close(directory);
        need(descriptor >= 0);
        struct stat st;
        need(fstat(descriptor, &st) == 0 && st.st_uid == 0 && !(st.st_mode & 022));
        if (next) need(S_ISDIR(st.st_mode));
        else if (directory_only) need(S_ISDIR(st.st_mode));
        else need(S_ISREG(st.st_mode) && st.st_nlink == 1 && !(st.st_mode & (S_ISUID | S_ISGID)));
        directory = descriptor;
        part = next;
    }
    return directory;
}
static int protected_file(const char *path) { return protected_node(path, 0); }
static int equal_file(const char *path, const unsigned char *expected, size_t length) {
    int descriptor = protected_file(path);
    unsigned char buffer[4096];
    size_t position = 0;
    while (position < length) {
        size_t count = length - position;
        if (count > sizeof(buffer)) count = sizeof(buffer);
        ssize_t got = read(descriptor, buffer, count);
        need(got > 0 && !memcmp(buffer, expected + position, (size_t)got));
        position += (size_t)got;
    }
    need(read(descriptor, buffer, 1) == 0 && lseek(descriptor, 0, SEEK_SET) == 0);
    return descriptor;
}
static void check_profile(const char *expected) {
    FILE *stream = fopen("/proc/self/attr/apparmor/current", "re");
    char buffer[256];
    need(stream != NULL && fgets(buffer, sizeof(buffer), stream) != NULL);
    need(!strcmp(buffer, expected) && fgetc(stream) == EOF);
    fclose(stream);
}
static void identity(const char *fixed, int before_namespace) {
    int descriptor = before_namespace ? protected_file(fixed) : open(fixed, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    need(descriptor >= 0);
    struct stat expected, actual;
    need(fstat(descriptor, &expected) == 0 && stat("/proc/self/exe", &actual) == 0);
    need(expected.st_dev == actual.st_dev && expected.st_ino == actual.st_ino);
    char capability[256];
    errno = 0;
    need(fgetxattr(descriptor, "security.capability", capability, sizeof(capability)) == -1 && errno == ENODATA);
    close(descriptor);
    uid_t r, e, s;
    gid_t gr, ge, gs;
    need(getresuid(&r, &e, &s) == 0 && r == PRODUCT_UID && e == r && s == r && r != 0);
    need(getresgid(&gr, &ge, &gs) == 0 && gr == PRODUCT_GID && ge == gr && gs == gr && gr != 0);

}
static void untraced(void) {
    FILE *stream = fopen("/proc/self/status", "re");
    need(stream != NULL);
    char *line = NULL;
    size_t capacity = 0;
    int found = 0;
    while (getline(&line, &capacity, stream) > 0) {
        int tracer = -1;
        if (sscanf(line, "TracerPid: %d", &tracer) == 1) {
            need(tracer == 0);
            found = 1;
        }
    }
    free(line);
    fclose(stream);
    need(found);
}
static int initial_namespace(const char *kind, unsigned long device, unsigned long inode) {
    char self[80];
    struct stat current;
    need(snprintf(self, sizeof(self), "/proc/self/ns/%s", kind) > 0);
    need(stat(self, &current) == 0);
    return (unsigned long)current.st_dev == device && (unsigned long)current.st_ino == inode;
}
static void require_pre_nnp_zero(void) {
    need(prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) == 0);
}
static void core_zero(void) {
    struct rlimit limit = {0, 0}, check;
    need(setrlimit(RLIMIT_CORE, &limit) == 0 && getrlimit(RLIMIT_CORE, &check) == 0);
    need(check.rlim_cur == 0 && check.rlim_max == 0);
}
static void close_unknown_fds(unsigned int first) {
    need(syscall(SYS_close_range, first, ~0U, 0U) == 0);
}
static void write_self(const char *path, const char *value) {
    int fd = open(path, O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    need(fd >= 0 && write(fd, value, strlen(value)) == (ssize_t)strlen(value));
    need(close(fd) == 0);
}
static int fixed_descriptor(int descriptor, int fixed) {
    if (descriptor != fixed) {
        need(dup3(descriptor, fixed, 0) == fixed);
        close(descriptor);
    } else need(fcntl(descriptor, F_SETFD, 0) == 0);
    return fixed;
}
static void maps(void) {
    char map[96];
    write_self("/proc/self/setgroups", "deny");
    need(snprintf(map, sizeof(map), "%u %u 1\n", PRODUCT_UID, PRODUCT_UID) > 0);
    write_self("/proc/self/uid_map", map);
    need(snprintf(map, sizeof(map), "%u %u 1\n", PRODUCT_GID, PRODUCT_GID) > 0);
    write_self("/proc/self/gid_map", map);
}
static void verify_map(const char *path, unsigned int expected) {
    FILE *stream = fopen(path, "re");
    unsigned int inside, outside, count;
    char extra;
    need(stream != NULL && fscanf(stream, "%u %u %u", &inside, &outside, &count) == 3);
    need(inside == expected && outside == expected && count == 1);
    need(fscanf(stream, " %c", &extra) == EOF);
    fclose(stream);
}
static void caps_empty(void) {
    struct __user_cap_header_struct header = {_LINUX_CAPABILITY_VERSION_3, 0};
    struct __user_cap_data_struct data[2] = {{0}};
    need(syscall(SYS_capget, &header, data) == 0);
    for (int i = 0; i < 2; i++) need(!data[i].effective && !data[i].permitted && !data[i].inheritable);
    for (int cap = 0; cap <= CAP_LAST_CAP; cap++) {
        need(prctl(PR_CAPBSET_READ, cap, 0, 0, 0) == 0);
        need(prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_IS_SET, cap, 0, 0) == 0);
    }
    need(prctl(PR_GET_SECUREBITS, 0, 0, 0, 0) == LOCKED_BITS);
}
static void drop_caps(void) {
    need(prctl(PR_SET_SECUREBITS, LOCKED_BITS, 0, 0, 0) == 0);
    need(prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0) == 0);
    for (int cap = 0; cap <= CAP_LAST_CAP; cap++) need(prctl(PR_CAPBSET_DROP, cap, 0, 0, 0) == 0);
    /* Refuse future kernels with additional bounding capabilities we did not drop. */
    errno = 0;
    need(prctl(PR_CAPBSET_READ, CAP_LAST_CAP + 1, 0, 0, 0) == -1 && errno == EINVAL);
    struct __user_cap_header_struct header = {_LINUX_CAPABILITY_VERSION_3, 0};
    struct __user_cap_data_struct data[2] = {{0}};
    need(syscall(SYS_capset, &header, data) == 0);
    caps_empty();
}
static void descriptor_bytes(int descriptor, const char *path, const unsigned char *expected, size_t length) {
    struct stat opened, linked;
    need(fstat(descriptor, &opened) == 0 && stat(path, &linked) == 0);
    need(S_ISREG(opened.st_mode) && opened.st_nlink == 1 && !(opened.st_mode & 022));
    need(opened.st_dev == linked.st_dev && opened.st_ino == linked.st_ino);
    need((fcntl(descriptor, F_GETFL) & O_ACCMODE) == O_RDONLY);
    need(lseek(descriptor, 0, SEEK_SET) == 0);
    unsigned char buffer[4096];
    size_t position = 0;
    while (position < length) {
        size_t count = length - position;
        if (count > sizeof(buffer)) count = sizeof(buffer);
        ssize_t got = read(descriptor, buffer, count);
        need(got > 0 && !memcmp(buffer, expected + position, (size_t)got));
        position += (size_t)got;
    }
    need(read(descriptor, buffer, 1) == 0 && lseek(descriptor, 0, SEEK_SET) == 0);
}
static void protected_inbox(void) {
    struct stat opened, linked;
    need(fstat(5, &opened) == 0 && stat(INBOX_PATH, &linked) == 0);
    need(S_ISDIR(opened.st_mode) && !(opened.st_mode & 022));
    need(opened.st_dev == linked.st_dev && opened.st_ino == linked.st_ino);
    need((fcntl(5, F_GETFL) & O_ACCMODE) == O_RDONLY);
}
static void resolver_ready(int source) {
    descriptor_bytes(source, RESOLVER_SOURCE, resolver_bytes, sizeof(resolver_bytes));
    int target = open(RESOLVER_TARGET, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    struct stat a, b;
    struct statvfs fs;
    need(target >= 0 && fstat(source, &a) == 0 && fstat(target, &b) == 0);
    need(a.st_dev == b.st_dev && a.st_ino == b.st_ino);
    need(fstatvfs(target, &fs) == 0 && (fs.f_flag & ST_RDONLY));
    unsigned char content[sizeof(resolver_bytes) + 1];
    need(read(target, content, sizeof(content)) == sizeof(resolver_bytes));
    need(!memcmp(content, resolver_bytes, sizeof(resolver_bytes)));
    close(target);
}
static unsigned long source_mount_flags(int descriptor) {
    struct statvfs fs;
    need(fstatvfs(descriptor, &fs) == 0);
    unsigned long flags = 0;
    if (fs.f_flag & ST_NOSUID) flags |= MS_NOSUID;
    if (fs.f_flag & ST_NODEV) flags |= MS_NODEV;
    if (fs.f_flag & ST_NOEXEC) flags |= MS_NOEXEC;
    if (fs.f_flag & ST_SYNCHRONOUS) flags |= MS_SYNCHRONOUS;
    if (fs.f_flag & ST_MANDLOCK) flags |= MS_MANDLOCK;
    if (fs.f_flag & ST_NOATIME) flags |= MS_NOATIME;
    if (fs.f_flag & ST_NODIRATIME) flags |= MS_NODIRATIME;
    if (fs.f_flag & ST_RELATIME) flags |= MS_RELATIME;
    return flags;
}
static void resolver_place(int preflight) {
    int source = fixed_descriptor(equal_file(RESOLVER_SOURCE, resolver_bytes, sizeof(resolver_bytes)), 4);
    need(source_mount_flags(source) == RESOLVER_MOUNT_FLAGS);
    int target = open(RESOLVER_TARGET, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    struct stat target_stat;
    need(target >= 0 && fstat(target, &target_stat) == 0 && S_ISREG(target_stat.st_mode));
    need(target_stat.st_uid != PRODUCT_UID && !(target_stat.st_mode & 022));
    close(target);
    need(initial_namespace("user", INITIAL_USER_DEVICE, INITIAL_USER_INODE));
    need(preflight || initial_namespace("mnt", INITIAL_MOUNT_DEVICE, INITIAL_MOUNT_INODE));
    untraced();
    need(unshare(CLONE_NEWUSER | CLONE_NEWNS) == 0);
    maps();
    need(prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) == 0);
    need(mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) == 0);
    char fdpath[80];
    need(snprintf(fdpath, sizeof(fdpath), "/proc/self/fd/%d", source) > 0);
    need(mount(fdpath, RESOLVER_TARGET, NULL, MS_BIND, NULL) == 0);
    need(mount(NULL, RESOLVER_TARGET, NULL, MS_BIND | MS_REMOUNT | MS_RDONLY | RESOLVER_MOUNT_FLAGS, NULL) == 0);
    need(source == 4);
    need(fcntl(source, F_SETFD, 0) == 0);
    resolver_ready(source);
}

/* The BPF interface is exercised by a test-owned native OS adapter. This is
 * deliberately not a command mode in either production executable. */
#define DENY_SYSCALL(number) BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (number), 0, 1), BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM)
static void install_namespace_filter(void) {
    struct sock_filter code[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP | BPF_JSET | BPF_K, 0x40000000, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        DENY_SYSCALL(SYS_unshare), DENY_SYSCALL(SYS_setns),
        DENY_SYSCALL(SYS_mount), DENY_SYSCALL(SYS_umount2), DENY_SYSCALL(SYS_pivot_root),
        DENY_SYSCALL(SYS_fsopen), DENY_SYSCALL(SYS_fsconfig), DENY_SYSCALL(SYS_fsmount),
        DENY_SYSCALL(SYS_fspick), DENY_SYSCALL(SYS_open_tree), DENY_SYSCALL(SYS_move_mount),
        DENY_SYSCALL(SYS_mount_setattr), DENY_SYSCALL(SYS_capset), DENY_SYSCALL(SYS_ptrace),
        DENY_SYSCALL(SYS_process_vm_writev), DENY_SYSCALL(SYS_process_vm_readv), DENY_SYSCALL(SYS_pidfd_getfd),
        DENY_SYSCALL(SYS_setuid), DENY_SYSCALL(SYS_setgid), DENY_SYSCALL(SYS_setreuid),
        DENY_SYSCALL(SYS_setregid), DENY_SYSCALL(SYS_setresuid), DENY_SYSCALL(SYS_setresgid),
        DENY_SYSCALL(SYS_setfsuid), DENY_SYSCALL(SYS_setfsgid), DENY_SYSCALL(SYS_setgroups),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_clone3, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | ENOSYS),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_clone, 0, 3),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0])),
        BPF_JUMP(BPF_JMP | BPF_JSET | BPF_K, CLONE_NEWUSER | CLONE_NEWNS | CLONE_NEWCGROUP | CLONE_NEWIPC | CLONE_NEWNET | CLONE_NEWPID | CLONE_NEWUTS | CLONE_NEWTIME, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    struct sock_fprog filter = {(unsigned short)(sizeof(code) / sizeof(code[0])), code};
    need(prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0);
    need(prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &filter) == 0);
    need(prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) == 1);
}
static void traced_preflight(const char *parent_text) {
    char *end;
    errno = 0;
    long parent = strtol(parent_text, &end, 10);
    need(!errno && !*end && parent > 1 && parent <= INT_MAX);
    need(prctl(PR_SET_PTRACER, parent, 0, 0, 0) == 0);
    char ready[64];
    int length = snprintf(ready, sizeof(ready), "R %ld\n", (long)getpid());
    need(length > 0 && length < (int)sizeof(ready));
    need(write(STDOUT_FILENO, ready, (size_t)length) == length);
    char byte;
    need(read(STDIN_FILENO, &byte, 1) == 1 && byte == 'G');
    need(read(STDIN_FILENO, &byte, 1) == 0);
    char *argv[] = {"/usr/bin/true", NULL};
    char *env[] = {NULL};
    execve(argv[0], argv, env);
    refuse();
}
static void arguments(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--preflight")) return;
    need(argc == 3);
    if (!strcmp(argv[1], "--preflight-traced")) {
        char *end;
        errno = 0;
        long parent = strtol(argv[2], &end, 10);
        need(!errno && !*end && parent > 1 && parent <= INT_MAX);
        return;
    }
    const char *prefix = "/tmp/paperradar-placement-";
    size_t start = strlen(prefix), length = strlen(argv[1]);
    need(length == start + 8 + strlen("/handshake") && !strncmp(argv[1], prefix, start));
    for (size_t i = start; i < start + 8; i++) need((argv[1][i] >= 'a' && argv[1][i] <= 'z') || (argv[1][i] >= '0' && argv[1][i] <= '9') || argv[1][i] == '_');
    need(!strcmp(argv[1] + start + 8, "/handshake"));
    char *end;
    errno = 0;
    long parent = strtol(argv[2], &end, 10);
    need(!errno && !*end && parent > 1 && parent <= INT_MAX);
    char directory[PATH_MAX];
    memcpy(directory, argv[1], start + 8);
    directory[start + 8] = 0;
    struct stat st;
    need(lstat(directory, &st) == 0 && S_ISDIR(st.st_mode) && st.st_uid == PRODUCT_UID && (st.st_mode & 0777) == 0700);
    need(lstat(argv[1], &st) == 0 && S_ISSOCK(st.st_mode) && st.st_uid == PRODUCT_UID);
}
int main(int argc, char **argv) {
    /* TracerPid is a normal pretrace refusal, NOT a guarantee against a hostile
     * tracer already controlling instructions. AppArmor mainline skips existing
     * unconfined tracers at exec; that threat remains outside the source guard. */
    untraced();
    arguments(argc, argv);
    int traced_probe = argc == 3 && !strcmp(argv[1], "--preflight-traced");
    int normal = argc == 3 && !traced_probe;
    core_zero();
#ifdef PLACEMENT_PRE
    close_unknown_fds(3);
#else
    close_unknown_fds(normal ? 6 : 5);
#endif
    need(clearenv() == 0);
#ifdef PLACEMENT_PRE
    require_pre_nnp_zero();
    identity(PRE_PATH, 1);
    int program = fixed_descriptor(equal_file(PROGRAM_PATH, program_bytes, sizeof(program_bytes)), 3);
    need(program == 3 && fcntl(program, F_SETFD, 0) == 0);
    int post = protected_file(POST_PATH);
    close(post);
    check_profile(PRE_PROFILE);
    if (normal) fixed_descriptor(protected_node(INBOX_PATH, 1), 5);
    resolver_place(!normal);
    drop_caps();
    char *post_argv[] = {POST_PATH, argv[1], argc == 3 ? argv[2] : NULL, NULL};
    char *env[] = {NULL};
    execve(POST_PATH, post_argv, env);
#else
    /* No handshake or dynamic code precedes these irreversible restrictions. */
    install_namespace_filter();
    identity(POST_PATH, 0);
    descriptor_bytes(3, PROGRAM_PATH, program_bytes, sizeof(program_bytes));
    check_profile(POST_PROFILE);
    need(!initial_namespace("user", INITIAL_USER_DEVICE, INITIAL_USER_INODE));
    need(!initial_namespace("mnt", INITIAL_MOUNT_DEVICE, INITIAL_MOUNT_INODE));
    verify_map("/proc/self/uid_map", PRODUCT_UID);
    verify_map("/proc/self/gid_map", PRODUCT_GID);
    caps_empty();
    resolver_ready(4);
    close(4);
    if (normal) protected_inbox();
    need(prctl(PR_SET_DUMPABLE, 1, 0, 0, 0) == 0);
    char *env[] = {NULL};
    if (!normal) close(3);
    if (traced_probe) traced_preflight(argv[2]);
    if (argc == 2) {
        char *probe[] = {"/usr/bin/true", NULL};
        execve(probe[0], probe, env);
    } else {
        char *python[] = {PYTHON_PATH, "-I", "-S", "-B", WRAPPER_PATH, argv[1], argv[2], NULL};
        execve(python[0], python, env);
    }
#endif
    refuse();
    return 125;
}
