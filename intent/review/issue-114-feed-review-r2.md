# Issue #114 Feed 交付双轴审查 r2

## 审查范围与来源

| 项 | 值 |
| --- | --- |
| 固定点 | `main` = `543942c55b3357720cbaf0c4965ded0bdbff1044` |
| HEAD | `fb52cd7e87b7febb558596fb3918fe4155a43890`（`integration/114-feed`） |
| Diff 命令 | `git diff main...HEAD`（三点，对 merge-base） |
| 规模 | 102 文件，+6305 / −231，18 个提交 |
| 主规格 | GitHub Issue #114（22 条 User Stories、11 条 Implementation Decisions、Testing Decisions、Out of Scope、Further Notes） |
| 子规格 | #115–#119 正文；其评论均为实现者完成报告，未发现用户裁决评论 |
| 交付声明 | `docs/verification/issue-114-feed-delivery.md`、`docs/verification/feed-parser-v1.md`、三个 Feed Contract |

提交列表：`fb52cd7` schema 兼容修复；`50f10f2`/`47be9c6` 测试类型；`acaa80a`/`d3bbea4` 独立审查修复与历史 scope 重绑；`62612ae`/`484457d` 身份/provenance/标准审查修复；`0c1891a`/`6f67abb` #119 组合服务；`31b8d88`/`dc0ba85` #117 元数据；`b48beca`/`a5913b7` #116 Feed 取得；`d25ce64`/`531aa5a`/`5c5caa4` #118 语言 provenance；`23f4165`/`22a425e` #115 强冲突证据。

两轴均为只读子 agent，均被授予 `bash`（`git diff|show|log`、`rg`、`sed`、只读 `gh issue view`）。未修改工作树、未创建提交、未运行 live、未运行 `./scripts/check-offline`。

**两轴完成状态**

- Standards：完成。已读 `AGENTS.md`、`docs/agents/*`、`docs/contracts/feed-*.md`、`paper-facts.md`、`screening-tasks.md`、ADR-0030–0036、`pyproject.toml`、`GLOSSARY.md`；实跑相关模块 `ruff check`（`All checks passed`）。缺失来源：该子 agent 未能访问 GitHub，故「是否已有用户裁决覆盖某条」标「未核实」；pytest/mypy 未运行。
- Spec：完成。已用 `gh issue view 114–119 --comments` 拉取正文与评论；实跑 `uv run --offline --locked pytest tests/test_feed_conflicts.py tests/test_feed_language.py -q` → `30 passed in 8.71s`。未验证：真实 JGR/HTTP live、语言来源约定、`run_id=4af951c3…` / 5274 固定 scope 回执（原始 JSON 在仓库外）、生产 parser 与审计的字段级机械比对。

---

## Standards

### 文档化标准违反

1. **共享审计解释就地变更**｜`src/paper_radar/fixture_audit/abstract_parser.py:262-268`、`fixture_audit/sampling_parser.py:67-77`｜影响：旧代码 RSS 取「首个 channel 或回退 root、`item`+`entry`」，新代码 `physical_feed_items` 要求恰好 1 个 channel、只认 `item`，否则 `feed_shape`；`ABSTRACT_RULES_VERSION`（`fixture_audit/abstract_models.py:15`）与 `SAMPLING_RULES_VERSION` 均未升版。｜标准：`docs/agents/invariants.md`「已版本化的…语义配置一经引用即冻结；需要变化时创建新版本」；`docs/contracts/feed-metadata.md:19-21`「共享规则升级仍须追加审计解释及审查字段变化，不能覆盖历史审计」；`docs/verification/feed-parser-v1.md:2` 自称「不改旧审计解释」。｜测试核查：`rg feed_shape tests/` 无命中，多 channel / 根级 item 行为无测试固定。｜硬违规或判断性：判断性（差异只落在旧实现静默容忍的畸形输入）。｜最小建议：为新边界登记 parser 解释差异条目，或让生产路径独享根级集合而审计保留原容器解析。

2. **Contract 新小节脱离骨架**｜`docs/contracts/paper-facts.md:359-380`「## 强身份冲突证据公共服务」位于「相关」依据行之后，自身无依据行；`docs/contracts/screening-tasks.md:477-508` 同形态。｜标准：`docs/agents/documentation.md` Contract 规则「出处写在「相关」小节的依据行」＋固定骨架顺序。｜判断性，低影响。｜最小建议：并入既有编号小节或补「相关/依据」行。

3. **README 链接逐票台账**｜`README.md:633-656` 新段落链接 `docs/verification/issue-114-feed-delivery.md`。｜标准：`docs/agents/documentation.md` README 规则「只描述当前可用的命令与行为；进度与计划链接到路线图」。｜判断性。｜最小建议：改链 `docs/contracts/feed-pipeline.md` 与 `docs/roadmap.md`。

### 基线 smell（均为判断性）

4. **Duplicated Code**｜`feed_ingestion/repository.py:33-42`、`feed_metadata/repository.py:22-33`、`papers/conflicts.py:22-27`、`screening_tasks/language.py:155-157`、`screening_tasks/feed_gate.py:40-49` 五份同形 `canonical/encode`+`sha/digest`，`corrupt()` 仅 `path` 不同；仓库已有 `screening_tasks/rules.py:47 digest`、`config/identity.py:10 canonical_json`。｜影响：编码规则变更要动 5 个文件。｜最小建议：抽出共享 identity 模块，`corrupt(path)` 带参。

5. **Duplicated Code / Primitive Obsession**｜`sources/feeds.py:6` 自称「唯一声明」，但 `screening_tasks/language.py:23` 再定义 `Journal`（`fixture_audit/models.py:24` 已有第三份），且 `screening_tasks/service.py:bind_feed_journal(journal: str)` 退回原始 `str`。｜最小建议：单一 `Journal` 导出 + 该参数改类型。

6. **Duplicated Code**｜`feed_pipeline/service.py:_register`（129-230）与 `_verify_basis`（232-280）重复同一套前置校验（metadata 完整/版本修订一致、boundary 指纹与 applicability、`out_of_scope`、test 来源）。｜最小建议：抽 `_check_basis(...)`。

7. **Long Method / 双开关分叉**｜`screening_tasks/service.py:_register`（约 200 行，`policy_version`、`feed_gate` 两个可选开关）；同文件 5 处函数内 `from paper_radar.screening_tasks.language import …`，而 `service.py:34-38` 已在顶部导入同模块符号。｜最小建议：语言/门禁逻辑收进 `language.py` 单函数，顶层导入。

8. **Mysterious Name**｜`screening_tasks/service.py:181-190 language_status` 名为状态查询却执行 `derive+retain` 写库（`docs/contracts/screening-tasks.md:497` 明确「追加保存」）。｜最小建议：改名 `record_language_status` 并同步契约。

9. **Duplicated Code / Repeated Switches**｜`screening_tasks/language.py:127-146` 与 `190-207` 重复 missing/ambiguous/resolved 推导；`load:253-283` 与 `observations:345-370` 的来源核验循环逐字重复；`POLICIES["v1"]` 比较在 `derive`/`load`/`validate` 出现 3 次。｜最小建议：抽 `_status(values)`、`_require_sources(...)`。

10. **Divergent Change**｜迁移链降级策略不一致：`feed02` 恒 `RuntimeError`，`feed01/03/05/06` 直接 drop，`feed04` 仅非空拒绝；仓库既有迁移无 downgrade。｜最小建议：统一为「非空即拒绝降级」。

11. **Mysterious Name / Data Clump**｜`papers/conflicts.py:34 request()` 返回三元组并隐藏哈希职责；`read_all`（约 100 行）全表扫描后在 Python 过滤。｜最小建议：改名 `request_identity()` 返回小 dataclass，过滤下推 SQL。

12. **一致性缺口**｜`papers/service.py:conflict_assertion` 是唯一未 `require_current_revision`、未 `BEGIN` 的读面（兄弟 `conflicts`/`conflict_bytes` 都有），并函数内 `import json`。｜最小建议：复用 `conflicts()` 的连接模式。

13. **Duplicated Code（测试与源码）**｜`next(v.url for v in FEED_ENDPOINTS if v.journal == "jgr")` 出现在 `tests/test_feed_ingestion.py:22`、`tests/test_feed_metadata.py:98`、`tests/test_feed_pipeline.py:42`、`tests/test_feed_language.py:361` 与 `src/…/feed_ingestion/repository.py:49`、`feed_metadata/service.py:83`（后者为函数内延迟导入，与顶部同模块导入并存）；`tests/test_feed_metadata.py:28` 另硬编码同一 URL，`:24` 重复导入顶部已有的 `JGRMetadata`。｜最小建议：`sources/feeds.py` 提供 `endpoint(journal)`。

### 说明与未覆盖

- 未发现 `docs/agents/testing.md`「负例须断言受控字段路径/类别」的违反：新测试一致使用 `match=` 或 `e.value.reason`（如 `tests/test_feed_review_boundaries.py:80-82`）。
- `scripts/a*_scope.py` 与 30 余个测试文件的哈希/`MIGRATION_REVISION` 改动是固定回执协议的必然扩散，不记为 Shotgun Surgery。
- `GLOSSARY.md` 本 diff 未更新（新增 feed 检查、元数据请求、组合前置无术语条目）；是否属 `documentation.md`「术语进 GLOSSARY.md」范围**未核实**。
- 未运行 pytest/mypy；行为判断来自静态阅读与 ruff 实跑。

### 聚合抽检

Standards 第 1 条已复核：`git diff main...HEAD -- src/paper_radar/fixture_audit/abstract_parser.py` 确认删除「首个 channel / 回退 root、`item|entry`」逻辑并改为 `physical_feed_items`，且两个规则版本常量未变。第 2、3、4 条已抽样确认文件位置与重复 `canonical/sha/corrupt` 实现。

---

## Spec

可用工具与来源：`read`/`bash`（只读）；`gh issue view 114/115/116/117/118/119 --comments`、`git diff main...HEAD`、`git show/log`、源码与测试阅读。115–119 的评论都是实现者完成报告，**未发现任何用户裁决评论**，故以 #114 正文与子票正文为需求基准。实测：`uv run --offline --locked pytest tests/test_feed_conflicts.py tests/test_feed_language.py -q` → `30 passed in 8.71s`。未运行 `./scripts/check-offline`，未执行 live。

### 1. 部分｜语言「策略新版本」无法承载映射变化，历史依据以代码常量为准

- **影响**：现有数据一致，不影响今天的事实；但 Decision 9 的「策略升级」路径无法表达。若将来按新裁决修改 `POLICIES["v1"]` 的映射，所有已冻结预算的 `language_basis`/`validate`/备份验证都会返回 `corrupt_reference`，直接违背「旧预算继续可用、策略升级不更正旧值」。
- **位置**：`src/paper_radar/screening_tasks/language.py:124`（`POLICIES`）、`:145`、`:193`（`mapping != POLICIES["v1"]` 即拒绝）、`:320`、`:342`（持久策略与常量比对）；`src/paper_radar/screening_tasks/service.py:224`（`register_language_policy` 只写入 `encode(POLICIES["v1"])`）。
- **规格引用**：Decision 8「固定 ADR-0035 v1：dqkx=true；aies/jgr/qjrms=false」；Decision 9「策略升级不更正旧值…已有预算可继续按原契约使用」；#118 AC「策略新版本只影响之后的新登记，不篡改旧策略身份」；Testing「语言测试覆盖…策略新版本」。
- **已有测试**：`tests/test_feed_language.py:144 test_policy_identity_and_feed_binding_are_immutable` 只登记「同映射的 v2」，未覆盖差异映射；`tests/test_feed_language.py:59` 用 `policy_version="future-policy"` 仅验证请求重放。
- **复现**：未复现。需改源码常量才触发，属静态推断。
- **最小建议**：`load`/`observations` 按 `basis["policy_version"]` 读取持久映射，而不是比对 `POLICIES["v1"]`；`register_language_policy` 允许新版本写入新的封闭映射（期刊集合不变）；补「v2 不同映射只影响新登记、旧预算依据不变」用例。

### 2. 部分｜路线图未把实现发现的下游缺口写成 B/C 承接责任

- **影响**：B spec 可能漏掉本次实现暴露的新前置（生产 `value` 登记要求真实生产 boundary/RPC，因为当前任务服务只交付 test 执行者）；下游消费者验收依据只剩 Contract 页。
- **位置**：`docs/roadmap.md:59`（只改状态与证据链接）、`docs/roadmap.md` 模块承接索引（88–101 行区块无新增 B/C 条目）。
- **规格引用**：#119 AC「按路线图维护规则记录 Feed 工程完成的证据及 B/C 后续责任，不把模块完成解释为 B 就绪」；`docs/agents/roadmap.md`「implement-spec 收尾时，标记完成，并把实现中发现、需要下游处理的缺口写成下游模块的承接责任（附出处）」。
- **已有测试**：文档项，无测试覆盖（同类先例：`docs/roadmap.md:196` 的叙述式承接）。
- **复现**：`git diff main...HEAD -- docs/roadmap.md` 仅两处 hunk（模块表行、mermaid `class J,Feed completed`）。
- **最小建议**：在承接索引 B（及 C/F 对应项）追加一行：「生产 value 登记需真实生产 boundary/RPC 前置；JGR 真实材料 parser 字段差异复核 —— 出处 #114/#119、`docs/contracts/feed-pipeline.md`、`docs/verification/feed-parser-v1.md`」。

### 3. 覆盖不足｜`requires_merge`/`not_retained` 与冲突读面的分离无新增断言

- **影响**：低。若日后把成功提示误接到 `retain`，冲突公共读面会把成功当冲突，现有新测试不会失败。
- **位置**：`src/paper_radar/papers/feed_repository.py:113-131`（仅四类走 `retain`）、`src/paper_radar/papers/conflicts.py:retain`。
- **规格引用**：Decision 2「`identity_conflict` 仍是拒绝；`requires_merge` 仍是已保留成功提示」；#115 AC「`requires_merge` 仍是成功提示，`not_retained` 不混作冲突」。
- **已有测试**：`tests/test_version_relations.py:258 test_requires_merge_stays_successful_when_candidate_material_is_reused` 仅断言 `status/reason`；`tests/test_feed_conflicts.py` 全篇未断言成功后 `conflicts()` 为空 → 覆盖不足（非测试失真）。
- **复现**：未复现（静态：`retain` 只被四个冲突分支调用）。
- **最小建议**：在 `tests/test_feed_conflicts.py` 或 `tests/test_feed_ingestion.py` 增一条：`requires_merge` 与 `not_retained` 提交后 `PaperFacts.conflicts() == ()` 且 `validate_all()` 通过。

### 暂缓项（有明确触发条件，不计作本次缺失）

- Decision 6 / #116 AC 的 `reinterpret_audit` 追加解释与真实 JGR 材料字段差异审查：`docs/verification/feed-parser-v1.md` 明确「首次生产交付，无旧版本可比较」，真实材料由 EXP-1/B 补齐。
- Decision 11 的升级门禁、7 天复查/`metadata_unobtainable`/完整 eligibility（C）、DEC-1/2/3 均按正文保留。

### 完成状态与未验证范围

已核对并认为满足：四类强冲突持久化/不可变/无 Paper 关联可查/精确重放（`tests/test_feed_conflicts.py` 全绿）、304 只记成功检查（`tests/test_feed_ingestion.py:439`）、doiRA 未知/404 不推断不存在（`tests/test_feed_metadata.py:167`）、歧义拒绝与旧预算冻结（`tests/test_feed_language.py:59`）、组合登记前置（`tests/test_feed_pipeline.py`）。**未验证**：真实 JGR/HTTP live、语言来源约定、`check-offline` 全门禁与 `run_id=4af951c3…`/5274 回执（原始 JSON 在仓库外，未核实）；独立 Feed parser v1 与 Audit 的字段级差异未做机械比对（本轮只读合成材料断言）。

### 聚合抽检

Spec 第 1 条已复核：`src/paper_radar/screening_tasks/language.py` 的 `_consistent_resolution`、`derive`、`load`、`validate` 均以字面量 `POLICIES["v1"]` 校验持久映射，故差异映射的新版本确会走 `corrupt_reference`；第 1 条属设计判断（当前 v1 固定映射不受影响），按「未复现」保留。

---

**一行总结**：Standards 共 13 条（3 条文档化标准违反 + 10 条 smell，均为判断性；最重为审计 parser 解释未升版即改变共享解析边界）；Spec 共 3 条（3 条部分/覆盖不足，无硬缺失；最重为语言策略版本无法承载映射变化）。

---

## 本轮逐条处置（2026-10-30）

原审查正文保留。复核基线 `543942c` 与修复前 `fb52cd7`，需求以 #114–#119 缓存正文和 ADR-0030–0036 为准；缓存未记录评论，不据此推断本轮重新核实了最新远端评论或新增裁决。重复项见 [r1 处置附录](issue-114-feed-review-r1.md#本轮逐条处置2026-10-30)。代码修改集中于本票触及服务，不修改任何旧 migration、冻结 Contract 或历史测试分母。

### Standards 逐条处置

| 原编号 | 处置 | 依据及实现／测试指针 |
| --- | --- | --- |
| 1：共享审计解释就地变更 | 部分采纳 | 真正差异在 `abstract_parser.parse_material` 的历史容器解释；已恢复默认 RSS 首 channel/root 回退、直接 item/entry，生产显式传入已校验 physical item，仍共享字段／主摘要／截断算法。原文对 sampling RSS 的概括不成立：`git show 543942c:src/paper_radar/fixture_audit/sampling_parser.py` 已要求唯一 channel 且只 item；抽 helper 未改变该规则，故不改其版本。公共对照回归 `test_feed_review_boundaries.py::test_historical_audit_feed_container_stays_distinct_from_production` 修前实际读到生产 item 摘要而非历史 entry，修后两条路径各守原语义；另有 `test_production_rejects_nonunique_or_missing_rss_channel` 固定生产严格边界。历史证据页 `docs/verification/feed-parser-v1.md` 原字节保留，容器差异和其历史“不改旧审计解释”声明的修前缺口由本附录纠正，不将旧证据改成当时已通过。 |
| 2：Contract 新小节脱离骨架 | 采纳 | paper-facts「强身份冲突证据公共服务」与 screening-tasks「Feed 原题名语言来源」均移到现有「相关」之前，依据行追加 #114/#115 或 #114/#118；feed-metadata 错误规则也移回「错误与拒绝」。 |
| 3：README 链接逐票台账 | 采纳 | README 组合入口只链现状 `feed-pipeline` Contract 和路线图承接，不再链逐票交付台账。 |
| 4：跨领域 canonical/sha/corrupt 重复 | 部分采纳 | 同 r1 smell 1，语言 resolution 的重复校验在本模块收敛。拒绝抽通用 identity 模块：冲突断言+payload 哈希、HTTP 检查、元数据请求及 StageInput 各有独立身份和已登记序列化语义，sha 接受类型亦不同；两个相似编码调用不足以证明同一变化轴。`corrupt()` 的受控领域路径保持在所属模块。 |
| 5：Journal 重复与 str 参数 | 采纳 | `sources.feeds.Journal` 是唯一 Literal 声明，fixture_audit.models 保留兼容重导出；language 直接复用，bind_feed_journal 参数改为 Journal。原调用入口与运行时受控拒绝保留，四刊语言测试及冷导入兼容组合验证消费者。 |
| 6：组合 register/verify 重复校验 | 拒绝 | 两者校验不同时间语义：新登记必须 metadata/current 修订一致、boundary applicability=current，精确重放必须核对冻结 version/revision/fingerprint 与原前置，但允许当前论文已变化（缺项仅排除 current_version_changed）。把两者机械抽成同一 `_check_basis` 易让合法历史重放依赖当前状态或放松新登记。本次无独立需要变化的相同规则；保留清楚的双路径，现有 `test_feed_pipeline.py` 后到歧义／字段变化与精确重放回归保护差异。 |
| 7：长 _register／双开关和延迟导入 | 部分采纳 | 语言模块符号提升顶层导入，公共 resolution 解码／状态／来源与策略校验回到 language 模块复用。保留 register 中的共享短写事务与可选 FeedGate 分支：语言冻结、现有预算重用、事实复核和前置引用必须原子提交；把整段移入 language 会使语言模块拥有组合门禁／任务登记职责。本轮不以 smell 为由重构全部既有登记流程。 |
| 8：language_status 查询名却写库 | 部分采纳 | 新增 `record_language_status` 明确写语义，旧 language_status 作为兼容委托入口保留，Contract 明示两者都追加观察。直接删名／改名会破坏已公开 API，故拒绝破坏兼容部分。 |
| 9：语言状态／来源／v1 校验重复 | 采纳 | `_status`、`_require_sources`、`_read_resolution` 和持久版本 `_policy_mapping` 共用；load/observations 不再各自复制来源循环。v1 固定政策保持，其他显式版本按持久映射校验。测试见 Spec 1 与既有坏引用公共验证。 |
| 10：统一旧 migration downgrade | 拒绝 | 规范要求通过追加 migration 维护结构，不允许为风格一致重写已发布历史迁移。各表历史 downgrade 能力不同，feed02 明确不可逆，现存 provenance 迁移回归还用到 feed06→feed05 重建路径；本轮无新增降级产品需求，不增加一个不能保护旧脚本执行的空迁移。全部 feed01–06 保持原字节。 |
| 11：request 名称／三元组／扫描 | 部分采纳 | 内部 helper 改为 `request_identity` 并返回具名 RequestIdentity；conflict_id 过滤下推 SQL，公共 conflicts/bytes/assertion API 保持。feed/entry/paper 过滤仍在解码、引用和材料校验后进行：其依据包含 JSON 原断言及可确定版本集合，不能在没有可靠索引／新持久事实设计时盲目下推而改变坏引用受控拒绝边界。本轮不追加查询性能 schema。 |
| 12：conflict_assertion 一致读缺口 | 采纳 | 与 conflicts 同样检查当前 schema、BEGIN 一致读、同连接引用校验与断言读取，并受控转换 SQL/Artifact 错误；json 提升顶层。回归 `test_feed_conflicts.py::test_conflict_assertion_uses_one_consistent_read_during_concurrent_damage` 在真实制品读取边界注入并发 SQLite 损坏：修前返回未核验 `{}`，修后返回同一历史视图且下一读受控拒绝。 |
| 13：端点查询与重复导入 | 采纳 | `sources.feeds.endpoint(Journal)` 提供已裁决首发端点，生产 require_feed、metadata 与四个 Feed 测试复用；删除 metadata 延迟重复导入与硬编码 URL。函数只查声明，不创建身份／订阅。相关 Feed 公共回归和导入兼容组合覆盖。 |

### Spec、说明及暂缓项处置

| 原编号／说明 | 处置 | 依据及实现／测试指针 |
| --- | --- | --- |
| Spec 1：策略新版本无法承载变化 | 采纳 | 与 r1 Spec 3 同项。新版本显式封闭映射由持久版本回放，不更正旧预算、不把策略塞进指纹；v1 固定不改。新公共回归 `test_new_policy_mapping_only_changes_new_inputs_and_replays_persistent_history` 已从 TypeError red 收敛，覆盖同预算重放、retry、输入变化后采用新版本及恢复。差异映射是合成测试，不是本轮真实语言政策批准。 |
| Spec 2：B/C 承接责任 | 采纳 | 与 r1 Spec 2 同项，已写入路线图模块承接索引，明确 B 真实生产 boundary/RPC 与来源/生产 parser 核验、C 四刊扩展及资格生命周期。 |
| Spec 3：requires_merge/not_retained 不混作冲突的公共断言 | 采纳 | 新增 `test_feed_conflicts.py::test_successful_merge_hint_and_not_retained_are_absent_from_conflicts`，真实 submit 后分别断言成功 requires_merge、not_retained，整体及 Paper 过滤 conflicts 均为空且 validate_all 通过。这是覆盖补强，核实修前业务分支已正确，无需人为修改正确实现制造 red。 |
| Standards 说明：GLOSSARY 是否遗漏，原未核实 | 采纳 | 核实这些为本项目持久事实概念；补 Feed 检查、强身份冲突观察、元数据请求、组合登记依据的简短词义，区分执行检查／发现、拒绝／待合并成功和准备／执行资格，无实现细节或新能力承诺。 |
| Standards 说明：负例路径、scope 扩散非 smell | 采纳（保留） | 本轮负例仍断言受控 reason/path；固定 scope 只按实际消费 DAG 重绑已登记路径，不新增历史测试模块或分母。逐项旧／新哈希台账留仓库外，collect 仅核对人工既定分母。 |
| Standards 来源缺口：未核实覆盖裁决、未跑 pytest/mypy | 部分采纳（说明限制） | 本轮已读本机 #114–#119 正文缓存与 ADR；缓存 comments 为空，未再次联网取得最新评论，不声称新核实远端裁决。新增回归及完整 Ruff/mypy 结果见本次验证记录；原报告各轴当时“未运行”的说明不重写。 |
| 暂缓 1：reinterpret_audit／真实材料字段审查 | 部分采纳（有界暂缓） | 本轮恢复历史 audit-abstract-v1，而非将新容器语义登记成同名算法；生产仅供已验证 physical item，共享字段/主摘要规则。合成同材料差异已有公共回归，本附录记录审计／生产容器差异。真实 JGR 本机材料、字段级审查及若未来独立 parser 变化所需 reinterpret_audit 追加解释仍由 EXP-1/B 在入口前承接；不得覆盖旧审计。本轮未运行真实材料机械比对。 |
| 暂缓 2：parser 升级门禁、7天复查、完整 eligibility、DEC-1/2/3 | 采纳（保留暂缓） | 当前生产 parser 仍 v1；后续升级须固定样本并声明关键字段损失。7天复查/metadata_unobtainable/完整资格仍 C；DEC-1/2/3 未获新裁决，本轮不放行、不改需求。路线图承接明确。 |
| 未验证：真实 JGR/HTTP 与语言来源约定 | 采纳（保留未验证） | 本轮 HTTP 仅冻结合成 transport；未访问真实来源，未验证 guid/entry 稳定性、Wiley 参数、真实截断／摘要质量、逐篇语言、B隔离入口、Pi/RPC、Docling/校准/NAS。v1 来源级约定的正确性不能由本轮合成策略回归证明。 |
| 未核实：历史 run_id=4af951c3…／5274 固定scope回执 | 采纳（已补核实历史） | 主仓 `verification-runs/4af951c3460c4a98a79e116a088e1fdf*.json` 实有 14 份；只读核实 terminal 绑定干净 `fb52cd7`、exit_code=0、materials_consistent=true，11组文件及 pytest 回执原字节哈希与 terminal 匹配；receipt completed=true、exit_code=0，合计 collected=passed=5274，其余计数为0。旧证据确可核实，原报告当时“未核实”保留历史原文；当前变更仍须最终提交后的独立新 run_id，不能用旧5274或本轮子集推定。 |
| 完成状态的正向核对与范围 | 采纳（限定证据） | 保留原文已满足项的历史描述；本轮相关公共 Feed/语言/冲突/metadata/组合及审计回归重新执行，不把“接口已交付”解释为真实来源/B/自动Read就绪。`docs/verification/issue-114-feed-delivery.md` 等历史交付证据保持原字节。 |

### 解析差异的追加纠正记录

修前 `abstract_parser` 在已登记 `audit-abstract-v1` 下改用严格 `physical_feed_items`，确实缩窄了历史容器解释；历史 `feed-parser-v1.md` 的“不改旧审计解释”声明因此在该基线上不完全成立。本轮恢复默认历史实现，生产路径继续显式使用严格根级条目，不提升或偷换旧规则身份。`sampling_parser` 的唯一 channel/item 要求本来就存在，未随本轮撤销。混合 item/entry 对照会呈现题名／摘要节点不同；DOI、entry ID、类别及顺序仍依 sampling-v1 严格集合。这是明确容器差异，不是独立发明主摘要算法，也不声称真实材料中没有该差异。未来新解释仍须追加版本／reinterpret审查，EXP-1/B 的真实材料责任保持。

### 本轮开发验证

- 相关 Feed、共享审计、恢复及追加解释回归：14 个模块，`163 passed in 144.12s`；命令与完整输出保存在仓库外 `/tmp/paperradar-114/review-pytest.log`。
- `uv run --offline --locked ruff check src tests scripts` 通过；`ruff format --check src tests scripts` 显示 659 个文件格式一致；`mypy src tests scripts` 显示 658 个文件无问题。
- scope 按已消费 DAG 对 A6–A10 共 21 项既有哈希重绑；`audit-verification-scope --collect --json` 退出 0，图问题和字节漂移为空，collection reason=ok；AST 比对确认历史测试注册与分母不变。旧／新哈希和原因见仓库外 `/tmp/paperradar-114/review-scope-rebind-ledger.json`。collection 的 execution=not_run 只说明未执行测试，不代表没有 collection；本轮不把 collect 当作功能通过。
- 完整入口兼容组合首次在 scope 重绑前运行，49 failed/127 passed，失败信号为 scope_drift 及其前置传播；重绑后重新运行 `./scripts/check-compatibility all`，`176 passed in 241.69s`，真实退出码 0（入口总耗时 242.26s）；完整输出见仓库外 `/tmp/paperradar-114/review-compatibility-final.log`。以上子集、静态检查与兼容组合不替代最终提交后的完整离线门禁；正式回执保持仓库外说明与原字节身份。
