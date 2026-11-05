"""已登记 PDF 的字节身份检查;异常与消费资格由调用方决定。"""

import hashlib


def valid_pdf_bytes(raw: bytes, expected_sha256: str) -> bool:
    return (
        len(raw) >= 1024
        and raw.startswith(b"%PDF-")
        and hashlib.sha256(raw).hexdigest() == expected_sha256
    )
