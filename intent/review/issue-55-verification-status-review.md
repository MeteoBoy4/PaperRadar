# Code Review: issue #55 verification-status（HEAD~2…HEAD）

- 基准点：`ac8934d3989af1509f2862a2b390b9fd3f37d981`（HEAD~2）
- Diff 命令：`git diff HEAD~2...HEAD`
- 提交：
  - `eb92acf fix: reject unsupported verification formats and unreadable evidence (#55)`
  - `e465d3b feat: query verified offline run status (#55)`
- 改动规模：19 个文件，+1078/-43。新增 `scripts/verification_status.py`、`scripts/verification-status`、`docs/contracts/verification-status.md`、`tests/test_verification_status.py`；修改 `scripts/verification_run.py`、`scripts/check-offline`、a2/a2_full/a3/a4/a5 scope 脚本、`tests/fixtures/verification_transcripts.json`、`README.md`、`docs/verification/offline-evidence.md` 等。
- Spec 来源：GitHub issue #55 正文 + 2026-10-20 范围调整评论（两个已复现缺陷拆至 #61；本票仅交付只读 `verification-status` 命令 + 控制方终态记录，其余验收条件不变；状态脚本不登记进任何验收 scope）。
- Standards 来源：`AGENTS.md`、`docs/agents/python-conventions.md`、`testing.md`、`cli-output.md`、`documentation.md`、`invariants.md`，外加 Fowler smell 基线。
- 审查方式：Standards 与 Spec 两个独立只读子代理并行审查，本文件为聚合结果，两个维度不混合排序。

## Standards

**(a) 文档化标准对照：未发现硬性违规。**

- `docs/agents/documentation.md`：新增公共 CLI/持久化终态记录，已同步 `docs/contracts/verification-status.md`、`README.md`、`docs/verification/offline-evidence.md`、`scripts/check-offline --help`。GLOSSARY.md 仅收业务领域词汇，验证工具词汇从未进入，不新增一致。
- `docs/agents/testing.md`：负例均断言受控字段对 `(status, reason)` 并附 SECRET 脱敏与字节不变断言（`tests/test_verification_status.py:108-148`）；全部离线、tmp_path+fixture；fix 提交 eb92acf 对应回归测试已在。
- `docs/agents/cli-output.md`：中文输出、`--help` 纯本地、退出码语义均有契约。`_Parser.error` 丢弃 argparse 具体 message 属"错误信息未写明具体原因"，但契约明确"不回显未知参数"（脱敏），文档优先，压制。
- `docs/agents/invariants.md`：终态经 `publish_conclusion` 原子只追加，不覆盖旧证据，符合"历史只追加"；读者自维护历史格式表、不导入生产 registry，版本语义冻结声明完整。
- `docs/agents/python-conventions.md`：无新依赖；确定性解析与 I/O 分离尚可。

**(b) 基线 smell（均为判断题）：**

1. **死参数/遮蔽**（近 Mysterious Name）：`scripts/verification_status.py` `_terminal(directory, run_id, terminal, evidence)` 的 `evidence` 形参从未被读取，即被函数内 `evidence = bound(".json", …)` 遮蔽。修法：删除该形参，调用点同步去掉。
2. **Speculative Generality**：`_version(value, expected=1)` 的 `expected` 在全部 3 个调用点均用默认值。修法：内联常量 1，待真实需求出现再参数化。
3. **Primitive Obsession（受控 vocabulary 未 enum 化）**：`Status`/`Reason` 用了 StrEnum，但同为输出受控词表的 `phase`（4 值）与 `applicability`（3 值）是裸字符串字面量，散落在 report 字面量、`PHASE_ZH` 键与契约三处；与 python-conventions"受控 enum 表达状态"有张力。修法：同样 StrEnum 化。
4. **Duplicated Code（轻微）**：组后缀正则 `\.[a-z0-9-]+\.json` 同时出现在 `scripts/verification_run.py`（新增校验）与 `verification_status.py`；`Path(__file__).resolve().parents[1]` 在 `main()` 重复。可提共享常量。
5. 已核实非问题：测试里 `writer.write_text(writer.read_text()+…)` 依赖 `fake_checks` 预建的 `write_receipt.py`（`tests/a2_full_support.py:86`），非死代码。

总体：标准合规良好，仅建议处理 1–3 三个判断级改进点。

## Spec

**总体结论**：范围与调整评论一致——仅交付只读 `verification-status` + 控制方终态记录（`verification_run.py:112` 在全部组发布后最后写入组后缀清单与退出码）；#61 的环境变量隔离/进程组修复未在此重复实现，正确。状态脚本及其测试未登记进任何 scope（grep 确认），符合评论第 3 点「状态命令脚本本身不要登记进任何验收 scope」。HEAD 已有终态记录 `2f8783b0…terminal.json`（exit_code 0、commit 匹配 eb92acf），佐证 check-offline 通过（验收条件 8）。

**(a) 缺失或部分实现：**

- 未发现整条件缺失。验收条件 2（屏障复现两种场景、不靠固定 sleep）由 `tests/test_verification_status.py:377` 的 FIFO 屏障覆盖两阶段；条件 3 的失配/坏 JSON/未知格式/发布失败等均有参数化用例；条件 5 的「未来新增组不会被静默漏掉」有 `test_future_group_is_never_silently_skipped`。
- 轻微偏差：条件 6 要求「`--json` 与中文文本输出表达相同事实」，文本输出未展示 JSON 的 `format_version`，且 `tests` 以 Python dict repr 打印（`verification_status.py:388`）。事实层面等价，属可接受的宽严度。

**(b) Scope creep：**

- 未发现。`check-offline` 帮助措辞、transcripts、文件数断言（8→9）均为评论预告的「新增输出文件会牵动…」项；README/契约文档是条件 1 的文档要求；`run_verification` 的后缀登记校验是终态记录完整性所必需。

**(c) 实现方式存疑：**

1. **历史 checks 校验依赖当前注册表**：`verification_status.py:100` 用当前 `default_checks()` 的 ID 列表比对历史证据；固定计划一旦调整，全部历史运行退化为 `invalid_document`。组维度已用终态冻结清单满足条件 5「历史运行的登记范围也不被当前注册表改写」，checks 维度未做同等隔离（虽是 fail-safe 方向且文档称「固定六检查」）。
2. 中断但缺 `finished_at` 的极端证据（写证据途中强杀）报 `unconfirmed/checking` 而非 `interrupted`；文档已声明「不区分」，可接受但值得知晓。

## 小结

- Standards：0 处硬性违规，5 条判断级 smell（建议处理前 3 条）；最严重为 `_terminal()` 的死参数 `evidence`（判断级）。
- Spec：0 条缺失、0 条 scope creep，2 条实现方式存疑；最严重为历史 checks 校验依赖当前注册表（fail-safe 方向，但组/checks 两个维度的历史隔离不对称）。

## 逐条核实与处理（2026-10-21）

关联 [Issue #55](https://github.com/MeteoBoy4/PaperRadar/issues/55)。本节是修复者的核实结果，
上文保留为 `eb92acf` 时的原始审查记录，原行号不代表修复后的行号。
本次改动基点为 `eb92acf`；范围仍按
[范围调整评论](https://github.com/MeteoBoy4/PaperRadar/issues/55#issuecomment-6285298982)，
不重复 #61 的环境隔离与进程组修复。

| 原报告条目 | 判断 | 处理与理由 |
| --- | --- | --- |
| Standards (a) 文档、测试、中文/脱敏、历史只追加及编码约定 | 核实原结论成立 | 未发现需新增修复的硬性违规；状态查询和测试仍不加入验收 scope，旧记录字节不改写，无数据库/业务配置变化。 |
| Standards (b) 1：`_terminal` 的 `evidence` 死参数 | 采纳 | 实参确实在读取前被 `bound()` 返回值遮蔽。删除形参与调用实参；仍仅用经本次哈希绑定读取的证据判断终态。 |
| Standards (b) 2：`_version(expected=1)` 未使用参数化 | 采纳 | 所有调用均校验格式 1，去掉 `expected`，保留严格整数校验（拒绝布尔值冒充 1）。 |
| Standards (b) 3：`phase`、`applicability` 裸字符串 | 采纳 | 新增 `Phase`、`Applicability` 两个 `StrEnum`，报告与阶段中文映射统一使用枚举；对外字符串和格式版本不变。 |
| Standards (b) 4：`main()` 重复求仓库根 | 采纳 | 在 `main()` 计算一次 `root`，复用于默认运行目录与查询。 |
| Standards (b) 4：为两处后缀正则提取共享模块/常量 | 暂不采纳 | 两处是生产登记和只读材料读取各自的边界校验，一段短协议文法不足以支持新增跨模块抽象。仅为消除此处重复去改生产组织模块，会扩大验收 scope 绑定与模块耦合；保留已有两处校验及受控失败行为。 |
| Standards (b) 5：`write_receipt.py` 非死代码 | 核实原结论成立 | 文件由 `fake_checks` 预建，FIFO 回归在其后追加屏障代码，保留。原小结的“5 条 smell”应理解为 4 条建议加 1 条已排除问题，不能将第 5 条计为待修复发现。 |
| Spec (a)：范围/验收完整性 | 核实原结论成立 | 两段 FIFO 屏障、坏材料、发布失败、可选组和只读保证继续由既有测试覆盖；本次只修复历史查询并做同模块清理。 |
| Spec (a) 轻微偏差：文本无 `format_version`、测试计数字典展示 | 部分采纳 | 中文文本补充输出格式版本；计数字典的键、数值与 JSON 已表达相同事实，保留现有展示，不将渲染风格认定为规格缺陷。同步明确契约。 |
| Spec (b)：无 scope creep | 核实原结论成立 | 代码改动限 `verification_status.py` 与其测试；补充 README、状态契约和本报告，不修改生产验收脚本或登记。 |
| Spec (c) 1：历史 `checks` 依赖当前 `default_checks()` | 采纳，已复现的兼容性缺陷 | 真实 CLI 回归中仅将当前计划的 `lockfile` 改名，未改历史材料，原实现即返回 `failed/invalid_document`。读者改按格式 1 已发布的六项有序检查清单校验和计总数，不再调用当前执行计划。对未知/缺项/乱序计划继续拒绝；以后不同计划须显式版本化并保留旧定义，不修改旧记录。 |
| Spec (c) 2：强杀、缺 `finished_at` 时显示 `unconfirmed/checking` | 不作修复，保留契约行为 | 只读材料不能区分进程仍在运行、强杀和未写完。没有控制方观察到的中断事实时，报告 `interrupted` 会捏造确定性；保持“终态未证实”，不按 PID、mtime 或回执猜测。 |

### 复现与验证记录

- 修复前：`uv run --offline --locked pytest tests/test_verification_status.py::test_historical_checks_do_not_follow_current_execution_plan -q`，1 failed；实际返回 `failed/invalid_document`，期望 `passed/verified`。测试只修改隔离仓库中的当前计划名称，不修改历史证据字节。
- 修复后：同一命令 1 passed，历史结果继续通过，当前适用性为 `different`，检查计数仍为 6，查询前后证据字节一致。
- 增加格式 1 的缺项、乱序和新增未知检查三个负例，均要求受控返回 `failed/invalid_document`，防止为历史兼容放宽通过判据。
- 状态查询测试：`uv run --offline --locked pytest tests/test_verification_status.py -q`，35 passed。
- 静态检查：`uv run --offline --locked ruff check scripts tests` 和 `uv run --offline --locked mypy` 均通过。
- Standards 独立复核：0 处硬性违规、0 项新增待处理 smell；认可各项处置及报告表述。
- Spec 独立复核：0 项未解决；确认历史查询隔离、保守拒绝、输出词表与范围边界。
- 完整离线门禁：`./scripts/check-offline` 实际退出码 0；lockfile、格式、静态规则、类型、全部 pytest、冻结契约均通过，A1、A2-01、完整 A2、A3、A4、A5 结论均为 `passed`。
- 同次运行 `d2b251fda10243e38357f1f51c116acb`；`./scripts/verification-status d2b251fda10243e38357f1f51c116acb --json` 返回 `passed/verified`、`phase=finished`、`exit_code=0`。查询发生在结果补记前，`applicability=same`。门禁覆盖提交前的修复工作树；本段为运行结束后补记，不回写历史验证材料。
- 本次未运行 live 来源、Pi/RPC 或模型验收。未来新增检查计划须明确升级记录协议和历史解析表；缺乏中断事实的运行仍保持“终态未证实”。
