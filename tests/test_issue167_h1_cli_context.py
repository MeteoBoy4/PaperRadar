"""Unbound D1: generator CLI must preserve explicitly requested lineage."""

import json
import subprocess
import sys
from pathlib import Path


def test_cli_forwards_explicit_retry_context_before_sealing(tmp_path: Path) -> None:
    context = {
        "kind": "additional_attempt_after_unknown",
        "predecessor_run_id": "7c93ab04d615",
        "predecessor_manifest_sha256": "b" * 64,
        "predecessor_ledger_sha256": "c" * 64,
        "additional_attempts": 1,
    }
    source = tmp_path / "retry.json"
    source.write_text(json.dumps(context))
    target = tmp_path / "review"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.issue167_h1_auto_bundle",
            str(target),
            "--run-id",
            "5d91ab26c704",
            "--retry-context",
            str(source),
        ],
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert json.loads((target / "retry-context.json").read_text()) == context
