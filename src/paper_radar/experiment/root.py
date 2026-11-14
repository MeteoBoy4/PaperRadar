"""一个显式根派生全部业务位置;用途沿用 Body 唯一事实。"""

import fcntl
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import inspect

from paper_radar.body import BodyService
from paper_radar.body.models import RootRegistration
from paper_radar.body.queries import root_fact
from paper_radar.eligibility import RootPurpose
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.filesystem import sync_directory

ExperimentReason = Literal[
    "root_unknown", "root_not_experiment", "unsafe_layout", "legacy_layout"
]


class ExperimentError(ValueError):
    def __init__(self, reason: ExperimentReason) -> None:
        self.reason = reason
        guidance = {
            "root_unknown": "此根尚未登记实验用途；请对独立空根运行 experiment init。",
            "root_not_experiment": "根用途不是 experiment；请使用已登记的独立实验根。",
            "legacy_layout": "旧制品布局非空；请保留原库与材料，另行安排显式迁移。",
            "unsafe_layout": "固定布局不可安全使用；请检查目录、链接和权限后重试。",
        }
        super().__init__(f"{reason}：{guidance[reason]}")


@dataclass(frozen=True)
class ExperimentRoot:
    root: Path

    @property
    def database(self) -> Path:
        return self.root / "paper-radar.sqlite3"

    @property
    def data_root(self) -> Path:
        return self.root / "data"

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def settings(self) -> Path:
        return self.config / "settings.yaml"

    @property
    def views(self) -> Path:
        return self.root / "views"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def _validate_layout(self) -> None:
        for path in (
            self.database,
            self.config,
            self.views,
            self.logs,
            self.data_root,
            self.data_root / "blobs",
            self.data_root / "tmp",
            self.root / "blobs",
            self.root / "tmp",
        ):
            if path.is_symlink() or (
                path.exists()
                and not (path.is_file() if path == self.database else path.is_dir())
            ):
                raise ExperimentError("unsafe_layout")

        for legacy in (self.root / "blobs", self.root / "tmp"):
            if legacy.is_dir() and next(legacy.iterdir(), None) is not None:
                raise ExperimentError("legacy_layout")

    def require(self) -> RootRegistration:
        """只读用途守卫;不创建根、日志或数据库。"""
        self._validate_layout()
        if not self.database.is_file():
            raise ExperimentError("root_unknown")
        registered = BodyService(self.database, self.data_root).root()
        if registered.purpose is RootPurpose.UNKNOWN:
            raise ExperimentError("root_unknown")
        if registered.purpose is not RootPurpose.EXPERIMENT:
            raise ExperimentError("root_not_experiment")
        return registered

    def initialize(self) -> RootRegistration:
        """先在私有临时库迁移及登记,再无覆盖发布完整数据库。"""
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._validate_layout()
        descriptor = os.open(
            self.root / ".experiment-init.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            0o600,
        )
        try:
            lock = os.fstat(descriptor)
            if not stat.S_ISREG(lock.st_mode) or lock.st_nlink != 1:
                raise ExperimentError("unsafe_layout")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            self._validate_layout()
            if self.database.exists():
                # 用途必须先于迁移核对;旧 experiment revision 可显式升级,
                # unknown/production 库不能借 init 被改用途或被迁移。
                engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
                try:
                    with engine.connect() as connection:
                        connection.exec_driver_sql("BEGIN")
                        if not inspect(connection).has_table("body_root"):
                            raise ExperimentError("root_unknown")
                        registered = root_fact(connection)
                finally:
                    engine.dispose()
                if registered.purpose is RootPurpose.UNKNOWN:
                    raise ExperimentError("root_unknown")
                if registered.purpose is not RootPurpose.EXPERIMENT:
                    raise ExperimentError("root_not_experiment")
                upgrade_database(self.database)
            else:
                with tempfile.TemporaryDirectory(
                    prefix=".experiment-init-", dir=self.root
                ) as temporary:
                    database = Path(temporary) / "paper-radar.sqlite3"
                    upgrade_database(database)
                    registered = BodyService(database, self.data_root).register_root(
                        RootPurpose.EXPERIMENT
                    )
                    with database.open("rb") as stream:
                        os.fsync(stream.fileno())
                    os.link(database, self.database)
                    sync_directory(self.root)
            for directory in (self.data_root, self.config, self.views):
                directory.mkdir(mode=0o700, exist_ok=True)
            return registered
        finally:
            os.close(descriptor)
