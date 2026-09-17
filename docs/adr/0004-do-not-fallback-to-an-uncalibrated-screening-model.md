# 不自动切换到未经校准的筛选模型

PaperRadar 第一版为 Screening Agent、条件式复用升级和 Read Agent 各显式配置一个主模型，调用失败时有限重试并留待以后恢复，不自动跨模型或跨供应商 fallback。正式筛选校准只绑定 Screening 侧模型、提示词、Profile、输出契约、升级参数和规则；Read 模型不进入校准门禁，可以在运行 Read 前另行版本化选择。用户显式更换 Screening 侧语义组合时，系统先暂停自动精读并要求把变化附理由分为 minor 或 major；PydanticAI 只隔离供应商接口，不能以协议适配为名静默换模型。
