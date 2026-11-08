# #168 / #169：准入登记与纯分项模型覆盖

本台账仅覆盖 #169 的公开登记与纯判定边界，不扩大任何历史 required 集合、组回执或固定分母。
ADR 0052／0053／0054 均为提议，G1 仍待所有者接受；本票不标完成、不开展 #170。
新 `live-evidence` Contract 和本票新增源码／测试／ADR 的分类与消费闭包由 #176 显式审阅收口，
本票不改既有 scope 或中央共享哈希，不改 #167 历史回执、状态、时间与字节。

## 公共 seams 与覆盖

经本次流水线授权，测试直接消费 AdmissionRegistry、evaluate_admission、earliest_verified_at、
受控词表和改名后的产品 loader；无网络、认证、模型、特权执行或用户数据库。
纯普通值不是账本授予来源，合成正例不接入产品。

| 独立新增模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_live_admission_registry.py` | 5 | 六格、完整分类、未定义用途、空必需集合、重复登记与期限参数 |
| `tests/test_live_admission_evaluation.py` | 48 | 三态与资格独立、披露未知／不适用、精确期限、时钟、覆盖、版本、材料、重复冲突、格隔离、21组件漂移 |
| `tests/test_live_admission_time.py` | 6 | 聚合最早UTC微秒时点与空／未知／naive／未来拒绝 |
| `tests/test_live_admission_reader.py` | 2 | 产品loader恒None，纯层冷导入无执行／存储依赖 |
| 合计 | 61 | 独立未绑定新增覆盖 |

`tests/live_admission_support.py` 仅提供合成内存事实。
既有 `tests/test_pi_execution_admission.py` 只改 reader 引用名，原15节点与语义保持；
两个 service 只改同一 reader 的导入／alias引用，私有工程测试接缝与旧三布尔模型保持。

## 开发验证与未证明范围

TDD 按登记、独立维度、供应商到期、时钟、水位线、覆盖、材料、冲突、聚合、reader 改名逐切片记录红灯后转绿。
开发期组合不发布正式 A1–A10 结论；同次全量 pytest 的退出约束不代表本票进入既有回执。
本票只运行相关 pytest、Ruff、mypy 和因 service 导入引用改名保守触发的 CLI 兼容组合，
不运行完整 `check-offline`。

免时限只检查显式输入的覆盖／特权证明组件集合，尚不验证其真实受保护来源；
完整模型元组、整树、host与认证／缓存元数据的可信构造、真实UTC时钟、账本水位线读取、
受信接收与人工证据激活、持久撤销和产品三检查点均由后继票承担。
本次没有认证／模型／网络采集、sudo、真实root部署或证据激活。

开发期实测：四个新增模块 5＋48＋6＋2＝61 节点通过，既有准入15节点保持通过；
两个消费者相关子集50节点通过；CLI兼容组合59节点通过（入口退出0）。
相关 Ruff 与 mypy 通过。只读 scope 审计退出0、issues为空；新消费闭包仍未纳入历史组。
这些开发检查不替代独立审阅、G1接受或最终树完整门禁。
