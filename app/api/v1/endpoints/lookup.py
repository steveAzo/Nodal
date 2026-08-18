import enum

from fastapi import APIRouter

from app.models import enums as enums_module

router = APIRouter(tags=["lookup"])

# One-line description per enum, for frontend readability. Adding a new enum
# class to app/models/enums.py picks it up here automatically (see below) —
# this dict is the only thing that needs a manual touch per phase, and the
# endpoint will still work (just with an empty description) if it's skipped.
_DESCRIPTIONS: dict[str, str] = {
    "NodeType": "Which of the three onboarding nodes a profile belongs to.",
    "OnboardingChannel": "How a profile was onboarded.",
    "IdentityVerificationStatus": "Whether identity was self-reported or confirmed against the Ghana Card API.",
    "SourceType": "The kind of data feed a Source represents.",
    "EntryMethod": "How a Source's value was captured.",
    "ConsentScope": "Named purposes a consent grant can cover (or explicitly exclude).",
    "ConsentStatus": "Lifecycle state of a Consent record.",
    "EventType": "Kind of event landing through the ingestion pipeline.",
    "Direction": "Cash-flow direction of a transaction event.",
    "BusinessActivityLabel": "Categorical read of the Business Activity sub-score.",
    "RiskLabel": "Shared low/medium/high band, used for both fraud_risk and internal risk-tier banding.",
}

# Not a Python enum (it's a plain 0-4 int column), but frontend needs the
# meaning of each value just as much — included here so there's one place to
# look up every "what are the valid values / what do they mean" question.
_TIERS = {
    "description": "Per-source verification tier (Section 2). Confidence is per data "
    "category, not global - a profile can be Tier 3 on momo and Tier 0 on utility "
    "at once.",
    "values": {
        0: "Self-declared - National ID only, self-reported details. Low confidence.",
        1: "Token/receipt verified - a token or reference ID matched against the "
        "issuing provider's expected format. Medium confidence.",
        2: "Document uploaded - OCR-extracted from a photo/PDF, cross-matched against "
        "Tier 1 data where available. Medium-high confidence.",
        3: "API-linked - live consented connection to the provider. High, live-updating "
        "confidence.",
        4: "Multi-source reconciled - two or more Tier 3 sources cross-validated against "
        "each other. Highest confidence.",
    },
}


@router.get("/lookup/enums")
def list_enums() -> dict:
    """All enums used across the API, plus the tier model, in one place -
    the reference doc for the frontend so valid request/response values
    don't have to be reverse-engineered from backend source."""
    result: dict[str, dict] = {}
    for name in dir(enums_module):
        obj = getattr(enums_module, name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum) and obj is not enum.Enum:
            result[name] = {
                "description": _DESCRIPTIONS.get(name, ""),
                "values": [member.value for member in obj],
            }
    return {"enums": result, "tiers": _TIERS}
