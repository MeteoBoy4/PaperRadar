# #184 部署 epoch 升版谱系：独立工程覆盖

本台账只覆盖本地部署时钟继承切片，不扩大既有固定验收分母，不表示新策略已封印、已部署或 Live 完成。来源为 #184 所有者批准的专用入口升版前置：保留原共同窗口、网络确认原文、原部署 epoch／72 小时目标及既有历史。功能契约见 [Live 正常认证刷新闭环](../contracts/live-evidence.md#正常认证刷新闭环)。

## 独立 D1 范围

新增未绑定模块 `tests/test_live_epoch_upgrade.py`：**42 项**。通过公开 `build_live_bundle`、`LiveDeployment.install`、`initialize_epoch`、`read_epoch` 验证：

- 真正 installed 的旧封印输入，negative 首轮 start/cancel 后以明确来源升级；四份旧 received、原 epoch 字节和 40/40 余量不变。
- 原 UTC 及 72 小时目标继承；刻意推迟 now 不重置，模型资格／刷新源仍未评估。
- descriptor 的 payload／runtime manifest／model manifest／首 plan／epoch SHA 错配，旧 epoch 缺失／篡改，以及新来源冲突在首次历史或退役写入前拒绝。
- owner 原文微变、窗口缩短／延长、产品／模型／站点身份变化在构建输出前拒绝；受控源码副本篡改继续触发源码守卫。
- retiring 的 previous／history、旧 model manifest 篡改拒绝；五处 host 阶段中断，以及 archive／runtime／epoch 原子发布后中断，同字节恢复。
- 一次真实 auth 预占后的 interrupted／stopped、失败链、撤销事件和受保护 intent 字节保留；已有 cutover 而日志缺失拒绝。
- 多代 epoch 线性回放、原始来源再次篡改拒绝；新计划有执行史而 epoch 丢失不能重建。
- 两份新增部署 metadata Schema 与权威 Pydantic 一致；非法 SHA、非 UTC、unknown 字段拒绝；原 v1 epoch 模型 AST 保留。

旧 `tests/test_live_bundle_lifecycle.py` 的 successive 升级节点只维护输入为相同 site／window 与显式来源；原 archive、journal 和幂等断言均保留。共享 `live_bundle_support` 只增加可注入的历史 source、site、window 和 descriptor，不减少原测试分母。

## 验证结果

- `uv run --offline --locked pytest -q tests/test_live_epoch_upgrade.py tests/test_normal_auth_refresh.py tests/test_live_collection_v2.py`：69 passed，116.99 秒；此轮新增 D1 为先完成的 41 项。
- 随后新增的原 v1 AST 保护节点：1 passed；新增 D1 合计 42 项，均已运行通过。
- `uv run --offline --locked pytest -q tests/test_live_evidence_contract.py tests/test_live_evidence_receipt.py tests/test_contract_schema.py`：27 passed。
- 经树外测试 helper 输入注入固定历史 source_root，维护后的原 successive 升级节点：1 passed。没有替换生产代码、守卫或安装状态机。
- 七个受影响 Python 模块的 mypy、Ruff check、Ruff format check 通过；`git diff --check` 通过。

本切片先有缺 descriptor 升级仍被允许的红回归，再补拒绝；继承接口的红回归为缺少新来源模型。开发途中计划成员连续性检查的调用顺序曾导致夹具失败，已移至所有计划来源写完、任何构建输出创建之前，组合回归随后全部通过。

## 字节保护及未验证范围

相对 `f7d9e4c3e40e3521bb8a3a115721f1f2230972da`，旧 `contracts/` 与 `examples/contracts/` 的 **12 份 schema.json + 12 份 manifest.json**、16 份 v1–v16 源码向量、16 个已审 pin 及原 `NormalAuthEpoch` AST 均保持。旧 receipt v1/v2 与既有 Schema 无迁移或重绑。新 `docs/schemas/` 仅保存两份独立部署 metadata Schema，不加入 receipt Frozen Contract 登记。

历史 v16 source_root 只作为不可变封印输入和离线状态机材料；新 builder 加历史源的合成候选不作为新的可执行包成功证据。当前切片不推进 launch/admission、向量或 pins；最终所有源合并后，完整新包与新策略源码守卫闭包由后续集成统一重验。

未运行完整离线门禁、真实 profile／scope、network、认证、模型、receive 或激活，未读取／写入实际 root 现场和私有 baseline；未 push、开 PR 或合并 main。内核／现场和供应商真实到期继续未验。
