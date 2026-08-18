import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LedgerEntry(Base):
    """Ledger & Repayment Tracking Service (Section 7, layer 8).

    One row per disbursement or repayment event. Disbursement-only fields
    (rail, due_at, repaid) and repayment-only fields (on_time) are nullable
    rather than split into two tables - the two entry types are few enough
    fields apart that one table stays simpler to query for "this profile's
    full ledger history" than a join would.
    """

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.profile_id", ondelete="CASCADE"), nullable=False
    )
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decisions.decision_id", ondelete="SET NULL"), nullable=True
    )

    entry_type: Mapped[str] = mapped_column(String(15), nullable=False)
    amount_ghs: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Disbursement-only:
    rail: Mapped[str | None] = mapped_column(String(15), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repaid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Repayment-only:
    on_time: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
