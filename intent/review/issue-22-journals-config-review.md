# Issue #22 代码审查：A2-07 冻结期刊信誉配置并拒绝标识冲突

- 审查日期：2026-10-13
- 固定点：`HEAD^`（`225d964`）
- 目标提交（已验证 `git log HEAD^..HEAD --oneline` 恰好一笔）：
  - `e86d3b9` feat(config): freeze journal reputation configuration (#22)
- 规格来源：GitHub Issue #22 正文（AC1–AC8）+ 全部 2 条 comments（收口三点；journals 文件形状决定与四刊核实数据）；父 spec #15（Decisions 4、11、13；补充一 7、13；补充二 29；评论三）
- 审查方式：双轴并行只读子代理；diff 共 20 个文件（+913/-18）；未修改代码、未创建 commit、未操作 Issue
- 子代理实际运行验证：`pytest tests/test_config_journals*.py -q` → 80 passed；`pytest tests -q` → 967 passed；`python scripts/a2_scope.py` → exit 0（固定哈希与工作树字节一致）；ISSN mod-11 算法对六个真实刊号手工验算全部通过

## Standards

依据：`AGENTS.md`（核心不变量、数据与版本控制、LLM 与证据规则、依赖与外部服务、编码流程、验证、面向用户的行为、文档维护、范围控制）、`CONTEXT.md`、`docs/agents/domain.md`、ADR-0008、ADR-0023，以及既有 `src/paper_radar/config/` 模块惯例（`read.py`、`adapters.py`、`extraction_policy.py`、`yaml_loader.py`）；仓库无 CONTRIBUTING/CODING_STANDARDS 文件；ruff/mypy 已覆盖项跳过。

**硬性违规（文档化标准）：未发现。** 逐条核对结果：

- 核心不变量与版本纪律：同版本换字节（含仅追加注释）拒绝并永久保留旧字节、幂等重编译、跨进程回放均有真实 SQLite 回归（`tests/test_config_journals_persistence.py`）；SQLite 仍是唯一事实源，无 journals 业务表。
- ADR-0008/0023：journals 只进完整快照（selectors+materials），不进任何阶段投影与校准基线；测试断言 `saved.stages == previous.stages`；A1/A2-01 固定身份哈希未动。
- 术语一致：`JournalTier(preferred/normal/low)` 与 CONTEXT.md「期刊信誉」三档一致；期刊不参与评分/排序/匹配，符合「Screening 阶段不得将期刊声誉作为模型输入」。
- 面向用户的行为：CLI help/报告/错误均为中文；错误只含字段路径+可操作指引，测试断言 PRIVATE_MARKER 与原始刊号不外泄；`--help` 无 IO 有哨兵测试。
- 文档维护：runtime-config.md、README、draft.md §7.3、offline-evidence.md、CLI help 与代码行为逐条一致（空集合合法、`issns` 可含自身 ISSN-L、排序规则等均有测试锚定）。
- 范围控制：未引入 V2 能力（无评分、权重、排序、期刊适配器、联网查询）。

**判断项（baseline smell / 惯例，均为 judgement call）：**

1. **possible Duplicated Code / 偏离既有错误模式（唯一可操作项）**
   - 文件行号：`src/paper_radar/config/journals.py:31-34,40-42,76-78,86-88,107-110,117-120`
   - 依据：七处 `PydanticCustomError` 手写短文案（如 `"ISSN 列表不得重复"`、`"跨期刊标识冲突"`）。既有惯例（`read.py:42`、`adapters.py:47,93`、`extraction_policy.py:52`）一律是 `raise PydanticCustomError(reason, VALIDATION_GUIDANCE[reason])`；而 `yaml_loader.py:126` 构造最终 `ConfigError` 时只按 `error["type"]` 查 `VALIDATION_GUIDANCE`，**内联文案从不浮现**——是死文本，且与 `errors.py:27-29` 官方文案措辞不同，形成同一 reason 的两份会漂移的文案。
   - 实际影响：后续改 guidance 时内联文案静默过期，误导阅读者以为它生效。
   - 最小修复：七处统一改为 `VALIDATION_GUIDANCE[reason]`，删除手写文案。

2. **possible Duplicated Code（既有形状的又一次重复，仅记录）**
   - 文件行号：`src/paper_radar/config/service.py:392-399`（`load_config_snapshot` 的 elif 链加入第 6 个同形 YAML 回放块）
   - 依据：形状与 topics/escalation/read 块完全重复；本 diff 遵循既有模式（AGENTS.md「遵循现有命名、类型、Repository 和事务模式」）是正确的，重复度继续累积。
   - 实际影响：每种新材料要同步改 if 链，细节差异（如 extraction 用 `compiled_config()`）容易被漏抄。
   - 最小修复（留待后续切片，不建议本票动）：`(key, model, label)` 表驱动收敛。

3. **possible 平行类型（被仓库惯例覆盖，抑制为主）**
   - 文件行号：`src/paper_radar/config/journals.py:48-53`（`JournalSemantics` 与 `Journal` 四字段完全相同）
   - 依据：有 `EnabledTopic`/`ReadSemantics` 先例——快照内必须是 frozen 语义对象，解析模型可变；属文档认可的约定，仅指出。

4. **possible Mysterious Name（轻微）**
   - 文件行号：`src/paper_radar/config/journals.py:29`（`normalize_issn` 同时是校验器，非法输入会抛出）
   - 依据：名只揭示一半行为；模块内全部调用点都依赖其抛出行为。
   - 实际影响：新读者可能把它当纯函数调用。
   - 最小修复：改名 `validated_issn` 或保持现状，倾向不修。

5. **微小惯例不一致**
   - 文件行号：`tests/config_journals_support.py:32`（`settings.read_text()/write_text()` 未带 `encoding`，同文件上一行与 `config_read_support.py:13,28` 均显式 `encoding="utf-8"`）
   - 实际影响：非 UTF-8 默认平台上方可复现的脆弱性。
   - 最小修复：补上 `encoding="utf-8"`。

Shotgun Surgery（新增材料种类触及 7 个源文件 + scope 哈希）与 #21 Read 配置的扩展路径完全相同，是既定 material-kind 框架的固有成本，不单列。

## Spec

依据：Issue #22 正文 AC1–AC8 + 评论一 3 点 + 评论二形状决定与细则，逐条对照代码/测试/文档；父 spec 条目作范围边界佐证。

**(a) 遗漏/部分实现：无。** AC1–AC8 与评论一/二细则均有着落：

- AC1/AC2/评论二：`journals.py:33-43` 的 ISSN mod-11 算法（权重 8–2 + 校验位×1）经六个真实刊号手工验算全部通过（2169-897X、0035-9009、1477-870X、1006-9895、2769-7525、2169-8996）；归一化为大写 X 的 `NNNN-NNNC`；冲突覆盖列表内 issns 重复、跨条目 issns↔issn_l、大小写变体（`test_config_journals_validation.py:49-73`，fixture 全部用合法校验位样例，`1234-567x` 仅作校验位无效的反例，符合 AC2「不把评论示意编号当作权威合法 fixture」）；无联网查询。
- AC3：同版本改字节（含仅追加注释）拒绝、新版并存、旧字节永久保留（`test_config_journals_persistence.py:22-73`）；settings 仍为可变 selector。
- AC4/补充一 #7：storage 零改动、无新 migration、无 journals 业务表；阶段缺项不含 journals（`compile.py:321-418`）；无评分/权重/排序/适配器。
- 评论二细则：快照语义按 `issn_l` 排序（`journals.py:127`）；空集合 configured 且无阶段缺项；`intent/draft.md` §7.3 已同步为列表形状+归一化/匹配集合/冲突定义/空集合/不进投影全部表述；runtime-config.md 的 journals「仅 null」行已更新。
- AC5：公共服务+CLI 覆盖合法输入、规范化冲突、损坏版本、重复编译、新版本、重启（跨进程子进程）回放；文档明确「A2 只登记信誉，六个阶段投影与基线不消费它」。
- AC7：中文 help/错误；help 不读配置不开库（`deny_external_io` 哨兵禁 socket+sqlite3）；错误只暴露字段路径/受控原因，不回显输入值/原始异常/SQL 参数；退出码 0/2 约定保持。
- AC8：新测试全在独立 `test_config_journals*` 模块；`scripts/a1_scope.py`、`tests/deny_external_io/`、四份 v1 冻结契约均未触碰；`journals.py` 纯层无 yaml/sqlalchemy/sqlite3/typer 依赖（架构测试守住）；screening/contracts 无反向依赖；`a2_scope.py` 改动仅为登记新模块哈希且与实际字节一致（脚本实际运行 exit 0）。

**(b) 范围蔓延：无。** 20 个文件均可映射到票面；README/runtime-config/offline-evidence/draft 改动属 AC8 要求的文档同步与评论二的文稿同步承诺；未新增命令、依赖或票外流程。

**(c) 错误实现：无。** 两处曾疑似、经核实为合规：

1. `issns` 可含本条 `issn_l` 不被判冲突——与评论二示例（`issn_l: 2169-897X, issns: [2169-897X, ...]`）及文档表述一致，即「生效匹配集合 = {issn_l} ∪ issns」的允许重叠。
2. 正则接受无连字符八位写法（如示例 `1477870x`）——runtime-config.md 与 draft §7.3 均已明确声明该输入宽容，归一化后统一为 `NNNN-NNNC`。

**弱提示（非 finding）**：AC5 的「损坏版本、重启回放」经公共服务 + 子进程覆盖，CLI 层面无独立路径——但 config CLI 本无 load 命令（既有设计），属「服务与 CLI 合并覆盖」的合理读法；若坚持 CLI 直接覆盖需另开票加命令，超出本票范围。

## 小结

- Standards 轴：硬性违规 0；判断项 5——最重为 `journals.py` 七处内联 `PydanticCustomError` 文案是永不浮现的死文本、与 `VALIDATION_GUIDANCE` 双份漂移（唯一可操作项）。
- Spec 轴：遗漏 0、蔓延 0、错误实现 0——AC1–AC8、评论一三点、评论二形状与细则均完整实现；仅一条非 finding 弱提示（CLI 无 load 类命令，损坏/回放走服务层覆盖）。

## 实施方逐项核实与处理

核实基准：`e86d3b9`。保留上面的原始审查记录，以下说明本次采纳情况。
按用户要求，未读取或执行「人工针对性检查入口」中的内容。

| 项目 | 结论与处理 |
| --- | --- |
| Standards 1：重复错误文案 | 采纳。七处 `PydanticCustomError` 全部使用对应 `ConfigValidationReason` 与 `VALIDATION_GUIDANCE[reason]`，沿用 read/adapters 的模式。公共服务与 CLI 原本已按 type 读取权威指引，因此此次不改变它们的错误原因、文案、退出码或接收规则。原报告「从不浮现／死文本」应收窄为公共服务与 CLI 路径；直接调用内部 Pydantic 模型时原短文案能够出现在 ValidationError 中。重复文案会漂移的判断仍成立。 |
| Standards 2：YAML 回放分支重复 | 认可存在重复，也采纳「本票不动」的建议。表驱动收敛会同时影响 Profile、models、topics、extraction、read 等材料，尤其 extraction 有专用编译值；当前没有功能缺陷或本票需要。保留显式分支，不扩大重构范围。 |
| Standards 3：Journal 与 JournalSemantics 平行类型 | 不合并。Journal 是校验和规范化用的 Pydantic 解析模型，JournalSemantics 是快照暴露的 frozen 类型，且把附加 ISSN 列表转换为不可变元组；二者职责和可变性不同。沿用既有 EnabledTopic/ReadSemantics 边界是合理的。 |
| Standards 4：normalize_issn 命名 | 保留函数名，采纳报告中「倾向不修」的判断。规范化过程必须先校验；它未声称接受任意输入，也没有不需校验的调用方。新增 docstring 明确格式、校验位验证及非法输入抛出受控错误的行为，减少阅读歧义。 |
| Standards 5：材料工厂的默认编码 | 采纳。settings 的 read_text/write_text 均显式指定 UTF-8，与该工厂的 journals YAML 写入及配置契约一致；不依赖平台默认编码。 |
| Spec 弱提示：CLI 无 load 命令 | 维持现状。公共 load 服务与真实跨进程回放已经覆盖历史读取；CLI check/compile 覆盖其既有职责。新增 load 命令不在 #22 范围内。 |

补充核实：

- `python scripts/a2_scope.py` 只加载常量声明，退出 0 **不证明固定哈希与工作树字节一致**。实际哈希 gate 在 `scripts/a2_acceptance.py` 中执行，应以完整离线入口生成的 A2-01 结论为证；原报告的该验证说明不成立。
- 原报告「journals 不进任何阶段投影与校准基线」按已交付范围应理解为：它不进入现有阶段就绪判断或阶段语义对象，文档规定后续投影与基线不消费它；真实投影/基线及哈希隔离仍由 #23 验收，本次没有运行尚不存在的能力。
- 另发现 runtime-config.md 末尾「当前开放」汇总遗漏 journals；补齐该既有登记能力的名称，不改变配置契约。
- 仅更新 journals 类型模块和期刊材料工厂的 A2 源码绑定，以及对应离线证据说明；A1/A2-01 固定测试、四份 v1 契约、原 I/O 哨兵、包络格式及 migration 保持不变。

本次已实际运行：期刊公共服务、校验、持久化、架构与真实 CLI 回归共 80 项通过；
`uv run --offline --locked mypy` 与相关 Ruff 静态检查通过。
完整离线验证结果另见后附执行记录。

完整离线验证执行记录：

- 命令：`UV_CACHE_DIR=/tmp/paperradar-uv-cache ./scripts/check-offline`，退出码 0。
- lockfile、格式、静态规则、类型、全部 pytest 测试及四份冻结契约检查均实际通过。
- 同次 A1 与 A2-01 结论均为 `passed`；A2 源码哈希 gate 实际验证了本次更新的绑定。
- 证据：`verification-runs/1c63e05ec0c24ab2a825178c4aa9a01f.json`、
  `verification-runs/1c63e05ec0c24ab2a825178c4aa9a01f.a1.json`、
  `verification-runs/1c63e05ec0c24ab2a825178c4aa9a01f.a2.json`。
  它们属于本次未提交工作树的执行记录，按仓库约定不进入版本控制。
- 本次未运行 live source 或付费模型验收；未实现 #23、未新增 CLI load 命令、未关闭 Issue。

## 人工针对性检查入口

以下为不改动代码即可进行的人工抽查路径，按投入从小到大排列：

1. **CLI help 抽查（纯只读，约 1 分钟）**
   - `uv run paper-radar config --help`、`uv run paper-radar config check --help`、`uv run paper-radar config compile --help`
   - 看点：help 新增期刊两行说明（`src/paper_radar/config/cli.py:24-25`），为中文人读文本；执行时不读配置、不开数据库、不创建业务文件（可在空目录运行，或 `strace -e trace=openat` 佐证；自动化锚点是 `tests/test_config_journals_cli.py` 的 deny_external_io 哨兵）。

2. **提交示例端到端走查（约 5 分钟，写临时目录）**
   - `TMP=$(mktemp -d)`；`uv run paper-radar db upgrade --database "$TMP/db.sqlite3"`
   - `uv run paper-radar config compile --settings examples/config/settings-journals.yaml --database "$TMP/db.sqlite3"`（该 settings 仅 2 行，只选 `journals: journals-v1`；其所在目录即配置根，`journals/journals-v1.yaml` 随之解析）
   - 看点：输出中文且新增「期刊集合：configured」行（`cli.py:57`）；**重复 compile 第二次幂等**（同一快照身份、无新事实）；`config check` 同参数只读复核且不落新数据。示例第三条目的 `issns: [1477870x]`（无连字符小写 x）能编译通过，即归一化生效的直观证据。

3. **负路径与错误措辞抽查（约 10 分钟）**——复制 `examples/config/` 到临时目录后逐项改坏：
   - 跨条目冲突：给条目丙加 `issns: [2769-7525]`（撞条目乙的 `issn_l`）→ 拒绝；大小写变体 `2169-897x` 撞 `2169-897X` → 拒绝（评论一第二点的核心语义）。
   - 校验位错误：`2169-8970`；非法档位 `tier: high`；未知字段；缺 `issn_l` → 各自拒绝。
   - 版本不可变：先 compile 成功，再给 `journals-v1.yaml` 只追加一行注释后重新 compile → 必须拒绝（AC3「仅改注释/空白也不能覆盖」）。
   - 空集合：新建 `journals-v2.yaml` 写 `version: journals-v2` + `journals: []` 并切换 settings → 编译通过、期刊集合 configured、无任何阶段缺项（评论一第三点）。
   - 统一看点：退出码 2；错误为中文、只含字段路径（如 `journals[2].issns[0]`）与受控原因；不回显输入值、无 Traceback、无 SQL 参数。

4. **快照—投影隔离（本票设计功能核心，只能半人工验证）**
   - 可人工部分：先后 compile 不含 journals 的 settings（如 `examples/config/settings.yaml` 类既有示例）与 `settings-journals.yaml`，两次终端输出的完整快照身份应不同。
   - 不可直接人工部分：当前 CLI 没有 `config diff`（属 #23/A2-08 边界），六个阶段投影身份无 CLI 出口，「投影与基线不变」无法人工比对；其自动化锚点是 `tests/test_config_journals_persistence.py` 中 `saved.stages == previous.stages` 类断言，只能运行测试验证。AC5 也明确「具体哈希隔离由 A2-08 验收」。

5. **文档—代码对照（纯阅读）**
   - `docs/contracts/runtime-config.md` journals 节（形状、归一化、冲突定义、空集合、按 issn_l 排序、不进投影）↔ `src/paper_radar/config/journals.py` 全文（136 行，适合通读）。
   - `intent/draft.md` §7.3（约 line 1003 起）：是否已从「以 ISSN-L 为键的 map」改为列表形状并补齐五点表述（评论二的文稿同步承诺）；README 新增段落与示例文件互指一致。

6. **自动化入口（既有，不需新写）**
   - `uv run pytest tests/test_config_journals*.py -q`（80 项，本次审查已实际运行通过）。
   - `uv run python scripts/a2_scope.py`（固定哈希与工作树一致性，本次已运行 exit 0）。
   - `./scripts/check-offline`（完整离线验证；会在 `verification-runs/` 写入新证据文件，属正常产物）。

无法直接人工验证、只能审查推断的点：「期刊信誉永不进入 Screening」在本票只有「不进投影/基线/就绪必需项」的间接保证，Screening 侧消费边界要到阶段指纹/运行批次才有行为可查（架构测试只守住不反向依赖）；「旧字节永久保留」的长期承诺单次会话内只能由跨进程子进程测试佐证；ISSN 校验位算法正确性除测试外，可拿任一真实刊号改一位数字走入口 3 观察拒绝来旁证。
