"""本根内分段持久化与 hard-link 不覆盖发布。"""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from collections.abc import Callable, Iterable
from contextlib import suppress
from itertools import product
from pathlib import Path

from paper_radar.storage.artifact_contract import (
    ArtifactError,
    ArtifactReason,
    BlobRecord,
    blob_relative_path,
    require_sha256,
)
from paper_radar.storage.filesystem import (
    UnsafePathError,
    controlled_path,
    sync_directory,
)

CHUNK_SIZE = 1024 * 1024


class BlobStore:
    def __init__(self, data_root: Path) -> None:
        # 根本身可为符号链接;其后只使用此解析结果。
        try:
            self.root = data_root.resolve()
        except (OSError, RuntimeError):
            raise ArtifactError(
                ArtifactReason.UNSAFE_PATH, "数据根无法解析；请检查路径"
            ) from None

    @classmethod
    def _mkdir(cls, path: Path) -> None:
        if path.exists():
            if not path.is_dir():
                raise ArtifactError(ArtifactReason.UNSAFE_PATH, "受控目录位置不是目录")
            return
        cls._mkdir(path.parent)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            if not path.is_dir():
                raise ArtifactError(
                    ArtifactReason.UNSAFE_PATH, "受控目录位置不是目录"
                ) from None
        # 将本级目录项同步到父目录。每级新建均执行,包含 root 与前缀目录。
        sync_directory(path.parent)

    def _path(self, relative: str, *, create_parents: bool = False) -> Path:
        try:
            return controlled_path(
                self.root,
                relative,
                create_directory=self._mkdir if create_parents else None,
            )
        except UnsafePathError as error:
            raise ArtifactError(ArtifactReason.UNSAFE_PATH, str(error)) from None

    def path_for(self, record: BlobRecord) -> Path:
        expected = blob_relative_path(record.sha256, record.layout_version)
        if (
            record.relative_path != expected
            or type(record.size_bytes) is not int
            or record.size_bytes < 0
        ):
            raise ArtifactError(
                ArtifactReason.REGISTRATION_CORRUPT, "内容对象登记位置或长度损坏"
            )
        return self._path(expected)

    def prepare_publish(self) -> None:
        """预检发布目录的创建/硬链接能力;不发布内容,不保证后续 I/O 成功。"""
        try:
            temporary = self._path("tmp/pending", create_parents=True).parent
            namespace = self._path("blobs/sha256/pending", create_parents=True).parent
            with tempfile.NamedTemporaryFile(dir=temporary) as stream:
                stream.flush()
                os.fchmod(stream.fileno(), 0o400)
                os.fsync(stream.fileno())
                self._probe_link_directory(namespace, Path(stream.name))
                # 布局只有 256 个两位十六进制槽位;不遍历内容,也不创建空 shard。
                for high, low in product("0123456789abcdef", repeat=2):
                    shard = self._path(f"blobs/sha256/{high}{low}/pending").parent
                    if shard.exists():
                        self._mkdir(shard)
                        self._probe_link_directory(shard, Path(stream.name))
        except OSError:
            raise ArtifactError(
                ArtifactReason.PUBLICATION_FAILED,
                "发布目录无法准备；请检查路径和写入权限",
            ) from None

    @staticmethod
    def _probe_link_directory(directory: Path, source: Path) -> None:
        # 所有探针均是可清理临时目录,不使用 blob 身份或登记制品。
        with tempfile.TemporaryDirectory(
            prefix=".publish-check-", dir=directory
        ) as name:
            probe = Path(name)
            os.link(source, probe / "link")
            sync_directory(probe)
        sync_directory(directory)

    def verify(self, record: BlobRecord) -> Path:
        try:
            path = self.path_for(record)
            mode = path.stat().st_mode
            if mode & 0o222:
                raise ArtifactError(
                    ArtifactReason.BLOB_CORRUPT, "内容对象具有写权限；请检查不可变存储"
                )
            if not stat.S_ISREG(mode):
                raise ArtifactError(ArtifactReason.BLOB_CORRUPT, "内容对象不是普通文件")
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                while chunk := stream.read(CHUNK_SIZE):
                    digest.update(chunk)
                    size += len(chunk)
            if size != record.size_bytes or digest.hexdigest() != record.sha256:
                raise ArtifactError(
                    ArtifactReason.BLOB_CORRUPT,
                    "内容对象长度或 SHA-256 不一致；不自动修复历史",
                )
            return path
        except FileNotFoundError:
            raise ArtifactError(
                ArtifactReason.BLOB_MISSING, "内容对象文件缺失；请检查数据根或备份"
            ) from None
        except OSError:
            raise ArtifactError(
                ArtifactReason.BLOB_CORRUPT, "内容对象无法读取；请检查文件和权限"
            ) from None

    def read(self, record: BlobRecord) -> bytes:
        path = self.verify(record)
        try:
            raw = path.read_bytes()
        except OSError:
            raise ArtifactError(
                ArtifactReason.BLOB_CORRUPT, "内容对象无法读取"
            ) from None
        # 两遍读取间发生普通文件变化也不能交出损坏内容。
        if (
            len(raw) != record.size_bytes
            or hashlib.sha256(raw).hexdigest() != record.sha256
        ):
            raise ArtifactError(
                ArtifactReason.BLOB_CORRUPT, "内容对象在读取期间发生变化"
            )
        return raw

    def publish(
        self,
        chunks: Iterable[bytes],
        expected_sha256: str | None = None,
        *,
        check_registration: Callable[[BlobRecord], None] | None = None,
    ) -> BlobRecord:
        if expected_sha256 is not None:
            require_sha256(expected_sha256)
        temporary: Path | None = None
        try:
            temp_dir = self._path("tmp/pending", create_parents=True).parent
            fd, name = tempfile.mkstemp(prefix="blob-", dir=temp_dir)
            temporary = Path(name)
            digest = hashlib.sha256()
            size = 0
            with os.fdopen(fd, "wb") as stream:
                for chunk in chunks:
                    if not isinstance(chunk, bytes):
                        raise ArtifactError(
                            ArtifactReason.INVALID_MANIFEST, "内容分段必须是原始 bytes"
                        )
                    stream.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                stream.flush()
                os.fchmod(stream.fileno(), 0o400)
                os.fsync(stream.fileno())
            sha256 = digest.hexdigest()
            if expected_sha256 is not None and sha256 != expected_sha256:
                raise ArtifactError(
                    ArtifactReason.HASH_MISMATCH, "实际内容与预期 SHA-256 不一致"
                )
            record = BlobRecord(sha256, size, blob_relative_path(sha256))
            if check_registration is not None:
                check_registration(record)
            destination = self._path(record.relative_path, create_parents=True)
            try:
                os.link(temporary, destination)
            except FileExistsError:
                self.verify(record)
            # 对新发布目录项持久化;已有同名对象也只核验,不覆盖。
            sync_directory(destination.parent)
            return record
        except ArtifactError:
            raise
        except OSError:
            raise ArtifactError(
                ArtifactReason.PUBLICATION_FAILED,
                "内容对象发布失败；需要同文件系统 hard-link 支持与写入权限",
            ) from None
        finally:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)
