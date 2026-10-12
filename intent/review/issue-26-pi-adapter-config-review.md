# Issue #26 代码审查：版本化 Pi RPC 适配器语义并接入配置快照

- 审查范围：`HEAD~3..HEAD`（已验证恰好三笔提交，固定点 `9e12da94fbd1d227019b668f33f0ee4596f97b68`）：

  ```
  c52986b fix(config): preserve type error classification (#26)
  03da919 fix(config): clarify adapter errors and verification bindings (#26)
  9aee663 feat(config): freeze Pi adapter materials (#26)
  ```

- 规格来源：GitHub Issue #26 正文（Problem、必须能冻结的内容 5 条、Scope boundaries、Acceptance criteria 9 条、Coordination）与全部 3 条 comments（①「一个文件」边界表与 V2 可插拔设计决策；②③ Pi 二进制供给/vendoring 讨论，明确不改变本票范围）。
- Standards 依据：AGENTS.md、CONTEXT.md、docs/agents/domain.md、docs/adr/0026-control-pi-through-a-bounded-rpc-adapter.md、docs/contracts/（runtime-config.md、adapter-config.md）与 Fowler smell 基线。
- 审查方式：只读双轴独立审查（Standards / Spec 两个并行子代理）；全部关键发现已经主代理逐一抽查复核（`compile.py:71-73`、`adapter_loading.py:20-32`、`errors.py:21-26`、`yaml_loader.py:1,140-148`、`adapters.py:67-70,97-100`、`service.py:158,223-225,390,399`、`scripts/a2_scope.py:108-111,144-155`、`runtime-config.md:3,14,29,39,43-44,196-202,232,254-256`、`offline-evidence.md:99-104`、`adapter-config.md:101-103,115-119,131`、`settings-pi.yaml:4-7`、`tests/test_config_extraction_cli.py:96`，均与报告一致）。未修改代码、未创建 commit、未触碰 Issue。
- 工具基线（实际运行）：5 个新增测试模块 80 passed；全量 `pytest` 805 passed；ruff、mypy 通过；`./scripts/check-offline` 全绿（lockfile/format/lint/types/tests/contracts 及 A1、A2-01 结论均 passed，run_id `cbc0556e…`）。`tests/test_a1_acceptance.py`、`scripts/a1_scope.py`、`contracts/` 的 diff 为空，A1 固定字节零改动。

## 逐条核实与处理（2026-10-12，Issue #26）

本次处理以 `c52986b8597d4b720f76b72f54b38ffd4367bfdc` 为基准，并重新核对
[Issue #26](https://github.com/MeteoBoy4/PaperRadar/issues/26) 的正文与全部评论，
它们与实现时已读取的版本一致。下文原审查报告保留为历史记录；当前处理结果以
本节为准。“人工针对性检查入口”按用户要求未读取、未执行、未修改。

### Standards 轴

| 建议 | 核实结论 | 本次处理 |
| --- | --- | --- |
| A1：公共契约缺项 vocabulary、开放总览与 Pi 示例未同步 | 成立。adapter 专门契约已说明三个原因，但主契约的阶段矩阵和总览不完整；这是文档缺口，不是缺项计算错误。 | 在 `runtime-config.md` 总览和封闭逻辑名称主列表纳入 adapter 与系统 Prompt，补全 boundary/value/reuse/Read 缺项矩阵及条件，说明 Pi 示例三槽的显式选择。未选 adapter 仍保留旧业务配置完整性含义。 |
| B1：`config_root` 名称与“配置根”术语冲突 | 成立，实际参数是 settings 所在的 `config/` 目录，而不是其父目录。 | 局部改名为 `config_dir`，公共配置服务签名和路径规则不变。 |
| B2：YAML 模块 docstring 陈旧，建议拆分 Prompt I/O | docstring 问题成立；不采纳拆分模块的建议。两类读取都属于配置文件 I/O 边界，纯编译/语义层没有引入 I/O 依赖，尚无不同生命周期要求。 | 更新模块自述为“严格 YAML 装载与 UTF-8 Prompt 字节读取”，保留集中 I/O 的现有边界，避免仅为一个简单读取函数新增模块。 |
| B3：工具/资源列表前置校验器重复 | 成立，属于微小重复，无功能错误。 | 提取模块内 `_tuple_or_passthrough`，两个字段校验器仍分别保留原契约与校验入口，没有引入通用注册表。 |
| B4：Prompt 回放的编译值检查重复 | 成立，两类 Prompt 的 UTF-8 内容检查相同，版本绑定不同。 | 将两类 Prompt 的共同内容校验合并到一个分支，再分别验证系统资源与业务 selector 绑定；不额外引入只包装单行比较的谓词。 |
| B5：Pydantic 错误类型键未说明来源 | 来源注释建议合理；这些是外部协议词汇，不是项目自由领域状态，无需新增一套领域 enum 或逐个常量。 | 在 `VALIDATION_GUIDANCE` 中注明通用键来自 `ValidationError.errors()` 的 `type` 字段，保留锁定依赖与未知类型的受控 fallback。 |

### Spec 轴

| 建议 | 核实结论 | 本次处理 |
| --- | --- | --- |
| A1：固定材料工厂未加入 A2 哈希绑定 | 符合既有配置票的证据惯例，采纳。原有固定语义载荷/常量没有从被测函数生成，未发现 AC8 断言来源本身违规；本项增强支撑文件的变更检测。 | 将 `tests/config_adapter_support.py` 精确字节哈希纳入 `REQUIRED_SOURCE_MODULES`，同步受影响源码哈希与离线证据文档；A1/A2-01 固定测试、scope、快照格式和 migration 不变。 |
| A2：主契约缺项矩阵与封闭逻辑名列表未同步 | 缺项矩阵问题成立。两个新增逻辑名原先已在补充句记录，并非完全缺失；合入主列表能避免读者遗漏。 | 与 Standards A1 一起修正文档，两个审查轴的原始发现仍分别保留。 |
| A3：悬空 adapter 版本文件无独立回归 | 成立，原代码已有拒绝机制，但尚无专门保护。 | 对 screening/reuse_assessment/reading 三槽分别覆盖公共 check/compile 服务和真实 CLI；CLI 返回 2、具体读取原因及修正指引，错误不回显系统 Prompt。 |
| B1：通用指引影响既有材料错误文案，建议知情记录 | 附带影响成立，采纳记录建议；不回退具体指引，也不另行请求确认。本次用户已授权核实并改进合理部分，仓库明确要求可操作错误。 | 在 `offline-evidence.md` 明确记录既有配置类型的文案变化，保留“类型错误”分类、接收规则、退出码与身份语义；由既有 OCR CLI 回归继续保护。 |
| C：未发现实现错误 | 对报告核查的版本登记、原子提交、回放、旧快照身份和语义隔离结论认可。 | 局部整理继续通过已有公共服务/真实 SQLite 与 CLI 测试验证；不将本次处理扩展为 RPC、校准或自动精读实现。 |

### 观察项与后续边界

- 统一交叉指引：主契约明确 `A2-08（Issue #23）` 是同一后续投影/基线/diff 任务，
  保留既有 ticket 名称，不改写职责或实施次序。
- 版本不一致定位建议合理。已针对 reading 与其他两槽不同选择的场景增加
  red → green 回归；错误指明 `settings.adapters.reading`。adapter 文件读取或
  校验错误补上对应 `adapters.<slot>`，不回显材料值或底层异常。
- 原报告未单列的同款 selector 校验惯例、依赖常量属性继续保留：已有公共契约与
  测试定义它们的边界，不为统一外形扩大重构。
- 原报告的两项新增保护缺口已处理；统一投影/基线/diff 联动仍待 #23，完整并发
  验收仍待 A2-09（#24）。未执行 Pi/Node、网络模型或人工检查入口，不产生
  minor/major、enable 或关闭 Issue 的操作。

### 本次验证

- 修正前新增 selector 定位回归：10 项失败，证明原错误缺少槽名；原有 58 项通过。
- 修正后 adapter 公共服务/SQLite/CLI 与 boundary 回归：105 项通过；mypy 通过。
- 最终 adapter、既有 OCR 错误分类与 A2 结论相关回归：110 项通过；mypy、Ruff
  静态规则与格式检查通过，`git diff --check` 通过。
- 完整 `./scripts/check-offline` 通过：lockfile/format/lint/types/tests/contracts
  全部 passed，A1 与 A2-01 结论均 passed；run_id 为
  `531d6bd407254f86b83bcf41424ab983`。证据记录本次提交前的工作树，不将其改写为
  提交后的 HEAD 证明；补录本段验证结果后未再改动实现或测试。

## Standards

**(a) 成文标准违反（硬违规）**

**A1. 新受控缺项 vocabulary 未同步进公共配置契约文档**
- 位置：`src/paper_radar/config/compile.py:71-73` 新增三个 `MissingReason` 成员（`screening_adapter_prompt_placeholder`、`reuse_adapter_prompt_placeholder`、`read_adapter_prompt_placeholder`），会实际出现在 boundary/value/reuse/read 的缺项输出中；未同步处为 `docs/contracts/runtime-config.md:196-202`（「当前就绪范围」逐阶段缺项表未列新原因）、`:3`（开头「当前开放…」总览句无 adapters，尽管 `:232` 已列）、`:254-256`（`settings-pi.yaml` 示例描述未提它现在选择 adapters，实际 `examples/config/settings-pi.yaml:4-7` 三槽均选 `pi-v1`）。
- 依据：AGENTS.md「文档维护」——「领域不变量或受控 vocabulary」变更需同步更新文档；AC9 亦要求同步公共配置 Contract（与 Spec 轴 A2 同源，两轴各自成立，不合并）。
- 实际影响：runtime-config.md 是运行配置契约的权威文档，其缺项表仍是旧集合；新缺项仅在 `docs/contracts/adapter-config.md:101-103` 记录，两份契约文档对同一 CLI/快照输出的描述不一致，会误导后续 #23 投影实现者与用户。
- 最小修复：在缺项表 boundary/value 行补 `screening_adapter_prompt_placeholder`、reuse 行补 `reuse_adapter_prompt_placeholder`、Read 行补 `read_adapter_prompt_placeholder`；总览句与 settings-pi 示例描述各补一句 adapters 选择。

其余成文标准类别逐项核查后**无发现**：核心不变量（SQLite 登记、同键同字节幂等、同键字节变化拒绝、失败整体回滚、历史回放不回退当前文件，均有 `tests/test_config_adapter_persistence.py` 钉住）；数据与版本控制（声明版本 `version` 与执行审计版本 `pi_version`/`adapter_version` 分离、语义载荷排除非语义身份、包络 `FORMAT_VERSION` 未提升、无 migration，符合 ADR-0026 第 11 段与 CONTEXT.md「适配器语义」）；Calibration 安全（`adapter-config.md:131` 明确不产生 minor/major、enable 或 calibration evaluation 事件；CLI 无条件打印「配置完整性不证明 Pi 执行就绪」）；LLM 与证据规则（错误脱敏有参数化测试；`AdapterSemantics.system_prompt_text` 用 `field(repr=False)`）；依赖与外部服务（无新依赖、全部测试离线、不执行 RPC）；范围控制（无 V2 能力）；CONTEXT.md/ADR 一致性。另核实撤回一项嫌疑：c52986b 的 `literal_error` 文案修订被既有测试 `tests/test_config_extraction_cli.py:96`（断言「类型错误」）钉住，回归覆盖满足。

**(b) 基线 smell（判断性发现）**

**B1. Mysterious Name — `config_root` 参数名与成文术语相反**
- 位置：`src/paper_radar/config/adapter_loading.py:20-21`；调用点 `service.py:223-225` 传入 `settings_path.parent`（即 `config/` 目录）。
- 依据：Fowler Mysterious Name；`runtime-config.md:14` 定义「配置根」为 `config/` 的**父目录**，`service.py:158` 亦以 `root = settings_path.parent.parent` 使用该含义。
- 实际影响：熟悉契约文档的读者会以为该参数是配置根（父目录），实际应传 `config/` 目录，属于会传错参数的误导命名。
- 最小修复：改名为 `config_dir` 或 `settings_dir`。

**B2. Divergent Change + 陈旧模块 docstring — yaml_loader.py 混入非 YAML 读取**
- 位置：`src/paper_radar/config/yaml_loader.py:1`（docstring「仅用于配置文件边界的严格 YAML 读取」）vs 新增 `read_prompt`（`:140-148`，读取 UTF-8 Markdown 字节）。
- 依据：Fowler Divergent Change（模块现为「严格 YAML 装载」与「Prompt 字节读取」两个原因变化）；改动后 docstring 仍描述旧行为。
- 实际影响：模块职责自述失真；后续维护者按 docstring 判断归属时会放错新函数。
- 最小修复：更新模块 docstring 纳入 Prompt 字节读取，或将 `read_prompt` 移入独立的材料 IO 模块。

**B3. Duplicated Code — 两个逐字相同的 tuple 前置校验器**
- 位置：`src/paper_radar/config/adapters.py:67-70`（`tool_list`）与 `:97-100`（`resource_list`），函数体逐字相同：`tuple(value) if isinstance(value, list) else value`。
- 依据：Fowler Duplicated Code。
- 实际影响：两处同步演进的义务；今后改动 YAML 列表归一化规则需记两处。
- 最小修复：提取模块级 `_tuple_or_passthrough(value)`，两个 decorator 共同调用。

**B4. Duplicated Code（轻微）— 回放中 Prompt 编译值校验重复**
- 位置：`src/paper_radar/config/service.py:390`（pi-system 分支）与 `:399`（业务 Prompt 分支）重复 `{"text": raw.decode("utf-8")} != entry["config"]`。
- 依据：Fowler Duplicated Code；两分支其余逻辑不同（版本绑定检查各异），故判轻微。
- 最小修复：提取小谓词如 `_prompt_config_matches(raw, entry)` 供两分支调用。

**B5. Magic strings — pydantic 错误类型字符串混入受控映射且无注释**
- 位置：`src/paper_radar/config/errors.py:21-26`（`"missing"`、`"extra_forbidden"`、`"literal_error"`、`"string_type"`、`"tuple_type"`、`"missing_argument"`），与 enum 值键混排在同一 `VALIDATION_GUIDANCE`。
- 依据：AGENTS.md「编码流程」——避免 magic string；Fowler Primitive Obsession 轻量形态。这些键是 pydantic `error["type"]` 外部词汇，源码中无注释说明来源。
- 实际影响：读者需懂 pydantic 内部才能理解键含义；pydantic 升级改名词时无编译期锚点。
- 最小修复：加一行注释说明这些键取自 pydantic 错误 `type` 字段，或定义为模块级具名常量。

**观察项（不计 finding，仅记录）**
- `AdapterSelectors.valid_version`（`schema.py:132-135`）是既有 PromptSelectors/ContractSelectors/Settings 同款校验器的第 4 次重复——属既有惯例延续，不单列。
- `adapter_dependencies`/`calibration_adapter_slots`（`compile.py:156-168`）是不依赖实例状态的常量属性，但 `adapter-config.md:115-119` 明确将其定为 #23 接口且有测试冻结，不判 Speculative Generality。
- 票名不一致：`runtime-config.md:212,241` 用「A2-08」，`adapter-config.md` / README / draft.md 用「#23」指同一批统一投影/基线交付，建议统一或互相指引。
- 版本不一致错误的消息定位精度：`adapter_loading.py:35-37`「与 selector 不一致」未含槽名，略逊于 `service.py:143-146` 既有模式；三槽各选不同版本时用户需自行定位。

## Spec

### (a) 缺失 / 部分实现

**A1. 新增测试支撑工厂未纳入 A2 固定哈希绑定，偏离既有证据惯例（minor）**
- 位置：`tests/config_adapter_support.py:8-11`（`SYSTEM_PROMPT` 固定字节与 `SYSTEM_PROMPT_SHA256`，是 `tests/test_config_adapters.py:47-67` 已审查固定载荷断言的来源）；`scripts/a2_scope.py:148-155` 仅登记了 `adapters.py`/`adapter_loading.py`；`docs/verification/offline-evidence.md:102-104` 的 #26 条目同样只提这两个模块。
- 规格：AC8「投影身份期望使用已审查固定载荷/常量，不从被测函数生成」；仓库既有先例——`offline-evidence.md:99`（A2-04 登记 `tests/config_reuse_support.py`）、`:100`（A2-05 登记 `tests/config_extraction_support.py`）均把对应支撑工厂固定进 `REQUIRED_SOURCE_MODULES`。
- 实际影响：`scripts/a2_acceptance.py:173` 的 SCOPE_DRIFT 检查发现不了对 `config_adapter_support.py` 的后续修改，固定合成材料的「已审查」绑定链不完整。
- 最小修复：将 `tests/config_adapter_support.py` 当前字节 sha256 加入 `scripts/a2_scope.py` 的 `REQUIRED_SOURCE_MODULES`，并在 offline-evidence.md 的 #26 条目补一句登记说明。

**A2. 公共配置 Contract 的就绪矩阵与封闭逻辑名列表未同步新增 adapter 内容（minor 文档缺口）**
- 位置：`compile.py:71-73` 新增三个公开 `MissingReason`；`docs/contracts/runtime-config.md:196-202` 的「阶段 | 必需材料 | 缺项原因」表仍只列旧原因；另 `:39` 的「当前封闭逻辑名称」主列表未并入 `adapter/pi-rpc`、`prompt/pi-system`，而是 `:43-44` 另起一句补充。
- 规格：AC1「文档明确 selector、版本来源、材料目录、封闭逻辑名称、字段/空值/默认值与依赖矩阵」；AC9「同步 README、公共配置 Contract、阶段/校准依赖矩阵」。（与 Standards 轴 A1 同源。）
- 实际影响：只读 runtime-config.md 的消费者无法从就绪矩阵得知 adapter 占位缺项的受控名称；封闭逻辑名称列表在形式上不完整。
- 最小修复：就绪矩阵四行补注对应 adapter 占位缺项（或加一行统一说明），并将两个新逻辑名并入 `:39` 主列表。

**A3. 悬空 adapter 版本文件无显式测试（minor 覆盖缺口）**
- 位置：`src/paper_radar/config/adapter_loading.py:31-33`（机制存在：selector 指向缺失的 `adapters/<version>.yaml` 时 `read_yaml` 返回脱敏 ConfigError「无法读取文件」）；5 个新测试文件中无对应用例。悬空**资源**引用已覆盖（`tests/test_config_adapter_validation.py` 的 `version: absent` 参数）。
- 规格：AC1「悬空版本/资源引用…返回脱敏受控错误」。AC8 的必测清单未列此项，故不算违规，仅为覆盖缺口。
- 实际影响：该错误路径（区别于资源悬空）无回归保护。
- 最小修复：在 `test_config_adapter_validation.py` 增加一个 selector 指向不存在 adapter 文件的用例，断言返回 2 且不回显输入。

### (b) 超范围实现

**B1. 通用校验指引改动波及既有配置种类的用户可见错误文案（low，建议知情确认而非回退）**
- 位置：`src/paper_radar/config/errors.py:21-26` 新增六个通用 pydantic 错误类型键。HEAD~3 之前，profile/models/topics/escalation/extraction 的所有 Pydantic 校验错误统一回退「字段缺失、类型错误或不受支持」，现在分别给出更具体的指引（含 c52986b 对 `literal_error` 文案的修订）。
- 规格：AC1 只要求 adapter 相关「错误类型…返回脱敏受控错误」。该改动方向符合仓库「错误信息应说明可操作的具体原因」原则，且已核实固定测试 `tests/test_config_validation.py`、`tests/test_config_service.py` 不断言旧文案、无快照身份影响；但严格说这是既有材料错误文案的行为变化，超出 #26 字面范围。
- 实际影响：既有配置种类的校验错误文案改变（仍中文、脱敏、不含输入值）。
- 最小修复：无需代码改动；建议在票据或 offline-evidence.md 中显式记录这一附带行为变化以便验收知情。注：同文件中 `yaml_loader.py:21-26,57-60` 的重复键脱敏（旧实现直接回显原始键）属于 AC1 明确要求的修复，不算蔓延。

### (c) 实现错误

**无发现。** 重点验证过的高风险点，实现均与规格及文档一致：

- **AC2 事务与回放**：`storage/repository.py:57-132` 单 `BEGIN IMMEDIATE` 事务覆盖冲突检查与全部写入；`tests/test_config_adapter_persistence.py` 覆盖 check 只读、幂等、仅注释冲突拒绝、删除全部源文件后经子进程精确回放（固定 `semantics_id` 常量断言）、trigger 注入失败整体回滚、四类损坏不回退当前文件。
- **AC3 兼容**：`compile.py:233-239` 仅在非空选择时写入 `selectors.adapters`，旧快照身份由 `tests/test_config_adapters.py:21-23` 的固定哈希（取自实现前 commit 的真实编译器）钉死；未选择时 `adapter_slots` 明确 `unconfigured`，不合成默认策略；CLI 无条件打印免责声明（`cli.py:55`）。
- **AC5/AC6 边界**：`AdapterSemantics.payload_json`（`adapters.py:121-139`）排除声明版本、YAML 原始哈希、`pi_version`/`adapter_version` 审计版本，保留策略语义版本 `bounded-rpc-v1` 与独立 `format_version: 1`；改名/注释/审计版本变化只变快照身份不变语义（`test_declaration_comments_and_transport_audit_do_not_change_semantics`），提示词/参数变化只影响对应槽（`test_only_selected_consumers_change…`、`test_shared_prompt_changes_follow_actual_consumers`）；未建第二套投影/diff，`adapter_dependencies`/`calibration_adapter_slots`（`compile.py:156-168`）恰好落在本票「补充 #23 未覆盖材料」的边界内。
- **评论①边界表**：提示词正文独立登记为 `(prompt, pi-system, version)`（`adapter_loading.py:52-62`），Pi 材料只存版本+哈希引用；`provider/model/protocol/temperature/top_p` 作为未知字段拒绝（参数化测试覆盖）；三槽 selector 独立（`schema.py:125-135`）；`MaterialKind.ADAPTER` 中性名 + 逻辑名 `pi-rpc` 带 harness 身份，符合评论①第 1 条决策。
- **Scope boundaries**：无超时/内存/凭据/任意 CLI 参数字段（extra-forbid + 参数化测试）；`tools` 固定空元组；policy 全部为固定 Literal 值、无可放宽布尔、无 attempt 预算参数；`prompt_only` 一致性检查（`adapter_loading.py:90-98`）只约束已选 adapter 的槽，既有协议材料可正常回放。

### 残留风险

- 悬空 adapter 文件路径无回归测试（Spec A3），属机制已实现但保护缺失。
- `config_adapter_support.py` 未进固定哈希绑定（Spec A1），未来改动不会被 SCOPE_DRIFT 捕获。
- 并发 compile 的完整验收由 A2-09 承接（约定范围内）；本票有 `BEGIN IMMEDIATE` 与唯一约束兜底。
- check-offline 通过 ≠ Pi live 接入、校准通过或自动精读资格；`adapter_dependencies` 的实际消费待 #23 验收。

## 总结

Standards 轴：1 项硬违规、5 项判断性发现（最重：A1——新受控缺项 vocabulary 未同步进 runtime-config.md 缺项表，违反 AGENTS.md「文档维护」对受控 vocabulary 的硬性同步要求）。Spec 轴：3 项缺失/部分实现（均 minor）、1 项超范围观察（low，建议记录而非回退）、0 项实现错误（最重：A1——固定载荷支撑工厂未纳入 A2 哈希绑定，「已审查」绑定链不完整）。Standards A1 与 Spec A2 指向同一文档缺口，两轴依据不同（文档维护硬要求 vs AC1/AC9），按双轴原则保留不合并。

## 人工针对性检查入口

以下入口可在不改动代码的前提下，对本 diff 的变更范围和 Issue #26 各条 AC 做人工抽查。通用入口：

- **变更范围**：`git log HEAD~3..HEAD --oneline`（应恰好三笔）、`git diff HEAD~3...HEAD --stat`、逐文件 `git diff HEAD~3...HEAD -- <path>`；A1 零改动用 `git diff HEAD~3...HEAD -- tests/test_a1_acceptance.py scripts/a1_scope.py scripts/a2_acceptance.py contracts/`（应为空）确认。
- **整体回归**：`uv run pytest tests/test_config_adapters.py tests/test_config_adapter_architecture.py tests/test_config_adapter_cli.py tests/test_config_adapter_persistence.py tests/test_config_adapter_validation.py -v`（80 例）；`./scripts/check-offline` 跑完整离线验证（A1 + A2-01 双结论）。

按 AC 的针对性入口（在临时目录复制 `examples/config/` 操作，避免污染仓库；先 `uv run paper-radar db upgrade --database /tmp/x.db`）：

- **AC1（受控错误）**：逐一构造畸形 `adapters/pi-v1.yaml` 喂给 `config check`：重复 YAML 键、未知字段（如 `provider`）、`thinking_level` 非法值、`resources` 空清单/多元素、`resources[0].sha256` 非 64 位小写、policy 字段改写（如 `compaction: enabled`）、内联 `api_key`、文件内 `version` 与 selector 不一致、`adapters: null` 整体置空（`adapter-config.md:10` 要求拒绝）、models 对应槽 `protocol: json_schema`（协议冲突）。预期：各自返回退出码 2 + 中文受控原因，stderr 不回显输入值或命令。另可构造 selector 指向不存在文件（`adapters.screening: no-such-version`）——注意此路径目前无测试覆盖（Spec A3），手工验证其脱敏行为恰好是补测试前的有效确认。
- **AC2（幂等/冲突/回放）**：`config compile --settings …/settings-pi.yaml` 连跑两次 → 同一快照 ID；仅改 `pi-v1.yaml` 注释再 compile 同版本 → 拒绝；删除/改坏 `adapters/pi-v1.yaml` 与 `prompts/pi-system-v1.md` 并把 settings 改选其他版本后，`uv run python -c "from paper_radar.config import load_config_snapshot; …"` 按旧快照 ID 回放 → 精确成功且身份不变；用 `sqlite3` 手工篡改库内登记字节 → load 受控报错而非静默重哈希。
- **AC3（未配置/旧快照兼容）**：settings 不含 `adapters` 键 compile → 快照 JSON 无 `selectors.adapters`、`adapter_slots` 全 `unconfigured`、不合成默认 Pi 策略；在 HEAD~3 检出（或临时 worktree）下用 `settings-value.yaml` compile 一份无 adapter 的旧快照，回到 HEAD 后按 ID load → 原格式原含义读取成功（`tests/test_config_adapters.py:21-23` 的固定哈希已钉住旧身份，可对照）。
- **AC4（包络/迁移不变）**：`git diff HEAD~3...HEAD -- src/paper_radar/storage/` 应为空；`grep -n FORMAT_VERSION src/paper_radar/config/compile.py` 应仍为 `1`。
- **AC5/AC6（语义身份与依赖边界）**：Python REPL 中用 `tests/config_adapter_support.py` 的固定材料构造两个仅声明版本/注释/`pi_version` 不同的 `PiAdapter` → `AdapterSemantics.semantics_id` 相同；改 `thinking_level` 或提示词正文 → 变化；读 `snapshot.adapter_dependencies` / `calibration_adapter_slots` 对照 `adapter-config.md:115-119` 表格。
- **AC7（隔离矩阵）**：`uv run pytest tests/test_config_adapters.py -v -k "only_selected_consumers or shared_prompt"` 看「仅改 Read 不影响校准槽」「共有资源按实际消费者传播」两条；或手工 compile `reading: pi-v1` vs `reading: null` 两份 settings 对比快照的 `adapters` 映射与阶段缺项。
- **AC8（测试前提）**：5 个新测试模块在断网/无 Pi/无 Node 环境下直接可跑（deny_network sentinel 已在全量 pytest 中生效）；`tests/config_adapter_support.py` 为固定合成材料、测试用 `tmp_path` 真实临时 SQLite，可 Read 核对。
- **AC9（文档/help）**：空 HOME + 临时 cwd 下 `uv run paper-radar config check --help`、`config compile --help` → 退出码 0、全中文、不产生文件；README 新增段落与 `docs/contracts/adapter-config.md` 对照 `pi-v1.yaml` 示例逐字段核对（含 `8b0188e4…` 哈希与 `examples/config/prompts/pi-system-v1.md` 实际字节一致：`sha256sum examples/config/prompts/pi-system-v1.md`）。

**无法直接验证 / 需说明的项**：

- Spec A1 的绑定链缺口只有在对 `tests/config_adapter_support.py` 做后续修改时才会以 SCOPE_DRIFT 漏检的形式显现；当前只能通过阅读 `scripts/a2_scope.py:148-155` 与既有先例（`:108-111`、`:144-147`）对比确认。
- 并发 compile 的原子性：约定由 A2-09 验收，本票仅有 `BEGIN IMMEDIATE` 与唯一约束兜底及 trigger 注入回滚测试，无并发验收入口。
- Pi 实际执行与 RPC 行为：本票明确不执行模型、不启用流水线；「锁定版本可复现供给」的正确性（issue 评论②③）属后续执行器/供给票，本次无入口。
- `adapter_dependencies`/`calibration_adapter_slots` 的实际投影消费：接口已按 `adapter-config.md:115-119` 冻结并有测试，但消费方是 #23 的统一投影/基线，在其交付前无法端到端验证。
- 升级语义评估（`pi_version` 变化是否影响校准）：`adapter-config.md:125-127` 只定义了纪律（不自动宣称校准兼容），机器不可验证，依赖后续升级时的实测流程。
