# RuntimePlan 命名尚未统一

状态：待决。尚未确定规范术语与规范写法，也未决定是否需要新增 `CONTEXT.md` 词条。
触发问题：一次「这个项目的上下文里，RuntimePlan 到底指什么？」的问答暴露出同一个概念在文档中至少有五种写法，且其中一种与清理计划共用无限定词「计划」。

参照文件：

- `intent/draft.md` §3.4（阶段输入指纹）、§3.5、§4.5、§4.6、§5.2（`runtime_plans`）、§5.3（`calibration_evaluations` / `calibration_changes`）、§6（保留清单）、§7.6（模型配置）、§8.1、§9.3（清理）、阶段 A / D / I 与最终 DoD
- `CONTEXT.md`「自动精读门禁」词条
- `docs/adr/0019-allow-calibration-recalculation-on-revealed-labels.md`、`docs/adr/0020-let-the-user-classify-calibration-impacting-changes.md`、`docs/adr/0022-conditionally-upgrade-reuse-feasibility-from-fulltext-excerpts.md`
- `intent/archived_discussions/daily-paper-reader.md` §6.1、`intent/archived_discussions/kimi-advise-grill.md` 第 15 条
- 当前实现：`src/paper_radar/` 下只有 `contracts/` 与 `screening/`，没有任何 RuntimePlan 相关符号

## 一、现状：同一概念的五种写法

| 写法 | 形态 | 出现位置 |
|---|---|---|
| `RuntimePlan` | PascalCase | `intent/draft.md:206`、`:436`、`:442`、`:892`、`:1051`、`:1364`、`:1382`、`:1528`、`:1555`；`docs/adr/0022…:5`；`intent/archived_discussions/daily-paper-reader.md:223` |
| `runtime plan` | 小写、空格 | `intent/draft.md:767`、`:768`、`:1564`、`:1593`、`:1828`、`:2030`；`CONTEXT.md:102`；`docs/adr/0019…:3`；`docs/adr/0020…:3`；`intent/archived_discussions/kimi-advise-grill.md:118` |
| `运行计划` | 中文 | `intent/draft.md:1049`；`intent/archived_discussions/daily-paper-reader.md:218`；`intent/archived_discussions/grill-history.md:1557` |
| `计划` | 无限定词 | `intent/draft.md:463`、`:749`（`runtime_plans` 行的「约束」列）、`:1566`、`:1594`、`:1596`、`:2030` |
| `runtime_plans` | snake_case 表名 | `intent/draft.md:749`（逻辑数据模型 §5.2） |

另外还有两种带限定词的派生写法，语义上并没有被单独定义：

- 「当前冻结 RuntimePlan」（`intent/draft.md:442`）、「旧预热 RuntimePlan」（`:1555`）、「新计划」（`:463`、`:1566`、`:2030`）——都用限定词表示不同时点的计划；
- 「当前 Screening runtime plan」（`intent/draft.md:1828`）、「当前 runtime plan」（`:1593`；`CONTEXT.md:102`）——把 plan 限定到某个阶段。这一点与 `runtime_plans` 行的「每次任务引用固定计划」并列时，尚不清楚「阶段级 plan」与「整体 plan」是不是同一条记录的不同标法。

同一段落内部也会混用，例如 `intent/draft.md:1555` 前半句写 `RuntimePlan`、后半句写「当前冻结计划」。

## 二、上下文：这个概念是什么

`RuntimePlan` 指**把本次运行中所有会改变语义的输入编译成的一份不可变运行计划**，任务是它的消费者而不是它的构造者：

- **内容**（`intent/draft.md:749`，逻辑表 `runtime_plans`）：编译后的配置、Profile、主题、期刊、模型、提示词、规则、升级参数、解析器及确定性算法版本哈希；约束是「每次任务引用固定计划」。
- **来源**：`settings.yaml` 只选择当前 Profile、主题、复用升级参数、提示词和契约版本（`:877`）；这些带版本的内容文件创建后不可原地改写，`doctor` 发现同一声明版本对应不同哈希时拒绝编译（`:1051`）。概念源自上游借鉴「版本化用户配置 → 校验/规范化 → 不可变 RuntimePlan → 各任务消费」（`intent/archived_discussions/daily-paper-reader.md:223`）。
- **制品可追溯**：`calibration_evaluations` 有 `runtime plan` 字段，`calibration_changes` 记录「前后 runtime plan」（`:767`、`:768`）；保留清单要求「所有被 RuntimePlan 或历史制品引用的 Profile、主题、提示词和导出契约版本」永久保留（`:892`）。
- **校准门禁的绑定物**：「冻结对应 RuntimePlan 才能创建正式批次」（`:436`）；自动精读门禁要求「当前 runtime plan 拥有通过门槛的 calibration evaluation」（`CONTEXT.md:102`，`:1593`、`:1828`）。
- **校准变更分级的触发源**：「运行计划与最近一次门禁所依据的计划存在校准相关差异时，doctor 和 run-due 必须列出差异并要求用户分级」（`:1049`，`docs/adr/0020…:3`）；`minor` 继承门禁、`major` 关闭门禁。触发参数如 `reuse_escalation_research_values` 必须进入 RuntimePlan、输入指纹和校准变更分级（`:206`，`docs/adr/0022…:5`）。
- **与阶段输入指纹分工不同**：指纹只回答「哪些制品需要重算」，plan 差异才回答「既有校准门禁是否仍然有效」（`:169`–`:184`）。
- **实施状态**：它是阶段 A 的待办「建立配置编译、提示词版本和 RuntimePlan」（`:1364`），验收条件之一是「同一声明版本下修改 Profile、提示词或契约内容时 RuntimePlan 编译失败」（`:1382`）。当前 `src/paper_radar/` 尚未出现该符号，`docs/adr/0020…`、`docs/adr/0022…` 与 `CONTEXT.md:102` 的描述仍是设计意图而非既有行为。

## 三、写法漂移的来源

三种写法各自对应一种行文场景，而不是有意的术语分工：

1. 概念借自上游英文术语，所以首次引入和涉及类名/模块名的语境倾向写 PascalCase `RuntimePlan`（`:1364`、`:1382` 的阶段 A 实施与测试条目）。
2. 中文散文行文时改写成「运行计划」（`:1049`），但同一节的下一段又回到 `RuntimePlan`（`:1051`）。
3. 逻辑数据模型与 ADR 倾向小写 `runtime plan`，与表名 `runtime_plans` 在视觉上更接近（`:767`、`:768`；`docs/adr/0019…`、`docs/adr/0020…`）。
4. 需要指代某个具体时点的 plan 时，中文行文直接用无限定词「计划」（`:1566`、`:1594`、`:1596`）。

## 四、两个具体的混淆风险

**1. `计划` 与清理计划冲突。** §9.3 的 `artifacts gc` 也有一个「计划」，共用同一个无限定词：

- `intent/draft.md:1257`：「**计划**显式列出 artifact ID、路径、未被引用证据和可重建依据。执行只接受已保存**计划** ID，不接受目录或 glob……永不进入**计划**。」
- 同一条文档里 `intent/draft.md:749` 的 `runtime_plans` 约束列也写成「每次任务引用固定**计划**」。

于是「计划 ID」在 `:749` 指运行计划，在 `:1257` 指清理计划，而 CLI 参数 `artifacts gc --execute <plan-id>` 又使用了同一个词。`:1566`、`:1594`、`:1596`、`:2030` 的「新计划 / 当前计划」虽在同一主题下可由上下文判断，但没有一处写明它就是在指 RuntimePlan。

**2. `CONTEXT.md` 引用了没有词条的术语。** `CONTEXT.md:102` 的「自动精读门禁」定义直接使用 `runtime plan`（小写），但 `CONTEXT.md` 全库没有 `RuntimePlan` 或「运行计划」词条；`rg` 确认 `CONTEXT.md` 中该写法只出现在这一处。也就是说，一个承担门禁绑定语义的概念只在定义句里被引用，而没有术语条目规定它的中英对应和规范大小写。

## 五、尚未确定的问题

以下问题需要用户决定，本文不代为选择：

1. 规范术语采用中文「运行计划」还是英文 `RuntimePlan`？还是像其他领域词一样以中文为主、英文派生名并列？
2. `runtime plan`、`RuntimePlan`、`运行计划` 三者是否需要统一为一种写法，还是按「散文用中文、代码标识符用 PascalCase、表名用 snake_case」明确分工？
3. 无限定词「计划」是否一律改为限定写法，以便与 §9.3 的清理计划区分？若是，`artifacts gc --execute <plan-id>` 的措辞是否也要一并调整？
4. `runtime_plans` 记录与「当前 Screening runtime plan」（`:1828`）是同一概念的不同限定，还是需要区分为两条独立记录？
5. `CONTEXT.md` 是否新增该词条；若新增，它与其他派生词（「校准变更分级」「自动精读门禁」「校准重算」）的引用关系如何表述？

各候选方案的取舍取决于第 1、2 题的答案，因此暂不记录倾向性建议。

## 六、附带确认的事实

- 命名统一只涉及领域 vocabulary 与文档表述。上述任一写法当前都没有对应的 Pydantic Schema、冻结契约或阶段指纹语义，因此改名（无论选哪种）不改变模型输入、建议规则、校准行为或阶段指纹，不触发 calibration change workflow。
- 由于阶段 A 尚未实现该概念，`src/`、`tests/` 与 `contracts/` 都不存在需要同步改名的标识符；现在统一的成本低于任何后续时点。
