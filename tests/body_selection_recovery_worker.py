"""标准恢复后移动根的冷进程验证;禁止网络、SDK、模型和原根。"""

import json
import sys
from pathlib import Path


def main() -> None:
    batch, target, moved, expected_file = map(Path, sys.argv[1:5])
    forbidden = tuple(sys.argv[5:])
    expected = json.loads(expected_file.read_text())

    def guard(event: str, args: tuple[object, ...]) -> None:
        if event in {"socket.__new__", "subprocess.Popen", "os.system"}:
            raise AssertionError("external_execution_forbidden")
        if (
            event in {"open", "sqlite3.connect", "os.listdir", "os.scandir"}
            and args
            and isinstance(args[0], str)
        ):
            path = args[0]
            if any(path == item or path.startswith(item + "/") for item in forbidden):
                raise AssertionError("original_root_forbidden")
        if (
            event == "import"
            and args
            and str(args[0]).split(".")[0]
            in {"docling", "torch", "pypdfium2", "openai", "anthropic"}
        ):
            raise AssertionError("SDK_forbidden")

    sys.addaudithook(guard)
    from paper_radar.backup import restore_backup, verify_contents
    from paper_radar.body import BodyService
    from paper_radar.body.selection import BodySelections
    from paper_radar.experiment.exposure import Exposures
    from paper_radar.experiment.reports import Reports
    from paper_radar.experiment.validation import validate_all

    restored = restore_backup(batch, target)
    target.rename(moved)
    database = moved / "database.sqlite3"
    body = BodyService(database, moved)
    body.validate_all()
    validate_all(database, moved)
    selected = BodySelections(database, moved).history()
    assert [s.model_dump(mode="json") for s in selected] == expected["selections"]
    assert body.current_body(expected["paper"]).identity == selected[-1].identity
    assert (
        Exposures(database, moved).payload(expected["export_id"]).decode()
        == expected["export"]
    )
    reports = Reports(database, moved, moved.with_name("rebuilt-views"))
    assert reports.receipt(expected["report_id"]) == expected["report"]
    assert reports.rebuild(expected["report_id"]) == expected["report"]
    verify_contents(moved, restored.manifest)
    assert (
        "ordinary_consumption_denied"
        in body.facts(
            expected["paper"], identity=selected[-1].identity, ordinary=True
        ).reasons
    )
    print("body selection recovered with old report and exposure scope")


if __name__ == "__main__":
    main()
