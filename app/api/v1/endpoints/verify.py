import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import EntryMethod, SourceType
from app.models.profile import Profile, Source
from app.schemas.verification import VerifyDocumentResult, VerifyTokenRequest, VerifyTokenResult
from app.services import ocr
from app.services.provider_verification import find_reference_across_types, find_reference_in_text
from app.services.provider_verification import verify_token as check_token

router = APIRouter(tags=["verification"])

_MAX_DOCUMENT_BYTES = 8 * 1024 * 1024  # 8 MB


@router.post("/verify/token", response_model=VerifyTokenResult)
def verify_token(payload: VerifyTokenRequest, db: Session = Depends(get_db)) -> VerifyTokenResult:
    source = db.scalar(
        select(Source).where(
            Source.profile_id == payload.profile_id,
            Source.source_type == payload.source_type,
            Source.entry_value == payload.value,
        )
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No source on this profile matches that source_type and value. "
            "Onboard the source first with this exact value.",
        )

    if not check_token(payload.source_type, payload.value):
        return VerifyTokenResult(
            profile_id=payload.profile_id,
            source_type=payload.source_type,
            verified=False,
            tier=source.tier,
            verified_at=None,
            message="Value does not match the expected format for this provider type.",
        )

    now = datetime.now(timezone.utc)
    source.tier = max(source.tier, 1)
    source.last_synced_at = now
    db.commit()

    return VerifyTokenResult(
        profile_id=payload.profile_id,
        source_type=payload.source_type,
        verified=True,
        tier=source.tier,
        verified_at=now,
        message="Token verified; source upgraded to Tier 1.",
    )


@router.post("/verify/document", response_model=VerifyDocumentResult)
async def verify_document(
    profile_id: uuid.UUID = Form(...),
    source_type: SourceType = Form(...),
    provider: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VerifyDocumentResult:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Document exceeds the 8MB limit for this prototype.",
        )

    try:
        extracted_text = ocr.extract_text(file_bytes)
    except ocr.UnsupportedDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    reference = find_reference_in_text(source_type, extracted_text)
    existing_sources = db.scalars(
        select(Source).where(Source.profile_id == profile_id, Source.source_type == source_type)
    ).all()

    if reference is None:
        other_matches = find_reference_across_types(extracted_text, exclude=source_type)
        message = "Could not find a recognisable reference number on this document."
        if other_matches:
            suggestions = ", ".join(
                f"{st.value} ('{val}')" for st, val in other_matches.items()
            )
            message += (
                f" No {source_type.value}-shaped reference found, but this document has text "
                f"matching a different source_type: {suggestions}. Check you selected the right one."
            )
        return VerifyDocumentResult(
            profile_id=profile_id,
            source_type=source_type,
            verified=False,
            tier=max((s.tier for s in existing_sources), default=0),
            verified_at=None,
            extracted_reference=None,
            cross_matched_tier1=False,
            message=message,
        )

    cross_matched = any(s.entry_value == reference and s.tier >= 1 for s in existing_sources)
    # Reuse the cross-matched source if there is one, otherwise the first
    # existing source of this type, otherwise create a new one — same
    # one-connection-per-source-type assumption the ingest endpoint makes.
    target = next((s for s in existing_sources if s.entry_value == reference), None)
    target = target or (existing_sources[0] if existing_sources else None)

    now = datetime.now(timezone.utc)
    if target is None:
        target = Source(
            profile_id=profile_id,
            source_type=source_type,
            provider=provider,
            entry_method=EntryMethod.document_upload,
            tier=2,
            entry_value=reference,
        )
        db.add(target)
    else:
        target.tier = max(target.tier, 2)
        # Only overwrite entry_value with the newly extracted reference — don't
        # store the raw OCR text itself, per the data-minimisation rule (Section 11).
        target.entry_value = reference
    target.last_synced_at = now
    db.commit()

    message = (
        "Document OCR'd and cross-matched against an existing Tier 1 record; source upgraded to Tier 2."
        if cross_matched
        else "Document OCR'd; no prior Tier 1 record to cross-match, accepted on its own. Source upgraded to Tier 2."
    )
    return VerifyDocumentResult(
        profile_id=profile_id,
        source_type=source_type,
        verified=True,
        tier=target.tier,
        verified_at=now,
        extracted_reference=reference,
        cross_matched_tier1=cross_matched,
        message=message,
    )
