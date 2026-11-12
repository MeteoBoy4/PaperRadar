# 按版本登记准入用途与分项能力要求

状态：已接受；由 [ADR-0058](0058-allow-bounded-auth-cache-stat-evolution.md) 补充；日期：2026-11-09；依据：所有者本轮明确接受；原裁决：[#168 所有者 D-3 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/168#issuecomment-6722370306)、[#169](https://github.com/MeteoBoy4/PaperRadar/issues/169)；补充 [ADR-0051](0051-separate-live-binding-capabilities-and-activation.md)，关联 [ADR-0053](0053-expire-capabilities-by-evidence-class-and-coverage.md)、[ADR-0054](0054-separate-execution-binding-from-call-materials.md)。 “产品执行必须凭证据”的约束关系由 [ADR-0068](0068-replace-live-prerequisites-with-explicit-owner-waiver.md) 取代，其他证据与历史规则保留。

将所有未知能力一律作为阻断会使无法安全取得的供应商观察永久阻断产品；用整体通过值放行又会抹掉安全缺口。准入用途采用带版本的代码登记，显式列出 Screening `PiExecution.run_attempt` 的 boundary/value × low/high 与 Read `read_execution` 的 read × low/high 六格，根用途与准入用途各自判断。未登记用途和必需集合为空的登记均拒绝。证据激活绑定登记版本、消费者格与档位，版本改变不能继承旧激活来扩大资格；旧记录不被重写。

每项能力分别归入必需、披露型或不适用。必需项包括认证／缓存当前属主、权限、无符号链接与自接收基线以来成员未变，cwd／祖先、文件隔离、IPv4 应用可见出站、零 core 与 Apport 身份、RPC 完成／EOF／terminate、实际模型身份、单次显式派发及无额外回合、供给／实例整树与 Pi 版本、启动／隔离策略、host／boot／kernel／Landlock ABI。每一必需项均须 verified、已接收、已显式证据激活、未撤销、未到期且当前适用。

实际 Pi 公共 300 秒、自然供应商迟延和真实错误、low/high 效力及日期 alias、账号可用集合与限额、精确请求计数、认证／缓存全写史及确切 writer 为披露型。允许缺证据或未知，但投影保留 unknown 提示、原状态、依据、范围、证据时点；渲染方补相应下一动作，健康汇总不能把其描述为已验。监督退出、外部中断、IPv6、新平台、无人值守、NAS 在本绑定下不适用，不单独产生阻断，不提升或改写历史 unknown／not_assessed。IPv6 与无人值守仍由阶段 I 另行评估。

核验三态与接收、证据激活、到期、撤销、当前适用性分别成立；诊断四态继续独立。代价是需维护逐项登记及展示义务，并接受供应商未知和特定非正常退出无法由准入层完整识别的风险。既有 attempt、每日配额、retry、停止条件与恢复不刷新预算继续约束本地用量；证据资格不代替外发确认、根用途或模型质量资格。
