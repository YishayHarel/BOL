"""Write grouped page ranges to individual PDFs using pypdf (BSD)."""

from pypdf import PdfReader, PdfWriter


def write_pages(source_pdf_path: str, page_indices: list[int], output_path: str) -> None:
    reader = PdfReader(source_pdf_path)
    writer = PdfWriter()
    for index in page_indices:
        writer.add_page(reader.pages[index])
    with open(output_path, "wb") as f:
        writer.write(f)
