"""一次fork的私有有界metadata通道;root不接触RPC、token或自由错误。"""

from __future__ import annotations

import ctypes
import os
import select
import signal
import socket
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Literal

from pydantic import Field

from paper_radar.live_evidence.model_manifest import ModelCell
from paper_radar.live_evidence.model_worker import ModelObservation, execute_model
from paper_radar.live_evidence.network_collection import (
    NetworkOutcome,
    execute_negative,
)
from paper_radar.live_evidence.receipt import (
    Digest,
    Identifier,
    WireModel,
    canonical_bytes,
)
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.llm.dispatch import CollectionReason, DispatchDenied

Stage = Literal["auth", "prepared", "model", "network", "result"]


class WorkerMessage(WireModel):
    case_id: Identifier
    sequence: int = Field(ge=1, le=4, strict=True)
    stage: Stage
    binding_sha256: Digest
    material_sha256: Digest
    pid: int = Field(default=0, ge=0, strict=True)
    start: int = Field(default=0, ge=0, strict=True)
    unit: str = Field(default="", pattern=r"^(|paperradar-[a-f0-9]{32}\.scope)$")
    model: ModelObservation | None = None
    network: NetworkOutcome | None = None


class Ack(WireModel):
    sequence: int = Field(ge=1, le=4, strict=True)
    accepted: bool
    reason: CollectionReason | None = None


def product_worker(
    site: SiteConfiguration,
    root: Path,
    cell: ModelCell | None,
    case_id: str,
    binding_sha: str,
    material_sha: str,
    handler: Callable[[WorkerMessage], None],
) -> ModelObservation | NetworkOutcome:
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    pid = os.fork()
    if pid == 0:
        parent.close()
        try:
            os.environ.clear()
            os.setgroups([])
            os.setresgid(site.product_gid, site.product_gid, site.product_gid)
            os.setresuid(site.product_uid, site.product_uid, site.product_uid)
            if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0):
                os._exit(2)
            # 不把root锁/账本文件描述符传给产品身份。
            keep = child.fileno()
            for value in os.listdir("/proc/self/fd"):
                descriptor = int(value)
                if descriptor > 2 and descriptor != keep:
                    with suppress(OSError):
                        os.close(descriptor)
            null = os.open("/dev/null", os.O_RDWR)
            for descriptor in (0, 1, 2):
                os.dup2(null, descriptor)
            os.close(null)
            sequence = 0
            child.settimeout(20)

            def exchange(
                stage: Stage, target_pid: int = 0, start: int = 0, unit: str = ""
            ) -> None:
                nonlocal sequence
                sequence += 1
                message = WorkerMessage(
                    case_id=case_id,
                    sequence=sequence,
                    stage=stage,
                    binding_sha256=binding_sha,
                    material_sha256=material_sha,
                    pid=target_pid,
                    start=start,
                    unit=unit,
                )
                child.sendall(canonical_bytes(message))
                ack = Ack.model_validate_json(child.recv(1025))
                if not ack.accepted:
                    raise DispatchDenied(ack.reason or "source_untrusted")
                if ack.sequence != sequence:
                    raise DispatchDenied("source_untrusted")

            worker_result: ModelObservation | NetworkOutcome
            if cell is None:
                worker_result = execute_negative(root, site, case_id, exchange)
            else:
                worker_result = execute_model(root, site, cell, exchange)
            sequence += 1
            child.sendall(
                canonical_bytes(
                    WorkerMessage(
                        case_id=case_id,
                        sequence=sequence,
                        stage="result",
                        binding_sha256=binding_sha,
                        material_sha256=material_sha,
                        model=worker_result
                        if isinstance(worker_result, ModelObservation)
                        else None,
                        network=worker_result
                        if isinstance(worker_result, NetworkOutcome)
                        else None,
                    )
                )
            )
            child.close()
            os._exit(0)
        except BaseException:
            os._exit(2)
    child.close()
    expected = 1
    result: ModelObservation | NetworkOutcome | None = None
    try:
        while result is None:
            if not select.select([parent], [], [], 330)[0]:
                raise DispatchDenied("interrupted")
            raw = parent.recv(8193)
            if not raw or len(raw) > 8192:
                raise DispatchDenied("source_untrusted")
            message = WorkerMessage.model_validate_json(raw)
            if (
                message.case_id != case_id
                or message.sequence != expected
                or message.binding_sha256 != binding_sha
                or message.material_sha256 != material_sha
            ):
                raise DispatchDenied("source_untrusted")
            expected += 1
            if message.stage == "result":
                if (message.model is None) == (message.network is None) or (
                    cell is None
                ) != (message.network is not None):
                    raise DispatchDenied("source_untrusted")
                result = message.model or message.network
            else:
                if message.model is not None or message.network is not None:
                    raise DispatchDenied("source_untrusted")
                try:
                    handler(message)
                except DispatchDenied as error:
                    parent.sendall(
                        canonical_bytes(
                            Ack(
                                sequence=message.sequence,
                                accepted=False,
                                reason=error.reason,
                            )
                        )
                    )
                else:
                    parent.sendall(
                        canonical_bytes(Ack(sequence=message.sequence, accepted=True))
                    )
        # 有界退出/EOF,不能仅凭一个结果包宣称worker已终止。
        if not select.select([parent], [], [], 3)[0] or parent.recv(8193):
            raise DispatchDenied("interrupted")
        _, status = os.waitpid(pid, 0)
        if status != 0:
            raise DispatchDenied("interrupted")
        return result
    except BaseException:
        with suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
        with suppress(ChildProcessError):
            os.waitpid(pid, 0)
        raise
    finally:
        parent.close()
