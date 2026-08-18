from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.consent import Consent
from app.models.enums import ConsentStatus
from app.models.profile import Profile
from app.schemas.consent import ConsentOut, ConsentRequest

router = APIRouter(tags=["consent"])


@router.post("/consent", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
def grant_consent(payload: ConsentRequest, db: Session = Depends(get_db)) -> ConsentOut:
    profile = db.get(Profile, payload.profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    settings = get_settings()
    granted_at = datetime.now(timezone.utc)

    consent = Consent(
        profile_id=payload.profile_id,
        source_type=payload.source_type,
        scopes=[s.value for s in payload.scopes],
        excluded_scopes=[s.value for s in payload.excluded_scopes],
        granted_at=granted_at,
        expires_at=granted_at + timedelta(days=settings.consent_default_expiry_days),
        status=ConsentStatus.active,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return ConsentOut.model_validate(consent)


@router.delete("/consent/{consent_id}", response_model=ConsentOut)
def revoke_consent(consent_id: str, db: Session = Depends(get_db)) -> ConsentOut:
    consent = db.get(Consent, consent_id)
    if consent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent not found")

    # revoking stops future ingestion immediately; it must not retroactively alter
    # terms already issued under an active facility (Section 11) — status change only.
    consent.status = ConsentStatus.revoked
    consent.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(consent)
    return ConsentOut.model_validate(consent)
