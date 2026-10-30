# 运行日志

## 用途与范围

运行日志是可能被保留上限淘汰的诊断事件流，用来关联一次执行及阶段任务明细。
SQLite 任务、审计执行事实和成功制品仍是 trace 的依据；日志不是完整审计账本，不能重放业务状态。

`paper_radar.runtime_logging` 提供唯一 `Sink.emit(Mapping[str, object])` 协议、
`NullSink`、`FileSink` 和负责安全字段与生命周期的 `RuntimeLog`。
服务显式接受 `sink=`，省略时使用 `NullSink`，不写持久日志。
构造服务或 `FileSink` 不访问文件系统，首次事件才尝试创建日志目录。
审计入口的显式邮箱预检先于首次事件；缺失或非法邮箱仍不创建数据根。

| 公共边界 | 注入方式与事件 |
| --- | --- |
| `ScreeningTasks.claim/fail/submit/reclaim/run_once` | `sink=`；任务事件，成功、失败与回收在结算事务返回后记录 |
| `FixtureAudit.run_audit/resume_audit/acquire_source` | `sink=`；入口事件与独立路线结算，内部取得服务共用同一汇 |
| `JGRFeed.check/resume` | `sink=`；入口事件与 Feed HTTP 路线结算 |
| `JGRMetadata.enrich/resume` | `sink=`；入口事件与各元数据路线结算 |
| `FeedPipeline` | 将同一显式 `sink`、`clock`、`monotonic` 传给 Feed、元数据与任务服务 |
| `audit run/resume` | 已交付执行 CLI 各自构造 `FileSink(data_root)`；`--data-root` 是显式所选根 |

`FeedPipeline` 是库组合服务，不推断生产根或实验根，不自行启用文件日志。
现有 Feed CLI 只有只读事实查询；没有 Feed 导入、Screening 生产执行、实验命令或 run-due CLI。
这些入口在 [B](../roadmap.md#module-b) 交付时必须装配显式根的文件汇并加入
`tests/test_runtime_logging_entries.py` 的执行守卫；实验根自带 `logs/`，不向父目录寻找根。
守卫验证已交付入口的装配，不禁止库调用和服务测试使用 `NullSink`。

## 规则

### 文件、格式与时间

- 位置是 `<显式所选根>/logs/`。固定自有文件为 `.runtime.lock`、`runtime.jsonl`、
  `runtime.jsonl.1` 至 `runtime.jsonl.4`；`.1` 比活动文件更旧，最大后缀最旧。
- 每事件一行 UTF-8 JSON，`format_version=1`，以换行结束。单文件上限为
  `MAX_BYTES=1048576` 字节，最多 `MAX_FILES=5` 个数据文件（包括活动文件），锁文件不计入。
  新事件会超出大小上限时先轮转；只淘汰最旧自有文件。单事件大于文件上限则拒写。
- 上限是代码常量，`FileSink(max_bytes=..., max_files=...)` 只为调用方测试提供注入；
  不增加 settings 字段，不改变配置快照、Contract 快照或 Stage fingerprint 身份。
- `timestamp` 使用注入的 `Clock` 转为 UTC；`elapsed_ms` 使用注入的 `MonotonicClock`。
  缺省使用系统 UTC 与单调时钟；独立任务方法没有入口计时范围时耗时为 0。
- 字段仅允许封闭的 `event/component/stage/route/category/kind/reason`，以及
  `task_id/paper_id/run_id/plan_id/execution_id/fingerprint/attempt/elapsed_ms/timestamp`。
  标识符只接受 UUID 或 32/64 位小写十六进制；fingerprint 固定保留前 **16** 位。
  未知字段丢弃，非法已知字段使整条事件拒写；不会调用任意对象的 repr/异常格式化。
- 一个执行入口有独立 `run_id`；路线沿用所属入口的 run，`plan_id` 关联审计计划，
  Feed `execution_id` 是 check_id，元数据 `execution_id` 是 request_key。
  字段在依据尚未知时可以缺省，例如 run 开始前尚无新计划 ID，元数据 resume
  开始时尚未加载论文依据。`paper_id/stage` 不按校准可见性许可省略。

### 事件语义

任务事件闭集：`claimed`、`succeeded`、`failed(kind)`、`submit_rejected(reason)`、
`reclaimed`、`interrupted`、`unexpected_error`。不记录 renew。

- `claimed` 在领取事务返回后记录；领取时回收过期尝试也在同次事务返回后记录
  `reclaimed(kind=outcome_unknown)`，包括回收第二次尝试后因预算耗尽拒绝新领取的路径。
- `succeeded` 仅在成功接收事务提交返回后记录。`submit` 的精确回放也可产生诊断事件，
  事件数量不代表新增业务事实数量。
- 合法的失败报告及无效输出保留现有失败结算和预算语义。执行者普通 `Exception`
  先记录无载荷 `unexpected_error`，仍结算 `failed(kind=executor_error)`，不退还预算。
- `submit` 的受控 `TaskError` 记录 `submit_rejected`，不改写原拒绝原因。
- `KeyboardInterrupt`、`SystemExit` 等非 `Exception` 中断记
  `interrupted(category=outcome_unknown)` 后原样重抛；不伪造失败、不退还已领取预算。
  事务或框架原本如何处理普通错误，仍沿用原处理。

审计及来源事件闭集：`run_started`、`run_finished`、`route_settled(category)`、
`interrupted`、`unexpected_error`。

- `run_started/run_finished` 描述一次公共执行入口；正常返回记
  `run_finished(category=completed)`，受控拒绝记 `controlled_failure` 后重抛。
  `completed` 仅表示入口返回，不表示所有路线取得成功或来源达到上线判据。
- `route_settled` 是单条路线的持久结算，category 使用来源的封闭 reason；不复制 HTTP 文本。
  审计路线提交返回后记录，包含 resume 对旧未结算路线的 `outcome_unknown` 结算；
  Feed HTTP 取得结算提交返回后记录；元数据路线的材料／
  论文事实及路线提交完成后记录。已结算路线的精确重放不重复新增路线事件。
- Feed `invalid_feed` 保留为该受控类别，HTTP 403 为 `access_blocked_403`；元数据
  依 DOI-RA、相应 registry、publisher 分别记录。没有 DOI 时没有虚构 HTTP 路线事件。
- 意外异常仅记录 `unexpected_error` 并保持既有抛出／转换语义；审计执行器的普通
  异常仍转换为原来的 `execution_incomplete`，路线保持未结算。
  非 `Exception` 中断记 `interrupted(outcome_unknown)` 并原样重抛。

成功提交与事件追加之间存在退出窗口：可能业务已经成功却没有 `succeeded`，
反向不成立。缺少结束事件不等于业务失败；回查任务与成功制品，不根据日志补造状态。
日志未 fsync，不承诺断电或 SIGKILL 时最后一条事件完整／持久。

### 并发与私密性

追加、大小检查与轮转都在同一固定锁文件的排他 `flock` 内串行化。
每次追加重新打开活动文件，不保留指向已轮转 inode 的写句柄。
目录和文件使用 `O_NOFOLLOW`，拒绝 logs 符号链接；自有文件必须是单链接普通文件，
使用钉住的目录 fd 操作，锁文件永不轮转或删除。只操作固定自有名字，不清扫其他文件。

在总保留容量足够时，遵守此协议的本机进程不会丢失、撕裂或交错事件；达到容量后
允许按上述策略淘汰旧文件。flock 只约束使用此锁的写入者：不支持人工编辑、
外部收集器同时改写／轮转、其他进程删除锁文件或恶意替换目录；不承诺 NFS/CIFS 语义
或文件系统级防篡改。普通写入异常时持锁尝试撤去本次半行，不补写、不重试事件。

日志完全不接入 Python `logging`，没有 root handler 或向父 logger 传播的路径
（等价于专用 logger 的 `propagate=False`）。`httpx` 的 INFO 记录不会进入文件汇；
不启用 traceback、`exc_info` 或任意异常类名输出。

禁写 §8.7 全部载荷，以及 `Claim.credential`、renewal_handle、联系邮箱、proxy、
绝对路径、用户名、主机名、环境变量值、完整 excerpt、RPC/模型输入输出、工具错误和
进程 stderr。完整 Profile、Prompt、摘要／正文、API key、cookie、Authorization、
TDM token、机构与会话凭据、带临时凭据的 URL 均不经过事件字段。
Agent 的预测、分数、建议和完整失败载荷仍禁写；阶段级任务明细不属于盲评禁运范围。

安全事件示例：

```json
{"format_version":1,"event":"failed","component":"screening","task_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","stage":"boundary","attempt":1,"kind":"timeout","elapsed_ms":100,"timestamp":"2026-01-01T00:00:00+00:00"}
```

禁写反例：`{"event":"unexpected_error","message":"HTTP Request: https://host/?token=..."}`。
原始异常消息和 HTTP URL 没有可写入的字段。

### 只读与备份

`audit list/show/replay`、任务 `query/status/load_input/load_success/validate_all`、
Feed／元数据 replay/view/content/requests/validate_all、`paper show/trace`、doctor、help
不发事件、不创建日志目录，即使服务已经注入文件汇。
默认 `NullSink` 的现有服务调用保持 data_root 字节不变的约束。

运行日志不随[备份恢复](backup-restore.md)保留；不能以日志替代可恢复业务事实。

## 错误与拒绝

序列化、时钟或文件写入的普通异常只导致诊断降级，不改变业务回执、CLI 成功退出码、
成功制品字节或失败类别，不触发额外模型调用。
每进程最多向 fd 2 输出一次固定中文提示：`运行日志写入失败，业务继续。`，
不含路径、异常或载荷。不缓存失败事件，不在稍后补写。

## 不提供／不证明

不提供完整审计账本、日志搜索平台、远程遥测、业务状态重放、生产模型接线或四刊 live 证明。
真实 Pi、cwd 隔离、Docling、正式校准与 NAS 仍由[路线图](../roadmap.md)对应节点承接；
后续 Audit 首轮 live 使用已有 audit 入口接线，离线合成来源不构成其通过证据。

## 相关

依据：[#120 最终裁决 D2/D5/D7](https://github.com/MeteoBoy4/PaperRadar/issues/120#issuecomment-6520223100)、
[#123](https://github.com/MeteoBoy4/PaperRadar/issues/123)、[规格 §6/§8.7](../../intent/draft.md#87-日志与隐私)。
相关边界：[任务](screening-tasks.md)、[审计](fixture-audit.md)、
[Feed 组合](feed-pipeline.md)、[元数据](feed-metadata.md)、[本机锁先例](../adr/0029-protect-installations-through-inherited-flock.md)。
