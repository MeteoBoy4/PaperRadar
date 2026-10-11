# Pi 决策后的现有交付内容适配复核

2026-10-11。按用户要求核对现有代码、配置、提示词、冻结契约、持久化、依赖、CLI 和离线验收材料；适配依据为 [ADR-0026](../../docs/adr/0026-control-pi-through-a-bounded-rpc-adapter.md) 与 [V1 规格](../draft.md) §7.6–§7.7。

## 修改与保留依据

| 内容 | 核对结果 | 处理 |
| --- | --- | --- |
| 模型调用代码 | 当前只有配置与输出验证，尚无 LLM/PydanticAI/Pi 执行器 | 无可替换的旧调用实现，现有生产代码不需要修改 |
| models 配置 | 配置 Schema 已接受 prompt_only；旧示例使用 json_schema，已版本化且历史示例有固定快照身份 | 新增 models-pi-v1，不覆盖 models-v1 或 models-reuse-v1 |
| 配置选择 | selector 可变，但旧示例仍承担已交付验收语义 | 新增 settings-pi.yaml，复用既有合成 Profile、主题、升级参数、三阶段提示词与四份契约 |
| 协议枚举及参数 | json_schema/json_object/prompt_only 和模型参数均已登记入不可变材料与快照；配置完整性不探测真实能力 | 保留枚举、参数默认值和编译行为，补充 Pi 目标协议与未来执行检查说明 |
| Screening 验证 | 单一 Pydantic 权威、受控类型、上下文业务校验、无效 JSON 与字段拒绝已存在，独立于 transport | 不修改输出 Schema、公共验证器或受控 vocabulary |
| 冻结契约 | 四份业务输出契约不包含模型调用协议，生成与只读漂移检查来自同一权威 | 官方与 examples 两套 v1 快照均保留，不重导出、不新建无语义变化的契约版本 |
| 提示词/Profile/主题 | 现有版本是工程合成材料，明确不用于真实调用或正式校准 | 不将它们改造为生产材料，也不原地改写版本 |
| 数据库/migration | 新示例使用已有 models 材料种类和登记格式，历史回放不需要新结构 | 不修改 migration、快照格式或用户数据库 |
| Python 依赖/lockfile | 不含 PydanticAI；当前配置与验证不需要 Pi/Node 或外部模型 | 不增加依赖、不修改 lockfile |
| 既有测试与验收身份 | json_schema fixture 验证历史配置；禁止导入 pydantic_ai 是契约层隔离检查，不是调用实现 | 保留固定测试、辅助材料和验收哈希，新增独立 prompt_only 配置回归测试 |
| README/配置契约说明 | 缺少与新决策一致的配置示例，未来投影依赖表遗漏适配器语义 | 增加新示例用法、现有交付边界和未来阶段/校准投影依赖 |

## 新配置的实际范围

[settings-pi.yaml](../../examples/config/settings-pi.yaml) 选择 [models-pi-v1.yaml](../../examples/config/models/models-pi-v1.yaml)，Screening 与 reuse_assessment 两个槽使用 prompt_only，reading 为 null。boundary、value、reuse 与 suggestion 只达到配置完整，Read 和 extraction 未就绪。provider/model、Profile 与提示词仍为合成材料。

当前 config check/compile 不执行 Pi、不选择真实模型、不检查认证或操作系统隔离，也不启用校准或自动精读。submit 工具协议与 Pi 运行策略材料尚未开放；没有新增隐藏 selector、自动 fallback 或第二套业务 Schema。

## 已运行的核对

- 最小相关离线测试：新配置、旧协议历史、版本保护、配置服务、业务 Schema 与冻结检查，共 90 项通过。
- 新回归验证：prompt_only 材料成功编译且重复编译幂等；删除所有示例源文件后仍从数据库回放；旧 json_schema/json_object 快照可加载；同版本原地切协议拒绝且不损坏历史。
- examples/contracts 四份冻结契约的显式整组只读检查通过；各 Schema SHA-256 与权威生成结果一致。
- 新测试文件 Ruff 静态与格式检查通过，git diff 空白检查通过。

完整仓库离线检查通过与否以本轮实际运行输出为准；此复核不构成 Pi RPC、正式校准、生产 Read 或 live 模型验收。
