# #167：E01认证输入更正与既有刷新附账

## 来源与撤回

本页追加所有者本次只读结构核查及旧批次公开元数据复核，不改已发布结果、永久账本或消耗。agent没有读取认证文件、access/refresh值、其长度/哈希/派生值、进程环境、日志或core；所有认证内容事实均来自所有者声明。

**撤回本轮提问中“六格后已由批准Pi写回models-store/cache、因而不再声明为空”的前提。** 旧六格模型临时树的已知非session写入，不能证明持久认证目录中的缓存发生过写入；该目录此前history仍为not_assessed。所有者报告如下：

| 输入 | 本次所有者确认 |
| --- | --- |
| 目录/auth权限和owner | 0700 / 0600，属主不变 |
| auth provider/type/scope | 仅openai，oauth，含chatgpt.tokens.use.direct |
| OAuth payload字段/命令输入 | 除另列type鉴别字段，为access、refresh、expires、clientId、scopes；无command/cmd/exec或shell形态值，无额外provider |
| models.json | 仍缺失 |
| models-store.json | 仍为空JSON对象，2bytes、0成员；mtime=2026-11-06 11:55 |
| node-compile-cache | 目录mtime=2026-11-06 11:55；不据顶目录mtime推断内部全写入史 |
| 目录成员 | 4，无新增隐藏文件；不推断未提供的第四成员名称 |
| auth.json | 所有者随后补充mtime=2026-11-08 07:13:14.872；access到期时间=2026-11-08 08:10:14，当前已过期 |

时间保留所有者报告原文口径，不从真实凭据读取或重新计算。expires单位仍为毫秒。E01据当前声明计划一次logical refresh及联网、持久写回，不能当离线前置；独立刷新HTTP仍下界0、上界unknown，不以计划数冒充实测HTTP数。若后续运行实际新增缓存写入，按S类别及该轮回执重新登记；不预先背书不存在的已有内容，也不把cache内部history的not_assessed改为零。

## 旧批次附账：授权与关联分开

| 项目 | 归属与实际结果 | 计数及后继 |
| --- | --- | --- |
| e93f7b82c461 / H2–H3 / auth1 | 在已批准六格内计划logical refresh1；首CLI成功、completed后checkpoint成立，首auth阶段有网络活动。原case计时确实包住认证CLI | 原6个auth CLI已计入，不退款。刷新HTTP0＋unknown，packet不是HTTP。原批次及unknown不变 |
| 所有者报告的07:13持久认证更新 | 最初因缺写入事件/排外声明登记待归属；所有者随后补齐精确时间窗、结构观察及排外声明，现**关联到已批准e93批次**，不分配具体CLI序号 | 本批原认证操作的关联补账，不另加第7个CLI或一笔额外HTTP，不退款；独立HTTP计数口径不变。归属依据为时间窗夹逼与所有者声明，不冒充原回执直证 |

e93首格UTC为2026-11-07 23:13:08.713058至23:13:21.668297；按本会话Asia/Shanghai显示为07:13:08.713058至07:13:21.668297。最初的分钟级mtime还覆盖后续CLI，不能指向序号1。补齐精确时刻后仍只按所有者确认范围归属批次，不进一步分配序号。原auth checkpoint只存固定元数据与完成状态，没有checkpoint UTC、auth.json mtime/版本或写入事件；history=not_assessed。不能追溯补写成当时已观察到的字段。

所有者新增的时间窗材料（保留报告口径）：execution-started.json为2026-11-08 07:12:59.589，auth.json为07:13:14.872，credentials目录mtime为07:14:50.056，批次owner-run.json为07:15:22.569，同批exp2.sqlite3写入为07:15:21.17。所见认证写入严格位于批次起止内，OAuth结构/字段未变、无额外provider或命令输入，到期时间距写入约57分钟。目录mtime作为目录变更元数据保留，不据它冒称抓获了具体rename或writer事件。

所有者同时确认窗口内未手工替换、未在其他位置执行登录/刷新、未用该目录运行其它Pi；07:14:50后到其核查无再写入观察，models-store仍空、models.json缺失、目录权限及成员集保持。该排外声明与时间窗/结构共同支持批次归属，超出该范围的程序活动和完整写入史不据此外推。

源码进一步限制了推断：refreshStoredOAuthCredential在锁内重查，另一个进程若已刷新，本CLI可以复用；AuthStorage.modify只有回调给新值才持久写入。CLI等待解析/必要持久化完成后输出，PaperRadar等待EOF和退出0后才返回token。这支持已批准认证成功，不排除其他调用者。

本轮已有上述非秘密补证，不再把该更新悬为未记录操作；原先缺证时的谨慎判断和旧JSON字节保留。仅有更精确mtime本来仍不足以排除其他actor，不能把本次额外排外声明省略，也没有为归属读取token/日志/凭据哈希或重发认证。

## 可复核的固定源码

fresh只读核对下列五个JS与e93绑定安装及所有者给定完整文档安装同字节，路径相对各自node_modules/@earendil-works/：

| 文件 | 关键行段及SHA256 |
| --- | --- |
| pi-ai/dist/auth/resolve.js | 46–47、62–118：最低寿命、15s期限、锁内重查/刷新/持久化；`3fcec09018831324d9c7fb02f4aea707e8a9e4fec5a2bdf1b3d84d716fd3091e` |
| pi-ai/dist/auth/oauth/openai-chatgpt.js | 110–154、172–183：token HTTP、credential/expires及refresh分支；`4cf9fc758a07ffe4ee022326404b5dcc86767ee4154945c0417c7f95eaecdcc2` |
| pi-coding-agent/dist/core/auth-storage.js | 142–150、385–401：等待回调及条件写回；`59791d54e50bfb86f0bb9e8dcee776547ae1744fc4aeb2fe14ff6610c1f5c567` |
| pi-coding-agent/dist/cli/credential-print.js | 48–56：OAuth bearer与minimum lifetime；`3f40aaf4101369f9b55d342b0bdb7911fe5c092b4db1a5e48b09fc29fa8d8654` |
| pi-coding-agent/dist/main.js | 128–133：15s signal、禁model network、await解析后输出；`08b91f9eb3adf9a5027c18732d1e4de70999bd15c445b65cb0ddd0cd68f2746b` |

e93封印worker第855行等auth gate、858–859行起计时、895行进入credential_phase；709–758行为前后checkpoint，905–913行发布auth-ready。当前Python auth.py与原runtime绑定相同：22–30行固定CLI/900s最低寿命，65–85行等待EOF/退出0后返回token。

## E01最终H2必须携带

使用本次正确空store、缺models.json及当前过期声明；计划一次联网刷新与持久认证更新，认证目录与模型临时agent分别记录，失败/超时/轮换不确定即停止，不回滚auth.json或重试/退款。认证完整退出及持久化后验之前不arm外部SIGINT。实际HTTP与隐含重试仍按ADR-0048下界/unknown，预算权威为Pi报告usage，缺usage不能填零成本。

按所有者新要求，E01及后续批次回执须增加credentials的pre/post快照：文件集合与各项mtime/size/inode/ctime，不读任何内容。快照与认证阶段和UTC时点关联，递归缓存集合保持有界/nofollow/稳定检查，缺参照、越界、别名或观察失败unknown并停止，不截断。内部安全检查可使用类型/owner/mode/nlink/dev，但snapshot不额外导出这些字段。它能直接证明所观察集合的前后delta，不等于瞬时全写史或进程作者身份；persistent history仍not_assessed。

只读文件集合核对已在所有者明确metadata权限后完成：顶层为auth.json、exp2-installation-id、models-store.json、node-compile-cache（含根五节点），没有读取任何一个文件内容；marker也不读取或hash，不充当供给权威。准备时递归只数到共27节点，完整快照实现与界限另在E01材料中封印。

所有者指出原实验库已有本批写入，E01必须读取当前公开供给/选择基线，不能假定空库、重建或初始化；执行只在另获许可后通过公共API/CAS恢复原逻辑选择，保留追加历史。此页不授权E01部署、认证、刷新、模型或信号发送；独立H1/H2/H3仍需绑定完整新包。内部认证元数据、绑定及回执只留本地，不上传GitHub。未运行现场或完整离线门禁。
