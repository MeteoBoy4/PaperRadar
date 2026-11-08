# #167 安装树外最小观察 loader：设计与离线参考模型

审查标签：`issue-167-loader-reference-review-1`。本标签只存在于本审查文档，不注册为产品启动策略、协议档案或供给身份。

依据：所有者本轮 H4 裁决，仅批准设计并离线验证安装树外的最小观察 loader。是否采用新启动策略身份、采用后 EXP-2 现场证据重测，均留到 H4 终局。本文件不授予注入、真实 Node/Pi 运行、联网、认证/模型调用或安装树修改。

## 本轮可执行范围

`scripts/issue167_loader.py` 是 Python 参考原型：`attach()` 实际替换两个独立合成 peer 的可调用 dispatch 口。安装完成后，由调用方产生前台、预热、重试、认证刷新等闭集类别操作；peer 发送口维护自身独立次数，不从观察器事件反推。没有原始请求对象、URL、headers、body、token、完整流或配置读取接口。

它证明“先安装接缝、调用经过接缝、观察失败不继续发送、事后与独立参照核对”的语义可以离线执行。它不是 JavaScript、Node module loader 或固定 Pi hook。本轮不提供未测试 JS 文件，避免仅检查源码字符串就称运行时覆盖通过。未运行 Node/Pi，也没有把 Python 调用计数改称实际 HTTP、供应商请求或计费。

## 四字段输出与闭集来源

所有可导出的观察记录仅有：`category`、`sequence`、`count`、`completeness`。`completeness` 只有 `complete/unknown`；没有原始异常、诊断文本、请求参数或秘密字段。运行中记录尚未完成独立核对，始终 `unknown`；只有整个声明窗口结束、两个角色均已安装且独立参照精确匹配后，合成最终记录才可为 `complete`。

类别由受信的外层角色/操作位置指定，不能解析请求内容来猜用途：

| 类别 | 应由何种控制点提供 | 本轮验证 |
| --- | --- | --- |
| prompt | 上层明确派发位置 | 合成 model dispatch |
| auth_cli | 宿主专用 CLI 启动位置 | 合成 auth dispatch |
| model_http / model_warmup / model_retry | 模型出口及受控调用来源；预热/重试也算额外模型操作 | 同一合成 model transport 调用口，分开独立计数 |
| auth_refresh_http | 宿主刷新出口，不能由模型 SDK hook 代替 | 独立 auth peer，不与模型计数互借 |
| model/auth_tls_connection 与 model/auth_packet | 每角色独立底层连接/packet事件源 | 参考模型只处理合成类别，不观察网络 |
| model_ws_connect / model_ws_create | 对应另一类连接与模型操作；首批真实 openai 应为0，出现则停止 | 本轮测试保留0，未执行WS |

`sequence` 是观察器整个合成窗口内单调序号；最终每类别返回该类别最近序号（未出现为0）与累计count。可选输出sink必须对当前序号ACK，缺ACK、错ACK、bool或异常均unknown，拒绝继续转发。ACK只演示合成接收语义，不证明真实持久存储或对抗不诚实sink。

## 未来 Node 侧拟接缝，尚未实现或批准采用

1. **global fetch与最低发送不是同一层。** 未来可考虑安装树外 loader 在应用import之前接入默认global fetch，但仅在调用前包裹fetch，只观察一次API调用，不能证明内部重定向、连接重试或自定义transport的实际HTTP发送次数。不得将其计数直接登记为完整provider HTTP事实。
2. **最低dispatch/diagnostics还需独立覆盖证明。** 若采用固定Node的底层dispatch或diagnostics事件，必须证明错误发生在连接前/响应前、连接复用、重试、重定向、预热/总结路径和未知transport均可见。当前未运行Node、未确认其事件语义，不能断言某个channel已足够。
3. **onResponse只观察收到响应之后。** 它漏响应前失败，且现成回调携带headers。未来不得保存或遍历该原始对象；只接受专门构造的受控category/sequence/count/完整性。不能启用SDK debug日志解决缺口。
4. **模型/auth进程角色在外部封印。** 模型consumer/档位、auth角色和观察窗口的关联从受审控制器与完整绑定而来，不能从URL、Authorization、body、token形状或用户提供字段推断。模型与auth的底层事件源独立；调用源类别无法可靠判定时保留unknown，不填foreground或0。
5. **不检查原始请求字段。** 拟适配器只接受预登记受控类别和最小事件触发，不序列化请求/响应，不访问headers/body/token、不采集外部异常文本，也不读取进程environ或认证文件。需要这些内容才能分类的方案不在本轮原型授权内，必须保留缺口。
6. **独立参照不能自证。** 真实运行须有可信、可验证连续性且角色适用的另一来源。观察器自己的累加值、Python合成peer、配置中的期望1或最终JSON都不能充当真实provider请求参照。缺参照、漏计、重复安装/重复计数、sink失败或事件丢失均unknown，禁止形成可消费通过。

## 失败与窗口

合成原型拒绝晚加载、角色重复安装、未知类别/错角色。调用口被替换或出口绕过时，独立peer与观察器不匹配，最终unknown；不能把两套都没有真实依据的0当成功。观察故障在实际转发前终止；一旦失败不能通过重新finish恢复。窗口结束后再dispatch或再次finish会撤销合成完整性，不打开新窗口。

合成下游已计一次操作后抛错时，观察仍记1次尝试，不因业务失败填0。`complete`只说明这个合成接缝观察闭合，不表示模型成功、计费准确、真实完整底层覆盖或任何现场资格。原型控制异常只用于阻断，外部日志/报告应仅导出四字段记录。

## 终局前不能外推的事项

未决定是否采用任何新启动身份，不新增/修改 `LAUNCH_POLICY_VERSION`、`pi_protocol` 注册或固定供给。未注入真实进程，不修改 `NODE_OPTIONS`、global fetch、SDK或系统dispatcher。没有部署代理、CA或新的core处理。后续即便代码审阅通过，也必须由所有者在H4终局决定策略身份和EXP-2重测范围，再按H1/H2/H3授权执行；本轮不预支通过结论。

## 按固定文档导航复核的公开接口

先读所有者指定的安装文档 `docs/docs.json`，按其中 Build on Pi → Use the SDK / Build Extensions / Add Custom Providers 导航到相关小节；文档基路径为 `/home/meteoboy4/.pi/agent/install/releases/1.4.0/node_modules/@earendil-works/pi-coding-agent/docs`。只读文档，不启动安装入口。

- `sdk.md:72–108`：session.subscribe是消息、队列、compaction、retry和生命周期观察；agent_settled表示不再自动继续，不是独立实际HTTP计数。默认factory还有文件settings/session/resource发现，不能为了观察就直接套用默认SDK运行时。
- `extensions.md:94–101`：文档明确请求hook顺序为context、context_with_system、before_provider_headers、before_provider_request、after_provider_response、provider_stream_event/assistant事件。上层before/after不能覆盖底层所有发送/隐含重试，也不覆盖宿主刷新；不能将其次数直接视为实际transport。**生产-ne保持，本轮不启用extension。**
- `custom-provider.md:178–198`：setup可能在start之前失败，认证缺失也可同步抛错；onPayload在发送前且可替换payload，onResponse在收到响应后、消费body前。它们不等于已发送请求和完整底层覆盖。本轮不读取/替换payload，不使用response headers或provider stream内容进行计数。

这些文档提供未来接缝候选和失败顺序依据，没有证明某个实际出口已经可独立计量；最终采纳与重测仍由所有者裁决。

参照在finish中一次性完整读取到纯受控dict后比较；items/迭代/索引异常均永久unknown，不能换成正常参照恢复。中断保持原有控制语义，但同时标记该窗口失效；不得吞掉中断生成complete。
