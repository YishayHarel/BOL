"""Rule-based extraction of structured fields from OCR text. No LLM."""

import re
from dataclasses import dataclass
from typing import Optional

# "PAGE 1 OF 2" — tolerate OCR reading 'O' as '0'/'Q' and missing spaces.
_PAGE_RE = re.compile(r"PAGE\s*(\d+)\s*[O0Q]F\s*(\d+)", re.IGNORECASE)
# "DATE: 7/6/2026" — tolerate ':'/'.'/',' after DATE and /-. as date separators.
_DATE_RE = re.compile(
    r"DATE\s*[:.,]?\s*(\d{1,2}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{2,4})", re.IGNORECASE
)
_MORE_PAGES_RE = re.compile(r"MORE\s*PAGE", re.IGNORECASE)
# The long printed number, labelled "BILL OF LADING NUMBER:" on headers and
# "BILL OF LADING#" on supplement pages.
_BOL_NUM_RE = re.compile(
    r"BILL\s+OF\s+LADING\s*(?:NUMBER|#)\s*:?\s*([0-9][0-9 ]{9,})", re.IGNORECASE
)

# Document types, by the title printed at the top of the page.
DOC_BOL = "bol"                # "BILL OF LADING" — starts a new order
DOC_MASTER = "master_bol"      # "MASTER BILL OF LADING" — starts a new order
DOC_SUPPLEMENT = "supplement"  # "SUPPLEMENT TO THE BILL OF LADING" — continuation
DOC_MANIFEST = "manifest"      # "BOL Manifest Report" — its own document
DOC_UNKNOWN = "unknown"

# doc types that begin a brand-new document
NEW_DOC_TYPES = {DOC_BOL, DOC_MASTER, DOC_MANIFEST}


@dataclass
class PageFields:
    doc_type: str
    bol_number: Optional[str]
    has_shipping_block: bool  # True if the page shows SHIP FROM / SHIP TO (a BOL front page)
    ship_to_name: Optional[str]  # best-effort extraction of the SHIP TO name
    page_current: Optional[int]
    page_total: Optional[int]
    more_pages_attached: bool
    date: Optional[str]
    top_text: str  # full OCR of the page top, used for fuzzy name matching


def _normalize_date(raw: str) -> str:
    nums = re.findall(r"\d+", raw)
    if len(nums) < 3:
        return raw.strip()
    month, day, year = nums[0], nums[1], nums[2]
    if len(year) == 2:
        year = "20" + year
    return f"{int(month)}/{int(day)}/{int(year)}"


def parse_date(text: str) -> Optional[str]:
    m = _DATE_RE.search(text)
    return _normalize_date(m.group(1)) if m else None


def _extract_ship_to(top_text: str) -> Optional[str]:
    """Best-effort: find the NAME value inside the SHIP TO block."""
    lines = [ln.strip() for ln in top_text.splitlines()]
    for i, line in enumerate(lines):
        if "SHIP TO" in line.upper():
            for j in range(i, min(i + 4, len(lines))):
                m = re.search(r"NAME\s*:?\s*(.+)", lines[j], re.IGNORECASE)
                if m:
                    value = re.split(r"\bLOCATION\b", m.group(1), flags=re.IGNORECASE)[0]
                    value = value.strip(" :.-")
                    if value:
                        return value
    return None


def _detect_doc_type(text: str) -> str:
    upper = re.sub(r"\s+", " ", text.upper())
    # Order matters: "SUPPLEMENT ..." and "MASTER ..." both contain "BILL OF LADING".
    # Match "SUPPLEMENT" loosely — the full title often OCRs imperfectly.
    if "SUPPLEMENT" in upper:
        return DOC_SUPPLEMENT
    if "MANIFEST" in upper:  # "BOL Manifest Report"
        return DOC_MANIFEST
    if "MASTER BILL OF LADING" in upper:
        return DOC_MASTER
    if "BILL OF LADING" in upper:
        return DOC_BOL
    return DOC_UNKNOWN


def parse_page(top_text: str, title_text: str) -> PageFields:
    """`title_text` is OCR of the thin top strip (for the title / doc type);
    `top_text` is OCR of the wider top crop (for the data fields)."""
    page_match = _PAGE_RE.search(top_text)
    bol_match = _BOL_NUM_RE.search(top_text)
    upper = top_text.upper()
    has_shipping_block = any(k in upper for k in ("SHIP TO", "SHIPPING FROM", "SHIP FROM"))
    return PageFields(
        doc_type=_detect_doc_type(title_text),
        bol_number=re.sub(r"\s", "", bol_match.group(1)) if bol_match else None,
        has_shipping_block=has_shipping_block,
        ship_to_name=_extract_ship_to(top_text),
        page_current=int(page_match.group(1)) if page_match else None,
        page_total=int(page_match.group(2)) if page_match else None,
        more_pages_attached=bool(_MORE_PAGES_RE.search(top_text)),
        date=parse_date(top_text),
        top_text=top_text,
    )
