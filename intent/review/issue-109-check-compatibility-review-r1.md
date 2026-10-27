# Issue #109 兼容性前置检查入口 — 两轴代码审查（r1）

- 日期：2026-10-27
- 固定基点：`HEAD^` = `d5812a4b8b231152422adc1733bcc04504ebfc0a`
- Diff 命令：`git diff HEAD^...HEAD`（三点，对比 merge-base）
- Commit：`8fd310f feat(dev): add offline compatibility check groups (#109)`
- 改动：11 文件，+626 / −6
- Spec 源：GitHub issue #109（`gh issue view 109 --comments`，state OPEN，无 sub-issues，无 blockers）；辅以本次提交自带的 `docs/verification/issue-109-scope-review.md`、`docs/contracts/check-compatibility.md`
- Standards 源：`AGENTS.md`、`docs/agents/{python-conventions,testing,cli-output,documentation,invariants,scope,refactor}.md`、`GLOSSARY.md`、`docs/adr/`（仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`），叠加 Fowler smell 基线
- 方式：两个并行只读 sub-agent，各持 bash；未修改工作区、未创建 commit

---

## Standards

### scripts/check_compatibility.py

**硬违规**

1. `main()` 的 `argparse.ArgumentParser(...)` hunk 未沿用仓库 `_Parser` 子类先例（`scripts/dev_environment.py:270`、`scripts/verification_status.py:372`）。实测 `--help` 打印 `usage:` / `positional arguments:` / `options:`，`--unknown` 打印英文 `error: …` 且无"下一步"，违反 `docs/agents/cli-output.md`（输出默认中文、错误须给原因+下一步），并与本文件 epilog「帮助仅打印中文」及 `docs/agents/testing.md:22` 自相矛盾。
2. `run_checks` / `main` 用裸字符串表达 reason 与结果（`empty_selection`、`empty_module`、`missing_node (not found)`、`passed` / `failed`、`code=1|2`），违反 `docs/agents/python-conventions.md`「用受控 enum / reason 表达状态与原因」，也偏离 `dev_environment.Reason` + `GUIDANCE` 先例。
3. `run_checks` hunk 把选择校验、`os.environ` 改写、`chdir`、打印、pytest 启动混在一处，违反同文件「确定性逻辑与 I/O 分离」。

**判断性 smell**

- Duplicated Code：结果行两处（`run_checks` 与 `main` 的 `finally`）；去重形状三处（`dict.fromkeys` ×2、`{item.nodeid: item}`）；`uv … -c "…run_checks"` 启动串在 `main()` 与 `tests/…::_run_selection` 重复。
- Primitive Obsession / Data Clumps：`tuple[tuple[str, str], …]` 需 `for selection, _ in …` 解包；`"all"` 哨兵散在三处。
- Mysterious Name：`code`（实为退出码）、`_run_selection`（实跑整组选择）。
- Shotgun Surgery：bash 引导块与 `scripts/dev-environment` 重复，改引导需两处同步。

### 其余 hunk

- `scripts/{a8,a9,a10}_scope.py`、`docs/verification/issue-109-scope-review.md`、`README.md`、`docs/agents/testing.md`、`docs/contracts/check-compatibility.md`：哈希六处同步一致，符合 `docs/agents/documentation.md`（契约入 `docs/contracts/` + README），无硬违规。
- `tests/test_check_compatibility.py::test_help_and_unknown_arguments_…`：仅断言中文关键词存在，未断言英文残留（判断性：上条规范缺测试覆盖）。
- `tests/test_cli_import_compatibility.py`：冷进程 + `deny_external_io` 守卫，与 `test_cli_help.py` 同构，未见硬违规（其 env 字典重复属判断性程度较低，不单列）。

---

## Spec

**核对（通过项）**

组合定义确为单一来源（`check_compatibility.py:17` `CHECK_GROUPS`；`--help` 与 `testing.md` 表格均由 `selection_documentation()` 派生）。并集三层去重；实测 acceptance 117 节点、171s。空集合 → 1、缺失模块 → 1、缺失节点 → 4，均非零且给原因。实跑未写 `verification-runs/`、无 `.pytest_cache`。README `e3219390…`、a8 `b8213f36…`、a9 `c1906218…` 与 `sha256sum` 一致，基线 `d5812a4` 正确，`AGENTS.md` 未改。

**(a) 缺失或半成品**

数量/环境/耗时与完整门禁对比仅存于 Git 忽略的 `.scratch/issue-109/`（`testing.md:66` 指引）；issue 只对"修前失败、修后通过"明许忽略归档，版本库内无法核对节省时间。

**(b) 范围蔓延**

README 5 行与新增 `docs/contracts/check-compatibility.md`（issue 只要求 `docs/agents` 导航），README 连带 3 处 scope 重绑；`test_cli_import_compatibility.py` 18 例与 `test_cli_help.py` 部分重叠，cli 组 41 → 59 节点（仍属"确有缺口的公共回归"）。

**(c) 实现偏差**

`--help` 非全中文：实际输出 `-h, --help  show this help message and exit`，与 issue"需带中文 `--help`"、`testing.md:22`"只打印中文帮助"不符（`scripts/verification_status.py:381` 已有 `add_help=False` + 「显示中文帮助并退出」范式）。`check_compatibility.py:154` 硬编码 `-o addopts=…`，与 `pyproject.toml:35` 构成第二处配置源；缺 `.venv` 时 `--help` 直接 exit 1 不出帮助，帮助未提示该前提。

---

## 小结

- Standards：7 项发现（3 硬违规 + 4 判断性 smell）；最严重为 `--help` / 未知参数仍走 argparse 英文默认文案，违反 `docs/agents/cli-output.md` 并自相矛盾于本文件 epilog。
- Spec：4 项发现（1 半成品 + 1 范围蔓延 + 2 实现偏差）；最严重为 `--help` 帮助头仍为英文 `show this help message and exit`，直接与 issue 的"需带中文 `--help`"要求冲突（两轴独立命中同一处，但结论分别归属各轴，未做跨轴排序）。

---

## 实现方逐条核实与处置（#109）

复核基线为 `8fd310f00fcf820614c0b16285c16ce2e0e86296`。上方报告原文保留，
其中 `HEAD^` 是生成报告时的相对引用；核实以原文给出的固定 SHA 为准。
已重新读取 GitHub #109 的最新评论和完整原生关系：无子任务、无 blocker。
以下拆开原文合并列举的建议，避免把判断性 smell 或边界增强一概认作硬违规。

| 编号 / 原报告位置 | 结论 | 核实依据与实际处置 |
| --- | --- | --- |
| S1：硬违规 1，中文帮助/参数错误 | 采纳 | 旧实现确有英文 usage、分组、help 描述及错误文案。新增 `_Parser` 的中文错误映射、中文参数组和显式 help；缺参数、未知组合、未知选项/多余参数均给中文原因及查看帮助的下一步。公开入口回归先在旧实现因 `usage:` 失败，修复后通过。 |
| S2：硬违规 2，原因/结果与退出码 | 部分采纳 | 原因及结果改用 `FailureReason` / `CheckStatus`，移除混合原因 `missing_node (not found)`，缺节点统一为 `missing_node`。不将所有进程退出码改成领域 enum：1/2 是标准控制方退出约定，uv/pytest 的其他非零值须保留整数原值；契约明确该边界。 |
| S3：硬违规 3，纯逻辑与 I/O | 部分采纳 | 原代码已有纯选择函数，I/O 编排中出现校验/打印不单独证明硬违规；但集合计数、环境规则确有分离价值。提取 `_collection_counts`、`_pytest_environment` 等纯计算，`_run_pytest` 集中实际环境应用、cwd 和 pytest 消费。公共执行测试继续验证行为，不直接锁定内部函数。 |
| S4a：Duplicated Code，两个结果行 | 采纳格式复用，保留两层统计 | 共用 `_print_result`。内层耗时测 pytest 执行，外层总耗时含 uv，含义不同，不能删成一条并失去启动失败/总耗时可观测性。 |
| S4b：Duplicated Code，三处去重 | 部分采纳 | 字符串选择并集和执行入口共享 `_ordered_unique`；pytest 对象按完整 nodeid 保留对象的去重仍在 hook 中。两类数据与返回类型不同，不抽取仅为合并行数的泛型框架；重叠模块/参数化节点的实际执行回归继续验证每节点一次。 |
| S4c：Duplicated Code，生产/测试启动串 | 不采纳共享启动串 | `main` 通过 uv 在真实仓库执行命名组合；测试通过独立 Python 进程在合成根执行明确选择，并设置陷阱文件验证无全量兜底。输入和职责不同，不是同一启动协议；共享生产字符串反而会让测试与实现同源。 |
| S5：Primitive Obsession / Data Clumps | 采纳适度具名化 | 清单改为 `TestSelection(selector, reason)`；收集计数用 `SelectionCount`，消除二元组位置解包；`ALL_GROUP` 集中并集名称。未改任何组合成员、顺序或理由，帮助/文档仍从唯一清单派生。 |
| S6：Mysterious Name | 采纳 | `code` 改为 `exit_code`；测试进程辅助函数改为 `_run_selected_checks`，与纯选择明确区分。 |
| S7：Shotgun Surgery，引导块共享 | 不采纳跨脚本重构 | #109 要求优先独立入口、少改冻结支撑文件；仓库没有通用引导模块。现有开发入口的只读引导模式可复用为先例，但不能仅因形似就同步重构 `dev-environment` / 状态查询。此次只修改本入口，并以有/无项目环境的公开命令回归保护。 |
| S8：其余 hunk，scope/文档 | 保留并继续审阅 | README/Contract 修改符合文档维护规则；本轮 README 的帮助前提说明再次按 A8→A9→A10 顺序重审六处哈希。旧登记记录保留并追加本轮台账，不改分母、成员、required、前置或 Frozen Contract。 |
| S9：帮助测试只查中文关键词 | 采纳 | 除原断言外，禁止英文 usage/分组/默认 help 残留；逐项断言中文错误原因和下一步；同时覆盖项目解释器已准备及缺失两种场景，检查文件集合完全不变。 |
| S10：CLI 冷进程守卫/env 字典 | 保留 | 原报告也未指出硬违规。沿用既有 socket/SQLite 拒绝哨兵；测试的独立环境字典保留，不与生产环境净化规则共源。 |
| P1：(a) 实测只在忽略目录 | 采纳可核查性增强，不认定原要求强制入库 | #109 要求记录数量/环境/实测对比，但没有规定这些记录必须跟踪；原始记录确实存在。仍采纳改进，将首次交付的提交、环境、四次实测、节省比例、历史 run 和证明限制写入 `docs/verification/issue-109-feedback-timings.md`，测试导航链接它；不冒充 r1 新结论。 |
| P2a：(b) README/Contract 范围蔓延 | 不采纳 | `docs/agents/documentation.md` 明确要求公共 CLI 同步 Contract 与 README，#109 没有禁止这些文档；只要求详细清单不要复制进根 AGENTS。保留必要导航、契约及最小文档哈希传播。 |
| P2b：(b) 18 例冷进程帮助守卫 | 不采纳删除 | 原 `test_cli_help.py` 只覆盖根与 contracts，fixture/audit 原测试多为已导入服务的同进程 CliRunner，不能替代冷导入守卫。18 例覆盖新增命令及受影响旧命令，正属 #109 允许的“确有缺口的公共回归”，没有扩大产品行为或验收范围。 |
| P3：(c) help 非中文 | 采纳 | 与 S1 同一实际缺陷，两轴分别保留结论，修复和回归共用同一公开入口。 |
| P4：(c) pytest addopts 第二配置源 | 采纳 | 删除入口的 `-o addopts=--strict-config --strict-markers`，保留仓库配置；继续清除外部 `PYTEST_ADDOPTS` 等环境注入。合成仓库配置 `-rA` 的公开执行回归在旧实现缺少 PASSED 摘要而失败，修复后通过，且外部 collect-only/-k 仍被隔离。 |
| P5：(c) 缺 .venv 无帮助/前提未说明 | 采纳能力增强 | 原契约及测试指南已说明需准备项目环境，不能说完全没有文档前提；但无环境帮助符合既有 `dev-environment` 先例且有益。引导优先项目 Python，缺失时用宿主 python3 >=3.12，禁 site 初始化与字节码；两者均不可用则中文失败。帮助、README、Contract 和测试指南均同步该边界。 |

## 本轮验证与证据边界

保留旧历史产物预期、逐字节 transcript、禁网络/SQLite 守卫、正式回执格式与全部
Frozen Contract。没有新依赖、migration、业务语义变化或跨模块引导重构。

三类行为缺陷均在公开入口先复现失败再修复；当前入口模块 12 项测试通过，
全项目 Ruff 格式/规则与 mypy 通过。合成选择仍证明空/缺失拒绝、无全量兜底、
参数化去重、外层回执不变及失败/中断不宣称成功。
本轮 `check-compatibility all` 实际收集并通过 176 项，入口实测 227.753 秒；
独立 scope 审计退出 0、无 affected_groups / issues。

完成门槛仍为本轮材料冻结、提交后执行 `./scripts/check-offline` 返回 0，
并核对可信终态及工作树适用性；不复用初次交付或审查方的历史通过作为本次证明。
本轮组合与完整门禁的原始输出、实际 run_id 和最终结果另存本机忽略归档
`.scratch/issue-109-r1/` 并在最终回复给出，不将运行身份回写跟踪材料造成身份漂移。
未执行真实来源、Pi/模型、PDF/Docling、NAS 或完整阶段 A live 行为。
