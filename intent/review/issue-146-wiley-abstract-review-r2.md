# Issue #146 两轴代码审阅（r2，提交后）

按 `code-review` skill 执行：固定基点 `94ee2d53180efbdf5f49bc159c517c85e0158e7b`，比较
`git diff 94ee2d53180efbdf5f49bc159c517c85e0158e7b...HEAD`（三点，对 merge-base）。

- Commit：`a7df05b fix: add versioned Wiley RSS main abstract selection (#146)`
- 规模：45 files changed, +2085 / −85（工作树干净）
- Standards 与 Spec 由两个 fresh-context 只读子代理并行审阅（均具 `read` + `bash`）：
  `diff-standards-reviewer`、`diff-spec-reviewer`。两轴独立记录，未跨轴排序。
- 规格来源：GitHub issue #146 正文（`gh api repos/MeteoBoy4/PaperRadar/issues/146`；零评论，
  label `ready-for-agent`，无覆盖正文的后续用户裁决）。`docs/verification/issue-146-wiley-abstract-v2.md`
  是实施者完成报告，不是需求。
- 规范来源：`AGENTS.md`、`docs/agents/{python-conventions,testing,documentation,cli-output,invariants,llm-evidence,calibration,scope,refactor,verification-scope}.md`、
  `GLOSSARY.md`、`docs/adr/`、`contracts/`、`pyproject.toml`；仓库无 `CODING_STANDARDS.md`／
  `CONTRIBUTING.md`。另加 Fowler 坏味道基线。

本记录是 r1（[过程审阅](issue-146-wiley-abstract-review.md)）在提交后的正式两轴复核，
不是验收结论，也不是可复用的 scope 身份确认。本轮未修改代码、未创建 commit。

## Standards

### 1) 硬违规：受控 vocabulary 用裸字符串 + 就地校验表达

规范：`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因。」
仓库既有做法是集中常量（`fixture_audit/abstract_models.py:15 ABSTRACT_RULES_VERSION`、
`acquisition_models.PARSER_VERSION`）。本 diff 未沿用，而是把 `"audit-abstract-v1"/"audit-abstract-v2"`
字面量与 `in {"…v1","…v2"}` 校验复制到 10 处：`fixture_audit/acquisition_service.py:96,102`、
`abstract_parser.py:247,252`、`abstract_service.py:195`、`service.py:576,621`、`history_rules.py:25-28`、
`interpretation_service.py:319`、`feed_metadata/service.py:78,100`、`resume_rules.py:53-57`、
`feed_ingestion/parser.py:120`、`feed_ingestion/service.py:144`；签名一律 `abstract_rules_version: str`，
而同一次改动里 `feed_metadata/models.py:41,65` 却用 `Literal[...]`，同一概念两种类型策略。
影响：新增 v3 需改 ≥10 文件（**Shotgun Surgery** + **Duplicated Code**）。
最小修复：在 `abstract_models.py` 定义
`AbstractRulesVersion = Literal["audit-abstract-v1","audit-abstract-v2"]` 与唯一映射
`abstract_parser_version(rules) -> int`，签名、比较、校验全部引用之。

### 2) 判断性：规则版本 ↔ 整数 parser 版本的重复 if 级联（**Repeated Switches** / **Primitive Obsession**）

`feed_metadata/service.py:138-142`、`342-344`、`548` 与 `resume_rules.py:53-57` 四处各自写
`2 if …== "audit-abstract-v2" else 1`；`feed_ingestion/parser.py:122` 反而反向由整数拼字符串
`f"audit-abstract-v{parser_version}"`（隐含命名约定耦合）。最小修复：同 §1 的单一映射函数，
`parser.py` 改为查表而非拼接。

### 3) 判断性：`history_rules.py:22-28` 自我比较（**冗余/迷惑**）

```python
versions = {**HISTORICAL_V1, "abstract_rules_version": plan.abstract_rules_version}
if plan.abstract_rules_version not in {...v1,v2} or any(getattr(plan,name)!=version ...)
```

该键的比较恒为「与自己相等」，真正生效的是外层成员检查；同时它把
`HISTORICAL_V1["abstract_rules_version"]` 覆盖成死数据，读者无法判断哪条规则在约束。
最小修复：构造 `versions` 时排除该键（或在 `HISTORICAL_V1` 中显式注释它由成员检查替代）。

### 4) 判断性：`feed_ingestion/repository.py:56-79` 双层 `**` 条件展开

`**({...} if row.get("parser_version",1)!=1 else {})` 与相邻 `**{key: row[key] …}` 叠加，
v1 兼容分支没有一句说明；且 `row.get(...)` 静默容错与其余 `row[key]` 严格访问不一致。
最小修复：先构造 dict，再 `if version != 1: payload["parser_version"] = version`。

### 5) 判断性：`abstract_parser.py` 重复条件与重复计算

`300-303` 与 `313` 重复同一复合条件
`rules_version == "audit-abstract-v2" and request.journal in {"jgr","qjrms"}`；
`502` 与 `506` 对同一候选重复 `_clean(value)`。最小修复：抽 `wiley_v2` 布尔、复用已算的 clean 值。
`_wiley_main` 四层嵌套 + `chosen/conflict` 旗标可读性偏弱，但语义与契约一致，仅记录。

### 未发现问题（已核对）

`feed07_parser_versions.py`（降级守卫风格与 `feed04` 一致）、十个 scope 的
`MIGRATION_REVISION`/A3 `backup_database_revision`、两个中央哈希、
`feed-metadata`/`feed-ingestion`/`backup-restore`/`artifact-store` 原地修正与
`#摘要矩阵与显式运行105` 锚点、D1 新台账点名数量（实测 collect：33 = 27+2+3+1，命令
`uv run --offline --locked pytest <4 模块> --collect-only -q`）均符合
`docs/agents/{testing,documentation,verification-scope}.md`。台账中「修前先观察到失败」为过程声明，
**未核实**。未跑门禁与 live。

## Spec

规格来源已核对（issue #146 正文、零评论、label `ready-for-agent`，无后续用户裁决覆盖正文）。
逐条对 5 项验收要求：

| 要求 | 状态 |
|---|---|
| 1 合成向量回归 + 共存/缺项/冲突规则、不拼接、不从卷期说明生成 | 已实现（`abstract_parser.py:446` `_wiley_main`；`tests/test_wiley_abstract_v2.py` 27 项） |
| 2 版本身份升级、v1 逐字保留 + replay/backup-restore、审计与生产共更新 | 已实现（`feed07_parser_versions`、`feed07` 空列迁移、`feed_ingestion`/`feed_metadata` 双消费；`tests/test_wiley_audit_versions.py`、`test_wiley_production_versions.py`） |
| 3 逐篇比较并保留旧事实；不绕过 `reinterpret_audit` 的 complete 前置 | 实现，见下 (c)-1 |
| 4 相关 pytest 子集 + 固定范围登记；不改旧负例/分母；不跑完整门禁 | 已实现（`tests/migration_expectations.py`、`scripts/verification_scope_materials.py` 仅精确重绑；旧冻结测试零改动） |
| 5 live 补跑/fixture 登记/稳定性 | 有明确触发条件的延后项，**不算缺失** |

独立复核（只读）：用保留的真实字节（JGR payload SHA-256 `9097d9f…`，与 issue 一致；来源为
`.scratch/exp-1/…/backups/…`）以 `rules_version="audit-abstract-v2"` 复算，得 JGR 1–5 =
1410/1142/1673/1647/1579 cp、locator 均为 `content:encoded`；QJRMS =
1510/2059/1795/**缺项**/2196，与 `issue-146-field-diff.json` 完全一致。核心修复目标在真实材料上成立。

### (a) 缺失 / 部分实现

1. **partial** — 逐篇比较只有结果 JSON、无入库的复算手段（无生成脚本、报告未记命令与输入身份）。
   影响：第三方无法自证十篇诊断，`issue-146-wiley-abstract-v2.md` 的表格只能靠本地证据根。
   规格：「逐篇比较字段增减、文本哈希、长度、截断信号与仲裁结果，保留旧事实」。
   位置：`docs/verification/issue-146-field-diff.json`、`issue-146-wiley-abstract-v2.md`。
   测试：未覆盖。复现：本次已手工复现（`uv run --offline --locked python /tmp/rv/check146*.py`），
   故数值可信、但仓库内不可复现。最小修复：记录等效只读命令与材料身份，或加只读诊断脚本。

### (b) 超出规格

2. **scope creep（低）** — `issue-146-field-diff.json` 公开真实成员摘要的**完整 64 位** SHA-256
   与精确 code point 数（`exp-1-http-audit.md` 只用 12 位前缀）。规格：「真实材料不上传…
   未获许可的真实原材料不入库」。测试：未覆盖。最小修复：按既有惯例截前缀，保持既披露面。

### (c) 实现可疑

3. **implemented-but-wrong（低）** — 同一 `request_id` 传入更高版本时静默返回旧版本结果：
   `feed_ingestion/service.py:158-166`（`previous` 存在即复用，忽略 `parser_version`）、
   `feed_metadata/service.py:112-115`（忽略 `abstract_rules_version`）。影响：调用方以为 v2 生效，
   实际得到 v1 身份；规格要求「明确规则身份升级…不同语义不能同版本换实现」的身份可核性被削弱
   （契约仅文字声明「新版本须用新 request_id」）。测试：`tests/test_wiley_production_versions.py`
   只用新 request_id，未覆盖该拒绝路径。最小修复：入口比较已存版本与请求版本，不等即
   `invalid_observation`。
4. **判断性（非违规）** — `_wiley_main` 以期刊名 `jgr/qjrms` 而非字段形状启用 v2；当前四刊中仅
   这两刊是 Wiley，无功能缺口，但规则身份与「字段共存」语义耦合。

### 未核实

- 十组 S3 敏感确认（`issue-146-scope-rebindings.json` 自述确认输入须在树外）——本轮无法核对；
  不能当作验收通过。
- 未运行完整离线门禁（符合要求），跨消费者回归结论不覆盖。仅跑
  `uv run --offline --locked pytest tests/test_wiley_abstract_v2.py -q` → 27 passed。

## 汇总

- Standards：5 项发现（硬违规 1、判断性 4）；最严重为受控 vocabulary 用裸字符串 + 就地校验，
  导致新增规则版本需散改 ≥10 文件。
- Spec：4 项发现（partial 1、scope creep 1、implemented-but-wrong 1、判断性 1）；
  最严重为逐篇比较缺少入库复算手段（partial），核心修复目标本身在真实材料上已被独立复现成立。
- 两轴未合并排序；本轮未修改代码、未创建 commit、未运行完整离线门禁与 live。

## 实施者逐项核实与处置

本轮起点 `a7df05be0d22a56134b51e0c2bee0f8c77a32652`；关联 [#146](https://github.com/MeteoBoy4/PaperRadar/issues/146)。以上审查原文保留；其“r1”引用实际指向最初过程审阅，用户本轮给出的另一个 r1 报告是 [issue-146-wiley-abstract-review-r1.md](issue-146-wiley-abstract-review-r1.md)。以下沿原条目编号处置。

### Standards

| 编号 | 判断 | 处置与理由 |
| --- | --- | --- |
| 1 受控 vocabulary 分散 | 采纳改进，不将所有 str 一概视为违规 | 在 abstract_versions.py 集中 AbstractRulesVersion、AbstractParserVersion、默认/显式 Wiley 规则、唯一双向映射和入口校验。已知版本的服务签名与元数据/矩阵模型共用 Literal 类型。AuditPlan 的历史原字符串仍保留：若把其也限制为当前 Literal，合法但未安装的历史版本会被错误分类成 corrupt_reference，破坏既有 unsupported_history 契约。 |
| 2 重复规则/整数 if | 采纳 | 元数据提交/回放共用 abstract_parser_version；Feed 反向查映射，不再靠 audit-abstract-v{整数} 拼接。resume 独立核对已安装规则和其余当前执行版本，并保留旧 v1 当前声明变化时拒绝继续的行为。 |
| 3 历史规则自我比较 | 采纳 | HISTORICAL_V1 完整字面快照保留；摘要身份单独查受支持规则，其余字段与冻结组合比较，不再覆盖摘要键后与自身比较。 |
| 4 check_identity 双层展开 | 采纳 | 先构造请求身份字典，再只为非 v1 加入 parser_version；移除 get 默认值，明确注释 v1 不能加入后来新增列，否则旧 check_id 会变化。非空上一 revision 和原回放回归继续保护历史算法。 |
| 5 重复条件与清洗 | 采纳最小改动 | parse_material 只计算一次 wiley_v2；_wiley_main 保存已算 clean 值做同级冲突判定。未进一步重写 chosen/conflict 流程或冻结 v1 的标签切分。 |

### Spec

| 编号 | 判断 | 处置与理由 |
| --- | --- | --- |
| (a)-1 缺少入库复算手段 | 采纳 | 新增 scripts/compare_wiley_abstracts.py 和合成端到端测试。工具读取一致数据库副本，仅在临时目录迁移副本，带 socket/DNS 拒绝守卫；--check 对原安全 JSON 逐字段比较，差异返回 1。输入计划/汇总/两刊 Feed 完整 SHA 及精确命令见后续台账。实际复算一致，不覆盖原 JSON。 |
| (b)-2 完整 SHA/长度属于原材料越界，应截短 | 不采纳 | Issue #146 第3项明确要求文本哈希与长度，正文自身亦使用完整 SHA。SHA-256、精确长度和来源定位是核对身份的安全投影，不是摘要/Feed 原字节；旧报告没有原题名、摘要正文或响应体。截成12位会丢失精确核验依据，也会改写已发布证据。未找到规定必须截短的仓库规则，故保留既有披露面和原字节。 |
| (c)-3 同 request_id 显式异版本 | 采纳防误用改进；原实现遵守当时的原请求优先契约，非同版本换实现 | 已先观察两条公开服务回归失败，再修复。显式指定版本与保存版本不一致时，在联网和追加事实前以 invalid_observation 拒绝；省略版本（None）时新请求仍默认 v1、旧请求仍用原版本，避免 v2 的普通精确重试被误拒。增加双向 v1/v2 冲突、无额外 HTTP 和旧回放不变覆盖，并同步 Contract。 |
| (c)-4 按期刊启用 v2 | 不扩展 | Issue 与规格限定 Wiley 两刊；当前 jgr/qjrms 正是这两个来源。按字段形状泛化会让 AIES/dqkx 的未审来源也改变解释，超出本票。保持期刊边界和其他来源的 v1 语义。 |

“未核实 S3”属审阅证明边界，无需拒绝或伪造旧确认。本轮以当前树重新执行范围审计、敏感变化核对及相关测试；不把旧报告或临时确认当作当前完整验收。原审阅提到未验证的完整门禁/live 继续未验证。

本轮覆盖、精确复算命令与验证见[后续台账](../../docs/verification/issue-146-review-followup.md)；没有修改旧冻结测试、负例、分母、EXP-1 证据或原 field-diff JSON。
