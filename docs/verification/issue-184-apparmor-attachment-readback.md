# #184 AppArmor DFA-only attachment 读回独立覆盖

本台账仅记录 attachment 证据适配的新增 D1 离线覆盖，不改旧冻结台账，不增加既有验收组成员或分母，也不代表真实部署资格。公共规则见 [Live 契约](../contracts/live-evidence.md#封印放置策略生命周期)；[ADR-0064](../adr/0064-authorize-userns-for-sealed-placement-entry.md) 的既有判据保持。

## 回归与证据边界

现场 metadata 的两个专用 profile 均导出 `attach=<unknown>`、`mode=enforce`、`raw_abi=v5`，独立 `raw_sha256` 与已审 binary 一致。非特权现场采集不能读取 root `raw_data`，因此它只提供导出形状，不证明真实 raw 字节相同。[内核 apparmorfs](https://github.com/torvalds/linux/blob/v7.0/security/apparmor/apparmorfs.c#L1113-L1126) 对有 DFA 而无 `xmatch_str` 的 attachment 导出该精确 sentinel。

独立未绑定模块 `tests/test_live_apparmor_attachment_readback.py` 使用已存在的离线 binary fixture、现场 handle/metadata 形状和公开 OS 接缝，不访问宿主策略。首个 tracer 在修复前以 `apparmor_attachment_mismatch` 失败（1 failed），仅修 reader 后通过（1 passed）；完成扩展后该模块实测 31 passed。

| 公开接缝 | 新增覆盖 | 数量 |
| --- | --- | --- |
| `AppArmorKernel.verify` | 精确 DFA-only sentinel 的完整封印读回 | 1 |
| `AppArmorKernel.check/load` | exact 只读复用，不写内核 | 1 |
| `AppArmorKernel.verify` | 异 raw 同 hash、错误 hash/ABI/mode、非规范 sentinel 与错误 literal | 11 |
| `AppArmorKernel.verify` | profile 缺失、重复、整包额外成员 | 3 |
| `AppArmorKernel.verify/check/load/remove` | changed revision、raw_data 不可读均受控 unavailable，无写入 | 8 |
| `AppArmorKernel.remove/check` | 显式 exact 退役后为 absent | 1 |
| `PlacementPolicyLifecycle.prepare/verify` | `recover=False/True` 均覆盖已知 preparing 恢复、未知 identity 和缺失 marker 拒绝；11 成员不变，不重新 load/remove | 6 |
| 合计 | 独立 D1，不进入旧回执 | 31 |

## 版本与保持项

`pi-admission-v19` 的新增 source guard 显式固定原 83 文件；仅 reader 与 admission 版本声明的源码摘要变化，`pi-launch-1.4.0-v10`、`pi-placement-v2`、原 native C/header/program/build/security/policy 算法和字节保持。v1–v18 guard JSON 与既有 pin 保留；增加 v16–v18 归档校验，当前 bundle/epoch fixture 指向 v19。

生产 `SealedPolicy` 继续来自已核封印树中的固定源码和 binary；本变更不提供调用方任选 binary 自证、策略替换、marker 接纳或完整 identity 变化后的升级路径。未修改实际 deployment、已有 preparing marker 或退役规则。

## 剩余验证

此处离线替身不证明实际 root raw_data 可读、与已审 binary 相等、真实 profile attachment/userns/mount/cap/seccomp/scope/ptrace 行为，也不执行认证、网络、模型、receive 或 activate。实际逐成员重包比对、现场只读复核、独立审阅后的最终完整离线门禁与后续 live 验收由 #177/#184 收口承接。
