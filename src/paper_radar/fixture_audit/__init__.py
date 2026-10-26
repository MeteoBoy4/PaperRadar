"""Fixture 注册和摘要审计的公共入口。"""

from typing import TYPE_CHECKING

from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.models import FixtureDeclaration

if TYPE_CHECKING:
    from paper_radar.fixture_audit.service import FixtureAudit


def __getattr__(name: str) -> object:
    if name == "FixtureAudit":
        from paper_radar.fixture_audit.service import FixtureAudit

        return FixtureAudit
    raise AttributeError(name)


__all__ = ["FixtureAudit", "FixtureDeclaration", "FixtureError", "FixtureReason"]
