# #167：合成RPC的外部中断与真实墙钟工程控制

## 范围与身份

本轮在现有AFK范围内，新增独立未绑定D1模块 `tests/test_issue167_live_fault_engineering.py`，只用临时合成Python controller/协议对端及公共run_call/PipeSession。没有Pi/Node、凭据、网络、root、服务/规则变更、真实数据库/安装锁或崩溃；没有修改生产代码、旧测试、历史证据或注册分母。它不替代[剩余真实案例](../../intent/review/issue-167/remaining-after-six.md)。

该模块 **4 passed**（两个KeyboardInterrupt注入点、一个外部SIGINT、一个短真实墙钟控制），mypy、Ruff check/format通过。默认pytest使用短截止；真实300秒是另行显式调用同一有界helper的一次控制，不增加D1节点、skip或正式回执。按本轮计数约束，SIGINT成功后没有为了复核再次运行该节点或整模块；fresh只读源码审阅及主代理复核，无额外信号。

## 外部SIGINT与KeyboardInterrupt

两例KeyboardInterrupt在真实PipeSession通信后的pump和清理killpg位置注入同一真正KeyboardInterrupt对象；核对异常对象继续传播、没有RpcCandidate返回，并在测试夹具fallback前确认leader及合成孙进程回收。只覆盖这两个固定位置，不泛化为所有异常窗口。

外部控制由父进程对Popen返回、已pidfd固定且仍存活的自建controller发送一次SIGINT。对端和孙进程来自固定合成fixture通知，先pin pidfd、核对仅自建进程的PPID/PGID及前后存活；不会读取任意cmdline/environ/内存、信号其它进程或依赖易复用PID发送。controller沿真实run_call传播KeyboardInterrupt，清理断言先于fixture兜底；父侧再独立通过两个pidfd观测退出。

本轮真实SIGINT物理发送总计 **1**，没有用cancel()或普通异常改名代替。prompt_observed只证明本地合成peer已读到prompt的状态通知，不证明controller已消费ACK，更不是供应商收件确认。没有生产任务入口或租约事实。

## 唯一300秒真实墙钟控制

显式调用 `run_control(..., mode="wallclock", total=300)`，该分支使用原DEFAULT_LIMITS，不patch时钟。合成对端完成初始化并读到prompt后保持挂起，factory仅进入1次；父绝对上限340秒、retries0。本地claim先固定六个列明执行材料SHA，结束后逐项比较相同：公共rpc.py、rpc_pipes.py、rpc_types.py，既有a8_pipe_support.py/a8_pipe_worker.py及新D1模块。原运行源在等待期间未编辑。该六成员清单不是完整传递依赖闭包或正式整树验收身份，不能扩大其绑定声明。

受控结果 `.scratch/issue-167/offline-fault-engineering-v1/wallclock.json`：

| 字段 | 实际结果 |
| --- | --- |
| result / reason | observed_expected / timeout |
| run_call真实monotonic耗时 | 300.003066805秒 |
| 父总耗时 / 绝对上限 | 300.246666506秒 / 340秒 |
| factory_count / external_sigint_count | 1 / 0（本长例） |
| 对端组回收先于fixture fallback | true |
| 父独立pidfd退出观察 | true |
| partial_candidate_returned | false |
| source_bindings_unchanged | true |
| actual_pi / network_operations | false / 0 |

结束后主代理只读重算六源SHA，核对claim、结果、时长、回收和无重跑；没有再次执行300秒控制。本地claim保持reserved_unknown消费标记，结果单列，不借新标识清余额。精确claim/结果SHA与执行材料绑定留在同目录，不上传GitHub。

## 不能外推的结论

本轮证明固定合成对端条件下公共RPC的真实时间截止、特定中断传播及回收工程行为；不是实际Pi信号、实际Pi300秒超时、自然供应商迟延、网络出口挂起、真实供应商错误、计费停止或生产租约通过。原六格整批unknown不改；普通产品准入仍阻断。

实际Pi的对应案例仍须新的具体H1/H2/H3和有限上限；若未触发，应记未触发，不自动加长任务或重发。本轮无模型token消耗声明，因为没有模型调用；不将本地回收解释为真实供应商零成本。
