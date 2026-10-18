"""固定官方来源与无凭据显式代理的纯规则。"""

from urllib.parse import unquote, urlsplit

from paper_radar.pi_supply.errors import SupplyError


def checked_url(url: str, source: str | None = None) -> str:
    try:
        parts = urlsplit(url)
        allowed = (
            (
                parts.hostname == "pi.dev"
                and parts.path.startswith("/api/installer/releases/")
            )
            or parts.hostname == "registry.npmjs.org"
            or (parts.hostname == "nodejs.org" and parts.path.startswith("/dist/"))
        )
        if (
            parts.scheme != "https"
            or parts.port not in (None, 443)
            or parts.username is not None
            or parts.password is not None
            or parts.fragment
            or parts.query
            or not allowed
            or any(part in {".", ".."} for part in unquote(parts.path).split("/"))
            or any(character.isspace() for character in url)
            or "\\" in url
            or (source == "registry" and parts.hostname != "registry.npmjs.org")
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise SupplyError("source_forbidden") from None
    return url


def checked_proxy(proxy: str | None) -> str | None:
    if proxy is None:
        return None
    try:
        parts = urlsplit(proxy)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
            or any(c.isspace() for c in proxy)
            or parts.port == 0
        ):
            raise ValueError
    except ValueError:
        raise SupplyError("proxy_invalid") from None
    return proxy
