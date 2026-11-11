# 以固定零参数入口采集封印合成模型证据

状态：Proposed；依据：[#177 最终裁决 E-6、E-1/E-2/E-5 与 S-9](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6768256547)、[#182 实施澄清](https://github.com/MeteoBoy4/PaperRadar/issues/182#issuecomment-6768787557)。记录已经批准的边界扩展；补充 ADR-0055／#168 P-6，封印字节部署仍须所有者审阅。 认证事件证明来源与正常刷新语义由 [ADR-0063](0063-observe-normal-oauth-refresh-in-product-process.md) 补充。

首次模型取证不能依赖先具备模型资格，否则形成循环。固定零参数模型采集入口仅消费所有者批准的封印合成案例集合、站点完成历史、当前观察和累计额度；root 管理批准、逐操作预占、完成事实及 inbox，认证与模型保持不可逆降权后的产品身份，并复用正式 `prepare_launch`、`run_call`、同一放置及权威业务校验。正式消费者继续要求完整当前资格，采集入口不派发业务 task/attempt、不 receive、不激活、不自动续期。

六格按模板 ID 固定顺序，各用一份单案例 v2 plan 与完整真实 binding；这保留已经冻结的 v2 wire，避免同一回执把 low/high 绑定到同一个模型元组。封印库存只冻结可预知静态输入；部署后才成立的 cgroup、出网、observer 和认证基线由受保护站点完成事实与当前 root 观察生成确定性运行绑定并固定于账本区，后续精确比较，避免构建时未来值和包身份哈希自循环。四个 IPv4 负对照使用相同放置和无秘密 worker，root 在逐次 network 预占后，结合规则 counter、归属窗口、真实认证/模型成功及所有者适用性确认形成局部复合证据。errno、超时或 RPC 成功单独均不补足出网证明。

相比把放宽动作加入 NOPASSWD，本决定只增加有限采集能力；相比复制正式业务任务，它保持业务预算和独立取证授权分离。代价是维护封印库存、metadata-only IPC、受保护完成历史与故障清理，以及每次改变 root 字节后重新审阅部署。完整会话写史继续未评估；自然到期和真实刷新需要独立无秘密来源，成功调用和 metadata 演进不替代该证明。
