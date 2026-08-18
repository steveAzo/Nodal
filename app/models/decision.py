import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Decision(Base):
    """One row per issued Decision object (Section 8.4). Append-only - a
    decision is never edited or deleted once issued, per the Section 11
    audit requirement ("every ... decision issued must be immutably logged").
    """

    __tablename__ = "decisions"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.profile_id", ondelete="CASCADE"), nullable=False
    )

    recommendation: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_ghs: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    duration_hours: Mapped[int] = mapped_column(nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(10), nullable=False)

    reasons: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    risk_flags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    issued_to_partner_id: Mapped[str] = mapped_column(String(50), nullable=False)
