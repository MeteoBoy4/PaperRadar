# Live v2 采集累计域独立工程覆盖

依据：[#178](https://github.com/MeteoBoy4/PaperRadar/issues/178)，消费
[#177 最终裁决 E-1/E-2、S-11](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6768256547)
及子票实施澄清。本台账是新的 D1 未绑定覆盖，不扩大 A1–A10 历史分母，不改写旧回执、
冻结 Schema、失败或旧源码守卫向量。

| 独立模块 | 节点数 | 公共接缝与独立判据 |
| --- | ---: | --- |
| `tests/test_live_collection_v2.py` | 22 | v2 Pydantic 计划／回执、`ProtectedCollection`、所有者 `receive/show`、冻结契约与 root Schema |

覆盖固定域与合并网络上限、并发 40/40 超额拒绝、预占后未知结果及重建重读、跨计划安全首停、
同类第三次与全局第六次边界、原因交错与其他模板成功不清零、合法续跑与历史篡改拒绝、
空准入轮取消、派发额度耗尽时新轮前拒绝、所有者接收及只读额度显示、v1 旧读者拒绝 v2、
未知版本拒绝、schema 1→2 显式 cutover／reopen、字段／类型／NULL／主键／UNIQUE 约束、
采集事实截尾拒绝及旧备份不能退款或清停止。7 个安全原因逐项参数化，预期来自裁决字面量。

开发期按 red→green 纵切核验格式、预占／重读、续跑、接收、CLI、恢复与耗尽边界。
本票变更后的独立环境实测：上述模块加既有 `test_live_evidence_*`、冻结契约 Schema／导出／
检查，以及 `test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`，
合计 209 通过。既有 Schema 一致性测试产生原表循环外键的 SQLAlchemy 警告，测试退出 0。
`mypy src tests/test_live_collection_v2.py` 检查 351 文件通过；触及文件的 Ruff 通过。

入口 `check-compatibility all` 已执行；acceptance 路径因本票修改固定 source 而报
`scope_drift`，未弱化旧测试或逐子票机械重绑，交最终集成对白名单实际字节重绑后复跑。
这不是兼容通过结论，也不替代最终冻结树的完整离线门禁。

本票不执行 root 部署、真实 auth／network／模型或所有者 receive／activation。
root 操作逐次预占的实际 collector 接线、封印部署的显式 schema cutover、现场持续性与
最终源码守卫／共享登记字节核对由 [Live 收口](../roadmap.md#module-live) 承接。
