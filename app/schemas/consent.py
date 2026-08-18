import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConsentScope, ConsentStatus, SourceType


class ConsentRequest(BaseModel):
    profile_id: uuid.UUID
    source_type: SourceType
    scopes: list[ConsentScope] = Field(min_length=1)
    excluded_scopes: list[ConsentScope] = Field(default_factory=list)


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consent_id: uuid.UUID
    profile_id: uuid.UUID
    source_type: SourceType
    scopes: list[str]
    excluded_scopes: list[str]
    granted_at: datetime
    expires_at: datetime
    status: ConsentStatus
    revoked_at: datetime | None
