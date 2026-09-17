# 由用户判定校准相关变更的等级

当 Screening 模型、关键提示词、Research Profile、输出契约、复用升级参数、评分语义或建议规则可能改变既有校准解释时，PaperRadar 记录 runtime plan 差异并暂停自动精读，直到用户附理由标为 `minor` 或 `major`。`minor` 继承门禁，但自动重算只覆盖 waiting_review、waiting_calibration 和尚无生效决定的论文，并预先显示篇数与配额耗时；既有人工决定继续生效，正式分析不因 Profile 演进自动重跑。`major` 关闭门禁，直到同标签重算或新盲评通过且用户再次显式启用。系统不能静默复用旧 enable，也不能替用户决定等级。
