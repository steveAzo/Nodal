"""Ledger & Repayment Tracking Service + Settlement Orchestration Layer
(Section 7, layers 8-9). Records disbursement and repayment events, and
feeds repayment history back into the scoring engine - the flywheel
Section 10 describes but nothing before this phase actually populated.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.enums import EntryMethod, LedgerEntryType, RecommendationType, SettlementRail, SourceType
from app.models.ledger import LedgerEntry
from app.models.profile import Profile, Source


class SettlementError(Exception):
    pass


class RepaymentError(Exception):
    pass


def _ensure_nodal_ledger_source(db: Session, profile_id: UUID) -> None:
    """"Automatic once the agent has borrowed once - pulled from Nodal's own
    ledger" (Section 5). The platform's own ledger becomes a Tier 3 source
    the moment a facility is disbursed; no separate verification step."""
    now = datetime.now(timezone.utc)
    source = db.scalar(
        select(Source).where(Source.profile_id == profile_id, Source.source_type == SourceType.nodal_ledger)
    )
    if source is None:
        db.add(
            Source(
                profile_id=profile_id,
                source_type=SourceType.nodal_ledger,
                provider="Nodal",
                tier=3,
                entry_method=EntryMethod.api_link,
                last_synced_at=now,
            )
        )
    else:
        source.tier = max(source.tier, 3)
        source.last_synced_at = now


def route_settlement(db: Session, decision: Decision) -> LedgerEntry:
    if decision.recommendation != RecommendationType.approve:
        raise SettlementError(
            f"Decision {decision.decision_id} is '{decision.recommendation}', not 'approve' - "
            "nothing to settle."
        )

    already_settled = db.scalar(
        select(LedgerEntry).where(LedgerEntry.decision_id == decision.decision_id)
    )
    if already_settled is not None:
        raise SettlementError(f"Decision {decision.decision_id} has already been settled.")

    # Section 7's routing rule, enforced in code rather than left as a
    # policy note: every agent-facing disbursement is domestic. There is no
    # parameter or branch here that could select 'stablecoin' for this leg.
    now = datetime.now(timezone.utc)
    entry = LedgerEntry(
        profile_id=decision.profile_id,
        decision_id=decision.decision_id,
        entry_type=LedgerEntryType.disbursement,
        amount_ghs=decision.amount_ghs,
        rail=SettlementRail.domestic,
        occurred_at=now,
        due_at=now + timedelta(hours=decision.duration_hours),
        repaid=False,
    )
    db.add(entry)
    _ensure_nodal_ledger_source(db, decision.profile_id)

    db.commit()
    db.refresh(entry)
    return entry


def record_repayment(
    db: Session, profile: Profile, amount_ghs: float, paid_at: datetime | None
) -> LedgerEntry:
    disbursement = db.scalar(
        select(LedgerEntry)
        .where(
            LedgerEntry.profile_id == profile.profile_id,
            LedgerEntry.entry_type == LedgerEntryType.disbursement,
            LedgerEntry.repaid.is_(False),
        )
        .order_by(LedgerEntry.occurred_at.desc())
        .limit(1)
    )
    if disbursement is None:
        raise RepaymentError("No outstanding facility to repay for this profile.")

    paid_at = paid_at or datetime.now(timezone.utc)
    on_time = paid_at <= disbursement.due_at

    entry = LedgerEntry(
        profile_id=profile.profile_id,
        decision_id=disbursement.decision_id,
        entry_type=LedgerEntryType.repayment,
        amount_ghs=amount_ghs,
        occurred_at=paid_at,
        on_time=on_time,
    )
    db.add(entry)
    disbursement.repaid = True

    db.commit()
    db.refresh(entry)
    return entry
