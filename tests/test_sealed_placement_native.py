"""D1:静态构建与进程级 syscall 拒绝;不加载 AppArmor 或执行 namespace。"""

import json
import subprocess
from pathlib import Path

import pytest


def test_freeze_produces_static_pair_and_exact_two_profile_blob(tmp_path: Path) -> None:
    from paper_radar.live_evidence.placement_build import freeze_placement
    from tests.site_collector_support import site_configuration

    staged = tmp_path / "staged"
    (staged / "resources").mkdir(parents=True)
    (staged / "resources/resolv.conf").write_bytes(b"nameserver 192.0.2.1\n")
    result = freeze_placement(staged, site_configuration(tmp_path), Path.cwd())
    manifest = json.loads(result.build_manifest.read_bytes())
    assert result.profiles == (
        (
            "paperradar-placement-pre-v1",
            "/usr/libexec/paperradar/live-evidence-runtime/placement-pre",
        ),
        (
            "paperradar-placement-post-v1",
            "/usr/libexec/paperradar/live-evidence-runtime/placement-post",
        ),
    )
    assert result.profile_binary.stat().st_size > 100
    assert "--zstd-compress-level=0" in manifest["parser_flags"]
    assert manifest["abi"] == "v5"
    assert manifest["includes"].keys() == {"abi-5.0"}
    source = result.profile_source.read_text()
    pre, post = source.split("profile paperradar-placement-post-v1", 1)
    assert "deny ptrace (readby, tracedby)," in pre
    assert "userns," in pre
    assert "Px -> paperradar-placement-post-v1," in pre
    assert "Px -> &" not in pre
    assert "deny userns," in post and "deny change_profile," in post
    assert " ux" not in source and " Ux" not in source
    assert '/placement-pre" ix' not in post
    assert '/placement-post" ix' not in post
    for name in ("placement-pre", "placement-post"):
        executed = subprocess.run(
            (str(staged / name), "--unexpected"), capture_output=True, check=False
        )
        assert executed.returncode == 125
        assert executed.stdout == executed.stderr == b""


def test_native_os_entry_refusals_and_filter_keep_threads(
    tmp_path: Path,
) -> None:
    from paper_radar.live_evidence.placement_build import freeze_placement
    from tests.site_collector_support import site_configuration

    staged = tmp_path / "staged"
    (staged / "resources").mkdir(parents=True)
    (staged / "resources/resolv.conf").write_bytes(b"nameserver 192.0.2.1\n")
    freeze_placement(staged, site_configuration(tmp_path), Path.cwd())
    # Test-owned OS adapter calls the same native filter; neither production
    # executable accepts a test target or syscall-probe argument.
    adapter = tmp_path / "filter_adapter.c"
    adapter.write_text(r"""
#define main sealed_main
#include "placement_native.c"
#undef main
#include <pthread.h>
#include <sys/wait.h>
#include <sys/ptrace.h>
static void *thread(void *value) { return value; }
int main(void) {
    untraced();
    require_pre_nnp_zero();
    pid_t traced = fork();
    if (!traced) {
        if (ptrace(PTRACE_TRACEME, 0, NULL, NULL)) _exit(2);
        raise(SIGSTOP);
        untraced();
        _exit(3);
    }
    int trace_status;
    if (waitpid(traced, &trace_status, 0) != traced ||
        !WIFSTOPPED(trace_status)) return 30;
    if (ptrace(PTRACE_CONT, traced, NULL, NULL)) return 31;
    if (waitpid(traced, &trace_status, 0) != traced ||
        !WIFEXITED(trace_status) || WEXITSTATUS(trace_status) != 125) return 32;
    pid_t nnp = fork();
    if (!nnp) {
        if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)) _exit(2);
        require_pre_nnp_zero();
        _exit(3);
    }
    if (waitpid(nnp, &trace_status, 0) != nnp ||
        !WIFEXITED(trace_status) || WEXITSTATUS(trace_status) != 125) return 33;
    install_namespace_filter();
    long calls[] = {SYS_unshare, SYS_setns, SYS_mount, SYS_umount2, SYS_pivot_root,
        SYS_fsopen, SYS_fsconfig, SYS_fsmount, SYS_fspick, SYS_open_tree,
        SYS_move_mount, SYS_mount_setattr, SYS_capset, SYS_ptrace, SYS_setuid,
        SYS_setgid, SYS_setreuid, SYS_setregid, SYS_setresuid, SYS_setresgid,
        SYS_setfsuid, SYS_setfsgid, SYS_setgroups, SYS_process_vm_readv,
        SYS_process_vm_writev, SYS_pidfd_getfd};
    for (unsigned int i = 0; i < sizeof(calls) / sizeof(calls[0]); i++) {
        errno = 0;
        if (syscall(calls[i], 0, 0, 0, 0, 0, 0) != -1 || errno != EPERM) return 20;
    }
    unsigned long flags[] = {CLONE_NEWUSER, CLONE_NEWNS, CLONE_NEWCGROUP,
        CLONE_NEWNET, CLONE_NEWIPC, CLONE_NEWPID, CLONE_NEWUTS, CLONE_NEWTIME};
    for (unsigned int i = 0; i < sizeof(flags) / sizeof(flags[0]); i++) {
        errno = 0;
        if (syscall(SYS_clone, flags[i], 0, 0, 0, 0) != -1 || errno != EPERM) return 21;
    }
    errno = 0;
    if (syscall(SYS_clone3, NULL, 0) != -1 || errno != ENOSYS) return 22;
    /* Landlock ABI query remains possible; the fixture never restricts itself. */
    if (syscall(444, NULL, 0, 1) < 4) return 23;
    pthread_t worker;
    void *value = NULL;
    if (pthread_create(&worker, NULL, thread, (void *)42) ||
        pthread_join(worker, &value) || value != (void *)42) return 24;
    pid_t child = fork();
    if (!child) { syscall(0x40000000 | SYS_getpid); _exit(1); }
    int status;
    if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status) ||
        WTERMSIG(status) != SIGSYS) return 25;
    child = fork();
    if (!child) {
        __asm__ volatile("int $0x80" : : "a" (20) : "memory");
        _exit(1);
    }
    if (waitpid(child, &status, 0) != child || !WIFSIGNALED(status) ||
        WTERMSIG(status) != SIGSYS) return 26;
    return 0;
}
""")
    executable = tmp_path / "filter-adapter"
    result = subprocess.run(
        (
            "/usr/bin/cc",
            "-static",
            "-O2",
            "-pthread",
            "-I",
            str(staged / "placement"),
            str(adapter),
            "-o",
            str(executable),
        ),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    result = subprocess.run((str(executable),), capture_output=True, check=False)
    assert result.returncode == 0
    assert result.stdout == result.stderr == b""


@pytest.mark.parametrize(
    "raw", [b"", b"\x28\xb5\x2f\xfd", b"\x04\x08\x00version\x00\x02\x06\x00\x00\x00"]
)
def test_wire_abi_rejects_unknown_or_compressed_policy(raw: bytes) -> None:
    from paper_radar.live_evidence.placement_build import raw_abi_from_binary

    with pytest.raises(ValueError, match="placement_policy_wire_abi"):
        raw_abi_from_binary(raw)


def test_wire_abi_comes_from_serialized_version_header() -> None:
    from paper_radar.live_evidence.placement_build import raw_abi_from_binary

    assert raw_abi_from_binary(b"\x04\x08\x00version\x00\x02\x05\x00\x00\x00") == "v5"
