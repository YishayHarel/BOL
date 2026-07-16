"""Render PDF pages to images for OCR — one page at a time to stay low-memory.

Loading every page of a 60-page scan at 300 DPI at once uses enough RAM to get
the container OOM-killed, so we render and hand back a single page at a time and
let the caller discard each image before the next is produced.
"""

from collections.abc import Iterator

from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image


def page_count(pdf_path: str) -> int:
    return int(pdfinfo_from_path(pdf_path)["Pages"])


def iter_pages(pdf_path: str, dpi: int = 300) -> Iterator[Image.Image]:
    for p in range(1, page_count(pdf_path) + 1):
        images = convert_from_path(pdf_path, dpi=dpi, first_page=p, last_page=p)
        yield images[0]


def render_pages(pdf_path: str, dpi: int = 300) -> list[Image.Image]:
    # Kept for ad-hoc use; the pipeline uses iter_pages to bound memory.
    return list(iter_pages(pdf_path, dpi=dpi))
