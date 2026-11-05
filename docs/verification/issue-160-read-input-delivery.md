# #160 Read 输入与领取前预算 D1 覆盖

依据：[#160](https://github.com/MeteoBoy4/PaperRadar/issues/160)、[#155 裁决链](https://github.com/MeteoBoy4/PaperRadar/issues/155)、[ADR-0044](../adr/0044-freeze-read-input-rendering-and-preclaim-budget.md)。

公共 seam 为纯 `ReadFacts/build_stage_input/replay_stage_input`、持久正文到
`prepare_read_input` 的组合，以及 `read_input_budget/build_read_correction/render_request`。
资格、用途、领取和调用不在纯输入层判断，后续任务服务在同一领取事务复核。

## 独立模块与数量

| D1 模块 | 完整节点数 | 覆盖 |
| --- | ---: | --- |
| `tests/test_read_stage_input.py` | 27 | 格式 1 严格回放、三元组、语言、非法/额外事实、PDF 与书目方向、历史配置、Screening/校准隔离、Profile/Prompt/adapter 变化、未知版本拒绝 |
| `tests/test_read_inputs.py` | 10 | 持久读取与 v2 预检、完整 UTF-8 帧阈值两侧、最坏修正、纯超额重算、身份替换、冷进程禁 extra、候选无锚点、zh/en 与历史回放、独立请求向量、三接收规则不影响模型输入 |
| 合计 | 37 | 独立未绑定 D1；不进入历史 required 或固定分母 |

手写最小正文与独立 UTF-8 向量位于 `tests/fixtures/read_inputs/`，没有改 A8 的
Screening 向量。父票故事 18–22、25、34 在本票覆盖输入层；故事 23–24、26–33 的
任务、独立会话、analysis、恢复、用途及可见性组合仍由后续 Body 消费者覆盖。
本票的语言和配置回放证明输入可重算，不代替持久任务或分析恢复。

## 冻结变化与漂移处置

用户已明确批准五处等量冻结预期更新：

- `tests/test_stage_inputs.py` 与 `tests/test_stage_input_extraction.py` 的 build 负例将
  `StageName.READ` 换成裸字符串 `read`，继续验证字符串冒充阶段被拒绝。
- `tests/test_stage_input_replay.py` 与 `tests/test_stage_input_extraction.py` 中相同 Read
  字节负例从 unsupported_stage 改为 invalid_payload，继续拒绝缺失合法 Read facts 的载荷。
- `tests/test_a5_acceptance.py` 的公共只读版本表预期仅新增 `StageName.READ: 1`；
  TypeError 只读保护不变。

授权依据：[原四处](https://github.com/MeteoBoy4/PaperRadar/issues/160#issuecomment-6646336005)、
[第五处](https://github.com/MeteoBoy4/PaperRadar/issues/160#issuecomment-6646690676)。
对应四模块节点数保持 20、33、38、106。没有 skip/deselect 或删除节点。

`scripts/a5_acceptance.py::_formats()` 显式消费 A5 原四阶段，而不枚举新增 Read。
其四阶段生产版本校验及 16 个异常向量保留，材料哈希检查不变；Read 能力只由本 D1
证明。上述四冻结模块、StageInput 语义以及这个实际消费者的精确 diff，均交 Body 最终树
逐组 S3 审阅；工具分类为 source/support 不替代对验收格式影响的人工审阅。
本票不机械重绑中央哈希，不产生 S3 人工确认。未处理的漂移不表示审计通过。
A9 v1 源码、15 个冻结模块、计数和规则格式，以及 A8 旧向量保持原字节。

## 验证边界与移交

开发期采用 `uv run --offline --locked` 相关 pytest、触发的 CLI 兼容检查及静态检查。
实际命令和结果记于交付报告；既有 1013 功能节点、59 CLI 节点与 mypy 结果只说明其
所测树，收口新增差异另行验证，不作为最终完整门禁结论。
`stage_a_verified=false` 保持；未运行模型、完整离线门禁、live 或产品 CLI。

后续 Read 任务服务应直接消费 `PreparedReadInput`，在领取前检查 `budget.accepted`；
实际修正必须使用 `build_read_correction`，预算预留与实际渲染共用 `llm/read_limits.py`
的冻结常数。超额返回 `read_input_over_budget`，不得占 attempt、截断或另建原因表。
事务消费者仍须核对正文当前性、质量、根用途、Pi 准入和业务预算，不能把纯输入准备
解释为执行许可。

B trace 与 G 复用相同纯计量入口。G 负责通用长文与 map/reduce；F 负责四刊正文质量、
复杂版式及通用资源阈值；B/Live 负责真实来源、现场 Pi 与真实纵向闭环。
当前离线输入覆盖不证明这些现场行为或完整阶段 A/B 完成。
