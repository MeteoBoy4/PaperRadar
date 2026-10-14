# Issue #23 代码审查：只读比较快照并识别真正影响阶段与校准的配置变化

- 审查范围：`HEAD~3..HEAD`（已验证恰好三笔提交，固定点 `5b515ea8177ded46d52f559814cc3895fef826dd`）：

  ```
  fbbcf07 Preserve snapshot ID placeholders in diff help (#23)
  e4ecacf Redact and translate config diff argument errors (#23)
  576c8ab Implement read-only configuration projections and diff (#23)
  ```

- 规格来源：GitHub Issue #23 正文（What to build、14 条 Acceptance criteria、Blocked by）与全部 3 条 comments（①「A2-08 实施前补充」21 条编号项；②用户决策：同意第一部分、第 10/12/13/14/15 点建议，第 11 点不物化；③后续 UX 衔接：快照发现与短 ID 留后续票，要求查询/存在性验证与 diff 语义比较分层）。
- Standards 依据：AGENTS.md、CONTEXT.md、docs/agents/domain.md、docs/contracts/（config-projections.md、runtime-config.md、adapter-config.md、extraction-config.md）与 Fowler smell 基线。
- 审查方式：只读双轴独立审查（Standards / Spec 两个并行子代理）；全部关键发现已由主代理逐一抽查复核（`projections.py:58-61,120-122`、`diff.py:27,68-72,84,91`、`cli.py:61-73,172,199,219,224`、`service.py:320-321,344-346`、`runtime-config.md:8-10`、`config-projections.md:97-107`，行号与内容均与报告一致）。未修改代码、未创建 commit、未触碰 Issue。
- 工具基线（实际运行）：7 个新增测试模块 107 passed（`test_config_projections.py`、`test_config_diff_cli.py`、`test_config_diff_service.py`、`test_config_projection_adapters.py`、`test_config_projection_algorithms.py`、`test_config_projection_architecture.py`、`test_config_projection_formats.py`）；`./scripts/check-offline` 全绿（format/lint/types/tests/contracts 及 A1、A2-01 结论均 passed，run_id `1bd32bfb31a047caab26753814d8eb43`）。

## 实施核实与处理（关联 #23）

以下是针对报告建议的后续处理，原始审查结果与其验证基线保留。
按用户要求，未读取或执行“人工针对性检查入口”章节。

| 条目 | 核实结论 | 处理与依据 |
| --- | --- | --- |
| B1 | 部分采纳 | projections/diff 重复拆已验证快照材料的事实成立，已统一经 `RuntimeConfigSnapshot.materials` 读取完整三元键与不可变材料视图，并通过 `adapter_selections` 读取槽绑定；共享 adapter 多版本不会相互覆盖。拒绝将 service 的三元键校验字典一并替换：该字典来自 SQLite 保存的原字节/哈希记录，而不是已验证快照；加载器在返回 RuntimeConfigSnapshot 前必须独立核对内容、引用与重建身份。原报告把三者视为同类读取，忽略了校验与消费的职责差别。 |
| B2 | 采纳 | 增加公共封闭 `ConfigCategory` StrEnum，`ConfigIdentityChange.category` 与内部索引使用该类型，CLI 仅渲染 `.value`。原有类别文本与字符串比较兼容，新增消费者须显式扩展枚举。 |
| B3 | 采纳 | 抽取仅查询 schema/manifest 的契约分量函数，模型投影与 suggestion 共用；suggestion 直接取 decision-reasons，不再构造并丢弃 boundary prompt、模型与 adapter 分量。投影与基线的载荷/格式不变。 |
| A1 | 采纳导航改进，不认定为规格内容缺失 | runtime-config.md 已有链接，config-projections.md 的完整演进说明也已交付。现于依赖矩阵后补充独立格式版本、传导范围、旧快照 null 重建及历史身份兼容摘要，并保留详细说明链接。 |
| C1 | 采纳 | 前后均已配置时才追加“（语义变化）”；未配置与已配置间仅显示受控转移。真实 CLI 回归覆盖正向、反向转移及已有内容变更，并保持基线事实和退出码判据。 |

测试继续使用 #15/#23 已确认的公共配置服务与真实临时 SQLite/CLI 边界。
新增材料访问测试验证不可变映射、不可变记录、共享 adapter 多版本及历史回放；
类别测试验证公共结果返回受控类型。重构继续使用已有固定投影/基线身份与隔离矩阵
测试，不为私有拆分增加测试。无 migration、声明配置改写、算法升级或门禁集成。

本次实际验证：

- `uv run --offline --locked pytest tests/test_config_projection*.py tests/test_config_diff*.py -q --tb=short`：109 passed。
- Ruff 格式与静态检查、mypy：全部通过；A2 固定源码/测试绑定一致，A1 固定测试与契约保留。
- `./scripts/check-offline`：lockfile、format、lint、types、全部 tests、contracts 均通过，
  独立 A1 与 A2-01 结论均 passed；run_id `22844627130c4d04b02737a7d3b35c60`。
  uv 使用临时 `UV_CACHE_DIR` 以适配当前目录写权限，依赖仍由项目环境和 lockfile 管理。

上述离线验证对应审查修订的代码与测试；原报告的 107 passed 和 run_id 仍只描述其原始审查基线。
本次没有运行 live 验收，也没有实现后续快照发现、短 ID 或校准门禁工作流。

## Standards

### (a) 成文标准违反（硬违规）

**无。** 逐项核对通过：

- **核心不变量**：diff 全程只读（`DatabaseMode.READ_ONLY`），不登记、不物化基线，历史快照不被改写；存在性/损坏验证先于相同 ID 短路，重复比较幂等（`test_config_diff_cli.py:41` 断言）；未引入单一 lifecycle/status 字段或合并逻辑。
- **Calibration 安全**：CLI 只输出"是否涉及校准"事实并声明"不判定变更等级或启用自动精读"（`cli.py:172,224`），退出码不受校准相关性影响，未替用户分级（ADR-0020）。
- **数据与版本控制**：无手写 Schema、无 migration；格式版本由封闭表 `PROJECTION_FORMAT_VERSIONS`/`BASELINE_FORMAT_VERSION` 控制（`projections.py:16-19`）。
- **面向用户的行为**：输出全中文、错误可操作；payload 经 `field(repr=False)` 隔离（`projections.py:33,43`），测试断言 Profile/Prompt 正文不外泄；`--help` 保持延迟导入、不读配置不开库。
- **文档维护**：CONTEXT.md 两处词条与 config-projections.md、runtime-config.md 依赖矩阵互相一致（基线含 extraction、排除 read/期刊/声明标签）；README、draft.md、`scripts/a2_scope.py` 哈希绑定同步更新，无矛盾。
- **模块解耦**：projections/diff 为纯领域层，`test_config_projection_architecture.py` 以测试固化禁止依赖 I/O 层。

### (b) 基线 smell（判断性发现）

**B1. Duplicated Code / Feature Envy — 手工拆快照 payload 的形状重复三处**
- 位置：`src/paper_radar/config/projections.py:58-61`、`src/paper_radar/config/diff.py:68-72`、`src/paper_radar/config/service.py:344-346`。
- 依据：三处都 `json.loads(snapshot.payload_json)` 后按 entry 的 kind/name(/version) 手工建材料字典，均从外部探入 `RuntimeConfigSnapshot` 载荷内部结构（Fowler Duplicated Code + Feature Envy）。
- 实际影响：快照载荷格式演进时需同步改动多个解析点，漏改即静默分歧。
- 最小修复：在 compile.py 给 `RuntimeConfigSnapshot` 增加一个只读材料访问方法（返回 kind/name/version→entry 映射），三处共用。

**B2. Primitive Obsession — `ConfigIdentityChange.category: str`**
- 位置：`src/paper_radar/config/diff.py:27`；键由 f-string 拼出（`diff.py:84` `f"{kind}.{name}"`、`diff.py:91` `f"adapters.{slot}"`），CLI 原样打印（`cli.py:199`），测试断言字面量 `"prompt.reading"`。
- 依据：AGENTS.md「编码流程」——优先使用明确的领域类型和受控 enum，避免 magic string；Fowler Primitive Obsession。值虽由封闭枚举派生（契约文档称"受控 category"），故降为判断性。
- 实际影响：category 集合无类型级穷举依据，未来新增材料种类时消费方只能靠字符串匹配。
- 最小修复：以 `(MaterialKind, name)` 或 `(slot)` 小组件承载，渲染层再格式化为字符串。

**B3. 误导性复用 — suggestion 契约经 boundary 参数构造**
- 位置：`src/paper_radar/config/projections.py:120-122`，`model_components("screening", "boundary", "decision-reasons")["contract"]`。
- 依据：为取一个 contract 分量，构造了含 boundary prompt 文本与 screening adapter 的完整五元 dict 后丢弃四项；读者会误以为 suggestion 投影依赖 boundary prompt/adapter（依赖矩阵中并无此依赖）。属轻微 Mysterious 形态。
- 实际影响：依赖关系被掩盖，后续审阅依赖矩阵时易产生错误推断；每次投影多算一份被丢弃的 prompt/adapter 查找。
- 最小修复：内联直接查 `(CONTRACT_SCHEMA, "decision-reasons")` 与对应 manifest 两个键。

**抑制说明**：`_ConfigDiffCommand.parse_args` 的宽 `except Exception`（`cli.py:61`）是契约文档明确要求的原始异常脱敏边界（错误不回显底层异常），按"仓库标准优先于基线"原则抑制该 smell。

## Spec

### (a) 缺失 / 部分实现

**A1. 投影/基线格式版本演进与旧快照兼容说明的落点与评论第 16 条不一致（minor 文档导航）**
- 位置：`docs/contracts/runtime-config.md:8-10`（仅加指向链接）；实际内容在 `docs/contracts/config-projections.md:97-107`。
- 依据：补充评论第 16 条将「新增投影/基线格式版本及其演进与旧快照兼容说明」列在 `runtime-config.md` 的改写项下。
- 实际影响：内容本身完整（格式版本封闭表、演进传导、旧快照按 null 重建且不改写历史均有），只是落在 config-projections.md，runtime-config.md 读者需跳链；属文档导航层面。
- 最小修复：可不改；或在 runtime-config.md 依赖矩阵段补一句"格式版本演进与旧快照兼容规则以 config-projections.md 为权威"以外的指针性语句。

### (b) 超范围实现

**无。** 已核查：未实现短 ID/快照列表/JSON 输出（评论③明确留后续票，`config-projections.md:125` 亦声明）；未新增单快照 CLI（`config-projections.md:15` 声明不新增，实际只有 `config diff`）；`_ConfigDiffCommand`（`cli.py:53-73`）服务于 AC 第 13 条的中文脱敏错误，非蔓延；`NOT_IMPLEMENTED` 仍含 `stage_config_projections/calibration_baseline/config_diff`（`scripts/a2_scope.py:197-199`），但该列表仅作为 A2-01 历史范围声明写入验收证据 JSON，不断言代码缺失，注释已说明"完整 A2 结论归 #25"，属有意保留。

### (c) 实现错误

**未发现。** 重点复核项均与规格一致：

- **退出码**：含校准差异仍返回 0（`test_config_diff_cli.py:75-76`）；ID 错误/不存在/未知格式/损坏/缺库/未迁移均返回 2 且不建库（`test_config_diff_cli.py:108-179`、`test_config_diff_service.py:73-83`）。符合决策 12 与评论第 9 条（存在性验证先于相同 ID 短路——实现根本不短路，语义等价）。
- **隔离矩阵**：票面五行 + 评论第 2 条四行全部有用例（`test_config_projections.py:130-287`、`test_config_projection_adapters.py:19-107`、`test_config_projection_algorithms.py:22-53`）。
- **adapter 分量**：直接嵌入 `AdapterSemantics.semantics_id`（`projections.py:84`），`pi_version/adapter_version` 审计版本不入投影（`test_config_projection_adapters.py:66-80`）。符合评论第 1、3 条。
- **声明版本标签排除**：Profile 仅取 `PROFILE_FIELDS`（`projections.py:63-67`）、models 按槽提取不含整文件版本/字节哈希、YAML 用编译值不用原始哈希；反例测试齐备（`test_config_projections.py:190-237`、`test_config_projection_formats.py:96-104`）。
- **基线**：五投影身份的规范组合、不物化、单一判据 `calibration_changed`（`projections.py:178-190`、`diff.py:61-62`），符合决策 10、11 与评论第 8 条；重导出确定性有断言（`test_config_diff_service.py:41-48`）。
- **错误脱敏**：非法 ID 不回显（`service.py:320-321`；`test_config_diff_service.py:54-70`）；存储层错误不回显 ID（`repository.py:146`）。
- **格式版本与 ID 形态**：每投影独立格式版本 + 基线独立版本、封闭表（`projections.py:16-19`），符合决策 13；StageName 六值小写、64 位小写十六进制不做大小写归一（`service.py:53`），符合决策 15。
- **分层**（评论③）：ID 校验在 service 层，projections/diff 为纯计算（`test_config_projection_architecture.py` 强制无 I/O 依赖）。

**C1（装饰性，可忽略）**：`cli.py:219` 对所有分量变化均追加"（语义变化）"，包括"未配置 → 已配置"转移；评论第 14 条将后者表述为受控转移。输出仍正确显示转移且校准标注正确，仅措辞冗余。最小修复：仅当前后均"已配置"时追加该后缀。

### 残留风险

- 本评审为静态核查（git diff + 票据 + 代码/测试/文档通读）加目标测试与 `./scripts/check-offline` 实际运行；live 行为（真实用户配置库上的长链路使用）未覆盖。
- 快照列表/短 ID 发现能力明确留后续票（评论③），当前只能手工复制完整 64 位 ID，UX 入口暂缺属既定范围。
- diff 事实如何接入校准变更工作流（自动运行的前置判断）属后续票，本票无法端到端验证。

## 总结

Standards 轴：0 项硬违规、3 项判断性 smell（最重：B1——三处手工拆快照 payload，载荷格式演进时漏改即静默分歧）。Spec 轴：1 项 minor 文档落点偏差、0 项范围蔓延、0 项实现错误（最重：A1——格式版本演进说明落在 config-projections.md 而非评论第 16 条指定的 runtime-config.md，仅导航层面）。两轴无指向同一问题的发现，无需交叉说明。

## 人工针对性检查入口

以下入口可在不改动代码的前提下，对本 diff 的变更范围和 Issue #23 各条 AC 做人工抽查。通用入口：

- **变更范围**：`git log HEAD~3..HEAD --oneline`（应恰好三笔）、`git diff HEAD~3...HEAD --stat`、逐文件 `git diff HEAD~3...HEAD -- <path>`；A1 零改动用 `git diff HEAD~3...HEAD -- tests/test_a1_acceptance.py scripts/a1_scope.py scripts/a2_acceptance.py contracts/`（应为空）确认。
- **整体回归**：`uv run pytest tests/test_config_projections.py tests/test_config_diff_cli.py tests/test_config_diff_service.py tests/test_config_projection_adapters.py tests/test_config_projection_algorithms.py tests/test_config_projection_architecture.py tests/test_config_projection_formats.py -q`（107 例）；`./scripts/check-offline` 跑完整离线验证。

准备（在临时目录操作，避免污染仓库）：

```bash
cp -r examples/config /tmp/pr-cfg && cd /tmp/pr-cfg
uv run --project <repo> paper-radar db upgrade --database /tmp/pr-diff.db
uv run --project <repo> paper-radar config compile --settings settings-value.yaml --database /tmp/pr-diff.db  # 记下快照 ID A
# 修改某处配置后再次 compile，记下快照 ID B
```

按 AC 的针对性入口：

- **AC「中文 help 无副作用」**：空 HOME + 临时 cwd 下 `uv run paper-radar config diff --help` → 退出码 0、全中文、含 `<before-id> <after-id>` 占位符（fbbcf07 的修复点）、不产生文件、不开库。
- **AC「退出码矩阵」**：相同 ID 两次传入 → "无差异"+0；短 ID、大写、非十六进制、含占位符 → 2 且错误文案不回显输入值（e4ecacf 的修复点，参数解析错误统一为中文脱敏指引）；不存在的合法 ID → 2；指向不存在库路径 → 2 且该路径未被创建。
- **AC「只读与幂等」**：同一对 ID 连跑两次 `config diff`，输出逐字节一致；比较前后用 `sqlite3 /tmp/pr-diff.db "select count(*) from …"` 或文件 mtime 确认未写入任何事实。
- **AC「隔离矩阵」抽查**：
  - 仅改 `prompts/reading-*.md` 文本 → compile 得 B，diff A B 应只显示 read 投影变化、前后基线相同、"是否涉及校准：否"；
  - 仅改某材料的声明版本标签（如 profile `version`）→ "配置类别"差异可见，但受影响投影为"无"、基线不变；
  - 仅改 screening 槽 adapter 选择 → boundary/value 投影与基线变化；
  - 仅改 adapter 文件内 `pi_version`/`adapter_version` → 仅完整快照身份差异，投影/基线不变（审计版本不入语义的显式反例）；
  - 停用主题的描述变化 vs 启用主题的语义变化 → 前者不动 value/基线，后者动 value/基线但不动 boundary。
- **AC「显示内容」**：核对 diff 输出仅含配置类别、版本/哈希、受影响投影、前后基线、"是否涉及校准"；不出现 Profile/Prompt 正文、原始全文 diff、minor/major 或"校准通过"字样。
- **AC「公共服务分层」**：Python REPL 中 `from paper_radar.config import load_config_snapshot, project_config, diff_config_snapshots`，对已验证快照直接调 `project_config`（不碰数据库/CLI），对照 `docs/contracts/config-projections.md` 的投影组成表核对六个 `projection_id` 与 `baseline_id`。
- **AC「文档同步」**：`grep -rn "尚待\|尚未交付" docs/contracts/ CONTEXT.md` 应无 A2-08/#23 占位残留；`docs/contracts/config-projections.md` 与 `runtime-config.md:8-10` 指针互相可达。

**无法直接验证 / 需说明的项**：

- **Standards B1 的静默分歧风险**：只有在未来修改快照载荷格式时才会显现；当前只能通过对 `projections.py:58-61`、`diff.py:68-72`、`service.py:344-346` 三处形状的阅读对比确认。
- **Spec A1 的落点偏差**：属文档组织取舍，无机器判据；对照评论第 16 条原文人工判断是否接受。
- **校准工作流衔接**：diff 输出的"是否涉及校准"事实如何被后续校准变更流程消费（ADR-0020 分级）属后续票，本票无端到端入口。
- **真实生产库上的长链路行为**：评审与测试均在合成 fixture / 临时库上完成；真实用户库上的重复运行幂等性虽有同一判据保证，但未在真实库实测。
