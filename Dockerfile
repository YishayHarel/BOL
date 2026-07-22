FROM python:3.12-slim

# System dependencies for OCR + PDF rendering (open source, run as binaries):
#   tesseract-ocr  -> OCR engine (Apache-2.0)
#   poppler-utils  -> pdftoppm, used by pdf2image to rasterize pages (GPL binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bol_splitter/ ./bol_splitter/

# Input batch and output folder are mounted at runtime (see docker-compose.yml).
ENTRYPOINT ["python", "-m", "bol_splitter.cli"]
