"""B 静态检查组合;只读元数据与登记,不认证、不启动、不建资源。"""

import os
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

from paper_radar.config import (
    ConfigError,
    StageName,
    load_config_snapshot,
    resolve_config_snapshot_reference,
)
from paper_radar.config.extraction import ExtractionSemantics
from paper_radar.docling_execution.deployment import ModelDeployment
from paper_radar.doctor.docling_runtime import runtime_checks, unassessed_checks
from paper_radar.doctor.pi_exec import execution_checks
from paper_radar.doctor.service import Check, Result, basic_checks
from paper_radar.experiment.egress import (
    EgressError,
    require_egress_authorization,
    selected_grants,
)
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.pi_execution.resources import ExecutionRoots
from paper_radar.pi_supply import SupplyError, available_installs, doctor_supply
from paper_radar.pi_supply.filesystem import no_symlink_components


@dataclass(frozen=True)
class HostPaths:
    meminfo: Path = Path("/proc/meminfo")
    cgroup_membership: Path = Path("/proc/self/cgroup")
    cgroup_mount: Path = Path("/sys/fs/cgroup")


HOST_PATHS = HostPaths()


def host_memory_check(meminfo: Path = Path("/proc/meminfo")) -> Check:
    try:
        lines = [
            line.split()
            for line in meminfo.read_text().splitlines()
            if line.startswith("MemAvailable:")
        ]
        if len(lines) != 1 or len(lines[0]) != 3 or lines[0][2] != "kB":
            raise ValueError
        available = int(lines[0][1]) * 1024
        if available < 0:
            raise ValueError
    except (OSError, ValueError):
        return Check(
            "host.memory",
            Result.NOT_ASSESSED,
            "host_memory_unknown",
            "主机可用内存 unknown；仅披露，未判断容量足够，可核对 MemAvailable。",
            required=False,
        )
    return Check(
        "host.memory",
        Result.PASSED,
        "host_memory_observed",
        f"可用内存字节={available}；仅披露实测值，不判断容量足够。",
        required=False,
    )


def cgroup_checks(
    proc: Path = Path("/proc/self/cgroup"), mount: Path = Path("/sys/fs/cgroup")
) -> tuple[Check, ...]:
    try:
        entries = [
            line[3:] for line in proc.read_text().splitlines() if line.startswith("0::")
        ]
        if (
            len(entries) != 1
            or not entries[0].startswith("/")
            or ".." in Path(entries[0]).parts
        ):
            raise ValueError
        group = mount / entries[0].lstrip("/")
        if (
            not (mount / "cgroup.controllers").is_file()
            or not (group / "memory.max").is_file()
        ):
            raise ValueError
        capable = all(
            os.access(group / name, os.W_OK)
            for name in ("memory.max", "memory.swap.max", "cgroup.procs")
        )
        capability = Check(
            "host.cgroup_v2",
            Result.PASSED if capable else Result.INVALID,
            "cgroup_v2_capable" if capable else "cgroup_v2_unavailable",
            "核对用户委派 memory 控制器；提取入口仍须在领取前核对 ≤8 GiB 与 swap=0。",
        )
    except (OSError, ValueError):
        return (
            Check(
                "host.cgroup_v2",
                Result.INVALID,
                "cgroup_v2_unavailable",
                "准备用户 cgroup v2 memory 委派后重新预检。",
            ),
            Check(
                "host.memory_peak",
                Result.NOT_ASSESSED,
                "memory_peak_unknown",
                "当前 cgroup 不可核对，峰值 unknown。",
                required=False,
            ),
        )
    try:
        peak = int((group / "memory.peak").read_text().strip())
        if peak < 0:
            raise ValueError
    except (OSError, ValueError):
        peak_check = Check(
            "host.memory_peak",
            Result.NOT_ASSESSED,
            "memory_peak_unknown",
            "峰值 unknown；提取后仍须单独记录。",
            required=False,
        )
    else:
        peak_check = Check(
            "host.memory_peak",
            Result.PASSED,
            "memory_peak_readable",
            f"当前 cgroup 峰值字节={peak}；不是 worker ru_maxrss。",
            required=False,
        )
    return capability, peak_check


def model_snapshot_disk_check(
    model_root: Path, attempt_root: Path, semantics: ExtractionSemantics | None
) -> Check:
    if semantics is None:
        return Check(
            "host.model_snapshot_disk",
            Result.MISSING,
            "extraction_unselected",
            "先显式选择 extraction 和模型部署。",
        )
    try:
        no_symlink_components(model_root)
        deployment = ModelDeployment.model_validate_json(
            (model_root / "deployment.json").read_bytes()
        )
        models = {model.repo_id: model for model in deployment.models}
        if len(models) != len(deployment.models):
            raise ValueError
        total = 0
        for selected in semantics.model_artifacts:
            declared = models[selected.repo_id]
            if (
                declared.commit_sha != selected.commit_sha
                or declared.files != selected.files
            ):
                raise ValueError
            for member in selected.files:
                source = model_root / selected.repo_id.replace("/", "--") / member.path
                no_symlink_components(source)
                if not source.is_file():
                    raise ValueError
                digest = sha256()
                with source.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        total += len(chunk)
                        digest.update(chunk)
                if digest.hexdigest() != member.sha256:
                    raise ValueError
        ancestor = attempt_root
        while not ancestor.exists():
            if ancestor == ancestor.parent:
                raise ValueError
            ancestor = ancestor.parent
        space = os.statvfs(ancestor)
        available = space.f_bavail * space.f_frsize
    except FileNotFoundError:
        return Check(
            "host.model_snapshot_disk",
            Result.MISSING,
            "model_deployment_missing",
            "准备所选模型及 deployment.json，预检不下载模型。",
        )
    except (OSError, ValueError, KeyError, SupplyError):
        return Check(
            "host.model_snapshot_disk",
            Result.INVALID,
            "model_deployment_invalid",
            "核对冻结部署、完整文件哈希和临时快照磁盘。",
        )
    sufficient = available >= total
    return Check(
        "host.model_snapshot_disk",
        Result.PASSED if sufficient else Result.INVALID,
        "model_snapshot_space_sufficient"
        if sufficient
        else "model_snapshot_space_insufficient",
        f"所选模型快照所需字节={total}；可用磁盘字节={available}；不足请释放临时快照磁盘。",
    )


def root_checks(
    root: ExperimentRoot,
    *,
    credentials_dir: Path,
    roots: ExecutionRoots,
    attempt_root: Path,
    snapshot: str,
) -> tuple[Check, ...]:
    checks = []
    for label, path in (
        ("data", roots.data_root),
        ("config", roots.config_root),
        ("material", roots.material_root),
        ("install", roots.install_root),
    ):
        try:
            no_symlink_components(path)
            no_symlink_components(attempt_root)
            candidate, execution = attempt_root.resolve(), path.resolve()
            separate = not candidate.is_relative_to(
                execution
            ) and not execution.is_relative_to(candidate)
        except (OSError, SupplyError):
            separate = False
        checks.append(
            Check(
                f"roots.attempt_{label}",
                Result.PASSED if separate else Result.INVALID,
                "attempt_root_separate" if separate else "attempt_root_overlap",
                "attempt 临时根须与该显式执行根互不包含；核对路径后重试。",
            )
        )
        candidate, execution = credentials_dir.resolve(), path.resolve()
        separate = not candidate.is_relative_to(
            execution
        ) and not execution.is_relative_to(candidate)
        checks.append(
            Check(
                f"roots.credentials_{label}",
                Result.PASSED if separate else Result.INVALID,
                "credentials_root_separate" if separate else "credentials_root_overlap",
                "凭据目录须在该业务根之外且互不包含；只核对元数据。",
            )
        )
    # 安装根只按供给对象检查;不推导 data/config/material 两两互斥。
    try:
        report = doctor_supply(root.database, snapshot)
        if report.current is None:
            checks.append(
                Check(
                    "roots.install",
                    Result.MISSING,
                    "selection_missing",
                    "先显式准备并激活固定供给。",
                )
            )
        else:
            current = next(
                (
                    item
                    for item in available_installs(
                        root.database, report.current.supply_id
                    )
                    if item.install_id == report.current.install_id
                ),
                None,
            )
            valid = (
                current is not None
                and current.root.resolve() == roots.install_root.resolve()
            )
            checks.append(
                Check(
                    "roots.install",
                    Result.PASSED if valid else Result.INVALID,
                    "install_root_matches" if valid else "install_root_mismatch",
                    "显式安装根须等于所选实例登记安装根；按 pi-supply 核对。",
                )
            )
    except SupplyError as error:
        checks.append(
            Check(
                "roots.install",
                Result.INVALID,
                error.reason,
                "按 pi-supply 核对所选安装登记与保护。",
            )
        )
    return tuple(checks)


def preflight_checks(
    root: ExperimentRoot,
    *,
    snapshot: str,
    credentials_dir: Path,
    material_root: Path,
    install_root: Path,
    attempt_root: Path,
    model_root: Path,
) -> tuple[Check, ...]:
    root.require()
    checks = list(basic_checks(root.database))
    try:
        selected = load_config_snapshot(
            root.database, resolve_config_snapshot_reference(root.database, snapshot)
        )
    except ConfigError as error:
        checks.append(
            Check(
                "config.selection",
                Result.INVALID,
                error.reason.value,
                "请用 config snapshots list 核对快照。",
            )
        )
        return tuple(checks)
    checks.append(
        Check(
            "config.selection",
            Result.PASSED,
            "configuration_valid",
            "历史快照有效；不保存新事实。",
        )
    )
    for config_stage in (
        StageName.BOUNDARY,
        StageName.VALUE,
        StageName.READ,
        StageName.EXTRACTION,
    ):
        readiness = selected.stages[config_stage]
        ready = readiness.status == "ready"
        checks.append(
            Check(
                f"config.{config_stage.value}",
                Result.PASSED if ready else Result.MISSING,
                "configured"
                if ready
                else ",".join(reason.value for reason in readiness.missing),
                "补齐所列配置；配置通过不代表执行通过。",
            )
        )
    for slot in ("screening", "reading"):
        checks.extend(
            replace(check, name=f"{slot}.{check.name}")
            for check in execution_checks(
                root.database, snapshot, credentials_dir, slot=slot
            )
        )
    for stage in ("boundary", "value", "read"):
        try:
            grant = selected_grants(selected, [stage])[0]
            require_egress_authorization(
                root,
                stage=stage,
                provider=grant.provider,
                model=grant.model,
                categories=grant.categories,
            )
        except EgressError as error:
            checks.append(
                Check(
                    f"egress.{stage}",
                    Result.MISSING
                    if error.reason == "egress_not_authorized"
                    else Result.INVALID,
                    error.reason,
                    "由所有者用 egress-authorize 授权本根、模型、阶段和数据类别。",
                )
            )
        else:
            checks.append(
                Check(
                    f"egress.{stage}",
                    Result.PASSED,
                    "egress_authorized",
                    "仅授权匹配；每次认证与领取前仍须重新核对。",
                )
            )
    checks.extend(runtime_checks(selected))
    checks.extend(replace(check, required=False) for check in unassessed_checks())
    roots = ExecutionRoots(root.data_root, root.config, material_root, install_root)
    checks.extend(
        root_checks(
            root,
            credentials_dir=credentials_dir,
            roots=roots,
            attempt_root=attempt_root,
            snapshot=snapshot,
        )
    )
    checks.append(host_memory_check(HOST_PATHS.meminfo))
    checks.extend(cgroup_checks(HOST_PATHS.cgroup_membership, HOST_PATHS.cgroup_mount))
    checks.append(
        model_snapshot_disk_check(model_root, attempt_root, selected.extraction)
    )
    checks.append(
        Check(
            "model_mapping",
            Result.NOT_ASSESSED,
            "model_mapping_not_probed",
            "本次仅静态预检；无 prompt 的受限 RPC 探测由独立入口执行。",
            required=False,
        )
    )
    return tuple(checks)
