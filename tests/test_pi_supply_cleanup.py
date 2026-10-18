"""清理计划经公共服务保存不可变依据,不删除安装。"""

from pathlib import Path
from typing import TypedDict

from tests.pi_supply_support import inputs, prepare


class Roots(TypedDict):
    data_root: Path
    config_root: Path
    material_root: Path


def test_dry_run_saves_canonical_plan_without_changing_selection_or_tree(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import (
        activate_supply,
        create_cleanup_plan,
        show_cleanup_plan,
    )

    source = inputs(tmp_path)
    installed = prepare(tmp_path, source)
    activate_supply(source[0], installed.supply_id, source[1])
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    assert plan.candidates == ()
    assert plan.present_count == 1
    assert plan.items[0].protection == ("current", "latest_install_check")
    assert plan.items[0].actual_tree_hash == plan.items[0].expected_tree_hash
    assert (
        show_cleanup_plan(source[0], plan.plan_id).canonical_bytes
        == plan.canonical_bytes
    )
    assert plan.items[0].allocated_bytes is not None
    assert plan.items[0].allocated_bytes > 0


def test_library_window_deduplicates_and_keeps_inflight_and_unknown(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import (
        acquire_install,
        activate_supply,
        create_cleanup_plan,
        doctor_supply,
        rebuild_supply,
        show_supply,
    )
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    identities = [first.install_id]
    activate_supply(source[0], first.supply_id, source[1])
    for _ in range(5):
        installed = rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=Run(),
        )
        identities.append(installed.install_id)
        activate_supply(source[0], first.supply_id, source[1])
    activate_supply(source[0], first.supply_id, source[1])
    args = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    with acquire_install(source[0], first.supply_id, first.install_id):
        plan = create_cleanup_plan(source[0], **args)
        assert [i.install_id for i in plan.candidates] == [identities[1]]
        assert plan.over_limit and plan.present_count == 6
        reasons = {i.install_id: i.protection for i in plan.items}
        assert reasons[identities[0]] == ("in_flight",)
        assert reasons[identities[-1]] == ("current", "latest_install_check")
        assert {
            i.install_id: i.protection
            for i in doctor_supply(source[0], source[1]).instances
        } == reasons
    lock = tmp_path / "install/.locks" / (identities[0] + ".lock")
    lock.unlink()
    plan = create_cleanup_plan(source[0], **args)
    assert plan.items[0].protection == ("protection_unknown",)
    assert all(
        i.path.exists() for i in show_supply(source[0], first.supply_id).installs
    )


def test_unactivated_bad_tree_is_candidate_but_special_and_unknown_never_are(
    tmp_path: Path,
) -> None:
    import os

    from paper_radar.pi_supply import create_cleanup_plan, rebuild_supply, show_supply
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    instance = next(
        i
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    node = instance.path / "node/bin/node"
    node.chmod(0o755)
    node.write_bytes(b"broken")
    staging = tmp_path / "install/.staging-secret"
    staging.mkdir()
    unknown = instance.path.parent / ("0" * 32)
    unknown.mkdir()
    trash = tmp_path / "install/.trash"
    trash.mkdir()
    (trash / ("1" * 32)).mkdir()
    args = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    plan = create_cleanup_plan(source[0], **args)
    assert [i.install_id for i in plan.candidates] == [first.install_id]
    assert plan.candidates[0].actual_tree_hash != plan.candidates[0].expected_tree_hash
    assert {i.reason for i in plan.manual} == {
        "unknown_staging",
        "unknown_entry",
        "unknown_trash",
    }
    instance.path.chmod(0o755)
    os.mkfifo(instance.path / "unsafe-fifo")
    plan = create_cleanup_plan(source[0], **args)
    assert plan.candidates == ()
    assert plan.items[0].reason == "tree_special_file"
    assert plan.present_count == 2
    assert plan.occupancy_unknown
    assert staging.exists() and unknown.exists()


def test_cross_supply_instances_compete_for_one_window(tmp_path: Path) -> None:
    import hashlib
    import json

    from paper_radar.pi_supply import (
        activate_supply,
        create_cleanup_plan,
        rebuild_supply,
    )
    from tests.pi_supply_support import NODE, Download, Run, node_archive

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    activate_supply(source[0], first.supply_id, source[1])
    roots: Roots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    second = rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=Run(),
    )
    activate_supply(source[0], first.supply_id, source[1])
    download = Download()
    archive = node_archive(("extra.txt", b"different fixed toolchain bytes"))
    digest = hashlib.sha256(archive).hexdigest()
    download.content[
        f"https://nodejs.org/dist/v{NODE}/node-v{NODE}-linux-x64.tar.xz"
    ] = archive
    download.content[f"https://nodejs.org/dist/v{NODE}/SHASUMS256.txt"] = (
        f"{digest}  node-v{NODE}-linux-x64.tar.xz\n".encode()
    )
    request = json.loads(source[2].read_bytes())
    request["node_sha256"] = digest
    source[2].write_text(json.dumps(request))
    other = prepare(tmp_path, (source[0], source[1], source[2], download, Run()))
    activate_supply(source[0], other.supply_id, source[1])
    third = rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=Run(),
    )
    activate_supply(source[0], first.supply_id, source[1])
    fourth = rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=Run(),
    )
    activate_supply(source[0], first.supply_id, source[1])
    activate_supply(source[0], first.supply_id, source[1])
    plan = create_cleanup_plan(source[0], **roots)
    assert {item.install_id for item in plan.candidates} == {first.install_id}
    assert {
        item.install_id for item in plan.items if "recent_activation" in item.protection
    } == {other.install_id, second.install_id, third.install_id}
    assert next(
        i for i in plan.items if i.install_id == fourth.install_id
    ).protection == ("current", "latest_install_check")


def test_synthetic_scopes_protect_independently_without_rpc_import(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from paper_radar.pi_supply import rebuild_supply, show_supply
    from paper_radar.pi_supply.execution import retention_protection
    from paper_radar.pi_supply.models import InstallCheck
    from paper_radar.pi_supply.retention import protection_reasons
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    second = rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=source[3],
        runner=Run(),
    )
    record = show_supply(source[0], first.supply_id)
    # 仅纯规则输入合成未来scope;真实库不导入RPC成功。
    synthetic = replace(
        record,
        installs=tuple(
            replace(
                i,
                checks=i.checks
                + (
                    (
                        InstallCheck(
                            9999,
                            "rpc_compatibility",
                            True,
                            "passed",
                            "2026-10-19T00:00:00+00:00",
                        ),
                    )
                    if i.install_id == first.install_id
                    else ()
                ),
            )
            for i in record.installs
        ),
    )
    reasons = protection_reasons((synthetic,), (), {})
    assert reasons[first.install_id] == ("latest_rpc_compatibility",)
    assert reasons[second.install_id] == ("latest_install_check",)
    assert retention_protection((synthetic,), ()).acceptance_install_ids == (
        second.install_id,
        first.install_id,
    )


def test_foreign_marker_is_reported_without_scanning_root(tmp_path: Path) -> None:
    from paper_radar.pi_supply import create_cleanup_plan

    source = inputs(tmp_path)
    prepare(tmp_path, source)
    marker = tmp_path / "install/.paper-radar-install-root"
    marker.chmod(0o600)
    marker.write_bytes(
        b'{"database_id":"00000000000000000000000000000000","root_id":"00000000000000000000000000000000"}'
    )
    (tmp_path / "install/.staging-do-not-scan").mkdir()
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    assert plan.candidates == ()
    assert plan.items[0].reason == "root_foreign"
    assert plan.items[0].allocated_bytes is None
    assert len(plan.manual) == 1 and plan.manual[0].reason == "root_unverifiable"


def test_real_occupancy_deduplicates_hardlinks_and_does_not_promise_external_blocks(
    tmp_path: Path,
) -> None:
    import os

    from paper_radar.pi_supply import create_cleanup_plan, rebuild_supply, show_supply
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    roots: Roots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=Run(),
    )
    instance = next(
        i
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    instance.path.chmod(0o755)
    sparse = instance.path / "sparse"
    with sparse.open("wb") as output:
        output.truncate(16 * 1024 * 1024)
    baseline = create_cleanup_plan(source[0], **roots)
    candidate = baseline.candidates[0]
    assert (
        candidate.logical_bytes is not None
        and candidate.logical_bytes > 16 * 1024 * 1024
    )
    assert (
        candidate.allocated_bytes is not None
        and candidate.allocated_bytes < 1024 * 1024
    )
    node = instance.path / "node/bin/node"
    node.parent.chmod(0o755)
    directory_blocks_before = node.parent.stat().st_blocks * 512
    os.link(node, node.parent / "alias")
    linked = create_cleanup_plan(source[0], **roots)
    directory_delta = node.parent.stat().st_blocks * 512 - directory_blocks_before
    assert (
        linked.candidates[0].allocated_bytes
        == candidate.allocated_bytes + directory_delta
    )
    external = tmp_path / "external-alias"
    os.link(node, external)
    bounded = create_cleanup_plan(source[0], **roots)
    assert bounded.allocated_bytes == linked.allocated_bytes
    assert (
        bounded.reclaimable_bytes
        == linked.reclaimable_bytes - node.stat().st_blocks * 512
    )
    assert (
        bounded.candidates[0].actual_tree_hash == linked.candidates[0].actual_tree_hash
    )
    assert external.read_bytes() == b"synthetic executable"


def test_safe_root_group_and_links_never_expand_candidates(tmp_path: Path) -> None:
    import os

    from paper_radar.pi_supply import create_cleanup_plan, rebuild_supply, show_supply
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    roots: Roots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=Run(),
    )
    instance = next(
        i
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    )
    external = tmp_path / "sentinel"
    external.write_bytes(b"leave outside untouched")
    instance.path.chmod(0o755)
    (instance.path / "escape").symlink_to(external)
    rejected = create_cleanup_plan(source[0], **roots)
    assert rejected.candidates == ()
    assert rejected.items[0].reason == "tree_link_unsafe"
    (instance.path / "escape").unlink()
    overlap: Roots = {**roots, "data_root": tmp_path / "install"}
    rejected = create_cleanup_plan(source[0], **overlap)
    assert rejected.candidates == () and all(
        i.reason == "unsafe_root" for i in rejected.items
    )
    (tmp_path / "config").rename(tmp_path / "actual-config")
    (tmp_path / "config").symlink_to(
        tmp_path / "actual-config", target_is_directory=True
    )
    rejected = create_cleanup_plan(source[0], **roots)
    assert rejected.candidates == () and all(
        i.reason == "unsafe_path" for i in rejected.items
    )
    (tmp_path / "config").unlink()
    (tmp_path / "actual-config").rename(tmp_path / "config")
    marker = tmp_path / "install/.paper-radar-install-root"
    original_marker = marker.read_bytes()
    marker.unlink()
    os.mkfifo(marker)
    rejected = create_cleanup_plan(source[0], **roots)
    assert rejected.candidates == () and all(
        i.reason == "root_foreign" for i in rejected.items
    )
    marker.unlink()
    marker.write_bytes(original_marker)
    (tmp_path / "install").rename(tmp_path / "actual-install")
    (tmp_path / "install").symlink_to(
        tmp_path / "actual-install", target_is_directory=True
    )
    rejected = create_cleanup_plan(source[0], **roots)
    assert rejected.candidates == () and all(
        i.reason == "unsafe_path" for i in rejected.items
    )
    assert external.read_bytes() == b"leave outside untouched"


def test_manual_residual_sizes_are_counted_without_joining_candidates(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import create_cleanup_plan

    source = inputs(tmp_path)
    prepare(tmp_path, source)
    args = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    before = create_cleanup_plan(source[0], **args)
    staging = tmp_path / "install/.staging-unknown"
    staging.mkdir()
    (staging / "file").write_bytes(b"residual bytes")
    plan = create_cleanup_plan(source[0], **args)
    assert len(plan.manual) == 1
    assert (
        plan.manual[0].logical_bytes is not None and plan.manual[0].logical_bytes >= 14
    )
    assert (
        plan.manual[0].allocated_bytes is not None
        and plan.manual[0].allocated_bytes > 0
    )
    assert (
        plan.allocated_bytes == before.allocated_bytes + plan.manual[0].allocated_bytes
    )
    assert plan.reclaimable_bytes == before.reclaimable_bytes == 0
    assert not plan.occupancy_unknown
    (staging / "escape").symlink_to(tmp_path / "config", target_is_directory=True)
    unsafe = create_cleanup_plan(source[0], **args)
    assert unsafe.manual[0].allocated_bytes is None
    assert unsafe.manual[0].occupancy_reason == "tree_link_unsafe"
    assert unsafe.occupancy_unknown and unsafe.candidates == ()
