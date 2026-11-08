# #167：服务规则、观察窗口与无网络 H1 待审包

本轮继续A1/A2/A4/A6/A7，只做本地实现、无秘密合成验证和只读事实核查。既有DNS/TLS许可已经消费，本轮未再发现场DNS/TLS、认证或模型请求，没有Node/Pi、root、服务安装、nft加载或配置变更。内部配置及进程元数据只留本地，未提交/上传。

## 已完成的三个接缝

1. `scripts/issue167_service_egress.py`从SHA绑定的冻结profile生成仅项目精确cgroup的deny/create、三allow原子切换、clear/delete与网络片段。完整核对allow后复用原deny结构verifier；稳定table/chain/counter/scope handles与独立CG身份、profile/host绑定，未绑定numeric、额外范围、句柄重建、源漂移和深嵌套均受控拒绝。caller提供的CG tuple不自证来源，真实读取/保护仍由上层完成；base Plan仅贡献身份，不输出旧loopback地址作为新scope。
2. `scripts/issue167_fork_observation.py`对预建模型树先arm；自身CG、dev/inode及完整子树成员均符合时才封口终态。必须只剩可信controller，死亡controller、额外子孙、重建CG或丢窗口都unknown。删除检查当场确认absent，receipt再次查成员；正常删除IN_IGNORED与overflow/unmount/move区分，封口后的写入也不能藏进cleanup。auth持久目录不自动删除，可信controller静默条件仍需实际代码/部署保证。
3. `tests/test_issue167_observed_launch_fixture.py`局部factory adapter验证public prepare_launch中正确观察时点：资源建好/Popen前arm、真实合成Python auth/model及preexec/pipe收尾、CG gate→terminal→原rmtree→独立deleted。残留fixture PID阻止删除，原constructor虚调close也正确回收。没有mock掉Popen；但这是测试改装路径、合成CG与Python替身，不是实际service或未改装生产路径，只证明继承FD存在，不扩成新的供给OFD锁证明。

FileObserver仍仅承诺所选树与该后端的事件窗口；不从这些用例推断任意程序、mmap/别名或实际Pi全会话都已覆盖。没有改production观察hook、read_evidence或全局策略身份。

## inotify 失败历史与所有者处理

新窗口初次真实watch在初始化失败。最小反馈：工具沙箱与同一普通用户宿主，对各自一个空临时目录inotify_init成功而add_watch均errno28。所查限额为max_user_watches65536、max_user_instances128、max_queued_events16384，不能把失败归给沙箱或新闭包逻辑。

只读同UID匿名inotify FD及kernel fdinfo计数，未读argv/environ、内存或文件内容：已观察65409个watch，统计有不可读项而不完整；一个comm=code的进程占64973个。没有关闭FD、发信号或改配额。所有者随后报告「我已释放资源，请最小复测」，agent仅对一个自建空树复测，init/add均errno0。此后4个真实inotify用例通过，保留早期失败，不skip、不把事件回放冒充kernel。

4个kernel用例包括初始化、短暂写删历史、预存终态文件与零观察分离、post-terminal写入unknown。其CG来源仍明确为fixture；只有事件和临时文件扫描是真实kernel。实际服务CG权威尚须H1。

## 解析缺口及 Apport 推导更正

本轮只选择性读取本机resolver、nss hosts项和API/Auth两域名的hosts条目：默认nameserver为本机stub，指定两条hosts记录为空；它与ADR-0050冻结的router DNS目标不同。官方Node/Pi资料未提供不改现有入口的resolver服务器开关，普通Python显式查询成功不能迁移为Node默认lookup兼容。当前准备项目unit专用resolver只读绑定，不改全机配置、允许集合或Pi argv/env；具体见[适配审阅](../../intent/review/issue-167/resolver-adaptation-decision.md)。模型内层TCP53没有顺便加入。

准备期曾漏读Apport的system.slice例外，错误推断绑定会使该服务进入namespace提前忽略分支。fresh审阅发现反证后已撤回这一额外core取舍前提，修正过程文档；没有向所有者基于该错误前提申请新方向。

当前Apport SHA=`e8b57da9924d461fee6d3b392dc184697bc14d2eb8d717c05e1cbf0bd376041e`；`is_same_ns()`在namespace inode不同时还查cgroup，以`/system.slice`开头会返回True，`_check_global_pid_and_forward`用的是该完整结果。仅AST提取两个原样函数，以合成ProcPid回放：system.slice及其子组模拟mnt不同时same_ns仍true且不提前退出；非system.slice控制组相同条件提前退出。没有导入/运行Apport主程序或制造崩溃，结果留忽略目录service-observation-v1。

因此仍按既定第三路保留双层零core，不回到其他路线、不重跑原C对照或EXP-2；H1须按实际namespace/cgroup与collector完整条件核对，不能从一个例外推出全部core适用性已现场通过。长期doctor责任仍在后续工程。

## 新的明确 H1/H3 待审包

`.scratch/issue-167/h1-resolver-window-v2/`，run=`c591eb6ad204`。先读owner-review.md、manifest.json、plan及全部root/worker代码。v1只是未执行、未授权的准备草案，收窄读取范围后入口已禁用；同一案例没有靠换ID获得新预算。旧已批准包不动。

| 身份 | SHA256 |
| --- | --- |
| review-seal.json | `021c03cec08e4f4f3fec2eeb03e577fbebbd96d899635ac16d11a69e83333c1d` |
| core manifest | `cf1c22635aacc842c0cea99cac7c6901a6093981ef2023b31ecd169e77a2f889` |
| driver | `32b1dbdb4c6fa2cc71b384458a121a9867b82d3579f3a210db34e69e09b88485` |

精确影响：1个UID/GID1000 unit `paperradar-167-h1net-c591eb6ad204.service`、唯一inet表 `paperradar167_c591eb6ad204`、代码 `/home/paperradar-probes/issue167-c591eb6ad204`、runtime `/run/paperradar-issue167-c591eb6ad204`、永久root0600记录 `/var/lib/paperradar/probe-runs/issue167-c591eb6ad204.json`。只读resolver源为本次root-owned文件，绑定仅此unit的视图；全机文件只读核对前后SHA，若外部变更则unknown，不回滚别人的配置。

worker显式cap/ambient空、NNP/seccomp、Delegate=no、零core，RestrictAddressFamilies=none、IPAddressDeny=any、SocketBindDeny=any；不创建socket。**DNS/TLS/HTTP/真实auth/model/Node/Pi/IPv6探测及崩溃均0**。仅两个合成Python角色各exec1；marker为公开非秘密fixture，只以匿名pipe→父memory→model env传递，结果只boolean/count，不保存marker、完整argv/env或内容。

可信worker源验证原FD共享offset、父close后独立EX拒绝、子退出后EX允许；不同session子进程仍须同CG。真实CG quiescence后才terminal→删模型树→独立deleted。model只借复制的production LL源码加**版本化Python stdlib目录**的fixture读取权限，不给整个/usr/lib，不更改产品策略或伪称实际Pi/production prepare_launch已经执行。

root owner仅临时sudo管理程序，具有该次sudo权限，不伪称受旧六cap guardian限制；没有常驻root服务。唯一一次sudo从TTY取密码，literal bootstrap在root导入前核全部源字节/工具/host，再用root-owned代码操作。root与worker均O_EXCL预占，无自动重试/退款；原子门闩、ready/result有界发布，nlink2中间态等待不误读partial JSON。

案例流程：worker ready后独立读live CG身份；表初始deny→三allow→clear→三allow，每步完整验表并要求packet计数0；gates驱动合成链与观察。RemainAfterExit只保留已退出worker状态供核ExecMainCode1/Status0、MainPID0和独立CG空，再stop、bound核表、delete本表、卸unit/reload。这里只验kernel规则结构，不做流量正负对照，不声称出站流量限制已完整验收。

保留5份已验本表kernel快照、binding、namespace来源、worker明细及永久ledger；不再像v5成功finish后只剩摘要。namespace对比标root-caller，不冒充实际handler；不运行Apport或重新声称完整core持久化通过，真实凭据前的配置等适用性仍须后续核对。

成功才精确清理本次runtime/code，ledger永久保留；未知归属/创建不明/中断保留unknown，先核单位scope再stop、确认CG空才撤规则。SIGKILL等不能保证自动恢复，不能覆盖或停止别的对象。默认case worker40s、unit50s、owner等待90s及有界命令/回收；不是任意kernel阻塞下的全局硬时间保证。

27/27成员、源码、unit与driver重渲染、宿主/工具SHA和空results由两名fresh审阅分别核对，最终无必须修项。当前拟用unit manager为not-found/inactive/dead、MainPID0、fragment/dropin/CG空；代码/runtime/ledger/unit路径均absent。没有运行完整入口、预占、服务或nft。只替换解释器及Bind源路径的/tmp语法副本verify退出0，原unit仍需安装后的真实检查。

## 回归与验证

新未绑定D1：service_egress50、fork_observation21、fork_observation_kernel4、observed_launch_fixture3、resolver_owner49、resolver_worker18、resolver_bundle4、bootstrap_fifo1，共150项。相关组合另含原observation21、phase37、core_wiring7、auto_bootstrap8，合计 **223 passed**，无skip/deselect。

原Bootstrap源成员open可能在FIFO上先阻塞，已用普通独立子进程的真实/tmp FIFO反馈环先超时失败，再为工作区新bootstrap加O_NONBLOCK并按fstat受控拒绝，相关9项通过；旧已执行包字节不变。合成model额外runtime目录曾比说明宽，新增实际preexec边界捕获回归先红再收窄为版本化stdlib，worker18项通过。其余窗口顺序、cleanup覆盖和metadata bool/int等回归各保留先红后绿。

16个本轮Python文件Ruff/format与MYPYPATH=src mypy通过。CLI兼容结果、链接/diff与最终scope含collect审计随本轮回记；不扩历史分母/required/正式回执，未运行完整离线门禁。内部细节不发GitHub，公共回记只含通用进度。

当前仅准备完这项无网络H1/H3包，待所有者绑定封印批准并亲自执行；不复用旧root或网络余额。下一真实Pi/认证/模型、完整接收权威/H5/激活仍未获许可，read_evidence=None、Live待探索与B等待保持。
