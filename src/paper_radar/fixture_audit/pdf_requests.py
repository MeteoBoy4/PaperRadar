"""显式本地取得请求文件;不保存请求文件路径或重写声明。"""

import json
from pathlib import Path

from pydantic import ValidationError

from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.pdf_models import PdfModel


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def read_pdf_request[T: PdfModel](source: Path, model: type[T]) -> T:
    try:
        raw = source.read_bytes()
    except OSError:
        raise FixtureError(
            FixtureReason.SOURCE_UNAVAILABLE, path="pdf.request"
        ) from None
    try:
        json.loads(raw, object_pairs_hook=_unique_pairs)
        return model.model_validate_json(raw)
    except (ValidationError, ValueError, UnicodeError):
        raise FixtureError(
            FixtureReason.INVALID_DECLARATION, path="pdf.request"
        ) from None
