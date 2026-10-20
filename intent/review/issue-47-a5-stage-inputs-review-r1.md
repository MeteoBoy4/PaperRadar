# Code review：issue-47 A5 阶段输入（r1）

- 分支：`integration/issue-47-stage-inputs`（HEAD = `f774831`）
- Fixed point：`main` = `4a5f4e8c850eab3da3fcf78f118d15864b7496e9`
- Diff：`git diff 4a5f4e8...HEAD`（三点，58 文件，+6172/−73，15 个 commit，#48–#54）
- Spec 来源：GitHub Issues #47（正文 + 实施前补充 6265057026 + C1 裁决 6265245363 + 第三轮补充 6266736991）及子票 #48–#54；#47 末条实现者完成报告不计入 spec
- 标准来源：AGENTS.md、GLOSSARY.md、docs/adr/、docs/agents/{python-conventions,testing,cli-output,documentation,refactor,invariants,calibration,llm-evidence,scope,domain}.md + Fowler smell 基线（仓库无 CODING_STANDARDS.md / CONTRIBUTING.md）
- 方式：Standards、Spec 两轴由两个并行只读 subagent（含 Bash 权限）独立审查后聚合，未混合排序；未修改代码、未创建 commit

## Standards

**与文档化标准冲突（硬违规）：0 项。** 核对 AGENTS.md、docs/agents/*、docs/adr/ 与 docs/contracts/stage-inputs.md：文档同步齐备（GLOSSARY 两术语、契约、README、intent/draft.md #46/#36 裁决同步）；`stage_inputs` 仅依赖 config/screening 公共面且有架构测试；错误/帮助文案中文并含下一步；载荷敏感文本未进 repr/异常/stdout（测试断言）；无新依赖、无 migration。

**基线 smell（判断题）：**

- 疑似 Duplicated Code：`scripts/a5_acceptance.py` 与 `scripts/a4_acceptance.py` 高度同构（~450 行：`_HELP`+逐 reason 追加+超长 or 链）；公共形状已部分抽入 `verification_checks`，剩余骨架仍可在下组接入前合并。
- 疑似 Duplicated Code：`src/paper_radar/stage_inputs/service.py` 中 ScreeningFacts/SourceSnapshotRef/SelectedExcerpt/ExtractionFacts/ReuseFacts/StageInput 重复 `_MISSING`+`**extra` 拒绝+`object.__setattr__` 构造样板；契约要求逐类型严格事实（部分压制），仍可收敛为公共工厂。
- 疑似 Data Clumps：`service.py` ReuseFacts 将 `extraction_fingerprint/reading_sha256/evidence_map_sha256` 手工组装三元组作正文身份，可提为 ExtractionRef 的 identity 属性。

## Spec

**0 项发现。** 高风险项逐一核实均符合：

- **C1 裁决**：`ExtractionFacts` 仅 `pdf_sha256`，题名/DOI/摘要经严格 `**extra` 拒绝；`docs/contracts/stage-inputs.md` 登记「C1 已知未决问题」，链接 §4.9 与用户裁决、写明阶段 F 两出路（#50）。
- **不复制第二套实现**：`service.py` 单一 `_canonical/_assemble/build/replay/compare`，阶段差异仅事实类型与固定组件表（#48/#49/#51/#52）。
- **回放纯度**：`replay_stage_input` 无 I/O，投影核对仅消费显式快照，`projection_format_unverifiable` 与 `projection_mismatch` 分立（#48、C11）。
- **脱敏**：`StageInputError` 仅含封闭 reason/field(+readiness)，未知键折叠至容器位置；测试断言 `__context__ is None`、PRIVATE_A5 不入 repr/stdout/caplog。
- 其余：封闭原因三词表、结构化/正文/混合来源与 manifest 审计隔离（真实 ArtifactStore）、跨进程 PYTHONHASHSEED、恢复后经 `get_artifact` 重取成员、独立向量（自行核算 6 份 fixture 哈希全符）、A5 组 required 且前置不含 A4、七份主要文件与 check-offline 帮助同步、GLOSSARY/#36/#46 窄修、依赖矩阵薄交叉检查——均落实且无 scope creep。

## 汇总

- Standards 轴：3 项发现（0 硬违规 + 3 判断题 smell）；轴内最重：`a5_acceptance.py` 与 `a4_acceptance.py` 约 450 行同构（疑似 Duplicated Code）。
- Spec 轴：0 项发现，无轴内最重问题。
- 两轴分列，不做跨轴合并排序。

---

## 实现者逐项核实与处理（2026-10-20）

本节由修复实现者追加，关联 #47、#48、#49、#51、#52、#53、#54；上文保留为原始审查记录，
不表示原审查人重新出具结论。与 r2 重复的意见只修复一次。当前用户已授权核实、修复及提交，
全部代码与报告修改由同一 implementer 完成。

| 原发现 | 处理 | 可验证依据与结果 |
| --- | --- | --- |
| Standards：A4/A5 验收重复 | 部分接受 | `scripts/verification_checks.py:31` 的 `environment_versions` 与 `:49` 的 `migrated_revision` 收敛实际版本采集及真实临时库 base→head 探针；`a4_acceptance.py:100`、`a5_acceptance.py:102` 实际调用。组内原因、判据、异常分类、返回形状继续独立，未抽整套 writer/原因引擎，未重构 a2_full/a3。既有 writer 的缺依赖、中断、新迁移 head 反例继续覆盖共享探针。必要 scope 哈希链显式更新，未放宽门禁。 |
| Standards：严格事实类型的构造样板 | 不采纳 | `service.py` 各 frozen 类型拥有不同字段、位置及语义校验，`StageInput` 还禁止公共直接构造；样板主要是严格拒绝 `**extra` 与不可变赋值。#47 决策14、#53 明确保留合理事实类型与分支，不要求继承体系。通用字段桶/工厂会隐藏逐类型安全边界，未发现规则漂移，不因相似赋值引入抽象。 |
| Standards：ExtractionRef 三哈希组合 | 接受 | `ExtractionRef.identity`（`service.py:237`）只读封装 `(extraction_fingerprint, reading_sha256, evidence_map_sha256)`，`ReuseFacts` 用它检查同次正文一致性；定位仍可不同。未新增持久化对象或改变载荷，原正文/混合来源独立向量与一致性测试保持通过。 |
| Spec：0 项发现及列举的安全边界 | 核实后保持 | C1 保留 PDF-only 配方及 §4.9 原文，见用户裁决 [C1](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6265245363)；A5 scope、直接前置及薄交叉边界按 [补充三](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6266736991) 与 #53/#54 保持。回放、脱敏、来源内容绑定及恢复路径由原测试及本轮相关测试继续验证。 |

本轮另落实 r2 中合理的 context 原因归属、摘录 kind 位置、历史投影格式支持边界与少量
交叉覆盖；详见 r2 同日附录。Frozen Contract、已登记配置版本、阶段指纹字节、migration、
lockfile 均未修改。A5 功能范围从 396 增至 412 例，验收/入口/回执仍为 117 例；新增期望
均显式登记，不在交付运行中动态刷新。

两份报告原为未跟踪文件，本次将原文与附录一并提交。`capture_identity` 对稳定 dirty 工作树
计算身份，并不要求 clean；报告字节属于非忽略工作树，会进入 `worktree_sha256`。
附录、文档、测试与哈希登记均在正式 `check-offline` 开始前完成，运行中不修改非忽略文件；
正式全门禁的 run_id 与结果记录在本次提交信息和实现者汇报中，避免验收后编辑报告使身份漂移。
离线证据不代表 RPC、真实来源、Docling/Pi 实际执行、NAS 或自动精读已经验收。

验证补记：首次完整运行 `38d08b69b2d04dd3a90531a9abd7d19c` 在发现新增 Contract 反例会
同时替换同名 Prompt selector 后受控中断，保留 incomplete 证据，未作为通过依据。
修正为只改解析后的 `settings["contracts"][selector]`，并断言 `ConfigError` 的 contracts
字段路径；随后更新该测试的固定哈希再正式重跑，原 Prompt 选择保持不变。
