"""两正式消费者的三个准入检查点;不接收外部证据或授予回调。"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.service import AdmissionRequest, request_time_tick
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.pi_execution.admission_guard import AdmissionGuard
from paper_radar.pi_execution.current_binding import (
    build_admission_request,
    recheck_admission_request,
)
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_supply import SupplyError


class PreclaimAdmissionDenied(Exception):
    """穿过业务事务的拒绝信号,避免被误分类为档案库损坏。"""


class AdmissionCheckpoints:
    def __init__(
        self,
        database: Path,
        credentials_dir: Path,
        guard: AdmissionGuard,
        now: Callable[[], datetime],
    ) -> None:
        self.database = database
        self.credentials_dir = credentials_dir
        self.guard = guard
        self.now = now

    def before_prepare(self, binding: EvidenceBinding) -> AdmissionRequest:
        """凭据刷新前构造并检查完整身份。"""
        try:
            request = build_admission_request(
                self.database,
                binding,
                use=self.guard.use,
                credentials_dir=self.credentials_dir,
                now=self.now(),
            )
        except LedgerError as error:
            self.guard.note_observation_failure(error)
            raise ExecutionError("evidence_missing") from None
        except SupplyError:
            raise ExecutionError("evidence_missing") from None
        self.guard.check(request, now=self.now())
        return request

    def after_prepare(
        self, original: AdmissionRequest, binding: EvidenceBinding
    ) -> AdmissionRequest:
        """准备后重绑、复核;仅成功后请求固定 helper 时间打点。"""
        rebound = self.before_prepare(binding)
        if rebound.binding != original.binding:
            raise ExecutionError("evidence_mismatch")
        if not request_time_tick():
            raise ExecutionError("evidence_missing")
        return rebound

    def preclaim(self, request: AdmissionRequest) -> None:
        """领取事务内只读复核;业务帧验证由调用者在此前执行。"""
        try:
            recheck_admission_request(request, now=self.now())
            self.guard.check(request, now=self.now())
        except LedgerError as error:
            self.guard.note_observation_failure(error)
            raise PreclaimAdmissionDenied from None
        except ExecutionError:
            raise PreclaimAdmissionDenied from None
