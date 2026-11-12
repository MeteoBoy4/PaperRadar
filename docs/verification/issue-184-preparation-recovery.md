# #184 同完整策略的 preparing 一跳恢复独立 D1 覆盖

新增模块独立于历史固定分母、旧 required 集合与旧组回执。全部输入是合成站点、完整本地封印、原 epoch/ledger 和 AppArmor/proc/systemd OS 模型，不读取现场凭据，不进行真实 mount、namespace、profile load/remove、scope/ptrace、认证、模型、网络、receive 或激活。

| 独立未绑定模块 | 节点数 | 公开接缝及覆盖 |
| --- | ---: | --- |
| `tests/test_preparation_recovery.py` | 8 | `FailedPreparationRetirement.check/prepare` 的只读认证、显式 recover、旧日志/快照/来源与业务字节及元数据保全、idle 后再次认证；own preparing 前/后、新 marker prepared 后及 own prepared 后中断；预检失败保全和原候选重入拒绝 |
| `tests/test_preparation_recovery_refusals.py` | 62 | 全十一放置成员原字节；三摘要来源、原日志完整规范字节/严格版本/阶段；全部相关 `.new`、未知其他退休日志、缺失/错误 snapshot、非初始 marker/MAIN、kernel absent/partial；来源保护模式、链接、大小、读取竞态；完整 descriptor/epoch/pair/工具及站点/owner 输入/窗口连续性；严格三字段类型、自引用与递归链、既有停止与预算保全 |
| `tests/test_preparation_recovery_install.py` | 5 | 真实 `LinuxLiveHost` 接线和 `LiveDeployment.install(recover=True)`；首认领前拒绝普通安装；新预检先于旧业务首写；own prepared 后 MAIN retiring/archived/runtime/resources 中断，及同 SHA 重验、卸载和显式恢复 |
| `tests/test_preparation_recovery_sealing.py` | 6 | 公开只读派生器与 `build_live_bundle` 在最终 payload 前封入三摘要；新旧 failed descriptor 相同；冷进程 CLI 帮助、配对输入、缺原退休来源和 derive 动作拒绝；网络/SQLite 禁用守卫 |

合计 81 个独立节点。`tests/preparation_recovery_support.py` 复用原退役合成模型，先通过原公开 prepare 重现新预检失败，再从固定 staging 布局构造不同源码 payload；不绕过 tree/manifest、marker、原日志、epoch、原 MAIN 或 kernel raw 身份认证。保全比较排除 atime，保留文件 bytes、mode、uid、gid、链接数和 mtime。仅允许当前共享新策略 marker 按既有生命周期推进与本 payload own journal 新增。

首次 red 在原行为上拒绝新描述的连续性；公开 builder/CLI 在新增参数实现前分别因缺参数能力与 arguments_invalid 拒绝。开发阶段源文件变更使现有 v22 sourceguard 失效；树外启动器采用 v22 显式 84 成员清单和当前启动时字节摘要，仍调用原 assert_source_guard 算法。它不改历史向量/pin，也不是生产准入或最终资格；统一 sourceguard 冻结后必须从未替换的 pytest 入口重跑本台账与关联回归。原日志、快照与失败来源始终不改写；任何拒绝用例只证明 refusal/preservation，不记作成功恢复。

本覆盖不证明隔离后的产品 manager 查询、真实 kernel attach、完整现场预检或 owner 安装成功；新增源码与封印字节仍需所有者审阅并由 owner 执行。源版本统一、最终冻结、独立审阅及完整门禁由 Live 收口；见[路线图](../roadmap.md#module-live)、[决策](../adr/0066-recover-preparing-placement-across-source-payloads.md)和[公共契约](../contracts/live-evidence.md#封印放置策略生命周期)。
