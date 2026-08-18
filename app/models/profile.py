import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    EntryMethod,
    IdentityVerificationStatus,
    NodeType,
    OnboardingChannel,
    SourceType,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    node_type: Mapped[NodeType] = mapped_column(String(20), nullable=False)
    onboarding_channel: Mapped[OnboardingChannel] = mapped_column(String(20), nullable=False)

    ghana_card_number: Mapped[str] = mapped_column(String(30), nullable=False)
    identity_verification_status: Mapped[IdentityVerificationStatus] = mapped_column(
        String(20), nullable=False, default=IdentityVerificationStatus.self_declared
    )

    # only set when onboarding_channel == agent_assisted
    assisting_agent_id: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    sources: Mapped[list["Source"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    consents: Mapped[list["Consent"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (CheckConstraint("tier BETWEEN 0 AND 4", name="ck_source_tier_range"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.profile_id", ondelete="CASCADE"), nullable=False
    )

    source_type: Mapped[SourceType] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[int] = mapped_column(nullable=False, default=0)
    entry_method: Mapped[EntryMethod] = mapped_column(String(20), nullable=False)

    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    consent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consents.consent_id", ondelete="SET NULL"), nullable=True
    )

    # raw entry value (token id / receipt id / doc reference) — not a full statement,
    # per the data-minimisation rule in the spec (Section 11)
    entry_value: Mapped[str | None] = mapped_column(String(255), nullable=True)

    profile: Mapped["Profile"] = relationship(back_populates="sources")
    consent: Mapped["Consent | None"] = relationship(back_populates="sources")
