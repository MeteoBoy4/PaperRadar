# 阶段 B 双轴审阅修复

本片从 `935a6bec19aef5cc5c94a7dfcbe73aaafe327b55` 的独立工作树修复
#185/#206 的 Standards 四项与 Spec 三项。工程测试只使用合成 HTTP、Pi RPC、
Docling parser/worker、PDF 与注入资源/时钟；不访问真实实验资料、凭据或 token，
不执行 live，不重做所有者 HITL，不为科学或现场能力背书。
没有 Schema、表或 Alembic migration 变化。

## 七项处置

| 轴/发现 | 工程修复与边界 | 回归 |
| --- | --- | --- |
| STD-1 P2 | paper show/trace 封闭接收 PDF、ReadTask、接受、布局、提取、全文、组合及 StageInput 错误；保留具体受控原因、中文下一步，不展开输入、路径或原异常。沿原 Paper CLI Contract，业务拒绝仍退出 1。 | 14 类错误分别注入 show/trace；原有六类拒绝兼容，缺库指引仍含 db upgrade。 |
| STD-2 P2 | screening failures 接收 Body 根查询错误，按本命令 Contract 退出 2；不改变根用途或查询状态。 | database_failed 的具体原因、下一步及隐私断言。 |
| STD-3 P3 硬规则 | 根/PDF 轻量事实下沉 body.query_records；查询、选择与提取单向依赖；LayoutError 下沉 layout_errors，LayoutBody 下沉 layout_models，消除 runtime 与 typing 反向依赖，旧公共导入保持。纯结构移动与功能逻辑分提交。 | 复用正文选择、并发重核、版式、恢复和旧公共导入回归；原 DTO 完整 class AST、字段顺序、frozen 与三项 repr=False 均一致，不增加私有调用计数测试。 |
| STD-4 P3 启发式 | 候选与报告复用 storage.filesystem.publish_projection 的同目录临时发布；路径、业务校验及 DB published 状态留调用者。 | 复用 fsync/replace 故障、临时清理、旧投影保留、并发及冷恢复。 |
| SPEC-1 P2 | 带 artifact 的自动质量永久失败与所有者否决仍进入当前受阻规划和运行告警。按当前 PDF/当前正文筛选；歧义只告警，不新增论文槽策略。新正文合格后不持续算旧否决积压。 | 自动失败、人工否决、健康空报、歧义、新正文选择及旧报告原字节重建；容量仍为 5/3，历史和预算保留。 |
| SPEC-2 P2 | trace 经 Body.current_projection 与公共当前正文权威装配 PDF/提取/质量/来源，调用共享 evaluate_paper；Read 前置转换复用同一事实装配，领取仍额外检查全部 Body reasons。 | 已知缺 PDF、待提取、永久失败、通过、旧否决、多成功歧义及显式选择；实验自动队列仍拒绝。 |
| SPEC-3 P2 | reading failures 新增显式 database/data_root 的根中性只读查询并披露用途；兼容 --root 原列表 stdout，stderr 披露用途。retry/reclaim/实际执行仍保留实验根和原资格守卫。 | 三种根用途×新旧位置形式、缺库不创建；主库/业务库存不变。 |

只读连接沿用 SQLite mode=ro；WAL 库可能维护标准协调 sidecar，不能解释为完全无文件系统副作用。
这不放宽恢复 replay 对其 DELETE-mode contents 只读且无 WAL/SHM 的既有断言。

旧组合额外暴露：提取快照的 Read stage 未 READY 时，失败查询重建抛出 StageInputError。
同一合成库在基线与修复源码均复现。现仅对明确未 READY 返回
mapping_determinable=false；其它缺失/损坏保留受控错误，不创建任务或后继，不领取或重置预算。

## 红绿与 D1 范围

新增未绑定 D1 模块，不改变 A1–A10 的成员、required 集合或历史分母；
`stage_a_verified=false`。收集与实际执行分别记录，零 skip/deselect 才记为通过。

| 新模块 | 收集数 | 能力 |
| --- | ---: | --- |
| tests/test_stage_b_review_query_errors.py | 29 | 14 类组合错误×show/trace，以及 Screening 根查询错误 |
| tests/test_stage_b_review_read_failures.py | 7 | 三种根用途×新旧位置，以及缺库只读边界 |
| tests/test_stage_b_review_trace_facts.py | 3 | 当前正文投影、已知无 PDF、未就绪 Read 配置 |
| tests/test_stage_b_review_report_quality.py | 3 | 自动质量、人工否决/旧空报、新选择/歧义/历史否决报告 |
| 合计 | 42 | 独立 D1，不进入旧回执 |

有效红回路：

- 纠正为原 Paper 退出 1 后，公开基线 src 的独立合成 CLI 对照为 15 failed、12 passed，
  1.03 秒。七类漏接组件×show/trace 与 Screening 根错误确实失败，已有六类×两命令保持兼容。
- 最初 trace/自动质量两例为 2 failed，36.60 秒；人工否决单例为 1 failed，20.33 秒。
- 根中性七例为 7 failed，1.46 秒。
- 追加 StageInput 转译、未就绪 Read 配置及新正文报告三类接缝为 4 failed、27 passed，42.98 秒。

原始输出及准确命令元数据保留于 `/tmp/paperradar-206/review-fix-*.log` 与同名 JSON。
早期错误的 exit2 预期、运行中修改源码导致的模块缓存 ImportError、缺 extra 的探索、
未完成结构组合及一次错误 StageStatus 导入造成的 collect failure 均仅作开发诊断，
不算最终通过，也不构造正式 run。

## 冻结与验证责任

v27 阶段使用显式 273 条准入源清单：原 271 条保留，追加两个下沉权威模块。
v1–v26 向量及既有 reviewed 摘要保持原字节；旧源码修改/同 key 重绑负例保留。
两个旧 guard 消费者在该阶段仅适配 v27 selector，原拒绝断言保留。
主会话已精确审阅 273 条源摘要、19 个触及源与下沉角色后批准冻结 v27；向量 SHA-256 为
`7527179b22cc6020985bedd9f66bbd2893a8d727aaf53ee9e7f5ba249c9396b5`。
v26 向量 SHA-256 仍为 `d3000d203a1b680c760abc852bfcb915dac40229d1d840242c93f5b0ab8b6ec5`。

随后按同一无循环规则收拢 typing 反向依赖，原 DTO 原样下沉独立 layout_models，
启用新 v28，而不重绑已冻结 v27。v28 显式 274 条源，保留 v1–v27 原向量及摘要；
其向量 SHA-256 为 `cd6ad7bb74b954002e40db4d5c6e7bb861f0be7108811b1b3a80607bb89d044e`。
新增下沉模块经过角色与每条源哈希审阅，两个 guard 消费者当前仅适配 v28 selector；
原解释器和源码编辑/同 key 重绑负例不变，历史 archive 增加 v26/v27 参数，未减旧分母。

最终定向组合、静态检查、兼容组合与只读 scope 审计的准确退出码、耗时、源码前后身份
在交接中列出；中央 hash、scope、分类、S3 和完整 gate 均由主会话负责。
本片不运行完整 check-offline，不授予 Live、生产消费、正式校准或阶段 A 结论。

## 实际验证分阶段记录

各行是独立开发期进程，不是同 run 或完整门禁。每行原始 `.log` 及命令/退出码/入口耗时
`.json` 位于 `/tmp/paperradar-206/`；短名是该目录的文件名前缀。源码快照分别保存在
`review-fix-v27-frozen-sources.json`、`review-fix-v27-final-query-sources.json` 与
`review-fix-final-sources.json`，前后均实际复核，旧快照不冒作后继树身份。

| 阶段/范围 | 结果（pytest 数量） | 退出 | 入口实测秒 | 原始短名 |
| --- | --- | ---: | ---: | --- |
| v27 初次功能树：Read/claim/retry/恢复 | 29 passed | 0 | 673.899 | review-fix-stable-read |
| v27 初次功能树：报告容量/故障/恢复/候选 | 46 passed | 0 | 1226.418 | review-fix-stable-reports |
| v27 初次功能树：正文选择/版式 | 48 passed | 0 | 923.453 | review-fix-stable-structure |
| v27 初次功能树：guard/两个消费者 | 82 passed | 0 | 354.980 | review-fix-stable-guard |
| v27 初次功能树：D1/旧查询 | 1 failed / 95 passed | 1 | 367.000 | review-fix-stable-d1 |
| v27 查询修正树：完整 D1/旧 trace/查询 | 96 passed | 0 | 309.812 | review-fix-final-query-tests |
| v27 查询修正树：CLI 兼容 | 59 passed | 0 | 100.324 | review-fix-final-query-compat-cli |
| v28 DTO 移动树：新增 D1 + 受影响版式/故障/恢复 | 54 passed | 0 | 440.550 | review-fix-v28-layout-d1 |
| v28 DTO 移动树：源码守卫/两个消费者 | 83 passed | 0 | 338.234 | review-fix-v28-guard |
| v28 DTO 移动树：CLI 兼容 | 59 passed | 0 | 105.701 | review-fix-v28-compat-cli |

初次查询唯一失败为原有 Screening-only scope 断言，公开基线同一测试亦失败（1.46 秒）；
装配端随后收窄为显式快照、当前 PDF 明确缺失、无任何 PDF/提取/Read 事实才保旧范围，
完整 96 例实际转绿。待提取、有正文歧义、Read 未就绪或已有 Read 历史仍保留 Read 映射；
省略快照仍为 partial/task_mapping_unknown。旧断言未修改。

`check-compatibility all` 在未重绑范围下实际选择 176 节点，61 failed / 115 passed，
退出 1，入口脚本 512.93 秒；原始短名 `review-fix-stable-compat-all`。
失败集中在 scope_drift 与前置级联的验收/回执模块；八个 CLI 模块无失败，最终 CLI 另行实际通过。
未刷中央 hash 或改 scope 消除失败，最终 all 由主会话在合并、白名单重绑及 S3 后统一运行。

v28 最终 Ruff、format check 与 strict mypy 覆盖全部 27 个触及 Python 文件，各自退出 0；
原始短名分别为 `review-fix-v28-final-ruff`、`review-fix-v28-final-format`、
`review-fix-v28-final-mypy`。完整新增 D1 仍为 29/7/3/3 = 42 例；
受影响组合实际收集并执行 54 例（42 新增 + 12 既有选定节点），无 skip/deselect。
源码守卫另实际执行 83 例，CLI 组合实际选择并执行 59 例，无 skip/deselect。
这三个 v28 进程前后 20 个触及源的 SHA-256 均与已审快照相同；274 个准入源逐条匹配 v28 向量。

只读 scope 审计以稳定 main `6f0c4e93d43b86cf25e87d90bf5130e7533d19d1` 为 base/target，
退出 1，2.282 秒，101 条 confirmation_required；未请求全量 collect。
它是提交前诊断，不是对最终提交的 S3 签收；原始短名 `review-fix-final-scope`。
scope、中央 hash、分类与 required 集合在本分支均未修改；主会话须对合并后的实际树重新审阅。
