# 审阅证据附加提示词

本文件不是编码标准，仅在用户手动附加时适用；Standards 轴不得把它列为标准来源。

## 用法

在请求 `code-review` 时，替换下方 `<repo>`、`<base>`、`<head>`、`<spec>`，把整个代码块附加到审阅请求中。`<base>` 与 `<head>` 使用固定提交 SHA；`<spec>` 填 Issue 链接或仓库内规格路径。说明、历史走读和检查表不属于要转交的提示词。

本文件只补充本次审阅的证据要求，保留 Standards（仓库标准）与 Spec（需求符合性）分工、原有格式及仓库规则优先级。读票方法沿用 [issue-tracker.md](../agents/issue-tracker.md)。是否附加由用户决定，无需安装技能或改动自动加载配置。

## 完整可复制提示词

```markdown
请在本次审阅中应用以下证据要求。它们不是代码判定标准；Standards 轴不得将这份提示词列为标准来源。

输入：仓库 <repo>，固定比较基准 <base>，目标提交 <head>，规格/Issue <spec>。

主 agent：把本提示词全文分别附加到 Standards 子 agent 和 Spec 子 agent 的提示中。保留两轴分工与原有格式，仓库规则优先。聚合时可以给证据不足的发现标注「未核实」，但保持两轴分列，不改变排序。

附加本提示词时，两轴子 agent 的「Under 400 words」上限各放宽到 800 词；用文件:行、测试名、评论永久链接压缩证据。仍超限时优先保留发现的证据字段，合并低优先级 smell 建议，披露因篇幅未展开的范围，不把缺证据的结论当成已核实发现。

1. 读取 Issue 沿用仓库 docs/agents/issue-tracker.md 的方法。评论中的后续用户裁决优先于正文；核对裁决的适用范围和时间，区分用户要求与实现者完成报告。说明两轴实际可用的只读工具和可访问来源；工具或来源不可用时标「未核实」。缺少完成审阅所必需的来源时，明确报告「审阅未完成」，不能用「通过」或「零问题」代替。
2. 对每条候选发现，核对具体代码路径、原始需求及最新适用裁决。已有明确裁决时按其执行；只有仍未解决的真实矛盾才请求新裁决。保留裁决中留待后续阶段解决的问题与触发条件，不能将暂缓处理误报成本次缺失。
3. 声称「缺测试」前搜索并读取现有公共行为用例，给出测试名与代码位置。区分没有覆盖、覆盖不足、测试本身失真和仅缺某种实现方式；测试通过也须核对断言是否证明了目标语义。
4. 功能缺陷给出最小正常调用路径、预期/实际差异及可运行反例（命令或代码）。遵守已验证快照等公开前提；失败需核对实际异常的原因、类型及位置，确认到达目标路径，排除其他前置错误。注明实际运行的命令和结果；未运行测试写「未运行」，仅静态推断或尚未复现的疑点写「未复现」，不能假称执行成功。历史缺陷同时注明缺陷提交和修复状态。
5. 区分文档化硬要求、功能错误、测试缺口与可选可维护性建议。smell 仅是判断线索；逐项说明实际修改成本与风险，并核对仓库明确许可的封闭分派和独立判据。机械问题优先建议可执行检查或回归测试；判断题才建议 reviewer 标准。测试通过不证明所有语义正确，语法相似也不自动证明需要通用框架。
6. 保持只读与脱敏。必要复现使用受控临时位置；保持当前工作树、冻结材料及 Issue 状态原样，不运行未授权 live。证据用最小合成输入、符号和来源指针，不要求读出或发布 secret、完整 Prompt、论文全文或会话原始日志。

每条发现至少包含：类别、影响、文件/符号位置、需求/裁决引用、已有测试核查、复现或未验证限制、最小建议。字段不适用时说明原因。没有足够证据时可以无发现，不按预定数量凑问题；同时分别披露两轴的完成状态、缺失来源和未验证范围。
```

## 三个历史样例走读

来源为 [Issue #58 及后续裁决](https://github.com/MeteoBoy4/PaperRadar/issues/58)、[r2 审阅与实现者处理附录](https://github.com/MeteoBoy4/PaperRadar/blob/152d95a82893ba8530674579b1b2f00481717448/intent/review/issue-47-a5-stage-inputs-review-r2.md)。以下为源码与裁决的人工走读，不是本次执行历史测试或模型审阅实验的记录；不要求模型固定措辞或固定发现数。

历史审阅目标是 `f774831ae4308b1c41dc9f2249af571429e9df9d`；核对基线 `152d95a82893ba8530674579b1b2f00481717448` 已含修复。用两个提交区分当时的真实问题与当前行为。

### 已有用户裁决：C1

候选发现：「未按文档维护通则同步修改 `intent/draft.md` §4.9，需再裁决。」

核对 [C1 用户裁决](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6265245363)的「落实要求」与 [stage-inputs Contract](https://github.com/MeteoBoy4/PaperRadar/blob/152d95a82893ba8530674579b1b2f00481717448/docs/contracts/stage-inputs.md)：用户明确要求 A5 保持 extraction 格式 1，只在 Contract 登记已知未决问题，§4.9 的收敛留给阶段 F。结果应为「适用已有裁决」，不再要求裁决同一问题，也不据通则判 A5 违规；阶段 F 的条件仍保留。

### 已有重复键用例：纠正缺测判断

候选发现：「回放拒绝重复 JSON 键没有测试，必须加 `object_pairs_hook`。」

读取原审阅提交中的 [test_stage_input_replay.py](https://github.com/MeteoBoy4/PaperRadar/blob/f774831ae4308b1c41dc9f2249af571429e9df9d/tests/test_stage_input_replay.py)，定位 `test_replay_rejects_equivalent_but_noncanonical_bytes`：第三个参数化变换已写入重复 `kind`，使用变换后载荷的正确哈希调用 `replay_stage_input`，并断言 `ReplayReason.NON_CANONICAL`。再核对同提交的 [回放实现](https://github.com/MeteoBoy4/PaperRadar/blob/f774831ae4308b1c41dc9f2249af571429e9df9d/src/paper_radar/stage_inputs/service.py)与核对基线的 [Contract](https://github.com/MeteoBoy4/PaperRadar/blob/152d95a82893ba8530674579b1b2f00481717448/docs/contracts/stage-inputs.md)。结果应纠正「无用例」判断：逐字节规范比较已拒绝重复键，指定另一种实现方式不是测试缺口。这不证明所有嵌套或冲突键均被该单例覆盖；是否有其他缺口须另查具体行为。本次只读源码，未运行该测试。

### 真实 context 原因分类：保留有证据的缺陷

以历史提交 `f774831ae4308b1c41dc9f2249af571429e9df9d` 为审阅目标，可形成如下发现：

| 字段 | 证据与结论 |
| --- | --- |
| 类别 | 功能错误：公共 context 面混用回放原因枚举。 |
| 影响 | 调用者按 `BuildReason` 判因时，会漏掉投影不匹配等 context 拒绝。 |
| 文件/符号位置 | [service.py](https://github.com/MeteoBoy4/PaperRadar/blob/f774831ae4308b1c41dc9f2249af571429e9df9d/src/paper_radar/stage_inputs/service.py)：`StageInput.value_prediction_context` 调用 `_verify_projection`，后者抛 `ReplayReason`。 |
| 需求/裁决引用 | [实施前补充（三）第三节](https://github.com/MeteoBoy4/PaperRadar/issues/47#issuecomment-6266736991)：构造拒绝、回放拒绝、不可比原因按面使用三张封闭词表。 |
| 已有测试核查 | 旧 [test_stage_input_value.py](https://github.com/MeteoBoy4/PaperRadar/blob/f774831ae4308b1c41dc9f2249af571429e9df9d/tests/test_stage_input_value.py) 的 `test_context_is_bound_to_the_explicit_value_projection_and_freezes_topic_ids` 已覆盖不匹配路径，但误断言 `ReplayReason.PROJECTION_MISMATCH`，属于断言语义失真。 |
| 复现或未验证限制 | 正常路径：`compile_config` 得到快照 → build value → replay → 合法更新 topics 声明并编译新快照 → 调用旧输入的 `value_prediction_context(changed, original_title_is_zh=False)`。预期 `BuildReason.PROJECTION_MISMATCH`，旧实现实际为 `ReplayReason.PROJECTION_MISMATCH`；两个快照均通过编译，不用损坏 frozen 对象制造错误。本次未运行历史反例；可在该提交的隔离副本运行下面的反例。 |
| 最小建议 | 共用投影核对按调用面选择原因类，context 使用 `BuildReason`、replay 保持 `ReplayReason`，修正该公共测试断言。 |

历史反例：在缺陷提交的受控临时副本中，仅将上述测试的 `assert caught.value.reason is ReplayReason.PROJECTION_MISMATCH` 改为 `assert type(caught.value.reason) is BuildReason`（旧词表尚无 `PROJECTION_MISMATCH` 成员，直接访问会先触发 `AttributeError`），运行：

```bash
uv run --offline --locked pytest -q tests/test_stage_input_value.py::test_context_is_bound_to_the_explicit_value_projection_and_freezes_topic_ids
```

预期在 context 原因身份断言处失败，replay 的断言保持原样；若失败在编译、就绪或其他前置步骤，不能据此认定复现。核对基线的 [service.py](https://github.com/MeteoBoy4/PaperRadar/blob/152d95a82893ba8530674579b1b2f00481717448/src/paper_radar/stage_inputs/service.py) 与 [test_stage_input_value.py](https://github.com/MeteoBoy4/PaperRadar/blob/152d95a82893ba8530674579b1b2f00481717448/tests/test_stage_input_value.py) 已按此分面处理并补充反例，因此审阅该基线时应标明「历史缺陷已修复」，不能重复报告为当前缺陷。

## 结果检查表

- [ ] 主 agent 已把完整代码块传给两个子 agent，两轴各自披露工具、来源与完成状态。
- [ ] 发现引用最新适用裁决；已有裁决没有被误当成待裁决问题。
- [ ] 「缺测试」结论附现有用例核查；缺陷反例遵守公开前提，失败确实来自目标原因。
- [ ] 每条发现具备七个证据字段；未运行、未复现与来源缺失已明确披露。
- [ ] 硬要求、功能错误、测试缺口和可选建议分清；自动化已覆盖的机械问题没有膨胀成常驻指引。
- [ ] Standards/Spec 分列且顺序保留；没有因篇幅省掉关键证据或按数量凑发现。
- [ ] 只读与脱敏边界保持；没有把历史缺陷当成当前问题或把审阅未完成写成通过。
