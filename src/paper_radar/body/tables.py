"""Body 查询使用共享 schema 的表;DDL 仅由 migration 管理。"""

from paper_radar.storage import schema

roots = schema.body_root
decisions = schema.body_decisions
decision_screenings = schema.body_decision_screenings
pdfs = schema.body_pdfs
samples = schema.body_samples
inputs = schema.body_extraction_inputs
attempts = schema.body_extraction_attempts
outcomes = schema.body_extraction_outcomes
successes = schema.body_extraction_successes
reviews = schema.body_layout_reviews
