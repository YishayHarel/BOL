"""End-to-end: scanned batch PDF -> individual named PDFs filed by month."""

import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Optional

from pypdf import PdfReader, PdfWriter

from .buckets import company_abbrev
from .config import Candidates
from .match import match_name
from .naming import (
    NEEDS_REVIEW_DIR,
    build_filename,
    folder_path,
    unique_path,
)
from .ocr import date_region_texts, ocr_title_band, ocr_top
from .parse import majority_date, parse_page
from .render import iter_pages, page_count
from .split import build_groups
from .store_lookup import StoreMatcher
from .writer import write_pages


def _new_tmp() -> str:
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    return path


def _repair_pdf(src: str) -> str:
    """Rebuild a malformed PDF (broken xref/trailer some scanners produce) into a
    clean copy Poppler can render. Tries pypdf first (fast, fixes complete-but-
    malformed files), then Ghostscript (recovers more damaged files). Raises if
    neither produces a readable PDF (e.g. a truncated file with no intact data).
    Returns the repaired temp path."""
    # 1) pypdf — rebuilds the xref for complete-but-malformed files.
    dst = _new_tmp()
    try:
        reader = PdfReader(src, strict=False)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with open(dst, "wb") as f:
            writer.write(f)
        page_count(dst)  # confirm Poppler can now read it
        return dst
    except Exception:
        if os.path.exists(dst):
            os.remove(dst)

    # 2) Ghostscript — heavier recovery; salvages what intact data remains.
    dst = _new_tmp()
    subprocess.run(
        ["gs", "-o", dst, "-sDEVICE=pdfwrite", "-dPDFSTOPONERROR=false", "-dQUIET",
         "-dBATCH", "-dNOPAUSE", src],
        check=False, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        page_count(dst)  # raises if gs produced nothing usable
        return dst
    except Exception:
        if os.path.exists(dst):
            os.remove(dst)
        raise ValueError("PDF is damaged and could not be repaired (file may be truncated)")


@dataclass
class DocumentResult:
    source_pages: list[int]        # 1-based page numbers in the batch
    company: Optional[str]
    customer: Optional[str]
    date: Optional[str]
    output_path: str
    needs_review: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class BatchResult:
    documents: list[DocumentResult]


def process_batch(
    pdf_path: str,
    out_dir: str,
    candidates: Candidates,
    store_matcher: StoreMatcher,
    dpi: int = 300,
) -> BatchResult:
    # If the PDF is malformed (broken xref/trailer), repair it to a clean copy
    # so Poppler can render it; use that copy for both rendering and splitting.
    work_path = pdf_path
    repaired = None
    try:
        page_count(work_path)
    except Exception:
        repaired = _repair_pdf(pdf_path)
        work_path = repaired

    try:
        page_fields = []
        for img in iter_pages(work_path, dpi=dpi):  # one page in memory at a time
            pf = parse_page(ocr_top(img), ocr_title_band(img))
            if pf.date is None:  # fallback: ensemble OCR of the date corner + majority vote
                pf.date = majority_date(date_region_texts(img))
            page_fields.append(pf)
            img.close()
        groups = build_groups(page_fields)
        results = _split_and_file(work_path, out_dir, candidates, store_matcher, groups)
    finally:
        if repaired and os.path.exists(repaired):
            os.remove(repaired)

    _write_manifest(out_dir, pdf_path, results)
    return BatchResult(documents=results)


def _split_and_file(work_path, out_dir, candidates, store_matcher, groups):

    results: list[DocumentResult] = []
    for group in groups:
        header_text = group.first.top_text
        company = match_name(header_text, candidates.companies, candidates.fuzzy_threshold)
        # Customer bucket comes from the store-dump lookup (falls back to OTHER).
        bucket = store_matcher.resolve(group.first.ship_to_name, fallback_text=header_text)
        # Borrow the date from any page in the group if the first page's failed.
        date = group.first.date or next((p.date for p in group.pages if p.date), None)

        reasons = list(group.warnings)
        if company.canonical is None:
            reasons.append(f"company not confidently matched (best score {company.score})")
        if date is None:
            reasons.append("date unreadable — cannot determine year/month folder")

        # OTHER is a valid destination, not a review reason. Review only when the
        # company or the date is missing, or the split flagged something.
        needs_review = bool(reasons)
        abbrev = company_abbrev(company.canonical) if company.canonical else "UnknownCo"
        if needs_review:
            target_dir = os.path.join(out_dir, NEEDS_REVIEW_DIR)
        else:
            target_dir = folder_path(out_dir, abbrev, bucket, date)
        os.makedirs(target_dir, exist_ok=True)

        filename = build_filename(abbrev, bucket, date)
        output_path = unique_path(target_dir, filename)
        write_pages(work_path, group.page_indices, output_path)

        results.append(
            DocumentResult(
                source_pages=[i + 1 for i in group.page_indices],
                company=company.canonical,
                customer=bucket,
                date=date,
                output_path=output_path,
                needs_review=needs_review,
                reasons=reasons,
            )
        )

    return results


def _write_manifest(out_dir: str, pdf_path: str, results: list[DocumentResult]) -> None:
    manifest = {
        "source": os.path.basename(pdf_path),
        "document_count": len(results),
        "needs_review_count": sum(1 for r in results if r.needs_review),
        "documents": [asdict(r) for r in results],
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
