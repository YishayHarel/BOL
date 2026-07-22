"""Optical character recognition via Tesseract (Apache-2.0)."""

import pytesseract
from PIL import Image, ImageOps


def _prep(image: Image.Image) -> Image.Image:
    """Grayscale + auto-contrast — helps Tesseract on faint/uneven scans."""
    return ImageOps.autocontrast(ImageOps.grayscale(image))


def ocr_page(image: Image.Image) -> str:
    """Return the full plain-text OCR of a page image."""
    return pytesseract.image_to_string(_prep(image))


def date_region_texts(image: Image.Image, left: float = 0.55) -> list[str]:
    """Ensemble OCR of the top-left corner where 'DATE:' lives — a fallback when
    the date can't be read from the normal top crop.

    The 'DATE:' line sits in a thin strip just above the black 'SHIPPING FROM'
    bar. Tesseract is very sensitive to the exact crop height and segmentation
    mode here — the same legible date reads correctly at one combination and
    fails at another. So we OCR several crop heights x several modes and return
    every result; the caller takes the majority date across them, which is far
    more stable than any single read.
    """
    width, height = image.size
    texts = []
    for top in (0.11, 0.13, 0.15):
        crop = image.crop((0, 0, int(width * left), int(height * top)))
        crop = _prep(crop).resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
        for psm in (6, 4, 3, 11):
            texts.append(pytesseract.image_to_string(crop, config=f"--psm {psm}"))
    return texts


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
