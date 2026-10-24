# 阶段 A9 双轴审查 r1（#92 / #93–#99）

- 固定点：`main` = `04ed7073172fdf6db9427dd68670b169140c2748`；merge-base 相同。
- 被审：`integration/issue-92-read-contract`，HEAD = `4d559c495b5158d5bd079e672a8fde6f540ba277`。
- diff：`git diff main...HEAD`（三点）＝ 89 files，+9437/−204；`git log main..HEAD --oneline` 共 22 个提交。
- 提交映射（新→旧）：`4d559c4`/`c446011` 门禁修复，`3da9170`/`c2200c7` 审查修复，`9e44d35`/`26ed341` → #99，`a719943`/`676aaa5` → #98，`9a67733`/`49dbca6`/`f6ef808`/`e76267d` → #95，`2939463`/`e285058` → #96，`c2d38b7`/`a5e6ad4`/`e926cec`/`1dbd3da` → #94，`4ef5288`/`592cd9c` → #97，`24a8741`/`192a51f` → #93。
- 两轴由独立只读 subagent 并行执行，均被明确授予 Bash 权限并实际使用；提示均逐字附加 `~/Prompts/code-review-enhancement.md`，单轴上限 800 词。本报告按轴保留原发现顺序，不跨轴合并或重排。
- 审查开始时工作树干净。写入本报告前，代码与 staged diff 仍为空；出现一个外部审查的未跟踪 `issue-92-a9-read-contract-review-r2.md`，其结论未纳入本报告，文件保持不变。本任务不修改代码、不创建 commit。

## 工具、来源与完成状态

**Standards**：仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`。读取 `AGENTS.md`、`docs/agents/{python-conventions,testing,invariants,llm-evidence,cli-output,documentation,domain,refactor,scope}.md`、`GLOSSARY.md`、相关 ADR/Contract、`pyproject.toml` 与 `scripts/check-offline`，另加 Fowler smell 基线。实际使用 Bash 执行只读 `git diff`/`git show`/`git log`/`git status`/`gh issue view`，并以 Read/Grep 核对；89/89 个变更文件均逐 hunk 阅读。未运行 pytest、Ruff、mypy、完整门禁或 live；工具已强制的事项不重复报告。

**Spec**：按 `docs/agents/issue-tracker.md` 对 #92–#99 八票逐一执行两种 `gh issue view`，正文、全部评论、labels 与原生 parent/subIssues/blockedBy 均读取完成；所有相关 `totalCount` 等于节点数，关系图完整。后续用户裁决优先，实现者完成报告仅作待核线索。辅助来源为 `intent/draft.md`、`GLOSSARY.md`、ADR-0021/0025、`docs/contracts/stage-inputs.md`；diff 内的 Read Contract 和覆盖台账不作为自证。实际使用 Bash 执行只读 git/gh、公共入口反例和离线 pytest。未逐行复核全部 89 个文件及全部历史 scope 哈希。

两轴必需来源均可用，审阅完成；均未运行会发布新证据的 `./scripts/check-offline`，未运行真实模型、Pi、Docling、PDF、NAS 或其他 live。

## Standards

### S1 — A9 接入后，离线证据正文仍描述旧发布与回执范围（低）

- **类别**：成文规范／文档同步；不属于 Fowler smell。
- **影响**：指定离线证据文档自相矛盾，可能误导人工验收与 scope 审阅。现有证据只支持文档问题，不主张运行时漏登 A9。
- **位置与证据**：`docs/verification/offline-evidence.md:163` 仍写“九组”，但同页 `:146-155` 已列 A1、A2-01、完整 A2、A3–A9 共十组；`scripts/a2_full_acceptance.py:447-454` 登记必需 A9，`scripts/a9_acceptance.py:265,551` 也调用同一个 `publish_conclusion`。`docs/verification/offline-evidence.md:169` 的当前回执只列到 `a8_scope`，而 `scripts/a2_test_receipt.py:24,34-44` 已导入并纳入 `A9_TEST_MODULES`。
- **规范引用**：`docs/agents/documentation.md:3` 要求公共 Contract 等改动在同一变更中同步文档；`docs/agents/testing.md:9` 明确“完整离线验证入口与证据格式见 `docs/verification/offline-evidence.md`”。`git show main:docs/verification/offline-evidence.md` 复核表明旧文案在 baseline 成立，是本次 A9 接入造成的失配。
- **已有测试核查**：`tests/test_a9_acceptance.py:8-15` 核查生产登记，`tests/test_a9_status.py:16-25` 核查真实回执包含 A9 模块；它们证明运行事实，但不是文档句子测试。对“九组／当前回执显式记录／offline-evidence.md”的测试搜索无匹配；本项不以“缺测试”为理由。Standards 轴未运行这些测试。
- **复现／限制**：当前文档与代码静态矛盾已复核，无需运行反例；未验证运行时是否存在同等问题，也没有证据作出该推断。
- **最小建议、成本与风险**：将“九组”改为“十组”，回执列表补 `a9_scope`，无需新增脆弱的全文计数测试。该文档冻结于 `scripts/a8_scope.py:341-342` 和 `scripts/a9_scope.py:606-607`，且 A9 固定 `scripts/a8_scope.py`（`scripts/a9_scope.py:497-498`），至少三处哈希需按实际 DAG 重绑；随后运行 scope 审计和完整门禁。运行语义风险低，成本包含文档、两级 scope 登记与验证，不能只改文案即宣称完成。

其余未发现可成立的成文 Standards 违例或 Fowler 基线 smell。工具强制项按规则跳过。

**Standards 完成状态**：完成，必需来源无缺失；89/89 个 diff 文件逐 hunk 审阅。未运行测试或完整门禁，不据此声明门禁通过。**FINDINGS=1；轴内最重项为 S1。**

## Spec

### F1 — 功能缺陷：无空格连字符范围丢失右端点，错误证据可静默通过

- **位置与影响**：`src/paper_radar/reading/numbers.py:161-170` 的 `_atoms()` 将 `3-5 km` 中 `-5` 当作带符号数，又因其前一字符为数字而跳过，最终只提取 `3`。正常公共调用 `validate_read_output(candidate(...), context_for(...))` 中，陈述 `3-5 km` 引用仅含 `3 to 4 km` 的片段时，右端点完全不检查；预期在 `$.main_findings[0].statement` 产生 `range_not_supported` 及程序降级警告，实际二者均为空，错误证据因而静默通过。
- **规格／裁决引用**：[#94 正文](https://github.com/MeteoBoy4/PaperRadar/issues/94) Acceptance criteria：“范围两个端点需在同一 provenance 切片出现，单位按后一端点解释。”[#92 正文](https://github.com/MeteoBoy4/PaperRadar/issues/92) User Stories 第 25 条：“数值、范围和相邻单位不匹配时保留分析并追加降级警告”。两句均来自 Issue 正文；已核对后续评论，没有相反裁决。
- **已有测试核查**：`tests/test_read_numbers.py:33` 在 `test_closed_numeric_equivalences_match_own_support`（`:46-56`）覆盖正例 `3-5 km`/`3 to 5 km`，但零诊断断言不能证明两个端点均被提取；`tests/test_read_numbers.py:67` 的错误端点负例使用 `3–5 km`，未覆盖连字符路径。这是覆盖不足，不是断言失真。
- **实际复现**：Spec 轴运行以下最小合成反例，未读取真实论文或完整 Prompt：
  ```bash
  PYTHONDONTWRITEBYTECODE=1 uv run --offline --locked python -c 'from paper_radar.reading.numbers import extract_numeric_literals; from paper_radar.reading import validate_read_output; from tests.read_support import candidate,context_for; s="3-5 km"; print("literals",[(x.text,tuple(str(v) if v is not None else None for v in x.values),x.units) for x in extract_numeric_literals(s)]); r=validate_read_output(candidate(main_findings=[{"statement":s,"evidence":[{"evidence_id":"e1"}]}]),context_for("3 to 4 km")); print("diagnostics",[(d.reason.value,d.ordinal) for d in r.diagnostics]); print("warnings",[w.text for w in r.warnings])'
  ```
  输出：
  ```text
  literals [('3', ('3',), (None,))]
  diagnostics []
  warnings []
  ```
  聚合者另以同一公共入口独立复现，得到 `diagnostics=()`、`warnings=()` 且仅一个提取结果，确认到达目标路径，不是前置上下文拒绝。
- **最小建议、成本与风险**：词元化时区分数字间连字符范围与负数符号，保留现有负数及带空格范围行为；向现有负例参数表加入 `("3-5 km", "3 to 4 km", "range_not_supported")`，并证明两个端点均参与检查。新增一项会使 `scripts/a9_scope.py:54` 固定分母 79→80、A9 总分母 541→542；须按实际 collection 更新分母，重绑 A9 对实现、测试和台账的固定 SHA-256，再跑完整门禁。修改集中在数值词元化，行为风险可用现有向量控制；冻结分母或哈希若手工绕过会损害回执可信性，不应那样处理。

**实际测试**：Spec 轴执行：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --offline --locked pytest -q -p no:cacheprovider \
  tests/test_read_contract.py tests/test_read_context.py \
  tests/test_read_validation.py tests/test_read_numbers.py \
  tests/test_read_privacy.py tests/test_read_restricted.py \
  tests/test_read_reduce.py tests/test_read_config.py \
  tests/test_read_config_cli.py tests/test_read_recovery.py \
  tests/test_a9_acceptance.py tests/test_a9_integrity.py \
  tests/test_a9_entry.py tests/test_a9_status.py tests/test_a9_scope.py
```

结果为 **541 passed in 48.67s**。这些通过用例未覆盖 F1 反例，不能据此否定该缺陷。

**Spec 完成状态**：完成，八票必需来源与关系图完整；除 F1 外，没有发现其他证据充分的缺失／部分实现、scope creep 或实现错误。未运行完整门禁、Ruff/mypy 或 live，未逐行复核全部 89 个 diff 文件及全部历史 scope 哈希。**FINDINGS=1；轴内最重项为 F1。**

**汇总：Standards 1 项，轴内最重为 S1（A9 文档仍写旧发布／回执范围）；Spec 1 项，轴内最重为 F1（连字符范围漏检右端点）。两轴不跨轴排序。**


## 本轮核实与处置（关联 #92、#94、#99）

核实基线为 `4d559c495b5158d5bd079e672a8fde6f540ba277`。以上审查原文完整保留；
本节记录逐条核实、采纳判断及实际修改，不改写审查时点的发现。
原文 SHA-256：`f7ba23e001685f0583e3369359c90ce594f4bb202775232e5bfbe8fa95221a06`。

| 项目 | 判断 | 核实与处置 |
| --- | --- | --- |
| Standards S1 | 采纳 | 生产登记已有 A1、A2-01、完整 A2、A3–A9 共十组，回执代码也已纳入 A9；文档仍写九组并漏列 a9_scope，属于文案失配。已改为十组并补列 a9_scope；沿用既有登记/回执测试，不新增全文计数测试。 |
| Spec F1 | 采纳 | 公共入口独立复现 `3-5 km` 对 `3 to 4 km` 零诊断。先把该反例加入现有参数表，实际得到 1 failed / 11 passed，再窄修紧邻有效数值词元的连字符范围右端识别；修后同组 12 passed。 |
| r1 的修复成本与验证建议 | 采纳 | 补充边界回归，按实际 DAG 核对并重绑 A8/A9 的文档/实现/测试材料，保留固定分母和独立收集、实际执行的区分。旧四契约、Read v1 Schema、规则 wire 身份及 migration 不变。 |

F1 新增15项公共入口向量：原始错误右端点1项，带空格/显式单位/负数/标识符
兼容正例7项，右端缺失、单位冲突与负数符号负例6项，连字符范围跨切片拒绝1项。
负例锁定 `$.main_findings[0].statement`、受控原因及程序警告；同一切片要求、负数、
已有 ±、科学记数和显式端点单位规则共同回归。数值模块由79增至94项，全部通过；
全部 Read 测试436项通过。Public Contract 已补充无空格连字符与负数端点的说明。

本轮没有需拒绝的具体修改建议。完整门禁必须在包含本报告的最终提交上重新执行；
本节不将尚未执行的新门禁写成通过，也不将此前运行的结果替代新提交证据。
最终同次结论由 `verification-runs/` 保存，修复前后绑定审阅记录见
`docs/verification/a9-scope-review.md` 的外部审查处置节。


### 本轮提交前实际验证

- `uv run --offline --locked pytest tests/test_read_numbers.py -q --tb=short`：94 passed。
- `uv run --offline --locked pytest tests/test_read_*.py tests/test_a9_*.py -q --tb=short`：556 passed（49.59s），为最终15项增量之后的Read/A9组合。
- A8/A9/scope受影响组合：322 passed（87.97s）；之后只补充了显式单位错误右端的一个回归和对应登记数，最终Read/A9组合已重新执行。
- 全项目 Ruff format/check、mypy：通过，528个源文件。
- 独立 `audit_verification_scope --collect --json`：exit0、collection=ok、无漂移/登记问题；数值94、A9总556，旧组分母保持。收集未冒充执行。

原始Read v1 Schema及旧四份契约、配置投影与migration没有改动。
完整 `./scripts/check-offline` 留给根代理在最终提交上执行；最终运行标识及结果
写入同次验收证据，不能回写本报告制造已验证提交的字节变化。
