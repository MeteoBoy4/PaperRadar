# 阶段 A6 双轴审查 r1（#67 / #68–#75）

- 固定点：`main` = `bd6afba80d0c9b1fa8b455c332be3329b97d513d`
- 被审：`integration/67-paper-facts`，HEAD = `706ecb1dc4c0354f0c00738d611b23af5f3abd33`，工作树干净、无未提交修改
- diff：`git diff main...HEAD`（三点，对 merge-base）＝ 129 files, +15743/−132；`git log main..HEAD --oneline` 共 14 个提交（6c17015 … 706ecb1）
- 两轴分别由独立只读子 agent 执行，互不共享上下文；本文按轴分列，未跨轴合并或重排。

## 工具与来源（两轴共同）

**可用（只读）**：`read`/`grep`/`find`/`ls`/`bash`（`git diff/log/show`、`rg`、离线 `uv run --offline --locked pytest <子集>`）、`gh issue view`（已认证，未写 Issue）、`verification-runs/` 只读解析。临时写入仅 `/tmp/a6review/`。

**不可用或未使用**：仓库**没有** `CODING_STANDARDS.md`，也**没有** `CONTRIBUTING.md`；两轴规范来源因此为 `AGENTS.md` + `docs/agents/*` + `GLOSSARY.md` + `docs/adr/*` + `docs/contracts/*`。未运行 `./scripts/check-offline` 全量门禁（引述已存档 run 并只读核对），未运行任何 live（真实 Feed/Crossref/模型/Docling/RPC/NAS）。

**已只读核对的完成证据**（Spec 轴）：`verification-runs` 中 `912c5913b4264a03975e6b2a045cfd7f` 为 `passed/verified`、`applicability=same`、649 秒，`code.commit=706ecb1…`、`dirty=false`；171 模块 3033 例全过、零 skip/deselect；A6 45 模块/499 例与旧分母 2534 相符；`a6_scope` 与 a2/a2f/a3/a4/a5 源码哈希重算零漂移；`a5_scope.py` 的 `NOT_ASSESSED`（含 `paper_fact_mapping`）未被改；A6 组 `ISSUE=75`/`PARENT_ISSUE=67`、依赖 A1/完整 A2/A3/A5。

**实跑**：Standards 轴 `pytest tests/test_paper_inputs.py tests/test_paper_service.py tests/test_a6_formats.py -q` → 61 passed；Spec 轴 8 个 A6 模块 80 例 → 80 passed（10.67s）；两轴各自运行了最小探针（见各条「复现」字段）。

## Standards

（文档化标准优先；smell 基线仅作判断线索；已跳过 Ruff/mypy 强制的格式与类型风格。仓库无 `CODING_STANDARDS.md`/`CONTRIBUTING.md`，规范取自 `AGENTS.md`、`docs/agents/*`、`GLOSSARY.md`、ADR 与 Contract。）

### F1 封闭类型未落成领域类型（文档化要求）
- **类别**：文档化硬要求（标准原文较概括）。`docs/agents/python-conventions.md`「用明确的领域类型和受控 enum / reason 表达状态与原因」；`docs/contracts/paper-facts.md` §6 规定 `relations` 每项封闭字段 `{kind,source_doi,target_doi,locator}`，`kind` 只收两种。
- **位置**：`src/paper_radar/papers/models.py:159` `relations: tuple[object, ...]`；`:146` `source_kind: str`；`:343` `RelationInput.kind: str`。
- **影响**：公共写边界对关系/来源没有静态约束，任意对象可进入 `normalize_relations`；`relations.py:13-40`、`rules.py:100-121`、`queries.py` 因此反复 `model_validate`。运行期已有受控拒绝，故不是安全缺陷。
- **测试核查**：`tests/test_paper_inputs.py`、`tests/test_version_relations.py` 只断言运行时受控原因；无测试断言声明类型；mypy 因 `object` 通配不报。
- **复现/限制**：静态阅读即可确认（已核对 `models.py:159/146/343`），未运行。
- **最小建议**：`tuple["RelationInput", ...]`、`source_kind: Literal["feed","publisher","registry","manual"]`、`kind: Literal["is-preprint-of","has-preprint"]`。

### F2 宽泛 `except` 把程序缺陷与输入校验失败统一报成 `corrupt_reference`（文档化要求）
- **类别**：文档化硬要求。`docs/contracts/paper-facts.md` §9 把 `corrupt_reference` 限定为引用链/归属/制品 kind/字节损坏。
- **位置**：`src/paper_radar/papers/queries.py:511-512`（`load_trace`）、`queries.py:165-166`；`src/paper_radar/papers/feed_queries.py:199`；`src/paper_radar/papers/manual.py:252`。均为 `except (ValueError, TypeError, KeyError[, StopIteration], PaperError)` → `corrupt()`/`CORRUPT_REFERENCE`。
- **影响**：重构引入的 `TypeError/KeyError` 被报成「数据损坏」，CLI 引导用户「停止使用该批次并检查备份」；合法校验失败（如 `require_public_url` 抛 `INVALID_OBSERVATION`）也被并入同一 reason，与词表定义相反。
- **测试核查**：`tests/test_paper_backup.py`、`tests/test_paper_recovery_damage.py` 只断言受控拒绝，无法区分「真损坏」与「程序缺陷」；`tests/test_a6_status.py`/`test_a6_integrity.py` 覆盖 reason 词表完整性，不覆盖本分类。
- **复现/限制**：**未复现**（未注入 `TypeError` 用例）；静态路径已核对。
- **最小建议**：白名单化预期异常，`TypeError/StopIteration` 直接上抛；或拆 `corrupt()`/`invalid()` 两条出口。

### F3 三个写入口重复「取得事实 + 修订」记账（判断题·Duplicated Code）
- **位置**：`src/paper_radar/papers/repository.py:337-391`、`feed_repository.py:274-322`、`manual.py:119-194`：各自算 `current_no`/`event_no`、写 `paper_source_acquisitions`、调 `update_revision`。
- **影响**：默认值已分叉（feed 用 `first_seen`，manual 固定 `parser_version=1`，`raw_doi` 三处写法不同）；新增来源类别要改三处，易漏一致性校验。
- **测试核查**：`tests/test_paper_acquisitions.py`、`tests/test_manual_corrections.py`、`tests/test_feed_discovery.py` 分来源覆盖；无跨来源一致性用例。
- **复现/限制**：静态；未改代码。**建议**：抽 `record_acquisition(...)->(acquisition_id, revision_no)` 三处共用。成本中、风险低。

### F4 获选与 trace 说明各自实现「最高 parser」规则（判断题·Duplicated Code）
- **位置**：`src/paper_radar/papers/rules.py:42-64`（`choose_fields`）与 `rules.py:133-142`（`explain_fields`）各建一份 `highest` 字典。
- **需求依据**：`docs/contracts/paper-facts.md` §1.3「说明复用纯仲裁权威」。
- **影响**：任一方改键（加入 version/relations）即出现「说明与实际获选不一致」；现有测试只覆盖常态。
- **测试核查**：`tests/test_source_arbitration.py`、`test_paper_reparse.py` 断言常态获选与 reason，无「说明与获选必须同源」的断言。
- **建议**：抽 `_highest_parser(observations)` 或让 `choose_fields` 同时返回两者。

### F5 跨模块导入私有符号（判断题·模块边界）
- **位置**：`queries.py:12` 导入 `_candidate`；`fact_reads.py:12`、`feed_queries.py:10`、`queries.py:32`、`relation_repository.py:19` 导入 `read_checks._utc/_uuid`；`feed_repository.py:18-20`、`manual.py:24-28` 导入 `repository._conflict/_insert_candidates/_saved_result`。
- **依据**：`docs/agents/refactor.md`「每个模块职责单一…只读单个模块即可完成该模块内的工作」。
- **测试核查**：无；`tests/test_a6_formats.py:19-36`、`tests/test_paper_migrations.py:113` 的 AST 守卫只禁 storage/sqlalchemy/外部客户端，未覆盖包内私有导出。**复现/限制**：静态。
- **建议**：`_utc/_uuid/require_*` 提升为公开名，`_candidate` 改 `load_candidate`。成本低。

### F6 读模型、校验与选择器混在同一模块（判断题·Divergent Change）
- **位置**：`queries.py`（614 行：`_acquisition`、`_validate_parser_history`、`load_trace`、`resolve_revision`、`load_manual_corrections`）；`relation_repository.py`（561 行，写/读/校验 17 个函数）。
- **影响**：`load_trace` 单函数同时反序列化、校验一致性与解释决策；后续恢复类扩展会反复改同一文件（#74 已触及）。
- **测试核查**：功能覆盖充分（`tests/test_version_relation_materials.py`、`test_paper_backup.py`），属结构判断，不涉测试缺口。
- **建议**：拆 `relation_writes`/`relation_reads`；`load_trace` 抽出 `_load_version_view()`。纯移动+改名，风险低。

### F7 README 文件计数过期（文档化要求，影响小）
- **位置**：`README.md:282`（A5 段「check-offline 输出七份主要文件」）与 `README.md:370`（「八份主要文件…`a6.json`」）并存；`docs/contracts/stage-inputs.md:372` 亦称七份。
- **依据**：`docs/agents/documentation.md`「公共契约…同一变更中同步更新」。
- **测试核查**：无文档断言。**复现/限制**：静态核对，已确认两处文本。
- **建议**：A5 段改为「A5 当时七份」或直接改为八份并注明 A6。

### F8 内部错误契约不一致（判断题，两项合并）
- `src/paper_radar/papers/models.py:42-46`：`ClosedModel.__init__` 抛裸 `ValueError("invalid_observation")`，与 `model_validate`/`model_validate_json`/`model_validate_strings` 的 `PaperError` 不一致；构造点 `manual.py:143`、`mapping.py:88` 若破不变式，`ValueError` 会逃出而非受控 reason。**未复现**（现有预校验/CHECK 拦住可达路径）。
- `src/paper_radar/backup/service.py:177`：函数内 `from paper_radar.papers import …` 隐藏依赖；包内 23 模块无环，可上提。
- **建议**：构造失败统一抛 `PaperError(INVALID_OBSERVATION)`；备份侧 import 提到模块头并加依赖断言。成本低。

**Standards 完成状态**：完成（范围为上述限制）。未发现需要新裁决的「仓库标准 vs 基线」冲突；未运行全量门禁。
**FINDINGS（Standards）: 8** — 最严重：F2（宽泛 `except` 把程序缺陷伪装成 `corrupt_reference`），其次 F1（封闭类型退化为 `object`/`str`）。

## Spec

（权威顺序：#67 正文 + 后续用户裁决（D1–D4、N1/N2、「实施中追加裁决」「用户最新裁决：选方案1」）> 既有 Contract/ADR/GLOSSARY 未被覆盖的部分；`docs/verification/a6-requirements.md` 与 `docs/contracts/paper-facts.md`、`docs/adr/0030-*.md` 是本次实现产出，按被审材料处理。「已完成…」为实现者报告，不作规格。）

### F1 题名/摘要中形似标签的通用写法被整笔拒绝（功能限制，低）
- **类别**：功能限制（受控拒绝）＋文档与实现不一致。
- **影响**：含 `List<String>`、`Array<int>` 等泛型写法的题名/摘要无法登记，`submit` 整笔 `rejected/invalid_text`；A6 无真实适配器，当前成本为零，但阶段 C 会阻断此类论文入库。
- **位置**：`src/paper_radar/papers/text_rules.py:7-18`（`_MARKUP` 标签形状正则）。
- **需求/裁决引用**：#67 第三轮 N1（用户「N1、N2 均同意建议项」）要求仅 LF 化 + 外围 `strip`、其余原样；`docs/contracts/paper-facts.md:167` 明确「数学比较 `a < b` 不是 HTML，须接受…不能用『含尖括号就拒绝』的近似实现」。
- **测试核查**：`tests/fixtures/paper_facts_v1.json` 的 `text` 向量仅覆盖数学比较、`<p>`/`<!-- -->`/`<b title="x">`、孤立代理字符；`tests/test_paper_inputs.py:135` 只断言数学比较被接受。泛型写法既未声明也未测试（覆盖不足）。
- **复现（已运行）**：`uv run --offline --locked python -c "from paper_radar.papers.text_rules import normalize_text; normalize_text('Type safety for List<String>')"` → `PaperError invalid_text`；`'Bounds on T <: Number'`、`'a < b'` 通过；`'Arrays of Array<int>'` 拒绝。聚合者独立复跑，结果一致。
- **未验证**：真实四刊题名是否含此类写法（无 live）。
- **最小建议**：改为「已知 HTML 标签名闭集或标签名+属性语法」再拒绝，并补固定向量（`List<String>` 接受、`<script>` 拒绝）；同时保留 `<!--`/`<!DOCTYPE`/`<?` 拒绝。风险是放宽后未知标签被当正文。

### F2 `requires_merge` 被当成论文级状态写进无关写入的成功结果（判断项，低）
- **类别**：语义/可维护性（可选），非硬违规。
- **影响**：`WriteResult` 无法区分「本次写入保留/新增了待合并关系」与「该 DOI 所在论文当前有待合并关系」；调用方按 reason 分支时会把普通元数据更新误判为需人工动作，阶段 C 适配器也可能误以为本条观察是待合并依据。
- **位置**：`src/paper_radar/papers/relation_repository.py:418-441`（`save_acquisition_result` 扫描全库 `load_relations`，按 DOI 命中即置 `REQUIRES_MERGE`）。
- **需求/裁决引用**：#72 评论点 2「`requires_merge` 是『观察与关系已保留、需人工动作』的成功结果…结果类型与 CLI 退出码要可区分」；`docs/contracts/paper-facts.md:254`。
- **测试核查**：`tests/test_version_relations.py:78`、`:209`、`:284` 与 `tests/test_version_relation_cli.py:49` 只断言「带关系的那次写入」；无「已有待合并关系后再提交普通更新」的用例（语义未固定）。
- **复现（子 agent 已运行，临时目录）**：先建 `10.1/pre` + `10.1/journal` 两 Paper，提交带 `is-preprint-of` 的观察得到 `retained/requires_merge`；随后对该 DOI 提交仅含 `volume` 的普通观察 → `status=retained, reason=requires_merge, conflict=None`。聚合者按代码路径静态确认，**未独立复跑**。
- **最小建议**：reason 仅在本次 acquisition 新增/保留关系时置 `requires_merge`，论文级状态继续由 `trace.relations[].state` 暴露；成本小，但改动公共结果字段，需 Contract 同步一句。

### F3 `trace --verify-source-bytes` 缺 `--data-root` 报为 `corrupt_reference`（判断项，很低）
- **类别**：CLI 文案/原因选择（可选）。
- **影响**：漏传选项被表述为「引用链/制品损坏，请检查备份」，误导排障；退出码 1 符合契约。
- **位置**：`src/paper_radar/papers/service.py:178-181`（`if self.data_root is None: raise PaperError(CORRUPT_REFERENCE, path="data_root")`）、`errors.py` 的 `CORRUPT_REFERENCE` 文案。
- **需求/裁决引用**：#74 评论点 3（`--verify-source-bytes`「一次定名」、默认关闭、只读）；Contract §8「data-root 在来源字节核验时指向既有制品根」。
- **测试核查**：`tests/test_paper_cli.py:114` 只覆盖缺数据库；`tests/test_paper_recovery_integrity.py` 覆盖核验成功/损坏，无该组合（覆盖不足）。
- **复现/限制**：静态确认 `service.py:179` 路径；**未复现**（未构造带论文的临时库）。
- **最小建议**：参数层校验 `--verify-source-bytes` 与 `--data-root` 同现，按 CLI 参数错误（退出 2）或独立 reason 返回；成本极小。

**未发现 scope creep**：S2/S3 等「建议默认」被采纳且在 Contract 写明替代/收缩规则（§8 无历史选择器、无修正入口；不建 `feeds.yaml`/ETag/`duplicate_candidates`/`merge_events`/`manual_intakes`）。阶段 C 暂缓项（强冲突观察持久化、parser 升级固定样本回归、真实来源假设）均记为硬门禁/`NOT_ASSESSED`，未误报为本次缺失。

**Spec 完成状态**：本轴审阅完成（非「零问题」）。已实际运行：8 个 A6 相关模块 80 例（全过）、两个探针脚本、CLI 退出码探针（1/2，不建库）、scope 哈希只读重算。未运行：全量 `check-offline`、任何 live。未核实：真实来源/解析器行为、F3 的端到端复现。
**FINDINGS（Spec）: 3** — 最严重：F1（Contract 明确禁止「含尖括号就拒绝」的近似实现，但泛型写法实际被整笔拒绝且无固定向量）。

## 聚合核验记录（不改变轴内排序）

- F1（Standards）：`models.py:159/146/343` 原文已核对，与报告一致。
- F2（Standards）：四处 `except` 与 `corrupt()` 出口已核对；`queries.py:165` 中 `PaperError` 也被吞并，报告结论成立，复现状态维持「未复现」。
- F7（Standards）：`README.md:282` 与 `:370` 文本并存已核对；按「A5 历史陈述」解释亦可能成立，故保留为低影响文档判断项。
- F1（Spec）：复现已由聚合者独立重跑确认；Contract `paper-facts.md:167` 原文与实现相悖。
- F2（Spec）：`save_acquisition_result` 的全局扫描逻辑已核对；子 agent 复现未由聚合者重跑，已在条目内标注。
- F3（Spec）：`service.py:179` 已核对；未复现状态如实保留。
- 未做：`./scripts/check-offline` 全量复跑（依赖存档 run 只读核对）、`scripts/a6_scope.py`/`a6_acceptance.py` 逐行审读、a601–a604 DDL 逐列审读、45 个新测试模块的全量阅读（两轴合计抽样约 17 个）。

## 完成状态与剩余风险

- 两轴均完成，均非「零问题」；必需来源齐备（#67 + #68–#75 评论、仓库标准文档、`verification-runs` 存档），无来源缺失导致的中断。
- 未验证范围：真实 Feed/Crossref/出版者响应、`<guid>` 裸 DOI、Wiley 落地页参数、eLocator、截断标记真实性、真实 parser 完整性；RPC、Docling、NAS、完整阶段 A；A6 全量离线门禁的本次复跑。
- 阶段 C 门禁（强身份冲突材料持久化、parser 升级固定样本回归/关键字段减少声明）仍按 Contract 保留，本审查未将其计为缺失。


## 2026-10-22 审查后处置索引

以上正文描述原基线 706ecb1 的历史审查，不代表修复后工作树或新的全量门禁状态。
逐条裁决、证据、未采纳理由与验证边界见[统一处置表](issue-67-a6-paper-facts-review-resolution.md)。
本报告全部编号均已登记：Standards F1、Standards F2、Standards F3、Standards F4、Standards F5、Standards F6、Standards F7、Standards F8、Spec F1、Spec F2、Spec F3。
