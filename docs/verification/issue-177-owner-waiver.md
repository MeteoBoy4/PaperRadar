# 所有者豁免与可选后置 Live 的独立工程覆盖

依据：[#177 所有者裁决](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6814413453)与 [ADR-0068](../adr/0068-replace-live-prerequisites-with-explicit-owner-waiver.md)。本台账独立登记新能力，不扩大 A1–A10 历史分母、required 集合或既有回执证明范围。

## 范围与保留

- 显式所有者动作持久保存版本；缺失默认严格，非法/损坏记录失败关闭，流水线不写开关。
- Screening 与 Read 的三检查点检查同一选择；豁免只免证据前提，test 来源仍拒绝普通消费，业务 attempt/预算保持。
- 关闭后新采集、接收及激活须晚于恢复边界；旧 verified、激活和回执保持原事实，但不能复活资格；备份恢复保留边界。
- doctor 单列豁免原因与 ADR，不冒充任何能力通过；未评估仍为 not_assessed。
- 可选放置使用宿主 resolver；固定 argv/env、Landlock 文件/TCP 权限、零 core、NNP、认证 helper 分离及临时根清理保持。
- 所有者卸载工具先汇总预检、认证身份并归档原字节，只移除明确部署；不加载策略、不改 journal，历史和累计额度原样保留。

## 新增 D1 模块

| 模块 | 节点数 | 覆盖 |
| --- | --- | --- |
| `tests/test_owner_live_waiver.py` | 22 | 动作、持久化、两消费者、doctor、损坏/撤回/恢复及重新取证 |
| `tests/test_owner_optional_placement.py` | 6 | 无放置宿主 DNS、文件与 TCP 拒绝、core/NNP、默认严格与失败清理 |
| `tests/test_live_uninstall.py` | 15 | 聚合预检、身份拒绝、原字节归档、全历史保持及卸载失败边界 |

## 既有测试逐项处置

证据链、采集、部署模块的既有测试全部保留；默认无豁免的产品拒绝断言原样保留。
`tests/test_live_bundle.py` 与 `tests/test_live_epoch_upgrade.py` 仅将“当前源码守卫”的测试材料引用从 v24 改为 v25；仍验证篡改源码拒绝，不删除或放宽断言。
`tests/test_live_admission_source_guard.py` 将当前向量推进 v25，并把 v24 纳入原字节归档检查；历史 v1–v24 向量与摘要锚不改写。
不修改已有 frozen contracts、数据库表定义或 migration；新增动作使用独立种类的现有配置版本记录，Schema 一致性与备份恢复另行验证。

## 开发期验证

相关 pytest 子集 622 项通过：默认消费者 189、隔离／来源／源码守卫 170、保留证据链 106、部署／Schema 83、新功能与相关恢复 74。
最后一项包含上述三个新模块的 43 项和原恢复模块的 31 项；旧模块原字节保留。
CLI 兼容组合 59 项通过；全仓 Ruff、格式检查及 mypy（1192 个文件）通过。
源码准入策略推进 `pi-admission-v25`，启动策略推进 `pi-launch-1.4.0-v11`，显式守卫 86 个成员；隔离策略与 `isolation.py` 原字节不变。
旧 v1–v24 向量／摘要锚保持，旧 ADR 仅在状态行添加取代关系，不改正文。

## 证明限制

定向离线回归与全仓静态检查不代表完整门禁通过。完整离线门禁只在所有者明确要求后运行。
合成对端不证明真实认证、DNS、模型或供应商行为。实际主机卸载须所有者本人执行，未执行不能声称已卸载。
证据链仍可按原计划、窗口、额度、接收和激活规则复验；本裁决不生成新封印包、不重置 40/40、不修改 v22–v24 候选字节。
