import re

from app.models.enums import SourceType

# Stand-in for the real partner adapters in Section 7 (MNO / utility / bank APIs).
# A hackathon prototype has no live provider connection, so a token/receipt is
# accepted if it matches the shape that provider actually issues — this is the
# same tier-1 confidence the spec describes ("confirms a real, paying address or
# transaction without a smartphone or camera"), just backed by a format check
# instead of a live lookup.
_REFERENCE_SHAPES: dict[SourceType, str] = {
    SourceType.utility: r"\d{4}-\d{4}-\d{4}-\d{4}-\d{4}",  # ECG/Ghana Water token
    SourceType.momo: r"[A-Z]{2}\d{6}\.\d{4}\.[A-Z0-9]{6}",  # MoMo txn reference
    SourceType.bank: r"[A-Z0-9]{6,20}",
    SourceType.payment_gateway: r"[A-Za-z0-9_-]{6,40}",
}

# Exact-match: the whole submitted value must be a valid reference (verify_token).
_EXACT_PATTERNS = {k: re.compile(rf"^{v}$") for k, v in _REFERENCE_SHAPES.items()}

# Search-within-text: same shape, but looked for anywhere in a block of OCR'd
# text rather than requiring the whole string to match (find_reference_in_text).
_SEARCH_PATTERNS = {k: re.compile(rf"\b{v}\b") for k, v in _REFERENCE_SHAPES.items()}


def verify_token(source_type: SourceType, value: str) -> bool:
    pattern = _EXACT_PATTERNS.get(source_type)
    if pattern is None:
        return False
    return bool(pattern.match(value.strip()))


def _search_with_digit(pattern: re.Pattern[str], text: str) -> str | None:
    """Like pattern.search, but skips matches with no digit anywhere in them.
    The bank/payment_gateway shapes are loose enough that a plain word (a
    company name, a section heading) can satisfy them on its own — real
    reference codes always contain at least one digit, so this filters out
    that class of false positive without tightening the shape itself."""
    for match in pattern.finditer(text):
        if any(char.isdigit() for char in match.group(0)):
            return match.group(0)
    return None


def find_reference_in_text(source_type: SourceType, text: str) -> str | None:
    """Scan OCR'd document text for a substring matching the provider's
    reference format (used for Tier 2 document verification, as opposed to
    verify_token's exact match against a single manually-entered value)."""
    pattern = _SEARCH_PATTERNS.get(source_type)
    if pattern is None:
        return None
    return _search_with_digit(pattern, text)


def find_reference_across_types(
    text: str, exclude: SourceType | None = None
) -> dict[SourceType, str]:
    """Scan OCR'd text against every source type's shape, not just one - used
    to build a "did you mean" hint when the requested source_type finds
    nothing, since that usually means the wrong source_type was submitted for
    this document rather than a genuinely unreadable one."""
    matches: dict[SourceType, str] = {}
    for source_type, pattern in _SEARCH_PATTERNS.items():
        if source_type == exclude:
            continue
        found = _search_with_digit(pattern, text)
        if found:
            matches[source_type] = found
    return matches
