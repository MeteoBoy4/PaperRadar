# #167：四个历史失败run的有限留存元数据盘点

盘点时点：2026-11-08 04:29 UTC。本次只核四个已知run的精确code/runtime/永久记录顶层lstat，以及其具名unit文件与已知CG路径；不做全宿主扫描、不遍历任何保留目录成员、不读取其内容，也不清理或修改任何对象。

## 路径来源

| run | 冻结plan来源 | 单元集合 |
| --- | --- | --- |
| 6e70b5a31d42 | `.scratch/issue-167/h1-synthetic-local-v2/plan.json` | paperradar-167-h1net-6e70b5a31d42.service、paperradar-167-h1guard-6e70b5a31d42.service |
| 7c93ab04d615 | `.scratch/issue-167/h1-synthetic-auto-v3/plan.json` | paperradar-167-h1net-7c93ab04d615.service、paperradar-167-h1guard-7c93ab04d615.service |
| a840c6d21e97 | `.scratch/issue-167/h1-synthetic-auto-v4-final/plan.json` | paperradar-167-h1net-a840c6d21e97.service、paperradar-167-h1guard-a840c6d21e97.service |
| c591eb6ad204 | `.scratch/issue-167/h1-resolver-window-v2/plan.json`及owner-review | paperradar-167-h1net-c591eb6ad204.service |

四份plan均明确给出code为 `/home/paperradar-probes/issue167-{run}`、runtime为 `/run/paperradar-issue167-{run}`。永久记录路径为 `/var/lib/paperradar/probe-runs/issue167-{run}.json`，来自各冻结owner_ops中的LEDGER_ROOT及文件名构造，不从目录枚举猜测。UNIT_ROOT为冻结源码中的 `/etc/systemd/system`；另只核 `/run/systemd/system` 下同名文件。worker CG来自plan的 `/system.slice/{unit}`；前三guardian源码也明确核同一system.slice下的guardian_unit。

## 当前顶层lstat结果

表内目录size是目录自身stat size，**不是递归文件数或占用字节**。UID/GID均在工具sandbox中显示65534映射；本次没有越过工具边界重新核宿主实际owner，不能将映射值写成真实宿主UID。

| run | code | runtime | 永久记录 |
| --- | --- | --- | --- |
| 6e70b5a31d42 | 目录仍在，0755，size4096 | 目录仍在，0700，size100 | 普通文件仍在，0600，nlink1，257bytes |
| 7c93ab04d615 | 目录仍在，0755，size4096 | 目录仍在，0755，size140 | 普通文件仍在，0600，nlink1，509bytes |
| a840c6d21e97 | 目录仍在，0755，size4096 | 目录仍在，0755，size160 | 普通文件仍在，0600，nlink1，503bytes |
| c591eb6ad204 | 目录仍在，0755，size4096 | 目录仍在，0755，size140 | 普通文件仍在，0600，nlink1，13928bytes |

上述七个具名单元在 `/etc/systemd/system` 与 `/run/systemd/system` 的同名文件均absent；七个对应 `/sys/fs/cgroup/system.slice/{unit}` 目录均absent。没有读取保留目录的子项，因此不能从本次观察重新证明其内容类别、完整成员、封印一致或没有其它内部残留；也没有计算永久记录实际SHA。

## manager与表状态的证明边界

普通用户尝试对这七个精确Id执行只读systemctl show，被当前工具sandbox的system bus连接权限拒绝（Operation not permitted）。没有升级权限或使用sudo，**当前manager状态为未独立取得**；不能把工具连接失败解释成unit仍活动，也不单凭文件/CG缺失声明manager已卸载。drop-in未另行枚举。

随后主代理另以普通宿主用户只读查询同七个精确Id，未使用sudo或修改服务：均LoadState=not-found、MainPID0、ControlGroup/FragmentPath/DropInPaths空；五个inactive/dead，v2/v3的两个guardian保留failed/failed退出缓存。后者不是活动进程，不为清显示而自动reset-failed。该补充取得当前manager元数据，不改变上段子代理最初工具限制记录，也没有取得当前nft状态。

本次没有调用nft，也没有取得四张表的当前独立枚举或规则内容。历史已审恢复结果与当前观察分开：

| 历史 | 原恢复出处及当时结论 | 本次不能补造的主张 |
| --- | --- | --- |
| v2/v3 | [失败与修订记录](../../../docs/verification/issue-167-h1-failures-auto.md)记owner恢复host_policy_restored、两unit文件删除、当时manager无加载路径/活动CG；code/runtime/ledger按失败策略保留 | 不把这次lstat变成当前table/manager独立验证，不把原unknown改为passed |
| v4 | [恢复闭合记录](../../../docs/verification/issue-167-h1-ipv4-next.md#v4-一次性恢复已闭合实验仍-unknown)记一次性H1/H4恢复成功、表absent由owner root核验，两unit/CG及当时manager另有普通用户复核；原账本/runtime/code保留 | 不抹去数字身份历史缺口及owner例外，不把后续IPv4成功回填原实验 |
| c591 | [原例与仅恢复记录](../../../docs/verification/issue-167-resolver-run-unknown.md)记project_resources_removed、原结果unknown、code/runtime保留，表absent由owner root核验，unit/CG/当时manager普通用户复核；缺原全局resolver前基线不重建 | 不据当前code/runtime仍在推定项目策略仍加载，也不把旧恢复报告说成本次nft查询 |

## H5采用范围

最近e93/d5独立目录清理和E01完整恢复，不代表所有历史制品已清零。这四个历史run的code/runtime确实仍保留，与原失败/仅恢复策略相符；永久单次记录也是刻意保留的审计对象。本次没有新设“必须删除全部历史制品”的完成条件。

H5可明确接受这些已知保留范围，或另指示准备精确清理并按H1由所有者审阅执行。任何未来删除都需要独立绑定目标、完整元数据及恢复边界；本页不授权root、递归删除、重验或退款，不以接受留存改变旧unknown。

本轮只新增此过程文件，未改原源码、封印、结果或账本；没有运行测试、完整门禁、Node/Pi、认证/模型、信号、网络、服务/规则变更、真实数据库或锁，没有读取凭据、环境、日志、core或0600账本正文。本文是四run的有限metadata观察，不能外推其它case或全宿主状态。
