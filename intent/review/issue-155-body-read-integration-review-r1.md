# Body / Read 集成分支两轴审查（fixed point: main）

- 审查范围：`git diff main...HEAD`（三点，merge-base 为 `c1a57f11c70521cd506bf8eba0145deef9d0cb60`）。
- 固定点：`main = c1a57f11c70521cd506bf8eba0145deef9d0cb60`；HEAD：`6e15d1cdfea10353437c7394f5966fedf0017ea8`。
- 变更规模：26 个提交，175 个文件，+21910/−279。
- Spec 来源：GitHub Issues #155–#165 的正文及全部评论；评论优先于正文，后发表评论优先。
- 两个独立 reviewer 均确认具有 `read, bash` 权限，并以只读方式运行。
- 本次仅静态审查；未运行 pytest、完整离线门禁或 live 验收，未修改代码，未创建 commit。

## Standards

1. **硬违规｜错误缺少下一步** — `src/paper_radar/fulltext/models.py:146-152`  
   hunk：`super().__init__(f"正文制品拒绝：{reason}")`。这是 Contract 公开的持久正文服务错误，但只给原因码。违反 `docs/agents/cli-output.md:5`：“错误信息写明具体原因和用户可采取的下一步。”  
   **最小修复**：按 `FulltextReason` 提供受控中文处理指引。

2. **判断｜Duplicated Code** — PDF 完整性检查重复于 `body/service.py:527-535`、`body/extraction.py:225-231`、`body/validation.py:104-109`、`read_tasks/preconditions.py:32-40`。  
   hunk：`sha(raw) != facts.pdf.pdf_sha256 or not raw.startswith(b"%PDF-") or len(raw) < 1024`。四处分别维护哈希、签名及长度规则，容易漂移。  
   **最小修复**：提取一个 Body 内共享的 PDF 字节核验函数，保留各处不同异常映射。

3. **判断｜Duplicated Code** — `feed_metadata/service.py:440-460` 与 `504-528` 重复路线 DOI、规则版本及 acquisition 匹配校验。  
   hunk：`route.request.doi != basis.doi or route.abstract_rules_version != basis.abstract_rules_version`。  
   **最小修复**：抽取路线闭包核验 helper，以可选 `revision_no` 表达历史重放的额外限制。

4. **判断｜Middle Man** — `read_tasks/service.py:495-496`  
   hunk：`def prepare_correction(...): return self.correction(task_id)`。两个公共入口仅因名称不同而并存。  
   **最小修复**：将实现并入 Contract 使用的 `prepare_correction`，把另一入口移除或收窄为私有实现。

## Spec

暂无可聚合的 Spec 审查发现；这不表示 Spec 轴通过。

首次 Spec subagent 在运行中遭遇服务端 `403 permission_denied_error`：当前方案仅支持 `k3.1-pro` 的 256K 上下文，而运行请求触发 1M 上下文限制。按相同 reviewer 和只读方式重试一次后，请求被中止，未产生报告。因此本文件不虚构缺失、部分实现、scope creep 或错误实现结论。

---

**汇总**：Standards 共 4 项发现（1 项硬性违规、3 项判断性 smell），本轴最严重的是 `FulltextError` 未提供用户可采取的下一步；Spec 共 0 项已完成的发现，但因 reviewer 未完成而无法判定本轴最严重问题。


---

## 后续逐条核实与处置（#155 整改；与原静态审查分开）

以上为用户提供的原报告，原字节前缀保留。以下是本轮唯一 fresh implementer 对
`6e15d1cdfea10353437c7394f5966fedf0017ea8` 基线的独立核实，不追改原判断。
逐条变更、完整实测、材料 SHA 与未验范围见
[独立增量台账](../../docs/verification/issue-155-review-remediation.md)。

| 原发现 | 处置 | 依据与实际验证 | 剩余风险 |
| --- | --- | --- | --- |
| Standards 1 | 采纳 | 九个 FulltextReason 增安全中文下一步，reason/quality 不变；新公开错误回归 RED 9 failed，GREEN 9 passed。 | 无正文/路径/原异常回显；指引不证明用户 PDF 或模型就绪。 |
| Standards 2 | 采纳局部重构 | Body 低层 valid_pdf_bytes 合并 SHA、签名、1024 下限；四消费者各保留 BodyError/ReadTaskError/恢复映射。相关 Body/fulltext/Read 前置与恢复组合见台账。 | 不把上传规则或 PDF 归属校验混进完整性函数。 |
| Standards 3 | 采纳 | metadata 路线闭包 helper 保留历史 result_revision_no<=revision_no 限制；既有 `test_historical_metadata_cannot_borrow_a_later_acquisition` 与历史回放组合见台账。 | 当前元数据资格与明确历史重放仍独立。 |
| Standards 4 | 采纳 | 全仓代码/测试/Contract 检索仅 prepare_correction 有业务调用；实现直接放入该入口，移除未文档化 correction。Read execution RPC/history 与任务组合见台账。 | 仓库外若调用未文档化 correction，需改用 Contract 入口。 |
| Spec 未完成 | 无可处置 finding | 原 reviewer 未完成的事实保留，不补造 Spec 结论，不将零 finding 解释为通过。 | 本轮核实不代替缺失的完整 Spec review。 |

本轮未运行完整离线门禁或 live。所有相关子集、兼容、静态与 scope 检查的实际结果
以独立增量台账为准；旧 #165 材料及旧门禁身份没有改写。
