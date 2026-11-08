"""Independent D1: explicit IPv4-only reaches the sealed plan via real CLI."""

import json
import subprocess
import sys
from pathlib import Path


def test_cli_seals_ipv4_mode_and_explicit_predecessor(tmp_path: Path) -> None:
    context = {
        "kind": "additional_attempt_after_unknown",
        "predecessor_run_id": "a840c6d21e97",
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
            "d7a1309cb482",
            "--network-mode",
            "ipv4_only",
            "--retry-context",
            str(source),
        ],
        capture_output=True,
        check=True,
        timeout=10,
    )
    value = json.loads((target / "plan.json").read_text())
    assert value["network_mode"] == "ipv4_only"
    assert value["addresses"] == ["127.0.0.1"]
    assert json.loads((target / "retry-context.json").read_text()) == context
    worker = (target / value["unit"]).read_text()
    assert "RestrictAddressFamilies=AF_INET\n" in worker
    assert "AF_INET6" not in worker
    review = (target / "owner-review.md").read_text()
    assert "ipv4_only" in review
