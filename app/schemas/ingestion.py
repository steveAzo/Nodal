import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Direction, EventType


class IngestEventRequest(BaseModel):
    profile_id: uuid.UUID
    provider: str
    event_type: EventType
    occurred_at: datetime
    amount_ghs: float | None = Field(default=None, ge=0)
    direction: Direction | None = None
    reference: str | None = None


class IngestEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    source_id: uuid.UUID
    consent_id: uuid.UUID
    event_type: EventType
    direction: Direction | None
    amount_ghs: float | None
    reference: str | None
    occurred_at: datetime
    ingested_at: datetime
