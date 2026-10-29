# Issue #114 Feed 双轴审查（r1）

- 固定点：`main`（`543942c55b3357720cbaf0c4965ded0bdbff1044`）
- 审查命令：`git diff main...HEAD`
- 规格来源：GitHub Issues #114、#115、#116、#117、#118、#119
- 审查方式：Standards 与 Spec 独立只读审查；未修改代码、未创建 commit、未运行测试

## Standards

### 硬性违规

- **公共 Contract 未同步**：`docs/agents/documentation.md:3,20` 要求持久化行为与现状 Contract 同变更更新。
  - `docs/contracts/paper-facts.md:154` 仍写“**不建期刊关联**”，但 `feed02_title_language.py:17-20` 新增：
    > `CREATE TABLE feed_journal_bindings ... journal ...`

    且 `screening-tasks.md:485-486` 公开 `bind_feed_journal`。
  - `paper-facts.md:146` 仍称 304、限流、失败的取得历史“**仍由未来 task_attempts 承担**”，但 `feed_ingestion/service.py:182-243` 已将这些结果写入 `feed_production_checks`：
    > `checks.update().values(settlement_json=..., ...)`

- **新 Contract 骨架错位**：`docs/contracts/feed-metadata.md:49-57` 在“相关”之后继续规定封闭类型、`corrupt_reference` 和 SQL 错误路径；这些属于“规则／错误与拒绝”，不是出处。违反 `docs/agents/documentation.md:46-47` 的固定骨架及相关小节用途。

### Baseline smells（均为 judgement call）

- **Duplicated Code**：`papers/conflicts.py:22-27`、`feed_ingestion/repository.py:33-38`、`feed_metadata/repository.py:22-29`、`screening_tasks/feed_gate.py:40-45`、`language.py:168-169` 重复：
  > `json.dumps(... sort_keys=True, separators=(",", ":"))`  
  > `hashlib.sha256(...).hexdigest()`

  另 `language.py:354-365,377-390` 重复 resolution 解码、哈希及身份校验，宜提取共享校验。

- **Repeated Switches**：`language.py:131-137` 与 `229-235` 重复同一状态级联：
  > `"missing" if ... else "ambiguous" if len(values) > 1 else "resolved"`

- **Data Clumps**：`feed_metadata/service.py:151-153,419-421` 持续传递 `key + basis + route`，且把已有 `MetadataBasis` 降级为：
  > `basis: dict[str, Any]`

  宜直接传递领域对象及请求上下文。

- **Primitive Obsession**：`feed_metadata/service.py:523` 已存在受控 `Route` 类型，却声明：
  > `source_bytes(self, request_key: str, route: str)`

## Spec

### Missing / partial

1. **组合读面缺少来源候选及选择依据。**  
   #119：「组合读面可回查取得路线、来源候选/选择、冲突、元数据缺项和语言预算依据」。`src/paper_radar/feed_pipeline/models.py:41-48` 的 `PipelineTrace` 仅有版本号、metadata、conflicts、language、receipts；`service.py:101-114` 虽调用 `papers.show()`，却丢弃其 `fields/selection`，也未返回 discoveries/acquisitions，无法回查来源候选及获选依据。

2. **B/C 承接责任未记入路线图。**  
   #119：「按路线图维护规则记录 Feed 工程完成的证据及 B/C 后续责任」。diff 仅将 Feed 标为完成；`docs/roadmap.md:96-106` 的承接索引仍只有旧 I/T/D 条目，未记录实现暴露的生产 boundary/RPC 前置及 C 四刊扩展责任。写在交付证据页不能替代路线图承接索引。

### Wrong implementation

3. **策略版本机制不能接受映射升级。**  
   #118：「策略新版本只影响之后的新登记，不篡改旧策略身份」；#114：「策略升级不更正旧值、不重置预算」。`src/paper_radar/screening_tasks/service.py:224-230` 注册任何新版本都只能复制 `POLICIES["v1"]`；`language.py:145、193、309-320、342` 又强制所有派生、冻结依据及校验等于 v1 常量。因此新映射无法登记；若直接改常量，旧预算反会被判 `corrupt_reference`，并非仅新版本生效。

### Scope creep

未发现。

---

汇总：Standards 6 项（2 项硬性违规、4 项 judgement calls；最严重：公共 Contract 未同步）；Spec 3 项（2 项 missing/partial、1 项 wrong implementation、0 项 scope creep；最严重：策略版本机制不能接受映射升级）。

---

## 本轮逐条处置（2026-10-30）

原审查正文保留；本附录以 `fb52cd7` 为修复前基线，依 #114–#119 正文、ADR-0030–0036 和现有公共服务逐项核实。判断性建议按本次触及模块取舍，不将相似代码自动视为同一领域身份算法；与 r2 重复的证据见 [r2 处置附录](issue-114-feed-review-r2.md#本轮逐条处置2026-10-30)。测试沿用 #114 已确认的公共事实、任务、生产服务和 HTTP transport seam。

| 原编号 | 处置 | 依据及实现／测试指针 |
| --- | --- | --- |
| Standards 硬性违规 1：公共 Contract 未同步（两处事实） | 采纳 | `paper-facts.md` §3 区分 `ObservationInput` 不表示 304/失败与生产检查已保存执行历史；§4 明确 Feed 身份仍是 URL/UUID，语言归属、ETag/Last-Modified 在独立关联／检查事实中引用 Feed。不再声称完全不建期刊关联或等待未来 task_attempts。实现仍见 `feed_ingestion/service.py`、`screening_tasks/language.py`，本项修正文档事实。 |
| Standards 硬性违规 2：feed-metadata Contract 骨架 | 采纳 | 封闭状态与 `corrupt_reference`/`metadata` 错误路径移入「错误与拒绝」；「相关」只保留依据链接。 |
| Standards smell 1：跨领域 canonical/hash 与 resolution 重复 | 部分采纳 | `language.py` 统一 `_read_resolution`、`_require_policy`、`_require_sources`，预算回放和观察查询共用校验。拒绝跨 Paper 冲突、HTTP 检查、元数据及任务指纹统一 identity helper：其载荷边界、bytes/string 接受类型及已登记字节语义分别冻结，重复两行不构成统一领域身份的充分依据。测试：`test_feed_language.py::test_new_policy_mapping_only_changes_new_inputs_and_replays_persistent_history` 及既有损坏／恢复回归。 |
| Standards smell 2：语言状态级联 | 采纳 | `language.py::_status` 被 derive 和 resolution 一致性校验共用；missing/ambiguous/resolved 原语义保持。既有 `test_feed_language.py` 四刊、缺失与歧义用例覆盖。 |
| Standards smell 3：Metadata key/basis/route clump | 部分采纳 | `feed_metadata.repository.load_run` 返回已校验的 `MetadataBasis`，service 直接传领域对象，去除 `dict[str, Any]` 降级；key 是请求身份、route 是单次路线选择，仍显式传递，不为三个职责不同的参数另造泛用上下文对象。canonical 持久字节不变。验证：`test_feed_metadata.py` 公共 replay／故障／恢复。 |
| Standards smell 4：source_bytes route 为 str | 采纳 | 改为已有封闭 `Route` 类型，运行时未知／未保留路线仍按原受控 `invalid_observation` 拒绝；公开内容与原字节测试保持。 |
| Spec 1：组合候选／选择读面缺项 | 采纳 | `PipelineTrace` 新增当前字段候选引用、selection、全部观察候选引用、decisions、discoveries、acquisitions。论文引用来自同一 `PaperFacts.trace` 一致视图；候选投影删除 value，不展开题名／摘要。测试 `test_feed_pipeline.py::test_trace_exposes_candidates_selection_and_discovery_without_text` 修前 AttributeError，修后验证三来源候选、选中／未选原因及文本不泄漏。Contract 同步。 |
| Spec 2：B/C 路线图承接 | 采纳 | `docs/roadmap.md` 模块承接索引写明 B 真实 boundary/RPC、JGR 真实字段／摘要／语言约定、实验根与恢复责任；C 四刊扩展、复查／生命周期／eligibility。附 #114/#119 与现状契约来源；EXP-1、DEC-1/2/3 不因工程完成变为通过。 |
| Spec 3：新策略不能表达映射升级 | 采纳 | `register_language_policy(version, mapping=...)` 支持显式新版本的完整四刊严格 bool 映射；省略参数兼容原 v1。拒绝修改 v1 和复用旧版本改变映射。derive/历史观察/冻结预算按各自持久版本回放；策略不进入指纹，不重置预算。测试 `test_new_policy_mapping_only_changes_new_inputs_and_replays_persistent_history` 修前 TypeError，修后覆盖差异映射、旧预算／retry、只有新输入新预算采用新值及备份恢复。测试中的 `test-policy-v2` 是合成政策，真实政策变更仍须新裁决，本轮不更改 v1 或批准真实政策。 |

判断性 smell 的未采纳部分均为范围与历史身份安全取舍，不列作未完成的本票代码义务。未执行真实 JGR/HTTP、语言约定核实、B/RPC、Docling、校准或 NAS live；不重写历史 A1–A10 结论及旧验收证据。完整门禁的本次运行结果由最终提交外的回执记录，原报告的“未运行”描述保留其历史含义。

### 本轮开发验证

- 相关 Feed、共享审计、恢复及追加解释回归：14 个模块，`163 passed in 144.12s`；命令与完整输出保存在仓库外 `/tmp/paperradar-114/review-pytest.log`。
- `uv run --offline --locked ruff check src tests scripts` 通过；`ruff format --check src tests scripts` 显示 659 个文件格式一致；`mypy src tests scripts` 显示 658 个文件无问题。
- scope 按已消费 DAG 对 A6–A10 共 21 项既有哈希重绑；`audit-verification-scope --collect --json` 退出 0，图问题和字节漂移为空，collection reason=ok；AST 比对确认历史测试注册与分母不变。旧／新哈希和原因见仓库外 `/tmp/paperradar-114/review-scope-rebind-ledger.json`。collection 的 execution=not_run 只说明未执行测试，不代表没有 collection；本轮不把 collect 当作功能通过。
- 完整入口兼容组合首次在 scope 重绑前运行，49 failed/127 passed，失败信号为 scope_drift 及其前置传播；重绑后重新运行 `./scripts/check-compatibility all`，`176 passed in 241.69s`，真实退出码 0（入口总耗时 242.26s）；完整输出见仓库外 `/tmp/paperradar-114/review-compatibility-final.log`。以上子集、静态检查与兼容组合不替代最终提交后的完整离线门禁；正式回执保持仓库外说明与原字节身份。
