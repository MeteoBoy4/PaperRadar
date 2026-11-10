# #180 独立放置工程覆盖

范围：[#180](https://github.com/MeteoBoy4/PaperRadar/issues/180)，依据父票最终 E-10/S-8/S-9 与子票两阶段澄清；架构见 [ADR-0060](../adr/0060-place-pi-in-anchored-user-scopes.md)，公共行为见[执行契约](../contracts/pi-execution.md#用户级放置与双阶段握手)。这是 D1 新增工程台账，不扩展 A1–A10、#140、#168 或历史现场回执的固定分母，不导入旧能力或写回历史向量。

| 独立模块 | 节点数 | 接缝与可证范围 |
| --- | ---: | --- |
| `tests/test_pi_placement.py` | 30 | 共享放置/正式消费者/受保护来源：阻塞封装，exec-stop 之前无目标动作，exec 后身份漂移拒绝，manager/linger/锚定门槛，握手退出/超时/协议分类，scope/slice/祖先/anchor ID，清理异常，resolver 摘要，两个消费者 preclaim 零业务副作用，临时拒绝与持久收紧，规范受保护 target 和当前规则观察 |

相关维护保持原节点数：`tests/test_pi_execution_launch.py` 18、`tests/test_pi_execution_review.py` 10、`tests/test_read_execution_resources.py` 7、`tests/test_read_execution_rpc.py` 14。维护将旧直接 Popen 替身迁移到共享 `PlacedProcess.execute` 公共边界，进程交接中断仍在领取后保留 outcome_unknown/原预算；准备阶段更早的受控放置失败使用实际新原因。测试支撑 `pi_execution_support.py`、`read_execution_support.py` 共用 `pi_placement_support.py` 的 Linux/systemd I/O adapter，实际 socket、SCM_RIGHTS、ptrace、Landlock、零 core 与 exec 继续执行。

开发期实测：新增模块 30 passed；正式双消费者、资源生命周期、RPC、准入及既有回归组合 172 passed；doctor 相关组合 57 passed；CLI compatibility 59 passed、退出 0；本票生产代码 mypy 与 Ruff 通过。开发子集不产生正式 verification-runs 回执，也不替代最终冻结树完整离线门禁。

现场仍未验证：真实 user manager/scope 的 PGID/fd/ptrace 支持、用户 manager/linger 与长期 slice 锚定稳定性、特权 observer 规则目标、非特权 userns 和 mount 与 ptrace 的组合、项目 resolver 只读挂载、认证/模型的实际 IPv4/UDP/DNS 与出站负对照。离线替身只复用当前系统 resolver；不声称已部署项目挂载、完成真实认证/模型或产生现场资格。若部署内核禁用 userns/ptrace，不授额外宿主 capability，继续拒绝并交 Live 封印集成及现场验收处理。

跨票集成责任：先合入认证基线策略，再升本票独立启动/准入策略；D7 以实际合并字节生成新向量、保留 v1–v6 历史字节。collector 共用 `prepare_launch` 或同一 `PlacedProcess`；collector 落地后补双方同函数结构断言。Live 部署生成受保护 `placement-target-v1.json`，冻结新封装与 resolver 源码，形成实际 unit/nft/observer 证据；最终集成方审阅本票触及的测试/支撑/源码与新增 ADR、台账登记漂移，按最终树精确重绑并执行统一门禁。
