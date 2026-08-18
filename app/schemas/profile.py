import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    EntryMethod,
    IdentityVerificationStatus,
    NodeType,
    OnboardingChannel,
    SourceType,
)


class SourceIn(BaseModel):
    source_type: SourceType
    provider: str
    entry_method: EntryMethod
    value: str | None = None
    tier: int = Field(default=0, ge=0, le=4)


class IdentityIn(BaseModel):
    ghana_card_number: str
    verification_status: IdentityVerificationStatus = IdentityVerificationStatus.self_declared


class OnboardingRequest(BaseModel):
    onboarding_channel: OnboardingChannel
    assisting_agent_id: str | None = None
    identity: IdentityIn
    sources: list[SourceIn] = Field(default_factory=list)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: SourceType
    provider: str
    tier: int
    entry_method: EntryMethod
    connected_at: datetime
    consent_id: uuid.UUID | None
    last_synced_at: datetime | None


class IdentityOut(BaseModel):
    ghana_card_number: str
    verification_status: IdentityVerificationStatus


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: uuid.UUID
    node_type: NodeType
    onboarding_channel: OnboardingChannel
    identity: IdentityOut
    created_at: datetime
    sources: list[SourceOut]

    @classmethod
    def from_model(cls, profile) -> "ProfileOut":
        return cls(
            profile_id=profile.profile_id,
            node_type=profile.node_type,
            onboarding_channel=profile.onboarding_channel,
            identity=IdentityOut(
                ghana_card_number=profile.ghana_card_number,
                verification_status=profile.identity_verification_status,
            ),
            created_at=profile.created_at,
            sources=[SourceOut.model_validate(s) for s in profile.sources],
        )
