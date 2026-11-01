# Issue #143：采样声明与 Pi 一次执行组合

依据 [#143](https://github.com/MeteoBoy4/PaperRadar/issues/143) 和父票
[#140](https://github.com/MeteoBoy4/PaperRadar/issues/140) 最终 C/D、B/N 裁决。
实施基线 `9967e87`（已集成 S1/S2），分支 `feat/issue-143-pi-execution`，初始 dirty=false。
本台账是新增 D1 范围，不加入或扩大 A7/A8 历史测试分母，也不产生 live 结论。

## 独立覆盖

已确认 seam 为公共配置编译/回放/投影、llm 外一次任务执行、纯证据判定与必要
cwd opt-in、Feed 组合和恢复。标准库对端独立编写 auth/RPC 消息及候选字面量，
未使用产品生成器推导预期，未迁移或改写 A8 helper。

| 未绑定模块 | 数量 | 覆盖 |
| --- | ---: | --- |
| `tests/test_models_v2.py` | 20 | provider_default/explicit 合法编译及历史加载，缺/混/非法参数，严格根格式分派，Screening/reuse/Read 实际消费者及校准影响 |
| `tests/test_pi_execution_admission.py` | 15 | 13 项身份绑定拒绝，产品恒 missing，显式采样映射为空，冷进程纯导入不连接 auth/launcher/安装保护 |
| `tests/test_pi_execution_service.py` | 32 | 领取前缺证据/错配/三项未验、v1/v2 explicit、cwd污染/隔离/auth/argv/路径/外层帧/损坏快照/未登记协议拒绝；真实本机受保护隔离进程与权威成功；四类RPC失败、cwd opt-in、输出及模型权威拒绝、leader退出/孤儿组回收，领取后cwd/exec预算、两次尝试/显式retry、中断租约与outcome_unknown、本次审计与首次语义分离、安全sink与敏感哨兵 |
| `tests/test_pi_execution_feed.py` | 1 | use_install→启动→PipeSession→run_call→run_once→pi_rpc查询→Feed生产value登记→value成功→备份恢复；原根不可访问时历史回放，新执行产品缺证据零领取 |
| 合计 | 68 | 无 skip/deselect/incomplete |

`tests/pi_execution_service_support.py` 与 `tests/pi_execution_rpc_peer.py` 是新支撑，不计用例。
供给的 Node/Pi 是复制的 Python 可执行文件和独立标准库对端，无真实 Pi/Node/auth/模型。
Python runtime 白名单只由测试私有注入，产品不开放该运行树。对端断言独占 settings、
敏感宿主 env 不继承、业务 DB 和 refresh 凭据文件不可读；不提供产品转储入口。

## 验证

TDD 首先观察 v2 extra-forbid 与缺少执行服务的红灯，再逐片实现。命令统一
`uv run --offline --locked`；uv 缓存锁按已授权权限运行，无联网补包。

最终相关回归 **436 passed**，115.01 秒：上述四模块，加历史
`test_config_material_compatibility`、`test_config_prompt_identity`、`test_config_projections`、
`test_config_projection_adapters`、`test_a8_call_description`、`test_a8_rpc_preflight`、
`test_a8_rpc_lifecycle`、`test_a8_rpc_pipes`、`test_a8_llm_architecture`、`test_feed_pipeline`、
`test_pi_execution_launch`、`test_pi_rpc_source`、`test_pi_rpc_source_backup`。
历史配置黄金字节/ID、A8 默认行为及 Feed test拒绝/current/out_of_scope/语言规则保持。
在该相关组合之后补齐缺安装、缺cwd和凭据资源非法三例（无产品代码变化），
最终新增独立子集 **68 passed**。Ruff通过，mypy检查28文件通过。
触发 `./scripts/check-compatibility cli`：**59 passed**，退出0，入口总耗时64.72秒。
不把开发组合当正式回执。

## 实现与漂移

models-v2 根级 format_version:2 严格分派；旧 ModelSlot/Models dump 与 snapshot/projection
格式版本保持。provider_default 保留参数缺席；sampling 只随实际 model 消费者进入语义。
执行服务在 llm 外，证据为纯内存值且产品读取恒 missing；无证据表、migration、文件写入、
产品 passed 导入、任意命令/cwd/factory 接口或模型执行 CLI。sink 原样复用任务日志。
只增加默认关闭的 RPC cwd 期望参数，贯穿 system.sections 校验，未改默认协议条件。
Feed 登记/回放只接收闭集 pi_rpc；根用途和 B 隔离权威不变。

同步 runtime-config/config-projections/adapter-config/pi-rpc/pi-execution/feed-pipeline、
规格、术语与能力摘要；新增 ADR-0040，既有 ADR-0020/0023/0026 仅在状态行加入反向链接。
没有修改 A4/A7/A8 历史 fixture、冻结测试/helper、scope 成员、计数或哈希。
只读审计 `issues=[]`，预期实现 hash drift 影响 A2-01、完整A2、A3–A10；
其中包含基线 S2 漂移，不能以本票确认清掉。新增 D1与精确重绑交 S4 统一收口。

## 未验证

未运行完整离线门禁、真实 Pi、真实 auth、网络/模型或 `/srv/pi-cwd` 现场探测。
产品缺 Cwd/Live 证据，真实执行在领取前阻断。实际参数、订阅资格/模型权限/额度/用量、
RPC及cwd包装、TLS/DNS、现场Landlock及主机级出站、隐含retry/预热抑制与DERIVED-01…11
仍由 Cwd/Live/EXP-2 承接；合成成功不是供应商独立证明或兼容 passed。
provider_default 不承诺确定参数/逐字重现，不自动继承校准门禁。
非test来源不授予B实验正常生产、正式校准或Read消费资格；无新增Read/reuse执行。
