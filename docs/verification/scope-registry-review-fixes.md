# 集中登记第二步审阅修复覆盖

本次记录 #126/#137 第二步候选 `093ba1e486111a01a98c44ff8b5e3462beaf62ab`
之后的三项审阅修复。它补充[集成台账](scope-registry-integration.md)，不修改既有
#132–#136 证据、第一步冻结证据或历史 JSON，也不发布正式验收结论。
机器记录见[修复台账](scope-registry-review-fixes.json)。当前为修订 2：首轮候选
`249652d` 合入 `6cee3a2` 后，定点复核发现 `GROUPS +=` 尚未要求旧计划组确认；
本轮补齐有序增量摘要。首轮验证保留在 JSON 的 `previous_review_fix`，不作为本轮重跑结果。

## 修复与源码闭包

- 原 audit ↔ baseline 当前进程依赖环已消除。共享 `Scope`、报告模型及纯接收校验
  下沉至现存 registry；audit 保留审计核心和公开兼容导出，baseline 通过明确
  `Callable[[Path, tuple[Scope, ...]], AuditReport]` 使用核心，collection 依赖 registry。
  历史树的独立进程读取自己的公开 audit 是跨版本协议。公开 `audit_baseline` 签名、
  错误原因与身份约束保持。旧合成 CLI 副本的复制闭包无需修改。
- 中文 CLI 将 scope 下游提示改为“需审阅/验证的受影响下游”；实际文件漂移继续
  按 `files.reason` 单独列出。原失败引导与受控原因保留。
- 生产 `GROUPS` 和 `Group` 字段声明（含默认值）进入敏感摘要；名称、后缀、required、
  dependencies、writer、receipt_scope 变化要求全部影响组确认。所有模块级 `Assign`、
  `AnnAssign`、`AugAssign` 声明按原序保留，后续追加不能覆盖早先声明的摘要；
  中央 SHA 更新不能解除确认，普通 helper 实现变化保持机械分类。

没有新增核心源码路径。实际源码闭包仍为 audit、baseline、registry 各由 A8/A9/A10
消费，collection 由 A9/A10 消费；下沉后的代码已受现存登记覆盖，没有遗漏间接实现。
先通过全项目格式/静态检查，再只重绑已逐路径审阅的五个实际源码变化：四处中央 SHA、
一处 A9 独有 CLI 字面量，共十二条漂移成员。第二轮仅再次更新 baseline 一处中央 SHA，
清除 A8/A9/A10 三条实际漂移；两轮均没有 scope 级联重绑。

## D1 独立覆盖

新增未绑定模块 `tests/test_scope_review_fixes.py`，累计 **16 例**。首轮 9 例：required flip
更新中央 SHA 后仍缺确认失败 1 例；名称、后缀、writer、receipt_scope、dependencies
逐字段变更 5 例；普通 helper 机械变化 1 例；中文 CLI 下游与实际漂移分列 1 例；
`Group` 默认依赖变化 1 例。required、CLI、默认依赖回归均保存修前失败与修后通过记录。
第二轮新增 7 例：实际 helper 以 `GROUPS +=` 新增组后，只有新组确认仍拒绝旧 11 组
缺确认 1 例；两种初始声明乘三种后续声明，已追加组后修改首声明仍须全部 12 组确认
6 例。这 7 例均保存修前失败和修后通过。
测试通过真实仓库副本、公开审计 Python 与 CLI 接缝验证，不进入旧组回执或扩大 required。

六个冻结 scope/audit 测试模块 SHA 不变；S4 已准备的十模块原 78 例本轮没有改动。
第二轮仅扩充本轮未绑定回归模块，未改其它普通测试或支撑。285 个固定模块、5281 例、41 refs、0 scope hash、
1203 条登记/695 路径、11 组/10 required 与独立 reader 支持表均保持。

## 精确审阅与确认承接

旧树外 `137-reviewed-changes.json` 不能直接绑定修复后的树。新依据仍为 34 项，
其中 27 项逐字保持，7 项逐字段审阅后更新：A9 scope、CLI、生产声明影响集合、
audit、baseline、collection、registry。新旧完整文件 SHA、entry 摘要、逐项登记、
类别、全部影响组与理由写入本次 JSON 台账。第二轮相对首轮 33 项完整对象不变，
仅 baseline 对象的文件/entry SHA、中央登记 SHA 和三组 registrations 四字段精确修订；
`reviewed_delta_from_v1` 保留完整差异，原全部影响组和类别保持。

确认授权为 151 条：原 144 条，加上受控枚举等价移动导致 audit/registry 各三组的
敏感分类确认，以及生产声明对 A1 的计划影响确认。实际 required 集合没有变化。
新树外依据和绑定脚本逐对象核对全部字段；既有 27 项必须完全相等，新 7 项以明确
对象 SHA 限定；第二轮再以唯一完整对象 SHA 限定本轮修订。不得用测试确认辅助函数代替审阅。

候选提交及最终 merge/root 身份必须分别生成外部确认。绑定脚本还核对完整审阅树身份；
确认仅解除 confirmation_required，不能清除 hash_drift，也不授权写回。
最终正式 run_id 只留树外，完整门禁由最终集成与复核后的唯一执行者承接。

## 本轮开发验证

- 全项目 Ruff check / format 通过；980 个文件格式稳定，mypy 707 source files 通过。
- 第二轮相关三模块 72 passed：34 基线、22 真实新组及累计 16 独立修复回归。
- 首轮 305 passed 和 `check-compatibility all` 176 passed 保留原版本证据；第二轮正常
  接口行为不变，未重复全部兼容组合。
- 每轮默认与提交后显式审计/收集的实测结果在树外报告；当前候选仍须绑定当前身份。
- 本轮没有运行完整离线门禁或 live；不证明完整 A、四刊 live、Pi RPC、模型质量、
  正式校准、Docling 或 NAS。
