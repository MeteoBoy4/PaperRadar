# #167：获批的前置 DNS/TLS 元数据结果

本轮承接[冻结与待审包](issue-167-exit-freeze.md)。所有者在绑定最终封印、明确单次预算和配置适用性确认的请求后回复「批准」；agent据此仅执行一次普通用户网络元数据轮。没有重试、后续查询或新增预算；内部网络细节仅保留本地，未提交或上传。

## 授权与实际执行

审阅包 `.scratch/issue-167/real-exit-metadata-v1/`，review-seal SHA256=`e21cdcec3fbddf969aadbbf354a2e15b6efe87b1ee094347dc15a24ada5a2220`。执行前重新核对core/driver/6成员及空results，均匹配。唯一执行入口为已审run-probe.sh及两个显式执行/配置确认参数；以同一普通用户在工具沙箱外运行，没有sudo或root。

启动器退出0、result=observed_expected、no_retry=true；collector自身摘要也为observed_expected，cleanup_complete=true。collector stdout、result.json与launcher.collector三个JSON值完全相等；launcher要求退出0、计划绑定及完整六步的接收条件均满足。

| 角色 | UDP A | TCP A | TLS |
| --- | --- | --- | --- |
| api | 28.0.5.94，TTL1 | 28.0.5.94，TTL1 | TLSv1.3，chain/hostname检查true |
| auth | 28.0.5.167，TTL1 | 28.0.5.167，TTL1 | TLSv1.3，chain/hostname检查true |

DNS目的均为冻结resolver，TLS地址来自同轮一致且落在冻结池内的A快照，SNI为各自固定域名。当前两个值与owner报告基线一致；不将它们提升为唯一允许集合，仍沿用ADR-0050的整个应用可见池与router DNS范围。上游配置/无TLS中间人的来源仍为所有者陈述，本机没有独立检查路由器配置或映射，不主张出口身份。

实际记录 **4个DNS操作、2个TLS操作**，序号1–6且每步observed。这里是进入受控操作的计数，不是独立wire统计。受审程序没有HTTP发送、auth CLI、model prompt、Node/Pi或配置操作，相应显式计数0；没有IPv6探测，保持not_assessed。此次结果不提供OS ACL、项目service/cgroup隔离或模型资格。

## TTL窗口与证明限制

四个DNS答案TTL均1秒。封印源码在TLS开始前、操作返回后以及各项绝对截止处核对同一单调时钟与两份DNS快照的最早失效点；通过摘要表明该程序接受了两次握手的窗口。

回执保留DNS接收时刻及TLS对应expiry，但没有TLS完成时间戳。因此不能独立重放具体完成毫秒、补造该时间，也不能从当前已完成结果继续沿用其TTL。后续任何采用解析地址快照的请求都须取得其自身有效窗口；已过期的本轮快照不充当仍有效的地址依据。ADR-0050固定池的范围不因此被换成短寿命的两个精确地址。

普通Python与冻结公共CA的TLS成功不等于固定Node/Pi、其TLS信任、实际DNS路径或生产模型边界通过；collector仍明确OS_ACL_assessed=false、router_configuration_independently_verified=false、exit_identity_claim=false。本轮也不证明隐藏HTTP/刷新次数、供应商模型能力或产品准入。

## 回执完整性与保留

launcher-result.json SHA256=`cbf439bd363762ba8e3fa053f6a3d4ef25dde64395b14c8b4826a2984339815f`。主代理使用nofollow/nonblock/有界regular读取，核对以下五个既有状态文件均当前普通用户所有、0600、nlink1，并核对JSON一致性/计划绑定、预算和完整序号：

- launcher-started.json、execution-started.json；
- collector-output.json、result.json、launcher-result.json。

只读复核另存results/post-run-readonly.json，不再触发入口或网络。两层预占与全部回执保留，视本次许可已经消费，不删除、退款或通过换目录自行再跑；普通用户状态仍不声称抗恶意回滚。进程成功退出与cleanup摘要来自已审单collector监督链，不外推任意后代回收。

fresh subagent只读独立核对了最终封印、6成员、工作区源码、两预占、五状态元数据及三份结果的一致性，未发现必须修复项；没有新网络或测试。没有保留DNS原文、证书正文、headers/body/token、外部异常原文或完整网络流。

## 后继前置

本轮预算止于该前置元数据检查。下一步只可AFK准备ADR-0050允许集合的项目service/cgroup接线、真实父子链及完整文件观察窗口；安装/运行、真实Node/Pi、认证/模型等仍须新的具体授权，不拿本轮成功或旧余额扩范围。

现有模型IsolationBoundary源码的TCP端口规则仅放443及显式proxy_port，本轮没有套用该边界；因此普通用户TCP DNS成功不能迁移成模型侧TCP53可用。后续须逐层验证实际路径，既不能悄悄增加内层端口/改隔离身份，也不能将外层允许集合当作所有内层能力均已实现。该静态差异不把已经获批并完成的本次普通用户检查改为失败。

真实认证宿主、同uid进程边界、Pi全窗口文件事实、模型/参数/故障能力与H5等各自前置保持，read_evidence=None仍阻断；Live/B状态不变，本票不自动关闭或激活。

## 本轮检查

没有修改Python或产品代码，没有重跑54项mock或59项兼容组合；其结果仍是上一份准备证据的离线结论。本轮新增验证为已授权的一次真实网络检查、预执行封印/空状态核对、受控回执完整性和fresh只读复核。文档链接/diff与最终固定scope含collect审计结果随本轮回记；不扩历史分母、required或正式回执，未运行完整离线门禁。
