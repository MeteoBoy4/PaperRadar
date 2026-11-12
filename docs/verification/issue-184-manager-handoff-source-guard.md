# #184 manager 与准备恢复的 v23 源码守卫收尾

本台账独立记录本次源码冻结及消费闭包，不扩大历史固定分母、旧 required 集合或旧组回执。
当前准入策略为 `pi-admission-v23`，沿用 v22 的原 84 个显式源码成员，无成员增删。
规范 JSON 向量的 SHA-256 与新增字面量 pin 均为
`803959899ae38d4d83d70d6f4a56654ee2439180fa50a757b5e167d0d86c0073`。
旧 v1–22 向量与 22 个原 pin 保持原字节，v22 追加进入历史向量参数化回归；
旧覆盖台账和 ADR 正文不改写。

本次向量只更新实际变化的五个源码成员摘要：`scripts/seal_live_bundle.py`、
`live_evidence/live_bundle.py`、`live_evidence/preparation_retirement.py`、
`pi_execution/current_binding.py` 与 `pi_execution/placement.py`；后四项均位于
`src/paper_radar/`。生成后独立重读全部 84 个实际文件，比较新旧显式成员集合，
并逐项核对原 22 个向量摘要及 pin。native C、正常认证刷新、旧 ADR 与锁文件均保持原字节。

| 测试选择 | 节点数 | 公开行为 |
| --- | ---: | --- |
| `tests/test_live_admission_source_guard.py` | 25 | 当前策略、字面量 pin、显式成员和实际源码一致；同版本源码编辑或向量重绑拒绝；原 v1–22 向量保全 |
| `tests/test_preparation_recovery_pending.py` | 16 | 最终源码通过真实守卫后，未知临时退休记录拒绝、默认入口兼容及已知临时记录保全 |
| `tests/test_preparation_recovery_refusals.py::test_pending_publication_is_never_guessed_or_overwritten` | 5 | 五个原已知临时发布位置均精确拒绝并保留原字节 |

上述 46 个节点使用未经替换的原 `pytest` 入口与实际 v23 向量；没有树外临时守卫替代。
源码更改后的旧 v22 守卫在实际摘要比较处失败；先将当前测试选择改为 v23 时，
尚不存在的新向量使真实测试失败，随后才更新生产常量、新向量与新 pin。

`test_live_bundle.py` 的当前 builder 负例和 `test_live_epoch_upgrade.py` 的源码副本
负例均显式选择 v23，继续保留原错误输入、精确 `source_guard_mismatch` 和无输出断言。
当前 Contract 的策略及清单链接同步指向 v23；刻意使用的历史版本保持不变。
最终集成树仍须独立运行 builder、epoch、全部准备恢复与 manager 组合及收口检查；
子工作树结果不转移为最终树结论。

本次只证明离线源码冻结与工程模型行为，不证明真实 manager、root 预检、kernel、
namespace、scope、认证、模型、网络、安装或激活成功。真实新封印仍由所有者审阅并执行。
相关行为与范围见[准备恢复覆盖](issue-184-preparation-recovery.md)、
[未知临时记录覆盖](issue-184-unknown-retirement-pending.md)、
[manager 覆盖](issue-184-private-manager-state.md)及
[公共契约](../contracts/live-evidence.md#封印放置策略生命周期)。
