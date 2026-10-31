# #133 首批中央登记交付台账

本台账独立于第一步冻结证据。实施起点为 `83750f04c5fd5f2b9cb5cf71607f7dbfdb5667de`；
第一步稳定基线为 `e6c1ec74c9fc8d15fc8f76d2c8a7b29fcdda9438`。
逐组旧绑定、中央成员、计数、测试字节与新增成员见
[机器台账](scope-central-registration-delivery.json)。未运行完整门禁，不形成正式验收结论。

## 过渡与实际成员

先从 Git blob 原字节导出旧树，在冷进程用旧解释器确认 `issues=[]`，仅保留 #132 已披露四条漂移：
A8/A9/A10 的 `verification_scope_audit.py` 与 A9 的 `audit_verification_scope.py`。
再引入中央解释，迁移前与旧解释器逐组比较完整有序绑定与计数相等。
最后迁移十二个既有共享基础设施路径，展开结果再次逐项相等；未删除旧校验或按同 SHA 去重。

中央现有十四个路径、九十三条成员资格；其中十二个原有路径的八十八条登记改为中央引用，
新增审计支撑另有五条成员资格。既有十二条中央 SHA 保留旧预期，未机械接受候选。
新支撑首次登记本票实际字节：`verification_scope_baseline.py` 登记 A8/A9/A10，
因为三组固定审计核心的公开显式基线能力实际调用它；`verification_scope_collection.py`
登记 A9/A10，因为 A9 的审计 CLI、A10 的审计包装入口实际调用该收集支撑。
这五条是明确新增 source/support 成员，不能冒充旧集合等价。

旧母集为 1211 条登记、699 个唯一路径；本步为 1216 条、701 个路径。
旧共享非 scope 路径 250 个，本步实际 tip 为 252 个（新增 baseline/collection），不能沿用 e6 的250作为最终母集。
同一路径各组 kind/role 保留，测试、fixture 与证据用途的变化均保持敏感。
首批未迁移业务源码、全部测试或其他共享支撑，交 #134 承接。

scope 哈希边定义为审计 files 中 `path` 等于实际生产 scope.path 的每一条合法登记，
方向为被引用 scope 到消费 scope。当前实际 41 条，按 A1/A2-01/完整A2/A3/A4/A5/A6/A7/A8/A9/A10
分别为 0/0/1/1/3/4/4/5/6/8/9。本步没有移除这些边。
原 `78413e6` 与 e6 按相同定义均为41；票面及第一步冻结说明中的42不据此改写。
完整边清单沿用旧解释器报告及本台账的全部旧绑定，取消边交 #134。

## 新增覆盖与兼容修改

独立、未绑定模块 `tests/test_scope_central_registration.py`：17例，不扩大历史 required 分母。
覆盖中央 tuple 等价、同组新旧语法共存、真实材料漂移、缺失/未知/非法/重复/循环/动态/冲突拒绝、
原始 replace 禁止中央整文件哈希、中央 SHA 单独变化的基线映射、机械与敏感/跨 kind 逐组确认，
以及真实 A8 writer 对中央离线说明材料字节漂移的拒绝。

六份公开冻结 scope/audit 测试与第一步结束时字节完全相同，逐文件 SHA 在 JSON 中。
两项未绑定 D1 兼容修改也逐文件登记旧新 SHA：

- `test_a8_a9_document_scope.py` 保持原移除清单与完整集合精确比较，独立显式补上 A8/A9 三条新支撑成员；用例数不变。
- `scope_document_support.py` 增加中央字典 SHA 的白名单重绑支持，仍先审计并拒绝调用方未审阅路径，保留各测试模块独立白名单。

## 验证与交接

真实树 `uv run --offline --locked pytest -q tests/test_scope_central_registration.py tests/test_scope_baseline_audit.py`：
51 passed（17新增、34基线）；Ruff 17个新改模块检查与格式通过，配置 mypy 700个模块通过。
白名单候选相关子集206 passed / 102.11s，包含六冻结模块与第一步全部93例。
候选 `./scripts/check-compatibility acceptance`：117 passed，exit0，总215.56s。
真实树同组合61 failed / 56 passed，exit1，总209.26s，旧scope哈希漂移使正常前置被拒绝；
候选只修正相同的已解释漂移即全部通过，不能把候选结果当正式验收。

候选副本只允许实际审阅的 audit/registry/baseline/CLI 文件与旧 scope DAG 必要传播，
实际修改2处中央SHA、1处CLI字面量SHA和33处scope传播SHA，不写生产登记。
初轮候选204 passed、1例因候选缺 `.venv/bin/python` 入口失败；补软链指向实际磁盘环境后
最终206例全部通过，没有复制现有venv或搬迁根工作树历史run证据。
当前真实树保留已解释漂移：继承 #132 四条、registry 三条，以及本步 scope 字节变化的旧哈希边。
结构错误不能视为预期漂移；中央与旧字面量路径都继续核验真实材料。

#134 承接余下共享母集与 scope 边取消，沿用本票中央语法及 #132 确认身份；
#137 统一审阅实际变化、敏感确认与必要重绑，归并本模块17例和 #132 的34例覆盖，再按用户指示验收最终树。
不改历史 JSON、第一步冻结台账、已接受 ADR 正文、业务源码、Schema、migration 或历史状态读者。
未验证四刊 live、Pi RPC、模型质量、正式校准、Docling、NAS，也不形成完整阶段 A 结论。
