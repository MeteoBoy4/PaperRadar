# Issue #146 两轴代码审阅（r1）

- 固定比较点：`94ee2d53180efbdf5f49bc159c517c85e0158e7b`
- 比较命令：`git diff 94ee2d53180efbdf5f49bc159c517c85e0158e7b...HEAD`
- 提交：`a7df05b fix: add versioned Wiley RSS main abstract selection (#146)`
- 规格来源：GitHub Issue [#146](https://github.com/MeteoBoy4/PaperRadar/issues/146) 正文；无评论。
- 审查方式：Standards 与 Spec 由两个 fresh-context、具备 `read`/`bash` 权限的只读 subagent 并行完成；本报告仅分轴汇总，不交叉合并或排序。

## Standards

1. **硬违规｜路线图写入回顾叙述**  
   `docs/roadmap.md:106` 新增「`#146 的 v2 工程交付见覆盖与差异`」，属于交付回顾。`docs/agents/roadmap.md:15` 明确规定：「承接责任……只写前向信息，不写回顾叙述。」这会混淆下游责任与实施历史。  
   **最小修复**：删除该交付叙述及其证据链接，保留「四刊 v2 live 须由新计划补跑……」等前向责任。

2. **Judgement call｜Primitive Obsession，并伴 Repeated Switches**  
   `src/paper_radar/fixture_audit/abstract_parser.py:247,252`、`feed_metadata/service.py:78,100` 等以裸 `str` 和重复集合表达封闭版本；`feed_metadata/service.py:342-343,548`、`fixture_audit/resume_rules.py:53-57` 又重复 `v2` 条件映射。新增版本时容易漏改并造成身份映射漂移。  
   **最小修复**：在本次触及模块内共享一个 `Literal`/enum 版本类型及唯一的版本→整数 parser 映射，入口复用校验与转换。

其余已审 hunk 未发现可证实的 Standards 违反或额外 baseline smell。测试：**未运行**；仅执行只读 diff、检索及 `git diff --check`（通过）。

## Spec

未发现符合证据门槛的规格缺失、部分实现、scope creep 或“看似实现但有误”问题。

已直接核对实现与测试：
- v2 按 `content:encoded` → `dc:description` → 其他字段选择，处理缺项、同级冲突及 PLS/Key Points 排除；v1 分支保留（`abstract_parser.py:239-316,446-512`）。
- 审计新计划、Feed 与元数据生产路径均传递并冻结版本；replay、迁移及 backup/restore 有对应覆盖。
- `issue-146-field-diff.json` 逐篇保留字段变化、哈希、长度、截断信号及仲裁结果；partial 原计划未被追加解释或覆盖。
- 四刊 live 补跑与 acquired 注册具有明确后续责任，未作为本票缺失报告。

验证：`uv run --offline --locked pytest -q tests/test_wiley_abstract_v2.py`，**27 passed**。未运行完整门禁或 live 实验。

**汇总：Standards 2 项（1 项硬违规、1 项判断性建议），最严重为路线图承接责任混入交付回顾；Spec 0 项，无轴内最严重问题。**

## 实施者逐项核实与处置

本轮起点 `a7df05be0d22a56134b51e0c2bee0f8c77a32652`；关联 [#146](https://github.com/MeteoBoy4/PaperRadar/issues/146)。以上审查原文保留，以下为逐项判断。

| 项目 | 判断 | 处置与依据 |
| --- | --- | --- |
| Standards 1 路线图回顾叙述 | 采纳 | 删除承接索引中的“v2 工程交付见覆盖与差异”，只保留新计划、fixture 登记和 B 证据前置等前向责任；符合 docs/agents/roadmap.md。 |
| Standards 2 版本裸字符串与重复映射 | 采纳 | 新增 fixture_audit/abstract_versions.py，集中 Literal 类型、受支持规则及规则/整数 parser 双向映射。审计、Feed 与元数据复用校验和映射；省去就地集合和拼接规则名。历史 AuditPlan 刻意保留 str，以维持 unsupported_history 与 corrupt_reference 的错误分类。 |
| Spec 无发现 | 核实一致 | 本轮没有改变 Wiley 主区块选择、v1 文本解释、选样或历史仲裁；旧差异 JSON 已由新入库复算工具逐字段复核一致。 |

本轮覆盖、复算命令与实际验证见[后续台账](../../docs/verification/issue-146-review-followup.md)。未将本轮结果追溯写入原工程证据，未运行完整门禁或 live。
