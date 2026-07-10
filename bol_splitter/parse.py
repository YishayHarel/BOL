"""Rule-based extraction of structured fields from OCR text. No LLM."""

import re
from dataclasses import dataclass
from typing import Optional

# "PAGE 1 OF 2" — tolerate OCR reading 'O' as '0'/'Q' and missing spaces.
_PAGE_RE = re.compile(r"PAGE\s*(\d+)\s*[O0Q]F\s*(\d+)", re.IGNORECASE)
# "DATE: 7/6/2026"
_DATE_RE = re.compile(r"DATE\s*:?\s*(\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4})", re.IGNORECASE)
_MORE_PAGES_RE = re.compile(r"MORE\s*PAGE", re.IGNORECASE)


@dataclass
class PageFields:
    page_current: Optional[int]
    page_total: Optional[int]
    more_pages_attached: bool
    date: Optional[str]
    document_title: Optional[str]
    top_text: str  # full OCR of the page top, used for fuzzy name matching


def _normalize_date(raw: str) -> str:
    parts = [p.strip() for p in raw.split("/")]
    month, day, year = parts
    if len(year) == 2:
        year = "20" + year
    return f"{int(month)}/{int(day)}/{int(year)}"


def _detect_title(text: str) -> Optional[str]:
    upper = re.sub(r"\s+", " ", text.upper())
    if "SUPPLEMENT TO THE BILL OF LADING" in upper:
        return "SUPPLEMENT TO THE BILL OF LADING"
    if "MASTER BILL OF LADING" in upper:
        return "MASTER BILL OF LADING"
    if "BILL OF LADING" in upper:
        return "BILL OF LADING"
    return None


def parse_page(top_text: str) -> PageFields:
    page_match = _PAGE_RE.search(top_text)
    date_match = _DATE_RE.search(top_text)
    return PageFields(
        page_current=int(page_match.group(1)) if page_match else None,
        page_total=int(page_match.group(2)) if page_match else None,
        more_pages_attached=bool(_MORE_PAGES_RE.search(top_text)),
        date=_normalize_date(date_match.group(1)) if date_match else None,
        document_title=_detect_title(top_text),
        top_text=top_text,
    )
