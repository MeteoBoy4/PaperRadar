"""版式编排与渲染共享的安全错误,不依赖任一上层模块。"""

class LayoutError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"{reason}：版式操作停止；核对当前样本、明确正文三元组及所有者六项结论；"
            "缺渲染依赖请准备锁定 extra，否决不能覆盖，材料可显式重建。"
        )


