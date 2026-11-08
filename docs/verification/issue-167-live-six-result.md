# #167：S 六格现场事实与收尾 unknown

## 身份与总结果

所有者批准并执行了[已封印准备包](issue-167-live-six-s-preparation.md)。本次 run 为 `e93f7b82c461`；原包、结果和永久单次账本保持原字节，不因后续诊断或清理重新定性。这里只追加本次事实，不进入历史分母、required 集合或正式回执。

本地受控回执 `.scratch/issue-167/h1-live-six-v1/results/owner-run.json` 的 SHA256 为 `50816d0838ef645196165d7943bb2b0d02382ce98c430b4fc6ab28e9d1cf7750`。外层及内层结果均为 **unknown**，`failure_stage=exit`、`failure_reason=owner_operation_unknown`、`artifacts=null`。六格各自记录和最终 worker 记录为 `observed_expected`，且 cases、preflight、selection journal 一致；这不覆盖监督进程缺失的成功退出证据，不构成整批通过或产品准入。

## 六格有限事实

固定 Pi 1.4.0、公共 prepare_launch/use_install、原启动/协议身份及此前绑定未变。仅使用批准的合成材料。下表时间来自受控回执，单位秒；token 为 Pi 报告用量，不主张计费核验或独立 HTTP 计数。

| 格 | 耗时 | input | output | totalTokens | UTC 验证完成 |
| --- | ---: | ---: | ---: | ---: | --- |
| boundary-low | 12.955 | 518 | 74 | 592 | 2026-11-07 23:13:21.668297 |
| boundary-high | 16.837 | 518 | 205 | 723 | 2026-11-07 23:13:38.586733 |
| value-low | 16.295 | 841 | 335 | 1176 | 2026-11-07 23:13:54.982827 |
| value-high | 21.010 | 841 | 546 | 1387 | 2026-11-07 23:14:16.094392 |
| read-low | 28.485 | 1294 | 935 | 2229 | 2026-11-07 23:14:44.660141 |
| read-high | 33.255 | 1294 | 1138 | 2432 | 2026-11-07 23:15:18.017226 |
| 合计 | — | 5306 | 3233 | **8539** | — |

每格 auth CLI 完成、model factory 进入一次、显式 prompt 完成一次，公开业务 validator 与模型身份比较通过；RPC 初态 clean、命令队列空、settled、EOF/退出零与 public terminate 返回均有记录。每格 prompt ACK sequence10 先于 agent_start sequence11。这里只证明本次普通合成调用，不证明实际参数因果效力、日期模型映射、订阅限额或供应商故障。

总计已消费六个 auth CLI 与六个显式 prompt；不退款、不重发。第一 auth 阶段 allowed packet 有增量，后续 auth 阶段没有新增 allowed packet；这不能证明恰好一次刷新 HTTP，也不能独立排除隐藏请求。模型/刷新 HTTP 均保留可证下界0、上界unknown；重试、预热、内部解析等未独立可见。初次过期与计划刷新来源是执行前所有者输入声明，不推定为以后批次的当前令牌状态；不得据此读取真实令牌或自动重试。

## S 文件观察与隔离

六格均记录 `session_window_complete`：session/guard/terminal/cleanup 完整，session mutation0、unknown mutation0、公开 settings 严格语义核验成立；终态 session 和 unknown 类成员0，独立目录删除成立、post-terminal assessed write0。每格终态分别有 baseline regular1/directory3、auth store regular1、model store regular1、compile cache directory2/regular31。已知非 session 的边界事件下界分别为 auth3、model3、compile1、control_settings12、store_lock30；缓存/锁内部全历史仍为 **not_assessed**，不能外推整个 attempt 零写。

持久认证目录另记 before/after metadata checkpoint，history not_assessed、persistent_not_deleted。agent 未读凭据内容或派生值；不删除认证目录及其缓存。模型临时树已独立删除，与下面仍保留的 root 控制目录不同。

持密前 IPC 七项控制允许/目标拒绝及观察后端初始化完成。独立 binding 核验的17份完整内核规则快照序列一致，最终 allowed847/reject0；packet 是内核计数，不是应用请求数。应用可见地址允许集合仍为批准的 fake-IP 池 TCP443 与路由器 UDP/TCP53，IPv6 not_assessed；本机不核验上游最终映射、线路或出口身份。当前 core 适用性检查沿原第三路边界，不新增崩溃或修改宿主策略。

## 恢复与遗留物

原回执的 host restoration 为完成：本次表和 unit absent、永久账本保留、resolver before/after相同。随后只读核对 manager 为 not-found/inactive/dead/MainPID0，unit文件和本次cgroup目录缺失；卸载后 manager 的默认 Result 不能倒推原 worker 成功退出。

worker 最终结果发布前，公共 API 已以 CAS 恢复原数据库逻辑选择，保留追加历史。独立普通用户只读查询仅访问两张公共选择表，确认当前 activation8 与回执恢复项一致，语义与最初 activation1 相同；未读业务/认证行或写数据库。此结论与 host 恢复、监督退出分别登记。

由于总结果unknown，原 finish 未清理 root-owned 代码和 runtime 控制目录。只读 lstat 确认两者仍在；永久账本0600、109292 bytes，仅核元数据，不由 agent 读取内容。其精确目录身份及后续仅清理审阅包留在本地。本文件冻结时尚未执行额外 root 清理；认证目录、原账本与全部原回执必须保留。

## 收尾证据缺口与后继边界

原程序把 phase_gate 与 wait_exit 合在同一个 exit 阶段，未保存具体子阶段/manager退出状态。现存 exit gate 的 exact run/sequence7 合法，但实际写入流程先发布文件再 fsync 父目录，文件存在不能证明该函数返回。纯 mock 对原封印实现分别注入发布后目录fsync失败、wait_exit失败，二者均产生同一 exit/unknown 投影；严格成功控制可正常完成。没有足够证据确定本次实际根因，未读日志、stderr、进程环境或私有账本内容来追查。

前瞻诊断可区分写 gate 与等待退出、保存封闭状态，但不能补回本次已缺失的证据，也不修改原封印包；独立D1和仅清理材料见[离线续办](issue-167-live-six-exit-followup.md)。任何额外现场测试、合成监督重验或真实重发均须另有具体授权；六格有限事实是否作为后续探索的依据、是否保留监督退出缺口，由所有者裁决。不得把部分事实改为整批passed或降低既有判据。

本次未覆盖外部 SIGINT/KeyboardInterrupt、真实墙钟/网络挂起、真实供应商错误、参数效力/日期模型/限额、H5、产品接收/人工激活。普通产品缺证据阻断保持；本票和Live模块未完成。
