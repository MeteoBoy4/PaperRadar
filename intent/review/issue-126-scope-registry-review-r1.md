# Issue #126 Scope Registry 两轴审查（r1）

- 固定点：`main`（`e6c1ec74c9fc8d15fc8f76d2c8a7b29fcdda9438`）
- 比较命令：`git diff main...HEAD`
- 规格来源：GitHub #126、#132–#137 的正文与评论（评论优先）
- 审查方式：Standards 与 Spec 两个独立 subagent 并行审查；二者均具备 `bash` 权限

## Standards

发现 4 项；测试未运行。

1. **确定性逻辑与 I/O 未分离 — hard violation**  
   `scripts/verification_scope_baseline.py:416-456`：`_changes()` 名义上比较两棵树，却通过 `_category()` 读取 AST，并直接执行 `_sha(old, path)` / `_sha(root, path)`。违反 `docs/agents/python-conventions.md`「确定性逻辑与 I/O 分离」，使比较逻辑依赖实时文件系统。最小修复：在编排层预采文件哈希及 AST 分类事实，将快照传入纯 `_changes()`。

2. **Duplicated Code — judgement call**  
   `scripts/a8_acceptance.py:168-183` 与 `scripts/verification_scope_registry.py:522-543` 重复遍历 `acceptance_groups()`、`inspect.getsourcefile(group.write)` 并转换相对路径：  
   > `for group in acceptance_groups(): source = inspect.getsourcefile(group.write)`  
   两处错误策略不同，但发现逻辑同形，后续登记方式变化需同步修改。最小修复：提取可指定 implementation root 的 writer 路径发现 helper，各自保留错误处理。

3. **Data Clumps — judgement call**  
   `scripts/verification_scope_baseline.py:378-425`：`report / paths / references` 以 old、new 两份在 `_entry_identity()`、`_changes()` 间成组旅行；`_changes()` 因此有 8 个参数：  
   > `baseline, report, old_paths, paths, old_references, references`  
   最小修复：定义单树视图类型，封装 root、report、paths、references，以两个视图传参。

4. **Mysterious Name — judgement call**  
   `tests/extensible_acceptance_support.py:87-95`：`frozen_bytes()` 实际返回 `dict[str, str]` 的 SHA-256 十六进制摘要，并非 bytes：  
   > `hashlib.sha256(p.read_bytes()).hexdigest()`  
   名称误导内容类型。最小修复：改名 `frozen_sha256()` 或 `frozen_digests()`。

## Spec

Spec 轴审查结果：**无发现**。

- **missing / partial：无。** #132–#137 的显式基线、S3 逐组确认、中央登记、显式 scope DAG、新组贯通、跨 spec 合并规则及 D1 台账均有对应实现与回归。
- **scope creep：无。** 门禁后的 pytest 临时材料保留策略属于完成规定离线门禁的修复，并有独立台账与行为测试。
- **wrong implementation：无。** 未发现确认失效、基线漂移、历史读者独立性或 required 集合被绕过的问题。

定点验证：`uv run --offline --locked pytest tests/test_scope_shared_dag.py::test_production_migration_keeps_exact_materials_counts_and_graph -q`，结果 **1 passed in 0.36s**。未运行完整门禁。

---

汇总：Standards 4 项（最严重：`_changes()` 将确定性比较与文件系统 I/O 混合的 hard violation）；Spec 0 项（无最严重问题）。


## 本批核实与处置（#126，base `bfc7117`）

逐项对照源码与仓库约束，4 项均采纳；本批保持公开 Python/CLI 契约、错误策略、敏感分类及确认身份语义。

1. 确认 `_changes()` 混入文件读取。`scripts/verification_scope_baseline.py` 在编排层采集两树的文件 SHA 与 AST 敏感常量，生成只读 `_TreeView`；`_changes()`、分类、entry 摘要和影响组比较只消费快照。快照不保留 root，原末尾树/HEAD/target race 复核保留。
2. 确认 writer 发现重复。`scripts/verification_scope_registry.py::discover_writer_paths()` 统一 registry 遍历、source 检查和相对路径转换，显式接收 implementation root。A8 继续从当前执行实现根发现路径，再读取传入 root 的 AST；继续跳过无法定位和树外 writer。registry 缺 source 继续给出 `writer_unavailable`，树外路径错误继续由 CLI 转成 `registry_unavailable`，不从宿主补读登记。没有新增模块或循环依赖。
3. 确认单树数据成组旅行。只读 `_TreeView` 封装 report 需要的 files/counts/downstream、paths、references 身份与预采事实，比较入口改为两份视图，entry 摘要改为单视图参数；分类顺序、双 origin、登记与全部下游影响计算保留。
4. 确认函数名与返回值不符。`tests/extensible_acceptance_support.py` 的 `frozen_bytes()` 及唯一调用者改为 `frozen_sha256()`；返回字典和冻结检查保持原行为。

开发验证：基线/分类/确认/并行集成/中央登记/DAG/新组贯通 120 passed；新增 `tests/test_scope_writer_discovery.py` 5 例与公开审计、A8–A10 writer 组合共 70 passed。中央只重绑本次三份 source 的 SHA；只读 collect 审计 exit0，285 固定模块 / 5281 例、1203 条登记保持。旧六冻结 scope/审计测试和既有证据原字节保留。上述均为开发验证，未运行本次完整 `check-offline` 或 live。


### 合批最终开发验证

与 r4 合批后：相关 pytest **237 passed / 206.59s**；`check-compatibility all` **176 passed / 325.79s**（入口总 326.39s，exit0）。低版本 shim 加强后 R4 模块再次 **15 passed / 3.96s**，实际模拟 3.11 执行探测，并拒绝树外将门槛误放宽至 3.10 的变异。全项目 Ruff check、format（988 文件）、mypy（710 source files）通过。默认及显式基线 collect 审计均 exit0，无既有漂移、固定 285 模块/5281 例、skip0/deselect0。本批共重绑四个中央 SHA（原三份 source 加 r4 的 `check-offline`），展开 18 条原成员资格；四个候选均为 mechanical source/support。旧成员、用途、分母、41 refs/0 scope hash 保持，原六冻结测试及旧证据不改。精确旧新 file/entry SHA、消费闭包与历史留痕见 `docs/verification/issue-126-review-followup.json`。本次未运行完整 `check-offline` 或 live。
