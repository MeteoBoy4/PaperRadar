"""唯一真实下载/进程实现;测试只替换这两个 I/O seam。"""

from __future__ import annotations

import contextlib
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin

import httpx

from paper_radar.pi_supply.errors import SupplyError
from paper_radar.pi_supply.source_policy import checked_proxy, checked_url


class Downloader(Protocol):
    def fetch(self, url: str, *, limit: int, proxy: str | None) -> bytes: ...


class Runner(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        limit: int,
    ) -> bytes: ...


class HttpDownloader:
    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def fetch(self, url: str, *, limit: int, proxy: str | None) -> bytes:
        checked_proxy(proxy)
        try:
            with httpx.Client(
                trust_env=False,
                proxy=proxy,
                follow_redirects=False,
                timeout=httpx.Timeout(30, connect=10),
                transport=self.transport,
            ) as client:
                for _ in range(6):
                    checked_url(url)
                    with client.stream("GET", url) as response:
                        if response.is_redirect:
                            target = response.headers.get("location")
                            if not target:
                                raise SupplyError("download_failed")
                            url = checked_url(urljoin(url, target))
                            continue
                        if response.status_code != 200:
                            raise SupplyError("download_failed")
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            if len(raw) + len(chunk) > limit:
                                raise SupplyError("download_limit")
                            raw.extend(chunk)
                        return bytes(raw)
        except (httpx.HTTPError, OSError, ValueError):
            raise SupplyError("download_failed") from None
        raise SupplyError("redirect_limit")


class ProcessRunner:
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        limit: int,
    ) -> bytes:
        """并发消费两条管道、限制合计输出;任何中断终止整个进程组。"""
        try:
            child = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                umask=0o022,
            )
        except OSError:
            raise SupplyError("process_failed") from None
        output = bytearray()
        total = 0
        try:
            assert child.stdout is not None and child.stderr is not None
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ, True)
                selector.register(child.stderr, selectors.EVENT_READ, False)
                deadline = time.monotonic() + timeout
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise SupplyError("process_timeout")
                    for key, _ in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        total += len(chunk)
                        if total > limit:
                            raise SupplyError("process_output_limit")
                        if key.data:
                            output.extend(chunk)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SupplyError("process_timeout")
                try:
                    status = child.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    raise SupplyError("process_timeout") from None
                if status != 0:
                    raise SupplyError("process_failed")
                return bytes(output)
        except OSError:
            raise SupplyError("process_failed") from None
        finally:
            # Includes cancellation while a descendant keeps the output pipes open.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            if child.stdout:
                child.stdout.close()
            if child.stderr:
                child.stderr.close()
