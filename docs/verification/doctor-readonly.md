# doctor 独立离线工程证据

范围：#124 的只读 CLI。T07 的调用隔离另见[独立映射](t07-call-isolation.md)，两者不互相替代。
新增测试模块不加入历史 required 集合，不改 A1–A10 的固定分母或冻结 JSON；完整收口由 #125 承接。

| 需求 | 公共边界 | 独立证据 |
| --- | --- | --- |
| US1、US2、I11/T06/D03：基础工程与四态 | doctor basic/config；现有存储 revision 服务 | `test_doctor_readonly.py`；`test_doctor_process.py::test_database_failures_are_controlled_and_readonly`、`test_invalid_packaged_migration_is_controlled`、不可读库/非文件路径用例 |
| US3、US4：明确原因、下一步与显式选择 | doctor 参数、只读 check/load/reference | `test_help_and_usage_errors_have_no_io_or_sensitive_echo`、`test_invalid_selection_never_writes_or_falls_back`、`test_selected_config_is_readonly_and_discloses_only_selected_models` |
| US5、US6、D03：基础通过与未配置共存，六阶段独立 | doctor config 的选择层与六阶段 readiness | `test_config_missing_stages_passes_without_persisting_snapshot`、`test_invalid_selection_keeps_basic_passed`、`test_placeholder_or_unconfigured_slots_only_change_stage_readiness` |
| US7：数据外发说明来自所选配置 | doctor config | `test_outbound_categories_follow_stage_data_boundary`、所选 settings/snapshot 模型披露用例；不读凭据哨兵 |
| US8、相关 T24：成功/错误/help 的只读与脱敏 | 已安装 CLI 冷进程 | 独立 `doctor_guard/sitecustomize.py` 拒绝网络、subprocess/exec/spawn/fork，help 拒绝 SQLite；成功与材料错误均比较逻辑库与忽略 sidecar 的文件树 |
| US9、B/Pi readiness：安装、配置和真实验收分开 | doctor 九类骨架与旧 pi-supply | config 不读供给/审计表、不遍历安装目录；`not_assessed` 保留承接；旧供给黄金字节用例 |
| US22、T07 | build_call/render_request 与既有任务/RPC 公共入口 | [T07 映射](t07-call-isolation.md)，独立 `test_t07_call_isolation.py` |

`tests/doctor_pi_supply_golden.json` 来自基线 `3439453` 的 doctor CLI：未激活退出 2、已激活退出 0。
只将 activation/supply/install 动态身份替换为模板，测试从公开 API 回执填入本轮身份后逐 UTF-8 字节比较 stdout/stderr。
未改既有有效调用的其他文本、行序、空格或退出码。

公开行为的红绿切片覆盖 basic 可用、config 选择与阶段缺失、基础类四态、basic 未选配置提示、
选择非法但基础通过、外发数据边界、非文件数据库，以及真实不可读文件被参数层提前拒绝的问题。
T07 原实现已有这些能力，新测试补回归证据；在临时包副本注入 boundary 带 topics、载荷多余键、
修正说明跨 attempt、unsupported stage 错误类别四种回归，分别检出 2/2/1/2 个失败，恢复后 6 项通过。
产品 `build_call` 源码与支持范围保持。

验证以本票本地相关 pytest、`check-compatibility cli`、Ruff 和 mypy 为准；原始运行记录及 scope 漂移
摘要交接到共享 `/tmp/paperradar-issue-120/handoff-124.md`。这些开发检查不发布正式阶段结论。

本次相关 pytest 386 项通过（其中新增独立 doctor 42 项、T07 6 项）；CLI compatibility 59 项通过。
Ruff lint、14 个触及文件的 format 检查、mypy 670 个文件与 `git diff --check` 均通过。
已有 schema/metadata 比较用例产生一条 SQLAlchemy 循环外键排序 warning，没有失败。
未运行完整离线门禁。T06 这里只证明诊断不改变库/配置事实；任务恢复与 NAS 仍由 #125/I 承接。

未验项：真实 Pi/Node/npm 生产启动器与 RPC、cwd 资源/权限隔离、外部模型/认证、四刊来源审计与 JGR 判据、
Docling 依赖/模型/四刊正文 fixture 与内存、正式校准、reuse/Read 消费者与 map/reduce、NAS、无人值守。
它们分别由 Pi/Cwd/Live、Audit/Source、Extra/Body/F、D/G、I/H 承接；合成/fake 证据不证明 live 就绪。
