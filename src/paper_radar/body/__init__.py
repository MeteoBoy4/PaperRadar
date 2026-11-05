"""正文附加、前置事实与持久提取的公共服务。"""

from paper_radar.body.models import BodyError, BodyReason
from paper_radar.body.service import BodyService

__all__ = ["BodyError", "BodyReason", "BodyService"]
