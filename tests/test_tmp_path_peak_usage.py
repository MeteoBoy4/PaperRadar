"""真实 pytest 会话及时释放通过用例,并保留失败诊断。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent


def test_passed_cases_release_payload_before_next_case_and_keep_failure(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "conftest.py").write_bytes((root / "tests/conftest.py").read_bytes())
    (suite / "test_payload.py").write_text(
        dedent(
            """\
            import json
            from pathlib import Path
            import pytest

            @pytest.mark.parametrize("case", range(6))
            def test_payload(tmp_path, case):
                payload = tmp_path / "payload"
                payload.write_bytes(b"x" * 1024 * 1024)
                usage = sum((path / "payload").stat().st_size for path in
                            tmp_path.parent.iterdir() if not path.is_symlink()
                            and (path / "payload").is_file())
                with (Path(__file__).parent / "observations.jsonl").open("a") as out:
                    out.write(json.dumps({"case": case, "path": str(tmp_path),
                                          "usage": usage}) + "\\n")
                assert usage <= 2 * 1024 * 1024, "passed payloads accumulate"

            def test_diagnostic(tmp_path):
                (tmp_path / "diagnostic").write_text("intentional failure evidence")
                (tmp_path / "diagnostic").chmod(0o444)
                tmp_path.chmod(0o555)
                (Path(__file__).parent / "failed-path").write_text(str(tmp_path))
                pytest.fail("intentional diagnostic failure")
            """
        ),
        encoding="utf-8",
    )
    temporary = tmp_path / "sessions"
    temporary.mkdir(mode=0o700)
    environment = dict(os.environ)
    for key in ("PAPER_RADAR_TEST_RECEIPT", "PAPER_RADAR_TEST_RUN_ID"):
        environment.pop(key, None)
    environment["PYTEST_DEBUG_TEMPROOT"] = str(temporary)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-c",
            str(root / "pyproject.toml"),
            str(suite / "test_payload.py"),
        ],
        cwd=suite,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "1 failed, 6 passed" in result.stdout, result.stdout + result.stderr
    observations = [
        json.loads(line)
        for line in (suite / "observations.jsonl").read_text().splitlines()
    ]
    assert [row["case"] for row in observations] == list(range(6))
    assert max(row["usage"] for row in observations) == 1024 * 1024
    assert all(not Path(row["path"]).exists() for row in observations)
    failed = Path((suite / "failed-path").read_text())
    assert (failed / "diagnostic").read_text() == "intentional failure evidence"
    assert (failed / "diagnostic").stat().st_mode & 0o777 == 0o444
