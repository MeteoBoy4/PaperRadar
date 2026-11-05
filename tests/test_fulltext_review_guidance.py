"""公开正文拒绝提供有限的安全下一步。"""

import pytest

from paper_radar.fulltext.models import FulltextError


@pytest.mark.parametrize(
    "reason,guidance",
    [
        ("conversion_incomplete", "请核对 PDF 与解析配置后重新提取"),
        ("ambiguous_reading_order", "请核对 PDF 阅读顺序与解析配置后重新提取"),
        ("unknown_parent", "请核对正文层级与解析配置后重新提取"),
        ("invalid_hierarchy", "请核对正文层级与解析配置后重新提取"),
        ("invalid_encoding", "请核对原 PDF 字符与解析配置后重新提取"),
        ("invalid_members", "请从完整备份恢复正文制品后重试"),
        ("identity_mismatch", "请核对引用的正文身份或从完整备份恢复后重试"),
        ("quality_failed", "请人工核对 PDF 与质量诊断,修正输入或解析配置后重新提取"),
        ("unknown_evidence", "请使用该分析保留的合法 evidence ID 回查"),
    ],
)
def test_fulltext_error_has_controlled_reason_and_next_step(
    reason: str, guidance: str
) -> None:
    error = FulltextError(reason)
    assert error.reason == reason
    assert str(error) == f"正文制品拒绝：{reason}；{guidance}。"
