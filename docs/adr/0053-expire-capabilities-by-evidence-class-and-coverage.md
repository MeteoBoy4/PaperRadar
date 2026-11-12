# 按证据类别与逐调用覆盖决定有效期

状态：已接受；日期：2026-11-09；依据：所有者本轮明确接受；原裁决：[#168 所有者 D-4=A 与 E01 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/168#issuecomment-6722370306)、[#169](https://github.com/MeteoBoy4/PaperRadar/issues/169)；补充 [ADR-0047](0047-expire-and-explicitly-activate-live-evidence.md) 与 [ADR-0051](0051-separate-live-binding-capabilities-and-activation.md)，关联 [ADR-0052](0052-version-admission-uses-and-capability-requirements.md)、[ADR-0054](0054-separate-execution-binding-from-call-materials.md)。 “产品执行必须凭证据”的约束关系由 [ADR-0068](0068-replace-live-prerequisites-with-explicit-owner-waiver.md) 取代，其他证据与历史规则保留。

供应商后台可在本地身份未变时改变，不能只靠漂移检测无限复用；站点与工程性质若能每次完整核验，机械套用同一个时钟会产生没有额外证明价值的重验。供应商和未分类能力均从每项原 `verified_at` 起精确 `timedelta(days=30)`；接收、签收和证据激活不重新计时，等于到期时刻即拒绝。登记的较短上限可以收紧该期限，不能延长它。粒度是能力 × 消费者格 × 档位；跨格聚合只取明确已核验各格的最早 UTC 时点，不生成跨格资格。

站点类包括当前认证／缓存隔离及成员基线、cwd／祖先、文件隔离、IPv4 出站、零 core、Apport 身份、供给／实例整树、Pi／Node／平台、host／boot／kernel／Landlock。工程类包括启动／隔离策略、本地单次显式派发代码路径，以及 E01 的 SIGINT → KeyboardInterrupt 性质。只有逐调用完整覆盖所有登记依赖，或由特权侧给出当前有效证明时才免时间上限；覆盖不足必须有登记的有限期限，否则拒绝。单次显式派发不证明供应商没有隐藏请求，额外模型回合仍独立判定。

实际模型身份与无额外模型回合为供应商类；300 秒、自然迟延／真实错误、参数效力、日期 alias、账号集合／限额、精确请求数的供应商主张同样使用供应商时钟。RPC 完成／EOF／terminate、认证／缓存全写史和 writer 的证据类别保持未分类，默认 30 天；存在合成工程控制不自动把真实 RPC 观察提升成无期限证明。监督退出与其余绑定外能力也保守保持未分类；E01 明确为工程类，但外部中断不适用的分类保持。逐项依赖与现状登记见 [Live evidence Contract](../contracts/live-evidence.md#到期类别与依赖)。

当前时间由判定调用者显式传入。使用 UTC 墙钟并以账本最大已记录时间为下限，低于下限立即拒绝；无时区、未来原验证／观察时间、verified 缺原时点、未核验却带 verified_at 均不合法。原状态、依据、范围和时间不随过期或撤销改写。代价是依赖覆盖和特权证明必须保持可靠；未覆盖组件不能假装享有漂移有效期。该口径不改变任何历史回执、#167 结果或旧时点。
