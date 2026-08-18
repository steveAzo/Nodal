import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import SourceType


class VerifyTokenRequest(BaseModel):
    profile_id: uuid.UUID
    source_type: SourceType
    value: str


class VerifyTokenResult(BaseModel):
    profile_id: uuid.UUID
    source_type: SourceType
    verified: bool
    tier: int
    verified_at: datetime | None
    message: str


class VerifyDocumentResult(BaseModel):
    profile_id: uuid.UUID
    source_type: SourceType
    verified: bool
    tier: int
    verified_at: datetime | None
    extracted_reference: str | None
    cross_matched_tier1: bool
    message: str
