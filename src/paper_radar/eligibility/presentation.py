"""质量失败的中文指引;DTO 继续使用 QualityFailure 的受控 wire 值。"""

from paper_radar.eligibility.models import QualityFailure

QUALITY_FAILURE_GUIDANCE = {
    QualityFailure.PDF_TEXT_LAYER: "PDF 无可靠文本层；保留原件，拒绝 Read。",
    QualityFailure.BODY_BOUNDARY: "正文起点未通过检查；核对封面与授权页信号。",
    QualityFailure.READING_ORDER: "阅读顺序或章节层级不可确定；核对规范正文。",
    QualityFailure.EVIDENCE_REPLAY: "源字符定位缺失或不可回放；不得调用 Read。",
    QualityFailure.CONTENT_IDENTITY: "内容与登记身份不符；停止消费并核查制品。",
    QualityFailure.LAYOUT_REVIEW: "人工版式核查未通过；当前提取指纹不可重试。",
    QualityFailure.REPRESENTATIVE_COVERAGE: "四刊覆盖未满足；由 F 提供正式依据。",
    QualityFailure.SOURCE_GENERATED_SEPARATION: "源与生成混合；候选不能冒充原文。",
    QualityFailure.EMBEDDED_BINARY: "制品含内联二进制或 base64；拒绝 Read。",
    QualityFailure.TEXT_INTEGRITY: "文本含替换字符或无效编码；拒绝 Read。",
}


def quality_failure_guidance(failure: QualityFailure) -> str:
    return QUALITY_FAILURE_GUIDANCE[failure]
