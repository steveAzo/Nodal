from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.decision import Decision
from app.models.ledger import LedgerEntry
from app.models.profile import Profile
from app.schemas.ledger import LedgerEntryOut, RepaymentRequest, SettlementRouteRequest
from app.services.ledger import RepaymentError, SettlementError, record_repayment, route_settlement
from app.services.passport_service import recalculate_passport

router = APIRouter(tags=["ledger"])


def _to_out(entry: LedgerEntry) -> LedgerEntryOut:
    return LedgerEntryOut(
        id=entry.id,
        profile_id=entry.profile_id,
        decision_id=entry.decision_id,
        entry_type=entry.entry_type,
        amount_ghs=float(entry.amount_ghs),
        occurred_at=entry.occurred_at,
        rail=entry.rail,
        due_at=entry.due_at,
        repaid=entry.repaid,
        on_time=entry.on_time,
    )


@router.post("/settlement/route", response_model=LedgerEntryOut, status_code=status.HTTP_201_CREATED)
def settle_decision(payload: SettlementRouteRequest, db: Session = Depends(get_db)) -> LedgerEntryOut:
    decision = db.get(Decision, payload.decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")

    try:
        entry = route_settlement(db, decision)
    except SettlementError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return _to_out(entry)


@router.post("/ledger/repayment", response_model=LedgerEntryOut, status_code=status.HTTP_201_CREATED)
def post_repayment(payload: RepaymentRequest, db: Session = Depends(get_db)) -> LedgerEntryOut:
    profile = db.get(Profile, payload.profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    try:
        entry = record_repayment(db, profile, payload.amount_ghs, payload.paid_at)
    except RepaymentError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # A repayment event is a recalculation trigger (Section 10) - fire it
    # inline since there's no event bus/internal service mesh here yet.
    recalculate_passport(db, profile)

    return _to_out(entry)


@router.get("/ledger/{profile_id}", response_model=list[LedgerEntryOut])
def get_ledger(profile_id: str, db: Session = Depends(get_db)) -> list[LedgerEntryOut]:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    entries = db.scalars(
        select(LedgerEntry).where(LedgerEntry.profile_id == profile_id).order_by(LedgerEntry.occurred_at)
    ).all()
    return [_to_out(entry) for entry in entries]
