"""暴露清单标准恢复冷进程;拒绝网络、模型及原根/配置。"""

import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    root, output = Path(sys.argv[1]), Path(sys.argv[2])
    exports = sys.argv[3].split(",")
    forbidden = tuple(sys.argv[4:])

    def guard(event: str, args: tuple[object, ...]) -> None:
        if event == "open" and args and isinstance(args[0], (str, bytes)):
            path = str(args[0])
            if any(path == item or path.startswith(item + "/") for item in forbidden):
                raise AssertionError("original/config input forbidden")
        if event in {"socket.__new__", "subprocess.Popen", "os.system"}:
            raise AssertionError("network/execution forbidden")
        if (
            event == "import"
            and args
            and (
                str(args[0]).split(".")[0]
                in {"docling", "torch", "openai", "anthropic", "pypdfium2"}
                or str(args[0]).startswith(
                    (
                        "paper_radar.pi_execution",
                        "paper_radar.read_execution",
                        "paper_radar.experiment.preflight",
                    )
                )
            )
        ):
            raise AssertionError("model/host admission forbidden")

    sys.addaudithook(guard)
    from paper_radar.experiment.exposure import Exposures
    from paper_radar.experiment.validation import validate_all

    def inventory() -> dict[str, str]:
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        }

    before = inventory()
    validate_all(root / "database.sqlite3", root)
    service = Exposures(root / "database.sqlite3", root)
    result = []
    for export_id in exports:
        receipt = service.write(export_id, output)
        assert (output / str(receipt["relative_path"])).read_bytes() == service.payload(
            export_id
        )
        result.append(receipt)
    assert inventory() == before
    assert not (root / "logs").exists()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
