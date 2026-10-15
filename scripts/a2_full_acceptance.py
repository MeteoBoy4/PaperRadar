"""同一次完整离线运行的 A2 全量结论。不继承历史 A2-01 的通过状态。"""

from __future__ import annotations

import importlib.metadata
import json
import os
import signal
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from scripts.a1_acceptance import capture_identity, run_a1_verification
from scripts.a2_full_scope import (
    FORMAT_VERSION,
    FORMAT_VERSIONS,
    ISSUE,
    MIGRATION_REVISION,
    NOT_ASSESSED,
    REQUIRED_CHECKS,
    REQUIRED_DEPENDENCIES,
    REQUIRED_FIXTURE_FILES,
    REQUIRED_SOURCE_MODULES,
    REQUIRED_TEST_MODULES,
    SCOPE,
)
from scripts.offline_evidence import file_sha256

_HELP = {
    "evidence_unavailable": "本次证据无法读取；请重跑完整离线入口。",
    "binding_mismatch": "证据、A1 结论或运行身份不一致；请重跑完整离线入口。",
    "format_mismatch": "证据或结论格式不受支持；请核对格式版本后重跑。",
    "a1_not_passed": "本次 A1 未通过；请先处理 A1 结论中的原因。",
    "check_not_passed": "完整固定检查缺失、失败或未执行；请查看本次离线证据。",
    "scope_drift": "固定范围文件缺失或字节变化；请逐项审查后显式更新范围。",
    "dependency_unavailable": "A2 依赖实际版本不可得；请修复锁定环境。",
    "migration_unavailable": "临时验收库迁移失败或 head 未登记；请审查迁移范围。",
    "config_format_drift": "配置格式身份变化；请审查并显式版本化验收范围。",
    "identity_changed": "运行期间代码、工作树或 lockfile 变化；请重跑完整入口。",
    "run_incomplete": "本次运行中断或未完成；请重新执行完整入口。",
}


def _reason(code: str, item: str | None = None) -> dict[str, str]:
    return {"code": code, "message_zh": _HELP[code], **({"item": item} if item else {})}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _files(
    root: Path,
    required: tuple[tuple[str, str], ...],
    reasons: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if not required:
        reasons.append(_reason("scope_drift"))
    records = []
    for relative, expected in required:
        actual = file_sha256(root / relative)
        matched = actual == expected
        records.append(
            {
                "path": relative,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "result": "passed" if matched else "failed",
            }
        )
        if not matched:
            reasons.append(_reason("scope_drift", relative))
    return records


def _environment(reasons: list[dict[str, str]]) -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for name in REQUIRED_DEPENDENCIES:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = None
        available = isinstance(version, str) and bool(version.strip())
        versions[name] = version if available else None
        if not available:
            reasons.append(_reason("dependency_unavailable", name))
    return {"python": sys.version.split()[0], "dependencies": versions}


def _formats() -> dict[str, Any]:
    from paper_radar.config.adapters import ADAPTER_SEMANTICS_FORMAT_VERSION
    from paper_radar.config.compile import FORMAT_VERSION as snapshot_version
    from paper_radar.config.projections import (
        BASELINE_FORMAT_VERSION,
        PROJECTION_FORMAT_VERSIONS,
    )

    return {
        "snapshot": snapshot_version,
        "stage_projections": {
            stage.value: version
            for stage, version in PROJECTION_FORMAT_VERSIONS.items()
        },
        "calibration_baseline": BASELINE_FORMAT_VERSION,
        "adapter_semantics": ADAPTER_SEMANTICS_FORMAT_VERSION,
    }


def _migrated_revision() -> str | None:
    """实际创建并升级独立临时库, 读取库内 revision。不接受用户库路径。"""
    from paper_radar.storage.database import (
        DatabaseMode,
        current_revision,
        open_database,
        upgrade_database,
    )

    with tempfile.TemporaryDirectory(prefix="paper-radar-a2-") as directory:
        database = Path(directory) / "acceptance.sqlite3"
        upgrade_database(database)
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            with engine.connect() as connection:
                revisions = (
                    connection.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    )
                    .scalars()
                    .all()
                )
        finally:
            engine.dispose()
        if len(revisions) != 1 or revisions[0] != current_revision():
            return None
        return str(revisions[0])


def _validate_run(
    evidence_path: Path,
    a1_path: Path,
    a1: dict[str, Any],
    reasons: list[dict[str, str]],
) -> dict[str, Any]:
    evidence = _read_json(evidence_path)
    if evidence is None:
        reasons.append(_reason("evidence_unavailable"))
        evidence = {}
    run_id = a1["run_id"]
    if (
        _read_json(a1_path) != a1
        or evidence_path.name != f"{run_id}.json"
        or a1_path.name != f"{run_id}.a1.json"
        or evidence.get("run_id") != run_id
        or a1.get("evidence_sha256") != file_sha256(evidence_path)
        or a1.get("scope") != "a1_screening_authoritative_contracts"
        or not isinstance(evidence.get("scope"), dict)
        or any(
            evidence["scope"].get(key) != value
            for key, value in {
                "issue": 12,
                "claim": "implemented_offline_checks_only",
                "full_a1_verified": False,
                "stage_a_verified": False,
            }.items()
        )
    ):
        reasons.append(_reason("binding_mismatch"))
    if evidence.get("format_version") != 1 or a1.get("format_version") != 1:
        reasons.append(_reason("format_mismatch"))
    if a1.get("status") != "passed" or a1.get("a1_verified") is not True:
        reasons.append(_reason("a1_not_passed"))
    checks = evidence.get("checks")
    if (
        evidence.get("completed") is not True
        or evidence.get("overall") != "passed"
        or not isinstance(checks, list)
        or [c.get("id") if isinstance(c, dict) else None for c in checks]
        != list(REQUIRED_CHECKS)
        or any(
            not isinstance(c, dict)
            or c.get("status") != "passed"
            or c.get("reason") != "none"
            or type(c.get("exit_code")) is not int
            or c.get("exit_code") != 0
            for c in checks
        )
    ):
        reasons.append(_reason("check_not_passed"))
    if (
        evidence.get("completed") is False
        or evidence.get("overall") == "incomplete"
        or a1.get("status") == "incomplete"
    ):
        reasons.append(_reason("run_incomplete"))
    return evidence


def write_full_a2_conclusion(
    root: Path,
    evidence_path: Path,
    a1_path: Path,
    a1_conclusion: dict[str, Any],
    output_dir: Path,
    *,
    interrupted: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """只追加完整 A2 结论。不执行完整测试或读取旧运行结论与配置正文。"""
    reasons: list[dict[str, str]] = []
    run_id = a1_conclusion["run_id"]
    result: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "run_id": run_id,
        "scope": SCOPE,
        "issue": ISSUE,
        "status": "incomplete",
        "a2_verified": False,
        "stage_a_verified": False,
        "live_verified": False,
        "evidence_file": evidence_path.name,
        "evidence_sha256": None,
        "a1_conclusion_file": a1_path.name,
        "a1_conclusion_sha256": None,
        "required_checks": list(REQUIRED_CHECKS),
        "test_modules": [],
        "source_modules": [],
        "fixture_files": [],
        "environment": None,
        "migration_revision": None,
        "format_versions": None,
        "code": None,
        "worktree_sha256": None,
        "lockfile_sha256": None,
        "not_assessed": list(NOT_ASSESSED),
        "reasons": reasons,
    }
    try:
        evidence = _validate_run(evidence_path, a1_path, a1_conclusion, reasons)
        result["evidence_sha256"] = file_sha256(evidence_path)
        result["a1_conclusion_sha256"] = file_sha256(a1_path)
        for key, required in (
            ("test_modules", REQUIRED_TEST_MODULES),
            ("source_modules", REQUIRED_SOURCE_MODULES),
            ("fixture_files", REQUIRED_FIXTURE_FILES),
        ):
            result[key] = _files(root, required, reasons)
        result["environment"] = _environment(reasons)
        try:
            result["migration_revision"] = _migrated_revision()
        except Exception:
            reasons.append(_reason("migration_unavailable"))
        else:
            if result["migration_revision"] != MIGRATION_REVISION:
                reasons.append(_reason("migration_unavailable"))
        result["format_versions"] = _formats()
        if result["format_versions"] != FORMAT_VERSIONS:
            reasons.append(_reason("config_format_drift"))
        current = capture_identity(root)
        result.update(
            code=current.code,
            worktree_sha256=current.worktree_sha256,
            lockfile_sha256=current.lockfile_sha256,
        )
        if (
            current.code["commit"] is None
            or current.code["dirty"] is None
            or current.worktree_sha256 is None
            or current.lockfile_sha256 is None
            or evidence.get("code") != current.code
            or evidence.get("lockfile_sha256") != current.lockfile_sha256
            or any(
                a1_conclusion.get(key) != result[key]
                for key in ("code", "worktree_sha256", "lockfile_sha256")
            )
        ):
            reasons.append(_reason("identity_changed"))
        # 结论发布前再次核对绑定文件, 不能接受检查期间替换的证据。
        if (
            file_sha256(evidence_path) != result["evidence_sha256"]
            or file_sha256(a1_path) != result["a1_conclusion_sha256"]
            or result["evidence_sha256"] != a1_conclusion.get("evidence_sha256")
            or _read_json(a1_path) != a1_conclusion
        ):
            reasons.append(_reason("binding_mismatch"))
    except KeyboardInterrupt:
        interrupted = True
    if interrupted:
        reasons.append(_reason("run_incomplete"))
    status = "passed" if not reasons else "failed"
    if any(reason["code"] == "run_incomplete" for reason in reasons):
        status = "incomplete"
    result.update(status=status, a2_verified=status == "passed")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}.a2-full.json"
    temporary = output_dir / f".{run_id}.{uuid.uuid4().hex}.tmp"
    payload = (
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path, result


def run_full_verification(root: Path, output_dir: Path) -> tuple[Path, dict[str, Any]]:
    """完整检查只执行一次。A2-01 保留独立范围。"""
    from scripts.a2_acceptance import write_a2_conclusion

    a1_path, a1 = run_a1_verification(root, output_dir)
    evidence = output_dir / f"{a1['run_id']}.json"
    interrupted = False
    try:
        legacy_path, legacy = write_a2_conclusion(
            root, evidence, a1_path, a1, output_dir
        )
    except KeyboardInterrupt:
        interrupted = True
        legacy_path = output_dir / f"{a1['run_id']}.a2.json"
        published = _read_json(legacy_path)
        if published is None:
            legacy_path, legacy = write_a2_conclusion(
                root, evidence, a1_path, a1, output_dir
            )
        else:
            legacy = published
    print(f"[A2-01 验收] 结论：{legacy_path}")
    print(f"[A2-01 验收] 结果：{legacy['status']}")
    path, full = write_full_a2_conclusion(
        root,
        evidence,
        a1_path,
        a1,
        output_dir,
        interrupted=interrupted,
    )
    print(f"[完整 A2 验收] 结论：{path}")
    print(f"[完整 A2 验收] 结果：{full['status']}")
    for reason in full["reasons"]:
        print(f"[完整 A2 验收] 原因：{reason['code']}：{reason['message_zh']}")
    return path, full


def _interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    signal.signal(signal.SIGTERM, _interrupt)
    root = Path(__file__).resolve().parents[1]
    _, full = run_full_verification(root, root / "verification-runs")
    return 0 if full["a2_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
