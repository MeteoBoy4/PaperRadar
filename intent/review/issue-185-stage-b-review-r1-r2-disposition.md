# #185 Stage B r1/r2 逐项处置

起点：`integration/185-stage-b` 的 `3a25e6574d50348f8ea7f92cb8961f028e4fa024`。
本次由单一 fresh implementer 在 `fix/185-review-r1-r2` 实现；不推送、不合入 main。
两份原审查报告保持原字节，SHA-256 分别为
`e455a9d304210eda933f9ff7a3c8300f0bc32593a55e97d0127f1ab6e1e47546`
与 `ff43c56a952f2ef0fcf16c28277189aebe521122e4ca7b18edead9f80eeb1640`。

开工初判不需要 migration；核实后发现原 `report_runs` 有
`CHECK(renderer_version=1)`。根会话批准为原有章节要求新增唯一线性
`b009_report_renderer`，承接 `b008_body_selection`，只扩展 renderer CHECK，
保留旧 migration、原报告及历史冻结输入。没有改写需求来认可整体 unknown。

## r1：六项

| 项 | 判断与处置 | 判据 |
| --- | --- | --- |
| README 复制 Contract 细则 | 接受；开头收敛为能力摘要及 Contract 导航。 | 不重复维护 cgroup 数值、预算、重放、根布局等详细前置规则。 |
| 任意 str 原因／状态 | 接受边界问题；九类产品错误规范化到各自封闭 StrEnum；未知运行时值映射 invalid_reason，原值不进错误输出。MappingReceipt/RpcMappingResult 状态封闭，RPC 原因复用 RpcReason。 | 有效既有原因保持；非法原因九例修前失败，修后通过；映射非法 state 受控拒绝。 |
| probe_mapping/run_call 重复 | 不采纳生命周期框架重构。 | run_call 有 DispatchDenied 穿透、before_prompt、audit.initialized/terminated/cleanup_failed；probe 无 prompt，初始化后关闭 stdin 并核正常退出。两者 cleanup 审计与异常责任不同，合并扩大准入关键修改面；本票没有复现其功能错误。 |
| Reports 多职责 | 不拆整个模块；采纳与 r2 F3 重合的最小只读边界。 | ReportHistory 只公开历史、校验与暴露范围；底层无 output_dir，写入口先拒绝，不能留下 prepared 事实。保留发布与重建现有公共边界。 |
| 仅数值合格 cgroup 被放行 | 接受。 | 当前 UID 的 user slice/user manager 精确归属，加有界 systemctl --user show 的 loaded/active/transient/Id/ControlGroup 核验；保 v2 mount root 映射、软链拒绝及领取前复核。普通组、UID/manager/状态不符不占预算。 |
| 元数据汇总无序覆盖 | 接受。 | 直接消费 JGRMetadata.result_in_connection，版本优先、observed_at/请求键排序完全沿用同一权威。旧成功／新失败、旧失败／新成功均有修前红灯。 |

## r2：八项

| 项 | 判断与处置 | 判据 |
| --- | --- | --- |
| Standards F1 visibility 去重 | 不采纳建议接口。 | calibration.visibility 是纯规则，只返回许可；把各产品异常类型注入它会反向耦合产品层。现有短守卫保留各自 capability 与错误语义。 |
| Standards F2 Stage 裸字符串 | 部分接受。 | required_categories 使用 Stage，selected_grants 接受 Sequence[Stage]；未类型化 CLI 输入先 parse_stages，运行时非法值仍受控拒绝。不要求每个已受类型检查的调用点常量改 Enum。--stage bogus 原来已正确拒绝，本次补具体 egress_scope_mismatch 回归，不伪造红灯。 |
| Standards F3 伪造 output_dir | 接受风险，实施最小 ReportHistory 接口。 | exposure/validation 不再把 data_root 冒充输出根；无输出目录的内核在 render/rebuild/replay 入口先拒绝，数据库事实不变。 |
| Standards F4 泛化 19 个 CLI 入口 | 不采纳。 | 各入口的受控异常集合、中断下一步及日志责任不同。未发现本次退出码缺陷，统一框架会触及大量无关入口与用户文案。 |
| Standards F5 持久 fact Pydantic union | 不采纳持久格式重构。 | primary_kind 已封闭；各事实按固定权威引用校验，未知 kind 不会静默接受；next_action 是冻结中文行动说明。引入新 union 没有本次功能收益，反而扩大历史冻结投影兼容面。 |
| Spec 1 trace selections 未过滤 | 接受过滤，拒绝“过滤后末条=current”。 | paper trace 仅返回该论文记录；current 仍由全根末条决定。A→B 时 A 的旧记录不成为 current；换回 A 后保留 A 两条及 B 历史 false。replaces 保原历史 ID，不伪造局部替换链。 |
| Spec 2 evidence 章节缺失 | 接受，采用源层级派生与 renderer v2。 | 从分析固定 artifact/三元组的已校验 evidence-map 读取 source orig、正文层级与阅读顺序，单独冻结 evidence_sections；不改 Read Schema/analysis_payload/源文。v1 保原输入与 Markdown，升级、备份与冷恢复仍逐字重建。 |
| 日志 §8/§34 冲突 | 澄清具体契约，不改安全行为。 | restore/replay 使用恢复封装 SESSION/views 的 FileSink；只读历史和派生重建不发运行事件，因此不建 logs，保持 §34 输出闭集。组件注入日志汇不等于实际发事件。 |

## 回归与兼容边界

已完成的开发检查如下，耗时为 pytest 自报值；所有命令在独立 worktree 内运行。

| 命令／日志 | 结果 |
| --- | --- |
| `uv run --offline --locked pytest tests/test_stage_b_review_followup_cli.py tests/test_stage_b_review_reasons.py tests/test_stage_b_report_renderer_migrations.py tests/test_stage_b_review_source_history.py -q --basetemp=…/d1-final-36`；`d1-final-36.log` | 冻结源码完整 36 passed，退出 0，无筛除／跳过，328.64s。 |
| `uv run --offline --locked pytest tests/test_stage_b_review_followup_cli.py tests/test_stage_b_review_reasons.py -q --basetemp=…/d1-first`；`d1-first.log` | 首轮 24 passed，249.48s；新增 RPC 非法状态随后由完整 reasons 模块覆盖。 |
| `uv run --offline --locked pytest tests/test_stage_b_review_reasons.py -q --basetemp=…/reasons-final`；`reasons-final.log` | 12 passed，0.85s。 |
| `uv run --offline --locked pytest tests/test_stage_b_report_renderer_migrations.py -q --basetemp=…/migrations-fourth`；`migrations-fourth.log` | 10 passed，61.26s。 |
| `uv run --offline --locked pytest tests/test_stage_b_report_renderer_migrations.py::test_v1_upgrade_backup_and_cold_restore_keep_exact_report_bytes -q --basetemp=…/v1-existing-originals`；`v1-existing-originals.log` | 收紧为现存原根 OS 拒读后，1 passed，65.07s。 |
| `uv run --offline --locked pytest tests/test_live_admission_source_guard.py tests/test_stage_b_review_source_history.py -q --basetemp=…/guard-v29`；`guard-v29.log` | 31 passed，0.39s。 |
| `uv run --offline --locked pytest tests/test_stage_b_review_followup_cli.py::test_report_metadata_health_uses_observed_time_not_request_key -q --basetemp=…/metadata-final`；`metadata-final.log` | 2 passed，3.62s。 |
| `uv run --offline --locked ruff check .`、`ruff format --check .`、`mypy` | 均退出 0；1873 文件格式保持，1333 Python 文件无类型错误。 |

`…` 统一指 `/tmp/paperradar-185-review-r1-r2`。首次真实红灯日志为
`trace-red2.log`、`metadata-red.log`、`cgroup-red.log`、`sections-red.log`、
`reasons-red.log`；对应原始症状分别为跨论文额外授权、双向健康误判、
普通组消耗 attempt、缺章节以及任意原因原值进入错误边界。

独立新增覆盖、准确模块数量和 fixture 身份见
[D1 台账](../../docs/verification/issue-185-review-r1-r2-coverage.md)。
原始开发日志在 `/tmp/paperradar-185-review-r1-r2/`，未写入正式验收回执。
最终确认使用专用临时根；首轮 compat 默认共享 pytest 根的例外见以下实测，
没有手工读取或清理共享残留。业务材料均为合成 HTTP/Pi/parser/资源与注入时钟。
冷恢复实际运行产品子进程与 OS 隔离，材料全合成；原 db/data/config/materials
保持存在且可读，断言隔离核验通过、missing_originals=0、originals_denied≥4，
再核 v1 Markdown 原 SHA。没有访问用户实验根、真实凭据或真实 runtime checkout；
没有执行 live、完整离线门禁或发布 A 结论。

开发时另尝试两个“跨版本”夹具，诊断证明 DOI 补全保持同一 version_id，
故该构造并未覆盖不同版本优先。错误构造在冻结前撤回，失败诊断日志保留于树外；
不改变共享元数据权威，不把该尝试记为通过。原两方向无序请求回归保持。
含该错误构造的 `related-first.log` 实际退出 1：76 passed、1 failed、5 deselected，
826.67s；`mapping-and-metadata.log` 实际退出 1：91 passed、1 failed，22.67s。
不把这两条完整命令记为通过，也不把未选节点计为通过；最终新增 36 节点已独立完整重跑。

首轮 `./scripts/check-compatibility all` 实际退出 0，176 passed，pytest 397.51s，
含 uv 总耗时 398.33s。首轮未设置 TMPDIR，使用默认共享 pytest 根；退出时自动
清理旧 garbage 目录出现 Directory-not-empty 警告。日志 `compatibility-all.log`
保持原样，不把该警告解释为产品失败，也不手工读取或清理共享目录。
最终确认另以专用 `TMPDIR=/tmp/paperradar-185-review-r1-r2/compat-onlytmp` 重跑同一组合。
`compatibility-all-isolated.log` 实际退出 0，176 passed，pytest 404.50s，
含 uv 入口总耗时 405.40s；无跳过或筛除，使用独占临时目录。

原 285 模块/5281 节点、41 条 refs、required 集合及旧验收材料保持各自范围。
v29 的显式源码闭包只在原 274 文件上新增被直接消费的 reasons.py；
v1–v28 manifest 原字节保持，v28 独立历史保护放新 D1，不扩大旧参数列表。
源材料登记重绑只按根会话审阅的精确路径/旧新 SHA/全部消费者执行。

现场剩余：用户 cgroup/systemd 部署、真实 Docling 峰值与章节保真、供应商参数效力、
NAS 及用户原样本恢复均未在本次验证；既有 #202–#205 和完整门禁只保留原 SHA 的历史范围。
