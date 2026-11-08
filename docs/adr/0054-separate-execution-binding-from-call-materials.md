# 分开执行身份绑定与调用材料校验

状态：提议，待所有者接受；依据：[#168 所有者 D-5／Q4=A 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/168#issuecomment-6722370306)、[#169](https://github.com/MeteoBoy4/PaperRadar/issues/169)；补充 [ADR-0051](0051-separate-live-binding-capabilities-and-activation.md)，关联 [ADR-0052](0052-version-admission-uses-and-capability-requirements.md)、[ADR-0053](0053-expire-capabilities-by-evidence-class-and-coverage.md)。

将 Prompt、Profile、Stage 投影和系统指令的精确字节统一放入能力证据身份，会使校准材料每次变化都迫使隔离／协议重验，并使首次真实资料外发形成循环。执行身份绑定供给与实例及整树、Pi／Node／平台、启动／隔离策略、host／boot／kernel／Landlock、cwd／祖先、文件隔离、应用可见 IPv4 出站、core／Apport、observer、模型元组和认证／缓存当前隔离及接收基线；相关依赖必须精确匹配。模型元组包含 provider、model、thinking、sampling、temperature、top_p、protocol_profile、auth_mode，消费者格与档位另由准入用途精确限定。

材料类保留逐调用形状和上限检查，沿用系统指令路径／形状检查与完整 RPC 帧预算；不成为内容无关证据的身份。只有明确依赖内容的能力才额外绑定材料身份，缺失或不同即拒绝。合成材料取得的内容无关能力可支持真实资料用途；真实资料外发仍分别执行 §2.4／§14 的确认，质量、拒答与真实正文超长不在能力证据覆盖范围内。

同一组件漂移按依赖影响资格，原始分项状态与时间保留；依赖未能确定时由接收／撤销权威保守扩围，不能默认为无影响。PaperRadar 自身运行时只绑定策略版本，开发期源码守卫约束相关执行代码变更时显式升版，不在运行时对源码整树求哈希。代价是依赖表、材料检查和策略守卫都需明确维护；收益是校准输入语义与可复用的执行能力保持分离。完整执行绑定或任何离线合成正例本身都不构成产品执行许可。
