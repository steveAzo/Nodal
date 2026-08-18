import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ConsentStatus, SourceType

if TYPE_CHECKING:
    from app.models.profile import Profile, Source


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Consent(Base):
    __tablename__ = "consents"

    consent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.profile_id", ondelete="CASCADE"), nullable=False
    )

    source_type: Mapped[SourceType] = mapped_column(String(20), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    excluded_scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(
        String(20), nullable=False, default=ConsentStatus.active
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped["Profile"] = relationship(back_populates="consents")
    sources: Mapped[list["Source"]] = relationship(back_populates="consent")
