"""受控原因; 底层异常、进程输出及 URL 不进入诊断。"""

from typing import Literal

SupplyReason = Literal[
    "export_conflict",
    "export_evidence_collision",
    "export_failed",
    "adapter_versions_mixed",
    "selection_version_mismatch",
    "install_unavailable",
    "selection_missing",
    "retention_exceeded",
    "request_invalid",
    "adapter_missing",
    "snapshot_invalid",
    "database_unavailable",
    "upgrade_required",
    "supply_corrupt",
    "evidence_unresolved",
    "material_limit",
    "material_unreadable",
    "material_invalid",
    "material_conflict",
    "lock_unsupported",
    "integrity_missing",
    "integrity_conflict",
    "engines_mismatch",
    "engines_unsupported",
    "source_forbidden",
    "proxy_invalid",
    "download_failed",
    "download_limit",
    "redirect_limit",
    "process_failed",
    "process_timeout",
    "process_output_limit",
    "node_checksum_mismatch",
    "node_version_mismatch",
    "npm_version_mismatch",
    "pi_version_mismatch",
    "entry_invalid",
    "platform_mismatch",
    "unsafe_path",
    "unsafe_root",
    "root_foreign",
    "root_unowned_nonempty",
    "filesystem_unsupported",
    "space_insufficient",
    "archive_limit",
    "archive_unsafe",
    "tree_invalid",
    "tree_link_unsafe",
    "tree_special_file",
    "publication_conflict",
    "publication_failed",
    "already_prepared_use_rebuild",
    "concurrent_supply_conflict",
    "concurrent_tree_conflict",
    "startup_side_effect",
    "installed_material_changed",
    "supply_reference_invalid",
    "supply_not_found",
    "prepare_failed",
    "tree_mismatch",
    "verify_failed",
    "rebuild_failed",
    "operation_interrupted",
    "failure_record_failed",
]

GUIDANCE: dict[SupplyReason, str] = {
    "export_conflict": "导出目标含异字节、链接或特殊条目；请保留原文件并选择空目标。",
    "export_evidence_collision": (
        "D5 证据摘要前 16 位冲突；请保留数据库并核对证据，不能覆盖或改名。"
    ),
    "export_failed": (
        "材料导出未完成；请检查安全文件能力、目录权限及空间后重试，同字节文件会跳过。"
    ),
    "adapter_versions_mixed": (
        "槽版本不一致，当前无任何可激活供给；请显式选择全部槽版本一致的快照。"
    ),
    "selection_version_mismatch": (
        "当前供给与所给快照的全部已选槽不匹配；请显式 activate 匹配供给与快照。"
    ),
    "install_unavailable": "无最近通过且现场完整的安装实例；请 rebuild 后再 activate。",
    "selection_missing": "尚无当前执行选择；请显式 activate 匹配供给与快照。",
    "retention_exceeded": (
        "实际安装树超过四棵保留上限；请检查保留保护并显式生成清理计划。"
    ),
    "request_invalid": (
        "请求字段、类型或 D5 不合法；请按 pi-supply 契约修正严格 YAML/JSON。"
    ),
    "adapter_missing": "指定快照没有该 adapter 槽；请明确选择已登记槽与快照。",
    "snapshot_invalid": (
        "快照引用不存在、不唯一或无法完整加载；请运行 config snapshots list 核对。"
    ),
    "database_unavailable": (
        "数据库不可用或事务未提交；请检查路径、权限与完整性后重试。"
    ),
    "upgrade_required": (
        "数据库未达到当前版本；请先运行 paper-radar db upgrade --database。"
    ),
    "supply_corrupt": "固定供给事实损坏；请保留数据库并检查材料、清单及引用闭包。",
    "evidence_unresolved": "D5 基线或证据不可回查；请引用冻结前已存在的材料或检查。",
    "material_limit": "小型材料超过 4 MiB 上限；请缩小证据文件。",
    "material_unreadable": "材料无法读取；请检查请求相对证据路径及权限。",
    "material_invalid": "官方 JSON 材料格式不受支持；请检查该精确 release。",
    "material_conflict": (
        "配对材料的版本、依赖或 override 冲突；请保留材料并核对官方 release。"
    ),
    "lock_unsupported": "仅支持 lockfile v3 的固定 registry 包；请检查官方锁文件。",
    "integrity_missing": "包缺少可验证 sha512；请取得同 release 的校验依据。",
    "integrity_conflict": "锁与 release 完整性依据冲突；请停止安装并核对上游材料。",
    "engines_mismatch": "Node 不满足 Pi engines；请选择兼容的精确 Node/bundled npm。",
    "engines_unsupported": (
        "engines 超出精确版本或单一 >= 子集；请核对 release，不能猜测兼容性。"
    ),
    "source_forbidden": "下载来源不在固定官方白名单；请检查材料，不支持镜像。",
    "proxy_invalid": (
        "代理格式无效或包含凭据；请显式提供无 userinfo 的 http/https 代理。"
    ),
    "download_failed": "官方材料下载失败；请检查网络与显式代理后重试。",
    "download_limit": "下载超过大小上限；请核对精确 release，不会继续安装。",
    "redirect_limit": "官方下载跳转过多；请检查来源，不能扩展白名单绕过。",
    "process_failed": "独立 Node/npm/Pi 检查失败；请核对工具链与固定材料。",
    "process_timeout": "独立程序执行超时并已终止；请检查资源或网络后重试。",
    "process_output_limit": (
        "程序输出超过上限并已终止；请核对 release，不回显原始输出。"
    ),
    "node_checksum_mismatch": (
        "Node 请求摘要、同版 SHASUMS 或归档不一致；请核对官方校验依据。"
    ),
    "node_version_mismatch": "独立 Node 实测版本不符；请核对官方归档。",
    "npm_version_mismatch": "Node 自带 npm 实测版本不符；请修正请求，不另装 npm。",
    "pi_version_mismatch": "安装 Pi 的身份或版本不符；请核对 adapter 与官方材料。",
    "entry_invalid": "运行入口无效或越界；请核对已安装包 bin 声明。",
    "platform_mismatch": "运行平台与 Linux x86_64/glibc 声明不符；请在支持平台准备。",
    "unsafe_path": "路径含符号链接或不安全条目；请选择独立普通目录。",
    "unsafe_root": "根目录互相包含或安装根含数据库；请提供分离的实际根路径。",
    "root_foreign": "安装根归属另一数据库或标记损坏；请使用本库独立安装根。",
    "root_unowned_nonempty": "未归属安装根不是空目录；请保留残留并选择新的空根。",
    "filesystem_unsupported": "安装根不在支持的本地文件系统；请使用本机普通文件系统。",
    "space_insufficient": "可用空间低于 512 MiB 预检下限；请释放空间后重试。",
    "archive_limit": "Node 解包超过 1 GiB 上限；请核对归档。",
    "archive_unsafe": (
        "归档含越界路径、链接、特殊文件或不支持格式；请核对官方 Node 归档。"
    ),
    "tree_invalid": "安装树无法完整读取；请保留现场并检查目录权限和条目。",
    "tree_link_unsafe": "运行树链接越界；请核对安装材料，不会发布。",
    "tree_special_file": "运行树含特殊文件；请核对安装材料，不会发布。",
    "publication_conflict": "发布位置或未完成意图与本次树不一致；请保留残留人工核对。",
    "publication_failed": "本地不覆盖发布失败；请检查文件系统、空间和权限。",
    "already_prepared_use_rebuild": (
        "相同固定材料已准备；请使用后续 rebuild，不可修改 D5 重新冻结。"
    ),
    "concurrent_supply_conflict": (
        "并发相同材料得到不同清单；请保留现场核对 D5 和树身份。"
    ),
    "concurrent_tree_conflict": "并发既有实例树不符；请检查现场并按既有清单重建。",
    "startup_side_effect": "无模型启动改变运行树或写入会话；请检查该 Pi release。",
    "installed_material_changed": "npm 改变了固定 package 或派生锁；请检查该工具链。",
    "supply_reference_invalid": "供给引用必须是完整小写 64 位 ID；请从 list 复制。",
    "supply_not_found": "未找到供给；请核对数据库并运行 pi supply list。",
    "prepare_failed": "本地准备步骤失败；请检查材料类型、空间和目录权限后重试。",
    "tree_mismatch": "现场完整树与冻结预期不符；请保留旧树并使用 rebuild 重建新实例。",
    "verify_failed": "本地核验步骤失败；请检查目录权限并使用 rebuild 重建。",
    "rebuild_failed": "固定材料重建失败；请检查资源与权限后重试，旧实例保留。",
    "operation_interrupted": "操作中断；历史事实保留，请检查现场并重试。",
    "failure_record_failed": "执行失败且失败审计未能保存；请检查数据库可写性后重试。",
}


class SupplyError(Exception):
    def __init__(
        self, reason: SupplyReason, *, execution_reason: SupplyReason | None = None
    ) -> None:
        self.reason = reason
        self.execution_reason = execution_reason
        suffix = f" execution_reason={execution_reason}" if execution_reason else ""
        super().__init__(f"[{reason}] {GUIDANCE[reason]}{suffix}")
