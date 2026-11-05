"""bounded-rpc-v1 / chunking v1 的 Read 渲染/完整帧冻结语义。"""

READ_RENDER_VERSION = "read-render-v1"
SINGLE_FRAME_BYTES = 262144
CORRECTION_CATEGORY_SLOTS = 36
CORRECTION_PATH_CHARACTERS = 192
CORRECTION_ENCODING_BYTES = 12
CORRECTION_FIXED_BYTES = 1024
CORRECTION_SLOT_BYTES = (
    CORRECTION_CATEGORY_SLOTS * CORRECTION_PATH_CHARACTERS * CORRECTION_ENCODING_BYTES
    + CORRECTION_FIXED_BYTES
)

# v1 修正词汇独立冻结;接收器新增规则不能自动扩大模型修正。
CORRECTION_CATEGORIES = frozenset(
    (
        "invalid_context",
        "invalid_identity",
        "duplicate_id",
        "identity_mismatch",
        "invalid_page",
        "invalid_source",
        "unknown_source",
        "unknown_page",
        "invalid_bbox",
        "invalid_charspan",
        "empty_support",
        "duplicate_provenance",
        "unsupported_source",
        "unsupported_mode",
        "missing_allowed_evidence",
        "unexpected_allowed_evidence",
        "invalid_allowed_evidence",
        "unknown_allowed_evidence",
        "invalid_json",
        "missing_field",
        "extra_field",
        "invalid_type",
        "invalid_enum",
        "invalid_text",
        "invalid_score",
        "language_mismatch",
        "value_types_required",
        "duplicate_value_type",
        "invalid_evidence_id",
        "duplicate_evidence",
        "unknown_evidence",
        "evidence_required",
        "evidence_not_allowed",
        "output_without_support",
        "invalid_degrade_policy",
        "invalid_attempt_ordinal",
    )
)
