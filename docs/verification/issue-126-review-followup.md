# #126 r1/r2/r4 审查修复覆盖台账

本轮基于 `bfc71177d38eb0355a7760f22a3554ba31834e42`，逐项核实三份用户报告。
r1/r2 原文逐字相同，按 4 个独立建议同批处理；r4 的 Standards 5 项、Spec 3 项分别处置。
三份报告保留原文前缀并追加判断；原 SHA、精确重绑和本轮独立覆盖见[机器台账](issue-126-review-followup.json)。
本台账补充新的开发事实，不修改旧冻结台账、历史 JSON 或旧结论。

## 改动与判断

- r1/r2 四项均采纳。基线编排先按原分类优先级选择需要 AST 的路径，再预采文件 SHA
  和敏感常量；不额外读取直接归类为 test/fixture/evidence 的材料。单树只读快照保存
  files/counts/downstream、paths、references 身份与预采事实，不持有 root。
  比较、entry 摘要、双 origin 与影响组计算不读文件；树/HEAD/target 的末尾 race 复核保留。
- writer 发现集中在既有 registry，显式传 implementation root；A8 从执行实现根发现路径，
  从传入 root 读取 AST，继续跳过缺 source/树外 writer。registry 继续将缺 source 转为
  `writer_unavailable`，树外错误在 CLI 转为 `registry_unavailable`。没有新模块或反向依赖。
- 返回摘要的测试支撑准确改名为 `frozen_sha256()`，保留原返回值和冻结断言。
- R4 Standards 1/2/4 采纳：路线图只留承接与规则链接；帮助缺解释器、无法运行或版本低于
  3.12 时中文指引 exit1，正常帮助仍不启动 uv/writer/检查或写产物；Contract 保留公开保证，
  测试维护细节归本台账与测试规则。
- R4 Standards 3 采用其最小替代建议：保留历史 `A1_GROUP`/`A2_01_GROUP` 与单独 A1 API，
  新增独立元数据一致性回归；只把精确两路径的 legacy 显式声明按原序纳入敏感摘要。
  不删除公共对象，不在生产 registry 强制不一致拒绝；`GROUPS` 策略变化保持原分析行为。
- R4 Standards 5 部分采纳。原已有 `unlisted_scope`、`non_scope_reference`、`invalid_graph`
  三个公共 writer 负例，最后一个覆盖审计失败，因此拒绝「无失败覆盖」的事实判断。
  单一调用者使用公开 registry/audit 校验冻结指针职责合理，未强抽服务层。
  采纳诊断改进：既有 `scope_drift` 下用 `item=scope_references.<受控审计原因>` 定位，
  不回显异常或非法内容，不新增 reason、字段或格式版本。

## 精确重绑与消费闭包

仅更新 `scripts/verification_scope_materials.py` 中四个实际变化路径的 SHA：
`a8_acceptance.py`、`verification_scope_baseline.py`、`verification_scope_registry.py`、
`check-offline`，展开后 18 条原成员资格变化；逐路径旧新 SHA、中央位置、各 scope 用途和
直接/下游组在机器台账列出。审计器及解释器自身旧绑定也显式重绑，未用它们的旧 SHA
跳过本轮解释器变化。共享发现和比较事实留在既有 source 闭包，不新增生产成员或 import 依赖。

scope/中央文件仍不进入组哈希闭包；11 组/10 required、255 个共享材料、1203 条登记、
695 路径、285 个固定模块/5281 例保持。scope 哈希边为 0、显式 refs 为 41。
六冻结 scope/审计模块、原 10 个准备模块/78 例、独立人工预期、reader 支持表、
业务源码、Stage fingerprint、Frozen Contract、Schema 与 migration 保持原字节或语义。

本轮新增两个未绑定模块，不纳入旧 scope/回执，也不扩充历史固定分母：

| 模块 | 例数 | 公开接缝与判据 |
| --- | ---: | --- |
| `tests/test_scope_writer_discovery.py` | 5 | 显式实现根；CLI 缺 source/树外受控错误；A8 跳过两种不可定位额外 writer |
| `tests/test_scope_review_r4.py` | 15 | 帮助失败、宿主及相对项目环境 5；legacy 一致性 1；两路径四字段重绑仍敏感 8；A8 受控诊断 1 |

## 测试维护与补充历史定位

独立人工预期为 `tests/fixtures/verification_group_expectations.json`，读取支撑是
`tests/verification_expectations.py`，两者均在中央固定。帮助、组后缀和完整产物集合
按该独立清单核对，预期不从生产登记或实际输出生成。旧 entry 单测的模拟 executor
只消费独立 fixture 模块清单，不能充当真实执行证据；新组扩展回归另行启动真实 pytest，
使用目标实际执行计数。这些维护细节不再复述于状态查询 Contract。

R4 Spec 1 的留痕补充为历史 `tests/test_tmp_path_cleanup.py`：
`622d3ab`→`bfc7117` 仅在原循环四次子会话传入 `-o tmp_path_retention_policy=all`，
继续检验最终保留三个成功会话，以及原权限/软链断言，模块仍为 8 例。
旧 SHA 为 `65aea68a7ec369c044d4a230799189137fb7b0a32b2a39e91d8a6c612653e40c`，
新 SHA 为 `f9ab3485dc7e6c34bea7075fbc2e66c41573ffe25a65e8c74c04f11aa1d04529`。
本轮该测试字节不变；这里补充旧台账的散文定位，不追改 `gate-failure-repair.md`。

R4 Spec 2/3 为口径说明：`cli.py` 示例只改 1 行中央 SHA，7 个直接组 + 3 个额外下游
= 10 个受影响组；scope 哈希边实际 41→0，42 为已披露的旧描述口径，不改冻结历史凑数。

## 开发验证与限制

R4 有效 red 为 12 failed / 3 passed，分别命中帮助 3、敏感声明 8、A8 诊断 1；
初次合成 scope fixture 的无效 red 已纠正后重跑，不作为证据。修后该模块 15 passed。
低版本 shim 实际执行传入探测代码并模拟 `sys.version_info=(3,11,0)`；加强后的公开 CLI
单例通过，树外把门槛错放宽至 3.10 的变异被该单例拒绝。真正帮助保留正常 sitecustomize 守卫。

合批相关测试 **237 passed / 206.59s**；`check-compatibility all` **176 passed / 325.79s**，
入口总耗时 326.39s、exit0。加强低版本 shim 后，R4 模块再次 **15 passed / 3.96s**。
全项目 Ruff check、format（988 文件）和 mypy（710 source files）通过。
默认与显式基线 collect 审计均 exit0、无 issues，固定 285 模块/5281 例、skip0/deselect0；
显式基线无既有漂移，本轮只有四条 mechanical source/support 变化，无需敏感逐组确认。
相关测试包含六个冻结 scope/审计模块；新增 20 例只属于本轮开发选择。
本轮未运行完整 `check-offline`，不发布正式 A1–A10 结论；历史门禁不代表本次新树。
未运行 live，不证明完整阶段 A、四刊 live、Pi RPC、模型质量、正式校准、Docling 或 NAS。
