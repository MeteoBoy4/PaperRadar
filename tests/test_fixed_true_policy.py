"""D1:固定 true 工具封印身份与 policy source 关联;不执行或加载策略。"""

from pathlib import Path

import pytest

from paper_radar.live_evidence.placement_build import render_profiles
from paper_radar.pi_execution.placement_protocol import PlacementProgram


@pytest.mark.parametrize("resolved", ["/usr/bin/true", "/usr/bin/gnutrue"])
def test_fixed_true_rule_uses_resolved_fixed_tool_identity(
    monkeypatch: pytest.MonkeyPatch, resolved: str
) -> None:
    original = Path.resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        return (
            Path(resolved) if path == Path("/usr/bin/true") else original(path, strict)
        )

    monkeypatch.setattr(Path, "resolve", resolve)
    program = PlacementProgram(
        1001, 1001, Path("/opt/pi"), Path("/var/lib/pi"), Path("/opt/pi.lock"), None
    )
    source = render_profiles(
        program,
        resolver_source=Path("/run/paper-radar/resolv.conf"),
        resolver_target=Path("/run/systemd/resolve/stub-resolv.conf"),
    )
    post = source.split("profile paperradar-placement-post-v1", 1)[1]
    assert f'  "{resolved}" ix,' in post
    assert len([line for line in post.splitlines() if line.endswith(" ix,")]) == 3
    assert "** ix" not in source


def test_frozen_source_and_binary_bind_same_fixed_true_identity(tmp_path: Path) -> None:
    import json

    from paper_radar.live_evidence.placement_build import freeze_placement
    from paper_radar.live_evidence.placement_policy import read_placement_policy
    from tests.site_collector_support import site_configuration

    root = tmp_path / "runtime"
    (root / "resources").mkdir(parents=True)
    (root / "resources/resolv.conf").write_bytes(b"nameserver 192.0.2.1\n")
    freeze_placement(
        root, site_configuration(tmp_path), Path(__file__).resolve().parents[1]
    )
    sealed = read_placement_policy(root)
    assert sealed is not None
    true = json.loads((root / "placement/security.json").read_bytes())["tools"][
        "/usr/bin/true"
    ]
    assert sealed.build["format_version"] == 2
    assert sealed.build["fixed_true_exec"] == true
    assert (
        f'  "{true["resolved"]}" ix,'
        in (root / "placement/apparmor.source").read_text()
    )
    assert sealed.policy.binary.startswith(
        b"\x04\x08\x00version\x00\x02\x05\x00\x00\x00"
    )


@pytest.mark.parametrize("drift", ["rule", "missing-association", "identity"])
def test_new_policy_association_drift_refuses_even_with_updated_member_hash(
    tmp_path: Path, drift: str
) -> None:
    import hashlib
    import json

    from paper_radar.live_evidence.placement_policy import read_placement_policy
    from tests.test_live_apparmor_lifecycle import policy_root

    root = policy_root(tmp_path / "runtime")
    security = json.loads((root / "placement/security.json").read_bytes())
    security["tools"]["/usr/bin/true"]["resolved"] = "/usr/bin/gnutrue"
    (root / "placement/security.json").write_text(json.dumps(security))
    program = {
        "runtime": "/usr/libexec/paperradar/live-evidence-runtime",
        "install": "/opt/pi",
    }
    (root / "placement/program.json").write_text(json.dumps(program))
    source = "\n".join(
        [
            '  "/usr/libexec/paperradar/live-evidence-runtime/python/bin/python3" ix,',
            '  "/opt/pi/node/bin/node" ix,',
            '  "/usr/bin/gnutrue" ix,',
        ]
    )
    if drift == "rule":
        source = source.replace('"/usr/bin/gnutrue"', '"/usr/bin/true"')
    (root / "placement/apparmor.source").write_text(source)
    build = json.loads((root / "placement/build.json").read_bytes())
    build["format_version"] = 2
    if drift != "missing-association":
        build["fixed_true_exec"] = dict(security["tools"]["/usr/bin/true"])
        if drift == "identity":
            build["fixed_true_exec"]["sha256"] = "f" * 64
    for field, name in (
        ("source_sha256", "apparmor.source"),
        ("program_sha256", "program.json"),
    ):
        build[field] = hashlib.sha256(
            (root / "placement" / name).read_bytes()
        ).hexdigest()
    (root / "placement/build.json").write_text(json.dumps(build))
    with pytest.raises(ValueError, match=r"^placement_seal_identity$"):
        read_placement_policy(root)
