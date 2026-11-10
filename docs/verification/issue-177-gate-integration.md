# #177 门禁修复合并与精确登记

本次记录本地 `integration/issue-177-live` 的门禁回归修复集成，不追溯修改
[原修复台账](issue-177-gate-fixes.md)或任何历史证据。开发检查与 S3 确认不构成正式门禁或 Live 通过。

## 合并与审阅依据

- 集成原 HEAD：`8977713e123fcb49e0342a42be8ec07698030712`。
- 已独立审阅的修复：`1db62d6de53bb1b583f7de040e9dd0a716127c46`。
- 本地 `--no-ff` 合并提交：`5109685840f181d3adb42deaf49bfc04d3a1732c`；无文本冲突。
- 显式审计 base 与本地 `refs/heads/main` target：
  `41f59888c35d264020bc0128cb7f4821e1695137`；不修改 main 或远端。
- Standards 独立审阅 `/tmp/paperradar-177/review-gate-standards-s3.md`，SHA-256
  `d649f6d3e62959b050eef84182e70b6dc0dd5c17c85a092a88755541745be7a8`：0 hard violation；
  唯一非阻断命名 judgement 为 `test_model_popen_failure...` 名称对应真实模型 execve 故障，
  保留原 node ID，不为命名扩大本次修改。
- Spec 独立审阅 `/tmp/paperradar-177/review-gate-spec.md`，SHA-256
  `1a9233f108cc37ff0f842f8e96b61567c6078ab5069ba8453cf6cf0570f8021e`：0 finding。
- 派生登记独立补审 `/tmp/paperradar-177/review-derived-scope-entries.md`，SHA-256
  `fabece646e6f4bb8789b3a099bc9458e25be13c9b295092717188b683f4d3ddc`：通过。
  独立 AST 展开、旧新字节及 entry 重算证明两份 scope 的变化只来自目标测试 SHA；
  已明确补充这两条路径的 19 条派生确认白名单。

上述审阅与用户对测试维护的授权共同支持本次精确登记；审阅报告不是最终身份的确认文件。
本台账与重绑提交完成后冻结材料，确认输入仅保存在树外，并重新绑定最终 HEAD、target
及完整 clean 工作树摘要；本文件不记录正式 run ID，也不复制旧确认身份。

## 唯一登记写入与实际摘要

仅修改 `scripts/verification_scope_materials.py` 现有
`tests/test_offline_evidence.py` 键的 SHA。其他成员、用途、计数、Schema、负例、required
与格式不变。该中央文件重绑前后 SHA 为
`524b6151380581e77369c477958ba4520104c7984b785f9039154ad633307d11` →
`29c273502d29793488ce46e6a8a557656d2e04ab00b64c129eb53b87b55723f1`。

修复提交已维护普通 source `src/paper_radar/config/service.py` 的
`dc3841724b49d2eab9cfa11adb0905078e314423f7c7f657aea112afa0e68aaf` →
`c23f3b4cec16ed28974ee9f6ffa20c0d0aae8e9334e81c4a2096694180955ee8`，本次保留该结果。

| 敏感路径 | 旧实际 SHA-256 | 新实际 SHA-256 |
| --- | --- | --- |
| `tests/test_offline_evidence.py` | `843308e18b62b0115ba149fc8ad6db1db15a5d01679086e91802b5f153dc5d49` | `4ad550638171513903050c053c5eadfede3f600475c6a515ca52aaea3f6fc28f` |
| `scripts/a1_scope.py` | `6e7c2a0be80c9090f63c018c63932ab4595bab1874c4253ac79f160f88996d56` | `6e7c2a0be80c9090f63c018c63932ab4595bab1874c4253ac79f160f88996d56` |
| `scripts/a2_full_scope.py` | `24d6fb81975101601c073d7f62e2955561327652d4a199ccd05a542c4c81165b` | `24d6fb81975101601c073d7f62e2955561327652d4a199ccd05a542c4c81165b` |

| 敏感路径 | 旧 entry SHA-256 | 新 entry SHA-256 |
| --- | --- | --- |
| `tests/test_offline_evidence.py` | `eb01cd8708dc93736ddadbc6575cc694b2e5483f347587e8fe7bc923e7a66d55` | `12f0e1ec2da67fe8e7a0950ff37dddd852f4725a9678455ad6514b78601ff5d1` |
| `scripts/a1_scope.py` | `c3125eebf6c420f047909e8ee881c9b6ae07213ea3382b15dfb7496d964513c9` | `9a9424e45979b76b4dcfceeb02e4dca69a92bff5e1bcc6c89a8d2295c38fc2a1` |
| `scripts/a2_full_scope.py` | `37b081e5eddf3a5018caa67bed00bf97f599fa742ad4416e709648450d331e20` | `1b914cb25a4317a266ee2ca21544661624ec3c48c2dba322f09cabc99fd01ebb` |

合并后、重绑前只有目标测试 1 条敏感候选。精确重绑后，既有审计规则把 test SHA 纳入
scope entry，因此另列两条字节不变的 registration 候选。发现后暂停并完成上述独立补审，
最终白名单严格为 test 10 组、A1 scope 10 组、完整 A2 scope 9 组，共 29 条；未修改 scope
或审计器，也不自动接受其他候选。

## 逐路径、逐组理由

目标测试的 11 个节点不变。四契约精确集合、计划次数、逐项参数和中文帮助断言保留；
全局 enum 增加 Live v2 后，旧计划明确且仅一次使用 v1，不把其他 kind 推广到 v2。
Read v2 的安全拒绝及既有负例保持。以下每行均须绑定前表对应路径的实际及 entry 摘要。

| 路径 | 组 | 本次具体理由 |
| --- | --- | --- |
| `tests/test_offline_evidence.py` | A1 | 直接消费旧四契约/v1 计划；契约集合、次数、参数、帮助与强度不变。 |
| `tests/test_offline_evidence.py` | 完整 A2 | 直接消费相同 11 节点与 A1 证据；旧语义、成员和分母不变。 |
| `tests/test_offline_evidence.py` | A3 | 经完整 A2 消费相同前置证据；本组 required、成员、分母、格式不变。 |
| `tests/test_offline_evidence.py` | A4 | 经 A1/完整 A2/A3 消费相同前置证据；required、成员、分母、格式不变。 |
| `tests/test_offline_evidence.py` | A5 | 经 A1/完整 A2/A3/A4 消费相同前置证据；required、成员、分母、格式不变。 |
| `tests/test_offline_evidence.py` | A6 | 经 A1/完整 A2/A3/A5 消费相同前置证据；required、成员、分母、格式不变。 |
| `tests/test_offline_evidence.py` | A7 | 经 A1/完整 A2/A3/A5/A6 消费相同前置证据；required、成员、分母、格式不变。 |
| `tests/test_offline_evidence.py` | A8 | 经 A1/完整 A2/A3/A5/A6/A7 消费相同前置证据；required、成员、分母、格式不变。 |
| `tests/test_offline_evidence.py` | A9 | 经 A1/完整 A2/A3–A8 消费相同前置证据；required、成员、分母、格式不变。 |
| `tests/test_offline_evidence.py` | A10 | 经 A1/完整 A2/A3–A9 消费相同前置证据；required、成员、分母、格式不变。 |
| `scripts/a1_scope.py` | A1 | 原字节及 12 test 成员不变；entry 仅替换已审目标测试 SHA，无格式或计数变化。 |
| `scripts/a1_scope.py` | 完整 A2 | writer 仍显式消费原 12 个 A1 test；69 test、1401 分母与 refs 不变。 |
| `scripts/a1_scope.py` | A3 | 经完整 A2 继承相同固定测试事实；A3 引用、required 和验收含义不变。 |
| `scripts/a1_scope.py` | A4 | 原 A1 及完整 A2/A3 路径保留；仅承接已审映射，成员、分母和格式不变。 |
| `scripts/a1_scope.py` | A5 | 原 A1/完整 A2/A3/A4 引用保留；本组用途、required、分母和判据不变。 |
| `scripts/a1_scope.py` | A6 | 原 A1/完整 A2/A3/A5 引用保留；本组用途、required、分母和判据不变。 |
| `scripts/a1_scope.py` | A7 | 原 A1/完整 A2/A3/A5/A6 引用保留；消费相同测试事实，成员、分母和格式不变。 |
| `scripts/a1_scope.py` | A8 | 原 A1/完整 A2/A3/A5/A6/A7 引用保留；fixture、冻结覆盖及格式不变。 |
| `scripts/a1_scope.py` | A9 | 原 A1/完整 A2/A3–A8 引用保留；固定成员、required、分母和格式不变。 |
| `scripts/a1_scope.py` | A10 | 原 A1/完整 A2/A3–A9 引用保留；冻结需求及其验收证明边界不变。 |
| `scripts/a2_full_scope.py` | 完整 A2 | 原字节、69 test/60 source/38 fixture、1401 分母及格式常量不变；entry 仅来自目标 test SHA。 |
| `scripts/a2_full_scope.py` | A3 | 原完整 A2 直接引用保留；接收同一 69 test/1401 分母的证明范围。 |
| `scripts/a2_full_scope.py` | A4 | 原完整 A2/A3 引用保留；没有新增或削弱条件，成员、分母和格式不变。 |
| `scripts/a2_full_scope.py` | A5 | 原完整 A2 及 A3/A4 路径保留；用途、required、分母和判据不变。 |
| `scripts/a2_full_scope.py` | A6 | 原完整 A2 及 A3/A5 路径保留；用途、required、分母和判据不变。 |
| `scripts/a2_full_scope.py` | A7 | 原完整 A2 及 A3/A5/A6 路径保留；消费相同测试事实，成员、分母和格式不变。 |
| `scripts/a2_full_scope.py` | A8 | 原完整 A2 及 A3/A5/A6/A7 路径保留；fixture、冻结覆盖及格式不变。 |
| `scripts/a2_full_scope.py` | A9 | 原完整 A2 及 A3–A8 路径保留；固定成员、required、计数和验收含义不变。 |
| `scripts/a2_full_scope.py` | A10 | 原完整 A2 及 A3–A9 路径保留；冻结证明边界、成员、分母和格式不变。 |

前 10 行依据 Standards/Spec 独立审阅，后 19 行依据派生 scope 独立补审。
完整 A2 的普通 source 哈希更新沿用原有 source 摘要排除规则，source 成员和用途仍受检查；
不是额外敏感授权。全部 11 scope 的显式引用图逐边不变，A2-01 不属于本次敏感闭包。

## 冻结材料和开发验证边界

- 合并后逐字节核对原有 79 份 fixture、contract、example contract 与 `verification-runs/`
  材料均等于集成原 HEAD；包括 v1–v11 向量、旧 wire/schema 与历史 JSON。
- v1–v11 的旧 SHA 锚值保持；只追加 v12 锚。
- v12 向量 SHA-256 为 `cd2bb0f609180552ad722c5e5f3e9f8f0c76ada71cfd59a218a3e5fa9290cef6`；
  与 v11 同为 71 个源码成员，逐成员 SHA 匹配。仅 config/service、current_binding、site_binding
  三个源码摘要变化；admission v12、launch v8。
- 重绑前后全部 289 条固定计数逐条相等，对应 285 个独立模块；计数字典列表的
  `json.dumps(..., sort_keys=True)` SHA-256 为
  `3a118c063de55f1dc9f27bce966015991a028a337fea3ed912b80567a7de3905`。
  基线既有问题为 0，重绑后 1214 条文件登记全部匹配。
- 合并树指定六模块回归：96 passed（26.71 秒，退出 0），无 skip/deselect。
  全仓 Ruff check、format check（1581 files）、mypy（1125 sources）均通过。
  pytest 对原有临时垃圾目录出现非空清理警告；未改或清理无关历史目录。
- 当前提交完成后必须在最终 clean 身份生成 29 条树外确认，执行显式基线的
  `audit-verification-scope --confirmations ... --collect`，核对 289 条计数、285 模块、
  0 skip/deselect 与基线问题为 0。完整 `check-compatibility all` 的 176 节点重新运行，
  其最终结果和身份留在树外报告，不能复用前次中断。

未运行完整离线门禁、root 部署、现场 credential/cache 操作、模型或网络验收。
auth 刷新、自然到期与 owner 窗口三项异步裁决继续 pending；离线合并不代替这些行为。
