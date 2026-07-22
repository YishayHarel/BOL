"""Build output filenames and folder paths, with duplicate-safe naming."""

import os
import re
from typing import Optional

# Characters illegal in Windows / Egnyte filenames.
_ILLEGAL = re.compile(r'[\\/:*?"<>|]+')

NEEDS_REVIEW_DIR = "Needs Review"


def sanitize(value: str) -> str:
    value = _ILLEGAL.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def year_month(date: Optional[str]) -> Optional[tuple[str, str]]:
    """'7/6/2026' -> ('2026', '07'). None if the date is unreadable."""
    if not date:
        return None
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date.strip())
    if not match:
        return None
    month, _day, year = match.groups()
    return year, f"{int(month):02d}"


def folder_path(
    out_dir: str, company_abbrev: str, customer: str, date: Optional[str]
) -> Optional[str]:
    """Company / Customer / YEAR / MONTH. None if the date can't be read.
    (A Warehouse level will slot in between Company and Customer once the email
    intake supplies it.)"""
    ym = year_month(date)
    if ym is None:
        return None
    year, month = ym
    return os.path.join(out_dir, sanitize(company_abbrev), sanitize(customer), year, month)


def _filename_date(date: Optional[str]) -> str:
    if not date:
        return "UnknownDate"
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date.strip())
    if not match:
        return sanitize(date)
    month, day, year = match.groups()
    return f"{int(month)}-{int(day)}-{year}"


def build_filename(company: Optional[str], customer: Optional[str], date: Optional[str]) -> str:
    company_part = sanitize(company) if company else "UnknownCompany"
    customer_part = sanitize(customer) if customer else "UnknownCustomer"
    return f"{company_part} - {customer_part} - {_filename_date(date)}.pdf"


def unique_path(directory: str, filename: str) -> str:
    """Return a path in `directory` that does not collide with an existing file.

    First file keeps its name; subsequent identical names get ' (2)', ' (3)', ...
    This is what lets us drop the BOL# yet never overwrite a distinct shipment.
    """
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    counter = 1
    while os.path.exists(candidate):
        counter += 1
        candidate = os.path.join(directory, f"{base} ({counter}){ext}")
    return candidate
