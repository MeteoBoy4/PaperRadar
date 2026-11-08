# #167：按 A 准备的固定 Node 无秘密诊断包

所有者已选择[内部解析未知范围 A](../../intent/review/issue-167/node-dns-budget-decision.md)。本轮仅准备源码、离线测试、具体审阅包和只读事实；没有运行 Node（包括版本/语法检查）、Pi、真实锁、网络、root、服务或规则加载，也没有读取凭据/业务记录或写入安装树。选择 A 不是本包执行许可，仍须新 H1/H2/H3 单次批准。

## 待审身份及影响

包为 `.scratch/issue-167/h1-node-diagnostic-v1/`，run=`b62d4a90e713`。先读 owner-review.md、node-binding.json、nss-context.json、plan.json、unit/规则和全部源码；[具体过程计划](../../intent/review/issue-167/node-diagnostic-plan-v1.md)说明判据和与产品路径的差异。

| 材料 | SHA256 |
| --- | --- |
| review-seal.json | `cdad7a9e9bb6ab82b704fe1ec7dfc458262dc4bec78487c1584fb4da371bfdc2` |
| core manifest | `5c3a8a434eb161594f63f4fdabf9ee65efdf5a38e8e7b964c8a5d34123c6a5f3` |
| driver | `da500581f7e98cbed49edcb64b477d4cc97a67bf1c4e94ce5e2d89eb8ce62e33` |

精确对象为一个 UID/GID1000 unit `paperradar-167-h1net-b62d4a90e713.service`、独占 inet 表 `paperradar167_b62d4a90e713`，代码 `/home/paperradar-probes/issue167-b62d4a90e713`、runtime `/run/paperradar-issue167-b62d4a90e713`、永久记录 `/var/lib/paperradar/probe-runs/issue167-b62d4a90e713.json`。保持固定 cwd、cap/ambient 空、NNP/seccomp、Delegate=no、双零 core、SocketBindDeny=any、AF_INET、服务内只读 resolver 及原恢复次序。

允许集合仍为应用可见 TCP443 至28.0.0.0/8、UDP/TCP53 至192.168.44.1；不新增目标、不开放模型 TCP53、不改全机/路由器/代理/core 策略或产品启动/协议身份。来源仍是所有者冻结配置及其确认，不核验上游映射、最终IP/线路，不主张出口身份；API/auth共享池不证明二者分离，IPv6 not_assessed。

## 执行清单及证明边界

拟4个固定 Node exec：无 Landlock 的 router TCP53 connect 正例1；原 Landlock 同目标拒绝1；api/auth 各一次默认 lookup及至匹配IPv4的 TLS1。父 Python 每域名先显式 UDP/TCP A 参考各1，共4个参考查询。lookup调用2，OS内部 A/AAAA/NSS/重试次数、wire QNAME、TCP fallback尝试均 unknown；不写总 DNS≤2/6。HTTP/auth CLI/model prompt/Pi/IPv6网络连接/崩溃均0，无应用重试或备用域名。

TCP53正负对照各5秒；查址/TLS每段最多10秒，同时受参考 TTL 更早截止约束。parent 截止覆盖输出/退出/回收，wait 后再查截止；不能只靠 JS timer，因为 OS lookup 仍可能在后台等待。每个 Node 回收后补查 NSS/hostname结构，缺失或漂移停止。父调用区间严格位于两份同轮参考收到后、最早失效前，旧1秒TTL不复用、不补查或延长。

同一 unit/cgroup 下每阶段只准受信 controller 保持存活，完整 verifier/原独立 binding持续核对。正例需 allowed 增量且无反相计数；Landlock TCP53拒绝应没有本表 packet 增量，不能冒称 nft reject。子进程未正常退出或窗口/身份不完整均 unknown；不降低已有清理/恢复条件。

Node 仅 builtin 固定JS，安装树外以 `-e` 提交；空环境，无 family/RES_OPTIONS/LOCALDOMAIN改写、loader、Pi或SDK桥。默认 lookup返回一个地址，IPv6/非参考地址停止，不挑备用地址。其查址和 TLS 是窄诊断，不等同 Pi/Undici connector 的全部自动选址行为或产品启动路径。

Node TLS 使用该固定构建的默认信任设置、固定 servername/hostname、rejectUnauthorized与最低TLS1.2；无 client key/cert、session或环境CA覆盖。它与前轮 Python TLS 的显式系统CA不同；本轮父Python只做DNS参考，不TLS。固定版本的默认 hostname 校验和 CA语义依据在[过程计划](../../intent/review/issue-167/node-diagnostic-plan-v1.md)直接链接官方源码/文档。没有通过执行 Node来验证此诊断JS的实际语法或运行效果；该现场结论仍待获批执行。

## 固定供给与只读原锁投影

固定原实例9b8e342f8bb64a29b1b1b0aa51b68c85、供给50eb56a3a7fab3c1dcdb3c54ea41a8ff1ca808af65182365368e1b3ef06c6587，实际 Node ELF SHA=`94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90`。版本沿公开供给 Node22.23.4/Pi1.4.0声明，不冒称本轮执行过版本探测。manifest.node_sha256 是归档摘要，不能代替 ELF摘要。

新增 stdlib helper 仅对白名单8张供给表/列/函数作 mode=ro、query_only、一致快照投影；不读取业务行、配置正文、材料raw或认证。失败检查只输出闭集 reason_category，不透传原始原因。Root仅验证包内绑定结构，不读实际DB或取原锁；未来UID1000 worker按封印的 rootmarker、登记/选择、路径和原锁dev/inode/owner/mode/nlink核查。

原实例锁仅 O_RDONLY/NOFOLLOW/NONBLOCK打开、SH|NB，四个 Node传递同一个 FD/OFD，不新建锁、不复制Node、不LOCK_UN；只关闭各自FD。持锁范围两端核对完整 tree-v1、实际ELF与公开登记，不把重hash塞进TTL临界段。明确标签为 `diagnostic_readonly_original_instance_lock_not_product_use_install`：没有调用完整产品use_install，不重做材料/D5/cleanup DAG或snapshot规则，不据此获得产品资格。

实际公共树只做元数据枚举：regular19692、directory2530、symlink11、special0，全部regular nlink1；regular总307493032bytes、最大124902584bytes，适用helper的100000项、单文件256MiB/总2GiB限制。未读树内文件内容或重算整树；此记录在 `.scratch/issue-167/node-diagnostic-tree-metadata.json`。ELF的单文件只读哈希与公共登记核查另属 prepare，不与该元数据枚举混为整树通过。

## 离线验证与待执行状态

新增独立未绑定 D1：`test_issue167_node_diag.py`37项、`test_issue167_node_diag_bundle.py`4项、`test_issue167_node_diag_supply.py`25项，共66项。与原 service_network36、service_egress50、resolver_owner49、restore_regression16 的相关组合 **217 passed**；命令使用 `UV_CACHE_DIR=/tmp/issue167-observation-uv uv run --offline --locked pytest -q …`。

8个新Python文件的 mypy（MYPYPATH=src）、Ruff/check/format通过。关键回归覆盖有界/单JSON/坏身份/超额计数、阶段早停、TTL/bool/截止、父timeout kill/reap、NSS后验、必要packet增量、只读白名单拒绝业务/写SQL、旧锁缺失/替换不创建、busy、树/外链/FIFO/登记/选择漂移以及原OFD继承。父截止两处缺失、原因原文投影等反例均先复现后修复；原始投影反例仅在隔离模块和/tmp合成DB回放，不是实际DB泄漏。

真实合成 Python 子进程仅操作/tmp自建锁：父close后独立EX仍拒绝，子退出才释放；没有取得真实实例锁。prepare不锁不整树、load不访问实际供给的断言通过。静态JS审阅和mock不能代替实际Node效果。

fresh终审核对39个封印成员、映射源码、两份entry、完整driver、unit、四份规则、工具/host/resolver/binding；无阻断项。bash-n通过。普通用户仅在/tmp将安装前缀替为现有包路径的unit语法副本 `systemd-analyze verify --man=no`退出0、无stderr；没有安装/执行原unit，安装后仍须原字节检查。新unit manager为not-found/inactive/dead、MainPID0、fragment/drop-in/CG空，unit文件/CG/代码/runtime/永久记录精确路径均absent，results为空。

未批准草稿移到 `h1-node-diagnostic-v1-unapproved-draft`，入口禁用，仅保留材料；无执行/预占/退款，不给同run新增额度。当前只提交上述canonical候选。最终链接/diff和固定scope含collect审计另记回记，不扩历史分母/required/正式回执；未运行完整离线门禁。

## 实际授权仍待申请

新入口为 `owner-wizard.sh --owner-config-confirmed --owner-dns-unknown-confirmed`，任一flag缺失均在本地预占/sudo前拒绝；flag仅转录所有者声明，不自证许可。获批后所有者只向sudo TTY输入一次密码，脚本验证/复制受保护字节并完成唯一启动、核查与恢复；不root导入workspace代码。永久预占、闭集恢复阶段、resolver持久before/after、CG空后删本表与成功清理均沿既有判据。

选择A及本次离线通过不授权执行；真实Pi、凭据、认证/模型、供应商能力/故障、H5与产品激活仍需后继授权和证据。内部配置、进程/内核详情、回执及相关哈希只留本地，不发布GitHub。
