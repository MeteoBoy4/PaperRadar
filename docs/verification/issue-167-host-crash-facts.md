# #167 A4：崩溃目录备份范围与上传通道只读事实

本次按所有者最新 H4-core 指令，仅补四条事实中的 **(a) /var/crash 的备份/同步范围** 与 **(b) whoopsie/其他崩溃上传是否确实关闭**。不选择 core 方向，不制作全机分发器，不改变判据。核查基线 c0bee235f4ebb0a88be4a60c392c96619ec61683，日期 2026-11-07。

所有命令只读；没有运行 Node/Pi、认证或网络，没有启动/停止/禁用任何服务，没有读取 /var/crash 或 /var/lib/apport/coredump 的成员、crash/core 内容、凭据、进程环境或完整命令行。对常见个人备份工具只查配置路径元数据，没有打开配置。未使用 sudo/root；初次沙箱 bus 查询被拒绝，主代理后来以同一普通用户完成限定的只读实时查询，补证见下表。

## 结论

| 所问事实 | 本轮可证实部分 | 严格结论 |
| --- | --- | --- |
| (a) /var/crash 是否在任何备份/同步范围 | PaperRadar 自身备份按数据库登记事实/制品闭包复制，不默认扫描该目录；已发现的系统 dpkg-db-backup 默认源为 /var/lib/dpkg，输出 /var/backups。未取得全机排除清单 | **unknown：不能证明未被任何备份/同步纳入，也没有本轮证据证明已被某一通道纳入** |
| (b) whoopsie 及任何崩溃上传通道是否确实关闭 | 主代理限定实时查询显示 whoopsie.service/path 当前 inactive/dead；apport-autoreport service/path/timer 当前 inactive/dead、条件不满足；但 path/timer 文件仍 enabled | **已证实所列通道的当次非活动状态；全局、持续的“任何上传均关闭”仍 unknown**。inactive 不等于持久 masked；缺 marker 不阻止未来改变、手动启动或未登记渠道 |

不把未知写成“不外流”。备份/同步边界、全部上传通道清单及如何维持这些事实到调用结束，仍须纳入所有者统一裁决和后续现场计划。

## (a) 有界核查与备份范围

### /var/crash 与产品边界

- 只做 lstat：/var/crash 存在，为目录、非符号链接；没有列出目录成员。
- 解析当前 /proc/self/mountinfo 仅输出覆盖该路径的 mount point/type，不输出 mount source/options：当次为根挂载 /、ext4。这不证明有无文件级备份、整盘镜像、快照、云同步或其他 namespace/宿主侧采集。根文件系统级备份不能因未发现专门 /var/crash 配置就排除。
- [PaperRadar 备份契约](../contracts/backup-restore.md)限定为显式数据库的已登记配置、全部制品与事实闭包，明确不从活动数据根递归猜测成员。当前公共 backup create 没有默认扫描宿主 /var/crash 的逻辑。此结论不是对全部实际备份任务的证明；不排除人工复制、错误登记或产品外通道。
- 清理/外流评估还须单列 /var/lib/apport/coredump：已安装 apport/fileutils.py 默认 report_dir=/var/crash、core_dir=/var/lib/apport/coredump。本轮未打开两目录内容，不能只排除第一处就称全部 core 路径被排除。

### 发现的备份/同步入口

| 核查对象 | 实际观察 | 限制 |
| --- | --- | --- |
| 系统 unit 文件离线清单 | dpkg-db-backup.timer=enabled、service=static；rsync包已安装、rsync.service=disabled | systemctl --root=/ 只读文件 enablement，不是运行状态；disabled daemon 不阻止手动 rsync 或脚本 |
| dpkg 备份公开脚本 | /usr/libexec/dpkg/dpkg-db-backup 默认 ADMINDIR=/var/lib/dpkg、BACKUPSDIR=/var/backups，复制选定 dpkg 数据库和成员 | 此默认任务不以 /var/crash 为源，不能外推其他任务；本轮未执行脚本 |
| 常见系统配置元数据 | /etc/restic、/etc/borgmatic、/etc/rsnapshot.conf、/etc/timeshift、/etc/snapper、/etc/duplicity 当次不存在 | 只查常规位置，不证明任意路径、容器、手装工具或其他用户均未配置 |
| 系统 cron 目录名字 | cron.d 仅看到 anacron、e2scrub_all 与占位；daily 为常见包任务（含 apport），hourly 仅占位 | 未打开任意可能带秘密的任务内容；名字不能穷尽其实际调用或间接同步 |
| 所有者常见配置元数据 | home 下 .config/rclone/rclone.conf、.config/syncthing/config.xml、.config/restic、.config/borgmatic、.config/duplicity、.config/deja-dup 当次不存在；user unit 目录直接成员名字未匹配所查 backup/sync 关键词 | 未递归读个人配置或查其他用户；自定义任务可无关键词 |
| root crontab | /var/spool/cron/crontabs/root 的元数据检查被拒绝 | 未读内容/未提权；root 和其他用户调度覆盖不完整 |
| 已知进程名快照 | 仅读 /proc/PID/comm，仅输出预登记名称命中集合；未命中所查 restic/borg/duplicity/syncthing/rclone/rsync 等 | 没有输出任意进程名/路径/PID或读cmdline/environ；短任务、不同名称、其他PID namespace与宿主任务不在证明范围 |
| 主代理 user manager 补证 | syncthing --user 为 not-found | 仅这一具名 unit，不等于所有同步程序均不存在 |

没有完整备份/同步工具和快照范围清单，不能用“当前无进程”证明历史/未来不会被备份。此项最终保持 unknown，不能靠权限不足或缺省路径不存在推成排除。

## (b) 上传与生成分开判断

### 本机配置与软件

| 来源 | 实际观察 | 含义 |
| --- | --- | --- |
| dpkg package metadata | apport、apport-core-dump-handler、whoopsie 为 installed；systemd-coredump 为 not-installed | 软件存在不证明运行；缺某包不排除其他上传器 |
| /etc/default/apport | enabled=1 | Apport 生成/处理未被此文件关闭；whoopsie非活动不等于Apport不生成本地报告 |
| /etc/whoopsie | General 下只有 report_metrics=true | 不是“崩溃上传持久关闭”的证据，不能误读成 report_crashes=false |
| whoopsie.path | PathChanged=/var/crash，离线状态 disabled | 不是 masked；依赖或手动启动仍需单独核实 |
| apport-autoreport.path/timer | 离线状态 enabled；共同 ConditionPathExists=/var/lib/apport/autoreport；path 监视 /var/crash，timer 为开机1小时/此后3小时 | 自动入口仍安装启用，条件必须单独核查 |
| /var/lib/apport/autoreport | 当次 lstat 不存在 | 当前新启动的条件不满足；marker 可改变，不能独自证明实时状态 |
| apport-autoreport.service | 同一 ConditionPathExists；Wants/After whoopsie.path；调用固定 whoopsie-upload-all --timeout 20 | 即使 whoopsie.path 文件层 disabled，依赖仍能请求启动；条件与实时状态分开 |
| apport-forward.socket | 离线状态 enabled，相关 forward/coredump-hook unit 存在 | 属另外的崩溃处理/转发面，不能直接当外部网络上传，也不能漏盘点 |
| /etc/cron.daily/apport | 包公开脚本按年龄/空文件等条件清理 crash 目录 | 不是即时清理或无外流保证；本轮未执行 |

### 主代理补充的实时只读状态

初次 system/user bus 查询在工具沙箱内均为 EPERM，未据此认定服务关闭。主代理随后以同一普通用户限定查询 Id/LoadState/ActiveState/SubState/UnitFileState/ConditionResult/TriggeredBy 等非秘密属性；没有查询 Environment、argv、StatusText 或日志。下面记录其本轮回传结果：

| unit | ActiveState/SubState | UnitFileState | ConditionResult / 关联 |
| --- | --- | --- | --- |
| whoopsie.service | inactive/dead | static | no；TriggeredBy whoopsie.path |
| whoopsie.path | inactive/dead | disabled | no |
| apport.service | active/exited | enabled | yes |
| apport-autoreport.service | inactive/dead | static | no；TriggeredBy timer/path |
| apport-autoreport.path | inactive/dead | enabled | no |
| apport-autoreport.timer | inactive/dead | enabled | no |

这支持“所列自动上报/上传 unit 在该查询时点未活动”，**不支持“任何崩溃上传通道已持续关闭”**。apport.service 的 active/exited 也与“本地生成完全关闭”不同。条件、配置或启动关系变化后证据失效；不把本轮结果外推到未来运行窗口。

另有同一 namespace 的已知 comm 名称快照，未命中 whoopsie/apport/apport-autoreport/systemd-coredump 等；只是辅助时点观察，不替代上表或对任意进程的保证。

### 覆盖限制与 doctor 的边界

- 没有读上传日志、现有 crash/core 或真实网络；不能判断历史是否上传过，也没有进行网络计数或“无外流”试验。
- 未穷尽 GUI crash提交、包自带遥测/上传、人工上传、浏览器、其他用户、容器、定制任务和宿主侧通道；只读范围内没有完整权威列表。
- doctor 的有限断言必须限定为已登记通道，逐项查实时状态、持久启动关系/条件和查询完整性；未知通道或查询失败应 unknown 阻断，不能输出笼统“上传关闭”。
- 所有者仍需提供覆盖根文件系统及两处 crash/core 目录的备份/同步/快照清单与 include/exclude；无需提供仓库密码、令牌或任何凭据正文。
- “不外流＋可清理＋doctor可查”路径是否允许本地报告短暂存在、权限/清理时限/失败处置由谁维持，属于待统一裁决成本，agent未自行接受该判据。

## 来源身份与验证

下列都是公开配置/包源码，不是凭据或进程数据；SHA只标识当次依据，不纳入历史组。

| 文件 | SHA-256 |
| --- | --- |
| /etc/whoopsie | 802dd6512644d10e0c811fe2aad6538cc99d4565f517abe8e80748dfd0bf2868 |
| /etc/default/apport | 810304fb0df6dbc8a651a8928ddd0bb2b521fa0ca6f32a328aa103be61977f91 |
| /usr/lib/systemd/system/whoopsie.service | 33d4dcd4c2f3797baa1ad4851e791baced85e1d79a4e59b2a21761385b6d83e1 |
| /usr/lib/systemd/system/whoopsie.path | 448d165321895eafe45d5e0aa53de567af910d405335ca6a205f5213a4e5da73 |
| /usr/lib/systemd/system/apport.service | c2026a8f813776108e2d91629f51ff0cf5bf013fac03314164cabcda6c9698aa |
| /usr/lib/systemd/system/apport-autoreport.service | 9be72b6a5ce373fc3c4580cbe3901703a6cb47fff0bde3d2c29fb82d69160b73 |
| /usr/lib/systemd/system/apport-autoreport.path | 22df838805217bd3c7381e87a8e7aff7db11eec6977b75a892db1e6dc42b4e8a |
| /usr/lib/systemd/system/apport-autoreport.timer | 72e4700854d2c3babee612f6dda7c1c61caf37878b7adf9663ddbcbbc3e4c9c5 |
| /usr/libexec/dpkg/dpkg-db-backup | fba28643afbd3f3cba56ce0ee9825271b233185f8fc4c9afca3e0eeaa04f10be |
| /etc/cron.daily/apport | ece406240beddfd8d262a9f0f2ffd5aa40cae4bf5401e7641db3ae1aca737a39 |

纯文档无测试变更；本地链接和 diff 核对通过，最终范围审计由主代理组合执行。没有上传/备份试运行或完整离线门禁，没有生成“不外流”通过回执。
