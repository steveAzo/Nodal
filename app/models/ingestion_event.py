import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IngestionEvent(Base):
    """A normalised event landing from a partner adapter (Section 7, Layer 3).

    Stores derived fields only (amount, direction, reference id) rather than
    raw partner payloads, per the data-minimisation rule in Section 11.
    """

    __tablename__ = "ingestion_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.profile_id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    consent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consents.consent_id", ondelete="RESTRICT"), nullable=False
    )

    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    amount_ghs: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
