# #183 nft native 与 resources 谱系恢复：独立 D1 台账

本台账只覆盖本轮新增工程控制，不扩充既有组成员或历史分母。公共行为见
[Live 契约](../contracts/live-evidence.md#固定模型采集闭环)。本轮沿用 tdd 的既有公共接缝，
先复现两层 resources 链拒绝、native 输入缺失、独立两 payload 形态不匹配及 selector
comment 丢失被误报临时不可用，再验证修复；不把权限错误或记录程序退出 0 当作 kernel 成功。

| 公共接缝 | 覆盖与保证 | 证明边界 |
| --- | --- | --- |
| `nft_program` / `verify_nft` | 同一 cgroupv2 实际 level/路径；四独立负 counter、池 TLS/路由器 DNS 三允许及剩余 drop；仅完整正确签名的协议依赖作有限等价约简，缺地址/端口、错协议、额外 meta 与 IPv6 拒绝 | 精确固定 native 字节与独立 source-derived JSON/native 字面材料；不是本机 kernel dump |
| `read_nft_snapshot` / `merge_nft_views` | 固定 JSON/native/JSON 与完整 u32 GETGEN 起止一致；实际 table/chain/rule handle、顺序、comment、socket RHS/操作符关联，level 只来自实际 native；缺失/改变的实际结构向观察层保留，矛盾视图拒绝 | 模拟固定 subprocess 接缝；generation 有限宽度，不能数学上排除无界完整回绕；generation 不进入稳定 binding |
| `nft_generation` | 固定只读 GETGEN；内核 sender、本地 port、seq/type/flags、nfgen 低16、完整非零 u32、恰三 attrs、长度/对齐/名字原始 bytes；超时、截断、错来源、duplicate/unknown/flagged attrs、错误消息拒绝 | Linux v7.0 官方源码与匹配本机 UAPI 推导的独立包络；真实 UID1000 EPERM 原包仅为拒绝负例，无权限 positive |
| `LinuxLiveHost.preflight_nft` / `check_nft_namespace` | 首次替换的 history/journal 或旧资源副作用前，root 子进程独立 NET namespace 固定 apply→实际回读→规则校验，再以相同程序宿主 `nft --check`；namespace 相同、提交/回读失败均拒绝；只输出固定 stage reason | pytest 显式替换 unshare、geteuid 与全部 nft I/O，真实 fork 验证阶段顺序；没有运行真实 root 或修改真实 namespace/宿主 nft |
| `LiveDeployment.install(recover=True)` | 至多16层无重复 payload 的完整 resources 链；逐层 canonical journal、phase/pair、封印升级声明、原 history/独立 archive；全部待替换祖先及新包的 plan/collector/epoch/来源无执行史；未知链与祖先执行史拒绝 | 真实受保护模型目录/SQLite；原 schema1→2、schema2 非零额度、失败/stopped/intents、legacy history 与 mode000 观察继续保留 |
| `refresh_once` | 稳定代际下实际 level、selector/comment 丢失、额外 chain/表达式及确认缺表为持久漂移；gen失败/库存矛盾为临时不可用，保留原观察字节与时点；重新打开仍拒绝并核分项撤销 | 合成受保护观察、cgroup/proc 和独立 source-derived 工具视图；不授予现场资格 |

新增未绑定模块逐个计数：

- `tests/test_live_nft_generation.py`：**28 项**。
- `tests/test_live_nft_rules.py`：**21 项**。
- `tests/test_live_nft_recovery.py`：**10 项**。
- `tests/test_live_nft_observation.py`：**8 项**。

共 **67 项**。原 `test_observation_refresh.py` 的工具 fixture 补齐真实输出所需的 chain/rule
身份、native 与 generation 替身，原分类、持久收紧、计数器变化和已确认缺表断言保留；
两个原篡改案例改用具有完整身份的额外实际规则。原源码守卫与 builder 当前向量改为 v15，
另加入 v14 历史字节核对；不减少原断言。admission v15 的显式源码清单为 **76 文件**，
包含两个新增 nft 模块；v1–v14 向量与所有旧 pins 原字节保留，launch v9 不变。
`OBSERVER_MEMBERS` 不添加新路径；manifest.sha256 传递绑定新增模块，root 入口在导入前
核验全体封印成员，旧 runtime 的 observer 身份仍按原成员原字节计算。

独立材料 `live-nft-1.1.6-source-derived.{json,nft}` 明确是源码推导，不是现场采集：
[官方 1.1.6 发布包](https://netfilter.org/projects/nftables/files/nftables-1.1.6.tar.xz)
的 `src/{parser_json,json,socket,datatype,meta,netlink_delinearize,payload}.c` 及
`tests/py/inet/meta.t.json.output`、`payloadmerge.t` 的 golden 支持 JSON 缺 level、native
保留 level、CGID fallback 为字符串，以及本轮固定地址/端口签名的两个协议依赖约简。
完整 443/53 九规则形态由相同路径推导，未冒充上游现成完整组合或本机 kernel positive。
GETGEN 包络来自官方 Linux v7.0 `nf_tables_fill_gen_info` / `nf_tables_getgen` 及本机头；
未宣称已逐字核对发行版 vendor kernel 实现。

无 SQL、migration 或 wire Schema 变更。开发验证包含原 resources schema1→2、业务
metadataSchema/Contract 一致性、builder/生命周期、受保护观察/负对照、全部历史源码向量、
整仓 Ruff/format/mypy（包含 tests/scripts），以及导入/发布接线触发的 compatibility all。
实测命令、数量与结果在树外实施交接记录；这些开发结果不替代完整离线门禁。

本轮不执行 sudo、真实 root 预检、部署/停止、宿主规则修改、凭据读取、认证、模型、出站、
receive 或激活。native 实际 kernel 回读、真实 GETGEN positive、新包恢复和现场模型行为
仍待所有者审阅新字节后验证。原共同 UTC 窗口、owner 网络原文、live-177 累计额度、预占
不退款、unknown 与失败/stopped/intents 的约束不变；默认 SDK/Auth 逻辑没有改动。
