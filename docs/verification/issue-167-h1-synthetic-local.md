# #167 H1-1：无凭据文件、loopback phase 与遗留后代审阅包

本轮承接已闭合的[H1-0](issue-167-core-wiring-h1.md)，不是重跑H1-0、EXP-2或模型调用。基线仍为 `c0bee235f4ebb0a88be4a60c392c96619ec61683`，保留此前工作区修改。原生关系重查#140 closed（1/1）、subIssues0/0，无新阻塞；本轮开始没有完整H1/H3或H2现场授权。

本轮只写候选代码、冻结审阅包、离线测试和普通用户只读检查；没有安装root目录/unit、启动服务、加载nft、创建loopback连接、运行Pi/Node、读取真实凭据/进程环境/core或制造崩溃。新包须单独由所有者批准H1/H3并执行root步骤。

## 包和精确范围

待审执行包：`.scratch/issue-167/h1-synthetic-local-v2/`，run_id=`6e70b5a31d42`，uid/gid1000/1000。

- manifest SHA256：`1fba953291de3c72c4231446601d6c338908d09d89e9bb59c51d7936e41233c6`，19/19成员哈希一致。
- worker：`paperradar-167-h1net-6e70b5a31d42.service`；guardian：`paperradar-167-h1guard-6e70b5a31d42.service`。
- 唯一nft表：`inet paperradar167_6e70b5a31d42`，只匹配worker的 `/system.slice/<unit>`、level2；不flush全局、不覆盖既有表。
- root-owned代码根：`/home/paperradar-probes/issue167-6e70b5a31d42`；运行目录：`/run/paperradar-issue167-6e70b5a31d42`。
- 永久单次消费记录：`/var/lib/paperradar/probe-runs/issue167-6e70b5a31d42.json`，恢复不删除。公共项目父目录只在缺失时新建，不改变已有目录权限/归属。
- loopback字面地址127.0.0.1、::1；阶段A端口38167、B端口38169、负例端口38168。每阶段最多10次连接/单字节发送，合计最多20次，包括v4/v6的UDP53拒绝负例；不是实际DNS域名查询，不允许外部地址或fallback。
- guardian仅使用NET_ADMIN、SETUID、SETGID、KILL、CHOWN、DAC_READ_SEARCH的显式cap集合，分别用于本表、降权peer、回收peer、worker私有目录归属和读取其受控metadata；worker cap为空。root代码和所有父目录须root所有且不允许普通用户写。

完整可读范围与所有命令在包内owner-review.md、owner-wizard.sh。向导复用wizard skill模板库，只展示所有者手动命令；不会自动sudo、安装、启动或删除。审批须绑定该包完整SHA，不把Plan中的not_granted字段当执行许可或通过证据。v1仅为未提交审批的准备候选，因缺少目录chown所需cap已由回归发现并废止执行用途；未发生现场运行，不改run_id增加预算。

## 实现分工和拒绝路径

| 新模块 | 实际提供 | 未提供/限制 |
| --- | --- | --- |
| issue167_h1_phase.py | 精确Plan、固定派生路径/端口/地址、排他create table、phase原子flush+add、严格kernel JSON规则/计数核对、有界nofollow递归cgroup读取 | 不执行nft或服务；packet计数不是HTTP/账单 |
| issue167_h1_guardian.py | root保护/成员及工具SHA/host context在导入前核验；持久O_EXCL消费；两阶段门闩和独立counter；只剩controller才切phase；遗留不同session子进程时拒切；先stop/确认cgroup空/核对本表再撤规则 | 未实际部署；创建结果不明/规则漂移保留状态供owner，不猜归属或自动重试 |
| issue167_h1_network_worker.py | 动作前预占；root门闩序号与原子发布；实际uid/core/cap/no_new_privs/cgroup metadata；ready前合成文件/写删历史/终态/删除；每phase固定10次本机尝试；固定OK peer；遗留后代负例 | 本轮真实socket/file-child-Landlock组合未执行；stdout不保存模型/请求内容；不推真实session零写入 |
| issue167_h1_owner_ops.py | root-installed helper绑定plan根、核对unit SHA/drop-in/manager scope后才stop；两cg空才验表撤规则；成功metadata与永久ledger一致、无额外挂载后才精确移除runtime/code；失败材料保留 | 不从workspace执行root代码；不能在scope/表归属未知时作用于其他对象；永久ledger不删 |
| issue167_h1_network_bundle.py | 纯生成全部具体字节与SHA、两unit、四份nft审阅文本、host context、解释器副本和手动向导 | 不安装/授权/连接；新包/新ID从不自动发放新尝试许可 |

文件fixture只创建自己的fake business/publisher/credentials标记，使用复制的生产IsolationBoundary原字节与空环境合成Python子进程。stdlib额外只读是私有fixture例外，不扩大生产Node白名单。故意写删哨兵必须观察到mutation；清理前终态集合、清理后删除分别取样，不宣称session历史为零。

网络阶段必须每阶段两正例allowed、八负例denied，connection_refused/timeout等保留unknown；另核对本包nft named counter的phase窗口aggregate增量。该aggregate不证明逐个packet精确因果，也不当作provider请求计数。IPv6不可用、端口占用、身份/规则/连续性不明都停止，不切目标/放宽规则。guardian根程序生命周期与worker通过BindsTo关联，异常时后续case不放行；两个精确cgroup未确认为空时不先撤规则。

## 独立审阅与红绿修复

本轮使用三个fresh subagent拆分pure policy、worker、guardian，主代理集成owner helper/生成器，并作交叉审阅。准备期修复包括：

- cgroup短读取可能漏掉后代PID：先回归失败，改读至EOF/严格上限；不是以单次read冒充完整集合。
- nft add table已存在时不报错：依据本机nft(8)改为create table，碰撞由kernel拒绝；回归先红后绿。
- guardian counters/owner restore的真实JSON bytes接口：先解析并拒重复key，再交纯规则验证；直接传bytes导致合法状态始终unknown的问题已修复。通用metadata重复key本已拒绝，未为制造红而改变正确代码。
- owner restore先核对unit字节/manager路径/drop-in再stop；main绑定实际installed根；finish核对永久ledger且读mountinfo以覆盖同设备bind mount，不能只看st_dev/is_mount。
- root guardian给worker目录chown需CAP_CHOWN：独立断言先失败，再加入显式cap。v1未审批/执行，v2统一封印，不自动追加case。

## 开发验证与边界

命令采用 `UV_CACHE_DIR=/tmp/issue167-observation-uv uv run --offline --locked …`。

五个新增独立D1模块的组合 **127 passed**：phase37、guardian50、worker27、owner_ops9、bundle4。测试使用mock/临时metadata；不执行root/systemd/nft或本机网络。worker导入复制Boundary的独立子进程只验证namespace加载，真实file-child/LL/网络仍待H1实际验证。Ruff check、format和mypy共10个新文件通过；历史分母/required/回执不扩充。

审阅包bash -n通过。原unit只读verify因未来root解释器尚未安装而退出1，仅报ExecStart文件不存在；没有因此创建root路径。仅替换/tmp语法副本的ExecStart解释器为已有同字节副本后，普通用户systemd-analyze verify返回0且无stderr；这只校验语法，实际安装后、运行前仍须对原unit再verify。工具沙箱内外host-context四字段相同，未来root安装目录当前不存在；没有实际启动/执行权限。

第一次用脚本路径直接执行生成器因scripts包导入路径失败，未创建包或现场动作；正确开发入口是 `uv run --offline --locked python -m scripts.issue167_h1_network_bundle DEST --run-id ID`。不把准备期命令更正当现场重试。

精确请求计数继续ADR-0048下界/unknown与I重评，loader不产品化、不改启动身份、不重跑EXP-2。core采用ADR-0049，不修改Apport/core_pattern或全机其他程序行为。原产品read_evidence缺失仍阻断。没有完整离线门禁、正式校准、NAS、真实provider/模型或产品激活。

## 仍未验证及审批状态

本包只覆盖这一次合成文件、双phase loopback与遗留后代组合；不等于整票或完整Live。外部SIGINT/KeyboardInterrupt、真实墙钟/供应商错误、真实端点/TLS、固定Node/Pi/认证、真实session全历史、任意进程逃逸等不由本包自动取得通过。故障处理的离线mock通过也不等于现场故障已触发。

所有者已明确批准上述v2合成包并表示自行执行向导，审批绑定本清单SHA、两个unit/唯一表/新项目目录与永久记录、最多20次loopback尝试及恢复范围；H1-0与旧EXP-2许可不复用。收到结果后还须核对root-produced回执、永久账本、实际服务/表/cgroup和恢复状态，不能只看一个JSON passed。最近一次普通用户只读查询时root代码目录及guardian-result均尚不存在；本条只记录该时点，不提前写现场passed。最终scope审计结果留回帖。
