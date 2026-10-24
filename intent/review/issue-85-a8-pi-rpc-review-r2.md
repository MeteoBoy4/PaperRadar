# 阶段 A8 双轴审查 r2（#85 / #86–#91）

- 固定点：`main` = `7473c1c8cd986827e55d9e8d12fa8cc18bf7ba89`；被审 HEAD = `da9b9ff6f0007822dc26e6f2454baae389281e9a`（`integration/issue-85-pi-rpc`）。
- merge-base 等于 `main`；审查命令为 `git diff main...HEAD`，共 74 个文件，`+9286/-84`。
- 两轴由独立子 agent 并行审查，均被赋予并实际使用 Bash；初次额度中断后从各自原上下文恢复并完成。两轴结果分列，未跨轴合并或重排。
- 全程未修改源码、测试、冻结材料或 Issue，未创建 commit，未运行真实 Pi/Node/模型/live；本文件是唯一写入的审查产物。
- 审查期间出现的 `issue-85-a8-pi-rpc-kernel-review-r1.md` 与 `issue-85-a8-pi-rpc-review-r3.md` 均未读取、未修改、未覆盖；本报告独立产出。

提交范围（`git log main..HEAD --oneline`）：

```text
da9b9ff Merge #85: review fixes for interruption cleanup and cancellation ACKs
465b3af fix(llm): finish interrupted RPC cleanup and validate cancel queue ACKs
b1014e3 Merge #91: independent A8 acceptance and trusted terminal binding
0270c97 test: register independent A8 offline acceptance (#91)
0a7137f Merge #90: RPC retry history and isolated recovery evidence
c03a89f test: prove RPC task budgets and isolated recovery (#90)
297e092 Merge #89: bounded RPC pipes cancellation and process cleanup
8196f93 feat: bound RPC pipes cancellation and process group cleanup (#89)
c809fdc Merge #88: strict RPC candidates and model usage observations
8f50be1 feat: harden complete RPC candidates and value acceptance (#88)
387e4c4 Merge #87: bounded RPC boundary call and authoritative reception
fdd1fe9 feat: accept boundary candidates through bounded single RPC call (#87)
ca845b8 Merge #86: frozen RPC call descriptions and protocol sources
7a8dcbc feat: freeze audited Pi RPC call descriptions and request vectors (#86)
```

## Standards

### 工具、来源与完成状态

- **完成。** 子 agent 实际使用 Bash（只读 Git、静态检查、受控离线测试）、Read、Grep、Glob，审阅全部 74 个变更文件及最终修复；HEAD 与 `465b3af` 的 tree 均为 `f440d8f171452f8f6398e4ae74234a8b7149a9ee`。
- 实读 `AGENTS.md`、`CLAUDE.md`、`GLOSSARY.md`、`README.md`、`docs/agents/` 适用规范、相关 ADR/Contract、`pyproject.toml`、测试及 #85–#91 快照；逐项套用仓库规范和 Fowler smell baseline，仓库明确许可优先，工具已强制的机械问题不重复报告。
- Pi 资料由 `docs/docs.json` 导航定位，按需核对文档与随包实现，并区分文档事实和源码推导；未凭印象补充 Pi 行为结论。
- 无必需来源缺失。未验证：Spec 结论、本轮完整 `./scripts/check-offline`、真实 Pi/Node/模型/live 与生产启动器行为。

### 发现

**无。** 文档化硬违例 0 条；smell/可选可维护性判断 0 条。未把独立验收判据、离线证据要求的 DAG 哈希同步或有意独立的测试夹具误报为 Shotgun Surgery/Duplicated Code。零发现时各证据字段不适用。

### 本轴验证

- `pytest -q -p no:cacheprovider tests/test_a8_*.py` → **613 passed / 86.75s**。
- 本次修改的 11 个既有验证测试模块 → **121 passed / 143.09s**。
- `ruff format --check .` → 702 文件符合；`ruff check .` → 通过；`mypy` → 496 文件无错误。
- `./scripts/audit-verification-scope --json` → exit 0，`affected_groups=[]`、`issues=[]`；`./scripts/dev-environment check --json` → exit 0；`git diff --check main...HEAD` → exit 0。
- 本轮未重跑会写入 `verification-runs/` 的完整门禁，不把 Issue 完成汇报当作本轮实跑结果。

## Spec

### 工具、来源与完成状态

- **完成。** 子 agent 实际使用 Bash、Read、Grep、Glob；复核 `main...HEAD`，读取 #85–#91 正文和全部评论、D1–D4/P3 及子票补充裁决、A8 实现、20 个测试模块和文档差异。评论永久链接与本地行号用于区分原始要求、后续裁决和实现者完成汇报。
- 原始 Issue 通过 `gh issue view <n> --comments` 及原生关系 JSON 取得；#85 的 6 个 subIssue、#87–#91 各 1 个 blockedBy 均完整，无关系分页缺失。本地 `intent/draft.md`、ADR-0026/0031、相关 Contract 与 A8 台账用于交叉核对，未用于自我证明。
- Pi 1.4.0 文档根目录及 `docs/docs.json` 可访问；按需核对 `rpc.md`、`rpc-commands.md`、`json.md`、`message-types.md` 等来源。未运行真实 Pi/Node/模型或网络。
- 最终复跑 `uv run --offline --locked pytest -q tests/test_a8*.py` → **613 passed / 87.53s**；scope 审计 exit 0，`affected_groups=[]`；`git diff --check main...HEAD` 通过。本轮未重跑完整 `check-offline`，未验证 live/生产启动器。

### 发现

#### S1｜P3｜规格部分落实（文档偏差）：验收组数量仍写“八组”

- **位置与影响**：`docs/verification/offline-evidence.md:159` 写“八组的 `write_*_conclusion`”，但同页 `:141-151` 已登记 A8，`scripts/a2_full_acceptance.py:385` 的 `acceptance_groups()` 实际返回 9 组。维护者可能误判当前发布范围；未发现实际注册或发布功能错误，未证实运行功能影响。
- **原始需求/裁决**：[#91 AC6](https://github.com/MeteoBoy4/PaperRadar/issues/91) 要求“新组登记、状态工具识别 .a8.json 格式1、控制方 terminal 绑定和帮助/文件份数说明在同一波完成”；[#85 第一次补充](https://github.com/MeteoBoy4/PaperRadar/issues/85#issuecomment-6377399778) §五.5 明确要求更新 `offline-evidence.md`。因此这属于 Spec 文档收口遗漏，不是 Standards smell，也不是新增要求。
- **预期/实际**：A8 加入后应为九组；正文仍保留八组，与本页表格和真实公共登记矛盾。
- **最小复现（聚合者独立实跑）**：

  ```bash
  uv run --offline --locked python - <<'PY'
  from scripts.a2_full_acceptance import acceptance_groups
  groups = acceptance_groups()
  print(len(groups))
  print([group.name for group in groups])
  PY
  ```

  实际输出：

  ```text
  9
  ['A1', 'A2-01', '完整 A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8']
  ```

- **已有测试核查**：`tests/test_a8_entry.py:146-171` 的 `test_a4_only_failure_preserves_a8_but_a7_failure_blocks_it` 使用真实 `acceptance_groups()` 验证失败传播；`tests/test_verification_scope_registry.py:15-20` 的 `test_real_registry_covers_all_writers_and_fixed_counts` 验证 scope 与真实组登记一致。二者都不读取该文档句子；全 `tests/` 搜索 `offline-evidence\.md|八组|九组` 无匹配。这是文档断言未覆盖，不是“真实组登记无测试”。
- **限制**：文档问题已由只读调用复现；未运行完整门禁或 live，也未主张存在运行时发布缺陷。
- **最小建议**：将“八组”改为“九组”。随后按 `./scripts/audit-verification-scope --json` 的实际闭包重绑受影响文档哈希并运行完整 `./scripts/check-offline`，不手工假定只影响 A8。代码行为不变、语义风险低，但验收重绑与完整门禁有实际成本；无需为一句计数新增脆弱的全文产品测试。

### 复核后撤回的候选（不计发现）

- **“五份公共文档必须全部加入 A8 SHA-256 绑定”**：子 agent 在受控临时 `repository_copy` 中删除 `GLOSSARY.md` 后捕获基线，再经真实 `conclude()`/`write_a8_conclusion()` 得到 `baseline_equals_current=true`、`status="passed"`、`a8_verified=true`，说明运行时现象成立；`tests/test_a8_integrity.py:248`、`:399`、`:469` 也未覆盖这五份文档的成员完整性。
- 但 #85 原文只对这五份文档要求“更新/增加/记录”，#91 AC2 的“源码/材料哈希”未明确把它们全部定义为固定材料。不能用本次实现新增的 `docs/verification/a8-requirements.md` 反向制造原始 Spec 义务。因此**撤回 P2 Spec 定性**；如未来需要该加固，应先明确材料范围，再增加绑定和负例。本项不计入 Spec findings，也不转投 Standards。

其余两类结论：未确认额外 scope creep；未确认新的 RPC/预算/恢复功能实现错误。613 个 A8 测试通过不证明真实 Pi、生产隔离、参数映射或 live 行为。

**汇总：Standards 0 条（无最严重项）；Spec 1 条，轴内最严重且唯一的是 S1（验收组数量文档漂移）；撤回候选不计。**

## 2026-10-24 逐项核实与处理（追加，原报告保留）

追加前原文字节 SHA-256：`2aa73fd2fe2e163ec88ec2117a00203cd6c09b9c7370ff3be4edc28c83542262`。
本轮重读 #85–#91 及补充裁决，按当前公共登记、文档和实际scope审计核实。

| 原编号/候选 | 核实与处理 | 落点/验证依据 |
| --- | --- | --- |
| Standards 无发现 | 核实背景，无需为“零发现”制造代码调整；继续保持内核分层、受控原因、离线/隐私、旧分母与独立验收模式。 | test_a8_llm_architecture.py、A8既有回归与scope审计；本轮仅A8闭包。 |
| Spec S1 九组/八组 | 接受。acceptance_groups()登记 A1、A2-01、完整A2、A3、A4、A5、A6、A7、A8 共九组；将 offline-evidence.md 中“八组”改为“九组”。这是文案遗漏，运行登记未错，不增加计数字符镜像测试。 | docs/verification/offline-evidence.md；test_a8_entry.py 与 test_verification_scope_registry.py 既有公共登记检查继续复用。 |
| 撤回候选：五份公共文档全部绑定 | 维持撤回、不采纳新增冻结范围。更新文档的原始义务不等于全部进入SHA-256固定成员；当前验收实现不能反向创造规格。新增绑定若有需求应先明确范围，本轮仅按现行审计更新既有成员哈希。 | #85文档落点、#91 AC2/7；本轮实际审计仅A8的8项绑定变化，不改成员边界。 |

其他两份报告的合理局部项同时收口：集中七档词表与Literal、prompt具名常量，修正公共入口
paper_radar.llm.rpc.run_call、poll封顶文案并补公共run_call安全行为覆盖。protocol新增16项后
69项通过；A8相关Ruff/format和严格mypy（39文件）通过。完整A8子集、scope --collect及
最终check-offline以本节后续验证记录/稳定提交证据为准；旧证据不能代替新树验证。
未运行真实Pi/Node、模型、网络、抓流或生产隔离；rpc/live/stage_a_verified不升级。

收口验证：全部A8子集 **629 passed/86.29s**（最慢恢复7.53s）；A8相关Ruff/format和
mypy39文件通过。`./scripts/audit-verification-scope --collect --json` exit0、无漂移/问题，
233模块与人工分母一致；git diff --check通过，三份报告原文字节前缀均保留。
最终完整check-offline仍由提交后稳定树运行，本段不宣称其已完成。
