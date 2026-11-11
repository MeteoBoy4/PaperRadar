"""AppArmor 封印包的独立离线 OS 接缝测试;不加载真实策略。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from paper_radar.live_evidence.live_apparmor_kernel import (
    AppArmorKernel,
    AppArmorPolicyError,
    ParserIdentity,
    SealedPolicy,
)

BINARY = b"offline-serialized-policy-v5"
BINARY_SHA = "c972abf36b6e26467cb99aa67c8ec4ed805dfc4bb597a1249a07d7a15fbd97d9"
PROFILES = (
    ("paperradar-placement-pre-v1", "/sealed/runtime/placement-pre"),
    ("paperradar-placement-post-v1", "/sealed/runtime/placement-post"),
)
PARSER = ParserIdentity("/usr/sbin/apparmor_parser", "a" * 64)


def sealed() -> SealedPolicy:
    return SealedPolicy(BINARY, BINARY_SHA, "b" * 64, "v5", PROFILES)


@dataclass
class KernelFixture:
    profiles: dict[str, dict[str, bytes]] = field(default_factory=dict)
    writes: list[tuple[str, bytes]] = field(default_factory=list)
    revision_value: bytes = b"11\n"

    def revision(self) -> bytes:
        return self.revision_value

    def profile_handles(self) -> tuple[str, ...]:
        return tuple(self.profiles)

    def profile_identity(self, handle: str) -> tuple[str, ...]:
        return (handle, "inode-7", "raw_data/23")

    def read_field(self, handle: str, field: str) -> bytes:
        return self.profiles[handle][field]

    def require_writer(self, parser: ParserIdentity) -> None:
        assert parser == PARSER

    def load_binary(self, binary: bytes) -> None:
        self.writes.append(("add", binary))
        self.profiles.update(loaded_profiles())
        self.revision_value = b"12\n"

    def remove_profile(self, name: str) -> None:
        self.writes.append(("remove", name.encode()))
        for key, value in tuple(self.profiles.items()):
            if value["name"] == name.encode() + b"\n":
                del self.profiles[key]
        self.revision_value = str(int(self.revision_value) + 1).encode()


def loaded_profiles() -> dict[str, dict[str, bytes]]:
    return {
        f"entry.{index}": {
            "name": name.encode() + b"\n",
            "mode": b"enforce\n",
            "attach": attachment.encode() + b"\n",
            "sha256": b"c" * 64 + b"\n",
            "raw_abi": b"v5\n",
            "raw_sha256": BINARY_SHA.encode() + b"\n",
            "raw_data": BINARY,
        }
        for index, (name, attachment) in enumerate(PROFILES)
    }


def test_unknown_same_name_refused_before_first_kernel_change() -> None:
    os_boundary = KernelFixture(loaded_profiles())
    os_boundary.profiles["entry.0"]["raw_sha256"] = b"d" * 64 + b"\n"
    kernel = AppArmorKernel(os_boundary, PARSER)
    with pytest.raises(AppArmorPolicyError, match="apparmor_blob_mismatch") as error:
        kernel.load(sealed())
    assert error.value.kind == "conflict"
    assert os_boundary.writes == []


def test_change_during_writer_preflight_refuses_add() -> None:
    class ChangedKernel(KernelFixture):
        def require_writer(self, parser: ParserIdentity) -> None:
            self.profiles = loaded_profiles()
            self.profiles["entry.0"]["raw_data"] = b"foreign-policy"
            self.revision_value = b"15\n"

    os_boundary = ChangedKernel()
    with pytest.raises(AppArmorPolicyError, match="apparmor_blob_mismatch"):
        AppArmorKernel(os_boundary, PARSER).load(sealed())
    assert os_boundary.writes == []


def test_production_writer_refuses_nonroot(monkeypatch: pytest.MonkeyPatch) -> None:
    from paper_radar.live_evidence.live_apparmor_kernel import LinuxKernelPolicyIO

    monkeypatch.setattr("os.geteuid", lambda: 1000)
    with pytest.raises(AppArmorPolicyError, match="apparmor_writer_not_root") as error:
        LinuxKernelPolicyIO().require_writer(PARSER)
    assert error.value.kind == "unavailable"


def test_linux_policy_root_symlink_and_kernel_decompressed_raw_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import live_apparmor_kernel as module

    root = tmp_path / "namespace"
    root.mkdir()
    policy = tmp_path / "policy"
    policy.symlink_to(root, target_is_directory=True)
    (root / "revision").write_bytes(b"17\n")
    raw = root / "raw_data" / "23"
    raw.mkdir(parents=True)
    (raw / "raw_data").write_bytes(BINARY)
    (raw / "sha256").write_text(BINARY_SHA + "\n")
    (raw / "abi").write_bytes(b"v5\n")
    for handle, fields in loaded_profiles().items():
        directory = root / "profiles" / handle
        directory.mkdir(parents=True)
        for field_name, value in fields.items():
            if field_name in {"raw_data", "raw_abi", "raw_sha256"}:
                target = {"raw_abi": "abi", "raw_sha256": "sha256"}.get(
                    field_name, field_name
                )
                (directory / field_name).symlink_to("../../raw_data/23/" + target)
            else:
                (directory / field_name).write_bytes(value)
    monkeypatch.setattr(module, "_POLICY_ROOT", policy)
    module.AppArmorKernel(module.LinuxKernelPolicyIO(), PARSER).verify(sealed())


def test_load_and_remove_are_idempotent_and_preserve_unrelated_profile() -> None:
    unrelated = {
        "unrelated.8": {
            "name": b"unrelated\n",
            "mode": b"enforce\n",
            "attach": b"/other/tool\n",
            "raw_abi": b"v5\n",
            "raw_sha256": b"e" * 64 + b"\n",
            "raw_data": b"unrelated-binary",
        }
    }
    os_boundary = KernelFixture(unrelated.copy())
    kernel = AppArmorKernel(os_boundary, PARSER)
    assert kernel.load(sealed()) is True
    assert kernel.load(sealed()) is False
    kernel.verify(sealed())
    assert os_boundary.writes == [("add", BINARY)]
    assert kernel.remove(sealed()) is True
    assert kernel.remove(sealed()) is False
    assert os_boundary.profiles == unrelated
    assert {value for action, value in os_boundary.writes if action == "remove"} == {
        b"paperradar-placement-pre-v1",
        b"paperradar-placement-post-v1",
    }


@pytest.mark.parametrize(
    ("field_name", "value", "reason"),
    [
        ("raw_data", b"same-hash-metadata-foreign-bytes", "apparmor_blob_mismatch"),
        ("raw_sha256", b"b" * 64 + b"\n", "apparmor_blob_mismatch"),
        ("raw_sha256", b"c" * 64 + b"\n", "apparmor_blob_mismatch"),
        ("mode", b"complain\n", "apparmor_mode_mismatch"),
        ("mode", b"unconfined\n", "apparmor_mode_mismatch"),
        ("raw_abi", b"v9\n", "apparmor_abi_mismatch"),
        ("attach", b"/usr/bin/python3\n", "apparmor_attachment_mismatch"),
    ],
)
def test_real_loaded_drift_is_distinct_from_unavailable(
    field_name: str,
    value: bytes,
    reason: str,
) -> None:
    os_boundary = KernelFixture(loaded_profiles())
    os_boundary.profiles["entry.0"][field_name] = value
    with pytest.raises(AppArmorPolicyError, match=reason) as error:
        AppArmorKernel(os_boundary, PARSER).verify(sealed())
    assert error.value.kind == "drift"


@pytest.mark.parametrize("extra_same_blob", [True, False])
def test_extra_profile_or_attachment_refused_before_add(extra_same_blob: bool) -> None:
    profiles = loaded_profiles()
    extra = profiles["entry.0"].copy()
    extra["name"] = b"unsealed-profile\n"
    if extra_same_blob:
        extra["attach"] = b"/unsealed/attachment\n"
    else:
        extra["raw_sha256"] = b"e" * 64 + b"\n"
    profiles["foreign.77"] = extra
    os_boundary = KernelFixture(profiles)
    with pytest.raises(AppArmorPolicyError, match="apparmor_profile_set_mismatch"):
        AppArmorKernel(os_boundary, PARSER).load(sealed())
    assert os_boundary.writes == []


def test_missing_profile_is_drift_and_partial_load_is_conflict() -> None:
    profiles = loaded_profiles()
    del profiles["entry.1"]
    os_boundary = KernelFixture(profiles)
    kernel = AppArmorKernel(os_boundary, PARSER)
    with pytest.raises(AppArmorPolicyError, match="apparmor_profile_missing") as error:
        kernel.verify(sealed())
    assert error.value.kind == "drift"
    with pytest.raises(AppArmorPolicyError, match="apparmor_partial_policy") as error:
        kernel.load(sealed())
    assert error.value.kind == "conflict"
    assert os_boundary.writes == []


@pytest.mark.parametrize("change", ["revision", "identity", "inventory"])
def test_snapshot_aba_or_revision_change_is_unavailable(change: str) -> None:
    class ChangedRead(KernelFixture):
        calls = 0
        identity_calls = 0
        inventory_calls = 0

        def revision(self) -> bytes:
            self.calls += 1
            if change == "revision" and self.calls > 1:
                return b"13\n"
            return b"11\n"

        def profile_identity(self, handle: str) -> tuple[str, ...]:
            self.identity_calls += 1
            return (
                handle,
                "replacement"
                if change == "identity" and self.identity_calls > 2
                else "original",
            )

        def profile_handles(self) -> tuple[str, ...]:
            self.inventory_calls += 1
            if change == "inventory" and self.inventory_calls > 1:
                return ("entry.1",)
            return super().profile_handles()

    os_boundary = ChangedRead(loaded_profiles())
    with pytest.raises(AppArmorPolicyError, match="apparmor_snapshot_changed") as error:
        AppArmorKernel(os_boundary, PARSER).load(sealed())
    assert error.value.kind == "unavailable"
    assert os_boundary.writes == []


@pytest.mark.parametrize("failure", ["permission", "field_missing", "abi_unknown"])
def test_insufficient_readback_never_becomes_drift_or_success(failure: str) -> None:
    class FailedRead(KernelFixture):
        def read_field(self, handle: str, field: str) -> bytes:
            if field == "raw_data" and failure == "permission":
                raise PermissionError("not authorized")
            return super().read_field(handle, field)

    profiles = loaded_profiles()
    if failure == "field_missing":
        del profiles["entry.0"]["raw_data"]
    if failure == "abi_unknown":
        profiles["entry.0"]["raw_abi"] = b"unrecognized\n"
    os_boundary = FailedRead(profiles)
    with pytest.raises(AppArmorPolicyError, match="apparmor_readback_") as error:
        AppArmorKernel(os_boundary, PARSER).load(sealed())
    assert error.value.kind == "unavailable"
    assert os_boundary.writes == []


@pytest.mark.parametrize("unknown_present", [True, False])
def test_partial_uninstall_requires_explicit_recovery_and_exact_present_blob(
    unknown_present: bool,
) -> None:
    profiles = loaded_profiles()
    del profiles["entry.1"]
    os_boundary = KernelFixture(profiles)
    kernel = AppArmorKernel(os_boundary, PARSER)
    with pytest.raises(AppArmorPolicyError, match="apparmor_partial_policy"):
        kernel.remove(sealed())
    assert os_boundary.writes == []
    if unknown_present:
        profiles["entry.0"]["raw_data"] = b"foreign"
        with pytest.raises(AppArmorPolicyError, match="apparmor_blob_mismatch"):
            kernel.remove(sealed(), allow_partial=True)
        assert os_boundary.writes == []
    else:
        assert kernel.remove(sealed(), allow_partial=True) is True
        assert os_boundary.writes == [("remove", b"paperradar-placement-pre-v1")]
        assert os_boundary.profiles == {}


def test_parser_failure_never_claims_load_success() -> None:
    class FailedParser(KernelFixture):
        def load_binary(self, binary: bytes) -> None:
            raise AppArmorPolicyError("apparmor_parser_refused")

    os_boundary = FailedParser()
    with pytest.raises(AppArmorPolicyError, match="apparmor_parser_refused") as error:
        AppArmorKernel(os_boundary, PARSER).load(sealed())
    assert error.value.kind == "unavailable"
    assert os_boundary.profiles == {}


def test_successful_parser_without_exact_kernel_result_fails() -> None:
    class WrongParser(KernelFixture):
        def load_binary(self, binary: bytes) -> None:
            self.profiles = loaded_profiles()
            self.profiles["entry.0"]["raw_data"] = b"wrong-installed-policy"

    with pytest.raises(AppArmorPolicyError, match="apparmor_blob_mismatch") as error:
        AppArmorKernel(WrongParser(), PARSER).load(sealed())
    assert error.value.kind == "drift"


def test_readback_has_aggregate_byte_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    from paper_radar.live_evidence import live_apparmor_kernel as module

    monkeypatch.setattr(module, "_MAX_SNAPSHOT_BYTES", 32, raising=False)
    os_boundary = KernelFixture(loaded_profiles())
    with pytest.raises(AppArmorPolicyError, match="apparmor_readback_limit") as error:
        AppArmorKernel(os_boundary, PARSER).load(sealed())
    assert error.value.kind == "unavailable"
    assert os_boundary.writes == []


@pytest.fixture
def pinned_parser_fs(monkeypatch: pytest.MonkeyPatch) -> ParserIdentity:
    """固定 parser 的 syscall 元数据/bytes fixture,不依赖宿主安装。"""
    import os

    fixed = Path("/usr/sbin/apparmor_parser")
    original_stat, original_resolve, original_read = (
        Path.stat,
        Path.resolve,
        Path.read_bytes,
    )

    def root_stat(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        if path == fixed:
            return os.stat_result((0o100755, 23, 7, 1, 0, 0, 14, 0, 0, 0))
        value = original_stat(path, follow_symlinks=follow_symlinks)
        if path in fixed.parents:
            values = list(value)
            values[4] = 0
            return os.stat_result(values)
        return value

    def resolve(path: Path, strict: bool = False) -> Path:
        return path if path == fixed else original_resolve(path, strict=strict)

    def read_bytes(path: Path) -> bytes:
        return b"fixture-parser" if path == fixed else original_read(path)

    monkeypatch.setattr("os.geteuid", lambda: 0)
    monkeypatch.setattr(Path, "stat", root_stat)
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    return ParserIdentity(
        "/usr/sbin/apparmor_parser",
        "1ce3196039998dcbd292d4cd9a1b120a8bc26bd3cbbfbb5e8840ef40f876d7df",
    )


@pytest.mark.parametrize(
    ("script", "reason"),
    [
        (
            "import sys; sys.stderr.write('DO_NOT_REPORT'); sys.exit(7)",
            "apparmor_parser_refused",
        ),
        ("import sys; sys.stdout.write('x' * 70000)", "apparmor_parser_output_limit"),
        ("import time; time.sleep(1)", "apparmor_parser_timeout"),
        ("", ""),
    ],
)
def test_fixed_parser_command_has_bounded_output_and_controlled_failures(
    monkeypatch: pytest.MonkeyPatch,
    pinned_parser_fs: ParserIdentity,
    script: str,
    reason: str,
) -> None:
    import subprocess
    import sys
    from typing import Any

    from paper_radar.live_evidence import live_apparmor_kernel as module

    original_popen = subprocess.Popen
    invocations: list[tuple[str, ...]] = []

    def parser_process(argv: tuple[str, ...], **kwargs: Any) -> subprocess.Popen[bytes]:
        invocations.append(argv)
        assert argv == (
            "/usr/sbin/apparmor_parser",
            "--config-file=/dev/null",
            "--add",
            "--binary",
            "--skip-cache",
            "--abort-on-error",
        )
        assert kwargs["env"] == {"LANG": "C", "LC_ALL": "C"}
        assert kwargs["cwd"] == "/"
        assert kwargs["start_new_session"] is True
        source = kwargs["stdin"]
        assert source.read() == BINARY
        source.seek(0)
        return original_popen(
            (sys.executable, "-I", "-S", "-B", "-c", script), **kwargs
        )

    monkeypatch.setattr(subprocess, "Popen", parser_process)
    monkeypatch.setattr(
        module, "_PARSER_TIMEOUT", 0.05 if reason == "apparmor_parser_timeout" else 5.0
    )
    io = module.LinuxKernelPolicyIO()
    io.require_writer(pinned_parser_fs)
    if reason:
        with pytest.raises(AppArmorPolicyError, match=reason) as error:
            io.load_binary(BINARY)
        assert error.value.kind == "unavailable"
        assert "DO_NOT_REPORT" not in str(error.value)
    else:
        io.load_binary(BINARY)
    assert len(invocations) == 1


def test_fixed_parser_missing_and_identity_failures_are_controlled(
    monkeypatch: pytest.MonkeyPatch,
    pinned_parser_fs: ParserIdentity,
) -> None:
    import subprocess
    from typing import Any

    from paper_radar.live_evidence.live_apparmor_kernel import LinuxKernelPolicyIO

    io = LinuxKernelPolicyIO()
    with pytest.raises(AppArmorPolicyError, match="apparmor_parser_identity"):
        io.require_writer(ParserIdentity(pinned_parser_fs.resolved, "f" * 64))
    io.require_writer(pinned_parser_fs)

    def missing_parser(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError("untrusted-free-text")

    monkeypatch.setattr(subprocess, "Popen", missing_parser)
    with pytest.raises(
        AppArmorPolicyError, match="apparmor_parser_unavailable"
    ) as error:
        io.load_binary(BINARY)
    assert "untrusted-free-text" not in str(error.value)


@pytest.mark.parametrize("method", ["load", "remove"])
def test_production_adapter_rejects_write_without_checked_root_identity(
    method: str,
) -> None:
    from paper_radar.live_evidence.live_apparmor_kernel import LinuxKernelPolicyIO

    io = LinuxKernelPolicyIO()
    with pytest.raises(AppArmorPolicyError, match="apparmor_writer_unchecked"):
        if method == "load":
            io.load_binary(BINARY)
        else:
            io.remove_profile("paperradar-placement-pre-v1")


def test_production_remove_only_writes_one_exact_name_to_fixed_interface(
    monkeypatch: pytest.MonkeyPatch,
    pinned_parser_fs: ParserIdentity,
) -> None:
    import os

    from paper_radar.live_evidence.live_apparmor_kernel import LinuxKernelPolicyIO

    writes: list[bytes] = []
    closed: list[int] = []

    def remove_open(path: Path, flags: int) -> int:
        assert path == Path("/sys/kernel/security/apparmor/policy/.remove")
        assert flags == os.O_WRONLY
        return 99999

    def write(fd: int, data: bytes) -> int:
        assert fd == 99999
        writes.append(data)
        return len(data)

    io = LinuxKernelPolicyIO()
    io.require_writer(pinned_parser_fs)
    monkeypatch.setattr(os, "open", remove_open)
    monkeypatch.setattr(os, "write", write)
    monkeypatch.setattr(os, "close", closed.append)
    io.remove_profile("paperradar-placement-pre-v1")
    assert writes == [b"paperradar-placement-pre-v1\x00"]
    assert closed == [99999]
    with pytest.raises(AppArmorPolicyError, match="apparmor_profile_name_invalid"):
        io.remove_profile("../../unrelated")
    assert len(writes) == 1


def test_revision_closes_the_entire_identity_read_window() -> None:
    class ChangedAtFinalIdentity(KernelFixture):
        identity_reads = 0

        def profile_identity(self, handle: str) -> tuple[str, ...]:
            self.identity_reads += 1
            if self.identity_reads == 3:
                self.revision_value = b"19\n"
            return super().profile_identity(handle)

    os_boundary = ChangedAtFinalIdentity(loaded_profiles())
    with pytest.raises(AppArmorPolicyError, match="apparmor_snapshot_changed") as error:
        AppArmorKernel(os_boundary, PARSER).load(sealed())
    assert error.value.kind == "unavailable"
    assert os_boundary.writes == []


def test_compressed_parser_cache_is_refused_before_kernel_change() -> None:
    import hashlib

    compressed = b"\x28\xb5\x2f\xfd" + BINARY
    os_boundary = KernelFixture()
    with pytest.raises(AppArmorPolicyError, match="apparmor_sealed_policy_invalid"):
        policy = SealedPolicy(
            compressed, hashlib.sha256(compressed).hexdigest(), "b" * 64, "v5", PROFILES
        )
        AppArmorKernel(os_boundary, PARSER).load(policy)
    assert os_boundary.writes == []


def test_production_revision_is_one_nonblocking_bounded_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from paper_radar.live_evidence.live_apparmor_kernel import LinuxKernelPolicyIO

    closed: list[int] = []

    def revision_open(path: Path, flags: int) -> int:
        assert path == Path("/sys/kernel/security/apparmor/policy/revision")
        assert flags == os.O_RDONLY | os.O_NONBLOCK
        return 99999

    def read(fd: int, count: int) -> bytes:
        assert (fd, count) == (99999, 128)
        return b"41\n"

    monkeypatch.setattr(os, "open", revision_open)
    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(os, "close", closed.append)
    assert LinuxKernelPolicyIO().revision() == b"41\n"
    assert closed == [99999]


@pytest.mark.parametrize("failure", ["refused", "short_write"])
def test_production_remove_does_not_swallow_write_failures(
    monkeypatch: pytest.MonkeyPatch,
    pinned_parser_fs: ParserIdentity,
    failure: str,
) -> None:
    import os

    from paper_radar.live_evidence.live_apparmor_kernel import LinuxKernelPolicyIO

    closed: list[int] = []

    def remove_open(path: Path, flags: int) -> int:
        return 99999

    def write(fd: int, data: bytes) -> int:
        if failure == "refused":
            raise PermissionError("untrusted detail")
        return 0

    io = LinuxKernelPolicyIO()
    io.require_writer(pinned_parser_fs)
    monkeypatch.setattr(os, "open", remove_open)
    monkeypatch.setattr(os, "write", write)
    monkeypatch.setattr(os, "close", closed.append)
    expected = (
        "apparmor_remove_refused"
        if failure == "refused"
        else "apparmor_remove_incomplete"
    )
    with pytest.raises(AppArmorPolicyError, match=expected) as error:
        io.remove_profile("paperradar-placement-pre-v1")
    assert error.value.kind == "unavailable"
    assert closed == [99999]


def test_remove_requires_post_write_absence() -> None:
    class NoopRemove(KernelFixture):
        def remove_profile(self, name: str) -> None:
            self.writes.append(("remove", name.encode()))

    os_boundary = NoopRemove(loaded_profiles())
    with pytest.raises(AppArmorPolicyError, match="apparmor_snapshot_changed") as error:
        AppArmorKernel(os_boundary, PARSER).remove(sealed())
    assert error.value.kind == "unavailable"
    assert len(os_boundary.writes) == 1


@pytest.mark.parametrize(
    "handle", ["../raw_data/23", "/etc/shadow", "profile/profiles/../x"]
)
def test_production_reader_does_not_offer_arbitrary_root_path(handle: str) -> None:
    from paper_radar.live_evidence.live_apparmor_kernel import LinuxKernelPolicyIO

    with pytest.raises(AppArmorPolicyError, match="apparmor_profile_handle_invalid"):
        LinuxKernelPolicyIO().read_field(handle, "raw_data")
    with pytest.raises(AppArmorPolicyError, match="apparmor_field_unknown"):
        LinuxKernelPolicyIO().read_field("entry.1", handle)


@pytest.mark.parametrize("value", [b"", b"unrecognized\n", b"1\n2\n"])
def test_unknown_revision_is_unavailable(value: bytes) -> None:
    os_boundary = KernelFixture(loaded_profiles(), revision_value=value)
    with pytest.raises(AppArmorPolicyError, match="apparmor_revision_unknown") as error:
        AppArmorKernel(os_boundary, PARSER).load(sealed())
    assert error.value.kind == "unavailable"
    assert os_boundary.writes == []


@pytest.mark.parametrize("present", [False, True])
def test_public_check_accepts_absent_and_exact_without_any_kernel_write(
    present: bool,
) -> None:
    os_boundary = KernelFixture(loaded_profiles() if present else {})
    assert AppArmorKernel(os_boundary, PARSER).check(sealed()) == (
        "exact" if present else "absent"
    )
    assert os_boundary.writes == []


def test_public_check_only_returns_partial_for_explicit_exact_recovery() -> None:
    profiles = loaded_profiles()
    del profiles["entry.1"]
    os_boundary = KernelFixture(profiles)
    kernel = AppArmorKernel(os_boundary, PARSER)
    with pytest.raises(AppArmorPolicyError, match="apparmor_partial_policy") as error:
        kernel.check(sealed())
    assert error.value.kind == "conflict"
    assert kernel.check(sealed(), allow_partial=True) == "partial"
    assert os_boundary.writes == []


@pytest.mark.parametrize("allow_partial", [False, True])
@pytest.mark.parametrize("unknown", ["blob", "mode", "extra_attachment"])
def test_public_check_never_accepts_unknown_existing_policy(
    allow_partial: bool,
    unknown: str,
) -> None:
    profiles = loaded_profiles()
    del profiles["entry.1"]
    if unknown == "blob":
        profiles["entry.0"]["raw_data"] = b"unrecognized-policy"
        reason = "apparmor_blob_mismatch"
    elif unknown == "mode":
        profiles["entry.0"]["mode"] = b"complain\n"
        reason = "apparmor_mode_mismatch"
    else:
        extra = profiles["entry.0"].copy()
        extra["name"] = b"unrecognized-profile\n"
        profiles["foreign.19"] = extra
        reason = "apparmor_profile_set_mismatch"
    os_boundary = KernelFixture(profiles)
    with pytest.raises(AppArmorPolicyError, match=reason) as error:
        AppArmorKernel(os_boundary, PARSER).check(sealed(), allow_partial=allow_partial)
    assert error.value.kind == "conflict"
    assert os_boundary.writes == []


@pytest.mark.parametrize("allow_partial", [False, True])
def test_public_check_never_turns_read_failure_into_absence(
    allow_partial: bool,
) -> None:
    class UnreadableKernel(KernelFixture):
        def read_field(self, handle: str, field: str) -> bytes:
            if field == "raw_data":
                raise PermissionError("raw_data denied")
            return super().read_field(handle, field)

        def require_writer(self, parser: ParserIdentity) -> None:
            raise AssertionError("read-only check attempted writer authorization")

    os_boundary = UnreadableKernel(loaded_profiles())
    with pytest.raises(
        AppArmorPolicyError, match="apparmor_readback_unavailable"
    ) as error:
        AppArmorKernel(os_boundary, PARSER).check(sealed(), allow_partial=allow_partial)
    assert error.value.kind == "unavailable"
    assert os_boundary.writes == []
