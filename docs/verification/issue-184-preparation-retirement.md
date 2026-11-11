# #184 固定 true 与失败准备退役的独立 D1 覆盖

新增模块不加入历史固定测试分母、旧 required 集合或旧组回执。测试使用合成站点、完整本地封印/manifest、原始 epoch 与 ledger，以及显式 AppArmor/proc/systemd OS 模型；不读取现场配置或凭据，不执行真实 profile load/remove、namespace/mount、scope/ptrace、认证、模型、网络、receive 或激活。

| 独立未绑定模块 | 节点数 | 公开接缝及覆盖 |
| --- | ---: | --- |
| `tests/test_fixed_true_policy.py` | 6 | 固定 true 的 direct/symlink resolved renderer；真实 compile-only parser 和静态 native 编译；新 build 关联缺失、错误 source 与工具身份漂移拒绝 |
| `tests/test_failed_preparation_descriptor.py` | 6 | 严格有限 SHA/身份描述；未知路径、命令、伪造 SHA、bool 版本和错误 pair 拒绝 |
| `tests/test_failed_preparation_host.py` | 4 | 实际 LinuxLiveHost 的只读 idle 接缝；保留已核 PID/start/exe 的 anchor，拒绝 native 与 controller |
| `tests/test_failed_preparation_retirement.py` | 36 | check 无写；完整来源/旧 MAIN/原 marker/kernel 认证；原 snapshot 耐久保全；有限阶段及 old/new marker 写后、旧单 profile remove、新 partial add、新预检失败后的显式恢复；未知 source、snapshot、journal、partial/额外/异字节/不可读 kernel 、原停止状态与不空闲拒绝 |
| `tests/test_failed_preparation_sealing.py` | 7 | 显式旧 runtime 派生及公开 builder 封印；native、source、build、site、旧 pair 连续性与全 manifest 身份拒绝 |
| `tests/test_failed_preparation_install.py` | 2 | LinuxLiveHost 与 LiveDeployment 公开 install/same SHA/uninstall/recover 接线；新预检先于旧业务首次写入，预检失败保留旧业务、epoch、余额、历史与候选 |

合计 61 个独立节点。`tests/preparation_retirement_support.py` 只提供合成封印与 kernel OS 模型，不绕过完整树、marker、epoch/祖先或 raw bytes 认证。旧 MAIN 的无 placement layout 是显式合成历史协议，不声称是某个实际旧封印。旧策略 binary 的合成 ABI5 literal 仅为 OS 模型输入；真实 parser 测试与该模型分别陈述。

恢复支持已拥有、可认证的稳定 intent/snapshot/marker 阶段、旧单 profile 已移除、新 partial add 和预检失败。未提交 `.new` 不凭其名字或看似规范字节猜归属，普通及 explicit recover 都拒绝并保持原文件；缺 snapshot、来源、主部署身份或未知记录同样拒绝。此类负例的通过表示 refusal/preservation，不能记为成功恢复。

开发中可在独立临时未来 source 副本生成仅供模型构建的未来 guard；这既非生产 v20 人工 review，也非实际源码 guard 正例。生产登记仍由统一 finalizer 进行，实际树的 builder/sourceguard 消费者须在该登记后重新验证，副本结果不能转移为集成树结论。

本覆盖不证明现场 canonical true exec、kernel attach、root bus 视图或完整预检成功；实际 owner 对新增归档字节的审阅、部署与 Live 验证仍独立进行。[决策](../adr/0065-retire-authenticated-failed-placement-preparation.md) 与[现状契约](../contracts/live-evidence.md#封印放置策略生命周期)分别维护规则与代价。
