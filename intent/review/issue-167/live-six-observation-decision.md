# #167：六格批次前的文件观察边界与认证输入裁定

本轮固定Node诊断[已通过并恢复](../../../docs/verification/issue-167-node-diagnostic-result.md)，没有追加Pi/认证/模型调用。下一六格的受信runtime、公共启动链、事务选择保护、回执与恢复源码已准备，但**当前不可执行**：固定Pi源码否定了候选“全attempt零写”预期。这里只提交具体事实和下一准备方向，不申请执行许可。

## 所有者裁定：S 与认证输入已确认

所有者已选择S，授权继续准备session/已知非session分类观察；session全窗口零写、未知阻断、完整终态及独立删除保留。没有授权本轮Pi、认证、刷新、模型、网络、root或真实库写入。旧blocked检查点保留原字节，后续以新的方法与封印交付，不把旧零写候选改记通过。

所有者另执行只读结构核查并作如下声明，来源为所有者报告，agent没有读取凭据内容或验证其值：目录0700/auth.json0600；顶层仅openai，oauth类型且scopes含`chatgpt.tokens.use.direct`；OAuth payload为access/refresh/expires/clientId/scopes，无命令字段、shell形态值或额外provider。models.json缺失，models-store为空对象（所有者报告2字节、0成员），node-compile-cache已存在；现有输入按此声明纳入H2可信范围。agent不新增凭据reader，不打印access/refresh的值、长度或哈希。

最终H2必须一并列入：expires单位为毫秒；所有者报告当前access已于2026-11-06 18:42过期（未提供时区，本轮不转换）。下一认证CLI会触发一次预期刷新并联网，必须计入该轮动作、计数口径及失败停止条件，不能安排为离线前置。预期一次刷新不等于独立观测到恰好一次HTTP；内部重试/重定向、后续CLI是否刷新仍按可证下界与unknown如实披露，不发明额外硬上限。

认证专用目录会持久写入刷新状态、初始化/目录缓存和编译缓存；它与模型临时agent目录分别记录，不套用模型attempt的删除或session零写口径。所有者报告其位于已被gitignore忽略的.scratch，本轮不归档或上传该目录。实际读写和联网仍须新的具体H1/H2/H3执行批准。

## 原样 Pi 的非 session 写入反证

原票要求分别观察attempt终态集合、目录删除、全运行session写入历史。下一批实现曾提出更强的候选：整个attempt mutation=0且终态只有预建settings；这不是已经由所有者接受的现场事实。

按所有者指定docs/docs.json导航复核，再与项目固定源码交叉核对：

| 固定源码 | 实际分支及有限结论 |
| --- | --- |
| core/agent-session-services.js:53–61 → core/model-runtime.js:80–85、109–110 | 新agent目录会建立AuthStorage和FileModelsStore，默认refresh(false)；离线/不刷新模型不等于不创建本地存储 |
| core/auth-storage.js:40–42、125–126、287、289–291、314–323 | 缺失auth.json或models-store.json时，正常锁定读取路径会先写入空JSON对象 |
| 实际dist/bundle/cli.js入口 → cli-runtime.js/chunk中的对应实现 | 原入口还调用Node enableCompileCache，模型TMPDIR内存在编译缓存写入路径；不把未执行过的具体文件数说成实测 |
| 公共rpc.py初始化 → rpc-mode.js:421–430 → agent-session.js:2653/3143 → settings-manager.js:635–641/686–692、450–483、155–177 | set_auto_retry/compaction(false)即使值未变也save/writeFileSync；这是固定RPC的已知非session控制写，不能把settings文件字节/时间不变当作原样路径的前提 |

这些是固定实际入口的静态分支反证，不是本轮Pi实测。已有model AttemptResources只预建settings，故原样启动至少会触发已知非session存储路径。不能拿其失败去声称发现了session持久化，也不能私下preseed文件、改env/argv、禁止compile cache或改变产品启动身份来让候选过关。

## 文件观察的两种处理

| 选择 | 下一步具体工作 | 成本与边界 |
| --- | --- | --- |
| S：按原票区分session与已知非session缓存 | 设计并离线验证内容无关的分类观察：保留session全窗口零写要求，完整记录终态/独立删除；已知auth/model目录初始化及compile-cache另列类别，未知写入/路径、溢出/观察缺口仍unknown并阻断。真实数据不发出，原Pi argv/env/产品身份不改 | 需要新的实验collector/分类映射及负例，明确缓存历史哪些可观测、哪些不在所声明范围；不能将缓存未知写数填0或把分类完整性冒充整个attempt零写。先完成方法及fresh审阅，再给新的H1/H2/H3执行包 |
| Z：继续要求整个attempt零写 | 保留现更强候选，不放行当前固定供给 | 当前源码已有反证，批次保持blocked；不能靠正常模型调用“试试看”消耗凭据或额度，也不自动重开已拒绝的新启动身份路线 |

S不是将session持久化改成允许。若无法内容无关地区分、不能保持所声明session观察范围完整、或出现未知写入，则仍unknown停止；具体session路径与缓存类别须以固定源码绑定，不能任意根据实测结果追加白名单。此时不预称分类方案已可行或已获覆盖。

按S准备的方法另保留严格的公开控制设置条件：只允许固定RPC引起的精确settings文件MODIFY/CLOSE_WRITE类别，写事件计数是inotify记录下界；inode/type/mode/owner/nlink、别名/rename/delete/ATTRIB变化仍阻断。本次由父程序创建的公开、非凭据settings在预arm/封口/删除前checkpoint必须与public SETTINGS_JSON有相同键、值和类型，容许格式变化，不用Python宽松dict相等混同false/0；不读取auth/model-store/cache内容。该检查不声称解读了每次写入的中间内容，也不更改两个RPC关闭命令、初始配置字节或产品策略身份。

## 专用认证目录的实际输入边界

所有者已确认准备时使用现专用目录并由其维护，但未授权认证执行。主代理只对固定路径lstat：目录0700、auth.json为当前UID普通0600文件；models.json缺失，models-store.json存在且为当前UID普通0600文件。没有读其内容、长度、哈希、token或派生值，也未移动、删除文件。

固定main.js的auth分支在通常SettingsManager/extensions/session加载前return，但print分支创建ModelRuntime后仍读取models.json、models-store.json并遍历provider凭据。core/auth-storage.js:376–383对api_key调用resolveConfigValue，命令型值可以执行命令。因此仅--provider openai不能证明其它凭据条目没有副作用。

models-store是持久cached catalog overlay，不是可以默认忽略的文件；缺失时本次CLI也会自行创建，不能逐格要求其持续不存在。auth provider-only getAuth不直接请求cached model，但全provider凭据检查的影响仍须声明。默认API/刷新初始域名依据固定源码，不把它当作ACL穷尽域名链证明。

该可信输入条件现由上述所有者结构声明满足；models.json缺失及目录/文件权限由程序metadata门槛复核。内容条件仍仅来自所有者声明，agent不读取来验证，不暗加Python凭据reader或patch Pi；已知变化、声明不适用或metadata无法核实仍停止。

这项声明不授权读取内容/刷新/调用；实际认证CLI可能读写auth/model缓存和编译缓存的范围，将在最终一次H2中明确列出。模型自己的临时agent目录与认证持久目录不同，分类、清理与证明范围必须分别记录。

## 已准备且不依赖此裁定的部分

已保留：完整公共prepare_launch/use_install链的controller、仅UID1000导入的代码/依赖绑定、六格封印输入、原实验库公共compile/activate与同事务expected-old/target保护、原选择恢复journal、SIGTERM受控收尾、模型前root/CG门闩、压缩RPC顺序/usage回执及host恢复。没有写真实实验库或读取凭据内容。

源审阅checkpoint为 `.scratch/issue-167/live-six-afk-review-v1/`，保留当时readiness=blocked、execution_authorization=false的原字节，无owner-wizard/安装入口；e93f7b82c461没有预占或消耗。下一S方法与执行包另行封印，它不是实际授权包，也不把离线测试提升为六格现场通过。最终源、测试、审计及具体SHA按本轮交付回记；新H1/H2/H3、供应商能力/故障、H5及产品激活仍待。
