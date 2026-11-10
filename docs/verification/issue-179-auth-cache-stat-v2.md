# #179 固定认证基线 v2 与 helper 临时资源工程覆盖

依据：[#179](https://github.com/MeteoBoy4/PaperRadar/issues/179)、[#177 最终裁决 E-3/E-10](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6768256547)、[ADR-0058](../adr/0058-allow-bounded-auth-cache-stat-evolution.md)。定义补充 [ADR-0059](../adr/0059-clarify-auth-cache-baseline-capability.md) 待所有者评审；它不重复方案授权。

## 固定行为与独立覆盖

| 未绑定测试模块 | 用例数 | 观察边界 |
| --- | ---: | --- |
| `tests/test_auth_cache_stat_v2.py` | 25 | 固定摘要、采集/当前绑定公用构造及受保护账本共享准入；原子替换与原地刷新保持适用；v1 不继承 v2 资格；新增/删除/改名、不可演进 stat、权限/属主/组/dev、链接/特殊节点、未知目录、compile cache、并发变化及遍历上限拒绝 |
| `tests/test_auth_helper_resources.py` | 5 | 真实离线合成 helper 成功/拒绝/超时、资源创建失败、删除不完整；HOME/TMPDIR 和 compile cache 位于独占临时根，退出删除可观察，模型不能读取持久认证根 |

沿已授权接缝执行 red → green：先观察原子刷新模块缺失、当前绑定仍采用 v1、helper HOME 仍为 credentials、临时资源创建异常未受控的失败，再实现对应纵切。不以重算期望放松禁止变化。

既有 `tests/test_live_admission_source_guard.py` 追加一项 v5 归档原字节回归，并改指独立新增 v6 清单；`tests/test_live_admission_review_fixes.py` 的冷进程负例使用当前清单文件名，继续分别验证源码篡改与同版本清单重绑被拒绝。旧五份 JSON 向量和摘要锚均保留，不覆盖历史字节。

`pi-launch-1.4.0-v6` / `pi-admission-v6` 绑定新 helper 布局和 v2 算法。新向量为 `tests/fixtures/live-admission-source-guard-v6.json`，显式新增 v2 算法、额度、v2 回执与账本错误权威，继续绑定已有封印部署构造源码；旧算法 `baseline.py` 原字节保留。集成其他启动策略后须继续升版并按实际合并字节重新登记，不复用本树的向量声明或旧证据。

## 开发验证

全部 Python 命令使用 `uv run --offline --locked`。最终检查使用本工作树独立 `.venv`，由离线缓存创建而未复制环境；冷进程与只读状态查询均使用同一工作树解释器。合入 #178 前的最终相关组合 266 项全部通过；`./scripts/check-compatibility all` 176 项全部通过，退出 0。触及的 11 个 Python 文件 Ruff、格式及严格 mypy 均通过。

最终提交前合入 `integration/issue-177-live` 的 `da8a39f`，保留 #178 的 v2 额度/历史/CLI 与冻结契约规则。新增 v6 守卫同步纳入 `ledger_errors.py`、`receipt_v2.py`、`collection.py`，按合并后实际源码重新生成；合并树相关回归 225 项全部通过，包含 #178 的账本 schema 升级、重开与列／索引一致性测试；归档向量／冷进程篡改守卫另测 10 项通过，Ruff 与严格 mypy 再次通过。

合并树以 base `da8a39fca93521322e4d1fd5b9e3cd04939ef36a`、target `integration/issue-177-live` 审计，退出 1，仅报告继承的 `baseline_drift`：`src/paper_radar/cli.py` 与 `src/paper_radar/contracts/schema.py`，传播到 A2-01、完整 A2、A3–A10；没有本票新增 current_change。本票保留该诊断，不重绑共享中央登记；由最终集成执行者按实际树白名单重绑、复审并运行统一门禁。

本票相对集成基线的差分不改 Schema、数据库表或迁移，不产生新 Frozen Contract；#178 已登记的 v2 Schema 与权威模型保留。只读固定范围审计使用显式 base `41f59888c35d264020bc0128cb7f4821e1695137`（合入 #178 前） 与 `integration/issue-177-live`；开发期审计退出 0、issues/affected_groups/baseline_issues 均为空。没有机械重绑既有组、扩大历史分母、添加 required 集合或写正式回执；最终集成仍须对实际新树重新审计并运行统一门禁。

## 未验证边界与承接

真实 Pi 1.4.0 订阅自然刷新、实际 Node compile cache 路径、现场权限与临时资源清理由 Live-07 在所有者审阅的新封印字节、批准计划窗口和额度内验收。本票仅本地离线，不认证、不联网、不调用模型、不 receive 或证据激活；不派发业务任务。

metadata 豁免不识别 writer，不证明完整写史，也不要求变化来自产品认证窗口；两项继续披露型。首次 v2 基线来自受保护批准采集，旧 v1 漂移不能自拍升级。准备资源与业务状态分离，失败不产生任务、attempt、预算或证据激活；清理失败拒绝模型准备并留给所有者处理现场资源。
