"""真实完整入口在 A3 最终发布和前置漂移时不能继承历史成功。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import run_full_verification
from tests.a2_full_support import repository_copy
from tests.a3_acceptance_support import fake_checks


@pytest.mark.parametrize("failure", ["interrupt", "io"])
def test_real_entry_final_a3_publication_failure_preserves_all_previous_conclusions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = root / "verification-runs"
    output.mkdir()
    historical = output / "historical.a3.json"
    historical.write_bytes(b'{"status":"passed","a3_verified":true}')
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import os,sys
from pathlib import Path
from scripts.a2_full_acceptance import main
original=os.link
published={{}}
def fail(source,target):
    if str(target).endswith('.a3.json'):
        assert len(published)==3
        assert all(path.read_bytes()==raw for path,raw in published.items())
        raise {"KeyboardInterrupt" if failure == "interrupt" else "OSError"}()
    original(source,target)
    published[Path(target)]=Path(target).read_bytes()
os.link=fail
try:
    code=main()
except (KeyboardInterrupt,OSError):
    assert len(published)==3
    assert all(path.read_bytes()==raw for path,raw in published.items())
    sys.exit(3)
sys.exit(code)
""",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert historical.read_bytes() == b'{"status":"passed","a3_verified":true}'
    assert list(output.glob("*.a3.json")) == [historical]
    assert not list(output.glob("*.tmp"))
    assert all(
        json.loads(path.read_bytes())["status"] == "passed"
        for pattern in ("*.a1.json", "*.a2.json", "*.a2-full.json")
        for path in output.glob(pattern)
    )


@pytest.mark.parametrize("replaced", ["receipt", "predecessor"])
def test_a3_rechecks_bound_bytes_before_final_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replaced: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = tmp_path / "runs"
    original = Path.read_bytes
    observed = 0
    suffix = ".pytest.json" if replaced == "receipt" else ".a2-full.json"

    def replace_after_read(path: Path) -> bytes:
        nonlocal observed
        raw = original(path)
        if path.parent == output and path.name.endswith(suffix):
            observed += 1
            # A3 capture+parse已读完后替换;回执此前还有完整A2的3次读取。
            trigger = 5 if replaced == "receipt" else 2
            if observed == trigger:
                path.write_bytes(b'{"PRIVATE_REPLACEMENT":true}')
        return raw

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    run_full_verification(root, output)
    path = next(output.glob("*.a3.json"))
    result = json.loads(path.read_bytes())
    assert result["status"] == "failed"
    assert not result["a3_verified"]
    assert "binding_mismatch" in {reason["code"] for reason in result["reasons"]}
    assert "PRIVATE_REPLACEMENT" not in path.read_text()
