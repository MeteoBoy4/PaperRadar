# #167：真实出口终局冻结与前置元数据待审包

本轮执行所有者 H4 真实出口终局的冻结工作。地址和路由器行为的来源为所有者实测陈述，agent 没有重测；当前 DNS/TLS、认证/模型、Node/Pi 执行和配置变更授权仍未授予。历史准备/现场证据保持原字节，不回写通过。

## 已接受的冻结范围

[ADR-0050](../adr/0050-bind-egress-to-owner-visible-addresses.md) 记录本机部署范围，规格 §7.7 与路线图同步；原 Landlock 策略、产品启动/协议身份、core/计数终局和产品接收权威均不变。原 A/B 比较标明已选 A，不再要求重复裁决。

| 来源事实 | 冻结值 |
| --- | --- |
| 上联软路由 / 软件 | 192.168.44.1 / OpenClash |
| 模式 / sniffer.override-destination | fake-ip / true |
| 路由器原配置池 / 规范允许池 | 28.0.0.1/8 / 28.0.0.0/8 |
| 应用可见允许集合 | TCP443至整个28.0.0.0/8；UDP/TCP53仅至192.168.44.1 |
| owner报告的当前A基线 | api.openai.com→28.0.5.94；auth.openai.com→28.0.5.167；TTL未提供 |
| LAN DNS行为 / 转发TCP行为 | TCP/UDP53劫持到路由器；转发TCP redirect至Clash7892 |
| TLS条件 | 所有者实测无TLS中间人；本机未独立重测 |
| IPv6 | not_assessed，本轮探测预算0 |

两个当前映射不是允许白名单，不能换成实际供应端 IP。router7892 也不是新增本机允许目标。上游决定线路与最终 IP，本机不核验其映射，不主张出口身份；池 ACL 不能单独证明域名或 API/Auth 目标隔离。v5 原 UDP53拒绝和 IPv6创建负例属于其旧合成绑定，不迁移为本轮允许集合的实测结论。

原池字符串与规范 CIDR 同时冻结。发现池或适用配置变化即停；DNS答案仍在池内不等于配置未变。当前没有自动读取路由器配置的权限或机制，下一轮必须通过外部授权转录所有者对冻结配置仍适用的确认；软件flag不是确认权威。证据措辞按本轮规定检查，旧已发布快照不为措辞变化重写。

## 已冻结的候选 DNS/TLS 预算

机器计划 [real-exit-plan-v1.json](../../intent/review/issue-167/real-exit-plan-v1.json)，说明 [real-exit-dns-tls-v1.md](../../intent/review/issue-167/real-exit-dns-tls-v1.md)。这是普通用户、无配置变更的前置元数据轮，不安装或验收 OS ACL，不占用真实认证或模型预算。

固定两域名 api.openai.com/auth.openai.com，各显式 UDP A1次、TCP A1次至192.168.44.1:53，随后各一次TCP443连接及TLS握手；合计 **DNS4（UDP2/TCP2）＋TLS2，HTTP0、auth CLI0、model prompt0**。查询后立即检查对应域名TLS，减少TTL等待；TLS只用同轮UDP/TCP一致的唯一池内A地址，固定SNI、hostname/chain校验，不调用系统resolver、无备用地址、隐式查询、fallback或重试。

DNS按nonce/question/source/A-IN/NOERROR及长度闭集核对；截断、多A、CNAME、池外地址、TTL0、UDP/TCP不一致、需要新查询或任何unknown均停止。TLS开始及结束都早于两份DNS快照最早TTL截止。只加载SHA冻结的公共系统CA bundle，不读取环境CA覆盖、client certificate/private key；不保存DNS原文、证书正文、headers/body、异常原文或完整流。

collector入口45s绝对deadline覆盖加载/预占和操作，最终化最多10s且不超过入口55s；Python文件I/O/close前后检查不提供硬中断保证。启动器用白名单环境（仅PATH/LANG）、Python -I/-S/-B，在uv外层管理下让timeout直接监督唯一collector进程55s，并给TERM后最多1s的KILL宽限。collector不创建子进程，不依赖uv转发信号；不扩大成任意后代回收保证。外层只读自检及结果整合不计作网络操作，不能声称全部本地文件I/O都被硬中断。

## 具体待审包与接收边界

`.scratch/issue-167/real-exit-metadata-v1/`，先读 owner-review.md、plan-review.md、manifest.json 和 run-probe.sh。当前 results 目录为空，没有预占或真实探针记录。

| 身份 | SHA256 |
| --- | --- |
| review-seal.json | `e21cdcec3fbddf969aadbbf354a2e15b6efe87b1ee094347dc15a24ada5a2220` |
| core manifest | `3a0c207a684721bb9ff0c809363fb633531930b823fc797c825b857c5a953838` |
| plan.json | `adf2fc72a20d11fabbe0de0265cdd85c3bcbf7973931c51802b3669528846a4c` |
| driver | `895dd60933405020895eed6f5f5fa77c09e7fb14c64282aa49b9aeb2f86eae0a` |

6个core成员及工具/Python/boot/kernel/host、公共CA身份都被核对；白名单环境也排除自定义OpenSSL配置/实现入口。collector从已验证内存字节compile/exec，不import工作区模块。默认入口只打印说明；显式参数不能自证外部批准。批准并确认配置适用后可由agent以同一普通用户执行，不用sudo；本轮尚未执行。

两层本地O_EXCL预占在操作前保留，任何未知/失败不自动再试或退款；普通用户状态不声称抗恶意删除/回滚，外部单次授权与本票历史继续约束。接收须同时满足进程退出0、collector摘要与文件一致、完整六步/计数/计划绑定及cleanup通过。超时/非零、缺文件、清理未知或格式/绑定不符一律unknown，不能只看中途result.json。结果写launcher-result.json；操作计数表示进入有界操作，不冒充网络发送次数或供应商请求总数。

## 离线实现与审阅反馈

新增独立工具 `scripts/issue167_dns_tls.py`，只导入标准库，导入/帮助不联网，拒绝root。新增未绑定D1 `tests/test_issue167_dns_tls.py` **54 passed**，仅mock/fixture；覆盖实际计划加载、重算SHA后的语义漂移、DNS压缩/恶意格式、固定router来源、单A/TTL、无隐式解析或fallback、TLS固定地址/SNI/CA同字节加载、操作及最终化截止、关闭失败/中断、预占不重跑与默认/帮助无网络。未改产品CLI/策略或已有测试登记。

准备期fresh审阅还用纯临时JSON复现包装器跟随result symlink并错误接收的回归。已改成dirfd、O_NOFOLLOW/O_NONBLOCK、有界regular/UID/nlink1/0600及前后stat稳定读取；预占前拒绝5个固定状态路径的任何既有成员，失败不读取指向目标。修后11个实际finalizer片段用例通过，含symlink/FIFO/hardlink/错权限、超时/非零和过计数。只用了合成fixture，未读真实凭据。此一次性包装验证不计入历史分母。

本机timeout为uutils0.8。帮助与普通完成/TERM超时、KILL样本只针对自建无秘密子进程，未做网络；带shell后代的样本不能支持任意组保证，因此将uv移至监督器外，改用单Python collector形状，并以直接单进程忽略TERM的样本验证KILL退出。启动器3个嵌入Python块语法及bash -n通过；纯读取前缀（明确截断在预占前）宿主只读通过，没有运行完整入口。

两文件Ruff check/format、mypy通过；CLI兼容组合59 passed/退出0。冻结JSON的CIDR/端口/来源/授权状态/预算和新证据措辞检查通过。最终独立封印审阅、文档链接/diff与固定scope含collect审计结果随本轮回记；不扩required、历史覆盖/分母或产品证据。

没有本轮DNS/TLS/HTTP、认证/模型、Node/Pi、root、路由器或宿主配置变更。当前仅冻结决定并准备单独授权包；真实认证宿主、服务/cgroup网络规则、完整文件窗口、模型/能力/H5和产品激活等仍保留，Live/B状态不变，#167不自动关闭。
