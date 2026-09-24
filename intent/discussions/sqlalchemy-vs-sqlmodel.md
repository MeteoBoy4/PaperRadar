# 持久层选型调研：SQLModel 还是 SQLAlchemy

状态：调研完成，建议 SQLAlchemy 2 typed ORM；尚非锁定决策，最终在阶段 A 锁依赖并进入验收证据时落定（draft.md §10"具体版本在阶段 A 锁定"）。
触发问题：draft.md:1341 写的是"SQLModel/SQLAlchemy 2 风格持久化"，两者并列未裁决；实施 storage/ 模块前需要定下来。
调研时间：2026 年（版本信息以各官方来源当日为准）。

参照文件：

- `intent/draft.md` §10（技术栈建议、模块边界）、§3.4（阶段输入指纹）、十一（阶段 A 验收）
- `AGENTS.md`（依赖规则、mypy strict、Frozen Contract、migration 强制）
- `pyproject.toml`（requires-python >=3.12,<3.15；pydantic>=2.12,<3；mypy strict）
- 归档讨论 `intent/archived_discussions/daily-paper-reader.md`（"数据库演进方式"一节按 SQLModel 表述，属上游思路归档，非权威）

## 一、结论

**直接使用 SQLAlchemy 2.x typed ORM（`DeclarativeBase` + `Mapped[...]` + `mapped_column()`），不引入 SQLModel。** Pydantic 保持现有定位：LLM 输出契约与冻结 Schema 的边界类型，不进入持久层。

一句话理由：SQLModel 的核心价值（同一模型同时充当 API Schema 与数据库表，服务 FastAPI 场景）在本项目不存在；而它引入的三个代价——Pydantic 版本耦合、SQLAlchemy `<2.1.0` 锁定、mypy strict / Python 3.14 边缘问题——恰好都命中本项目的硬约束（长期无人值守运行、mypy strict CI、Python 3.12–3.14 支持窗口、pydantic 跟随契约需求升级）。

该选择完全满足 draft.md:1341 的表述——"SQLAlchemy 2 风格持久化"本来就是两个并列选项之一；SQLModel 底层也是 SQLAlchemy 2，"风格"不变。

## 二、两个库的现状（一手来源）

### SQLModel

- 最新版 **0.0.31（2025-12-28）**，破坏性变更：移除 Pydantic v1 支持（官方 release notes：https://sqlmodel.tiangolo.com/release-notes/）。
- 自我分类为 **`Development Status :: 4 - Beta`**，2020 年发布至今版本号仍是 0.0.x（pyproject：https://github.com/fastapi/sqlmodel/blob/main/pyproject.toml）。
- 依赖约束：`SQLAlchemy >=2.0.14,<2.1.0`、`pydantic>=2.11.0`、`requires-python >=3.10`（同上 pyproject；classifiers 声明到 3.14）。
- 发布节奏历史上不均：0.0.22（2024-08-31）到 0.0.24（2025-03）间隔约 7 个月；2025 下半年 0.0.25–0.0.31 集中发布，多为跟随 Pydantic 新版本的修复（如 0.0.26 修 `model_dump` 与新 Pydantic 的兼容）。
- 已知问题（均来自官方 issue/discussion）：
  - **`table=True` 模型构造时绕过 Pydantic 校验**——字段验证器、默认值校验均不执行（issue #1837：https://github.com/fastapi/sqlmodel/issues/1837）。维护者建议需要校验时另建非 table 模型。
  - **Python 3.14（PEP 649）下 `Relationship` + `TYPE_CHECKING` 前向引用可空联合抛 `TypeError`**，讨论至今无人回应，workaround 是给整个注解加引号（discussion #1765：https://github.com/fastapi/sqlmodel/discussions/1765）。
  - 严格类型检查器（pyright/mypy strict）下存在 `Field`/`__tablename__` 等边缘报错（discussion #1932：https://github.com/fastapi/sqlmodel/discussions/1932）。
  - 官方文档自己定位为"90% 常规用法 + 转义口"：自定义类型/约束/加载策略都要降级到 `sa_type` / `sa_column` / `sa_relationship_kwargs`；一旦给出 `sa_column`，`Field` 的常规参数被整体排除（features：https://sqlmodel.tiangolo.com/features/）。

### SQLAlchemy

- 稳定线最新 **2.0.45（2025-12-09）**（changelog：https://docs.sqlalchemy.org/en/21/changelog/changelog_20.html）。
- 2.1 线在推进：2.1.0b1（2026-01-21）、b2（2026-04-16）、rc2（2026-09-08）；2.1 要求 Python ≥3.11、greenlet 不再默认安装（同步用法不受影响）、提供 free-threaded wheel（https://www.sqlalchemy.org/download.html 、https://docs.sqlalchemy.org/en/21/changelog/changelog_21.html）。项目 requires-python ≥3.12，无冲突。
- **2.0 typed ORM 为 PEP 484 工具设计，官方声明可在无插件下通过 `mypy --strict`**；旧 mypy 插件已废弃且只兼容到 mypy 1.10.1（本项目锁 mypy ≥1.18，插件路线本来就不可用）（https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html）。
- Python 3.14 支持在稳定线持续修复：2.0.45 修了 `MappedAsDataclass` 与延迟注解/TYPE_CHECKING 关系的问题（同上 changelog）——与 SQLModel #1765 恰成对照。
- 无任何 Pydantic 依赖，版本升级路径完全自持。
- 数据类风格可选 `MappedAsDataclass`（https://docs.sqlalchemy.org/en/20/orm/dataclasses.html）。

## 三、项目约束逐条对照

| 项目约束（来源） | SQLModel | SQLAlchemy 2 typed ORM |
|---|---|---|
| SQLite 唯一事实源 + Alembic migration 强制（AGENTS.md、draft §阶段 A） | 均为 SQLAlchemy metadata，均可；Alembic 对未命名约束的 autogenerate 限制两边一样，都要配 naming convention | 同左，且少一层 |
| mypy `strict = true`（pyproject） | 有已报告的 strict 检查器边缘问题（#1932 等） | 官方设计目标，声明无插件通过 strict |
| Python >=3.12,<3.15，当前解释器 3.14.4 | 声明支持 3.14，但关系模型密集场景有未回应的 PEP 649 bug（#1765） | 2.0.45 已修复 3.14 延迟注解/关系问题 |
| pydantic>=2.12,<3 为契约层依赖，需跟随升级 | 双重耦合：历史上 Pydantic 小版本常需等 SQLModel 出修复版；自身 Beta | 零耦合 |
| 长期无人值守流水线，依赖变化要"无聊"（AGENTS.md 依赖规则） | 额外一层包装，锁 `SQLAlchemy <2.1.0`，2.1 正式版后需等其放开 | 20+ 年发布工程，2.0 维护线与 2.1 开发线并行 |
| 无 Web/API 层（V1 明确不做，V2 未承诺 FastAPI） | 核心卖点（一模型两用 + FastAPI 文档）用不上 | 无损失 |
| 表结构特点：受控枚举、UUID、JSON 原始条目、复合唯一约束（强标识）、指纹哈希、追加式事实表 | 恰好落在 sa_type/sa_column 转义区，等于写 SQLAlchemy 加间接层 | 原生表达 |
| Pydantic 只用于 LLM 契约与冻结 Schema（AGENTS.md"Frozen Contract"条、draft §10） | 表类即 Pydantic 类，模糊 storage/models.py 与 screening/schema.py 的既定边界 | 边界天然清晰 |

## 四、关键论证

1. **SQLModel 的核心卖点在本项目不存在。** 它解决的问题是把 API 请求/响应 Schema 与 ORM 表合一，主要服务 FastAPI。本项目是 CLI 单用户系统，权威 Pydantic Schema 的职责是约束 LLM 输出并导出冻结契约（`screening/schema.py`），draft §10 已经把 storage/models.py 与它分开。让表类同时是 Pydantic 模型，反而制造"表模型能否当契约用"的诱惑，正是 AGENTS.md"不维护第二份手写字段定义"要防的混合。

2. **"免费校验"对持久层行不成立。** SQLModel `table=True` 模型构造时绕过 Pydantic 校验（#1837），维护者自己建议校验用单独的非 table 模型。而本项目的校验语义本来就规定在两层：模型输出经权威 Pydantic Schema + 业务规则；入库经 repository。SQLModel 在这两层都不增益，只留下 Pydantic 元类机制的复杂度。

3. **mypy strict 与 Python 3.14 是硬门槛，不是偏好。** 项目 CI 跑 mypy strict（锁 1.18+），SQLAlchemy 2.0 typed ORM 是唯一有官方"无插件过 strict"声明的选项；SQLModel 有活跃的 strict 检查器问题。项目 Python 上界 <3.15、当前解释器 3.14.4，数据模型关系密集（论文→版本→发现记录→制品→证据），SQLModel #1765（TYPE_CHECKING 可空前向引用在 3.14 抛错、无官方回应）是直接命中的风险；SQLAlchemy 2.0.45 已在稳定线修复同类 3.14 注解问题。

4. **依赖耦合方向与项目诉求相反。** 项目因契约层需要而主动跟踪 Pydantic 升级（已锁 2.13.x）；SQLModel 历史上多次出现"新 Pydantic 小版本 → SQLModel 滞后修复"（0.0.24、0.0.26 均为此类），且把 SQLAlchemy 锁死在 `<2.1.0`。加这一层等于给两条活跃依赖链各加一个闸门，违背 AGENTS.md"除非明显简化当前需求，否则不新增依赖"。

5. **实际表定义很快下沉为 SQLAlchemy 写法。** 受控枚举要存 `.value` 需 `sa_type=Enum(..., values_callable=...)`；强标识复合唯一、指纹索引、JSON 原始条目、`Uuid` 类型（SQLite 下 CHAR(32)、PostgreSQL 下 uuid，正好满足归档讨论保留的 PG 迁移余地）都需要转义口。写完一圈 `sa_column` 后得到的是 SQLAlchemy 模型加一层语法糖。

6. **反向风险很低。** 两者共享同一套 SQLAlchemy metadata 与 Alembic 迁移：如果 V2 真引入 FastAPI 服务层并想统一 Schema/表，届时再评估 SQLModel，已写的 migration 与数据库完全兼容，不存在锁死。

## 五、SQLModel 的合理优势与重新评估条件

如实列出对冲因素：

- 简单表定义样板略少（`id: int | None = Field(default=None, primary_key=True)` 一行）；
- 注解风格与团队已有的 Pydantic 习惯一致；
- `model_dump()` 序列化顺手——但本项目报告必须经 `reports/queries.py` 从事实重建，不靠 ORM 行自序列化。

重新评估的触发条件（任一成立再议）：V2 真的需要**通用表级 CRUD 管理界面**且接受绕过领域规则；SQLModel 发布 1.0、放开 SQLAlchemy 2.1 并修复 3.14 关系注解问题；或项目放弃 mypy strict。注意"引入 Web 前端/FastAPI"本身**不构成**触发条件，见 §5.1。

### 5.1 前置推论：V2/V3 做前端展示与页面交互，结论会变吗？

**不会。** 前端带来的是**新增一层**（HTTP API + 命令/响应 Schema），不改变存储层选型的任何前提：

1. **"一模型两用"在 FastAPI 场景下也会缩水。** SQLModel 官方 FastAPI 教程自己就是表模型 + 独立 `HeroCreate`/`HeroPublic`/`HeroUpdate`（https://sqlmodel.tiangolo.com/tutorial/fastapi/ ）；FastAPI 把 `response_model` 定位为校验、文档与**字段过滤**的安全边界，生产实践默认 ORM 实体与 API DTO 分离（https://fastapi.tiangolo.com/tutorial/response-model/ ）。于是 SQLModel 的剩余收益只是"表模型用 Pydantic 风格语法定义"，而 §四.3/§四.4 的代价原封不动。
2. **本项目的 API 形状天然与"表即 Schema"冲突。** 论文无单一 status 字段，列表页/详情页是跨事实投影（等价于 `reports/queries.py` 的服务）；校准可见性硬门槛要求**所有展示查询**过 `calibration/visibility.py`，不能直接序列化 ORM 行；写侧操作（合并、人工决定、请求精读）是命令 + 审计事件，不是表 CRUD。通用 CRUD 管理界面在本项目里甚至是危险品——会绕过 supersede、合并链和审计不变量。
3. **框架中立性。** V2/V3 未必选 FastAPI（Litestar 自带 SQLAlchemy 集成，Django 是另一套 ORM 世界）；直接用 SQLAlchemy 让存储层不与 Web 框架选择耦合。选了非 FastAPI 框架时，SQLModel 剩余卖点归零。
4. **若前端带来并发压力**，真正的变化是评估 PostgreSQL（归档讨论已预留此路），而 SQLAlchemy 的方言抽象正是那条路径的载体；彼时 SQLModel 仍锁 `<2.1.0`。
5. **届时应重新以当时的版本事实评估**（SQLModel 或已 1.0、放开 2.1、修复新 Python 注解问题），但上述 1–2 条是结构性理由，不随版本消失。

因此 V2/V3 前端的正确增量是：新增 `api/` 层（FastAPI 或届时选型）+ 命令/响应 Pydantic DTO + 复用既有查询/可见性服务；storage 层与本次选型结论不动。

## 六、若采纳：落地要点（阶段 A）

- 依赖：`sqlalchemy>=2.0.45,<2.1`（2.1 落地前不升线）+ `alembic`；不引入 SQLModel、不引入其他序列化辅助库（`MappedAsDataclass` 或显式转换函数即可覆盖报告侧需要）。
- `Base(DeclarativeBase)` 的 `metadata = MetaData(naming_convention=...)` 先于一切模型定义建立（Alembic autogenerate 对未命名约束不可靠，两边同理；来源：https://alembic.sqlalchemy.org/en/latest/autogenerate.html 、https://docs.sqlalchemy.org/en/20/core/constraints.html ）。
- 枚举：`sqlalchemy.Enum(..., values_callable=lambda e: [m.value for m in e], native_enum=False)` 存受控 vocabulary 的 value，保证 DB 内容稳定、SQLite/PostgreSQL 一致。
- 标识与时间：`Uuid` 类型 + UTC 存储，避免 SQLite 方言渗透（满足归档讨论的 PG 迁移余地，但按 draft 该余地不是 V1 需求）。
- 业务校验仍在 repository/服务层，不指望 ORM 行校验；与"`--help` 不写库""外部调用不持事务"等既有规则正交。
- 决策落定时新增一条 ADR（本调研文档作为其依据），并把锁定版本写入阶段 A 验收证据。

## 七、来源清单

- SQLModel release notes：https://sqlmodel.tiangolo.com/release-notes/ （0.0.31 日期与破坏性变更、历史节奏）
- SQLModel pyproject：https://github.com/fastapi/sqlmodel/blob/main/pyproject.toml （Beta 分类、`SQLAlchemy >=2.0.14,<2.1.0`、`pydantic>=2.11.0`、3.14 classifier）
- SQLModel #1837：https://github.com/fastapi/sqlmodel/issues/1837 （table=True 绕过校验）
- SQLModel #1765：https://github.com/fastapi/sqlmodel/discussions/1765 （Python 3.14 PEP 649 Relationship 问题）
- SQLModel #1932：https://github.com/fastapi/sqlmodel/discussions/1932 （严格类型检查器边缘问题）
- SQLModel features：https://sqlmodel.tiangolo.com/features/ （转义口定位与"继承 Pydantic 校验"表述）
- SQLModel 官方 FastAPI 教程：https://sqlmodel.tiangolo.com/tutorial/fastapi/ （表模型与 Create/Public/Update 分离模型的官方用法）
- FastAPI response_model 文档：https://fastapi.tiangolo.com/tutorial/response-model/ （响应模型作为校验与字段过滤边界）
- SQLAlchemy 2.0 changelog：https://docs.sqlalchemy.org/en/21/changelog/changelog_20.html （2.0.45、Python 3.14 修复）
- SQLAlchemy 2.1 changelog / 下载页：https://docs.sqlalchemy.org/en/21/changelog/changelog_21.html 、https://www.sqlalchemy.org/download.html （2.1 节奏、Python ≥3.11、greenlet 可选）
- SQLAlchemy mypy 支持文档：https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html （typed ORM 过 strict、旧插件废弃且仅兼容至 mypy 1.10.1）
- SQLAlchemy dataclasses：https://docs.sqlalchemy.org/en/20/orm/dataclasses.html
- Alembic autogenerate：https://alembic.sqlalchemy.org/en/latest/autogenerate.html ；约束命名：https://docs.sqlalchemy.org/en/20/core/constraints.html
