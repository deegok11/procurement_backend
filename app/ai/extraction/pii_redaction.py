import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PiiPattern:
    label: str
    pattern: re.Pattern


# Order matters: GSTIN embeds a PAN-shaped substring (chars 3-12 of a GSTIN
# are a PAN), so GSTIN must be redacted first or the PAN pattern would later
# match what's left of an already-redacted GSTIN. IFSC/PAN are checked before
# the loose digit-based patterns (bank account, mobile) for the same reason —
# most-specific-shape first, most-permissive last.
PII_PATTERNS: list[PiiPattern] = [
    # GSTIN: 2-digit state code + 10-char PAN + 1 entity code + fixed 'Z' + 1 checksum char.
    PiiPattern("GSTIN", re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b")),
    # PAN: 5 letters + 4 digits + 1 letter.
    PiiPattern("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    # IFSC: 4 letters + fixed '0' + 6 alphanumeric.
    PiiPattern("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    # Bank account number: no universal shape, so anchor on a preceding label
    # (A/C, Account No, ...) rather than matching bare digit runs, which would
    # also catch invoice numbers, HSN codes, and amounts.
    PiiPattern(
        "BANK_ACCOUNT",
        re.compile(
            r"(?:bank\s+)?a/?c\.?\s*(?:no\.?|number)?\s*[:\-]?\s*\d{9,18}"
            r"|account\s*(?:no\.?|number)?\s*[:\-]?\s*\d{9,18}",
            re.IGNORECASE,
        ),
    ),
    # Mobile: either label-anchored ("Mobile:", "Ph:", "+91 ...") or the
    # standalone Indian mobile shape (10 digits starting 6-9, optional +91) —
    # deliberately not a bare "any 10-12 digit run" match, which would also
    # catch invoice/PO numbers and amounts on most bills.
    PiiPattern(
        "MOBILE",
        re.compile(
            r"(?:mobile|ph|phone|contact|tel|cell)\.?\s*(?:no\.?|number)?\s*[:\-]?\s*"
            r"(?:\+?91[\-\s]?)?[6-9]\d{9}"
            r"|\b(?:\+91[\-\s]?)?[6-9]\d{9}\b",
            re.IGNORECASE,
        ),
    ),
    PiiPattern("EMAIL", re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")),
]


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Applies every pattern in order, replacing each match with a
    `[REDACTED:<LABEL>]` placeholder. Redaction is uniform and final for
    every field here, GSTIN included — none of it is reattached from the
    regex match afterward (that was considered for GSTIN specifically and
    explicitly rejected: simpler to treat every PII type the same way).
    Returns the redacted text plus a per-label match count, so the caller can
    record what was stripped for audit/transparency without ever storing the
    matched values themselves."""
    counts: dict[str, int] = {}
    for p in PII_PATTERNS:
        text, n = p.pattern.subn(f"[REDACTED:{p.label}]", text)
        if n:
            counts[p.label] = counts.get(p.label, 0) + n
    return text, counts
