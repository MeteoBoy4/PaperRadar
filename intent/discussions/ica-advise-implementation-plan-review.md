# ica-advise：#1/#2 实施计划确认与 commit 切分修正

日期：2026-09-22
状态：已决。
来源：架构审视报告候选 #1 + #2 实施前的五条推论确认（grilling 尾声）。
前序：Q1–Q7、Q9、Q10 八份 ica-advise 决策记录。

## 决策是什么

对实现 agent 自行推导的五条实施推论逐条核实。结果：第 1、2、3、5 条确认（第 2 条补措辞精度），第 4 条（commit 切分）修正。

## 核实结论

1. item 字段形状：created/unchanged 带 snapshot_dir + schema_sha256、error_category=None；failed 带类别+指引、dir/sha=None；not_attempted 带指引、其余 None。与 check.py:236-242 失败项形状一致。注意 export 侧 error_category=None 不再唯一等于成功（not_attempted 亦为 None），outcome 是判别字段，文档 item 表须写明。
2. 批量语义不变：预检全部完成后有任何失败则零写入；matched 项一律 unchanged；ABSENT 待发布项在未轮到时报 not_attempted；发布首个失败即停止。精度修正：not_attempted = 未轮到发布的 ABSENT 项，matched 项无论声明顺序一律 unchanged（预检期已定局）。
3. 选择无效（未知/重复/空/版本非法）在任何 item 之前整体抛 ContractExportError(invalid_selection)，CLI「导出失败 [类别]：…」路径不变。
4. commit 切分修正：test_contract_export.py:12 顶层 import ContractBatchExportError，删除该类的 commit 不同步改测试会在收集阶段 ImportError。正确切分——commit 1 = 行为与公共 API 不变的 seam 重构（Q1/Q4/Q5/Q9/Q10），测试不改全绿；commit 2 = Q2/Q3/Q6/Q7 + 同 commit 更新测试与 a1_scope.py 哈希（contract 四个测试文件均在钉扎清单）。禁止出现"API 变了而测试没变"的中间 commit；合成单 commit 亦可。
5. 流程确认：先按 docs/agents/issue-tracker.md 建 issue，正文发布前交所有者过目（对外操作）；正文应引用八份决策记录与审视报告，范围清单含 docs/contracts/frozen-contracts.md 同步更新。

## 是否改变外部行为

否。全部为实施计划层面的确认与修正，外部行为与已定决策一致。

## 是否需要 ADR

否。
