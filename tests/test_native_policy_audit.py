"""D1:固定 native 操作所需权限和无秘密有限检查点;不加载策略。"""

import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

from paper_radar.live_evidence.placement_build import render_profiles
from paper_radar.pi_execution.placement_protocol import PlacementProgram


def test_pre_can_verify_post_readonly_before_the_mandatory_transition() -> None:
    program = PlacementProgram(
        1001, 1001, Path("/opt/pi"), Path("/var/lib/pi"), Path("/opt/pi.lock"), None
    )
    source = render_profiles(
        program,
        resolver_source=Path("/run/paper-radar/resolv.conf"),
        resolver_target=Path("/run/systemd/resolve/stub-resolv.conf"),
    )
    pre, post = source.split("profile paperradar-placement-post-v1", 1)
    # Native pre opens this root-protected file O_RDONLY before userns or exec.
    assert '  "/usr/libexec/paperradar/live-evidence-runtime/placement-post" r,' in pre
    assert (
        '  "/usr/libexec/paperradar/live-evidence-runtime/placement-post" '
        "Px -> paperradar-placement-post-v1,"
    ) in pre
    assert "deny change_profile," in pre and "deny change_profile," in post
    assert "deny userns," in post and "deny capability," in post
    assert "deny mount," in post and "deny ptrace (readby, tracedby)," in pre


@pytest.mark.parametrize("stage", ["pre", "post"])
def test_valid_preflight_emits_only_fixed_native_checkpoint(
    tmp_path: Path, stage: str
) -> None:
    from paper_radar.live_evidence.placement_build import freeze_placement
    from tests.site_collector_support import site_configuration

    root = tmp_path / "runtime"
    (root / "resources").mkdir(parents=True)
    (root / "resources/resolv.conf").write_bytes(b"nameserver 192.0.2.1\n")
    # No install, policy load, namespace or root paths are created. Both staged
    # executables reject their identity before accessing any protected payload.
    freeze_placement(root, site_configuration(tmp_path), Path.cwd())
    for arguments in (("--preflight",), ("--preflight-traced", "2")):
        result = subprocess.run(
            (str(root / ("placement-" + stage)), *arguments),
            capture_output=True,
            check=False,
        )
        assert result.returncode == 125
        assert result.stdout == b""
        assert result.stderr == f"placement_native_v1:{stage}_identity\n".encode()
    for arguments in (("--unexpected",), ("--preflight-traced", "0")):
        result = subprocess.run(
            (str(root / ("placement-" + stage)), *arguments),
            capture_output=True,
            check=False,
        )
        assert result.returncode == 125
        assert result.stdout == result.stderr == b""
    with (
        tempfile.TemporaryDirectory(prefix="paperradar-placement-") as directory,
        socket.socket(socket.AF_UNIX) as channel,
    ):
        handshake = str(Path(directory) / "handshake")
        channel.bind(handshake)
        result = subprocess.run(
            (str(root / ("placement-" + stage)), handshake, "2"),
            capture_output=True,
            check=False,
        )
        assert result.returncode == 125
        assert result.stdout == result.stderr == b""


@pytest.fixture(scope="module")
def denial_adapter(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from paper_radar.live_evidence.placement_build import freeze_placement
    from tests.site_collector_support import site_configuration

    directory = tmp_path_factory.mktemp("native-denial-adapter")
    root = directory / "runtime"
    (root / "resources").mkdir(parents=True)
    (root / "resources/resolv.conf").write_bytes(b"nameserver 192.0.2.1\n")
    freeze_placement(root, site_configuration(directory), Path.cwd())
    source = directory / "denial.c"
    source.write_text(r"""
#define main sealed_main
#include "placement_native.c"
#undef main
#include <stdarg.h>
static const char *failure;
static size_t read_position[64];
ssize_t __real_write(int fd, const void *value, size_t length);
int __wrap_open(const char *path, int flags, ...) {
    (void)flags;
    if ((!strcmp(failure, "setgroups") && !strcmp(path, "/proc/self/setgroups")) ||
        (!strcmp(failure, "uid_map") && !strcmp(path, "/proc/self/uid_map")) ||
        (!strcmp(failure, "gid_map") && !strcmp(path, "/proc/self/gid_map"))) {
        errno = EACCES;
        return -1;
    }
    if (!strcmp(path, "/")) return 10;
    if (!strcmp(path, RESOLVER_TARGET)) return 11;
    return 42;
}
int __wrap_openat(int fd, const char *path, int flags, ...) {
    (void)fd; (void)path;
    return flags & O_DIRECTORY ? 10 : 12;
}
int __wrap___openat_2(int fd, const char *path, int flags) {
    return __wrap_openat(fd, path, flags);
}
int __wrap_fstat(int fd, struct stat *st) {
    memset(st, 0, sizeof(*st));
    st->st_mode = (fd == 10 ? S_IFDIR | 0755 : S_IFREG | 0644);
    st->st_nlink = 1;
    st->st_dev = 7;
    st->st_ino = 11;
    return 0;
}
int __wrap_stat(const char *path, struct stat *st) {
    __wrap_fstat(12, st);
    if (!strcmp(path, "/proc/self/ns/user")) {
        st->st_dev = INITIAL_USER_DEVICE;
        st->st_ino = INITIAL_USER_INODE;
    } else if (!strcmp(path, "/proc/self/ns/mnt")) {
        st->st_dev = INITIAL_MOUNT_DEVICE;
        st->st_ino = INITIAL_MOUNT_INODE;
    }
    return 0;
}
int __wrap_fstatvfs(int fd, struct statvfs *fs) {
    (void)fd;
    memset(fs, 0, sizeof(*fs));
    fs->f_flag = ST_RDONLY;
    if (RESOLVER_MOUNT_FLAGS & MS_NOSUID) fs->f_flag |= ST_NOSUID;
    if (RESOLVER_MOUNT_FLAGS & MS_NODEV) fs->f_flag |= ST_NODEV;
    if (RESOLVER_MOUNT_FLAGS & MS_NOEXEC) fs->f_flag |= ST_NOEXEC;
    if (RESOLVER_MOUNT_FLAGS & MS_SYNCHRONOUS) fs->f_flag |= ST_SYNCHRONOUS;
    if (RESOLVER_MOUNT_FLAGS & MS_MANDLOCK) fs->f_flag |= ST_MANDLOCK;
    if (RESOLVER_MOUNT_FLAGS & MS_NOATIME) fs->f_flag |= ST_NOATIME;
    if (RESOLVER_MOUNT_FLAGS & MS_NODIRATIME) fs->f_flag |= ST_NODIRATIME;
    if (RESOLVER_MOUNT_FLAGS & MS_RELATIME) fs->f_flag |= ST_RELATIME;
    return 0;
}
ssize_t __wrap_read(int fd, void *buffer, size_t length) {
    if (fd < 0 || fd >= 64) return -1;
    if (fd == 11 && !strcmp(failure, "resolver_verify")) return -1;
    size_t available = sizeof(resolver_bytes) - read_position[fd];
    if (length > available) length = available;
    memcpy(buffer, resolver_bytes + read_position[fd], length);
    read_position[fd] += length;
    return (ssize_t)length;
}
off_t __wrap_lseek(int fd, off_t offset, int whence) {
    (void)whence;
    if (fd < 0 || fd >= 64 || offset != 0) return -1;
    read_position[fd] = 0;
    return 0;
}
int __wrap_dup3(int oldfd, int newfd, int flags) {
    (void)oldfd; (void)flags;
    return newfd;
}
int __wrap_fcntl(int fd, int command, ...) {
    (void)fd;
    return command == F_GETFL ? O_RDONLY : 0;
}
int __wrap_unshare(int flags) {
    if (flags != (CLONE_NEWUSER | CLONE_NEWNS) || !strcmp(failure, "userns")) {
        errno = EPERM;
        return -1;
    }
    return 0;
}
int __wrap_mount(const char *source, const char *target, const char *type,
                 unsigned long flags, const void *data) {
    (void)type; (void)data;
    if ((flags == (MS_REC | MS_PRIVATE) && !strcmp(failure, "mount_private")) ||
        (flags == MS_BIND && !strcmp(failure, "mount_bind")) ||
        ((flags & MS_REMOUNT) && !strcmp(failure, "mount_readonly"))) {
        errno = EACCES;
        return -1;
    }
    if (flags == (MS_REC | MS_PRIVATE)) return strcmp(target, "/");
    if (flags == MS_BIND)
        return strcmp(source, "/proc/self/fd/4") || strcmp(target, RESOLVER_TARGET);
    if (flags == (MS_BIND | MS_REMOUNT | MS_RDONLY | RESOLVER_MOUNT_FLAGS))
        return strcmp(target, RESOLVER_TARGET);
    return -1;
}
ssize_t __wrap_write(int fd, const void *value, size_t length) {
    if (fd == STDERR_FILENO) return __real_write(fd, value, length);
    return (ssize_t)length;
}
int __wrap_close(int fd) { (void)fd; return 0; }
int __wrap_prctl(int option, ...) {
    va_list arguments;
    va_start(arguments, option);
    int first = va_arg(arguments, int);
    va_end(arguments);
    if ((!strcmp(failure, "dumpable") && option == PR_SET_DUMPABLE) ||
        (!strcmp(failure, "securebits") && option == PR_SET_SECUREBITS) ||
        (!strcmp(failure, "ambient") && option == PR_CAP_AMBIENT &&
         first == PR_CAP_AMBIENT_CLEAR_ALL) ||
        (!strcmp(failure, "bounding") && option == PR_CAPBSET_DROP) ||
        (!strcmp(failure, "caps_verify") && option == PR_GET_SECUREBITS)) {
        errno = EPERM;
        return -1;
    }
    if (option == PR_CAPBSET_READ && first == CAP_LAST_CAP + 1) {
        if (!strcmp(failure, "future_capability")) return 0;
        errno = EINVAL;
        return -1;
    }
    return option == PR_GET_SECUREBITS ? LOCKED_BITS : 0;
}
long __wrap_syscall(long number, ...) {
    va_list arguments;
    va_start(arguments, number);
    if (number == SYS_write) {
        int fd = va_arg(arguments, int);
        const void *value = va_arg(arguments, const void *);
        size_t length = va_arg(arguments, size_t);
        va_end(arguments);
        return __real_write(fd, value, length);
    }
    va_end(arguments);
    if (number == SYS_capset && !strcmp(failure, "capset")) {
        errno = EPERM;
        return -1;
    }
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    failure = argv[1];
    diagnostic = 1;
    if (!strcmp(failure, "setgroups") || !strcmp(failure, "uid_map") ||
        !strcmp(failure, "gid_map")) maps();
    else if (!strcmp(failure, "userns") || !strcmp(failure, "dumpable") ||
        !strcmp(failure, "mount_private") || !strcmp(failure, "mount_bind") ||
        !strcmp(failure, "mount_readonly") || !strcmp(failure, "resolver_verify"))
        resolver_place(1);
    else drop_caps();
    return 3;
}
""")
    # All mocked functions are OS boundaries. Neither production binary gains
    # this fixture's operation selection or any syscall adapter mode.
    executable = directory / "denial-adapter"
    compiled = subprocess.run(
        (
            "/usr/bin/cc",
            "-static",
            "-O2",
            "-I",
            str(root / "placement"),
            str(source),
            "-Wl,--wrap=open,--wrap=openat,--wrap=__openat_2,"
            "--wrap=write,--wrap=read,--wrap=close,"
            "--wrap=prctl,--wrap=syscall,--wrap=fstat,--wrap=stat,--wrap=fstatvfs,"
            "--wrap=lseek,--wrap=dup3,--wrap=fcntl,--wrap=unshare,--wrap=mount",
            "-o",
            str(executable),
        ),
        capture_output=True,
        check=False,
    )
    assert compiled.returncode == 0, compiled.stderr.decode()
    return executable


@pytest.mark.parametrize(
    ("failure", "checkpoint"),
    [
        ("setgroups", "pre_setgroups"),
        ("uid_map", "pre_uid_map"),
        ("gid_map", "pre_gid_map"),
        ("securebits", "pre_securebits"),
        ("ambient", "pre_ambient_caps"),
        ("bounding", "pre_bounding_caps"),
        ("future_capability", "pre_bounding_limit"),
        ("capset", "pre_capset"),
        ("caps_verify", "pre_caps_verify"),
        ("userns", "pre_userns"),
        ("dumpable", "pre_dumpable"),
        ("mount_private", "pre_mount_private"),
        ("mount_bind", "pre_mount_bind"),
        ("mount_readonly", "pre_mount_readonly"),
        ("resolver_verify", "pre_resolver_verify"),
    ],
)
def test_namespace_mount_and_capability_denials_have_finite_checkpoints(
    denial_adapter: Path, failure: str, checkpoint: str
) -> None:
    result = subprocess.run(
        (str(denial_adapter), failure), capture_output=True, check=False, timeout=5
    )
    assert result.returncode == 125
    assert result.stdout == b""
    assert result.stderr == f"placement_native_v1:{checkpoint}\n".encode()
