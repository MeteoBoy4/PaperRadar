# #162 单篇 Read Pi 执行组合覆盖

## 交付范围与依据

依据 [#162 正文与补充评论](https://github.com/MeteoBoy4/PaperRadar/issues/162)、
[#155 裁决链](https://github.com/MeteoBoy4/PaperRadar/issues/155)。本台账只登记新的 D1 工程覆盖，
不进入 A1–A10 required 或固定分母，不扩大历史回执。产品 read_evidence 恒 None；
任何离线替身成功均不表示 EXP-2 或真实执行准入成立。

新增 `read_execution.ReadExecution.run_attempt` 组合，与 ScreeningTasks 独立。
直接复用 admission、prepare_launch、run_call、安装保护和 PiRpcExecutionAudit，
经 ReadTasks.run_pi_once 进入既有唯一 v2 接收/原子保存权威，没有第二份 Read Schema。

顺序为同根 Read 资源 → 明确历史描述 → 本次绑定准入 → 完整最坏修正预算/实际帧 →
安装保护与认证 → identity 重新绑定 → 短事务最新资格/修正/ordinal → 一次 RPC → 一次结算。
等待不占 attempt，也不先刷新短期 token；准入和预算同时失败时准入优先。
每次 attempt 新进程组、私有目录与独立 session，无 retry/compaction/额外 turn 或输出通道切换。

`ReadTasks.prepare_execution` 新增只读加载边界；明确本次 audit_snapshot_id 必须已对该任务登记，
Read 投影与首次相同。新 Read 审计记录另外保留该快照引用，PiRpcAudit 格式 3 不变。
历史无该字段的记录按首次配置保留验证，旧 JSON 序列化字节保持。
ReadTasks 的类型注解与输入重建改为延迟导入，空 Read 库的旧备份完整校验不加载 LLM，
结构/引用校验不跳过，A9 冷恢复 worker 与冻结测试字节不变。
PiReadFailure 只传封闭失败；test 端口仍只收 bytes，不增加 executor_kind 或模拟生产参数。

## 独立 D1 测试

收集 48 个节点；各模块均为新增未绑定模块：

| 模块 | 节点 | 观察边界 |
| --- | ---: | --- |
| tests/test_read_execution_admission.py | 18 | 产品缺失/不符/未实测证据拒绝；准入优先于超额帧；cwd/安装/认证/隔离/超时/根路径拒绝且无 attempt/auth |
| tests/test_read_execution_rpc.py | 14 | 独立进程/协议对端；首拒末次安全修正降级；两进程/两目录；唯一成功；超时/孤儿/环境/协议/cwd/modelMismatch/retry/compaction/额外 turn/重复完成/取消 |
| tests/test_read_execution_resources.py | 7 | 同根等待无认证/次数；auth及模型期安装在途保护；auth期间首尝试结算后使用最新修正；两类中断整组回收、未知恢复不退款；激活切换重绑拒绝；领取后启动失败 |
| tests/test_read_execution_history.py | 7 | 审计与首次语义两轴；当前settings失效不改历史；独立冷进程无原根/安装/执行实现/网络恢复、丢弃和来源保持、只读hash相等；供给/adapter/channel伪造及test冒充Pi拒绝；历史服务冷导入不取得执行能力 |
| tests/test_read_execution_logging.py | 2 | 明确所选根FileSink、默认NullSink边界；领取前零事件、闭集DTO、prompt/Profile/正文/候选/坏ID/stderr/auth/env不泄漏；汇失败不改变成功/次数 |

测试支撑为 `tests/read_execution_support.py` 与独立标准库对端 `tests/read_execution_peer.py`。
对端不导入产品消息生成器、Read Schema 或接收器；自行实现固定 RPC 消息与静态 Read JSON，
校验 new_session/prompt 各一次、工具命令为空、无私有数据库/凭据访问和无环境继承。
真实本机进程在临时根中运行；没有调用真实 Pi、认证、模型或网络。
私有准入 monkeypatch 仅到达后续工程路径；退出测试后产品仍缺证据即拒绝。
帧优先级负例在登记后收紧测试内存中的边界常量，不增加任何产品开关或持久准入事实。

## 验证与冻结边界

使用磁盘独立环境 `.scratch/venvs/issue162`，uv offline locked；只运行相关开发期 pytest、
CLI 兼容组合及静态检查，不运行完整 check-offline、真实模型或 live。
最终实测结果和最终树身份由实施外部报告记录，不把 run_id 或工作树摘要回写本固定台账。

A9 v1 源码、15 模块/560 节点、格式/版本和 A8 旧向量保持原字节；没有新增 migration，
不改中央材料哈希、固定 scope 成员、固定计数或分类控制数据。实际修改的既有契约若产生
登记漂移，连同 #160/#161 已继承漂移由 #165 按最终树精确审阅，禁止机械全重绑。
新增 read-execution Contract 按未知新文档视作固定材料，不扩大 live 分类白名单。

## 未验与承接

本覆盖不证明真实 Pi 1.4.0、模型质量/权限、订阅刷新、token识别、参数映射、cwd祖先资源、
TLS/DNS/主机出站或安装现场准入。Cwd/Live/B 承担 EXP-2；产品仍 fail-closed。
#165 承担真 PDF→真 Read→恢复组合及最终 S3/门禁；B 注入所选根 FileSink、产品 CLI、
真实样本/用途/质量与最小日报；F/G 承担正式 fixture/阈值和长文/队列。
Docling 独立锁与每日 quota 未扩张，不宣称跨阶段调度或正常生产 Read 已完成。

公共边界：[Read 执行](../contracts/read-execution.md)、[Read 任务](../contracts/read-tasks.md)、
[Pi 资源](../contracts/pi-execution.md)、[RPC](../contracts/pi-rpc.md)、[运行日志](../contracts/runtime-logging.md)。
