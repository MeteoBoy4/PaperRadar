"""来源服务共享错误转换;不导入任何生产或审计service。"""

from collections.abc import Callable
from functools import wraps
from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError

from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.storage.artifact_contract import ArtifactError


class ErrorDecorator(Protocol):
    def __call__[**P, R](self, function: Callable[P, R]) -> Callable[P, R]: ...


def controlled(path: str) -> ErrorDecorator:
    def decorate[**P, R](function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def call(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return function(*args, **kwargs)
            except (SQLAlchemyError, ArtifactError):
                raise PaperError(PaperReason.CORRUPT_REFERENCE, path=path) from None

        return call

    return decorate
