"""标准恢复冷进程:报告只读重建;禁网络/模型/宿主准入/原根读取。"""

import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    root, output = Path(sys.argv[1]), Path(sys.argv[2])
    forbidden = tuple(sys.argv[4:])

    def guard(event: str, args: tuple[object, ...]) -> None:
        if event == "open" and args and isinstance(args[0], (str, bytes)):
            path = str(args[0])
            if any(path == p or path.startswith(p + "/") for p in forbidden):
                raise AssertionError("original/private input forbidden")
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
    from paper_radar.experiment.reports import Reports
    from paper_radar.experiment.validation import validate_all

    def inventory() -> dict[str, str]:
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        }

    before = inventory()
    validate_all(root / "database.sqlite3", root)
    service = Reports(root / "database.sqlite3", root, output)
    receipt = service.rebuild(sys.argv[3])
    assert service.verify(sys.argv[3]) == receipt
    (historical,) = service.history()
    assert historical.report_id == sys.argv[3]
    assert historical.entries[0].version_id
    assert (
        historical.entries[0].basis["authorization"]["version_id"]
        == historical.entries[0].version_id
    )
    assert inventory() == before
    assert not (root / "logs").exists()
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
