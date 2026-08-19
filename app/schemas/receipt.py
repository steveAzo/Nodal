import uuid
from datetime import datetime

from pydantic import BaseModel


class ReceiptIngestResult(BaseModel):
    profile_id: uuid.UUID
    success: bool
    provider: str
    amount_ghs: float | None
    occurred_at: datetime | None
    date_extracted: bool
    tier: int | None
    message: str
