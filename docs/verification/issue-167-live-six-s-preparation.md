# #167：S 六格正常批次待审包与离线验证

所有者已选S并完成认证输入结构声明，[裁定记录](../../intent/review/issue-167/live-six-observation-decision.md)保留来源和边界。本轮只准备与验证代码、合成材料和执行包；没有Pi/Node、认证、刷新、模型、网络、root、服务、真实安装锁或实验库写入。此前blocked源码检查点与已执行证据原字节保留。

## 最终待审身份

包 `.scratch/issue-167/h1-live-six-v1/`，run=`e93f7b82c461`，尚未预占/消费，results为空。先审owner-review.md、全部代码、live-context/runtime绑定、65成员合成材料zip和unit/规则。

| 材料 | SHA256 |
| --- | --- |
| review-seal.json | `65959db33984fe642ce1d52f4eb2edaa1d898b4a9440c7796349d20b0a82d531` |
| core manifest | `84c75ad3e4ed33a8647afcbd8579c1646cd97031e4d59d4e162fdb835dc766d6` |
| driver | `e1c93132b6ac2ae8106602f8ea0bc7fbae17bfd6859631be5671509d820db051` |

仅一个UID/GID1000 unit `paperradar-167-h1net-e93f7b82c461.service`、独占inet表 `paperradar167_e93f7b82c461`，代码 `/home/paperradar-probes/issue167-e93f7b82c461`、runtime `/run/paperradar-issue167-e93f7b82c461`、永久记录 `/var/lib/paperradar/probe-runs/issue167-e93f7b82c461.json`。真实执行仍须新的H1/H2/H3一次批准，S与输入裁定不代替该许可。

## 必须进入最终 H2 的认证事实

来源是所有者只读结构核查：仅openai OAuth，scope含chatgpt.tokens.use.direct，OAuth payload除type鉴别字段为access/refresh/expires/clientId/scopes；无命令型key/额外provider。目录0700/auth.json0600，models.json缺失、models-store空对象（所有者报告2字节/0成员）、compile-cache已有。agent不读取或验证access/refresh值、长度/哈希或派生值，不新增凭据reader。

**expires单位为毫秒。** 所有者报告access已于2026-11-06 18:42过期；未提供时区，本轮不转换或从mtime回填。固定CLI把900s最小有效期转成900000ms后判断刷新。若输入未被别处更新，首CLI计划一次logical refresh并联网，必须作为本轮实际认证操作批准，不能归入离线前置。

计划logical refresh1与独立观测HTTP次数分开；首auth还要求本表allowed packet增量，但不把packet或CLI成功冒充HTTP1。后5个CLI是否再次刷新、redirect/隐藏传输重试仍unknown，model/refresh的HTTP下界0+unknown及Pi报告token权威口径不变。本轮Pi内部DNS/QNAME/fallback的未知范围也须在新H2批准，不从旧无秘密诊断A继承余额或执行权。

刷新开始后有独立持久化轮换token的窗口，父强停仍可能使轮换/写回未知；失败、超时或不确定即停止，不回滚auth.json、不自动重试。认证持久目录的刷新、初始化/catalog、锁和编译缓存写入，与模型临时agent分别登记；认证目录只做权限/类型等metadata前后checkpoint，history not_assessed、persistent_not_deleted，不删除或移动已有缓存。

## S 观察的实际声明范围

预arm root/home/tmp/agent及公开settings文件inode，真实CG只剩controller后才封口；完整终态分类/type/count与独立deleted必须成立。session/guard的声明范围必须完整且session零写；未知路径、缺watch、overflow、跨边界move、alias/special等均unknown阻断。

固定源码支持的auth/model store初始化、三个exact锁目录（auth/models/settings锁）和自身TMPDIR的compile-cache另分类。缓存/锁内部全写史从起点即not_assessed，边界事件仅为inotify记录下界；这不是整个attempt零写或全部缓存写数精确计量，post0也只对应assessed边界。

公共RPC的set_auto_retry/compaction(false)即使已false仍会save/writeFileSync。因此精确control_settings的MODIFY/CLOSE_WRITE另列下界，容许同inode格式重写；公开设置在prearm/封口/删除前checkpoint须与public SETTINGS_JSON键、值、类型严格相同。只读取本次父程序创建的公开非凭据settings，拒绝False/0混同、重复键/NaN/未知字段、inode/mode/nlink/owner/别名变化；不读取store/cache/session内容，不声称解析每次写入中间内容。原RPC命令、初始配置字节、argv/env、LAUNCH/协议身份均不改。

已先红后绿修复真实/tmp反例：seal后移除watch曾可漏掉session写并误报零；现在只有显式删除授权及对应真实DELETE_SELF之后的IGNORED才可作为正常rmtree元数据，其它watch丢失unknown。正常删除不能掩盖assessed范围后续写入。

## 调用、DB与恢复范围

固定六格boundary/value/read×low/high，模型元组openai/gpt-6.1-sol/prompt_only/provider_default/chatgpt_subscription，temperature/top_p=null。仅65个已封印合成成员，非真实资料；authCLI/显式prompt/model exec各最多6，Node exec最多12，各格最多1，不退款/重发。auth30s、model300s、cleanup10s，worker2520s/unit2580s/owner2700s；首失败停止后续格。

UID1000使用真实公共prepare_launch/use_install、原OFD和私有token路径；Root只stdlib管理生命周期，不导入可写应用/SQLAlchemy。嵌入live-context的runtime绑定仍保留2284文件/28根逐字节和目录成员核验、受控导入及绕过旧pyc，所有context读点有界8MiB，通用40成员上限未放宽。

新低/高配置将通过公共compile/activate写入原实验库，切档位后以公共API恢复原逻辑选择，保留追加历史，不字节回滚。OLD/NEW同事务CAS、封印原基线、提交后检查、durable journal及SIGTERM finally保留；未知不覆盖别人，DB恢复与host恢复分开，任一证据未知不能finish/passed。真实根路径只在私有控制journal中用于恢复，执行回执仅root_path_identity，不带用户名/原路径。

Root保持CG空后按独立binding完整核表再撤本表/unit、持久resolver before/after。普通失败若late reject违反严格post-stop判据，也可能保留表/unit待所有者仅恢复；不声称所有失败必全自动清理。失败未知attempt树/材料不读内容、不归档、不误说已删。

持密前额外只读核当前core pipe精确参数含%c、主Apport/fileutils/report三源码SHA、uid默认unpackaged配置明确absence、非打包/home可执行路径及同system.slice适用性。当前三源码与既有事实一致，paired C元数据与当前同boot；旧C未记录pattern逐字字符串，不虚称其全字节same。没有新崩溃或host core更改；第三路及root内存瞬时采集残余/长期doctor责任不变。

允许集合保持应用可见28.0.0.0/8 TCP443与192.168.44.1 UDP/TCP53，IPv6网络0/not_assessed，不改全机/路由器/其它程序。API/auth共享池不证明分离，本机不核上游映射/最终IP/线路或主张出口身份；无TLS中间人仍取所有者来源。

## 最终离线验证

六个独立未绑定D1模块：batch67、runtime16、bundle3、resources16、IPC28、session_observation45，组合 **175 passed**。14文件mypy（MYPYPATH=src）、Ruff check/format通过；均使用UV_CACHE_DIR=/tmp/issue167-observation-uv与uv run --offline --locked。

fresh两项终审核对当前40成员、22源码映射、专用bootstrap required集合、两entry/完整driver/unit/四规则/工具、65+manifest zip66、嵌入runtime及输入声明。修复阶段与末尾回执矛盾、遗漏bootstrap成员、公开settings写入与core门禁缺口后，当前封印无阻断。旧未批准草稿入口均禁用，不把旧seal审阅当作新seal结论。

实际public owner.run_owner配合FakeOps的6格完整、已validated元数据/17份kernel fixture/12 auth checkpoint/8投影选择/近上限计数，序列化 **111599 bytes**，小于driver131072；这是合成尺寸反馈，不是现场回执。阶段cases/preflight与最终worker两份记录必须一致，矛盾unknown不finish。

bash-n通过。普通用户仅在/tmp替换安装前缀的unit语法副本verify退出0、无stderr；未安装/运行原unit。最终五个精确FS目标均absent，manager not-found/inactive/dead/MainPID0且fragment/drop-in/CG空；未追加root nft查询。结果目录为空，尚无预占。

新台账不扩历史分母/required/正式回执，旧blocked检查点和现场证据不改。链接/diff及最终固定scope含collect审计随回记，未运行完整离线门禁。实际六格、刷新、故障/能力、H5与产品接收/激活仍待；普通read_evidence缺失阻断保持。内部配置、绑定/回执、进程元数据及相关SHA只留本地。
