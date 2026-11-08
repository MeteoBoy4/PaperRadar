# #167 T1：双向过滤无凭据合成待审包

## 选择与边界

所有者已[裁决K2/T1](../../intent/review/issue-167/post-e01-h4-fault-scope.md)：不另备E02，直接注入实际Pi保持not_assessed、合成KI回归保留；先准备项目INPUT+OUTPUT机制的无凭据正负对照。本包是该前置，不是实际Pi300秒、自然供应商迟延/错误或产品准入证据。准备授权不包含现场执行。

canonical `.scratch/issue-167/h1-duplex-synthetic-v1/`，run=`a73d9c02e651`，尚未预占、未执行，results仅offline-validation.json。

| 材料 | SHA256 |
| --- | --- |
| review-seal.json | `2ea3df160bc9c06c7f224b5bb3c48698c3f6ea923d30307886a8cb7779f1ec21` |
| outer manifest.json | `ae332e1ce6d43d4e914ecfac3ac62ff5c4d883f58f478da2c23974e931decae1` |
| owner-wizard.sh | `3d7b798f640ed0c3433551d32e06a3b292a16398995bd1c5d703f9f7e57a351c` |
| installed-manifest.json | `dbf76a59a0916a99e1d5f1c4b23ace90035365c9c43d9a242a4c811ae0b2069a` |

## 新H1动作与预算

仅本unit `paperradar-167-h1net-a73d9c02e651.service`、唯一inet表 `paperradar167_a73d9c02e651`，代码 `/home/paperradar-probes/issue167-a73d9c02e651`、runtime `/run/paperradar-issue167-a73d9c02e651`与永久单次记录。root动作由所有者审阅执行；一份UID1000 client unit、一份owned UID1000 peer进程（CG外）及各自有限生命周期。

peer只监听127.0.0.1:46167，并在同一selectors进程内发起CG外control到自身listener。主+control共active connect上限2、accept2、应用send上限12（预期10），无应用重试、端口fallback或旧余额继承。端口忙、未知连接、归属不明即unknown，不杀其它进程或换端口试到成功。TCP自动重传为传输层未知，不算应用重发，也不拿packet当请求数。

本轮Pi/Node、认证/刷新/模型、凭据/cache、真实业务DB、安装锁、外部DNS/TLS均0。不会访问原认证目录，不需要读取新expires。worker75秒、service90秒、owner180秒、命令各8秒；负观察共同绝对gate预算1500ms，实际两端在B发送后须具至少1秒有效持续观察，晚到/不足unknown，不延长/重试。

## 受控实验与数据面判据

1. 初始client ready不联网；先独立取得live CG dev/inode、创建deny表并捕获完整binding，再单事务进入allow。主连接双向A必须到达、尾buffer为空；CG外同UIDcontrol也双向成功。
2. 单一nft批次同时flush并重建INPUT/OUTPUT两个phase链到stall。独立完整核表通过后才发stall gate，两端各send唯一B一次，继续有界recv；负观察新增主payload字节必须0、B未到、无尾buffer/早EOF。两方向drop packet/byte各须增加，不能只timeout自称阻断。
3. stall窗口CG外同UIDcontrol再次双向成功，支持本例按CG而非UID隔离，不扩为全宿主所有应用资格。
4. 负观察完成后进入resume_pending仍持续pump。再单事务allow，原B到达且不做应用重发；记录切换意图与接收时点，切换前到达/无引用仍unknown。control第三轮双向成功。实验resume是恢复正对照，不是最终host回收，不能用它容忍最终late packet。
5. Root只有在双方resumed完整后才授权close；等待close一端先收到FIN时须重核同run有效close授权，数据阶段早EOF仍unknown。所有连接关闭、client严格退出、CG空及owned peer回收后，才按完整规则/身份及post_stop计数稳定撤表、卸unit/reload、删除两树，保留永久记录。

IPv4 loopback高端口不是未来fake-IP/TCP443、外部TLS、Pi请求或供应商流的实测。即使机制通过，后续真实T1仍另冻规则/输入/条件认证计划并新批H1/H2/H3，最多1 CLI＋1 prompt/model。真实300秒从public factory前开始，不从DROP重置；提前完成/早期错误/缓冲未触发不补跑、不加任务、不退款。

## 规则身份、事务与失败恢复

新模块仅纯render/parse/verify，旧OUTPUT不登记为INPUT覆盖。两个hook只匹配精确project socket/cgroup，再匹配127.0.0.1与固定TCP端口；其他流量policy accept。六方向packet/bytes计数分别为allowed_in/out、dropped_in/out、unexpected_in/out，故意DROP与异常拒绝独立。

独立CG身份及13个常驻table/chain/counter/scope handle绑定；phase动态rule handle每个已声明事务后重新捕获，引用严格deny0→allow1→stall2→allow3，sequence及predecessor摘要完整。半边切换、缺/多/错规则、跨阶段漂移、错CG数字、计数回退或unexpected均unknown。最终packet与byte六计数全部不增才quiescent；late packet、恢复失败或未知归属保留本表/单元/树与unknown，所有者仅恢复，不为删表降低判据。

Linux v7.0官方nf_tables_api.c及本地matching header用于确认handle命名空间：chain/rule/named counter共享table.hgenerator，联合去重；table自身来自独立table_handle，不盲拒数值重合。这只是[上游源码静态依据](https://raw.githubusercontent.com/torvalds/linux/v7.0/net/netfilter/nf_tables_api.c)，不是INPUT或事务切换现场通过。

Root读取普通及failure role元数据均从/逐层FD固定、核本次创建的runtime/worker/role inode及最终FD身份后完整有界读取；短读、尾部垃圾、重复键/NaN/Inf及别名拒绝。角色写入也从固定目录FD，不向外部路径回落。收尾PinnedArtifactTree先核封闭名字再stat/descend，根parent FD相对rmdir，两树全验后才删；不递归扫描未知目录后把它纳入expected。

关闭peer/描述符等最终收尾后才写永久结果；未知异常仅闭合原因、不调用任意__str__或存payload。部分安装/归属/删除失败可能留材料，单次预占不退款、不重启清余额。本包不保证所有失败自动清空。

## 材料和离线验证

新scope共7个core文件（5个标准库脚本、worker entry、unit）；scope.json另加入部署共8，Root派生installed manifest，外层审10成员（部署8＋installed manifest＋review），无自hash循环。不改旧通用40上限或旧执行包。Root字面stdin核真实bytes再载闭包，不Root import可写应用；worker entry只closed sources与系统Python-I-S-B，无workspace fallback。

三个独立未绑定D1：filter45、probe42、bundle24，合计 **111 passed**。已取得原stub红、phase规则与handle冲突红例、真实runner/fault阶段、Rootreader祖先/短读、真实byte/min观察/close竞态、命令前phase/gate拒绝及实际/tmp两树收尾反例；此前110项检查点不当最终计数。六文件mypy（MYPYPATH=src）、Ruff check/format通过。

完整无padding FakeOps结果43358bytes，含7份完整kernel fixture及全部phase引用，已实际LOCAL_RESULT往返保全，小于原131072限制；另测精确边界及metadata别名/非法JSON/类型/身份矛盾。Root实际literal仅移唯一owner_main：5模块加载、main0/主动操作0/fallback0。worker实际entry只替唯一main调用，原保护/hash/闭包检查执行，明确synthetic固定prefix/UID适配；5模块、10个sealed/python读取、main0/主动操作0/fallback0，不证明真实Root权限。

bash-n通过；普通宿主用户只读exact probe.service的systemd-analyze verify退出0、无输出，未安装/启动。最终fresh独立111项通过并核当前seal/全部源字节、两manifest、closure/规则、entry、完整driver/reader和无preclaim，无剩余确定材料阻断，可交H1。实际INPUT效果及selectors网络行为仍未测；本材料本身不授执行许可。

本轮没有真实socket、连接发送、nft操作、服务或root执行，没有读取凭据/缓存内容、进程环境、日志/core或私有ledger。公开工具/source/host metadata只读用于准备。链接/diff及固定scope含collect审计随本次收口记录；新D1不扩历史分母/required/正式回执，未运行完整离线门禁，保留合成KI回归未重复已有SIGINT/300秒控制。旧unknown、H5草稿状态及普通产品阻断保持；内部配置/metadata/绑定/回执及相关SHA仅留本地。

获具体H1批准后，所有者入口为 `bash .scratch/issue-167/h1-duplex-synthetic-v1/owner-wizard.sh --owner-duplex-synthetic-confirmed`，只输入一次sudo TTY密码。当前选择仅为无凭据机制，真实T1不继承此许可；自然供应商迟延/真实供应商错误不得由本合成结果登记通过。
