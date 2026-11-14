# #199 报告参数与披露精度补丁

本台账记录 `422a1567a5010f5c9ab8843326c21fe4fda2f867` 之后的窄补丁。
[原工程台账](issue-199-experiment-reports.md)保持原字节；其 25 项长组合、29 个新 D1 与其他实测结论各自属于原次验证。
本补丁不新增 migration，head 保持 `b006_reports`。

## 变化与接缝

- 报告组复用既有 BatchGroup，未知命令/选项给出受控中文原因和 --help，不回显自由文本。
- `render_unassessed_fragment` 不创建历史 CapabilityClaim。共享 AdmissionRow/片段显式区分
  本次 assessment=not_assessed、historical_state_read=false 与未读取的 original_state=unknown；
  received/active/revoked 同为 unknown。严格模式默认展示保留实际读到的原状态。
- 没有 delegated acceptance 的条目显示“尚无代执行接受决定（保留选样授权）”；
  只有存在实际记录时标注所有者授权与 Agent 代执行。

受影响生产路径为 experiment/cli.py、doctor/admission.py、experiment/report_rendering.py。
新负例使用 CLI；两个决定来源用例使用所有者批准的纯冻结输入接缝。
受保护历史来源在 CLI 负例中设置为一旦读取即失败；不提供资格成功 mock。

## 新增 D1 与精确去重

新增 7 个未绑定 D1：

| 模块/节点族 | 新节点数 | 行为 |
| --- | ---: | --- |
| test_experiment_reports_cli.py::test_report_group_argument_errors_never_echo_private_text | 3 | 未知命令、组未知选项、render 未知选项 |
| test_experiment_reports_disclosure.py::test_unread_history_is_unknown_and_current_assessment_is_unassessed | 2 | waiver 开/关均不读取保护来源、不制造历史原状态 |
| test_experiment_reports_disclosure.py::test_frozen_projection_only_labels_actual_delegated_acceptance | 2 | 有/无实际 acceptance 的标题分支 |

最终新 D1 精确去重集合为原 29 + 新 7 = **36**，分布在十个模块；
完整收集清单和逐模块数量保存在外部交接材料。
收集 36 不表示本补丁把全部 36 重新执行为一次长组合；最终集成树的全并集验证由 merger 另记。

## 实际补丁验证

- 新组参数 3 + 原冷帮助 4：**7 passed /1.76s**；红测原为 2 failed、1 passed。
- 新披露/决定来源 4 + 原 doctor_admission_disclosure 完整 8 + 原 waiver 披露 1：
  **13 passed /7.50s**；新反例 red 为 3 failed、1 passed。
- 受影响报告 CLI 完整 14 + replace→准入改变→标准 restore verify→NoRuntime 冷重建 1：
  **15 passed /157.28s**。原成员/依据/first-key/字节、恢复库和制品库存保持；不重跑无影响六成员准备链。
- 参数组补丁后的 `check-compatibility cli`：**59 passed /79.32s**，入口总 79.82s；
  TMPDIR 在设置前已独占创建。其后共享展示精度窄修不改变 CLI 注册/导入链，受影响入口由上述 13/15 项复核。
- 全部触及的 **34 个 Python**（生产、迁移/scope 声明、全部新 test/support）默认 strict mypy、
  Ruff、format 通过；实际提交范围 diff-check 与最终 clean 身份见外部交接。

未修改旧冻结测试、fixture、历史 ledger 或原证据字节，未机械重绑旧 source hash。
Scope 的敏感确认、漂移与未执行 collect 保留到最终集成责任；没有运行完整离线门禁。
没有真实/live 命令、真实实验根/运行 checkout/私有材料或真实凭据读取；全部为 /tmp 合成边界。
Python 冷守卫不代表 OS 隔离、模型质量或 NAS 通过。
