from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import EntryMethod, SourceType
from app.models.ingestion_event import IngestionEvent
from app.models.profile import Profile, Source
from app.schemas.ingestion import IngestEventOut, IngestEventRequest
from app.services.consent_check import get_active_consent
from app.services.passport_service import recalculate_passport

router = APIRouter(tags=["ingestion"])


@router.post("/ingest/{source_type}", response_model=IngestEventOut, status_code=status.HTTP_201_CREATED)
def ingest_event(
    source_type: SourceType,
    payload: IngestEventRequest,
    db: Session = Depends(get_db),
) -> IngestEventOut:
    profile = db.get(Profile, payload.profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    now = datetime.now(timezone.utc)
    consent = get_active_consent(db, payload.profile_id, source_type)

    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No active consent for source_type '{source_type.value}' on this profile. "
            "Grant consent via POST /v1/consent before ingesting.",
        )

    # A live event arriving through this endpoint is, by definition, an
    # API-linked connection — Tier 3 in the progressive verification model
    # (Section 2) — regardless of what tier the source was manually entered at.
    source = db.scalar(
        select(Source).where(Source.profile_id == payload.profile_id, Source.source_type == source_type)
    )
    if source is None:
        source = Source(
            profile_id=payload.profile_id,
            source_type=source_type,
            provider=payload.provider,
            entry_method=EntryMethod.api_link,
            tier=3,
            consent_id=consent.consent_id,
        )
        db.add(source)
        db.flush()
    else:
        source.tier = max(source.tier, 3)
        source.consent_id = consent.consent_id
    source.last_synced_at = now

    event = IngestionEvent(
        profile_id=payload.profile_id,
        source_id=source.id,
        consent_id=consent.consent_id,
        event_type=payload.event_type,
        direction=payload.direction,
        amount_ghs=payload.amount_ghs,
        reference=payload.reference,
        occurred_at=payload.occurred_at,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # A new Tier 3+ transaction is a recalculation trigger (Section 10);
    # Section 12 requires this to land under 5s, so it's fired inline rather
    # than queued.
    recalculate_passport(db, profile)

    return IngestEventOut.model_validate(event)
