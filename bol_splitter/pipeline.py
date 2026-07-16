"""End-to-end: scanned batch PDF -> individual named PDFs filed by month."""

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

from .buckets import company_abbrev
from .config import Candidates
from .match import match_name
from .naming import (
    NEEDS_REVIEW_DIR,
    build_filename,
    folder_path,
    unique_path,
)
from .ocr import ocr_date_region, ocr_title_band, ocr_top
from .parse import parse_date, parse_page
from .render import render_pages
from .split import build_groups
from .store_lookup import StoreMatcher
from .writer import write_pages


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
    images = render_pages(pdf_path, dpi=dpi)
    page_fields = []
    for img in images:
        pf = parse_page(ocr_top(img), ocr_title_band(img))
        if pf.date is None:  # fallback: zoomed OCR of the date corner
            pf.date = parse_date(ocr_date_region(img))
        page_fields.append(pf)
    groups = build_groups(page_fields)

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
        write_pages(pdf_path, group.page_indices, output_path)

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

    _write_manifest(out_dir, pdf_path, results)
    return BatchResult(documents=results)


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
