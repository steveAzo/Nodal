from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.models.enums import ConsentStatus, SourceType


def get_active_consent(db: Session, profile_id: UUID, source_type: SourceType) -> Consent | None:
    """The consent gate every ingestion path (live events, receipts) shares:
    an active, unexpired consent for this profile + source_type, or None.
    Flips a stale-but-still-'active' row to 'expired' as a side effect,
    rather than leaving that until something else notices."""
    now = datetime.now(timezone.utc)
    consent = db.scalar(
        select(Consent).where(
            Consent.profile_id == profile_id,
            Consent.source_type == source_type,
            Consent.status == ConsentStatus.active,
        )
    )
    if consent is not None and consent.expires_at <= now:
        consent.status = ConsentStatus.expired
        db.commit()
        return None
    return consent
