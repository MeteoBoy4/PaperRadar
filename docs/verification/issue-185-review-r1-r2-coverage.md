# #185 r1/r2 修复独立 D1 覆盖

本台账只描述新增工程覆盖，不扩展旧验收组、required 集合或历史结论。
原 285 模块/5281 节点与 41 条 refs 保持；以下四模块独立登记，共 36 个节点。

| 独立模块 | 节点 | 行为 |
| --- | ---: | --- |
| `tests/test_stage_b_review_followup_cli.py` | 13 | 跨论文 A→B→A trace、普通 cgroup/UID/用户 manager/状态拒绝、章节 v2 固定与自洽哈希篡改拒绝、无标题/不可靠标题/父层级、双向元数据健康。版本优先完全沿用共享权威。 |
| `tests/test_stage_b_review_reasons.py` | 12 | 九类未知原因的封闭安全输出、非法 RPC state、CLI --stage bogus 具体原因、只读历史内核写入口无副作用拒绝。 |
| `tests/test_stage_b_report_renderer_migrations.py` | 10 | 非空 b008→b009 原子升级/故障回滚、实际 Schema 与 metadata 的列/PK/UNIQUE/FK/CHECK 一致、原追加保护、拒 renderer3、v2 安全拒绝降级、合成 v1 标准备份与产品子进程/OS 隔离回放原字节。 |
| `tests/test_stage_b_review_source_history.py` | 1 | 原 v28 manifest 原字节及 274 文件历史集合。 |

既有 `test_live_admission_source_guard.py` 的 30 个节点数量保持；当前策略推进到
`pi-admission-v29`，显式 275 文件为原 274 文件加 `experiment/reasons.py`。
原 v1–v28 manifest 保持原字节，同策略键重绑与源码漂移负例保持。

## 合成历史 fixture

`tests/fixtures/stage_b_report_v1.zip` 来自本次修前红灯的真实产品 CLI 合成根，
数据库当时为 b008，存在非空已发布 renderer=1 报告。
pytest 已结束后用 SQLite backup API 取得一致快照，保留 data 成员及原 Markdown；
排除 logs、凭据、认证文件及模型 runtime。来源、19 个成员的 SHA/大小/权限见
`tests/fixtures/stage_b_report_v1.manifest.json`。

- 压缩包：82,126 bytes；SHA-256 `27e3f911f0092fc8afd223afd781c99376071864f19f4c39f97b224ece0c049d`。
- 原报告 SHA-256：`4c0c27698af9ee63d1b1b6a22a87ca58ce7cea6d57e18000f26aa0a48265d8e6`。
- 当前迁移唯一新增节点：`b009_report_renderer`，前驱 `b008_body_selection`；旧节点原字节不改。

## 验证范围

相关 pytest、静态检查、入口兼容组合及只读 scope 审计的实际结果由本次
[处置记录](../../intent/review/issue-185-stage-b-review-r1-r2-disposition.md)和树外原始日志承接。
不运行完整离线门禁，不发布正式组回执，不赋予新树现场执行或 A 验收资格。
合成冷恢复使用仍存在的原 db/data/config/materials，实际核验 OS 拒读与恢复输出原字节；
它不代表用户现场、真实模型、真实论文或 NAS 验收。
