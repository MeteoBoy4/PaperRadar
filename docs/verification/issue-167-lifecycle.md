# #167 A5：准入接收与生命周期离线验证

本次材料只记录独立探索原型。依据 [ADR-0047](../adr/0047-expire-and-explicitly-activate-live-evidence.md)、[Pi 执行现状](../contracts/pi-execution.md)及 [#167](https://github.com/MeteoBoy4/PaperRadar/issues/167)。没有接入产品 `read_evidence`，没有读取认证、调用 Pi、联网、部署配置或激活产品。普通产品继续 `evidence_missing` 阻断。

## 接收权威候选与信任边界

候选采用单一 Live receiver，使用受保护的独立状态库，核对所有者批准的采集计划、受信 collector 身份、签名和完整观察对象，再生成不可由配置文件直接制造的 received 身份。collector 与 receiver 的权限须独立于模型进程；模型不能写采集结果、替换观察器、接收状态或激活记录。receiver 从逐案例原始安全元数据重算覆盖与结论，检查事件连续性、结束时间及回收状态，不能只信 `passed=true`。生产应采用独立权限的签名或受保护的本地传输，不把共享校验密钥交给模型或普通用户配置。

`scripts/issue167_lifecycle.py` 用测试专用 HMAC key、内存 accepted/active 集合与显式合成 owner action 模拟上述边界。任意字典/布尔值、未知 collector、篡改签名、未批准 plan、缺观察项不能接收；received 本身不激活。HMAC 只证明测试消息的来源与完整性，不证明采集器诚实、观察充分或宿主安全。原型函数 `synthetic_collect` 可以在 Python 中直接调用，owner action 是合成字符串；二者均不构成生产认证机制。实际产品必须实现独立所有者通道、完整案例回执解析、抗回滚时钟、状态事务/持久化与备份权限。本原型不对攻击者控制 Python 进程作安全保证。

## 完整绑定组成候选

所有字段均为非秘密受控身份；不得包含认证路径、内容或 token 的任何派生值。指纹应覆盖规范的完整组成，不能用版本号或目录路径替代实际树身份。

| 原型字段 | 生产应核验的完整组成 |
| --- | --- |
| supply / install_tree / pi_version | manifest supply_id、install_id/实例与实际源码和依赖整树校验身份、固定 Pi `1.4.0`；不是任意相同版本安装 |
| node_toolchain / platform | 固定 Node 入口、版本与字节校验；架构、libc、OS，影响运行库的身份 |
| host | 机器受控身份、boot_id、kernel release/build、Landlock ABI、cgroup/service manager 能力；重启与内核变动不得隐式复用 |
| cwd_ancestors | 唯一 `/srv/pi-cwd`、各祖先 owner/mode/类型/真实目标、资源发现检查身份 |
| endpoint_policy / proxy_policy | 模型和刷新分别允许的目的主机/IP集合及解析策略、IPv4/IPv6、UDP/DNS、TLS 对端约束、端点漂移处置；显式代理禁用或配置身份，不含代理秘密 |
| launch_policy / isolation_service / core_policy | 精确 argv/env/settings 策略，系统调用和文件规则、专属 uid/service/cgroup、主机出站规则、继承/子孙回收、项目专用 core 策略及权限；观察期与卸载版本 |
| observer | collector/观察器源码版本、全部事件源/受控分类、窗口、连续性/丢失判据、会话/目录/请求/刷新计数方法；改变观测可信度必须重验 |
| config_bundle | 一份不可变的六格配置清单，按 boundary/value/read × low/high 映射完整 config snapshot、相应 Stage 投影、system prompt 精确字节、输出 Contract/schema、RPC profile、校验/证据规则身份；六格 receipt 共用清单指纹，各 slot 必须核验其映射 |
| slot_config | 本消费者及档位的 Stage 投影、prompt、Contract 和规则的具体映射指纹；从共同 config_bundle 解析并核验，六格可以各不相同。此字段不参加共同 site 相等，但每次调用仍精确核对 |
| provider / model / protocol / sampling / auth_mode | 固定 `openai / gpt-6.1-sol / prompt_only / provider_default / chatgpt_subscription`，包含请求模型身份与实际回显身份的核验依据 |
| temperature / top_p / stage / level | 首批两采样参数均为 None；消费者 boundary/value/read 和显式 low/high 分别绑定，不能借另一格通过 |

原型把复合现场身份当不透明字符串，演示其精确相等和失效，不实现现场重采样或以上指纹构造。生产接收必须验证这些组成存在且来源可信，再构造绑定；不能接收用户随意填的 `host`、`config_bundle` 作为事实。首次激活及任何共同现场身份改变后都需同一完整现场绑定的六格证据。已激活旧现场也不能让新现场只激活一格；切换完整现场会取消旧 active 集合。未验支持范围继续阻断。

## 生命周期与重验依赖

接收逐项要求 cwd/祖先、文件隔离、主机出站/DNS/IPv6、core、RPC 实际模型/参数、模型/刷新独立计数、session 完整写历史、attempt 终态文件及目录删除、外部中断/真实超时/供应商错误的独立观察。本原型只用集合表示完整合成案例覆盖，不声称这些现场要求已测。

1. `receive` 验证受信来源、完整性、批准计划、覆盖、模型元组与完成时间，产生 pending 身份；不得由接收触发调用或刷新。
2. 所有者审阅脱敏回执，经独立显式操作激活对应 receipt；初次或换现场必须齐备六格。同现场已有完整支持覆盖后，可以针对重验格逐项激活。
3. 有效期严格从验证完成时间起 30 天；到期时刻拒绝新调用。晚激活、重复激活、提前重验失败均不续期。拒绝未来完成时间和无时区时钟。
4. 每次调用重新核验完整绑定和现场条件；绑定漂移或当前条件失败立即阻断并保守撤销全部六格旧事实。即使随后现场恢复，旧通过也不能复活。
5. 外部观察到失败或漂移调用 `invalidate`；明确关联到单格的供应商失败只撤销受影响格。影响未知传 None，扩大为六格；旧完成时间早于或等于失败时刻的回执不能重新接收。重验完成在失败后，仍需独立人工激活。

依赖候选：host/kernel/cwd/core/启动/隔离/共享观测器改变影响全部六格；某个 stage 的 prompt/Contract 或其 RPC 路径改变至少重验该 stage 两档（若 config_bundle 变动，原型保守要求六格）；供应商某格实测失败先撤销该格并检查共用模型/端点影响，不能自动认定其他格无影响；刷新/订阅/端点变化影响共用认证的全部六格。只有接收权威有明确证据证明其他格不依赖变化时才准复用，否则扩围。原型不自动推断依赖图，完整产品须固化依赖表并保存具体影响判定。无论重验范围多小，调用预算与停止规则都须重新冻结并经 H2 批准。

## 本次验证

独立未绑定 `tests/test_issue167_lifecycle.py`：29 个节点，`uv run --offline --locked pytest -q tests/test_issue167_lifecycle.py` 返回 0，29 passed。定向 Ruff check/format 和 mypy 两文件通过。不运行完整离线门禁，不扩大既有验收组、required 集合或历史分母。

覆盖拒绝路径：字典/布尔伪证、来源、完整性、计划、覆盖缺项、未人工激活、首次六格不齐、换现场单格激活、逐字段漂移、当前条件失败并撤销、验证完成日起硬到期、未来/无时区时间、提前重验失败撤销旧通过、针对性重验仍需激活、未知影响扩围。异构六格配置共用清单的正例通过；六格与两档不互借。所有样本均为合成哨兵。

## 仍需 HITL 与后续产品工程

H1/H2 先审阅实际 collector/service 权限与完整现场计划，H3 才能采集真实观察；不能以原型 CHECKS 集合或签名自证现场 passed。H5 审阅最终证据和后续接收工程；产品激活独立于实验接收/闭票。本次不生成可供产品导入的通过回执，也不提供真实资料外发、正式校准或无人值守许可。

产品须补：受保护的 receiver/collector 身份供给和撤销、批准计划的逐案例约束、观察连续性与安全元数据解析、完整绑定构造、持久化状态机与事务审计、抗时钟回退/状态回滚、每次调用入口的现场复核及失败持久撤销、继承依赖的重验决策、人工激活权限和备份恢复后的重新准入。未补齐前维持原闸门。
