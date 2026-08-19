"""Extracts an amount (and, best-effort, a date) from OCR'd receipt text.

This is deliberately separate from provider_verification.py: that module
answers "does this text contain a reference code shaped like provider X
issues" (a yes/no format check). This module answers a harder question -
"which of the possibly several GHS figures on this document is what was
actually paid" - which needs real disambiguation, not a single regex.

A real receipt (see the ClickInsure test case) often prints more than one
amount: an insurance premium of GHS 6,000 and a "total amount paid" of
GHS 557 are both real numbers on the same document, and only one of them is
what actually left this person's pocket. Picking the wrong one would feed
the scoring engine a number 10x too large - worse than finding nothing.
"""

import re
from datetime import datetime, timezone

_AMOUNT_PATTERN = re.compile(r"GHS\s*([\d,]+\.\d{2})", re.IGNORECASE)

# Higher score wins when more than one amount is found on the document.
# Ties (equal score) keep the first one encountered in reading order.
_PRIORITY_KEYWORDS: list[tuple[str, int]] = [
    ("total amount paid", 4),
    ("amount paid", 4),
    ("total paid", 4),
    ("amount due", 2),
    ("total", 2),
    ("balance", 1),
]

_MONTHS = {
    name: i
    for i, name in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
    )
}
_DATE_PATTERN = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b"
)


def extract_amount(text: str) -> tuple[float, str] | None:
    """Returns (amount, the line it was found on) for the best candidate, or
    None if no GHS-denominated figure was found at all."""
    candidates: list[tuple[int, float, str]] = []
    for line in text.splitlines():
        lowered = line.lower()
        priority = 0
        for keyword, score in _PRIORITY_KEYWORDS:
            if keyword in lowered:
                priority = max(priority, score)
        for match in _AMOUNT_PATTERN.finditer(line):
            amount = float(match.group(1).replace(",", ""))
            candidates.append((priority, amount, line.strip()))

    if not candidates:
        return None

    best_priority, best_amount, best_line = max(candidates, key=lambda c: c[0])
    return best_amount, best_line


def extract_date(text: str) -> datetime | None:
    """Best-effort "DD Month YYYY" parse (matches the date format on the
    receipts we've tested against). Returns None rather than guessing when
    nothing matches - callers should fall back to the upload time, not a
    fabricated date."""
    match = _DATE_PATTERN.search(text)
    if not match:
        return None

    day_str, month_str, year_str = match.groups()
    month = _MONTHS.get(month_str.lower()[:3])
    if month is None:
        return None

    try:
        return datetime(int(year_str), month, int(day_str), tzinfo=timezone.utc)
    except ValueError:
        return None
