"""Render PDF pages to images for OCR only.

Uses pdf2image (MIT) + Poppler (invoked as a subprocess binary). The rendered
images are fed to Tesseract; the actual PDF splitting/merging is done separately
by pypdf against the original file, so no image quality is lost in the output.
"""

from pdf2image import convert_from_path
from PIL import Image


def render_pages(pdf_path: str, dpi: int = 300) -> list[Image.Image]:
    # 300 DPI is the sweet spot for Tesseract accuracy on printed forms.
    return convert_from_path(pdf_path, dpi=dpi)
