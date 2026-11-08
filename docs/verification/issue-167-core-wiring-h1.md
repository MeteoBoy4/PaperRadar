# #167 续办：生产子进程零限额接线与 H1-0 审阅包

本轮保留全部前轮未提交工作，基线仍为 `c0bee235f4ebb0a88be4a60c392c96619ec61683`。重读 #167 原生关系为#140 closed（1/1），subIssues0/0；终局来源为所有者本会话与已回帖记录。没有扩展loader、精确请求计数或全机core方案，也没有进行真实Pi/Node、认证/模型、外部网络或新崩溃。

## 已实现的代码边界

`pi_execution/isolation.py` 新增只用标准库resource的 `disable_core_dumps()`；先设置软硬RLIMIT_CORE=(0,0)，再回读核验。模型的IsolationBoundary pre-exec最先执行该函数，宿主auth Popen pre-exec引用同一函数。设置或回读失败不得继续exec，分别沿现有auth_failed/startup_error受控路径；没有新增原因、launch策略身份或协议注册，也不修改父进程限额。公共现状见[执行资源Contract](../contracts/pi-execution.md#子进程零-core-限额)。

独立D1 `tests/test_issue167_core_wiring.py` 7项：真实合成Python auth/model子进程exec后均读到[0,0]，父限额不变；auth/model设置失败拒绝且不泄漏哨兵或外部错误文本；回读不生效也拒绝。先写回归得到auth实际继承[0,-1]的失败，再接线转绿。不执行真实Node/Pi或凭据，pytest没有崩溃。

此接线不等于持有token的controller已经由服务零限额保护，不证明Apport版本/分支长期稳定，也不解除普通产品read_evidence缺失阻断。服务部署与后续doctor长期检查分别保留其责任。

## 所有者清理已完成

所有者明确报告执行前轮精确清理命令；本轮以同一普通用户仅lstat指定合成rawcore成员，确认absent，没有打开内容或删除其他成员。回执在 `.scratch/issue-167/core-limit/owner-cleanup-receipt.json`。前轮[正负对照报告](issue-167-final-core-validation.md)保留当时尚未删除的历史字节，本条是后续状态。

## H1-0：先核对服务本身，不冒称完整隔离通过

[完整无凭据H1提案](../../intent/review/issue-167/h1-proposal.md)指出旧EXP-2实际为单worker中直接fork链、unit外phase规则管理，可以保留原安装锁OFD/token内存路径而不先引入跨unit broker或Delegate。旧全机core guard/IPv4-only/fake-IP绑定不能复用。它仍只是后续完整H1设计，不作为已安装包。

本轮另生成更小的H1-0服务预检包，源码为 `scripts/issue167_h1_bundle.py` 与 `issue167_h1_worker.py`：

- 只新增一个具名unit，以uid1000检查服务/固定合成Python后代的core软硬限额、NoNewPrivileges、五类socket创建被拒绝和constant cwd。
- 合成解释器仅复制本机Python字节到包内非打包路径，不更改系统Python、固定安装、生产入口或启动身份。worker不读凭据/环境或core，不crash，不创建网络连接、DNS请求或运行Pi。
- 不加mount namespace选项，避免把Apport namespace早退混成零限额证明；不装nft/guardian/timer/socket或开机自启。
- 不证明真实端点允许正对照、主机出站完整性、文件白名单、任意后代逃逸、模型/凭据能力或产品准入。完整H1与H2仍分别审批。
- 使用wizard skill原模板库生成四阶段所有者手动向导；向导只展示命令，不自动sudo、安装、启动或删除。root步骤仍由所有者审阅执行。

### 审批与修订

所有者已批准H1-0范围及原unit `paperradar-167-preflight-a51db59cf820.service`，并明确旧包尚未安装或启动。独立审阅发现v1在动作后才排他创建回执，重复start可能先重复检查，已撤回v1用于执行；没有实际现场重复。

修复先用入口回归观察到“已有回执仍调用collect/合成子进程”的失败，再改为任何动作前O_EXCL预占并fsync；失败/中断保留reserved_unknown，后续同回执不能再次collect。另补期望uid核验，以及成员SHA、同名unit/drop-in冲突、卸载前目标unit SHA的具体手动核对步骤。不会自动推定人工步骤已执行。

修复包为 `.scratch/issue-167/h1-service-preflight-v2/`，保留原批准unit名、uid、动作与权限范围；v1原字节保留，不执行它。v2 manifest SHA256为 `b8a5f05bfb930543225a8df17ea56ceb744752bc6197dd5345d4ce4d772aea2a`，6/6成员哈希与当前worker源一致。所有者须核对修订字节后使用v2手动向导；包中not_granted默认字段不能自授权限，真实授权以所有者会话/人工核对为准。随后出现v2受控运行回执，见下节的独立只读复核；不能从此推为完整H1通过。

## H1-0 当次观察（已获所有者批准、由所有者执行）

v2回执SHA256为 `a13bc2b778179c6d203e91f73be2a06feed8003df13a49f245e3e7354bb576d8`。主代理确认6/6封印成员未变、worker与审阅源码相同；已安装 `/etc/systemd/system/` 下唯一unit的SHA与封印一致，没有读取其他配置或凭据。

- 回执：uid=1000，core_limits=[0,0]，child_metadata=[1000,[0,0]]，no_new_privs=true，cwd_matches=true；IPv4/IPv6 TCP与UDP、Unix共五类socket创建均denied；auth_calls=model_calls=0，结果observed_expected。
- 普通用户限定systemctl只读：LoadState=loaded、ActiveState=inactive、SubState=dead、Result=success、ControlGroup为空、DropInPaths为空；LimitCORE=LimitCORESoft=0，NoNewPrivileges=yes。RestrictAddressFamilies的普通显示为空串，不把该单字段当完整语义证明；源码配置、字节核对和实际五类socket拒绝分别保留。
- 本次仅支持服务预检这些字段和固定正常退出的合成后代；不证明任意后代均被回收、所有出站路径均拒绝、真实Pi/Node文件/网络或模型可用。最初批准前后的v1问题未产生现场重复；没有自动重跑或执行root动作。
- 运行后首次查询unit文件仍存在；所有者随后完成v2向导。主代理复查精确文件absent，manager为LoadState=not-found、inactive/dead，FragmentPath/DropInPaths/ControlGroup均为空。恢复回执另存results/agent-restoration-observation.json；不只依赖inactive/dead来声明卸载。

受控回执与此只读状态记录在包的results目录，未导入产品证据权威。其他H1/H2范围没有因H1-0获得许可。

## 开发验证

- 新增D1核心接线7项通过；相关launch/isolation/review/external_review组合初次84 passed+1失败。失败节点在创建首个AF_INET socket时被工具沙箱EPERM拒绝，尚未进入待测逻辑；保留失败，未skip/改旧测试。该节点后以同一普通用户沙箱外本机loopback合成对端单独复核1 passed。所选85节点分别取得通过，不能称单次组合85passed。
- 新增D1包生成/worker模块 `tests/test_issue167_h1_bundle.py` 12项通过：静态封印/模板库/无自启、uid/路径拒绝、受控元数据、已有回执入口不执行动作、中断持久预占。pytest不启动服务或root操作。
- 定向Ruff check/format、mypy六文件通过；包向导bash -n通过。系统未安装shellcheck，未运行。
- v1/v2 unit在沙箱内systemd-analyze遇到其内部socket权限拒绝；同一普通用户沙箱外只读 `systemd-analyze verify --man=no` 均退出0，不安装或启动服务，初始失败保留。
- 因执行边界的导入涉及doctor/CLI链，运行 `check-compatibility cli`：59 passed，退出0。它不是完整离线门禁。
- 最终只读固定scope审计、链接/diff结果在回帖记录；不新增旧组required或重绑历史材料，不修改旧测试/fixture。两个新增模块分别登记7/12，不叠加历史组合为唯一总数。

没有完整离线门禁、真实Node/Pi、模型调用或准入激活；H1-0手动执行与卸载已获所有者报告并由主代理只读复核。不能把这个更小预检冒称完成H1的网络/文件/后代全部责任。

## 独立补测：同uid跨进程读的有限结论

[Landlock process_vm_readv对照](issue-167-landlock-process.md)只读取自建空环境target内预定25字节哨兵buffer、不输出内容；同一普通用户沙箱外，未隔离正例allowed，现有IsolationBoundary负例返回EPERM，独立D1 1项通过。两peer均NoNewPrivs=1、core(0,0)，没有为了通过而更改Yama或产品规则。默认工具沙箱内连正例也被拒，保留positive_control_unknown失败，不把它归因为Landlock。

这支持现有域关系下一个具体syscall的拒绝，不等于全部ptrace/process_vm_writev/pidfd_getfd/信号/proc路径或真实部署已经隔离。后续完整H1按需要补其他负例，不据此无依据地要求跨uid/broker，也不降低未验边界。
