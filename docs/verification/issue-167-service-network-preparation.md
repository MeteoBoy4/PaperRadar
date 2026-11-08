# #167：项目服务网络包的离线验证与待审身份

本次在 [v3 无网络现场通过并恢复](issue-167-resolver-window-v3-result.md)后继续 A4/A6 准备。只生成新源码、纯 mock/临时目录测试和待审包；没有新网络动作、root、服务安装/启动、规则加载、Node/Pi、凭据读取或崩溃。新包须另获 H1/H2/H3 单次授权，不复用历史余额。

## 待审包及范围

`.scratch/issue-167/h1-service-network-v1/`，run=`f287c9ad630e`。完整影响与预算以包内 owner-review.md、plan.json、unit/规则/全部源码为审阅对象；[过程计划](../../intent/review/issue-167/service-network-plan-v1.md)记录顺序与后继边界。

| 材料 | SHA256 |
| --- | --- |
| review-seal.json | `292ee4f3bbdda1cd216eeaaf157e1c338074163b9ca37f7b7ebe93a9918e989d` |
| core manifest | `336e927f59eab59a2568017e2d3f8bb771ba271d197326f7c05d9f053ef097cd` |
| driver | `6961d7be4eb3dc9f6e3da0767e4f4e9f11d6b7cd9de0a54fe4d0560131f53107` |

仅一个具名 unit `paperradar-167-h1net-f287c9ad630e.service` 和独占 inet 表 `paperradar167_f287c9ad630e`，受保护代码 `/home/paperradar-probes/issue167-f287c9ad630e`、runtime `/run/paperradar-issue167-f287c9ad630e`、永久记录 `/var/lib/paperradar/probe-runs/issue167-f287c9ad630e.json`。固定 cwd、UID/GID1000、cap 空、NNP/seccomp、Delegate=no、零 core、SocketBindDeny=any 保留；新 worker 仅 AF_INET，systemd 地址层只允许既定 pool/router。resolver 文件仅绑定到该服务视图，不改全机文件。

初始 deny 下分别由 gate 放行一次 router:53 TCP connect（无 DNS payload）、一次 api UDP A；每个 socket 已关闭且 worker 静默后，由 owner 独立核完整规则/绑定，要求 allowed 不增、rejected 增。两项均符合才激活既定允许集合并执行 api UDP A/TCP A/TLS、auth UDP A/TCP A/TLS。单项失败/unknown 即停止，无重试或退款。

总上限：DNS5（UDP3/TCP2）、UDP send3、router TCP 连接尝试3、TLS TCP 连接/握手各2；HTTP、认证 CLI、模型 prompt、Node/Pi、IPv6 探测及崩溃均0。deny UDP 若规则失效可能实际到 router，已包含在5次查询预算内。上限指有界操作/连接尝试，不将内核重传或 packet counter 当成 DNS/HTTP 次数。

显式 Python collector 沿用原严格 DNS、CA、SNI/hostname 与 TTL 检查。新增 TLS 调用开始/返回后的单调时间戳，其区间保守包含 CA 核验、TCP、握手及 close；两个时刻均须在该域名同轮两份 DNS 的最早 TTL 截止前。不是精确握手内部瞬间的测量。组件的原 scope/OS_ACL_assessed=false 保留；服务规则与代表性流量由新 owner 单列，不改组件摘要自证。

## 实现和离线边界

新增 `issue167_service_network_{case,worker,owner,bundle}.py` 四个探索脚本。新 Case/result/envelope 使用独立网络语义；旧零网络 Case 不接收新 Case，原字段及默认行为保留。原 `issue167_resolver_case.verify_installation` 仅增加可选 case_loader 接缝，默认仍为旧 load_case。

复用 v3 的安装/归属核对、永久预占、独立 cgroup binding、完整规则 verifier、持久化 resolver 基线、恢复子阶段和清理顺序。新 owner 对每次快照同时要求 counter 单调，deny 时 allowed 不增、active 时 rejected 不增；另要求每个拒绝及正例具有独立的必要增量。它包括正例之后和 post_stop 的窗口，不只看中途摘要。

入口是安全验证所有 root-owned 成员后才导入模块的 stdlib entry，复用单 sudo 字面 bootstrap；不以 root 导入工作区源码。所需外部配置声明是显式 `--owner-config-confirmed`，缺失时在预占和 sudo 前拒绝；flag 不证明路由配置或执行授权。所有者须审批时确认冻结配置仍适用，运行时只有 sudo TTY 读取密码。

旧已执行包、原 unknown、永久记录、历史固定登记、产品策略与协议不修改。无新 loader、无内层 TCP53 放宽。API/auth 共享池的 ACL 不证明两类目标分离；不核验上游映射或主张出口身份。可信 Python 的显式 DNS 不证明 Node 默认 lookup、模型 Landlock 网络或实际 Pi 兼容。IPv6 保留 not_assessed。

## 验证

命令统一使用 `UV_CACHE_DIR=/tmp/issue167-observation-uv uv run --offline --locked …`。

- 新独立未绑定 D1：`tests/test_issue167_service_network.py`33项，`tests/test_issue167_service_network_bundle.py`3项，共36项通过。关键负例包括额外原始字段/错误计数口径、close 失败、末窗口 counter 异常、bool TTL、缺时间戳/过期、各阶段失败不继续、拒绝/正例缺独立 packet 增量。关闭失败和 bool TTL 等反例均先复现拒绝缺失再修复，不靠现场试错。
- 新36项与原 DNS54、service_egress50、auto_bootstrap8、FIFO1 的组合 **149 passed**。旧 resolver owner49/worker18/bundle4/restore16/recovery9 组合另为 **96 passed**，验证默认接缝兼容；不把两次命令写成单次结果。
- 涉及的7个Python文件 mypy、Ruff check/format 通过。fresh 独立审阅核对全部33个 core 成员、映射源码、两份 entry 重渲染、unit、seal/core/driver；results 为空。
- bash -n 通过。仅将安装前缀替换为现有包路径的 `/tmp` unit 语法副本，在默认工具沙箱内被本地 socket 选项限制而退出1；随后同一普通用户宿主 `systemd-analyze verify --man=no` 退出0、无 stderr。没有安装或执行原 unit，实际安装后仍须原字节检查。
- 新 unit 文件、cgroup、代码、runtime、永久记录精确路径均 absent；未为此追加 root nft 查询。文档链接、diff 和最终固定 scope 含 collect 审计随本轮回记。

这些是准备和离线验证，不是现场网络结果，不进入历史分母/required/正式回执。内部配置、进程/内核细节、回执及相关哈希只留本地。未运行完整离线门禁；真实凭据、认证/模型、供应商能力/故障、H5 与产品激活仍须各自后继步骤。
