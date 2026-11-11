# #184 私有系统 bus 视图与 preflight 诊断独立覆盖

本台账记录独立 D1 工程覆盖；不修改此前冻结台账、测试分母或回执，不产生 live 放置、认证、模型或安装资格。

## 接缝与数量

接缝为公开 `native_preflight` 的真实 fork/root-child 控制流，并继续调用公开
`run_traced_preflight`、`LinuxPlacementPlatform.manager_environment` 的实际固定
manager 检查循环。OS adapter 只替代权限、mount、受保护路径元数据、manager 命令和
cgroup/scope 边界；常规 pytest 不连接真实 bus/socket，不执行实际 loginctl、manager、
scope、namespace、mount、ptrace、认证、模型或网络。

| 独立未绑定模块 | 节点数 | 覆盖 |
| --- | ---: | --- |
| `tests/test_preflight_system_bus.py` | 28 | 双固定 bus 视图、root 保护链与只读绑定、降权前关闭句柄、失败阶段诊断、cold 模式和成功后重核 |

28 个节点分解：完整 traced 固定依赖恢复 1、缺失目录诊断 1、错误来源/设置 10、
manager/身份/执行链/未知/超时/信号诊断 12、cold 不需要 bus 1、cold 原生/未知退出 2、诊断流不可写仍保留原拒绝 1。

## Red → green 与拒绝边界

首个回归在修复前经真实 fork 进入实际 `_manager` 循环：固定用户 bus 可见，
私有 `/run` 下系统 bus 不可见，固定 `loginctl` 命令的离线 OS 回放因此返回失败，
公开入口得到精确 `placement_preflight_refused`。保留经核固定 `/run/dbus` 的私有
只读视图后，三个 manager 检查均取得各自固定成功响应，并抵达模拟 scope 边界。
测试在创建真实 scope 前退出；该成功只证明依赖视图及控制流，不证明 native/trace
或现场安装已成功。

第二个切片先确认原实现在拒绝时没有阶段诊断；修复后父端仅输出固定中文阶段和
受控类别，最终异常仍是 `placement_preflight_refused`。测试包含带秘密标记的
任意异常正文、工具 stderr、未列入映射的 ExecutionError、未知退出码、超时和信号，
只允许固定诊断；不新增 child-to-root 文件、写句柄或持久 Schema。

固定来源缺失、socket/目录类型错误、错误 owner、组/其他用户可写目录、目录/终点
symlink、替代 socket 路径、namespace 或 bind 失败均在产品身份前拒绝。manager
非 running、linger=no、anchor 非 active 继续在 scope 边界前拒绝；anchor 身份、
native/trace 类失败、未知失败、超时和信号均保持受控拒绝。三个永久降权调用前
核对全部设置 fd 和父端继承锁的 child 副本已关闭；父端继续持有原锁。cold 模式
不打开或恢复任一 bus；成功后仍重核 host 和 kernel raw policy。

OS 模型明确将固定目录建为不可组写；仅固定 socket 普通占位文件的 fstat 类型被
替代为 socket，真实 symlink 类型保持，因此 no-follow 负例不因模型覆盖而放行。

## 未验证行为

此离线模型不确认现场失败的唯一原因，也不产生 root-positive 证据。真实 root
保护链、目录/socket 可用性、私有 bind、产品 manager/linger/anchor、native scope、
profile attach、userns、cap/seccomp、ptrace 和 true exec-stop 仍须由所有者批准的
live 流程验证。完整 11 成员策略字节和原 marker 的复用须在实际新包逐项比较后
判断；本修复不修改这些成员的生成算法或源码。独立审阅、合并树兼容/静态/Schema/
固定范围审计及获授权后的完整离线门禁由 integration 收尾负责。
