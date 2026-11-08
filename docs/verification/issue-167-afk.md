# #167 AFK 离线探索与后续工程边界

本次基线 `c0bee235f4ebb0a88be4a60c392c96619ec61683`，工作起点 main、clean。#167 原生 blockedBy 为已关闭 #140（1/1），subIssues 为0/0；票无评论。只执行 A1–A7 可离线部分；票仍需 H1–H5，不声明整票完成。没有运行 Pi/Node、认证 CLI、真实模型/刷新网络，没有读取认证或 token 派生值，也未提权、修改宿主策略、激活证据。

## 交付入口

| 项 | 产物与本轮结论 | 保留的限制 |
| --- | --- | --- |
| A1 | [事实矩阵](issue-167-facts.md)：六个 I/T、11 个 DERIVED，固定源码20项哈希 same | 源码身份不是现场实测；历史low不能覆盖high |
| A2 | [文件观测原型](issue-167-observation.md)、`scripts/issue167_observation.py` | 只对合成树/声明窗口验证，非产品公开接缝；新目录竞态/事件丢失unknown |
| A3 | 同一原型的分层事件计数与独立参照，[固定请求路径](issue-167-request-paths.md) | 合成元数据对端，不是实际HTTP hook；固定SDK是否可无改动完整观测需H4 |
| A4 | [部署候选](../../intent/review/issue-167/deployment-plan.md)：双worker、unit模板、出站/DNS/IPv6、core及卸载恢复 | 未路径化/安装；unit桥接/core行为/实际nft仍未验，H1审阅实施，不能直接进入认证 |
| A5 | [生命周期原型](issue-167-lifecycle.md)、`scripts/issue167_lifecycle.py` | 合成collector/签名/所有者通道，无生产接线、持久化或真实安全权威 |
| A6 | [现场计划](../../intent/review/issue-167/field-plan.md)及[六格封印](../../intent/review/issue-167/synthetic-manifest.json)：先无认证，再六格，最后单独故障批次 | 授权/现场值/实际观测手段未满足即不可执行，未知不豁免 |
| A7 | 独立未绑定测试、静态检查与只读固定范围审计 | 不写旧回执/分母/哈希，不运行完整离线门禁 |

## 后续产品工程要求

现有产品 `read_evidence=None` 继续阻断。原型不得注入测试私有 `_evidence_for` 或用外部JSON/Markdown/布尔覆盖权威。Live 后续工程须：

1. 在资源创建后、启动前、全部后代退出后但删除前、删除后提供受控无秘密元数据接缝，绑定同一attempt/安装/策略；终态成员集合、独立删除和全运行历史分别签收。原型的驱动声明不能替代可信cgroup观察。
2. 为prompt派发、auth CLI、TLS/packet、模型HTTP、WebSocket连接/response.create和刷新HTTP分别建立可信覆盖与独立参照。对预热、重试、重定向、缓存及观察器失败做完整性验证；未知值阻断，不把一次prompt或TCP连接算成一次HTTP；固定包替代provider的Codex Responses默认auto传输的WS重连及SSE降级不能漏计（首批openai不直接走此路径，出现即停止），总模型操作仍最多一次。
3. 实现固定策略的项目专用部署、失败回收/重启保护与core边界；不静默改变现有固定供给或全机core策略。H1/H4接受具体实现后才能形成现场证据。
4. 接收权威核验来源/完整性/授权计划/失败历史/消费者与档位及完整现场绑定，所有者单独激活；30天硬到期、漂移/失败撤销、逐调用现场复核、针对重验与影响不明扩围。持久状态须抗回滚，重启不能清空消耗或撤销；密钥/权限与所有者身份验证须独立设计，原型内存状态不能直接上线。
5. B 在完整Live准入后自行验收真实产品入口、用途/根/日志/预算及输入质量；本票不替代B/F/G/I职责。

## 验证记录的口径

测试数量按新增模块独立登记，不相加历史组合，不进入A1–A10 required集合。完整门禁仅在用户明确要求时运行，本轮未运行。证据中的“通过”限相应离线原型预期/拒绝路径，不表示现场隔离、订阅能力、参数效力、真实供应商错误、HTTP独立计数、产品准入或无人值守已通过。Live仍为待探索，B继续等待完整Live。

本次开发检查（均用 `uv run --offline --locked …`，缓存前缀 `UV_CACHE_DIR=/tmp/issue167-observation-uv`）：

- `pytest -q tests/test_issue167_materials.py tests/test_issue167_lifecycle.py tests/test_issue167_observation.py`：52 passed；按模块分别2、29、21项。
- 定向 `ruff check`、`ruff format --check`：6个新增Python文件通过。
- `MYPYPATH=src … mypy scripts/issue167_*.py tests/test_issue167_*.py`：6个文件通过；需显式源码路径，不能以跳过未类型化安装包掩盖结果。
- `./scripts/audit-verification-scope --json --collect --base c0bee235f4ebb0a88be4a60c392c96619ec61683 --integration-target main`：退出0，issues/affected_groups为空，固定测试只收集未执行，未重绑旧登记。
- `git diff --check` 与新增文档本地链接核对通过。未触及公共CLI、包导入链、验收组/回执接线，无兼容组合触发。

收口时无未解释固定材料漂移；新测试仍独立未绑定。全部检查为开发结果，不能称完整门禁或现场准入通过。
