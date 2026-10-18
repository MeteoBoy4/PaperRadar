"""真实 HTTP/进程适配器的有界 I/O, 网络只用 MockTransport。"""

import sys
from pathlib import Path

import httpx
import pytest

from paper_radar.pi_supply import SupplyError, list_supplies, prepare_supply
from paper_radar.pi_supply.transport import HttpDownloader, ProcessRunner
from tests.pi_supply_support import inputs


@pytest.mark.parametrize("failure", ["redirect", "oversized"])
def test_real_downloader_rejects_forbidden_hop_or_body(
    tmp_path: Path, failure: str
) -> None:
    source = inputs(tmp_path)
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if failure == "redirect":
            return httpx.Response(
                302, headers={"location": "https://SECRET.example/hidden"}
            )
        return httpx.Response(200, content=b"x" * (4 * 1024 * 1024 + 1))

    downloader = HttpDownloader(transport=httpx.MockTransport(handle))
    with pytest.raises(SupplyError) as caught:
        prepare_supply(
            source[0],
            source[1],
            "screening",
            source[2],
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=downloader,
            runner=source[4],
        )
    assert caught.value.reason == (
        "source_forbidden" if failure == "redirect" else "download_limit"
    )
    assert "SECRET" not in str(caught.value)
    assert len(seen) == 1
    assert list_supplies(source[0]) == ()


@pytest.mark.parametrize(
    "code,reason,timeout,limit",
    [
        (
            "import sys;sys.stderr.write('SECRET failure');sys.exit(1)",
            "process_failed",
            5,
            4096,
        ),
        ("import time;time.sleep(10)", "process_timeout", 1, 4096),
        ("print('SECRET' * 10000)", "process_output_limit", 5, 128),
    ],
)
def test_process_output_failure_and_timeout_are_bounded_and_redacted(
    tmp_path: Path,
    code: str,
    reason: str,
    timeout: int,
    limit: int,
) -> None:
    with pytest.raises(SupplyError) as caught:
        ProcessRunner().run(
            (sys.executable, "-c", code),
            cwd=tmp_path,
            env={},
            timeout=timeout,
            limit=limit,
        )
    assert caught.value.reason == reason
    assert "SECRET" not in str(caught.value)


def test_process_uses_fixed_umask(tmp_path: Path) -> None:
    result = ProcessRunner().run(
        (sys.executable, "-c", "import os;print(oct(os.umask(0)))"),
        cwd=tmp_path,
        env={},
        timeout=5,
        limit=4096,
    )
    assert result == b"0o22\n"


def test_real_http_path_with_allowed_redirect_does_not_inherit_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = inputs(tmp_path)
    monkeypatch.setenv("HTTPS_PROXY", "http://SECRET.invalid:1")
    original = "https://pi.dev/api/installer/releases/1.3.0/package.json"
    redirected = "https://pi.dev/api/installer/releases/1.3.0/paired-package.json"
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        seen.append(url)
        if url == original:
            return httpx.Response(302, headers={"location": redirected})
        return httpx.Response(
            200, content=source[3].content[original if url == redirected else url]
        )

    prepared = prepare_supply(
        source[0],
        source[1],
        "screening",
        source[2],
        tmp_path / "install",
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
        downloader=HttpDownloader(transport=httpx.MockTransport(handle)),
        runner=source[4],
    )
    assert list_supplies(source[0])[0].supply_id == prepared.supply_id
    assert redirected in seen
