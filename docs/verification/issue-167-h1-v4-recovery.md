# #167：v4 现场 unknown 与一次性恢复待裁决

本轮属于 H1/H3 已批准的无凭据合成验证及 A7 回记。v4 已执行一次，预算已消费，不自动补跑或退款。本文不构成完整 H1、真实 Pi 或 Live 通过证据；前两次失败见 [失败及自动执行台账](issue-167-h1-failures-auto.md)。

## 固定身份与现场结果

run=`a840c6d21e97`，包 `.scratch/issue-167/h1-synthetic-auto-v4-final/`；所有者已明确批准 review-seal SHA256=`e2461d9622c0176d9bee26d676b15f835e6c6309c4a03d0dee78130806e3bee6`，随后报告已运行。core manifest=`64fa5e6b65119a0d60eee1f57565c41675887e4ebd7d4f266bfeaaf4c606fba7`；原封印包未改。

- root guardian 实际 UID0、NoNewPrivileges=true、core=[0,0]、六项 capability 全部 true。删除冗余 `User=root` 的修复本次有实际 metadata 支持，不再仅是源码预测。
- 合成 worker 的 ready：UID1000、NoNewPrivileges=true、effective capabilities 空、core=[0,0]、cgroup 匹配。九项合成文件布尔检查均 true：attempt 写入与安装读取正例、业务/凭据 fixture/发布者读取负例、cwd/安装写入负例、观察完整性和目录删除；写入历史 observed_mutation，清理前终态普通文件数1。它们只覆盖本包合成 fixture，不外推真实凭据或任意路径。
- 阶段 A 只保存4行：IPv4/IPv6 当前端口38167 TCP allowed；IPv4 其他端口38169 TCP denied/admin_unreachable；IPv6 其他端口38169 TCP unknown/timed_out。最后一行不能算拒绝成功，原因尚未证明。worker 在首个不符预期项停止，阶段 B、UDP/DNS及遗留后代案例未完成。
- guardian 要求完整阶段材料，收到不足10行后报 phase_metadata_invalid，failure_stage=phase_a，整体 unknown。其 phase_counts={}，不能用表计数补造案例结果。
- 自动 owner 结果 unknown，failure_stage=collect，restoration_error=restoration_unknown；原实验记录保持 cleanup_complete=false/table_may_remain=true。两 unit 均已 failed，MainPID=0、ControlGroup 空，两个精确 cgroup 目录均消失；两个 unit fragment 和本表尚未恢复闭合。

owner-run.json 原字节 SHA256=`8e938275fe73b16ecdc76e4f4fe95d79e9163c54d80410850fb9d7325b928201`。未读凭据、真实进程 environ、日志或 core 内容；没有 Pi/Node、认证、模型或新崩溃。

## 所有者只读导出与确定的恢复拒绝

所有者执行单 sudo 的只读导出脚本，得到 results/kernel-recovery-state.json，原字节 SHA256=`a18a6eaec2b02717b16f8268b6ccb6d43c3c601d01a4062bdfbda6e3118842f9`。它读取本表 JSON、root go-a/结果及 worker cgroup 状态，没有修改规则、启停服务或发送探针。

当前 `inet paperradar167_a840c6d21e97`，table handle=23；scope 的 socket cgroupv2 right 为数字字符串 `844648`，不再是原精确路径。规则仍是阶段 A 的两个 loopback TCP38167 allow 和末尾 reject，allowed packets/bytes=8/512、rejected=2/140。这是 packet 计数，不能当 HTTP/模型请求数。

当前恢复器停止服务后按原路径严格验表，numeric 或数字字符串均不接受；因此 guardian cleanup 和 owner restore 都保留表，未以空 cgroup 代替身份核验。独立离线回放覆盖此拒绝和“不调用 delete”分支。现有材料没有停止前独立保存的数字 cgroup ID；root go-a 证明此前通过原规则核查，但不能独立重证当前数字身份的历史绑定。没有把“停止必然导致该格式变化”当作已证明的一般规律，也没有在通用 verifier 中接受任意数字。

## 仅恢复包，等待 H1/H4 一次性例外

审阅目录 `.scratch/issue-167/h1-recovery-a840c6d21e97-v1/`，先读 owner-review.md 和 review-seal.json。源码 `scripts/issue167_h1_recovery_once.py`；owner-recover.sh 包含逐字相同的 root stdin 字面代码，不让 root 执行工作区模块。密码仅由 sudo TTY 接收。

请求所有者明确接受**本表数字身份历史绑定无法独立重证**的残余，仅对该 run 允许一次恢复例外。批准前不执行；这不改变实验 unknown，也不改变通用规则归属判据。

允许的具体动作仅为：

1. 只读核对原 root-owned 安装父链、固定 manifest/guardian SHA、原 bootstrap 的全部成员/工具/boot-context、unit 字节/drop-in/manager 路径、两个停止态及 cgroup absent、root go-a/结果和原永久账本。
2. 整张当前表的 canonical SHA 必须为 `9721daafa30c44f0e4837f8c4b5694f1fdd99feaceac62df4fe8b37f67df5b9d`。句柄、数字字符串、规则、计数或 metainfo 任何变化都拒绝，不做 normalization。
3. 排他新增 `/var/lib/paperradar/probe-runs/issue167-a840c6d21e97-recovery-v1.json`，0600，fsync 文件和目录，状态 reserved_unknown；失败不清预占、不自动重试。
4. 再验停止态和同一完整快照，只删除固定表；独立确认表 absent 后，重验两个 unit，具名 reset-failed，删除两份精确 unit fragment，daemon-reload。
5. 再查本表 absent、unit fragment/manager not-found、inactive/dead、MainPID0、ControlGroup 空和 cgroup absent、原账本 SHA 不变；保留原永久账本、runtime 和安装代码。恢复成功与实验结果分列，失败输出受控 stage 和 last_completed_stage。

没有 start/stop、探针/连接、认证/模型请求、其他 nft 表操作、全局 flush、递归删除或实验重跑。若中途失败，保持 unknown 并停止；不能自动再试。root 管理员并发改变这些对象不在此归属模型内，任何被核查到的漂移拒绝。

后续一般工程应在首次原路径核查后、停止前保存同次内核数字身份，绑定 boot/run/table/handle 等来源；当前没有追补这种历史证据，也没有为下一次探针扩预算。IPv6 超时原因、一般恢复设计和是否再验均仍未解决，不借一次性恢复例外批准它们。

## 前驱链接错误与离线验证

发现 generator CLI 虽解析 --retry-context，却未传给 create_auto_bundle。因此 v4 实际封印的 retry-context 和 owner-run.retry_history 仍指向 `6e70b5a31d42`，不是准备期描述的 `7c93ab04d615`。两次旧记录均保留，v4 有外部明确额外一次授权；不修改旧封印/账本、不重建历史链、不将错误链接当退款或新额度。新增真实 generator CLI 的纯文件回归先失败，再修 workspace CLI 转发后通过；该修复不改已执行的 v4。

本轮 `uv run --offline --locked pytest -q tests/test_issue167_h1_*.py` **242 passed**，仅相关 H1 工程验证，无现场/root 操作。独立 D1 模块计数：auto_bootstrap8、auto_bundle11、bundle12、capability_contract1、cleanup_diagnostics11、cli_context1、failure_diagnostics13、guardian50、network_bundle4、network_worker27、owner_ops9、owner_run31、permissions7、phase37、recovery_once20。新恢复模块的正例明确保留 experiment_result=unknown；负例覆盖完整快照漂移、预占持久/权限/重复拒绝、部分恢复和异常内容不泄露。

相关5文件 Ruff check/format 与 mypy 通过，恢复入口 bash -n 通过；fresh subagent 独立审查了实际导出摘要、root 导入链和命令顺序。所有测试均未绑定，不进入历史分母/required/正式回执；scope 审计结果另随本轮回记。未运行完整离线门禁，未取得 H2 或新探针许可。Live 仍待探索，B 仍等待完整 Live，#167 保持 open。
