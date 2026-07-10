"""End-to-end: scanned batch PDF -> individual named PDFs filed by month."""

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

from .config import Candidates
from .match import match_name
from .naming import (
    NEEDS_REVIEW_DIR,
    build_filename,
    month_folder,
    unique_path,
)
from .ocr import ocr_top
from .parse import parse_page
from .render import render_pages
from .split import build_groups
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


def process_batch(
    pdf_path: str,
    out_dir: str,
    candidates: Candidates,
    dpi: int = 300,
) -> list[DocumentResult]:
    images = render_pages(pdf_path, dpi=dpi)
    page_fields = [parse_page(ocr_top(img)) for img in images]
    groups = build_groups(page_fields)

    results: list[DocumentResult] = []
    for group in groups:
        header_text = group.first.top_text
        company = match_name(header_text, candidates.companies, candidates.fuzzy_threshold)
        customer = match_name(header_text, candidates.customers, candidates.fuzzy_threshold)
        date = group.first.date

        reasons = list(group.warnings)
        if company.canonical is None:
            reasons.append(f"company not confidently matched (best score {company.score})")
        if customer.canonical is None:
            reasons.append(f"customer not confidently matched (best score {customer.score})")
        month = month_folder(date)
        if month is None:
            reasons.append("could not determine month folder from date")

        needs_review = bool(reasons)
        subdir = NEEDS_REVIEW_DIR if needs_review else month
        target_dir = os.path.join(out_dir, subdir)
        os.makedirs(target_dir, exist_ok=True)

        filename = build_filename(company.canonical, customer.canonical, date)
        output_path = unique_path(target_dir, filename)
        write_pages(pdf_path, group.page_indices, output_path)

        results.append(
            DocumentResult(
                source_pages=[i + 1 for i in group.page_indices],
                company=company.canonical,
                customer=customer.canonical,
                date=date,
                output_path=output_path,
                needs_review=needs_review,
                reasons=reasons,
            )
        )

    _write_manifest(out_dir, pdf_path, results)
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
