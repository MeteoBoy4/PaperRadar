# 为专用封印放置入口授权 userns

状态：已接受；依据：[#184 所有者授权](https://github.com/MeteoBoy4/PaperRadar/issues/184#issuecomment-6792224122)；补充 [ADR-0060](0060-place-pi-in-anchored-user-scopes.md)。

项目私有 resolver 视图需要 user/mount namespace，而站点的 AppArmor 可以拒绝通用解释器使用其中的能力。为通用 Python 或 Node 授权会同时开放任意脚本入口；修改全机限制又会影响项目之外的程序。因此，站点只为封印的专用放置入口授权 userns，正式认证、模型和 collector 共用该入口，新增字节仍须所有者审阅并部署。

入口采用固定静态引导与后续执行两个阶段。引导阶段只处理固定的只读 resolver 视图，不接收凭据、Prompt 或任意目标；以产品身份映射后撤除 capabilities，并过渡到禁止 userns、挂载和提权的策略。后续阶段在动态代码和握手之前固定零 core、`no_new_privs` 及不可逆 syscall 限制，再处理闭合的认证、模型和负对照操作。它不提供通用解释器、可变脚本或任意 argv/env/path 接口，也不增加 root Pi 执行者。

封印同时绑定入口、配置、策略源码和编译字节；受保护观察核对实际加载的策略字节、模式、attachment 和所依赖的站点限制。缺失或无法核对时拒绝，真实漂移继续按依赖收紧。全机 sysctl、resolver、上游路由及默认 AppArmor 策略保持；升级继承经认证的原部署时点，不能重置目标窗口、额度、停止、撤销或旧回执。

代价是维护静态工具链闭包、策略加载身份及中断恢复，并在真实调用前先验证无秘密放置链。它沿用既有同 uid 源码修改不在防护模型的边界；正常预先 trace 须拒绝，不把该检查宣称为抵抗已控制指令的 tracer。入口存在、离线编译或握手成功都不产生现场能力或执行资格。
