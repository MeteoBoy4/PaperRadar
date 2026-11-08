# #167 A2/A3：离线观测原型证据

本次证据仅对应 `scripts/issue167_observation.py` 与独立未绑定测试
`tests/test_issue167_observation.py`。不修改产品接缝、现状 Contract、历史 EXP-2
或固定验收登记。没有运行 Pi、读取认证内容、联网、提权或修改宿主策略。

## A2：三个独立事实

原型只在合成临时目录建立 Linux inotify 描述符，监视启动前已有的目录。
不读取文件内容；解析事件头后跳过名字字节，不保存文件名或完整路径。
`snapshot_terminal()` 必须在声明全部后代回收之后、cleanup 之前显式调用。
快照记录每一成员的类型与本轮随机密钥 HMAC 相对路径 ID，不输出路径原文、内容或密钥；
同一路径在不同 observer 的 ID 不同，不能跨轮关联。ID 与认证完全无关。
在可信合成驱动声明全部后代回收后，snapshot 同时冻结运行窗口的变更数与历史原因；
后续 cleanup 的事件丢失单列 `cleanup_reasons`，不会回写已结束的运行历史。运行中
IN_IGNORED/overflow 等仍令历史 unknown，不能由 snapshot 修复。该声明未接入真实
cgroup，不是现场后代清空证明。
`receipt()` 独立检查目录删除并保留之前快照；没有显式快照时 terminal_unknown、成员与
计数为 None，不能用删除后的空目录代替终态为空。回执另含变更事件数与闭集原因。

| 独立主张 | 实测/合成方法与结论 | 限制与后继条件 |
| --- | --- | --- |
| 终态文件集合 | 子进程创建并删除合成哨兵，显式快照普通文件数为零；另例保留 settings，删除目录后快照仍含原成员 | 每项类型和随机 HMAC ID；无快照为 terminal_unknown，不能跨轮关联路径 |
| 目录删除 | 完整窗口 snapshot 后删除空目录，回执 directory_deleted=true 且历史 zero_observed；运行中先删目录仍 unknown | cleanup 引起 watch 结束单列原因；删除本身不能外推历史零写入 |
| 全运行写入历史 | 在启动前装 watch，真实 Python 后代创建/写入/删除文件，仍记录 observed_mutation | kernel 事件与写调用数不是一一对应；不证明写入进程身份，不计精确写次数 |
| 无变更合成窗口 | 显式开始、显式声明所有后代回收后零事件，返回 zero_observed | 仅限选定树和声明窗口；未与 cgroup/启动器接线，不是 session 历史零写入证明 |
| 新子目录竞态 | 创建新目录后立即写文件，返回 new_directory_race/unknown | 没有用事后递归补 watch 冒充无缝覆盖；现场须预建并冻结目录拓扑，或 H1 审阅更强内核观测方案 |
| 事件丢失/窗口不足 | 注入 IN_Q_OVERFLOW、截断事件，遗漏回收声明，均 unknown | 真正 queue overflow 压力测试未做；合成解码负例不证明部署不会丢事件 |
| 根路径替换 | 删除根并替换为 symlink，拒绝扫描目标并返回 unknown | 任意现场路径竞态仍需 inode/cgroup/挂载边界绑定 |

零观察不等于零行为。inotify 仅覆盖选择的树，无法证明树外写入、原已打开的 fd、
所有挂载别名、mmap 写入或被内核合并的事件。运行窗口内收到 IN_IGNORED/UNMOUNT/MOVE_SELF
均丢失覆盖；扫描错误、已有 symlink、关闭后取回执均 unknown。原型不能证明
整个进程组已清空；`descendants_reaped()` 是合成驱动声明，产品应从可信 cgroup
控制器获得事实，并在启动前至所有后代退出后保持同一观察窗口。终态目录删除
与关闭窗口的顺序须分别取样和签收。全运行 session 历史目前仍 not_assessed。

## A3：分层计数与独立参照

RequestLedger 只接受受控 layer、phase、正整数 sequence；没有接受 URL、headers、
body、token、token 派生值或任意文本的字段。合成对端驱动产生元数据，由独立给定的
各层预期数量进行 reconciliation。每层序列单独递增；重复、缺号、预期不符、
缺参照、未观测层和观察失败均返回 unknown，不从其他层补数。

合成例明确构造：1 prompt、1 CLI、1 TLS connection、4 packet、3 model HTTP
（foreground/warmup/retry 各 1）、1 WebSocket connect、1 WebSocket response.create 及 1 auth refresh HTTP，验证彼此不可互换。
这不是网络对端/TLS 解密器，也没有接入 Pi 的真实 SDK；其通过仅证明元数据模型
及拒绝规则可以独立保留各层事实。独立参照缺失时无法识别未发出观测事件的请求。

| 层 | 现场可采用的接缝候选 | 尚未解决的证据缺口 |
| --- | --- | --- |
| prompt | PaperRadar 受控 RPC dispatch 前的次数及案例关联 | 不能据此推算供应商 HTTP |
| CLI | 固定 auth CLI 的实际 spawn/退出控制点 | 不能据此推算刷新网络次数 |
| TLS connection / packet | 项目专用 cgroup 内核计数，仅输出聚合元数据 | TCP 复用、TLS multiplexing、DNS、IPv6、连接失败和 retransmit 不等于 HTTP；H1 才能部署 |
| model HTTP | 固定 SDK 每次实际 transport dispatch 的无秘密 hook，独立于 prompt 与 retry 配置 | 必须证明所有入口、重试/预热/重定向均穿过 hook；目前未接入，计数 unknown |
| auth refresh HTTP | 宿主固定 auth CLI 的 OAuth transport dispatch hook | refresh 单飞/缓存/重试路径均需覆盖；目前未接入，计数 unknown |

固定安装不可静默修改以加 hook。若固定供给不允许可核验 hook，H4 应在“保持未知并阻断”、
“单独裁决新的观测供给与重新绑定”或“单独裁决代理及隐私成本”之间决定；agent 不能
擅自部署解密代理。单纯 TCP/TLS/packet 计数不足以解决 HTTP 计数问题。原型本身
不证明真实模型身份、计费、订阅额度或参数效力。

## 开发验证

为避开只读的默认 uv 缓存，命令前缀 `UV_CACHE_DIR=/tmp/issue167-observation-uv`；
所有执行仍采用 `uv run --offline --locked …`。

- `pytest -q tests/test_issue167_observation.py`：21 passed，0.18s。
- `ruff check scripts/issue167_observation.py tests/test_issue167_observation.py`：通过。
- `mypy scripts/issue167_observation.py tests/test_issue167_observation.py`：2 source files，通过。

21 项独立 D1 节点仅覆盖本次原型，不进入 A1–A10 历史分母、组回执或正式 Live 准入。
未运行完整离线门禁；现场 H1–H5 仍待各自适用授权和复核。

静态补查发现固定包的另一 openai-codex provider 默认 auto transport 存在 WebSocket 路径；首批 openai 直接走 openai-responses，不能据此断言本次openai使用WS。原型已独立增加 model_ws_connect/model_ws_create 层，不能仅 hook fetch。详细来源与未验见[请求路径表](issue-167-request-paths.md)；WS重连/response.create和SSE fallback须共同覆盖，总模型操作上限保持1，不授予额外WS预算。
