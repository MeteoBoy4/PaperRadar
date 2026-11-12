# #184 私有 /run 的 manager 状态查询独立覆盖

本台账是新增 D1 工程覆盖，不扩大既有验收组、历史分母或回执，不产生现场安装或执行资格。

## 接缝与数量

| 独立未绑定模块 | 节点数 | 覆盖 |
| --- | ---: | --- |
| `tests/test_preflight_manager_state.py` | 18 | 私有 `/run` 遮住 boot marker 时读取同一 user manager 属性；17 类状态、输出、退出码、工具和 bus 拒绝 |

复用既有 `PreflightModel` 的普通真实 fork 和 OS adapter，从公开 `native_preflight`
进入真实 `run_traced_preflight`、`LinuxPlacementPlatform.manager_environment` 及真实
`_manager` 循环；不替换 `_manager`。权限、mount、路径元数据、外部命令及 scope
边界由离线 adapter 替代，抵达模拟 scope 边界即退出，不创建真实 scope 或 ptrace。

## 源码行为模型与红绿

模型按独立字面量解释两条查询，不从生产常量推导成功：

- [systemd v259 is-system-running](https://github.com/systemd/systemd/blob/v259/src/systemctl/systemctl-is-system-running.c#L32-L35)
  在取得 user bus 前检查 `sd_booted()`；随后读取 manager 的 `SystemState`。
- [sd_booted](https://github.com/systemd/systemd/blob/v259/src/libsystemd/sd-daemon/sd-daemon.c#L742-L754)
  检查 `/run/systemd/system`。因此旧命令在 user bus 仍可见、boot marker 被遮时得到
  非零退出和 `offline\n`，不读取实际 manager 的 running 属性。
- [systemctl show](https://github.com/systemd/systemd/blob/v259/src/systemctl/systemctl-show.c#L2275-L2307)
  对无 unit 的查询直接取得 manager bus，不经过该 boot-marker 检查。

首个公开入口回归在修复前实际失败，固定诊断为
`放置预检拒绝：阶段=产品 manager；原因=依赖不可用。`，最终异常精确为
`placement_preflight_refused`。记录中两个固定 bus 已绑定、用户 bus 可见且 boot marker
不可见。仅改第一条固定查询后，实际模型状态 `running\n` 且 code 0 才到模拟 scope。
固定绑定集合仍只有用户 runtime 与 `/run/dbus`；host marker 存在，私有 marker 未创建。

17 个负例分别覆盖 degraded、unknown、starting、initializing、stopping、maintenance、
offline、空输出、缺换行、多换行、重复行、大小写偏差、非零退出、信号退出码、OSError、
TimeoutExpired 和用户 bus 缺失。每个负例都精确断言受控 manager 诊断及最终拒绝，
不进入后续 linger/anchor/scope，不泄漏注入异常正文或工具 stderr。
既有 linger、anchor、保护链及阶段诊断回归继续保持，相关旧模型仅维护新查询的精确 argv。

## 材料与验证边界

本次开发期相关组合为新模块 18、`test_preflight_system_bus.py` 28、
`test_pi_placement.py` 31 及 `test_sealed_placement_preflight.py` 14，共 91 个节点；
这不是完整离线门禁或正式组回执。
旧 ADR、旧覆盖台账、历史证据和旧 pins 保持原字节。代码及旧测试的实际字节变化会产生
预期运行时 guard/源码绑定漂移，由 integration 在最终候选统一审阅和重绑；此处不修改
`current_binding`、不升候选版本、不新增 guard 或重包。

该模型依据源码描述外部命令行为，不是实际 systemctl、mount、namespace、降权、
profile、scope、ptrace 或 root preflight 成功证明，也不能判定现场 122 的唯一原因。
宿主只读属性查询的 code 0 / running 观察与私有视图模型是不同证据；真实封印预检、
认证、网络和模型行为仍未由本次验证。跨候选恢复由另一个独立变更承接。
