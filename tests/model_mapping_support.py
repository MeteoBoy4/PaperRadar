"""#191 合成固定供给与 RPC 外部对端;不读任何凭据内容。"""

import shutil
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from paper_radar.config import compile_config
from paper_radar.experiment import ExperimentRoot
from paper_radar.pi_supply import activate_supply, prepare_supply
from tests import pi_supply_support
from tests.pi_execution_support import PeerRun


def invoke(*args: str) -> Result:
    return CliRunner().invoke(app, ["experiment", *args])


def prepared(
    root: Path, monkeypatch: pytest.MonkeyPatch, mode: str = "normal"
) -> list[str]:
    monkeypatch.setattr(pi_supply_support, "PI", "1.4.0")
    experiment = root / "experiment"
    assert invoke("init", "--root", str(experiment)).exit_code == 0
    layout = ExperimentRoot(experiment)
    source = pi_supply_support.inputs(root)
    settings = root / "config/settings.yaml"
    models_path = root / "config/models/models-v1.yaml"
    models = yaml.safe_load(models_path.read_text())
    models["format_version"] = 2
    models["version"] = "mapping-v1"
    models["screening"] = dict(
        provider="openai",
        model="screening-mapping-model",
        protocol="prompt_only",
        sampling="provider_default",
    )
    models["reading"] = {**models["screening"], "model": "reading-mapping-model"}
    models_path.with_name("mapping-v1.yaml").write_text(yaml.safe_dump(models))
    settings.write_text(settings.read_text().replace("models-v1", "mapping-v1"))
    adapter = root / "config/adapters/pi-v1.yaml"
    adapter.with_name("pi-read.yaml").write_text(
        adapter.read_text().replace("pi-v1", "pi-read").replace("low", "high")
    )
    settings.write_text(
        settings.read_text().replace("reading: pi-v1", "reading: pi-read")
    )
    for directory in ("config", "prompts", "contracts"):
        shutil.copytree(root / directory, experiment / directory, dirs_exist_ok=True)
    snapshot = compile_config(layout.settings, layout.database)
    peer = (
        Path(__file__)
        .with_name("model_mapping_rpc_peer.py")
        .read_text()
        .replace('"__MODE__"', repr(mode))
        .replace("__DATABASE__", str(root / "experiment/paper-radar.sqlite3"))
    )
    installation = prepare_supply(
        layout.database,
        snapshot.snapshot_id,
        "screening",
        source[2],
        experiment / "pi-install",
        data_root=layout.data_root,
        config_root=layout.config,
        material_root=experiment / "pi-materials",
        downloader=source[3],
        runner=PeerRun(peer),
    )
    activate_supply(layout.database, installation.supply_id, snapshot.snapshot_id)
    waiver = CliRunner().invoke(
        app,
        [
            "live-evidence",
            "owner-waiver",
            "--database",
            str(experiment / "paper-radar.sqlite3"),
            "--enable",
            "--reason",
            "PRIVATE_WAIVER",
        ],
    )
    assert waiver.exit_code == 0, waiver.output
    grant = invoke(
        "egress-authorize",
        "--root",
        str(experiment),
        "--snapshot",
        snapshot.snapshot_id,
        "--stage",
        "boundary",
        "--stage",
        "value",
        "--stage",
        "read",
        "--reason",
        "PRIVATE_EGRESS",
    )
    assert grant.exit_code == 0, grant.output
    cwd = root / "cwd"
    cwd.mkdir()
    credentials = root / "credentials"
    credentials.mkdir(mode=0o700)
    (credentials / "auth.json").write_text("UNREAD_SYNTHETIC_CREDENTIAL_SENTINEL")
    monkeypatch.setattr("paper_radar.pi_execution.resources.EXECUTION_CWD", cwd)
    monkeypatch.setattr(
        "paper_radar.pi_execution.auth.local_auth_entry", lambda install: install.pi
    )
    from paper_radar.pi_execution import isolation

    monkeypatch.setattr(
        isolation,
        "_RUNTIME_PATHS",
        (*isolation._RUNTIME_PATHS, Path(sys.base_prefix) / "lib/python3.14"),
    )
    return [
        "--root",
        str(experiment),
        "--snapshot",
        snapshot.snapshot_id,
        "--credentials-dir",
        str(credentials),
        "--material-root",
        str(experiment / "pi-materials"),
        "--install-root",
        str(experiment / "pi-install"),
    ]
