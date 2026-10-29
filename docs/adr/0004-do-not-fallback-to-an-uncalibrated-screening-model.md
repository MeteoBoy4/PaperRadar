# 不自动切换到未经校准的筛选模型

状态：决策记录（原文未单列接受状态）；日期：原接受日期未单列；正文补充／修订日期：2026-10-11；依据：[基线裁决原文](https://github.com/MeteoBoy4/PaperRadar/blob/91e5d02e199f1921ca8afd2b7bdb8f257e6264f3/docs/adr/0004-do-not-fallback-to-an-uncalibrated-screening-model.md)；补充／部分取代：[ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md)。

2026-10-11：模型调用边界按 [ADR-0026](0026-control-pi-through-a-bounded-rpc-adapter.md) 改为 Python 控制的 Pi RPC adapter；本次取代原 PydanticAI 实现选择，有限重试、显式模型与禁止自动 fallback 的决策继续适用。

PaperRadar 第一版为 Screening Agent、条件式复用升级和 Read Agent 各显式配置一个主模型，调用失败时有限重试并留待以后恢复，不自动跨模型或跨供应商 fallback。正式筛选校准只绑定 Screening 侧模型、提示词、Profile、输出契约、升级参数、适配器语义和规则；Read 模型不进入校准门禁，可以在运行 Read 前另行版本化选择。用户显式更换 Screening 侧语义组合时，系统先暂停自动精读并要求把变化附理由分为 minor 或 major；Pi RPC adapter 必须核对实际模型，不能以协议适配为名静默换模型或切换权威输出通道。Pi 的隐含 retry 与 compaction 关闭，一次 attempt 最多一次模型调用，同一阶段输入的最多两次尝试由 Python 统一计数。
