# Issue #21 代码审查：A2-06 独立保存 Read 配置并明确缺少权威契约

- 审查日期：2026-10-12
- 固定点：`HEAD~2`（`1e19af9`）
- 目标提交（已验证 `git log HEAD~2..HEAD --oneline` 恰好两笔）：
  - `4624260` feat(config): preserve versioned Read configuration (#21)
  - `257ee92` docs(config): clarify Read business prompt location (#21)
- 规格来源：GitHub Issue #21 正文 + 全部 comments（含补充边界三点与 chunking 宿主决定）；父 spec #15（Decisions 4–5、11、13–14；补充一 2；补充二 21、25、31–32）；ADR-0004、ADR-0023
- 审查方式：双轴并行只读子代理；diff 共 1356 行、23 个文件（+851/-30）；未修改代码、未创建 commit、未操作 Issue
- 子代理实际运行验证：`pytest tests/test_config_read*.py -q` → 68 passed；`pytest tests -q` → 883 passed；`scripts/a2_scope.py` 38 个固定哈希与工作树字节逐一相符

## Standards

依据：`AGENTS.md`（核心不变量、数据与版本控制、LLM 与证据规则、依赖与外部服务、编码流程、面向用户的行为、文档维护、范围控制）、`CONTEXT.md`、`docs/agents/domain.md`；仓库无 CONTRIBUTING/CODING_STANDARDS 文件；ruff/mypy 已覆盖项跳过。

**硬性违规（文档化标准）：未发现。** 逐条核对结果：

- 核心不变量：SQLite 原子登记、版本冲突拒绝、幂等重试、历史回放均有回归测试（`tests/test_config_read_persistence.py`）。
- 数据与版本控制：`read/read` 与 `prompt/reading` 走既有不可变登记键；包络格式版本未提升，无需 migration 且未新增。
- LLM 与证据规则：错误不回显输入（`PRIVATE_MARKER`/`secret-marker` 测试覆盖）；CLI 不输出提示词正文。
- 面向用户的行为：新增错误指引为可操作中文（`src/paper_radar/config/errors.py:16-18`）；`--help` 无 IO 有测试。
- 文档维护：公共配置契约变化同步更新了 runtime-config.md、adapter-config.md、README、intent/draft.md、offline-evidence.md、CLI help。
- 范围控制：未引入 V2 能力，明确不执行分块、不接受手写 Read Schema。

**判断项（baseline smell / 约定，均为 judgement call）：**

1. **Primitive Obsession / magic string（邻近文档标准）**
   - 文件行号：`src/paper_radar/config/service.py:59`、`:225`；`src/paper_radar/config/compile.py:397-401`、`:286`
   - 依据：AGENTS.md 编码流程"优先使用明确的领域类型和受控 enum / reason，避免 magic string"（"优先"级，故列为判断项）。`_PROMPT_NAMES = (StageName.BOUNDARY, StageName.VALUE, StageName.REUSE, "reading")` 混入裸字符串；`if name == "reading"`、`prompt_reason("reading", …)` 共三处字面量；`compile.py:286` 把 `prompt_reason(name: StageName)` 加宽为 `name: str`。
   - 实际影响：提示词逻辑名一半借 StageName、一半是裸串，拼写错误只能靠运行期暴露；类型签名变弱。
   - 最小修复：定义 `PromptName` StrEnum（boundary/value/reuse/reading）供两处共用，恢复 `prompt_reason` 的枚举签名。

2. **Repeated Switches（单次特例）**
   - 文件行号：`src/paper_radar/config/service.py:223-227`
   - 依据：统一 prompt 循环内唯一的按名分支 `path = (root/"prompts/reading"/f"{version}.md" if name == "reading" else …)`。注：reading 路径布局本身已写入 `docs/contracts/adapter-config.md`，文档标准覆盖路径选择；但分支可以数据化。
   - 实际影响：再增 prompt 槽时循环体会继续长特例。
   - 最小修复：在 `_PROMPT_NAMES` 旁放一张 `名称 → 路径模板` 映射，循环内无条件查表。

3. **Duplicated Code（既有形状的第 5 次重复）**
   - 文件行号：`src/paper_radar/config/service.py:395-402`（`elif key[:2] == _READ_KEY:` 分支）与 `service.py:211-219`（`_selected_materials` read 块）
   - 依据：Duplicated Code——分别复刻 models/topics/escalation 分支形状。AGENTS.md 编码流程要求"遵循现有命名、类型、Repository 和事务模式"且禁止顺手大重构，文档标准覆盖本气味，仅作记录。
   - 实际影响：每种新材料要同步改 if 链；extraction 用 `compiled_config()`、其余用 `model_dump()` 的差异容易被漏抄。
   - 最小修复（留待下一切片）：把 `(key, model, label, settings 属性, dump 函数)` 收敛为一张表驱动。

4. **测试夹具脆弱（轻微）**
   - 文件行号：`tests/config_read_support.py:29-44`
   - 依据：靠 `str.replace("reading: null", …)`、`replace("  boundary: v1\ncontracts", …)` 改写 YAML 文本；与既有 `config_test_support.py` 风格一致，但对方是整体重写文本而非局部替换。
   - 实际影响：上游夹具格式微调（如注释插入）会静默失效。
   - 最小修复：直接在 `read_inputs` 里整体重写 models/settings 文本。

其余说明：`NOT_IMPLEMENTED` 将 `prompts_reading` 换成 `read_output_contract`/`read_execution`，仅被 `scripts/a2_acceptance.py:224` 记录进证据 JSON，改名安全；提交示例 `settings-read.yaml` 声称"boundary 就绪、Read 仅缺 read_contract"与代码行为一致（`test_committed_read_example…` 通过）。

## Spec

依据：Issue #21 正文 9 条验收标准 + 评论一 3 点边界 + 评论二 chunking 宿主决定，逐条对照代码/文档/测试。

**(a) 遗漏/部分实现：无。** 9 条验收标准、评论一 3 点、评论二均逐条核对到代码/文档/测试，无缺口。

**(b) 范围蔓延：无。** 改动全部落在票内：config 代码与测试、本票文档（README、runtime-config.md、adapter-config.md、offline-evidence.md、draft.md §6+A2-06 段）、a2_scope.py 哈希与 NOT_IMPLEMENTED 更新、示例材料。未新增命令、依赖或票外流程；draft.md 同步属 AGENTS.md 明确要求。

**(c) 错误实现：无。** 重点怀疑点均已排除：

- `compile.py:397-403` Read 缺项含 `read_prompt`/`read_prompt_placeholder` 与 `chunking_version`，与 `docs/contracts/runtime-config.md:149` 必需项表一致；READ 恒 `NOT_READY` 且必含 `read_contract`（`compile.py:385-405`）。
- 历史快照兼容：未选 read 时 selectors 不含 `read`（`compile.py:231-232`），包络与 FORMAT_VERSION=1 不变，旧快照身份不被重算；`service.py:395-402,450` 回放校验 read 与 settings 一致性。
- `read.py:38-46` 的 before-validator 使 `null`/数字/布尔/未知值统一走受控 `chunking_version_unsupported` 中文指引，不回显输入值（`tests/test_config_read_validation.py` 覆盖）。

两处非问题观察（不影响结论）：README 概述仍写「三阶段提示词/契约」未单列 reading 提示词，但紧随段落已专门说明 settings-read 示例；依赖矩阵缺项列举顺序与 CLI 输出顺序不同，文档未承诺顺序。

**已满足的验收标准（审计用清单）：**

- AC1 版本化加载/严格验证/原子登记/重启回放：`service.py:211-219`、`schema.py:101,151`；`test_config_read_persistence.py` 覆盖三类材料改字节拒绝、新版本并存、旧快照跨进程回放。
- AC2 chunking 受控 v1 身份：宿主按评论二定为独立 `config/read/<version>.yaml` + `settings.read`，写入 runtime-config.md「Read 配置与分块身份」节与依赖矩阵；`ChunkingVersion` 代码受控 enum，语义经 `ReadSemantics` 保留，文档明示「算法自身没有内容文件或独立字节登记」；不运行分块/Read、不新增 Read 输出契约。
- AC3 READ 恒 not_ready 且含 `read_contract`；其余缺项用统一受控词汇；`contracts.reading`/`contracts.read` 按未知字段拒绝；`runtime-config.md:137-139` 与测试覆盖。
- AC4 合法变更新快照且保留旧模型/Prompt；boundary 完整性不变（`test_config_read_persistence.py:106-126` 跨阶段相等断言）；仅依赖 A2-02 已有 reading 槽。
- AC5 `settings.language/paper_id/artifact/task` 与 `read.language/api_key/paper_id` 均拒绝且不回显；diff 无凭据读取、能力探测或 fallback。
- AC6 公共 CLI 参数化演示未配置/占位/已配置缺契约/新版本与旧材料读取（`test_config_read_cli.py`）；提交示例 `settings-read.yaml` 经真实 CLI 验证；README 明示「不构成阶段 B 验收」。
- AC7 真实临时 SQLite + 回归/CLI 集成测试；全套 883 通过；无网络/付费/真实配置依赖。
- AC8 中文 help/错误；help 无 I/O（`test_help_with_read_support_has_no_external_io`）；错误只给字段路径与受控指引、无 Traceback、不回显标记；退出码 0/2 约定保持。
- AC9 新测试独立模块 `test_config_read_*`；`a1_scope.py`、`tests/deny_external_io`、四份 v1 冻结契约均未动；`read.py` 纯层架构测试；contracts/screening 不反向依赖；a2_scope 哈希与实际字节一致，NOT_IMPLEMENTED 更新与 offline-evidence.md 表述一致。
- 评论一①：`read_adapter_prompt_placeholder` 接入 Read 就绪判定（`compile.py:389-391`），必需项表与测试同步。
- 评论一②③：宿主位置写入 Contract 与依赖矩阵；`prompts.reading` 行由「仅 null」改为版本化选择，封闭逻辑名新增 `prompt/reading`，绑定路径 `prompts/reading/<version>.md` 在 runtime-config.md 与 adapter-config.md 双双明确。
- 评论二：`settings.read` + 独立 `config/read/read-v1.yaml` 如期实现。

## 实施者逐项核实与处理（2026-10-12）

关联 Issue：[#21](https://github.com/MeteoBoy4/PaperRadar/issues/21)。核实基线为
`257ee92`；上文保留独立审查时的原始结论和历史验证记录。

| 建议 | 核实判断 | 处理 |
| --- | --- | --- |
| Standards 1：Prompt 逻辑名与 StageName 混用、裸字符串与宽泛签名 | 合理。业务提示词名称应独立于阶段名称；特别是 `reading` 与 `read` 含义不同。 | 已在纯配置 `schema.py` 定义 `PromptName`，加载与回放共用其四个受控值，编译层 `prompt_reason` 接收枚举。模型和 adapter 槽仍使用各自具名槽，不与提示词混同。 |
| Standards 2：固定 Prompt 路径查表 | 查表建议合理，但单个路径条件分支不构成“Repeated Switches”；不以假设的新槽作为扩展理由。 | 已将四种既定路径写入枚举键的固定映射，加载循环直接查表。未新增可配置路径、注册表或其他 Prompt 槽。 |
| Standards 3：版本化材料加载、回放的通用表驱动 | 重复形状的观察成立；报告也明确建议留待下一切片。当前不采纳该改造。 | 保留既有具名分支与事务模式。统一各类材料会触及 Profile 的独立处理、extraction 的 `compiled_config()` 和其他材料的严格回放检查；本次没有漏验或行为错误证据，不为消除气味扩大重构范围，也未自行创建后续任务。 |
| Standards 4：Read 材料工厂依赖上游 YAML 格式 | 合理。局部 `str.replace` 可在上游空白、注释或顺序调整时静默失效。 | `read_inputs` 改为显式写入完整 models/settings YAML；继续复用 boundary 工厂建立 Profile、冻结契约及真实临时 SQLite，生成的版本化材料字节和快照身份保持一致。 |
| Spec (a)：遗漏/部分实现为 0 | 核实成立。Read 配置保存、缺项、安全和历史回放要求均已有覆盖。 | 无额外功能修改。 |
| Spec (b)：范围蔓延为 0 | 核实成立。投影、diff、校准基线、Read 契约与执行仍属于后续票。 | 本次只整理已有 Prompt 名、既定路径与本票夹具，不实现后续能力。 |
| Spec (c)：错误实现为 0 | 核实成立。Read 恒未就绪、旧包络兼容和 chunking 类型校验均符合规格。 | 使用公共 check/compile/load 服务与四个改动前固定身份补充兼容性回归。 |
| 非问题观察：README 概述和缺项顺序 | 原结论合理。README 已专段说明 Read 配置；契约未承诺缺项展示顺序。 | 不为措辞或顺序观察修改无关行为。 |

本次不读取或执行报告中的“人工针对性检查入口”，该部分保留原样。
新增身份回归的期望值在代码修改前，从已验证提交 `257ee92` 的固定合成材料记录，
以字面量保存；测试运行中不调用被测代码生成期望值。

本次实际验证：

- 相关测试（Prompt 身份、全部 Read 模块、boundary/value/reuse、架构及 A2 验收）：172 passed。
- `uv run --offline --locked mypy`：99 个源码文件通过。
- `./scripts/check-offline`：lockfile、format、lint、types、全部 tests、四份冻结 contracts 均 passed；A1 与 A2-01 结论均 passed。
- 离线证据：`verification-runs/d979bddb1d9c4722b3c5a8980f437081.json`；同前缀 `.a1.json`、`.a2.json` 保存独立结论。验证后仅补入本报告的结果文字，代码和测试未再改动。

处理后：三项整理建议已落实，一项跨材料通用重构不采纳；未发现待修复的规格问题。
仍未实施的 Read 契约、执行与 #23 投影/diff 属于原有票边界，不因本次验证开放。

## 小结（独立审查原始结论）

- Standards 轴：硬性违规 0；判断项 4（最重：prompt 逻辑名裸字符串 `"reading"` 三处 + `prompt_reason` 签名加宽，邻近 AGENTS.md "避免 magic string" 标准）。
- Spec 轴：遗漏 0、蔓延 0、错误实现 0——#21 正文、评论一三点、评论二均完整实现。

## 人工针对性检查入口

以下为不改动代码即可进行的人工抽查路径，按投入从小到大排列：

1. **CLI help 抽查（纯只读，约 1 分钟）**
   - `uv run paper-radar config --help`、`uv run paper-radar config check --help`、`uv run paper-radar config compile --help`
   - 看点：help 为中文人读文本；执行时不读配置、不开数据库、不创建业务文件（可用 `strace -e trace=open,openat` 或在空目录下运行佐证）。

2. **提交示例的端到端走查（约 5 分钟，写临时目录）**
   - 准备：`TMP=$(mktemp -d)`；`uv run paper-radar db upgrade --database "$TMP/db.sqlite3"`
   - 编译：`uv run paper-radar config compile --settings examples/config/settings-read.yaml --database "$TMP/db.sqlite3"`
   - 只读检查：`uv run paper-radar config check --settings examples/config/settings-read.yaml --database "$TMP/db.sqlite3"`
   - 看点：输出为中文；READ 行恒 `not_ready` 且缺项含 `read_contract`（评论一①的 `read_adapter_prompt_placeholder` 在本示例非占位、不应出现）；boundary 行 ready。重复 compile 第二次应幂等（同事实不产生新快照）。

3. **负路径与错误措辞抽查（约 5 分钟）**
   - 复制示例到临时目录，分别改坏一处：`read.chunking_version: v99`（未知 enum）、加入 `contracts: {reading: ...}`（手写 Schema）、加入 `read.api_key: x`（禁区字段）、把 reading prompt 指向占位文本。
   - 看点：退出码为 2；错误为中文、只含字段路径与受控原因（如 `chunking_version_unsupported`），不回显输入值、无 Traceback、无 SQL 参数。

4. **版本演进与旧材料保留（约 10 分钟）**
   - 在临时副本中新增 `models-read-v2.yaml` / `prompts/reading/v2.md` 并 bump settings 版本，先后 compile v1、v2，再 `config check` 分别指向两个版本。
   - 看点：v2 生成新快照；重新指向 v1 时旧模型/Prompt 内容仍可完整回放（AC1/AC4 核心承诺）；改动已登记版本文件字节会被拒绝。

5. **文档—代码对照（纯阅读）**
   - `docs/contracts/runtime-config.md` 的「Read 配置与分块身份」节、依赖矩阵、必需项表 ↔ `src/paper_radar/config/compile.py:385-405`（缺项来源）与 `read.py`（ChunkingVersion enum）。
   - `docs/contracts/adapter-config.md` 的 `prompt/reading` 路径约定 ↔ `service.py:223-227`。
   - 看点：必需项表与 CLI 实际缺项输出一致；文档明示 chunking 算法无独立字节登记。

6. **自动化入口（既有，不需新写）**
   - 相关测试：`uv run pytest tests/test_config_read*.py -q`（68 项）；架构边界：`tests/test_config_read_architecture.py`。
   - 完整离线验证：`scripts/check-offline`（注意：会在 `verification-runs/` 写入新证据文件，属正常产物）。

无法直接人工验证、只能审查推断的点：AC4 中「最终全部投影/校准基线隔离由 A2-08 验收」在本票分支上无对应行为可查（票文明确不要求）；`read_adapter_prompt_placeholder` 的占位判定依赖 A2-02 已交付的 adapters.reading 语义，本票只接入、不重新定义。
