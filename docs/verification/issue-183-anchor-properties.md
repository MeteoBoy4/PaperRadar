# #183 anchor 空执行数组与 resources 中断替换：独立 D1 台账

本台账覆盖固定宿主读取接缝及明确 `resources` 中断的替换恢复，不扩充既有组成员或历史分母。
详细规则归属 [Live 契约](../contracts/live-evidence.md#固定模型采集闭环)。

| 公共接缝 | 本轮覆盖 | 限制 |
| --- | --- | --- |
| `LinuxLiveHost.unit_properties` + `validate_unit_identity` | systemctl 省略空数组时只凭六条明确 D-Bus 空数组通过；数量、签名、结构、非空、重复键、解析失败、工具失败与任意 unit 输入拒绝 | subprocess 边界为离线替身；不把缺字段默认为空，既有 unit 身份拒绝另由原测试覆盖 |
| `LinuxLiveHost.verify_resources_stopped` | 固定 anchor inactive/PID0、项目无其他进程；已有 nft 表拒绝且不删除 | 合成 cgroup 文件与只读工具替身，不证明真实 kernel 控制 |
| `LiveDeployment.install(recover=True)` | 精确旧新 payload/manifest、原 legacy 归档、原 journal 和已发布资源；普通安装、其他 phase、prior journal、未知字节、target、旧新 epoch、strict/model 来源、stopped、已登记计划及同 collector 别名拒绝 | 仅已核无执行史的 resources 中断；不泛化部分安装，也不清未知状态 |
| 恢复时的历史与中断 | schema1 旧计划保留后在正常初始化阶段迁入 schema2；已有 schema2 的 live-177 非零 auth/model 预占、失败/stopped、账本字节/审计与真实意图来源（仅+a内核替身）保留；旧 collector-history 字节保留；旧观察保留、pending observer 来源拒绝；停止/核空失败、资源删除、runtime 归档及旧 journal 发布后的续行 | observer 用实际冻结源码闭包，其他 OS 操作仍替身；无 root 现场修改 |
| builder 与源码身份 | `/usr/bin/busctl` 精确路径/SHA 封印；admission v14 新向量与独立 pin，v1–v13 向量及 pins 原字节保留，launch v9 不变 | 新源码自然派生新 collector/计划身份，不保留伪旧身份；不授予准入 |

新增未绑定模块逐个计数：`tests/test_live_anchor_properties.py` **19 项**；
`tests/test_live_resources_replacement.py` **28 项**。原源码守卫增加对 v13 归档字节的核对，
原 builder 的篡改测试维护为 v14 当前向量；未减少既有断言或用例。

没有 SQL、表定义、migration 或 wire Schema 变更。既有 schema1→2 初始化和 Schema
一致性检查继续运行，包括 `test_collection_schema_constraints_are_preserved_after_upgrade`、
`test_schema_cutover_reopen_and_missing_fact_history_refuse` 与 `tests/test_contract_schema.py`。
开发期还运行原 builder、宿主规则、部署生命周期、所有历史源码向量，以及发布产物变更触发的
`check-compatibility acceptance`；具体命令与结果记录在树外实施交接，不代替最终冻结树门禁。

真实用户 manager 的固定 systemctl/busctl **只读**回放从 `anchor_extra_commands` 转为通过；
它只说明本次实际空数组读取及已有 unit 身份投影可接受，不能证明新包已安装、nft/cgroup
恢复、cache 迁移、epoch 初始化、正常 OAuth 刷新、模型采集、receive 或显式激活。
这些 live 行为均未在本变更执行。共同授权窗口、网络确认原文、累计域、历史和停止事实由
既有封印与所有者新字节审阅继续约束，不从本次离线测试取得现场资格。
