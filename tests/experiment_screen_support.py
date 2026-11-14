"""B Screening 的合成供给/HTTP 接缝;不替换内部准入或权威接收。"""

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from typer.testing import Result

from paper_radar.config import compile_config
from paper_radar.pi_supply import activate_supply, prepare_supply
from tests.config_adapter_support import adapter_inputs
from tests.pi_execution_service_support import deny_default_live_io
from tests.pi_execution_support import PeerRun
from tests.pi_supply_support import Download, encoded
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_selection_cli import select
from tests.test_owner_live_waiver import command as waiver


@dataclass
class ScreenFixture:
    root: Path
    selection_id: str
    snapshot: str
    credentials: Path
    install: Path
    materials: Path
    view_id: str
    paper_id: str

    def screen(
        self, *, selection_id: str | None = None, receipt_id: str | None = None
    ) -> Result:
        return invoke(
            "screen",
            "--root",
            str(self.root),
            "--selection-id",
            selection_id or self.selection_id,
            "--snapshot",
            self.snapshot,
            "--credentials-dir",
            str(self.credentials),
            "--material-root",
            str(self.materials),
            "--install-root",
            str(self.install),
            *(["--receipt-id", receipt_id] if receipt_id is not None else []),
        )

    def egress(self, *, disabled: bool = False) -> Result:
        return invoke(
            "egress-authorize",
            "--root",
            str(self.root),
            "--snapshot",
            self.snapshot,
            "--stage",
            "boundary",
            "--stage",
            "value",
            "--reason",
            "PRIVATE_EGRESS_REASON",
            *(["--disabled"] if disabled else []),
        )


def screen_fixture(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "normal",
    boundary: str = "in_scope",
    inferable: bool = True,
) -> ScreenFixture:
    from paper_radar.pi_execution import isolation, resources

    root, state, fetch = feed
    state["order"] = [1, 2]
    check = fetch("screen-round")
    candidates = invoke(
        "candidates", "--root", str(root), "--check-id", check["check_id"]
    )
    assert candidates.exit_code == 0, candidates.output
    view = json.loads(candidates.stdout)["view_id"]
    chosen = select(root, view, "screen-select", "--position", "1")
    assert chosen.exit_code == 0, chosen.output
    selection = json.loads(chosen.stdout)
    source = tmp_path / "source"
    source.mkdir()
    settings, adapter, _ = adapter_inputs(source)
    adapter.write_text(adapter.read_text().replace("1.1.0", "1.4.0"))
    models_path = settings.parent / "models/models-v1.yaml"
    models = yaml.safe_load(models_path.read_text())
    models["format_version"] = 2
    for slot in ("screening",):
        models[slot]["provider"] = "openai"
        models[slot].pop("temperature", None)
        models[slot].pop("top_p", None)
        models[slot]["sampling"] = "provider_default"
    models_path.write_text(yaml.safe_dump(models))
    shutil.copytree(settings.parent, root / "config", dirs_exist_ok=True)
    shutil.copytree(source / "prompts", root / "prompts", dirs_exist_ok=True)
    shutil.copytree(source / "contracts", root / "contracts", dirs_exist_ok=True)
    database = root / "paper-radar.sqlite3"
    snapshot = compile_config(root / "config/settings.yaml", database)
    install, materials = tmp_path / "install", tmp_path / "materials"
    # Download 的 PI 常量只定义合成 release 版本;同步独立供给替身。
    from tests import pi_supply_support

    monkeypatch.setattr(pi_supply_support, "PI", "1.4.0")
    download = Download()
    (tmp_path / "evidence.txt").write_bytes(b"Synthetic supply evidence\n")
    request = tmp_path / "request.json"
    request.write_bytes(
        encoded(
            dict(
                format_version=1,
                node_version="22.19.0",
                npm_version="10.9.3",
                node_source="nodejs.org",
                node_sha256=download.node_sha256,
                platform=dict(os="linux", arch="x86_64", libc="glibc"),
                d5=dict(
                    decision="unknown",
                    basis="Synthetic first supply",
                    baseline_supply_id=None,
                    evidence=[dict(kind="evidence_file", path="evidence.txt")],
                ),
            )
        )
    )
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    (credentials / "auth.json").write_text(
        json.dumps(dict(token="oauth-test-only-sensitive-sentinel"))
    )
    peer = Path(__file__).with_name("pi_execution_rpc_peer.py").read_text()
    peer = (
        peer.replace("__MODE__", mode)
        .replace("__DATABASE__", str(database))
        .replace("__CREDENTIALS__", str(credentials / "auth.json"))
    )
    invalid_condition = (
        'if MODE == "output_invalid" and os.environ["OPENAI_API_KEY"] == '
        '"oauth-test-only-sensitive-sentinel":'
    )
    peer = peer.replace('if MODE == "output_invalid":', invalid_condition)
    if mode == "value_invalid":
        peer = peer.replace(
            invalid_condition,
            "if '\"stage\":\"value\"' in command['message'] and "
            "os.environ['OPENAI_API_KEY'] == 'oauth-test-only-sensitive-sentinel':",
        )
    peer = peer.replace('"boundary":"in_scope"', f'"boundary":"{boundary}"')
    if not inferable:
        peer = peer.replace(
            '"reuse_feasibility_reason_zh":"需要调整数据处理流程。"',
            '"reuse_feasibility_reason_zh":"当前输入不足以判断复用可行性。"',
        ).replace(
            '"reuse_feasibility_inferable":true', '"reuse_feasibility_inferable":false'
        )
    prepared = prepare_supply(
        database,
        snapshot.snapshot_id,
        "screening",
        request,
        install,
        data_root=root / "blobs",
        config_root=root / "config",
        material_root=materials,
        downloader=download,
        runner=PeerRun(peer),
    )
    activate_supply(database, prepared.supply_id, snapshot.snapshot_id)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setattr(resources, "EXECUTION_CWD", cwd)
    monkeypatch.setattr(
        isolation,
        "_RUNTIME_PATHS",
        (*isolation._RUNTIME_PATHS, Path(sys.base_prefix) / "lib/python3.14"),
    )
    deny_default_live_io(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
    )
    result = ScreenFixture(
        root,
        selection["selection_id"],
        snapshot.snapshot_id,
        credentials,
        install,
        materials,
        view,
        selection["paper_id"],
    )
    assert (
        waiver(database, "--enable", "--reason", "PRIVATE_WAIVER_REASON").exit_code == 0
    )
    assert result.egress().exit_code == 0
    return result
