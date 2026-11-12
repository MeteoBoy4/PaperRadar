"""两正式消费者的三个准入检查点;不接收外部证据或授予回调。"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from paper_radar.config.owner_waiver import OwnerWaiverError, owner_waiver
from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.protected_observer import request_observation_refresh
from paper_radar.live_evidence.service import AdmissionRequest, request_time_tick
from paper_radar.pi_execution.admission import EvidenceBinding
from paper_radar.pi_execution.admission_guard import AdmissionGuard
from paper_radar.pi_execution.current_binding import (
    build_admission_request,
    diagnose_observation_failure,
    recheck_admission_request,
)
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_supply import SupplyError


class PreclaimAdmissionDenied(Exception):
    """穿过业务事务的拒绝信号,避免被误分类为档案库损坏。"""


@dataclass(frozen=True, slots=True)
class WaivedRequest:
    """执行绑定的当次豁免令牌,不是 AdmissionRequest 或证据。"""

    binding: EvidenceBinding


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
        try:
            self.waiver = owner_waiver(database, now=now())
        except OwnerWaiverError:
            raise ExecutionError("evidence_missing") from None
        self.owner_waived = self.waiver.enabled
        self.guard.owner_waived = self.owner_waived

    def _recheck_waiver(self) -> None:
        try:
            if owner_waiver(self.database, now=self.now()) != self.waiver:
                raise ExecutionError("evidence_missing")
        except OwnerWaiverError:
            raise ExecutionError("evidence_missing") from None

    def before_prepare(
        self, binding: EvidenceBinding
    ) -> AdmissionRequest | WaivedRequest:
        """凭据刷新前构造并检查完整身份。"""
        self._recheck_waiver()
        if self.owner_waived:
            return WaivedRequest(binding)
        try:
            request_observation_refresh()
            request = build_admission_request(
                self.database,
                binding,
                use=self.guard.use,
                credentials_dir=self.credentials_dir,
                now=self.now(),
            )
        except LedgerError as error:
            self.guard.note_observation_failure(
                error,
                diagnose_observation_failure(
                    self.database,
                    binding,
                    use=self.guard.use,
                    credentials_dir=self.credentials_dir,
                    now=self.now(),
                    error=error,
                ),
            )
            raise ExecutionError("evidence_missing") from None
        except SupplyError:
            raise ExecutionError("evidence_missing") from None
        request = replace(request, evidence_after=self.waiver.strict_since)
        self.guard.check(request, now=self.now())
        return request

    def after_prepare(
        self, original: AdmissionRequest | WaivedRequest, binding: EvidenceBinding
    ) -> AdmissionRequest | WaivedRequest:
        """准备后重绑、复核;仅成功后请求固定 helper 时间打点。"""
        rebound = self.before_prepare(binding)
        if type(rebound) is not type(original) or rebound.binding != original.binding:
            raise ExecutionError("evidence_mismatch")
        if self.owner_waived:
            return rebound
        if not request_time_tick():
            raise ExecutionError("evidence_missing")
        return rebound

    def preclaim(self, request: AdmissionRequest | WaivedRequest) -> None:
        """领取事务内只读复核;业务帧验证由调用者在此前执行。"""
        try:
            self._recheck_waiver()
            if isinstance(request, WaivedRequest):
                if not self.owner_waived:
                    raise ExecutionError("evidence_missing")
                return
            recheck_admission_request(request, now=self.now())
            self.guard.check(request, now=self.now())
        except LedgerError as error:
            self.guard.note_observation_failure(error)
            raise PreclaimAdmissionDenied from None
        except ExecutionError:
            raise PreclaimAdmissionDenied from None
