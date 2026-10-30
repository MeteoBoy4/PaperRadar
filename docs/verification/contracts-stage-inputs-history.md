# 阶段输入 Contract 历史证明范围

以下原文迁自基线 `2ad8f354e8d2497719b22eb1a543223d4c8d98aa` 的
[`docs/contracts/stage-inputs.md`](../contracts/stage-inputs.md)。这是既有恢复测试覆盖说明，
不是本轮验收结果；原文未提供独立执行日期或运行记录，不从这些描述推断当前测试通过、
真实 Docling/Pi、来源合法性、生产消费、校准、完整阶段 A 或 NAS 恢复就绪。
现状接口与消费者前置以[阶段输入契约](../contracts/stage-inputs.md#隔离恢复跨进程与后续消费者义务)为准。

## 隔离恢复、跨进程与后续消费者义务（迁入原文）

#53 通过真实 compile/load、临时 SQLite、[ArtifactStore](../contracts/artifact-store.md#公共服务)
与[备份/恢复公共服务](../contracts/backup-restore.md#公开边界与使用)验证历史输入重建。
调用方明确传入合成规范事实、载荷和独立期望指纹；原配置、原数据库与原数据根移走后，
新进程只从恢复库加载完整历史 snapshot_id，并从恢复后的 `get_artifact` 返回记录中
重新取得 original_pdf/source_snapshot 的 payload 与 extraction 的 reading/evidence_map
成员哈希，再组装引用。测试不会把旧成员哈希或旧 StageInput 对象作为恢复事实带入。
恢复和纯计算均不隐式 compile、upgrade、安装、激活或任务续跑；恢复数据库保持 DELETE
原字节，构造、回放和比较前后不变。此路径不修改 A3 备份算法或格式。

不同 PYTHONHASHSEED、cwd、主题集合枚举及映射构造顺序均匹配同一独立固定向量；
fixture 含两个启用主题，实际顺序变化受到断言。摘录/locator 顺序、精确 Unicode、空白
与换行仍按其语义保留，不能为了跨进程稳定而归一化。四阶段共同测试还以文件、SQLite
与网络 I/O 拒绝哨兵验证纯构造/回放/比较；架构检查保持 config/screening 公共面单向依赖。
无日志设施时结合空 caplog、repr、异常和 stdout/stderr 检查敏感内容不外泄。

[恢复固定向量](../../tests/fixtures/stage_inputs/recovery-v1.json)只含合成材料，
配置投影按手写 Profile、模型默认值、冻结 Schema/manifest、Prompt、adapter 语义及两主题
独立核算；extraction/reuse 复用先前已固定的投影 ID。阶段载荷和 SHA-256 未由 builder
生成，普通测试不会重写期望：

| 案例 | 输入格式 1 指纹 |
| --- | --- |
| boundary | `2f03c2722378c7d45971c9f3629884b962b806515f8625d0159fc2392de6aac3` |
| value | `8604eb842877279a6aca4aa9174d180569ea4dc6341e90ab25fa148b070b9df7` |
| extraction | `d108b2cc6e9ebe37a6cba1e832916c5d530c3b3fee0c2e795826eeb9ebf0e56d` |
| 结构化 reuse | `8a457a1e793ada05122c1d02a718ef3969442b50f44be855fbdb80273541a6ac` |
| 正文 reuse | `63debebc1c9dc39aef214ef8e663a2b5b2a13bd15636c2cae01d37dbf8e10644` |

历史 A5/A6/A7 证明范围与文件数量见[既有证据索引](doc-unification-history.md#阶段输入历史证明范围)。
