# 潜在风险：契约帮助文本与受控版本注册表可能静默漂移

- 代码基线：`HEAD` = `adad0f6 Address contract export review findings (#4)`（实验前后 `git status --short` 均为空）
- 发现来源：用户在 `paper-radar contracts export --help` 看到「声明版本；当前仅支持 v1。」后提问「想导出 v2 是否受限」；排查该问题时定位到本风险
- 审查方式：只读排查 + 一次可逆变异实验；**未修改任何产品代码、测试或文档**，工作区已按字节级还原（见「证据」）
- 离线验证（实际运行）：`uv run --no-sync pytest tests/ -q` → 70 passed（基线 / 变异中 / 还原后各一次）
- 与既有审查的关系：不属于 Issue #4 的验收范围，为后续注册新契约版本时的维护性隐患

## 风险陈述

帮助文本里「当前支持哪些受控选择」是**手写字面量**，而运行时报错里的同一份清单是从受控枚举**动态推导**的。两者事实来源不同，且帮助侧没有任何测试钉住，因此将来注册新契约版本时，会出现「`--help` 说只支持 v1，实际 v2 已可导出」的静默不一致。

当前只有 1 个契约（`boundary`）和 1 个版本（`v1`），所以风险**尚不可观测**；但按 CONTEXT.md「同一版本永久对应同一字节内容，语义变化必须创建新版本」，注册 v2 是既定路径，届时必然兑现。

## 事实来源对照

| 位置 | 内容 | 事实来源 | 是否被测试钉住 |
| --- | --- | --- | --- |
| `src/paper_radar/cli.py:99` | `--version` 帮助「声明版本；当前仅支持 v1。」 | 手写字面量 | **否** |
| `src/paper_radar/cli.py:95` | `--contract` 帮助「受控契约名；当前仅支持 boundary。」 | 手写字面量 | **否** |
| `src/paper_radar/cli.py:57` | `EXPORT_HELP` 散文「只支持 `boundary` 的声明版本 `v1`」 | 手写字面量 | **否** |
| `src/paper_radar/cli.py:39` | `CONTRACTS_HELP` 散文「本 ticket 不提供只读 check 或批处理」 | 手写字面量 | 间接（`test_cli_help.py` 只反向断言 `"run-due" not in stdout`） |
| `src/paper_radar/contracts/export.py:215,224`（消息在 `218,227`） | 报错 `当前支持：{supported_names}` / `{supported_versions}` | 枚举推导 | **是**（`tests/test_contract_cli.py:82-91`） |
| `src/paper_radar/contracts/schema.py:28-36` | `ContractName` / `ContractVersion` | 枚举，唯一事实源 | 是 |
| `README.md:49`、`docs/contracts/frozen-contracts.md:3,50-51` | 「只支持当前已经实现的 `boundary/v1`」、首份快照 SHA-256 | 手写文档 | 否（属 AGENTS.md 要求的人工同步范围，不算缺陷） |

关键不对称：**报错侧被测试钉死，帮助侧完全裸露**。给枚举加上 `V2` 后，`test_contract_cli.py:91`（断言 `无效声明版本；当前支持：v1`）会立即失败并提醒改文案；而帮助里的字面量不会被任何测试发现，会一直宣称「仅支持 v1」。

这也顺带落在 AGENTS.md「优先使用明确的领域类型和受控 enum / reason，避免 magic string」的边缘：受控选择清单这一事实被复制成了字符串。

## 影响

- **触发条件**：注册并实现 `ContractVersion` 的第二个成员（新契约名或新版本）。
- **后果**：`--help` 是仓库明确维护的零副作用自学入口（`tests/test_cli_help.py` 在 `deny_external_io` 下断言其无副作用），用户会据它判断能力边界。漂移后用户会误判能力（正如本次提问所显示的方向：用户以为 `--version` 有额外限制），或反之信任一份已失效的清单。
- **严重度**：低。不影响导出行为、幂等性、路径安全或错误语义；只影响可发现性与文档可信度。
- **修复成本**：单文件级，不需要 ADR（不涉及领域不变量、持久化或 Stage fingerprint）。

## 证据：变异实验（已还原）

为确证「帮助漂移不被任何测试捕获」，做了一次可逆变异：

1. `sha256sum src/paper_radar/cli.py` → `b16f629d14a31f8c7a8285c15dfd3b4dbba8e6e66a75a4d809c043d43befe702`
2. 临时把 `cli.py:95` 改成「当前仅支持 boundaryv9（故意漂移）」、`cli.py:99` 改成「声明版本；当前仅支持 v9（故意漂移）。」
3. `uv run --no-sync pytest tests/ -q` → **70 passed**（帮助文本变成明确错误值，全部测试仍通过）
4. `cp` 备份还原 → `sha256sum -c` OK、`git diff --exit-code` 干净、`tests/` 再跑 **70 passed**

对照：报错侧若把枚举扩到 v2，`tests/test_contract_cli.py:91` 的「无效声明版本；当前支持：v1」断言会立刻失败。**一侧有警报，另一侧没有任何警报**。

## 最小修复建议（未实施）

- **方案 A（推荐）**：帮助文本改为从受控枚举派生，与 `export.py:215,224` 共用同一个清单渲染。例如在 `schema.py` 提供 `支持清单渲染`，生成端与帮助端共同消费。`--help` 仍然只读枚举、无 I/O，满足零副作用约束。
- **方案 B（成本最低）**：在 `tests/test_cli_help.py` 增加一致性断言——帮助 stdout 必须覆盖 `ContractName` 与 `ContractVersion` 的每个已注册值。它把「帮助必须与注册表一致」变成可执行规格，但字面量仍需人工维护。
- **方案 C（不推荐）**：删掉帮助里的具体值，只说「无效值会列出当前支持清单」。会牺牲零副作用的自学能力，与 AGENTS.md「错误信息应说明可操作的具体原因」的精神相悖。

建议 **A + B 同时做**：A 消除重复事实源，B 防止未来重新引入同类字面量。

## 范围提示

若新增 `v2` 属于边界输出契约的语义变化，则按 ADR-0020 / AGENTS.md 属于「可能改变 Screening 语义的修改」，须遵循 calibration change workflow，且**不得由实施者自行判定为 minor 或 major**。本文件只记录帮助文本的漂移风险，不对 v2 本身的可行性与必要性作判断。

## 验证与限制

实际运行：

- `uv run --no-sync paper-radar contracts --help` 与 `contracts export --help`：帮助正常，原文即上表所列
- `uv run --no-sync paper-radar contracts export --contract boundary --version v2 --target /tmp/pr-v2`：退出码 2，`invalid_selection`，目标目录未被创建
- `uv run --no-sync pytest tests/ -q`：70 passed（三次）
- 变异实验及字节级还原（见上）

未运行与已知限制：

- 未运行 `./scripts/check-offline`（本文件不改动代码）
- 未运行任何 live source 验收
- 变异实验只针对 `cli.py` 内字面量；`README.md` 与 `docs/contracts/frozen-contracts.md` 的同类表述属人工维护范围，未纳入本风险（文档本就不应由代码派生）
- 未在 CI 或其他 Python 版本上复现变异实验

## 实施代理复核与处理

结论：风险成立，方案 A+B 合理并已采纳。虽然当前 `boundary/v1` 没有可观察错误，
但帮助是零副作用的能力发现入口；新增已实现契约或版本时，手写清单确实可能与运行
时注册表静默漂移。此修复只统一既有选择的展示来源，没有新增 `v2`、改变冻结
Schema 或触发 calibration change workflow。

具体处理：

- 从已实现契约注册表 `_CONTRACTS` 确定性生成契约名和声明版本清单；没有建立新的
  手写清单，也不访问网络、数据库或模型。
- `contracts` 组帮助、`contracts export` 说明、`--contract` / `--version` 选项帮助，
  以及无效选择错误共同消费同一清单渲染结果。
- 示例仍选择当前已实现的 `BoundaryOutput v1`，但通过受控 enum 取值，不再在帮助
  字符串中重复 `boundary` / `v1` 字面量。
- 新增真实安装入口测试，从 `ContractName` / `ContractVersion` 动态构造期望，断言
  `contracts export --help` 覆盖每个已注册选择；测试继续在拒绝网络和 SQLite 的
  `sitecustomize` 下运行并验证无文件副作用。

处理后实际运行 `./scripts/check-offline`：lockfile、Ruff 格式、Ruff 静态检查、
mypy 和全部 71 项离线测试均通过；未运行 live source 验收。
