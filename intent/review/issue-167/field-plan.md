# #167 A6：现场计划候选 v1

网络范围已由所有者 H4 终局冻结为 [ADR-0050](../../../docs/adr/0050-bind-egress-to-owner-visible-addresses.md) 的应用可见集合；下一前置元数据轮按 [DNS/TLS 计划 v1](real-exit-dns-tls-v1.md) 另行审批。下文旧网络案例不扩大现行预算或替代该范围。

最新H4终局覆盖本计划中的旧硬门槛：core采用项目显式零限额的第三路（ADR-0049），不制作全机分发器；计数采用可证下界+unknown、token预算口径依Pi报告（ADR-0048），不采用新启动身份、不为精确计数重跑EXP-2或将loader接线。当前只可保证已授权的显式派发/CLI/attempt边界并披露隐藏请求未知，不声称可以实施实际HTTP硬上限。任何新模型/认证批次仍需H2具体批准，旧余额不复用。


本轮只冻结可审阅案例和预算；H1/H2 之前无现场许可。未满足的观测/桥接前置使计划保持不可执行，而不是默认豁免。旧 EXP-2 余额不得挪用。每次启动前核对最终代码/材料哈希、完整绑定、授权 receipt 和剩余额度；人工改计划即新版本，但原轮消耗/失败历史继续保留。无自动重试或 fallback。

旧pre-exec dumpable候选失效的反证仍保留，但H4已明确第三路替代：[项目显式零core限额的合成正负对照](../../../docs/verification/issue-167-final-core-validation.md)。该验证不等于实际auth/model与服务已接线；未完成适用部署前不提供真正凭据。另须落实[原OFD传递与同uid内存隔离](remaining-decisions.md)。

## 先行无认证案例 H1/H3

所有案例只用合成 worker，真实 Node/Pi 仍需 H2；每例一次，无HTTP/模型/刷新请求。由所有者按 deployment-plan 完成宿主变更后执行：

| ID | 动作与预期 | 停止与回收 |
| --- | --- | --- |
| F01 | cwd/所有祖先放合成 AGENTS/CLAUDE/.pi 资源对照，文件读写哨兵允许/拒绝符合精确白名单；最终恢复空cwd | 任一资源可注入即失败；先停止再还原本轮哨兵 |
| F02 | 两个角色各对合成允许端点、同IP错误端口、未授权IPv4/IPv6、UDP53/443、DNS各1连接尝试；允许/拒绝计数分别有对照 | 全部目的均为所有者控制测试端点；每角色最多8次连接，不连接真实供应商；无DNS隐式联网；不满足则停止 |
| F03 | 合成后代短暂写删session、预建目录写入、全运行窗口丢失/overflow、观察器退出各一次，缺失/丢事件必须unknown | 证明探针可报失败；不把注入哨兵作为Pi真实行为 |
| F04 | 按第三路检查实际项目进程/服务显式零core限额及Apport非打包适用分支；已有本轮C合成零/非零对照，不自动重复 | 只查目录新增成员，不读core；root内存瞬时采集残余已接受，漂移长期doctor交后续工程；不把C结果外推真实Pi部署 |
| F05 | 端点/boot/策略/证据到期/观测器失效各1次漂移拒绝；重启controller仍保留旧消耗与失效 | 不发模型请求，不实际重启宿主；重建项目controller模拟 |

F01 资源探测只在所有者批准的项目路径操作；不往 `/`、`/srv` 写探针。祖先只读清点；若须修改祖先，另交 H1/H4。F02 若无法提供合成端点，则该例阻断，不改用真实供应商。

## 合成材料与首次六格覆盖 H2/H3

统一模型元组 `openai / gpt-6.1-sol / prompt_only / provider_default / chatgpt_subscription`，consumer 为 boundary/value/read，各 low/high；`temperature/top_p=null`。每格独立冻结输入/配置/system/user字节、业务Schema/规则/证据上下文与指纹，不共享会话。取合成天文无关任务：虚构 Profile「玩具估计量对合成序列的均值估计」、题名「合成估计量示例」、摘要「比较虚构估计量A与B，无真实数据」；value 带冻结主题与适用性指引，Read 为自制单页PDF/正文、两个独立有效evidence项。完整格式材料由公共 builder 构造并离线业务校验，哈希封印供 H2 审阅，不能把本段自然语言直接发给Pi。禁止真实Profile/论文。

已用公共 `compile_config → build_stage_input → build_call → render_request` 生成六格新输入，见 [无秘密封印](synthetic-manifest.json)；完整合成字节保存在忽略目录 `.scratch/issue-167/synthetic/`。每格含 stage-input、system/user、description、extraction-input、context 和通过对应公共业务校验的 `expected-valid-output.json`。Read 使用既有 schema v1 与 `validate_read_output_v2(attempt_ordinal=1)`，v2 是接收规则身份，不是另一个 schema 版本。PDF 是新手制单页；canonical/两个 evidence 均为显式手制合成，经公共 normalize/render/reconstruct_context 构造，不冒称 Docling 提取或真实版式通过。模型请求仍为零，封印 `authorization=not_granted`。

复现：`uv run --offline --locked python scripts/issue167_materials.py /tmp/issue167-new-synthetic`（目标须不存在；不覆写旧封印）；公共 manifest 中的配置/输入身份应一致，数据库字节不作为确定性封印。`tests/test_issue167_materials.py` 检查六格覆盖、独立指纹、文件哈希、公开 manifest 一致及旧根拒绝覆写。extraction 配方是旧 EXP-2 无认证配置的显式新版本副本，只用作合成身份，不继承旧批准或安装许可。H2 仍须审阅最终全部字节及 sha256，A3/A4 现场前置未解除。

| ID | consumer/thinking | 预期 | 显式CLI / prompt 上限；实际模型HTTP / 刷新HTTP |
| --- | --- | --- | --- |
| N01 | boundary/low | 完整RPC与boundary权威验证 | 1 / 1；unknown / unknown |
| N02 | boundary/high | 同上，独立档位证据 | 1 / 1；unknown / unknown |
| N03 | value/low | 完整RPC与value权威验证 | 1 / 1；unknown / unknown |
| N04 | value/high | 同上，独立档位证据 | 1 / 1；unknown / unknown |
| N05 | read/low | Read v2权威与证据回查 | 1 / 1；unknown / unknown |
| N06 | read/high | 同上，独立档位证据 | 1 / 1；unknown / unknown |

每格wall 300s、auth30s、cleanup10s；显式prompt/CLI各最多1，不因一次CLI就推断一次刷新。实际模型HTTP、隐藏retry/预热/刷新只能记可证近似下界及unknown；没有对应层发送证据时，下界也不能从prompt/TLS/packet补造。预算的token计量以Pi报告为权威，缺失/totalTokens=0保留未知，不当零消耗；单价成本估算与供应商独立账单分开。任务attempt/每日名额不变，换run不清余额。

不为计数采用新启动身份、注入loader、代理、patch SDK或重跑EXP-2。精确计数缺口本身不单独阻断本轮；协议/身份、外发、文件与出站、完整窗口/清理等其余闸门仍分别满足。隐藏请求与Pi口径限制须进入后续doctor/日报，精确请求计数留I重评。首批provider/model绑定未放宽，可见替代provider/额外回合仍停止，不自动切换或fallback。

## 故障与能力 H2/H3/H4

正常六格完成且分别审阅后，才考虑以下独立批次。每例 `value/low`、新指纹、新会话一次；不以此覆盖其他阶段/档位故障行为。每例显式上限同正常格，不能因取消或Pi用量缺失/零值就返还预算。所有批次合计最多10 prompt与10 auth CLI；隐藏模型/刷新HTTP总数仍unknown，token计量依Pi报告，不把候选授权当实际HTTP硬限额。独立批次必须逐批新授权，数字不是现在许可。

| ID | 方法 | 预期与限制 |
| --- | --- | --- |
| E01 | 所有者从外部向精确controller PID送SIGINT | 保留中断/租约事实，无部分候选，整组回收；不能只call cancel冒充 |
| E02 | 测试入口在真实运行中受控触发KeyboardInterrupt | 区别E01；不把普通异常改名；历史余额保存 |
| E03 | 实际单调墙钟到300s | 超时与清组；若供应商提前完成就记未触发，不补跑，不虚构时钟 |
| E04 | H1已批准的项目专用网络挂起，绝对300s截止 | 本机网络故障仅证明网络挂起恢复，不称供应商错误；规则恢复先确认进程已清 |

认证刷新失败先用合成对端/拒绝连接，计为本机失败，不损坏真实凭据以强迫刷新。真实刷新失败/供应商错误/额度/日期alias政策优先使用供应商现有明确资料与自然发生的受控错误；不故意耗尽额度、不发超额请求。无法安全触发、缺可信公开能力资料或provider仅回显时，标 unknown，H4 决定是否接受有限探索；不默认豁免相应准入。真实参数效力无法仅靠两次输出差异证明；low/high 回显与真实供应商效力分开。

## 回执、停止与授权形状

回执白名单：plan/case/revision、code/input非秘密SHA、collector身份与版本、host/boot/kernel/install/supply/策略/端点集合非秘密身份、consumer/thinking/模型元组、UTC开始结束/单调耗时、分层计数与完整性、三类文件观察状态、受控错误类别、cgroup空/目录删除/规则恢复事实、收集权威验签状态及失败历史引用。不要用户名、认证路径、文件名原文、headers/body/token/派生值、完整session、stderr、packet payload。receipt须说明何者来源推导、何者真实观察；不保存任意外部异常原文。

H1 批准必须列最终unit/nft/桥接/core补丁的差异、具体目标与恢复步骤；H2 必须列最终材料封印、端点/专用认证元数据（所有者供给，agent不读内容）、适用隔离证据、逐批case清单/预算/停止规则。两者独立，不由“同意探索”推断。缺失适用的显式预算/Pi用量口径声明、签名失败、绑定漂移、预算到界、异常资源可见、收尾失败立即停止本批；不自动重发，保留失败和未知。回收严格采用 deployment-plan 顺序，独立复核后才能下一批。H5 审阅探索结论，产品显式激活另行进行。
