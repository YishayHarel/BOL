"""Optical character recognition via Tesseract (Apache-2.0)."""

import pytesseract
from PIL import Image, ImageOps


def _prep(image: Image.Image) -> Image.Image:
    """Grayscale + auto-contrast — helps Tesseract on faint/uneven scans."""
    return ImageOps.autocontrast(ImageOps.grayscale(image))


def ocr_page(image: Image.Image) -> str:
    """Return the full plain-text OCR of a page image."""
    return pytesseract.image_to_string(_prep(image))


def ocr_date_region(image: Image.Image, top: float = 0.14, left: float = 0.45) -> str:
    """Zoomed, cleaned OCR of the top-left corner where 'DATE:' lives — a
    fallback when the date can't be read from the normal top crop."""
    width, height = image.size
    crop = image.crop((0, 0, int(width * left), int(height * top)))
    crop = _prep(crop).resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
    return pytesseract.image_to_string(crop, config="--psm 6")


def ocr_title_band(image: Image.Image, fraction: float = 0.20) -> str:
    """OCR only the thin strip at the very top of the page, where the big
    centered title lives ("BILL OF LADING" / "MASTER BILL OF LADING" /
    "SUPPLEMENT TO THE BILL OF LADING" / "BOL Manifest Report"). Reading just
    this strip avoids the "Master Bill of Lading: with attached..." checkbox
    text printed lower on every page, which otherwise confuses title detection.
    """
    width, height = image.size
    band = image.crop((0, 0, width, int(height * fraction)))
    return pytesseract.image_to_string(_prep(band))


def ocr_top(image: Image.Image, fraction: float = 0.45) -> str:
    """OCR only the top portion of the page.

    All the fields we care about (title, DATE, PAGE X OF Y, MORE PAGES banner,
    SHIPPING FROM, SHIP TO) live in the top ~45% of the form, so cropping there
    reduces noise from the freight tables below.
    """
    width, height = image.size
    top = image.crop((0, 0, width, int(height * fraction)))
    return pytesseract.image_to_string(_prep(top))
