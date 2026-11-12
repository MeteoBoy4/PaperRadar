# #184 v24 失败准备事务集成

本次新增工程覆盖使用独立 D1，不进入历史验收组成员或扩大固定分母。
完整离线门禁仍由 #184 收尾承担；功能子集、类型检查和封印一致性不授予现场执行资格。

## 源码身份与历史

当前 `pi-admission-v24` 的源码守卫有 85 个显式成员：原 84 个加
`live_evidence/preparation_void.py`。放置策略为 `pi-placement-v3`；启动策略
`pi-launch-1.4.0-v10`、隔离策略 `pi-landlock-v1` 与固定 Pi RPC 协议保持。
源码向量 v1–v23 和各自摘要锚保留原字节；当前向量的消费者明确选择 v24，
同版本改源码及重绑清单仍拒绝。v23 加入归档向量逐项检查。

两个真实诊断原因分别是私有 `/run` 隐藏 loginctl 所需真实 systemd 启动标记，
以及 pre 身份核验时只读打开 post 的权限遗漏。新构建封印预检协议 2，旧已封包
缺失字段沿旧解释。原目录只读绑定与固定 post 读取权限分别修复这两个原因；
普通认证/模型执行范围不增加，native 和 supervisor 有限诊断不传播原始输出。

## 独立新增覆盖

| 模块 | 节点数 | 主要边界 |
| --- | ---: | --- |
| `test_native_policy_audit.py` | 20 | 完整 native 操作与策略核对、静态入口、受控拒绝、关闭诊断管道 |
| `test_prerequisite_report_v24.py` | 12 | 全部独立前提汇总、依赖受阻、有限消息 |
| `test_preflight_boot_marker_v24.py` | 16 | 原目录保护链与只读绑定、root 有限诊断 |
| `test_preflight_protocol_v24.py` | 9 | 新协议选择、历史缺失字段、未知版本与类型拒绝 |
| `test_native_preflight_diagnostics_v24.py` | 67 | 冷/完整预检、握手前后有限检查点、恶意或不完整消息拒绝 |
| `test_preflight_supervisor_v24.py` | 28 | scope、状态字段、SEIZE、释放、exec-stop、DETACH、退出 |
| `test_preparation_void.py` | 22 | 归档、六持久化边界、kernel 中断、失败回滚与再恢复 |
| `test_preparation_void_descriptor.py` | 2 | 严格描述 Schema、规范恢复 |
| `test_preparation_void_install.py` | 5 | 报告失败前零写入、业务首写与策略事务责任界线 |
| `test_preparation_void_baseline.py` | 5 | 零操作、候选无证据与旧历史保留 |

合计 186 个新增节点。测试中的 native OS adapter 不执行真实 mount、AppArmor
加载或网络操作；已有 ptrace 测试仅操作测试子进程。历史测试替身增加显式报告
接口，未提供模型时主动拒绝，不能默认冒充所有前提通过。类型收窄保留原失败
原因断言，并明确区分 native、manager 和 supervisor 异常。

## 验证与现场边界

合并后直接使用项目 `uv run --offline --locked …` 验证上述模块、既有安装/
退役/恢复/额度/刷新/native 关联回归、Contract Schema、数据库 Schema 幂等性
及 CLI compatibility。最终树与测试命令、结果、材料审计身份记录在树外报告，
不在本文写入 run_id 或回写历史回执。

用户本轮明确跳过代理独立 review；新 root 字节仍须所有者亲自审阅与安装。
原失败包、journal、marker、快照和历史额度只追加保全。作废记录和回滚只有
在实际 root 命令执行后才成为现场事实；离线测试不表示已经完成归档、清理、
部署、站点/模型采集、自然刷新闭环、接收或证据激活。
