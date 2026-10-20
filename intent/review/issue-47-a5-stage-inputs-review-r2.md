# Code review：issue-47 A5 阶段输入（r2）

- 分支：`integration/issue-47-stage-inputs`（HEAD = `f774831ae4308b1c41dc9f2249af571429e9df9d`）
- Fixed point：`main` = `4a5f4e8c850eab3da3fcf78f118d15864b7496e9`
- Diff：`git diff main...HEAD`（三点，58 文件，+6172/−73，15 个 commit，#48–#54）
- Spec 来源：GitHub Issue #47（正文 + 「实施前补充说明」C1–C12 + 「C1 裁决」+「A5 实施前补充（三）」）及子票 #48–#54；#47 末条实现者完成报告不计入 spec
- 标准来源：`AGENTS.md`、`CLAUDE.md`、`GLOSSARY.md`、`docs/adr/`、`docs/agents/{python-conventions,testing,cli-output,documentation,refactor,invariants,calibration,llm-evidence,scope,domain}.md`、`docs/contracts/`、`pyproject.toml` + Fowler smell 基线（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`）
- 方式：Standards、Spec 两轴由两个并行只读 subagent（均授予 Bash）独立审查后聚合；两轴分列，未混合排序；未修改代码、未创建 commit

---

## Standards

### (a) 硬违规（1 处）

`docs/agents/documentation.md`：「行为偏离 `intent/draft.md` 且已获用户允许时，同步修改该文稿的相应表述。」

`docs/contracts/stage-inputs.md:306-311` 明写 extraction 格式 1 不纳入 `intent/draft.md:630`（用规范题名/DOI/摘要识别仓储封面）所需元数据，仅"留待阶段 F"，而 `intent/draft.md` §4.9 未同步该裁决 → 偏离只写在 Contract，未进文稿。

> 聚合注：这是 `documentation.md` 与 #47「C1 裁决」（原文：「不修改 `intent/draft.md` §4.9 原文；措辞收敛留给阶段 F 票随实现一并窄修」）之间的**直接冲突**。按 `AGENTS.md`「冲突时保持已有安全行为，向用户指出冲突并由用户裁决」，实现方遵守了用户裁决，故此处应视为**待用户裁决的标准-裁决冲突**，而非实现方擅自违规。

其余标准项合规：CLI 中文/下一步（`scripts/a5_acceptance.py:66-99` 全带"请…"）、离线测试、无新依赖且 `uv.lock` 未动、模块单向依赖（`tests/test_stage_input_architecture.py`）。

### (b) 基线 smell（均为判断题）

- **Duplicated Code**：`scripts/a5_acceptance.py:103-164` 的 `_environment`/`_migrated_revision` 与 `a4_acceptance.py:101-146` 逐字重复（仅 enum 名与 tempdir 前缀不同），a2_full/a3 各已有一份 → 第 4 份。
- **Duplicated Code + 魔法字面量**：`a5_acceptance.py:251-262` 与 `a4_acceptance.py:230-241` 同形 or-chain，并硬编码 `35/29/13/25`，而这些常量已在 `a3_scope.py:204-205`、`a2_full_scope.py:8` 定义 → 改前置身份要双改（**Shotgun Surgery**）。
- **Repeated Switches**：`service.py` 阶段分派写 6 遍（`build_stage_input` expected_type 字典、`_facts_payload:472`、`_replay_source:627`、`_replay_facts:660`、`compare_stage_inputs:729-770`、上下文两法）。
- **Primitive Obsession**：`service.py:735,763` 用 `assert isinstance(...)` 收窄三型联合，`-O` 下即失效，未走受控 reason。
- **Mysterious Name / 一词一义**：`a5_scope.py:3-5` `ISSUE = PARENT_ISSUE = 47`，与 a4（issue 45/parent 36）语义相反；README 又称"A5 由 #54 接入"。
- **Data Clumps**：`a5_acceptance.py:234-246` 以字符串拼 `result[label+"_file"/"_sha256"]`，5 组兄弟字段无类型。

### (c) 被抑制的候选 smell

`__init__.py` 薄转发（文档定为公共边界）、`MappingProxyType` 只读版本映射、封闭 reason enum、各组自带判据并共用 `publish_conclusion`（`docs/verification/offline-evidence.md` 明文认可）→ 不报 **Middle Man** / **Speculative Generality**；无 **Feature Envy** / **Refused Bequest**。

### (d) 文档同步

`GLOSSARY.md` 增「复用升级摘录」(211)、「阶段输入载荷」(382)；README 增「阶段输入」节与七份文件；`artifact-store`/`backup-restore`/`config-projections`/`screening-validation`/`pi-supply` 交叉链接齐全；`offline-evidence.md` 增 A5 判据表。缺口仅 (a) 的 §4.9 与 draft 无 #47–#54 交付进度标注。

### (e) 抽查

`src/paper_radar/stage_inputs/service.py` + `tests/test_stage_inputs.py`（固定字面量载荷、无 skip）；`scripts/a5_acceptance.py` + `tests/test_a5_test_receipt.py`（真实插件回执、6 种模式含 skipped/deselected）。

---

## Spec

### (a) 缺失 / 半成品

1. 决策 20 原文要求绑定「前置 A1、完整 A2、A3、A4 结论」；实现只依赖 A1/完整 A2/A3（`scripts/a2_full_acceptance.py:415`）。按补充七与 #54 是**已批准的偏离**且 `offline-evidence.md` 说明理由 → 判定可接受，但 A5 passed 不蕴含 A4。
2. 测试表「书目与审计隔离」的"普通声明标签、注释"与「模型与适配器」的"权威 Contract 变化"未在 A5 层用真实快照变体证明，只靠"指纹仅引用 projection_id"的结构保证 + A2 矩阵 → 半覆盖。
3. Contract 称回放拒绝"重复 JSON 键"（`stage-inputs.md:89`）无对应用例；实际由逐字节比较兜成 `non_canonical`，属未验证断言。

### (b) 越界（scope creep）

`GLOSSARY.md` 增「复用升级摘录」词条（补充八只点名「阶段输入载荷」与「价值预测」窄修）；新增 `artifact-store.md`、`backup-restore.md` 互链（补充六只允许 `screening-validation.md` 一条）。均文档级，未改契约语义 → 不阻断。

### (c) 疑似有错

1. `service.py:679` 硬编码 `projection_version != 1`，而 `stage-inputs.md`「格式版本公开访问」称 `STAGE_INPUT_FORMAT_VERSIONS` 是"构造、回放和 A5 格式核对共同消费的生产权威"——它只管阶段格式；投影格式权威被分散，提升时需改两处，仅靠 A5 漂移检查兜底。
2. `service.py:376-378` `value_prediction_context` 抛 `ReplayReason`，与补充三"按面三张封闭词表"混用（Contract 已注明），按 `BuildReason` 判因会漏。
3. `SelectedExcerpt` 的 kind 错误折叠为 `invalid_facts / facts.excerpts`（无 `facts.excerpts.kind`），诊断精度低于 `excerpt_id`/`text`。

### 逐项结论

决策 3 ✅ 身份域(kind/stage/格式/投影 id)分离 + 独立字面量向量；5 ✅ `snapshot.stages[stage]`、`not_ready` 带 readiness、reuse 不读 extraction 就绪；6 ✅ 精确文本、`str.strip()` 纯空白拒绝、bool 严格，NFC/NFD、CRLF 变身份（子进程）；9/10/11 ✅ ID 调用级唯一先于映射、payload 成员哈希、extraction 指纹 + reading/evidence_map、manifest 排除（真实 ArtifactStore）；"限定正文范围"按 C5 降为生产者义务、未虚报；13 ✅ 唯一派生同源（词表问题见 c2）；14 ✅ 冻结 + 严格拒绝（实测 both/data/空白 ID/重复 ID 全拒）；15 ✅ 逐字节 + 指纹 + 历史投影，unverifiable/mismatch 分离；16 ✅ 固定顺序、无原文、跨阶段不可比；17 ✅ 无审计字段、10×6 参数化拒绝；20 ✅ required、14 模块 513 例固定、migration head 未变；21 ✅ 四处陈旧表述（含 `draft.md:1223`）已修。

### 测试表落点

「算法版本」`replace` 纯 fixture + 真实 compile 拒绝（`test_stage_input_extraction.py:110/130`、`test_stage_input_reuse.py:298/321`）、「审计 manifest」`test_stage_input_extraction_reuse.py:127`、「历史恢复」恢复库 `get_artifact` 重建（子进程，实测通过）、「无业务副作用」架构 1 例 + DB 字节不变、「描述回放」7 例；实测 396 + 117 = 513 全通过。

### A5 宣称核对

7 项能力与 scope 一致，`not_assessed` 15 项为建议超集，README/`offline-evidence` 措辞与实现一致，未发现夸大。提醒：工作区现存未跟踪 `intent/review/issue-47-a5-stage-inputs-review-r1.md`，若在 `check-offline` 前存在需确认不破坏"干净工作树"绑定。

---

## 核对与限制

- **过程限制**：首轮 `reviewer` subagent 实际未加载 Bash（工具集为 read/grep/find/ls），Spec 轴无法执行 `gh issue view 47 --comments`，其结论仅基于仓库内转写；因此两轴均已用具备 Bash 的 agent 重跑，本节结论取自重跑结果，首轮结果未采用。
- **已由我实跑的抽查**：
  - `scripts/a5_acceptance.py:151-152` 确为 `from paper_radar.config.projections import PROJECTION_FORMAT_VERSIONS` / `from paper_radar.stage_inputs.service import STAGE_INPUT_FORMAT_VERSIONS`；`PROJECTION_FORMAT_VERSIONS` 不在 `src/paper_radar/config/__init__.py` 的 `__all__` 中。先例：`scripts/a2_full_acceptance.py:127` 同样从 `config.projections` 导入，故此写法并非本次新引入。
  - `src/paper_radar/stage_inputs/service.py:679` 确为 `projection_version != 1` 硬编码；同一文件 `_parse`（`:554-557`）使用裸 `json.loads`，无 `object_pairs_hook`，故「重复 JSON 键」只能跌入逐字节比较的 `NON_CANONICAL`。
  - `scripts/a2_full_acceptance.py:415` A5 `dependencies=("A1", "完整 A2", "A3")`，与 #47 补充七的批准偏离一致。
  - `scripts/a5_scope.py:3-5` `ISSUE = 47` / `PARENT_ISSUE = 47`；此项在 #47 补充六中已被 spec 明确许可（"`PARENT_ISSUE` 留空或填 47，不要指向已关闭的 #36/#45"），故属 spec 认可行为而非未受控命名。
  - `service.py:735,763` 确以 `assert isinstance(...)` 收窄联合类型。
  - `GLOSSARY.md` 新增「复用升级摘录」「阶段输入载荷」两条，且「价值预测」已补入"已启用主题"窄修。
- **未验证**：`./scripts/check-offline` 未在本次审查中重跑（只读审查范围）；`intent/review/issue-47-a5-stage-inputs-review-r1.md` 为未跟踪文件，可能影响 A5「干净工作树」绑定，需在下次验收前处理。

## 汇总

- **Standards 轴：7 项发现**（1 项文档化标准违背——且已与 #47 C1 用户裁决直接冲突，待用户裁决；6 项判断题 smell）。轴内最重：`intent/draft.md` §4.9 未同步 C1 裁决（`documentation.md` 明确要求同步，但 C1 裁决明确禁止修改）；若仅按 smell 计，最重为 `scripts/a5_acceptance.py` 与 `a4_acceptance.py` 的验收骨架第 4 份重复。
- **Spec 轴：8 项发现**（3 缺失/半成品、2 文档级越界、3 疑似实现有错）。轴内最重：`docs/contracts/stage-inputs.md:89` 宣称回放拒绝「重复 JSON 键」但无对应用例、实际只兜成 `non_canonical`，属未被测试证明的契约断言。
- 两轴分列，不做跨轴合并排序。

---

## 实现者逐项核实与处理（2026-10-20）

本节为实现者追加的核实记录，关联 #47、#48、#49、#51、#52、#53、#54。上文原始审查意见
保持原样；下面的接受/拒绝由实现者负责，不冒充审查人改口。用户已授权修复与当前分支提交，
同一 implementer 完成全部修改。

### Standards

| 原发现 | 处理 | 可验证依据与结果 |
| --- | --- | --- |
| (a) C1 与 documentation.md 冲突，待再次裁决 | 不采纳 | [C1 用户裁决](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6265245363)已明确“不修改 intent/draft.md §4.9 原文”，按用户指令优先规则执行即可，不是新的待裁决冲突或实现违规。保持 §4.9 与 Contract 的已知未决问题，不能借文档通则覆盖裁决。 |
| (b)1 环境版本与真实迁移探针重复 | 部分接受 | 抽至既有 `verification_checks.py:31/49`，A4/A5 实际消费；组内依赖清单、错误原因、异常边界和判据保持独立。原 `test_a4_acceptance`/`test_a5_acceptance` 的实际依赖缺项、新 migration head、中断覆盖仍走 writer 公共面。未扩成通用验收引擎，未顺手重构 a2_full/a3。 |
| (b)2 前置 or-chain 与 scope/issue 魔法字面量 | 部分接受 | A4/A5 的 A3 scope/issue/parent 与完整 A2 scope/issue 改用既有 `a3_scope`、`a2_full_scope` 权威常量（`a4_acceptance.py:194/199`、`a5_acceptance.py:216/221`）。A1 当前只有 writer 结果中的字面量，未为消除字面量扩大历史 A1 范围。各组反向链接判据仍独立；接受的前置格式继续显式白名单，producer 格式升级不自动授权新消费者格式。 |
| (b)3 repeated switches | 不采纳 | build 的事实类型约束、事实编码、来源解码、事实回放、比较组件及 context 是不同职责的封闭分派；没有复制 builder/replayer 或公共编码/哈希。#47 决策14 与 #53 允许逐类型校验及阶段分支；统一动态注册器会扩大机制，不构成必要修复。 |
| (b)4 assert 在 -O 下失效 | 不采纳 bug 判断 | `StageInput.__init__` 禁止直接构造，公共 build 严查阶段/事实配对，replay 按阶段解码并经私有 `_assemble` 返回；compare 中 assert 只做已验证联合类型收窄。实际用 `uv run --offline --locked python -O` 跑四阶段/两类 reuse 共5条 build→replay→compare 路径均为 same，非法事实配对全部仍由 `BuildReason.INVALID_FACTS` 拒绝；未通过破坏 frozen 对象伪造公共漏洞。 |
| (b)5 ISSUE=PARENT_ISSUE=47 命名 | 不采纳 | [补充三第六节](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6266736991)及 #54 明确允许此值。#47 是本组范围归属，#54 是接入实施票，README 两种关联并不矛盾。 |
| (b)6 result 的五组 file/sha256 兄弟字段 | 不采纳 | 它们是封闭输出 Schema 的固定字段，已有 `paths` 映射驱动同次文件和字节核对。writer/entry 失败矩阵验证缺项、篡改、串用及发布前复核；未发现字段错配，不引入泛型 binding 框架。 |
| (c) 已抑制的候选 smell | 核实后保持 | 公共薄转发、只读映射、封闭原因与共享 `publish_conclusion` 都有明确职责，保留。 |
| (d) §4.9 与 draft 未标 #47–#54 交付进度 | 不采纳 | §4.9 按 C1 已裁决；draft 的日期状态注记不是 mandatory 交付账本。README 与 offline-evidence 已准确描述能力及未验收范围，#47/#54 为进度权威，不新增无要求的状态同步。 |
| (e) 抽查通过 | 核实后补强 | 保留独立字面量向量与真实回执拒绝矩阵；本轮新增16个功能用例，A5 总数由513增为529（功能412+验收117），没有删除或跳过旧例。 |

### Spec

| 原发现 | 处理 | 可验证依据与结果 |
| --- | --- | --- |
| (a)1 A5 不直接依赖 A4 | 不采纳缺失判断 | [补充三第二节](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6266736991)、#54 验收标准与最终澄清明确授权 A1/完整A2/A3 直接前置。A4 仍是整体必需组，A5 passed 不蕴含 A4；原 entry 测试继续分别验证整体失败和本组前置失败，未改依赖。 |
| (a)2 普通声明/注释与权威 Contract 变化半覆盖 | 部分接受 | `test_stage_input_dependencies.py:115` 新增两类代表性的真实声明重命名+注释 compile/load 快照变体，四阶段字节不变；`:142` 沿 A2 纯 fixture 先例验证 boundary/value/reuse 三类未来权威 Schema 标记只改变相应消费者，真实 compile 仍拒绝 fixture-v2 且原历史快照可 load。未登记假生产 v2、未改冻结输出，也未复制 A2 的全组件矩阵。 |
| (a)3 无重复 JSON 键用例，NON_CANONICAL 不足以证明拒绝 | 不采纳原判断；补强覆盖 | 原 `test_replay_rejects_equivalent_but_noncanonical_bytes`（现 `test_stage_input_replay.py:125`）已经含重复 kind 且断言 `NON_CANONICAL`，原审查“无用例”是误报。逐字节 canonical 比较能严格拒绝被 json.loads 折叠的重复键，无需 object_pairs_hook。`:140` 窄补嵌套投影同值/冲突键、事实题名冲突键及敏感值不入异常链。 |
| (b) GLOSSARY 增复用升级摘录越界 | 不采纳 | #47 决策21 要求必要术语同步，[实施前补充第二节](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6265057026)澄清 excerpt_id/locator 概念，#53 要求总核对；补充八点名的窄修不是排他白名单。词条说明现有公共事实，不扩展业务能力。 |
| (b) artifact-store/backup-restore 互链越界 | 不采纳 | #47 决策21 与 #53 明确要求跨契约互链及消费者义务核对；“可选 screening-validation 一句”不是禁止其他准确互链。链接只解释现有来源成员/恢复消费者职责，不改变相关契约语义。 |
| (c)1 projection_version != 1 无名边界 | 部分接受 | `service.py:451` 命名封闭的 `_SUPPORTED_REPLAY_PROJECTION_FORMATS={1}`，回放实际消费；独立于 config 当前写出格式。`test_stage_input_replay.py:153` 验证即使当前投影提升为2，未知格式在无快照/有快照回放中仍拒绝；原历史格式与当前不同仍为不可核对。Contract 澄清 `STAGE_INPUT_FORMAT_VERSIONS` 只管阶段输入配方，不承担历史投影支持权威。未自动绑定未来 current 版本、未扩大支持范围或导入 config 私有实现。 |
| (c)2 value_prediction_context 抛 ReplayReason | 接受 | 先红测发现3处失败，再让同一 `_verify_projection` 按调用面使用原因类；context 的非法快照/不可核对/不匹配全部是 `BuildReason`，replay 保持 `ReplayReason`。新增 BuildReason 两个投影成员，README/Contract 同步；`test_stage_input_value.py:123/281/336` 验证原因归属及脱敏，27例通过。 |
| (c)3 SelectedExcerpt kind 位置不精确 | 接受 | 先红测6处失败，新增封闭 `InputField.EXCERPT_KIND=facts.excerpts.kind`。非法 ID/种类通过同一 `ReuseAssessmentContext` 权威区分（两者非法先报 ID），没有复制 ID/kind 规则或保留原异常；`test_stage_input_reuse.py:174` 验证6种位置与无泄漏，原 both/data 拒绝仍有效。 |
| “逐项结论”“测试表落点”“A5 宣称核对”其余正向结论 | 核实后保持 | 未变阶段配方、独立向量、真实 ArtifactStore/恢复消费者、无 I/O/无业务副作用与未来算法反例。context 词表与重复键判断按上列纠正，其他已交付能力继续由相关测试及正式门禁验证。 |

### 运行身份、验证与限制

原报告关于“未跟踪报告可能破坏干净工作树绑定”的提醒需要纠正：门禁要求同次身份稳定，
并不强制 clean。`verification_identity.capture_identity` 与 `verification_checks.identity_matches`
支持真正 bool 的 dirty 标记；两份报告属于非忽略字节，也进入 `worktree_sha256`。本次将原文与
附录纳入提交，保留历史审阅记录。报告、文档、测试与静态哈希在正式入口启动前全部完成，
正式运行中不改非忽略文件；run_id 与实际结果放本次提交信息/实现者汇报，避免完成后再写回
报告导致身份漂移。旧 scope 仅重绑这次共享探针、writer 与必要传递哈希，旧分母、冻结材料不变。

已观察到的红绿结果：context 修复前3失败、修复后27通过；摘录定位修复前6失败、修复后
reuse+正文复用125通过；回放模块33通过；依赖薄交叉14通过；mypy 全273文件通过。
正式相关组合与完整门禁由最终提交信息记录，运行环境统一为
`TMPDIR=/tmp GIT_CEILING_DIRECTORIES=/tmp UV_NO_SYNC=1 uv run --offline --locked …` 与同环境
`./scripts/check-offline`，复用现有 .venv；不把 TMPDIR 放主仓避免 wheel 隔离测试误判。

原审查工具权限/未重跑完整门禁的过程限制保留为历史事实；本轮不将其当作产品缺陷。
未验证 live RPC、真实来源、Pi/Docling 实际执行、NAS 与自动精读；C1 封面识别仍按既有裁决
留给阶段 F，未修改 §4.9、Frozen Contract、已登记版本、指纹字节、migration 或 lockfile。

验证补记：首次完整运行 `38d08b69b2d04dd3a90531a9abd7d19c` 在测试阶段受控中断，结果
incomplete/exit1，保留旧证据。原因是只读复核发现新增未来 Contract 反例用全局字符串替换时，
boundary 同时命中 prompts 与 contracts，可能以缺 Prompt 假阳性通过。运行结束后已修正为
只修改解析后的 `settings["contracts"][selector]`，并匹配 `contracts.<selector>` 错误位置；
原 Prompt 保持不变。该测试及必要固定哈希更新后重新跑相关测试与正式入口，成功运行以提交
信息记录为准，不将前一运行或原有宽泛异常断言当作最终验收。
