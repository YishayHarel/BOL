"""Optical character recognition via Tesseract (Apache-2.0)."""

import pytesseract
from PIL import Image


def ocr_page(image: Image.Image) -> str:
    """Return the full plain-text OCR of a page image."""
    return pytesseract.image_to_string(image)


def ocr_top(image: Image.Image, fraction: float = 0.45) -> str:
    """OCR only the top portion of the page.

    All the fields we care about (title, DATE, PAGE X OF Y, MORE PAGES banner,
    SHIPPING FROM, SHIP TO) live in the top ~45% of the form, so cropping there
    reduces noise from the freight tables below.
    """
    width, height = image.size
    top = image.crop((0, 0, width, int(height * fraction)))
    return pytesseract.image_to_string(top)
