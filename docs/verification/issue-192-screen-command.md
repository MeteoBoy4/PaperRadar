# #192：显式两阶段 Screening 工程覆盖

本台账仅记录 B 独立 D1 工程覆盖，`stage_a_verified=false`，不进入 A1–A10
历史回执、固定分母或 required 集合。全部材料在 `/tmp` 临时根合成；未执行 live、
未访问真实实验根或真实凭据，没有用成功替身授予现场或正式消费资格。

## 覆盖与已确认接缝

| 独立模块 | 数量 | 工程断言 |
| --- | ---: | --- |
| `tests/test_experiment_screen_cli.py` | 22 | 缺选择、外发/严格证据/冻结依据拒绝；真实 CLI waiver/egress；生产 Feed 与合成固定供给/RPC 经 PiExecution 和权威接收取得两阶段 pi_rpc；Feed 派生语言；out_of_scope 停止 value；false inferable 不建下游任务；两次失败、精确重放、A→B→A 预算保持；阶段间及认证到领取之间换样/版本/授权变化；已领取 boundary 按原租约结算但不放行 value；ready 前置失败/中断后的明确回执执行；boundary 恢复后显式生产登记 value、重复仅回原回执及与 receipt 模式互斥；value 显式 retry 后继只执行该代；成功/耗尽/非当前回执拒绝；test 来源不晋级；所选根日志守卫及敏感内容不泄漏；冷进程帮助禁网络/SQLite/文件写入；真实备份与恢复子进程保留失败预算 |

CLI 为主接缝；只有明确故障/并发与恢复准备使用公开服务 API。HTTP 由
`httpx.MockTransport` 与注入退避时钟替代；供给下载/安装及 Pi 使用独立合成对端，
不 mock `PiExecution.run_attempt`、内部准入或成功接收。waiver 和外发授权均通过
已有真实 CLI 登记。并发用例仅在外部认证/RPC 返回处注入事实变化，最终资格由真实
短事务检查；未让拒绝进入模型失败结算，也未退款已领取预算。

恢复用例通过真实 `restore verify` 子进程及禁 socket 的公共历史查询子进程读取恢复
副本；移开原根后仍保留原 task/budget/generation 与两次失败。它不要求 Pi 安装、
认证或 Docling，不证明操作系统强制禁网或 #201 的现场回放闭环。

## TDD 与检查

可观察 red → green：未注册 screen 时缺选样用例失败；初始仅预验时没有两阶段 JSON；
显式 `--receipt-id` 未注册时 ready 恢复用例失败；value 后继初始拒绝 boundary_missing，
加入 FeedPipeline 公共生产依据读取后由原始合成 RPC 与权威接收成功。
boundary 回执恢复后默认重放无法新建 value；完整 CLI 反例先失败，再加入互斥的
`--continue-value` 与生产原子登记状态入口，明确继续才登记/执行，重复不续跑。
领取前正常授权拒绝最初误记 unexpected_error；增加受控 ClaimDenied 基类并在入口声明
受控组件异常后，零 attempt 且只记 controlled_failure。

本票功能模块、受影响 A7/Pi/Feed/选择/外发/日志子集与 CLI 入口兼容组合分别验证；
严格 mypy 包含全部九个触及生产文件和两个新增测试/支撑文件，Ruff、format 与 diff 检查。
实际命令、退出码与数量见本次外部交付报告。未运行完整离线门禁。

## 持久化、接口与预期漂移

不新增 migration、表或新的预算/成功事实；Alembic head 仍为既有
`b001_selection_authorizations`。不修改历史测试、fixture、向量、冻结 Contract 或 scope 哈希。

生产新增 `experiment/screening.py`；已有变更为：

- `experiment/cli.py`、`experiment/selections.py`：入口及事务外完整预验后的同连接当前行复核。
- `pi_execution/service.py`：认证前产品复核及 A7 Connection guard 透传。
- `screening_tasks/service.py`、`screening_tasks/execution.py`、`errors.py` 与公共导出：原子登记重放标志、只读登记/领取守卫、当前代际读取。
- `feed_pipeline/service.py`：同预算的历史生产 value 依据读取，含显式 retry 后继；
  生产新登记/重放标志与事务内产品守卫，不补挂新证明。

README、GLOSSARY 与 B/Pi/任务/Feed Contract 同步当前接口；组合规则只在 B Contract
定义，组件文档保留各自公共接缝。默认 request 重放不授予执行许可；显式回执模式不
新增请求、不创建后继、不自动执行另一阶段；`--continue-value` 显式登记缺少的 value。#193 消费这一入口提供产品恢复路径。

以上 source/support 字节漂移交 #185/#206 最终树审阅、必要重绑及 S3 确认，不机械
重绑。D7 `live-admission-source-guard-v25` 的 service.py 源码哈希漂移保持受控拒绝；
#191 的 launcher/RPC 等漂移另在其台账记录。旧 v1–v25 向量、策略与证据保持原字节，
最终策略/向量推进由 #206 负责；功能子集通过不代表 D7 或完整门禁通过。

## 未验证边界

真实 Feed 字段/语言约定、固定 Pi 认证刷新与生成、供应商参数效力、现场隔离/资源、
实际论文质量、Docling 与真实纵向闭环均未验证。Screening 不建立决定、建议、Read、
reuse 或自动任务；#194 及后续 B 能力继续消费明确成功与选样授权，不能把本票合成
工程结果解释为现场执行许可。
