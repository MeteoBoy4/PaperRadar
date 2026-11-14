"""恢复冷进程仅回查持久 Read,不启动模型/SDK、不修改副本。"""

import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    root = Path(sys.argv[1])
    database = root / "database.sqlite3"

    def inventory() -> dict[str, str]:
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        }

    def guard(event: str, args: tuple[object, ...]) -> None:
        if (
            event == "import"
            and args
            and (
                str(args[0]).split(".")[0]
                in {"docling", "torch", "pypdfium2", "PIL", "openai", "anthropic"}
                or str(args[0]).startswith(
                    ("paper_radar.read_execution", "paper_radar.pi_execution")
                )
            )
        ):
            raise AssertionError("SDK forbidden")
        if event in {"socket.__new__", "subprocess.Popen", "os.system"}:
            raise AssertionError("network/model forbidden")

    sys.addaudithook(guard)

    from paper_radar.experiment.reading import analysis_payload
    from paper_radar.experiment.validation import validate_all
    from paper_radar.paper_trace import query_paper_trace
    from paper_radar.read_queries import ReadQueries
    from paper_radar.read_tasks import ReadTaskError

    before = inventory()
    validate_all(database, root)
    queries = ReadQueries(database, root)
    try:
        queries.analysis(sys.argv[4], ordinary=True)
    except ReadTaskError as error:
        assert error.reason == "ordinary_consumption_denied"
    else:
        raise AssertionError("experiment promoted")
    result = dict(
        trace=query_paper_trace(
            database, root, sys.argv[2], snapshot_id=sys.argv[3]
        ).safe_payload(),
        analysis=analysis_payload(database, root, sys.argv[4], snapshot_id=sys.argv[3]),
    )
    assert queries.evidence(sys.argv[4], "e000002")[0].text == "Exact source α = 2."
    assert inventory() == before
    assert not (root / "logs").exists()
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            default=lambda value: (
                value.model_dump(mode="json")
                if hasattr(value, "model_dump")
                else value.isoformat()
            ),
        )
    )


if __name__ == "__main__":
    main()
