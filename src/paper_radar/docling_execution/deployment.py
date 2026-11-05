"""锁前验证部署清单,仅向 worker 暴露已核验的私有快照。"""

import hashlib
import os
import stat
import tempfile
from pathlib import Path
from typing import Literal

from paper_radar.config.extraction import ExtractionSemantics
from paper_radar.config.extraction_models import ModelFile
from paper_radar.fulltext.canonical import CanonicalModel


class DeployedModel(CanonicalModel):
    repo_id: str
    commit_sha: str
    files: tuple[ModelFile, ...]


class ModelDeployment(CanonicalModel):
    format_version: Literal[1] = 1
    models: tuple[DeployedModel, ...]


def snapshot_models(
    root: Path, semantics: ExtractionSemantics
) -> tempfile.TemporaryDirectory[str]:
    """commit 是显式部署声明,哈希核验文件;不声称证明 Git 历史。"""
    deployment = ModelDeployment.model_validate_json(
        (root / "deployment.json").read_bytes()
    )
    models = {m.repo_id: m for m in deployment.models}
    if len(models) != len(deployment.models):
        raise ValueError("重复模型部署声明")
    snapshot = tempfile.TemporaryDirectory(prefix="paperradar-docling-models-")
    try:
        for selected in semantics.model_artifacts:
            declared = models[selected.repo_id]
            if (
                declared.commit_sha != selected.commit_sha
                or declared.files != selected.files
            ):
                raise ValueError("模型部署与冻结身份不符")
            for member in selected.files:
                relative = Path(selected.repo_id.replace("/", "--")) / member.path
                source = root / relative
                # 整条路径必须位于根内;不消费链接文件或目录。
                current = root
                for component in relative.parts:
                    current /= component
                    if current.is_symlink():
                        raise ValueError("模型部署不得使用符号链接")
                if not source.is_file():
                    raise ValueError("缺少模型文件")
                target = Path(snapshot.name) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as reader, target.open("xb") as writer:
                    if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
                        raise ValueError("模型成员不是普通文件")
                    while chunk := reader.read(1024 * 1024):
                        digest.update(chunk)
                        writer.write(chunk)
                if digest.hexdigest() != member.sha256:
                    raise ValueError("模型文件哈希不符")
                target.chmod(0o400)
        return snapshot
    except BaseException:
        snapshot.cleanup()
        raise
