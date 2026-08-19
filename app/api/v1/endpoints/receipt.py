from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import Direction, EntryMethod, EventType, SourceType
from app.models.ingestion_event import IngestionEvent
from app.models.profile import Profile, Source
from app.schemas.receipt import ReceiptIngestResult
from app.services import ocr, receipt_extraction
from app.services.consent_check import get_active_consent
from app.services.passport_service import recalculate_passport

router = APIRouter(tags=["ingestion"])

_MAX_RECEIPT_BYTES = 8 * 1024 * 1024  # 8 MB, same cap as document verification


@router.post("/ingest/receipt", response_model=ReceiptIngestResult, status_code=status.HTTP_201_CREATED)
async def ingest_receipt(
    profile_id: str = Form(...),
    provider: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ReceiptIngestResult:
    """Lets a profile with no momo/bank/payment-gateway rails at all still
    build real transaction history - a photo of any receipt (a utility
    bill, a school-fees receipt, an insurance payment, anything with a
    printed GHS amount) becomes one outflow event feeding the same scoring
    pipeline a live API transaction would.

    Unlike /v1/verify/document, this doesn't just prove a source is real -
    it extracts an amount and records it as spend history. That's a bigger
    claim about the data, so it's gated behind the same active-consent check
    as any other ingestion path, not the lighter verification one.
    """
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    consent = get_active_consent(db, profile.profile_id, SourceType.receipt)
    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active consent for source_type 'receipt' on this profile. "
            "Grant consent via POST /v1/consent before uploading a receipt.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_RECEIPT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Receipt image exceeds the 8MB limit for this prototype.",
        )

    try:
        extracted_text = ocr.extract_text(file_bytes)
    except ocr.UnsupportedDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    found = receipt_extraction.extract_amount(extracted_text)
    if found is None:
        return ReceiptIngestResult(
            profile_id=profile.profile_id,
            success=False,
            provider=provider,
            amount_ghs=None,
            occurred_at=None,
            date_extracted=False,
            tier=None,
            message="Could not find a GHS amount on this receipt. A clearer photo, or one that "
            "prints the amount as 'GHS 000.00', is more likely to work.",
        )
    amount, matched_line = found

    extracted_date = receipt_extraction.extract_date(extracted_text)
    occurred_at = extracted_date or datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    source = db.scalar(
        select(Source).where(
            Source.profile_id == profile.profile_id,
            Source.source_type == SourceType.receipt,
            Source.provider == provider,
        )
    )
    if source is None:
        source = Source(
            profile_id=profile.profile_id,
            source_type=SourceType.receipt,
            provider=provider,
            entry_method=EntryMethod.document_upload,
            tier=2,
            consent_id=consent.consent_id,
        )
        db.add(source)
        db.flush()
    else:
        source.tier = max(source.tier, 2)
        source.consent_id = consent.consent_id
    source.last_synced_at = now

    # Data minimisation (Section 11): store the amount and the one matched
    # line for audit purposes, never the full OCR text.
    db.add(
        IngestionEvent(
            profile_id=profile.profile_id,
            source_id=source.id,
            consent_id=consent.consent_id,
            event_type=EventType.transaction,
            direction=Direction.out,
            amount_ghs=amount,
            reference=matched_line[:255],
            occurred_at=occurred_at,
        )
    )
    db.commit()

    recalculate_passport(db, profile)

    return ReceiptIngestResult(
        profile_id=profile.profile_id,
        success=True,
        provider=provider,
        amount_ghs=amount,
        occurred_at=occurred_at,
        date_extracted=extracted_date is not None,
        tier=source.tier,
        message=f"Recorded GHS {amount:,.2f} as spend evidence; source upgraded to Tier {source.tier}."
        + ("" if extracted_date else " Date not found on the receipt, used upload time instead."),
    )
