import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import LedgerEntryType, SettlementRail


class SettlementRouteRequest(BaseModel):
    decision_id: uuid.UUID


class RepaymentRequest(BaseModel):
    profile_id: uuid.UUID
    amount_ghs: float
    paid_at: datetime | None = None


class LedgerEntryOut(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    decision_id: uuid.UUID | None
    entry_type: LedgerEntryType
    amount_ghs: float
    occurred_at: datetime
    rail: SettlementRail | None
    due_at: datetime | None
    repaid: bool | None
    on_time: bool | None
