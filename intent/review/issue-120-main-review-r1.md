# Issue #120 相对 main 的双轴代码审查 R1

- 固定点：`main`（merge-base：`b04c8d5da2fabc0d384bebbfde0d65e845873789`）
- 审查 HEAD：`3f41b1adc8b9826d1895ea78e9b3c5cc25778a85`
- 差异命令：`git diff main...HEAD`
- 规格来源：GitHub Issue #120 及原生子票 #121–#125 的正文与全部评论；后续评论中的裁决优先。
- 审查方式：两个 fresh-context subagent 并行前台执行，均具备 `bash` 权限；只读审查，不修改代码、不创建 commit。

## Standards

### 明确违反

1. **CLI 产品输出未默认中文化**  
   `src/paper_radar/doctor/cli.py:27-52` 输出 `"Feed readiness"`、`"Pi adapter readiness"`、`"backup/restore gate"`、`"unattended automation gate"` 等英文展示标签。  
   标准：`docs/agents/cli-output.md`：“产品输出（CLI help、错误信息、报告和分析文本）默认使用中文。”  
   **影响**：doctor 正常及失败路径均出现英文产品文本。**硬违规**。最小修复：翻译显示标签，保留受控 `category/result/reason` token。

2. **公共 Contract 未随实现原地同步**  
   - `docs/contracts/feed-ingestion.md:5`、`feed-metadata.md:5`、`feed-pipeline.md:5`、`screening-tasks.md:200` 的构造签名仍省略新增的 `sink/clock/monotonic`。
   - `docs/contracts/fixture-audit.md:175-177,260-263` 的 run/resume 副作用说明未补充新增运行日志或链接。  
   标准：`docs/agents/documentation.md` Contract 规则：“只用现在时描述已实现的公共边界”“行为变化时原地修正既有说明……不以文末追加新说明代替修正旧陈述”。  
   **影响**：权威公共边界描述与代码不一致。**硬违规**。最小修复：更新上述签名及副作用摘要，并链接 `runtime-logging.md`。

### Baseline smell（判断）

- **Duplicated Code**：`tests/test_eligibility_architecture.py:9-64` 与 `tests/test_calibration_visibility_architecture.py:22-38` 重复 AST `_violations` 遍历及 Import/ImportFrom/Call 检查形状。两套守卫可能独立漂移。最小修复：提取共享测试辅助函数，以允许导入集合及 `TYPE_CHECKING` 策略为参数。

### 实际验证

`git diff --check main...HEAD` 通过。测试：**未运行**；完整离线门禁未运行。

## Spec

1. **[硬违反／实现错误] 跨版本但指纹相同的当前 Screening 制品被误拒。**  
   规格 `intent/draft.md:1509–1510`：“当前适用性由当前输入指纹与筛选制品指纹完全派生：**版本变化但指纹相同仍适用**。”#122 亦要求“复用……A7 applicability”。  
   `src/paper_radar/eligibility/rules.py:102–110` 额外要求 `applicability="current"` 的制品 `version_id` 必须等于当前版本。触发：A7 已判定为 `current` 的 v1 制品，在论文进入 v2 且语义输入不变时，`CURRENT_SCREENING_ARTIFACT` 返回 `screening_contradictory`，并阻断系统决定及 Read 前置。  
   `tests/test_eligibility_review.py:368–396::test_system_request_cannot_borrow_old_or_crossed_screening` 反而固化了该错误；缺少跨版本同指纹正例。最小修复：删除 Screening 的当前版本相等限制，保留引用完整性及 PDF 的版本绑定规则，并补两种公共入口的跨版本 `current` 正例；同步修正 Contract `:73–79`。

未发现其他仍成立的缺失或 scope creep；明确 deferred 项未计入。

**实际验证：**运行 `PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/paperradar-spec-review-uv-cache uv run --offline --locked --no-sync python -`，stdin 构造上述 v1→v2 合成事实并断言应通过；实际输出 `eligible=False, reasons=('screening_contradictory',)`，断言失败、退出 1。未运行完整门禁或 live。

---

汇总：Standards 共 3 项，轴内最严重为 2 项明确规范违反（CLI 英文产品输出、公共 Contract 漂移）；Spec 共 1 项，轴内最严重为跨版本同指纹 Screening 制品误拒的硬违反。

## 本轮逐项核实与处置（原审查正文保留）

基线 `3f41b1a`，直接在 main 实施；唯一 implementer，无子代理、push、PR 或 Issue 写入。
按 `/tmp/paperradar-issue-120-r2/implementer-guide.md` 的十类统一核实；完整编号、
低优先级合并项与证据见[另一报告附录](issue-120-a-narrow-review-r2.md#本轮逐项核实与处置原审查正文保留)。
Issue 裁决依据由协调者独立核验，本轮实现核对本地规格 §8.5、ADR-0031/0036/0037 与 Contract。

| 本报告条目 | 统一编号／裁定 | 落实与公开证据 |
| --- | --- | --- |
| Standards 1 中文展示 | 3，采纳 | 九类标签中文化、D3 固定句原文保留；readiness 是明确用户裁决例外，受控 token、六阶段名保持；test_doctor_process 的所选配置/失败路径与旧 pi-supply 黄金字节回归 |
| Standards 2 Contract 漂移 | 4，采纳 | 四服务构造签名原地补齐；fixture-audit 的 run 正文与 resume 副作用表原地链接运行日志 |
| Baseline smell：AST 重复 | 8，部分采纳 | 仅两份新增守卫共用 tests/pure_dependency_support.py；依赖集合与 TYPE_CHECKING 例外各自声明；不重构历史 Screening 守卫 |
| Spec 1 跨版本 current 误拒 | 1，采纳 | 移除 Screening 的额外版本相等条件；evaluate_paper/evaluate_concept 同时验证系统 accepted、Read 前置与请求；历史/未知、缺引用、交叉引用和 PDF 版本拒绝仍成立 |

红绿过程：跨版本公共回归先出现 `screening_contradictory`（1 failed、1 passed），
修复并修正负例原因声明顺序后，资格与文件日志切片共 116 项通过。
doctor 中文标签先 2 failed，修复后 doctor 两模块 42 passed，包含旧 pi-supply 字节比较。
主协调者提交后核对发现本轮曾将 D3 固定句的 readiness 也翻译，超出了标签中文化范围。
已依据 #120 用户最终裁决（issuecomment-6520223100 的 D3，非完成记录）恢复 SUCCESS_NOTICE
与 doctor Contract 原句；readiness 在此属于明确用户裁决例外。公共 CLI 测试使用来自裁决的
完整独立字面量核对成功输出最后一行，不从生产常量导出预期，覆盖 basic、settings/snapshot
及阶段配置缺项。强化测试先 2 failed，再恢复固定句并复验；九类标签中文化保持。
恢复后 doctor 公共子集 42 passed，CLI compatibility 59 passed，Ruff/严格 mypy/只读 scope
均通过；SUCCESS_NOTICE 与 doctor Contract 已逐字节／字面量对照 3f41b1a 原文。
此前错误的“跨版本 current 属矛盾”参数已替换为 undeterminable／缺版本／缺引用反例，
未改历史固定测试模块分母；原始跨版本探针现返回 eligible=true、reasons=[]。

协调者进一步指出：删除错误的版本相等比较时，原先被该比较间接拒绝的空串来源版本也会被放行。
本轮同一 finding 补 `test_empty_screening_origin_version_is_contradictory`，先从公共单篇入口
复现 eligible=true（1 failed），随后以 `not artifact.version_id` 保留缺失／空串的
screening_contradictory 拒绝；单篇及批量同时覆盖制品、系统决定、Read 与请求。
这用于防止删除错误比较时放宽既有输入安全行为，合法 v1→v2 current 与 PDF 绑定继续成立。
补充后的资格、架构及公共组合子集 133 passed；Ruff、严格 mypy、只读 scope 复验通过。
该补充仅涉及未绑定的规则和测试，按协调者指示不重复已通过的 compatibility-all。

完整离线门禁本阶段未启动；不得将 `3f41b1a` 的历史通过转用于本轮提交。
后续同次门禁的运行标识与终态由协调者留在工作树外并回帖 #120/#125，不回写本报告。
本轮实际相关验证、scope 与未验边界详见另一报告附录的验证段。
