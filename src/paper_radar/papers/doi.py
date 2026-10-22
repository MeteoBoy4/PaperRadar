"""DOI 规则 v1;不联网、不依赖持久化。"""

import re
import unicodedata
from urllib.parse import unquote, urlsplit

from paper_radar.papers.errors import PaperError, PaperReason

DOI_RULES_VERSION = 1
_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def normalize_doi(value: str) -> str:
    def invalid() -> PaperError:
        return PaperError(PaperReason.INVALID_DOI, path="doi")

    if type(value) is not str:
        raise invalid()
    try:
        if len(value.encode("utf-8")) > 8192:
            raise invalid()
        value = value.strip()
        if not value or len(value.encode("utf-8")) > 2048:
            raise invalid()
        if any(c.isspace() or unicodedata.category(c).startswith("C") for c in value):
            raise invalid()
        lowered = value.translate(_ASCII_LOWER)
        if lowered.startswith(("http:", "https:")):
            try:
                url = urlsplit(value)
                if (
                    url.scheme.translate(_ASCII_LOWER) not in {"http", "https"}
                    or url.hostname not in {"doi.org", "dx.doi.org"}
                    or url.username is not None
                    or url.password is not None
                    or url.port
                    not in (None, 80 if url.scheme.lower() == "http" else 443)
                    or "?" in value
                    or "#" in value
                ):
                    raise PaperError(PaperReason.UNSUPPORTED_FORM, path="doi")
                value = url.path[1:] if url.path.startswith("/") else url.path
                if re.search(r"%(?![0-9A-Fa-f]{2})", value):
                    raise invalid()
                value = unquote(value, encoding="utf-8", errors="strict")
            except UnicodeError:
                raise invalid() from None
            except ValueError:
                raise PaperError(PaperReason.UNSUPPORTED_FORM, path="doi") from None
        elif lowered.startswith("doi:"):
            value = value[4:]
        if (
            len(value.encode("utf-8")) > 2048
            or any(
                c.isspace() or unicodedata.category(c).startswith("C") for c in value
            )
            or re.fullmatch(r"10\.[0-9]+(?:\.[0-9]+)*/.+", value) is None
        ):
            raise invalid()
        return value.translate(_ASCII_LOWER)
    except UnicodeError:
        raise invalid() from None
