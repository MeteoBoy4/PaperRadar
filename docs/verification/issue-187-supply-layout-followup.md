# #187 后续：实验根与 Pi 供给布局组合工程覆盖

本台账是独立 D1 跟进，不回写原按次证据，`stage_a_verified=false`；不进入
A1–A10 历史回执、固定分母或 required 集合。不新增 Alembic migration、表或 Schema。
全部测试材料位于 `/tmp`；不执行 live，不访问真实实验根或真实凭据。

## 接缝与判别力

| 独立 D1 模块 | 当前用例数 | 本次覆盖或适配 |
| --- | ---: | --- |
| `tests/test_experiment_supply_layout.py` | 10 | 新增实际 CLI init→Feed→配置→供给 prepare/verify/activate→模型探测→Screening 组合；原数据库及预算重放；非空旧 blobs/tmp 受控拒绝并保留字节；仅用途登记空库保持 inode/root_id 补建 data；`data/`、`data/blobs/`、`data/tmp/` 的链接和错误类型拒绝 |
| `tests/test_experiment_feed_cli.py` | 21 | init 安全相对输出及 Feed/元数据回查使用实际 data_root；增量回执使用明确类型；原成员和断言保留 |
| `tests/test_experiment_candidates_cli.py` | 18 | 候选制品/事实与备份输入使用实际 data_root；恢复后工作副本放入 data/blobs，不改 restore 输出格式 |
| `tests/test_experiment_selection_cli.py` | 29 | 选样事实回查、备份及授权验证使用实际 data_root |
| `tests/test_experiment_accept_migrations.py` | 6 | 非空历史升级/原子回滚材料沿实际 data_root 回查；旧 revision 与 head 预期不变 |
| `tests/test_stage_b_egress_preflight.py` | 41 | init 后在同一实验库编译配置并供给，四根取实际布局；attempt 冲突负例仍指向制品临时目录 |
| `tests/test_model_mapping_rpc.py` | 10 | 未修改，独立 RPC 映射探测与拒绝回归 |
| `tests/test_stage_b_model_mapping.py` | 11 | support 改为先 init、同库配置/供给/激活；不再搬数据库或重新登记根 |
| `tests/test_experiment_screen_cli.py` | 22 | 实际 data_root 的任务、源/预算、重放、失败和隔离恢复组合 |
| `tests/test_experiment_accept_cli.py` | 27 | 实际 data_root 的成功依据、authorizer、visibility、代记决定及备份恢复组合 |
| `tests/test_screening_recovery_trace_cli.py` | 23 | 显式 retry→screen→continue-value→trace 消费实际 data_root |
| `tests/test_experiment_selection_migrations.py` | 4 | 未修改，旧迁移保留回归 |
| `tests/test_stage_b_production_prompts.py` | 10 | 未修改，完整帧与 Prompt 预算保留回归 |

上述 232 项属于 B 独立 D1 组合，不减少旧成员或合并历史计数。
`experiment_screen_support.py` 与 `model_mapping_support.py` 只替换 HTTP 下载、安装程序、
合成 RPC 与已确认的系统边界；根布局、`safe_roots`、准入、任务领取、接收与预算使用
真实产品实现。waiver 和外发授权走真实 CLI。供给、模型探测、任务消费采用同一实验库，
同一个 `ExperimentRoot.data_root`；不使用影子 data/config/material 根。

## TDD 与验证边界

第一条组合回归在修前由真正 `safe_roots` 报 `unsafe_root`，修后可完成
prepare/verify/activate/probe/screen，且再次 screen 仅返回原回执。
旧非空 blobs/tmp 的两个回归在缺少拒绝守卫时错误返回成功，补守卫后受控拒绝；
原库与旧材料字节不变，不自动搬迁，不另建库绕过预算。

开发期检查包括全部 B 组合、供给/backup/restore/模型映射、Feed 与正文/任务恢复消费者、
精确节点 `test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`、
`check-compatibility cli`、默认 strict mypy（src 及所有新增/修改测试 support）、
Ruff/format 和 diff 检查。精确 Schema 比较保持一致，仅有既有循环外键排序 SAWarning。
供给/backup/restore/模型映射与该精确 Schema 节点组合为 386 passed；CLI 兼容为
59 passed。全部 B 独立 D1 与本次新布局模块同树合计 232 passed；默认 strict mypy
为 408 个文件通过。Ruff/format 与 diff 检查通过；不运行完整离线门禁。

### #206 固定测试适配审阅候选

扩展普通 library 消费者组合为 106 passed、3 failed。失败节点分别是
`test_feed_backup.py::test_feed_backup_restores_originals_and_interpretations_after_move`、
`test_paper_backup.py::test_backup_restores_paper_identity_and_candidates_in_new_process` 与
`test_source_backup.py::test_nonempty_wal_backup_restores_all_source_history_in_new_process_after_move`。
三者均是旧冻结测试将 CLI trace 整对象与 PaperFacts.trace 模型比较，实际多出
`workflow` 字段；相关 CLI/trace 源码及三项测试与 integration 基线相同，本票未改。
`git diff --exit-code integration/185-stage-b -- src/paper_radar/papers/cli.py
 src/paper_radar/paper_trace.py tests/test_feed_backup.py tests/test_paper_backup.py
 tests/test_source_backup.py` 返回 0（基线 `7bab8d3307372fb26d02244969577104eaa06c24`）。
这项现有兼容差异仅列为 #206 固定测试适配审阅候选；保留旧用例、计数和 fixture，
不回退新 trace 契约，不削弱断言或回写旧证据，不宣称全消费者全绿。

## 预期漂移与后续责任

源码漂移仅 `src/paper_radar/experiment/{root,cli}.py`；support 漂移为
`tests/{experiment_screen_support,model_mapping_support}.py`；测试漂移为上表本次适配的
模块（模型映射 CLI/RPC 模块本身、selection migrations 与生产 Prompt 模块未改），另新增
`test_experiment_supply_layout.py`。现状文档为 README 与 B 工作流 Contract，
新增本台账。旧按次证据、冻结 fixture、required 集合、D7 v1–v25 向量和策略均不改。
#206 承接最终代码树漂移/S3/必要白名单审阅；本票不机械重绑。

数据库保持 `paper-radar.sqlite3`，仅制品根改为 `data/`；config/views/logs 保持。
普通 library 的显式 database/data_root 接口与 restore 的 `database.sqlite3 + blobs/`
格式不变。非空旧布局的真实材料处理、实际 Pi 供给/认证/模型生成、真实 Feed、
Docling、现场隔离与纵向 live 仍由后续明确授权的会期承担，本票不处理 runtime。
