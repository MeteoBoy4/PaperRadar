# 在锚定的用户级 scope 中核验 Pi 放置

状态：已接受；依据：[#177 最终裁决 E-10、S-8、S-9](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6768256547) 与 [#180 两阶段澄清](https://github.com/MeteoBoy4/PaperRadar/issues/180#issuecomment-6768785838)；按 E-10 自动记录已决方案；专用入口授权由 [ADR-0064](0064-authorize-userns-for-sealed-placement-entry.md) 补充。

认证与模型使用同一个用户级 transient scope 放置边界，归于项目 slice，并由长期锚定单元维持规则目标身份。放置依据是实际进程及祖先 cgroup 身份、当前受保护规则目标和锚定身份；相同路径文本不替代核身份，slice 重建或 ID 变化必须拒绝。用户 manager、linger 或锚定异常时失败关闭，不增加 root Pi 启动器，也不要求所有产品命令经过系统 unit。

模型领取前只启动有界阻塞封装。先核封装的实际放置，再由同一进程施加隔离、`no_new_privs`、软硬零 core 限额和受控环境后 exec 固定入口；exec 后、目标执行认证动作或收到 prompt 前再次核身份。`preexec_fn` 不能跨越 `systemd-run` 承担这一保证。认证、正式 Screening/Read 与模型 collector 共用放置函数；领取前可以创建临时 scope、进程和清理资源，但不创建业务 task/attempt、不消耗业务预算、不发送 prompt 或形成采集成功事实。

项目 resolver 使用显式只读视图接缝，同时覆盖认证和模型；不修改全机配置、固定 Pi argv/env 或模型内层 TCP53 权限。确切视图、挂载支持和特权封印部署仍分别验证。代价是依赖可用的用户 manager、稳定锚定、Linux 进程身份及有界握手机制；不支持时保持拒绝，不以离线替身通过授予现场资格。安装使用保护、逐调用文件隔离、`--no-session` 与独立删除检查继续成立；删除不证明历史零写入，完整会话写史不新增为本决定的必需门槛。
