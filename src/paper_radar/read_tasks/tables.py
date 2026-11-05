"""Read 查询使用共享 schema 的表;DDL 仅由 migration 管理。"""

from paper_radar.storage import schema

budgets = schema.read_budgets
tasks = schema.read_tasks
registrations = schema.read_registrations
attempts = schema.read_attempts
renewals = schema.read_renewals
outcomes = schema.read_outcomes
analyses = schema.read_analyses
evidence = schema.read_evidence
